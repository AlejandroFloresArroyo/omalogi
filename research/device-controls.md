# Solaar device-control contract for the MVP

Verified 2026-09-29 against upstream tag `1.1.20` and the installed Arch package `solaar 1.1.20-2` under `/usr/lib/python3.14/site-packages`. This is an external CLI integration contract, not copied implementation. Capability availability and physical behavior still require live hardware validation.

## CLI arguments and output

Run subprocesses with `LC_ALL=C` so translated setting choices stay stable. Read with `solaar config DEVICE SETTING`; write with an extra value. Choice values first match their exact display label, then a numeric argument is interpreted as a **one-based position**. Therefore send DPI `1000`, but diversion `Mouse Gestures`, not `2` (which selects `Diverted`). Toggle arguments `true`/`false` are accepted. Range settings take decimal integers.

For keyed reads, use the **control label**, not its numeric ID: numeric strings do not resolve in the read path. Writes accept either labels or decimal control IDs. An absent setting raises an error; a failed read reports `?`, so process exit success alone does not prove a readable value.

Examples:

```text
solaar config SERIAL dpi 1000
solaar config SERIAL divert-keys "Mouse Gesture Button" "Mouse Gestures"
solaar config SERIAL divert-keys "Back Button" "Diverted"
solaar config SERIAL divert-keys "Back Button"
```

