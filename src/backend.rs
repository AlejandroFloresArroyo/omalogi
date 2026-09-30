use serde::{Deserialize, Serialize};
use std::{
    collections::BTreeMap,
    io::{Read, Write},
    process::{Command, Stdio},
    thread,
    time::{Duration, Instant},
};

pub fn run(program: &str, args: &[&str], input: Option<&str>) -> Result<String, String> {
    let mut child = Command::new(program)
        .args(args)
        .env("LC_ALL", "C")
        .stdin(if input.is_some() {
            Stdio::piped()
        } else {
            Stdio::null()
        })
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Could not run {program}: {e}"))?;
    let mut out = child.stdout.take().unwrap();
    let mut err = child.stderr.take().unwrap();
    let stdout = thread::spawn(move || {
        let mut s = String::new();
        let _ = out.read_to_string(&mut s);
        s
    });
    let stderr = thread::spawn(move || {
        let mut s = String::new();
        let _ = err.read_to_string(&mut s);
        s
    });
    if let Some(text) = input {
        child
            .stdin
            .take()
            .unwrap()
            .write_all(text.as_bytes())
            .map_err(|e| e.to_string())?;
    }
    let start = Instant::now();
    let status = loop {
        if let Some(status) = child.try_wait().map_err(|e| e.to_string())? {
            break status;
        }
        if start.elapsed() > Duration::from_secs(25) {
            let _ = child.kill();
            let _ = child.wait();
            return Err(format!("{program} did not respond within 25 seconds"));
        }
        thread::sleep(Duration::from_millis(20));
    };
    let output = stdout.join().unwrap_or_default();
    let errors = stderr.join().unwrap_or_default();
    if !status.success() {
        return Err(format!(
            "{program}: {}",
            if errors.trim().is_empty() {
                output.trim()
            } else {
                errors.trim()
            }
        ));
    }
    Ok(output)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Setting {
    pub value: String,
    pub choices: Vec<String>,
    pub toggle: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Device {
    pub id: String,
    pub name: String,
    pub settings: BTreeMap<String, Setting>,
    pub buttons: BTreeMap<String, String>,
}

pub fn discover_ids(text: &str) -> Vec<(String, String)> {
    let mut devices = Vec::new();
    let mut name = String::new();
    for line in text.lines() {
        // Device headings are "  1: MX Master 3S"; nested firmware and
        // feature headings use more indentation and must not reset identity.
        if line.starts_with("  ")
            && !line.starts_with("   ")
            && let Some((slot, title)) = line.trim().split_once(": ")
            && slot.parse::<u32>().is_ok()
        {
            name = title.to_string();
        }
        if name.starts_with("MX Master")
            && let Some(serial) = line.trim().strip_prefix("Serial number: ")
            && !serial.is_empty()
            && serial != "None"
        {
            devices.push((serial.into(), name.clone()));
            name.clear();
        }
    }
    devices
}

pub fn parse_settings(text: &str) -> (BTreeMap<String, Setting>, BTreeMap<String, String>) {
    let mut settings = BTreeMap::new();
    let mut buttons = BTreeMap::new();
    let mut choices = Vec::new();
    let mut toggle = false;
    for line in text.lines() {
        if line.starts_with("#   possible values:") {
            toggle = line.contains("on/true");
            if let Some((_, rest)) = line.split_once("one of [")
                && let Some((list, _)) = rest.split_once(']')
            {
                choices = list.split(',').map(|v| v.trim().to_string()).collect();
            }
        } else if let Some((key, value)) = line.split_once(" = ") {
            if key == "divert-keys" {
                for pair in value.trim_matches(['{', '}']).split(',') {
                    if let Some((name, choice)) = pair.trim().split_once(':') {
                        buttons.insert(name.into(), choice.into());
                    }
                }
            }
            if !value.contains('?') {
                settings.insert(
                    key.into(),
                    Setting {
                        value: value.into(),
                        choices: choices.clone(),
                        toggle,
                    },
                );
            }
            choices.clear();
            toggle = false;
        }
    }
    (settings, buttons)
}

pub fn device(id: &str, name: &str) -> Result<Device, String> {
    // A fresh GUI scans the same HID++ receiver. Retry transient transport
    // assertions rather than misreporting a disconnected mouse at startup.
    let mut result = run("solaar", &["config", id], None);
    for _ in 0..2 {
        if result.is_ok() {
            break;
        }
        thread::sleep(Duration::from_millis(300));
        result = run("solaar", &["config", id], None);
    }
    let text = result?;
    let (settings, buttons) = parse_settings(&text);
    if !settings.contains_key("dpi") {
        return Err("The mouse is not responding; turn it on and move the pointer".into());
    }
    let actual_name = text
        .lines()
        .find(|l| l.contains(" ["))
        .and_then(|l| l.split_once(" ("))
        .map(|p| p.0)
        .unwrap_or(name);
    Ok(Device {
        id: id.into(),
        name: actual_name.into(),
        settings,
        buttons,
    })
}

pub fn discover() -> Result<Vec<Device>, String> {
    let text = run("solaar", &["show"], None)?;
    let mut result = Vec::new();
    let mut failures = Vec::new();
    for (id, name) in discover_ids(&text) {
        match device(&id, &name) {
            Ok(device) => result.push(device),
            Err(error) => failures.push(error),
        }
    }
    if result.is_empty() {
        if let Some(error) = failures.into_iter().next() {
            return Err(error);
        }
        return Err("No MX Master is connected. Check Bolt and turn on the mouse".into());
    }
    Ok(result)
}

pub fn set(id: &str, key: &str, value: &str) -> Result<(), String> {
    run("solaar", &["config", id, key, value], None).map(|_| ())
}

pub fn set_button(id: &str, key: &str, value: &str) -> Result<(), String> {
    run("solaar", &["config", id, "divert-keys", key, value], None).map(|_| ())
}

pub fn write_settings(device: &Device, values: &BTreeMap<String, String>) -> Result<(), String> {
    for (key, value) in values
        .iter()
        .filter(|(key, _)| key.as_str() != "smart-shift" && key.as_str() != "scroll-ratchet")
    {
        set(&device.id, key, value)?;
    }
    if let Some(threshold) = values.get("smart-shift") {
        if device.settings.contains_key("scroll-ratchet") {
            set(&device.id, "scroll-ratchet", "Ratcheted")?;
        }
        set(&device.id, "smart-shift", threshold)?;
        let text = run("solaar", &["config", &device.id, "smart-shift"], None)?;
        let (settings, _) = parse_settings(&text);
        if settings
            .get("smart-shift")
            .is_none_or(|s| s.value != *threshold)
        {
            return Err("SmartShift threshold was not confirmed".into());
        }
    }
    if let Some(mode) = values.get("scroll-ratchet").or_else(|| {
        if values.contains_key("smart-shift") {
            device.settings.get("scroll-ratchet").map(|s| &s.value)
        } else {
            None
        }
    }) {
        set(&device.id, "scroll-ratchet", mode)?;
    }
    Ok(())
}

pub fn button(device: &Device, event: &str) -> Option<String> {
    let candidates: &[&str] = match event {
        "button.back" => &["Back Button", "MultiPlatform Back"],
        "button.forward" => &["Forward Button", "MultiPlatform Forward"],
        _ => &["Mouse Gesture Button", "MultiPlatform Gesture Button"],
    };
    candidates
        .iter()
        .find(|n| device.buttons.contains_key(**n))
        .map(|n| n.to_string())
}

pub fn validate_hardware(device: &Device, values: &BTreeMap<String, String>) -> Result<(), String> {
    for (key, value) in values {
        let setting = device
            .settings
            .get(key)
            .ok_or_else(|| format!("The mouse does not support {key}"))?;
        let valid = if setting.toggle {
            ["true", "false"].contains(&value.to_lowercase().as_str())
        } else if key == "smart-shift" {
            value.parse::<u32>().is_ok_and(|n| (1..=50).contains(&n))
        } else {
            setting.choices.contains(value)
        };
        if !valid {
            return Err(format!("Unsupported value for {key}: {value}"));
        }
    }
    Ok(())
}

pub fn equal_value(a: &str, b: &str) -> bool {
    a.eq_ignore_ascii_case(b)
}
