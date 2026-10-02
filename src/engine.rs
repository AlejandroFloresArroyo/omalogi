use crate::{
    backend::{self, Device},
    config::{self, Config, HARDWARE},
    rules,
    storage::{self, Paths},
};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};
use std::{collections::BTreeMap, fs, path::Path};

const SERVICE: &str = "omalogi-solaar.service";
const PYTHON: &str = include_str!("../scripts/solaar-state.py");
const SCALAR: &str = include_str!("../scripts/solaar-scalar.py");

#[derive(Clone, Serialize, Deserialize)]
struct Snapshot {
    device: Device,
    persisted: Value,
    rules: String,
    keys: Vec<String>,
    buttons: Vec<String>,
}

#[derive(Clone, Serialize, Deserialize)]
struct State {
    baseline: Snapshot,
    config: Config,
    applied: bool,
    pending: bool,
}

pub struct Engine {
    pub paths: Paths,
}

impl Engine {
    pub fn new() -> Result<Self, String> {
        Ok(Self {
            paths: Paths::system()?,
        })
    }
    pub fn draft(&self) -> Result<Config, String> {
        if self.paths.file("profile.json").exists() {
            return storage::read(&self.paths.file("profile.json"));
        }
        let _lock = self.paths.lock()?;
        let device = backend::discover()?.remove(0);
        Ok(default_config(&device))
    }
    pub fn save(&self, config: &Config) -> Result<(), String> {
        config.validate()?;
        let _lock = self.paths.lock()?;
        storage::save(&self.paths.file("profile.json"), config)
    }
    pub fn daemon_active(&self) -> bool {
        backend::run("systemctl", &["--user", "is-active", SERVICE], None).is_ok()
    }
    fn service(&self, command: &str) -> Result<(), String> {
        backend::run("systemctl", &["--user", command, SERVICE], None).map(|_| ())
    }
    fn persistence(
        &self,
        op: &str,
        id: &str,
        keys: &[String],
        buttons: &[String],
        original: &Value,
    ) -> Result<Value, String> {
        let request = json!({"op":op,"path":self.paths.solaar.join("config.yaml"),"id":id,"keys":keys,"buttons":buttons,"original":original});
        let result = backend::run("python3", &["-c", PYTHON], Some(&request.to_string()))?;
        serde_json::from_str(&result).map_err(|e| e.to_string())
    }
    fn rules_text(&self) -> Result<String, String> {
        let path = self.paths.solaar.join("rules.yaml");
        if !path.exists() {
            return Ok(String::new());
        }
        fs::read_to_string(path).map_err(|e| e.to_string())
    }
    fn write_rules(&self, block: &str) -> Result<(), String> {
        let (_, outside) = rules::split(&self.rules_text()?)?;
        let text = format!("{block}{outside}");
        rules::validate(&text)?;
        storage::atomic(&self.paths.solaar.join("rules.yaml"), text.as_bytes())
    }
    fn snapshot(&self, device: Device) -> Result<Snapshot, String> {
        let persisted = self.persistence("read", &device.id, &[], &[], &Value::Null)?;
        let (rules, _) = rules::split(&self.rules_text()?)?;
        let keys = HARDWARE
            .iter()
            .copied()
            .chain([
                "hires-scroll-mode",
                "lowres-scroll-mode",
                "thumb-scroll-mode",
            ])
            .filter(|k| device.settings.contains_key(*k))
            .map(String::from)
            .collect();
        let buttons = ["button.back", "button.forward", "gesture"]
            .iter()
            .filter_map(|e| backend::button(&device, e))
            .filter_map(|n| button_id(&n).map(|id| id.to_string()))
            .collect();
        Ok(Snapshot {
            device,
            persisted,
            rules,
            keys,
            buttons,
        })
    }
    fn restore_snapshot(&self, snapshot: &Snapshot) -> Result<(), String> {
        let mut hardware = BTreeMap::new();
        for key in &snapshot.keys {
            let original = if key == "smart-shift"
                && snapshot
                    .device
                    .settings
                    .get("scroll-ratchet")
                    .is_some_and(|s| s.value == "Freespinning")
            {
                snapshot.persisted["smart-shift"]
                    .as_u64()
                    .filter(|n| (1..=50).contains(n))
                    .map(|n| n.to_string())
            } else {
                None
            };
            hardware.insert(
                key.clone(),
                original.unwrap_or_else(|| snapshot.device.settings[key].value.clone()),
            );
        }
        backend::write_settings(&snapshot.device, &hardware)?;
        for event in ["button.back", "button.forward", "gesture"] {
            if let Some(button) = backend::button(&snapshot.device, event) {
                backend::set_button(
                    &snapshot.device.id,
                    &button,
                    &baseline_button(snapshot, &button),
                )?;
            }
        }
        self.persistence(
            "restore",
            &snapshot.device.id,
            &snapshot.keys,
            &snapshot.buttons,
            &snapshot.persisted,
        )?;
        self.write_rules(&snapshot.rules)?;
        verify_snapshot(snapshot)
    }
    pub fn apply(&self, config: Config, binary: &Path) -> Result<Value, String> {
        config.validate()?;
        let _lock = self.paths.lock()?;
        let draft_before = if self.paths.file("profile.json").exists() {
            Some(fs::read(self.paths.file("profile.json")).map_err(|e| e.to_string())?)
        } else {
            None
        };
        let old: Option<State> = if self.paths.file("state.json").exists() {
            Some(storage::read(&self.paths.file("state.json"))?)
        } else {
            None
        };
        if old.as_ref().is_some_and(|s| s.pending) {
            return Err(
                "There is an incomplete operation. Run Restore before applying again".into(),
            );
        }
        if old
            .as_ref()
            .is_some_and(|s| s.applied && s.config.device_id != config.device_id)
        {
            return Err("Restore the current mouse before selecting another".into());
        }
        if let Some(ref state) = old
            && state.applied
            && incremental_eligible(&state.config, &config)
        {
            return self.apply_incremental(config, state, draft_before, binary);
        }
        let device = backend::device(&config.device_id, &config.device_name)?;
        backend::validate_hardware(&device, &config.hardware)?;
        let block = rules::generate(&config, &device, binary)?;
        let (_, outside) = rules::split(&self.rules_text()?)?;
        rules::validate(&format!("{block}{outside}"))?;
        let active = self.daemon_active();
        if !active && backend::run("pgrep", &["-x", "solaar"], None).is_ok() {
            return Err(
                "Solaar is running outside the Omalogi service. Close it and apply again".into(),
            );
        }
        self.service("stop")?;
        let transaction = self.snapshot(backend::device(&config.device_id, &config.device_name)?);
        let previous = match transaction {
            Ok(s) => s,
            Err(e) => {
                if active {
                    let _ = self.service("start");
                }
                return Err(e);
            }
        };
        let baseline = old
            .as_ref()
            .filter(|s| s.applied)
            .map(|s| s.baseline.clone())
            .unwrap_or_else(|| previous.clone());
        let mut state = State {
            baseline: baseline.clone(),
            config: config.clone(),
            applied: false,
            pending: true,
        };
        storage::save(&self.paths.file("state.json"), &state)?;
        let result = (|| {
            if block != previous.rules {
                self.write_rules(&block)?;
            }
            // Keep the transaction/rollback and full verification, but write only changed values.
            let changed = changed_hardware(&previous, &config.hardware);
            backend::write_settings(&previous.device, &changed)?;
            for event in ["button.back", "button.forward", "gesture"] {
                let custom = if event == "gesture" {
                    config.gestures()
                } else {
                    config.action(event) != "native"
                };
                if let Some(button) = backend::button(&device, event) {
                    let value = if custom {
                        if event == "gesture" {
                            "Mouse Gestures".into()
                        } else {
                            "Diverted".into()
                        }
                    } else {
                        baseline_button(&baseline, &button)
                    };
                    let physical = if value == "Regular" {
                        "Regular"
                    } else {
                        "Diverted"
                    };
                    if baseline_button(&previous, &button) != value
                        || previous.device.buttons.get(&button).map(String::as_str)
                            != Some(physical)
                    {
                        backend::set_button(&device.id, &button, &value)?;
                    }
                } else if custom {
                    return Err(format!("The mouse does not support {event}"));
                }
            }
            for (thumb, names) in [
                (false, &["hires-scroll-mode", "lowres-scroll-mode"][..]),
                (true, &["thumb-scroll-mode"][..]),
            ] {
                if let Some(key) = names.iter().find(|k| device.settings.contains_key(**k)) {
                    let value = if config.wheel(thumb) {
                        "true"
                    } else {
                        &baseline.device.settings[*key].value
                    };
                    if !backend::equal_value(&previous.device.settings[*key].value, value) {
                        backend::set(&device.id, key, value)?;
                    }
                } else if config.wheel(thumb) {
                    return Err("The mouse does not support actions for that wheel".into());
                }
            }
            self.persistence("sensitive", &device.id, &previous.keys, &[], &Value::Null)?;
            verify_profile(&config, &baseline)?;
            state.applied = true;
            state.pending = false;
            storage::save(&self.paths.file("state.json"), &state)?;
            storage::save(&self.paths.file("profile.json"), &config)?;
            self.service("start")?;
            if !self.daemon_active() {
                return Err("Event capture did not start".into());
            }
            Ok(
                json!({"ok":true,"message":"Settings applied and verified on the mouse","config":config}),
            )
        })();
        if let Err(error) = result {
            let _ = self.service("stop");
            if let Err(rollback) = self.restore_snapshot(&previous) {
                state.pending = true;
                state.applied = false;
                let _ = storage::save(&self.paths.file("state.json"), &state);
                if active {
                    let _ = self.service("start");
                }
                return Err(format!(
                    "{error}. Recovery needs attention: {rollback}. Run Restore"
                ));
            }
            if let Some(old) = old {
                storage::save(&self.paths.file("state.json"), &old)?;
            } else {
                let _ = fs::remove_file(self.paths.file("state.json"));
            }
            if let Some(bytes) = draft_before {
                storage::atomic(&self.paths.file("profile.json"), &bytes)?;
            } else if self.paths.file("profile.json").exists() {
                fs::remove_file(self.paths.file("profile.json")).map_err(|e| e.to_string())?;
            }
            if active {
                self.service("start")?;
            }
            return Err(format!("{error}. Previous settings were restored"));
        }
        result
    }
    // Existing applied profiles can change simple settings without rediscovering all features.
    // The scalar adapter captures and verifies only touched physical values in one connection.
    fn apply_incremental(
        &self,
        config: Config,
        old: &State,
        draft_before: Option<Vec<u8>>,
        binary: &Path,
    ) -> Result<Value, String> {
        let values: BTreeMap<String, String> = config
            .hardware
            .iter()
            .filter(|(key, value)| old.config.hardware.get(*key) != Some(*value))
            .map(|(key, value)| (key.clone(), value.clone()))
            .collect();
        let keys: Vec<String> = values.keys().cloned().collect();
        let block = rules::generate(&config, &old.baseline.device, binary)?;
        let (previous_rules, outside) = rules::split(&self.rules_text()?)?;
        rules::validate(&format!("{block}{outside}"))?;
        let active = self.daemon_active();
        if !active && backend::run("pgrep", &["-x", "solaar"], None).is_ok() {
            return Err(
                "Solaar is running outside the Omalogi service. Close it and apply again".into(),
            );
        }
        self.service("stop")?;
        let persisted = match self.persistence("read", &config.device_id, &[], &[], &Value::Null) {
            Ok(p) => p,
            Err(e) => {
                if active {
                    let _ = self.service("start");
                }
                return Err(e);
            }
        };
        let mut state = old.clone();
        state.config = config.clone();
        state.pending = true;
        state.applied = false;
        if let Err(e) = storage::save(&self.paths.file("state.json"), &state) {
            if active {
                let _ = self.service("start");
            }
            return Err(e);
        }
        let mut physical_before: Option<Value> = None;
        let mut uncertain = false;
        let result = (|| {
            if !values.is_empty() {
                let response =
                    scalar(&config.device_id, &json!(values)).inspect_err(|_| uncertain = true)?;
                if !response["ok"].as_bool().unwrap_or(false) {
                    uncertain = response["rolled_back"] != true;
                    return Err(response["error"]
                        .as_str()
                        .unwrap_or("The mouse setting failed")
                        .to_string());
                }
                physical_before = Some(response["before"].clone());
                let persisted_values: Value = values
                    .iter()
                    .map(|(key, value)| {
                        let v = match value.as_str() {
                            "true" => json!(true),
                            "false" => json!(false),
                            _ => json!(value.parse::<u32>().unwrap_or_default()),
                        };
                        (key.clone(), v)
                    })
                    .collect::<serde_json::Map<String, Value>>()
                    .into();
                self.persistence("values", &config.device_id, &keys, &[], &persisted_values)?;
            }
            if block != previous_rules {
                self.write_rules(&block)?;
            }
            storage::save(&self.paths.file("profile.json"), &config)?;
            state.pending = false;
            state.applied = true;
            storage::save(&self.paths.file("state.json"), &state)?;
            self.service("start")?;
            if !self.daemon_active() {
                return Err("Event capture did not start".into());
            }
            Ok(json!({"ok":true,"message":"Cambio aplicado y verificado","config":config}))
        })();
        if let Err(error) = result {
            let _ = self.service("stop");
            if !uncertain {
                let rollback = (|| {
                    if let Some(before) = physical_before {
                        let response = scalar(&config.device_id, &before)?;
                        if response["ok"] != true {
                            return Err("Hardware rollback was not confirmed".to_string());
                        }
                    }
                    self.persistence("restore", &config.device_id, &keys, &[], &persisted)?;
                    self.write_rules(&previous_rules)?;
                    storage::save(&self.paths.file("state.json"), old)?;
                    if let Some(bytes) = draft_before {
                        storage::atomic(&self.paths.file("profile.json"), &bytes)?;
                    }
                    if active {
                        self.service("start")?;
                    }
                    Ok::<(), String>(())
                })();
                if rollback.is_ok() {
                    return Err(format!("{error}. Previous settings were restored"));
                }
            }
            state.pending = true;
            state.applied = false;
            let _ = storage::save(&self.paths.file("state.json"), &state);
            return Err(format!("{error}. Recovery needs attention. Run Restore"));
        }
        result
    }

