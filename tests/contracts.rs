use omalogi::{
    backend::{self, Device, Setting},
    config::{Config, EVENTS},
    engine::default_config,
    rules, storage,
};
use std::collections::BTreeMap;

fn device() -> Device {
    Device {
        id: "A1B2C3D4".into(),
        name: "MX Master 3S".into(),
        settings: BTreeMap::from([
            (
                "dpi".into(),
                Setting {
                    value: "1000".into(),
                    choices: vec!["200".into(), "1000".into(), "8000".into()],
                    toggle: false,
                },
            ),
            (
                "hires-scroll-mode".into(),
                Setting {
                    value: "False".into(),
                    choices: vec![],
                    toggle: true,
                },
            ),
        ]),
        buttons: BTreeMap::from([
            ("Back Button".into(), "Regular".into()),
            ("Forward Button".into(), "Regular".into()),
            ("Mouse Gesture Button".into(), "Regular".into()),
        ]),
    }
}

#[test]
fn discovery_ignores_receiver_and_feature_serials() {
    let text = "Bolt Receiver\n  Serial: AAAA\n  1: MX Master 3S\n     Serial number: A1B2C3D4\n     Supports 37 HID++ features:\n         0: ROOT\n  1: G502\n     Serial number: BADBAD\n";
    assert_eq!(
        backend::discover_ids(text),
        vec![("A1B2C3D4".into(), "MX Master 3S".into())]
    );
}
#[test]
fn parses_actual_cli_shapes_and_keeps_choices_per_setting() {
    let (s, b) = backend::parse_settings(
        "#   possible values: one of [ 200, 1000, 8000 ], or higher\ndpi = 1000\nsmart-shift = 10\n#   possible values: on/true/t or off/false\nhires-scroll-mode = False\ndivert-keys = {Back Button:Regular, Mouse Gesture Button:Diverted}\nbroken = ?\n",
    );
    assert_eq!(s["dpi"].choices, ["200", "1000", "8000"]);
    assert!(s["smart-shift"].choices.is_empty());
    assert!(s["hires-scroll-mode"].toggle);
    assert!(!s.contains_key("broken"));
    assert_eq!(b["Mouse Gesture Button"], "Diverted");
}
#[test]
fn wheel_and_gesture_diversion_requires_complete_explicit_mapping() {
    let mut c = default_config(&device());
    assert!(c.validate().is_ok());
    c.bindings.insert("wheel.up".into(), "volume.up".into());
    assert!(c.validate().is_err());
    c.bindings.insert("wheel.down".into(), "volume.down".into());
    assert!(c.validate().is_ok());
    c.bindings.insert("gesture.up".into(), "native".into());
    assert!(c.validate().is_err());
}
#[test]
fn invalid_and_unsupported_hardware_never_reaches_writer() {
    let d = device();
    assert!(
        backend::validate_hardware(&d, &BTreeMap::from([("dpi".into(), "1001".into())])).is_err()
    );
    assert!(
        backend::validate_hardware(&d, &BTreeMap::from([("change-host".into(), "2".into())]))
            .is_err()
    );
    assert!(
        backend::validate_hardware(&d, &BTreeMap::from([("dpi".into(), "8000".into())])).is_ok()
    );
}
#[test]
fn rules_scope_every_event_to_device_and_preserve_foreign_bytes() {
    let d = device();
    let mut c = default_config(&d);
    for e in EVENTS {
        c.bindings.insert(e.to_string(), "diagnostic".into());
    }
    let block = rules::generate(&c, &d, std::path::Path::new("/tmp/a b/omalogi")).unwrap();
    rules::validate(&block).unwrap();
    assert_eq!(block.matches("\"Device\": \"A1B2C3D4\"").count(), 11);
    assert_eq!(block.matches("\"Execute\"").count(), 11);
    let foreign =
        "# custom rules\n---\n- Key: [Back Button, pressed]\n- Execute: [/usr/bin/true]\n...";
    assert_eq!(
        rules::split(&format!("{block}{foreign}")).unwrap(),
        (block, foreign.into())
    );
    assert!(rules::split(&format!("foreign\n{}{}", rules::BEGIN, rules::END)).is_err());
    assert!(rules::split(rules::BEGIN).is_err());
}
#[test]
fn atomic_storage_replaces_complete_document() {
    let temp = tempfile::tempdir().unwrap();
    let p = temp.path().join("config.json");
    let c = default_config(&device());
    storage::save(&p, &c).unwrap();
    let r: Config = storage::read(&p).unwrap();
    assert_eq!(c, r);
    assert_eq!(std::fs::read_dir(temp.path()).unwrap().count(), 1);
}

#[test]
fn legacy_rules_can_be_migrated_and_mixed_markers_are_rejected() {
    let block =
        "# BEGIN OMARCHY-LOGI v1\n---\n- Execute: [/usr/bin/true]\n...\n# END OMARCHY-LOGI v1\n";
    let foreign = "# foreign rules remain exact\n";
    assert_eq!(
        rules::split(&format!("{block}{foreign}")).unwrap(),
        (block.into(), foreign.into())
    );
    assert!(rules::split(&format!("{block}{}{}", rules::BEGIN, rules::END)).is_err());
}
