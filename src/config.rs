use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const EVENTS: &[&str] = &[
    "gesture.click",
    "gesture.up",
    "gesture.down",
    "gesture.left",
    "gesture.right",
    "button.back",
    "button.forward",
    "wheel.up",
    "wheel.down",
    "thumb.left",
    "thumb.right",
];
pub const HARDWARE: &[&str] = &[
    "dpi",
    "scroll-ratchet",
    "smart-shift",
    "hires-smooth-invert",
    "hires-smooth-resolution",
    "thumb-scroll-invert",
];

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(deny_unknown_fields)]
pub struct Config {
    pub version: u32,
    pub device_id: String,
    pub device_name: String,
    pub hardware: BTreeMap<String, String>,
    pub bindings: BTreeMap<String, String>,
    pub wheel_interval_ms: u64,
}

impl Default for Config {
    fn default() -> Self {
        let bindings = EVENTS
            .iter()
            .map(|event| {
                let action = match *event {
                    "gesture.click" => "apps",
                    "gesture.up" => "menu",
                    "gesture.down" => "scratchpad",
                    "gesture.left" => "workspace.previous",
                    "gesture.right" => "workspace.next",
                    _ => "native",
                };
                (event.to_string(), action.to_string())
            })
            .collect();
        Self {
            version: 1,
            device_id: String::new(),
            device_name: String::new(),
            hardware: BTreeMap::new(),
            bindings,
            wheel_interval_ms: 120,
        }
    }
}

impl Config {
    pub fn action(&self, event: &str) -> &str {
        self.bindings
            .get(event)
            .map(String::as_str)
            .unwrap_or("native")
    }

    pub fn gestures(&self) -> bool {
        EVENTS[..5]
            .iter()
            .any(|event| self.action(event) != "native")
    }

    pub fn wheel(&self, thumb: bool) -> bool {
        let events = if thumb { &EVENTS[9..11] } else { &EVENTS[7..9] };
        events.iter().any(|event| self.action(event) != "native")
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.version != 1 {
            return Err("Unsupported configuration version".into());
        }
        if self.device_id.is_empty()
            || self.device_id.len() > 128
            || self.device_id.chars().any(char::is_control)
        {
            return Err("Select a connected mouse before applying changes".into());
        }
        if !(40..=1000).contains(&self.wheel_interval_ms) {
            return Err("Wheel action interval must be between 40 and 1000 ms".into());
        }
        for (event, action) in &self.bindings {
            if !EVENTS.contains(&event.as_str()) {
                return Err(format!("Unknown event: {event}"));
            }
            if !actions().iter().any(|entry| entry.id == *action) {
                return Err(format!("Unknown action: {action}"));
            }
        }
        let native_gestures = EVENTS[..5]
            .iter()
            .filter(|event| self.action(event) == "native")
            .count();
        if native_gestures != 0 && native_gestures != 5 {
            return Err(
                "Assign all five gestures (No action is allowed), or leave all at their defaults"
                    .into(),
            );
        }
        // Diverting a wheel changes both directions. Require explicit choices for
        // both rather than losing native scrolling in the unassigned direction.
        for events in [&EVENTS[7..9], &EVENTS[9..11]] {
            let native = events
                .iter()
                .filter(|event| self.action(event) == "native")
                .count();
            if native == 1 {
                return Err(
                    "Assign both wheel directions, or leave both as normal scrolling".into(),
                );
            }
        }
        for key in self.hardware.keys() {
            if !HARDWARE.contains(&key.as_str()) {
                return Err(format!("Setting not allowed: {key}"));
            }
        }
        Ok(())
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct Action {
    pub id: String,
    pub label: String,
}

pub fn actions() -> Vec<Action> {
    [
        ("native", "Default behavior"),
        ("none", "No action"),
        ("apps", "Applications"),
        ("menu", "Omarchy menu"),
        ("workspace.next", "Next workspace"),
        ("workspace.previous", "Previous workspace"),
        ("workspace.former", "Last workspace"),
        ("scratchpad", "Scratchpad"),
        ("audio", "Audio panel"),
        ("clipboard", "Clipboard"),
        ("screenshot", "Screenshot"),
        ("volume.up", "Volume up"),
        ("volume.down", "Volume down"),
        ("volume.mute", "Mute / unmute"),
        ("media.next", "Next track"),
        ("media.previous", "Previous track"),
        ("media.play", "Play / pause"),
        ("dpi.next", "Next DPI"),
        ("dpi.previous", "Previous DPI"),
        ("diagnostic", "Log test event"),
    ]
    .into_iter()
    .map(|(id, label)| Action {
        id: id.into(),
        label: label.into(),
    })
    .collect()
}

pub fn action_command(action: &str) -> Option<Vec<String>> {
    let command: &[&str] = match action {
        "apps" => &["omarchy", "menu", "toggle", "apps"],
        "menu" => &["omarchy", "menu", "toggle", "root"],
        "workspace.next" => &[
            "hyprctl",
            "dispatch",
            "hl.dsp.focus({ workspace = \"e+1\" })",
        ],
        "workspace.previous" => &[
            "hyprctl",
            "dispatch",
            "hl.dsp.focus({ workspace = \"e-1\" })",
        ],
        "workspace.former" => &[
            "hyprctl",
            "dispatch",
            "hl.dsp.focus({ workspace = \"previous\" })",
        ],
        "scratchpad" => &[
            "hyprctl",
            "dispatch",
            "hl.dsp.workspace.toggle_special(\"scratchpad\")",
        ],
        "audio" => &["omarchy-shell", "shell", "toggle", "omarchy.audio"],
        "clipboard" => &["omarchy-shell", "shell", "toggle", "omarchy.clipboard"],
        "screenshot" => &["omarchy", "capture", "screenshot"],
        "volume.up" => &["omarchy", "audio", "output", "volume", "raise"],
        "volume.down" => &["omarchy", "audio", "output", "volume", "lower"],
        "volume.mute" => &["omarchy", "audio", "output", "volume", "mute-toggle"],
        "media.next" => &["omarchy-shell", "media", "next"],
        "media.previous" => &["omarchy-shell", "media", "previous"],
        "media.play" => &["omarchy-shell", "media", "playPause"],
        _ => return None,
    };
    Some(command.iter().map(|arg| arg.to_string()).collect())
}