    pub fn restore(&self) -> Result<Value, String> {
        let _lock = self.paths.lock()?;
        let mut state: State = storage::read(&self.paths.file("state.json"))?;
        if !state.applied && !state.pending {
            return Ok(json!({"ok":true,"message":"Original settings are already restored"}));
        }
        self.service("stop")?;
        state.pending = true;
        storage::save(&self.paths.file("state.json"), &state)?;
        self.restore_snapshot(&state.baseline)?;
        state.pending = false;
        state.applied = false;
        storage::save(&self.paths.file("state.json"), &state)?;
        self.service("start")?;
        Ok(json!({"ok":true,"message":"Original settings restored y verificado"}))
    }
    pub fn status(&self) -> Result<Value, String> {
        let _lock = self.paths.lock()?;
        let saved: Option<Config> = storage::read(&self.paths.file("profile.json")).ok();
        let devices = if let Some(ref c) = saved {
            vec![backend::device(&c.device_id, &c.device_name)?]
        } else {
            backend::discover()?
        };
        let config = saved.unwrap_or_else(|| default_config(&devices[0]));
        let state: Option<State> = storage::read(&self.paths.file("state.json")).ok();
        Ok(
            json!({"ok":true,"devices":devices,"config":config,"actions":config::actions(),
            "applied":state.as_ref().is_some_and(|s| s.applied),"pending":state.as_ref().is_some_and(|s| s.pending),
            "daemon":self.daemon_active(),"events":self.events()?}),
        )
    }
    pub fn events(&self) -> Result<Value, String> {
        Ok(storage::read(&self.paths.file("events.json")).unwrap_or_else(|_| json!([])))
    }
    pub fn trigger(&self, event: &str, manual: bool) -> Result<Value, String> {
        if !config::EVENTS.contains(&event) {
            return Err("Evento no reconocido".into());
        }
        let wheel = event.starts_with("wheel.") || event.starts_with("thumb.");
        let _lock = if wheel {
            match self.paths.try_lock()? {
                Some(lock) => lock,
                None => return Ok(json!({"ok":true,"throttled":true})),
            }
        } else {
            self.paths.lock()?
        };
        let mut state: State = storage::read(&self.paths.file("state.json"))?;
        if !state.applied || state.pending {
            return Err("No active profile".into());
        }
        let timestamp = storage::now();
        let mut events: Vec<Value> =
            storage::read(&self.paths.file("events.json")).unwrap_or_default();
        if event.starts_with("wheel.") || event.starts_with("thumb.") {
            let group = event.split('.').next().unwrap();
            let last = events.iter().rev().find(|e| {
                e["event"].as_str().is_some_and(|s| s.starts_with(group))
                    && e["source"] == if manual { "manual" } else { "solaar" }
            });
            if last.and_then(|e| e["timestamp"].as_u64()).is_some_and(|t| {
                timestamp.saturating_sub(t as u128) < state.config.wheel_interval_ms as u128
            }) {
                return Ok(json!({"ok":true,"throttled":true}));
            }
        }
        let action = state.config.action(event).to_string();
        let outcome = if action.starts_with("dpi.") {
            self.cycle_dpi(&mut state, action == "dpi.next")
        } else if let Some(args) = config::action_command(&action) {
            backend::run(
                &args[0],
                &args[1..].iter().map(String::as_str).collect::<Vec<_>>(),
                None,
            )
            .and_then(|output| {
                if ["unknown", "unhandled", "disabled"].contains(&output.trim()) {
                    Err(format!(
                        "The desktop could not run {action}: {}",
                        output.trim()
                    ))
                } else {
                    Ok(())
                }
            })
        } else {
            Ok(())
        };
        let entry = json!({"event":event,"action":action,"timestamp":timestamp,"source":if manual {"manual"} else {"solaar"},
            "ok":outcome.is_ok(),"error":outcome.err()});
        events.push(entry.clone());
        if events.len() > 100 {
            events.drain(..events.len() - 100);
        }
        storage::save(&self.paths.file("events.json"), &events)?;
        Ok(entry)
    }
    fn cycle_dpi(&self, state: &mut State, up: bool) -> Result<(), String> {
        let device = backend::device(&state.config.device_id, &state.config.device_name)?;
        let dpi = &device.settings["dpi"];
        let presets: Vec<u32> = [400, 800, 1000, 1600, 2400, 3200]
            .into_iter()
            .filter(|n| dpi.choices.contains(&n.to_string()))
            .collect();
        let current = dpi.value.parse::<u32>().map_err(|e| e.to_string())?;
        let next = if up {
            presets.iter().find(|n| **n > current).or(presets.first())
        } else {
            presets
                .iter()
                .rev()
                .find(|n| **n < current)
                .or(presets.last())
        }
        .ok_or("No supported DPI presets")?;
        backend::set(&device.id, "dpi", &next.to_string())?;
        let live = backend::config(&[&device.id, "dpi"])?;
        let (readback, _) = backend::parse_settings(&live);
        if readback
            .get("dpi")
            .is_none_or(|d| d.value != next.to_string())
        {
            return Err("Solaar did not confirm the DPI change".into());
        }
        state.config.hardware.insert("dpi".into(), next.to_string());
        storage::save(&self.paths.file("state.json"), state)?;
        // Preserve un-applied edits in the draft except this explicit DPI action.
        let mut draft = self.draft()?;
        draft.hardware.insert("dpi".into(), next.to_string());
        storage::save(&self.paths.file("profile.json"), &draft)
    }
}

