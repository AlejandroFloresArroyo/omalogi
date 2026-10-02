use omalogi::{
    backend::{self, Device, Setting},
    config::{Config, EVENTS},
    engine::default_config,
    rules, storage,
};
use std::{collections::BTreeMap, time::Duration};

fn device() -> Device {
    Device {
        id: "A1B2C3D4".into(),
        name: "MX Master 3S".into(),
        transport: "Bolt".into(),
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
// Solaar 1.1.20 `show` prints a directly connected device as a top-level heading
// without a slot, with an empty serial; its unit ID repeats under DEVICE FW VERSION.
const BLUETOOTH_SHOW: &str = "solaar version 1.1.20\n\nMX Master 3S\n     Device path  : /dev/hidraw11\n     USB id       : 046d:B034\n     Codename     : MX Master 3S\n     Kind         : mouse\n     Protocol     : HID++ 4.5\n     Serial number: \n     Model ID:      B03400000000\n     Unit ID:       A1B2C3D4\n     Supports 36 HID++ 2.0 features:\n         2: DEVICE FW VERSION      {0003} V4     \n            Unit ID: A1B2C3D4  Model ID: B03400000000  Transport IDs: {'btleid': 'B034'}\n\n";

#[test]
fn discovery_identifies_a_bluetooth_mouse_by_unit_id() {
    assert_eq!(
        backend::discover_ids(BLUETOOTH_SHOW),
        vec![("A1B2C3D4".into(), "MX Master 3S".into())]
    );
    // The same mouse stays paired, offline, on a receiver while it is on its Bluetooth channel.
    let both = format!(
        "Bolt Receiver\n  Serial       : AAAA\n\n  1: MX Master 3S\n     Device is offline.\n\n{BLUETOOTH_SHOW}"
    );
    assert_eq!(
        backend::discover_ids(&both),
        vec![("A1B2C3D4".into(), "MX Master 3S".into())]
    );
}
#[test]
fn discovery_ignores_direct_devices_without_a_usable_identity() {
    let other = BLUETOOTH_SHOW.replace("MX Master 3S", "MX Keys Mini");
    assert!(backend::discover_ids(&other).is_empty());
    let zero = BLUETOOTH_SHOW.replace("Unit ID:       A1B2C3D4", "Unit ID:       00000000");
    assert!(backend::discover_ids(&zero).is_empty());
    assert!(backend::discover_ids("MX Master 3S\n     Device is offline.\n").is_empty());
    // Without a top-level unit ID, the copy nested under the features is not an identity.
    let nested = BLUETOOTH_SHOW.replace("     Unit ID:       A1B2C3D4\n", "");
    assert!(backend::discover_ids(&nested).is_empty());
}
#[test]
fn transport_comes_from_the_selection_adapter_and_is_optional_in_saved_state() {
    assert_eq!(
        backend::transport(
            "MX Master 3S (MX Master 3S) [None:]\n\ndpi = 1000\n# transport: Bluetooth\n"
        ),
        "Bluetooth"
    );
    assert_eq!(backend::transport("dpi = 1000\n"), "");
    // Snapshots written before transports were recorded must still load for Restore.
    let saved: Device = serde_json::from_str(
        r#"{"id":"A1B2C3D4","name":"MX Master 3S","settings":{},"buttons":{}}"#,
    )
    .unwrap();
    assert_eq!(saved.transport, "");
}
#[test]
fn queries_wait_out_the_solaar_service_startup_scan() {
    let started = "ActiveState=active\nActiveEnterTimestamp=@1000\n";
    let remaining = |text, now_ms| backend::settle_remaining(text, now_ms);
    assert_eq!(remaining(started, 1_000_000), backend::SETTLE);
    assert_eq!(
        remaining(started, 1_001_500),
        backend::SETTLE - Duration::from_millis(1500)
    );
    assert_eq!(
        remaining(started, 1_000_000 + backend::SETTLE.as_millis()),
        Duration::ZERO
    );
    assert_eq!(remaining(started, 9_000_000), Duration::ZERO);
    // A clock stepped backwards must not turn into an unbounded wait.
    assert_eq!(remaining(started, 0), backend::SETTLE);
    // Transactions stop the service before touching the mouse: nothing to wait for.
    assert_eq!(
        remaining(
            "ActiveState=inactive\nActiveEnterTimestamp=@1000\n",
            1_000_000
        ),
        Duration::ZERO
    );
    assert_eq!(
        remaining("ActiveState=active\nActiveEnterTimestamp=\n", 1_000_000),
        Duration::ZERO
    );
    assert_eq!(remaining("", 1_000_000), Duration::ZERO);
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
