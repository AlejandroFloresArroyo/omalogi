use crate::{
    backend::{self, Device},
    config::{Config, EVENTS},
};
use serde_json::{Value, json};
use std::path::Path;

pub const BEGIN: &str = "# BEGIN OMALOGI v1\n";
pub const END: &str = "# END OMALOGI v1\n";

pub fn split(text: &str) -> Result<(String, String), String> {
    // Recognize the local MVP's markers during migration and recovery.
    let legacy_begin = "# BEGIN OMARCHY-LOGI v1\n";
    let legacy_end = "# END OMARCHY-LOGI v1\n";
    let (begin, end_marker) = if text.contains(legacy_begin) || text.contains(legacy_end) {
        if text.contains(BEGIN) || text.contains(END) {
            return Err("Two managed rule blocks were found; the file was left unchanged".into());
        }
        (legacy_begin, legacy_end)
    } else {
        (BEGIN, END)
    };
    let starts: Vec<_> = text.match_indices(begin).collect();
    let ends: Vec<_> = text.match_indices(end_marker).collect();
    if starts.is_empty() && ends.is_empty() {
        return Ok((String::new(), text.into()));
    }
    if starts.len() != 1 || ends.len() != 1 || starts[0].0 != 0 || ends[0].0 < starts[0].0 {
        return Err("The Omalogi rule block is damaged; the file was left unchanged".into());
    }
    let end = ends[0].0 + end_marker.len();
    Ok((text[..end].into(), text[end..].into()))
}

pub fn generate(config: &Config, device: &Device, binary: &Path) -> Result<String, String> {
    if !binary.is_absolute() {
        return Err("The rule executable must use an absolute path".into());
    }
    let mut rules: Vec<Value> = Vec::new();
    for event in EVENTS {
        if config.action(event) == "native" {
            continue;
        }
        let condition = if let Some(direction) = event.strip_prefix("gesture.") {
            let button =
                backend::button(device, "gesture").ok_or("The mouse has no gesture button")?;
            let mut gesture = vec![button];
            if direction != "click" {
                gesture.push(format!(
                    "Mouse {}",
                    match direction {
                        "up" => "Up",
                        "down" => "Down",
                        "left" => "Left",
                        _ => "Right",
                    }
                ));
            }
            json!({"MouseGesture": gesture})
        } else if event.starts_with("button.") {
            json!({"Key": [backend::button(device, event).ok_or("Unsupported side button")?, "pressed"]})
        } else {
            let test = match *event {
                "wheel.up" => {
                    if device.settings.contains_key("hires-scroll-mode") {
                        "hires_wheel_up"
                    } else {
                        "lowres_wheel_up"
                    }
                }
                "wheel.down" => {
                    if device.settings.contains_key("hires-scroll-mode") {
                        "hires_wheel_down"
                    } else {
                        "lowres_wheel_down"
                    }
                }
                "thumb.left" => "thumb_wheel_up",
                _ => "thumb_wheel_down",
            };
            if event.starts_with("thumb.") {
                json!({"Test": [test, 15]})
            } else {
                json!({"Test": [test]})
            }
        };
        rules.push(json!([{"Device": config.device_id}, condition, {"Execute": [binary.to_string_lossy(), "trigger", event]}]));
    }
    let mut text = BEGIN.to_string();
    for rule in rules {
        text.push_str("---\n");
        text.push_str(&serde_json::to_string_pretty(&rule).map_err(|e| e.to_string())?);
        text.push_str("\n...\n");
    }
    text.push_str(END);
    Ok(text)
}

pub fn validate(text: &str) -> Result<(), String> {
    backend::run(
        "python3",
        &[
            "-c",
            "import sys,yaml; list(yaml.safe_load_all(sys.stdin.read()))",
        ],
        Some(text),
    )
    .map(|_| ())
}