CLI ordinary read output uses `SETTING = VALUE`; keyed output omits `=`. CLI writes directly and, when the Solaar GUI owns the GTK application, forwards the normalized value to it; otherwise it saves through the device persister. [CLI source](https://github.com/pwr-Solaar/Solaar/blob/1.1.20/lib/solaar/cli/config.py)

Choice-map rendering is `{Control Label:Choice Label, ...}`, sorted by numeric control ID. A keyed read can therefore print `divert-keys {Back Button:Regular}`. Booleans render `True`/`False`; ordinary choice values render their labels. [Validator source](https://github.com/pwr-Solaar/Solaar/blob/1.1.20/lib/logitech_receiver/settings_validator.py)

## Controls and setting names

| Capability | Solaar setting | Accepted contract |
| --- | --- | --- |
| DPI | `dpi` | Discovered choice labels; obtain list from CLI |
| Ratchet/free spin | `scroll-ratchet` | `Ratcheted`, `Freespinning` |
| SmartShift threshold | `smart-shift` | Integer **1–50**, with 50 always ratcheted |
| Vertical inversion | `hires-smooth-invert` | Boolean |
| Vertical resolution | `hires-smooth-resolution` | Boolean high-sensitivity mode |
| Vertical diversion | `hires-scroll-mode` | Boolean HID++ notifications |
| Older vertical diversion | `lowres-scroll-mode` | Boolean; use only if exposed |
| Horizontal inversion | `thumb-scroll-invert` | Boolean |
| Horizontal diversion | `thumb-scroll-mode` | Boolean HID++ notifications |
| Button diversion | `divert-keys` | Per-control choice |

DPI choices are hardware-discovered. Wheel diversion suppresses ordinary scrolling. Software button modes: `Regular=0`, `Diverted=1`, `Mouse Gestures=2`, `Sliding DPI=3`. Fresh physical diversion reads distinguish only Regular/Diverted; restore software mode from configuration.

**SmartShift compatibility:** when `scroll-ratchet` is Freespinning, Solaar's `SmartShift.read` returns **1 regardless of the stored threshold**. Freespinning plus configured threshold 12 therefore correctly reads 1. Threshold writes preserve ratchet mode. Apply and verify threshold while Ratcheted, then set Freespinning last; final verification must check Freespinning, expect live threshold 1, and separately check persisted threshold 12. For Ratcheted, switch mode first, then write/verify the intended threshold. [Exact setting source, SmartShift read/write](https://github.com/pwr-Solaar/Solaar/blob/1.1.20/lib/logitech_receiver/settings_templates.py#L698-L738)

Control labels can differ by variant. Candidates include `Back Button` (83), `Forward Button` (86), `MultiPlatform Back` (206), `MultiPlatform Forward` (207), `Mouse Gesture Button` (195), and `MultiPlatform Gesture Button` (208). Discover available controls rather than selecting solely from the marketed model. [Control names](https://github.com/pwr-Solaar/Solaar/blob/1.1.20/lib/logitech_receiver/special_keys.py)

## Stable mouse selection

The CLI matches a serial, codename, kind, name substring, or receiver slot number; **unit ID is not a CLI selector**. Use the detected mouse serial. Receiver slot/name matching may select another device when several are attached. [CLI discovery](https://github.com/pwr-Solaar/Solaar/blob/1.1.20/lib/solaar/cli/__init__.py)

`solaar show` exposes `Serial number:`, `Unit ID:`, `Model ID:` and device names. A receiver's `Serial:` is distinct from the mouse's serial; parse device sections before choosing. [Show source](https://github.com/pwr-Solaar/Solaar/blob/1.1.20/lib/solaar/cli/show.py)

## Rules for wheels and buttons

The rule condition is **`Device`**, not `DeviceID`. It matches unit ID, serial, codename or name exactly and case-sensitively. Prefer a unique ID. `Key: [CONTROL, pressed]` matches a diverted button press.

Valid wheel tests are `hires_wheel_up/down`, `lowres_wheel_up/down`, and `thumb_wheel_up/down`. Vertical up is positive displacement, vertical down negative; thumb up is negative, thumb down positive. Test names indicate motion sign, not a universal physical left/right orientation.

Only thumb tests support an accumulated threshold: `Test: [thumb_wheel_up, 120]`. HIRES/LOWRES tests run once per notification and ignore the optional threshold argument. A fast wheel can therefore trigger many command processes: rate-limit in the CLI. Thumb accumulation resets at wheel-start notifications and consumes a threshold after matching. `MouseGesture: [CONTROL]` matches a click with no movement; append `Mouse Up/Down/Left/Right` for one-segment gestures. [Rules source](https://github.com/pwr-Solaar/Solaar/blob/1.1.20/lib/logitech_receiver/diversion.py)

## Persistence and restoration

`$XDG_CONFIG_HOME/solaar/config.yaml` (normally `~/.config/solaar/config.yaml`) is a YAML sequence: first the version string, then device maps. Receiver entries identify devices with `_wpid` + `_serial`; direct devices use `_modelId` + `_unitId`. Preserve unrelated devices, keys and metadata. Diversion maps must retain integer YAML keys.

When absent, `_sensitive` initializes these three settings to `ignore`: `hires-smooth-resolution`, `hires-smooth-invert`, `hires-scroll-mode`. Save the original sensitivity entries as well as values. Applying owned wheel changes requires clearing that ignore state and restoring it on uninstall. Editing while Solaar runs risks its in-memory configuration overwriting the file; coordinate stopping/restarting the service for configuration edits. [Configuration source](https://github.com/pwr-Solaar/Solaar/blob/1.1.20/lib/solaar/configuration.py)

On reconnect, `apply_all_settings` skips exactly sensitivity `ignore`; a false sensitivity still allows automatic replay. Individual setting reads and writes do not check that sensitivity gate. Thus a successful immediate CLI write can disappear after reconnect if the corresponding wheel setting remains ignored. Also, a settings write can retain an attempted value in memory/configuration before its hardware write fails; verify live reads after changes. [Settings source](https://github.com/pwr-Solaar/Solaar/blob/1.1.20/lib/logitech_receiver/settings.py)

For free spin, retain the intended SmartShift threshold in both the application profile and Solaar's per-device `smart-shift` entry. A fresh read caches 1 but leaves an existing persisted threshold intact; do not replace the profile/configuration with that derived read. Solaar reapplies its cached value, loading persistence only when the cache is empty. Standalone CLI reads do not change the GUI cache, but forced GUI reads can. Verify reconnect behavior. Free spin hides the raw threshold through this CLI; Ratcheted readback checks it before restoring free spin. [Read and apply semantics](https://github.com/pwr-Solaar/Solaar/blob/1.1.20/lib/logitech_receiver/settings.py#L116-L201)

The GUI's remote command handler forwards changes asynchronously. It does not establish a synchronous hardware-readback guarantee. Treat subsequent live device state and physical input as validation. [GUI command handler](https://github.com/pwr-Solaar/Solaar/blob/1.1.20/lib/solaar/ui/__init__.py)