pub fn default_config(device: &Device) -> Config {
    Config {
        device_id: device.id.clone(),
        device_name: device.name.clone(),
        hardware: HARDWARE
            .iter()
            .filter_map(|key| {
                device.settings.get(*key).map(|s| {
                    (
                        key.to_string(),
                        if s.toggle {
                            s.value.to_lowercase()
                        } else {
                            s.value.clone()
                        },
                    )
                })
            })
            .collect(),
        ..Config::default()
    }
}
fn scalar(id: &str, values: &Value) -> Result<Value, String> {
    let input = json!({"id":id,"values":values}).to_string();
    let result = backend::run("python3", &["-c", SCALAR], Some(&input))?;
    serde_json::from_str(&result).map_err(|e| e.to_string())
}

fn incremental_eligible(previous: &Config, next: &Config) -> bool {
    if previous.device_id != next.device_id
        || previous.device_name != next.device_name
        || previous.hardware.keys().ne(next.hardware.keys())
    {
        return false;
    }
    let changed: Vec<&str> = next
        .hardware
        .iter()
        .filter(|(k, v)| previous.hardware.get(*k) != Some(*v))
        .map(|(k, _)| k.as_str())
        .collect();
    if !changed.is_empty() {
        return previous.bindings == next.bindings
            && previous.wheel_interval_ms == next.wheel_interval_ms
            && changed.iter().all(|k| {
                [
                    "dpi",
                    "hires-smooth-invert",
                    "hires-smooth-resolution",
                    "thumb-scroll-invert",
                ]
                .contains(k)
            });
    }
    // Changing an action within an existing capture mode only changes Solaar rules.
    previous.gestures() == next.gestures()
        && previous.wheel(false) == next.wheel(false)
        && previous.wheel(true) == next.wheel(true)
        && ["button.back", "button.forward"]
            .iter()
            .all(|e| (previous.action(e) != "native") == (next.action(e) != "native"))
}

fn changed_hardware(
    snapshot: &Snapshot,
    desired: &BTreeMap<String, String>,
) -> BTreeMap<String, String> {
    desired
        .iter()
        .filter_map(|(key, value)| {
            let setting = snapshot.device.settings.get(key)?;
            // Free-spin readback is 1, while Solaar stores the ratchet threshold separately.
            let stored = if key == "smart-shift"
                && snapshot
                    .device
                    .settings
                    .get("scroll-ratchet")
                    .is_some_and(|s| s.value == "Freespinning")
                && desired
                    .get("scroll-ratchet")
                    .is_none_or(|m| m == "Freespinning")
            {
                snapshot.persisted[key]
                    .as_u64()
                    .filter(|n| (1..=50).contains(n))
                    .map(|n| n.to_string())
            } else {
                None
            };
            let current = stored.as_deref().unwrap_or(&setting.value);
            (!backend::equal_value(current, value)).then(|| (key.clone(), value.clone()))
        })
        .collect()
}

fn button_id(name: &str) -> Option<u32> {
    match name {
        "Back Button" => Some(83),
        "Forward Button" => Some(86),
        "Mouse Gesture Button" => Some(195),
        "MultiPlatform Back" => Some(206),
        "MultiPlatform Forward" => Some(207),
        "MultiPlatform Gesture Button" => Some(208),
        _ => None,
    }
}
fn baseline_button(snapshot: &Snapshot, button: &str) -> String {
    let original =
        button_id(button).and_then(|id| snapshot.persisted["divert-keys"][id.to_string()].as_u64());
    match original {
        Some(0) => "Regular",
        Some(1) => "Diverted",
        Some(2) => "Mouse Gestures",
        Some(3) => "Sliding DPI",
        _ => snapshot
            .device
            .buttons
            .get(button)
            .map(String::as_str)
            .unwrap_or("Regular"),
    }
    .into()
}
fn verify_snapshot(snapshot: &Snapshot) -> Result<(), String> {
    let device = backend::device(&snapshot.device.id, &snapshot.device.name)?;
    for key in &snapshot.keys {
        if !backend::equal_value(
            &device.settings[key].value,
            &snapshot.device.settings[key].value,
        ) {
            return Err(format!("Restoration of {key} was not confirmed"));
        }
    }
    for button in snapshot
        .device
        .buttons
        .keys()
        .filter(|n| button_id(n).is_some())
    {
        let expected = if baseline_button(snapshot, button) == "Regular" {
            "Regular"
        } else {
            "Diverted"
        };
        if device.buttons.get(button).map(String::as_str) != Some(expected) {
            return Err(format!("Restoration of {button} was not confirmed"));
        }
    }
    Ok(())
}
fn verify_profile(config: &Config, baseline: &Snapshot) -> Result<(), String> {
    let device = backend::device(&config.device_id, &config.device_name)?;
    for (key, value) in &config.hardware {
        // Solaar maps free-spin SmartShift reads to 1, even when the
        // underlying stored threshold is higher and will be used in ratchet.
        if key == "smart-shift"
            && device
                .settings
                .get("scroll-ratchet")
                .is_some_and(|s| s.value == "Freespinning")
        {
            if device.settings.get(key).is_none_or(|s| s.value != "1") {
                return Err("SmartShift in free-spin mode was not confirmed".into());
            }
            continue;
        }
        if device
            .settings
            .get(key)
            .is_none_or(|s| !backend::equal_value(&s.value, value))
        {
            return Err(format!("{key} was not confirmed"));
        }
    }
    for event in ["button.back", "button.forward", "gesture"] {
        if let Some(button) = backend::button(&device, event) {
            let custom = if event == "gesture" {
                config.gestures()
            } else {
                config.action(event) != "native"
            };
            let expected = if custom || baseline_button(baseline, &button) != "Regular" {
                "Diverted"
            } else {
                "Regular"
            };
            if device.buttons.get(&button).map(String::as_str) != Some(expected) {
                return Err(format!("{button} was not confirmed"));
            }
        }
    }
    for (thumb, key) in [
        (false, "hires-scroll-mode"),
        (false, "lowres-scroll-mode"),
        (true, "thumb-scroll-mode"),
    ] {
        if let Some(setting) = device.settings.get(key) {
            let expected = if config.wheel(thumb) {
                "true"
            } else {
                &baseline.device.settings[key].value
            };
            if !backend::equal_value(&setting.value, expected) {
                return Err(format!("{key} was not confirmed"));
            }
        }
    }
    Ok(())
}
