# Solaar integration research (Omalogi V1)

Facts gathered from primary sources: Solaar source at master commit `e7304c4c451cc9bb4f206a914844525e67856a28` (2026-08-18), Solaar docs, Solaar GitHub issue tracker, and the Arch Linux package database. All source line numbers refer to that commit. No GPL code was copied; integration is via the external `solaar` program only.

---

## 1. The rule engine

### 1.1 rules.yaml location and schema

- Solaar reads rules from `~/.config/solaar/rules.yaml` (honours `$XDG_CONFIG_HOME` if set): `_XDG_CONFIG_HOME = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser(os.path.join("~", ".config"))`; `_file_path = os.path.join(_XDG_CONFIG_HOME, "solaar", "rules.yaml")` — `lib/logitech_receiver/diversion.py` L1494–L1495.
- The file contains zero or more YAML documents; **each document is one rule**, and each rule is a list of components (conditions / actions), each a single-key mapping. Solaar's own writer emits a `%YAML 1.3` directive with `---`/`...` document separators (`docs/rules.md` "Example Solaar Rule File"; `_save_config_rule_file` in `diversion.py` L1497–L1529). Verified locally with PyYAML: both with and without the `%YAML 1.3` directive, `yaml.safe_load_all` (which is exactly what Solaar uses, `diversion.py` `_load_rule_config`) parses the multi-document file fine.
- Rules are evaluated in file order for every HID++ notification; if the last thing a rule does is execute an action, no later rules are processed for that notification (`docs/rules.md` "HID++ notifications and diversion"). A rule whose condition fails just falls through to the next rule.

### 1.2 `MouseGesture` condition — exact allowed values

- The condition exists: class `MouseGesture` in `lib/logitech_receiver/diversion.py` L969–L1021. It matches only on the synthetic `MOUSE_GESTURE` notification (feature id `0xFE00`, `lib/logitech_receiver/hidpp20_constants.py` L237), which Solaar itself generates (see §4).
- Allowed movement arguments (exact strings, `MOVEMENTS` list, `diversion.py` L970–L979):
  - `Mouse Up`, `Mouse Down`, `Mouse Left`, `Mouse Right`, `Mouse Up-left`, `Mouse Up-right`, `Mouse Down-left`, `Mouse Down-right`
  - (8-way; no "Click" pseudo-direction and no case variants — matching against directions is exact string equality, `diversion.py` L1008–L1011.)
- Any other argument is treated as the **Logitech name of a key/button** and, if it is the first argument, is matched against the button that initiated the gesture (i.e. the diverted "Mouse Gestures" button held down), `diversion.py` L1001–L1004. On MX Master 3/3S that button's Logitech name is exactly **`Mouse Gesture Button`** (CID `0x00C3`; source comment: "Thumb_Button on MX Master - Logitech name App_Switch_Gesture", `lib/logitech_receiver/special_keys.py` L218). Names are `NamedInt` display names: underscores → spaces, `__` → `/` (`common.py` `_readable_name`).
- **Tap / no-movement**: an **empty argument list** `MouseGesture: []` matches "the gesture button was clicked with no movement" — the docs call this the "No-op" gesture: "It's possible to create a `No-op` gesture … This gesture will trigger when you simply click a Mouse Gestures button" (`docs/rules.md` "Mouse gestures"); the rule editor renders empty movements as "No-op" (`lib/solaar/ui/rule_conditions.py` L612–L613). Evaluation confirms: payload is just the initiating CID, `data_offset == len(data)` → true (`diversion.py` L1005–L1017).
  - To restrict the tap to the MX gesture button specifically: `MouseGesture: [Mouse Gesture Button]`.
  - **Do not write the literal string `No-op`** — it is not a direction or key name; it logs "rule Mouse Gesture argument not direction or name of a Logitech key: No-op" and the condition is broken (user hit exactly this on 1.1.20 and had to delete the parameter: [issue #3317](https://github.com/pwr-Solaar/Solaar/issues/3317)).
- The argument string for the initiating button is **case-sensitive and exact** (`self.movements[0] != str(CONTROL[data[0]])`, `diversion.py` L1003), so `Mouse Gesture Button` must be spelled exactly.

### 1.3 `Execute` action — exact syntax and semantics

- Class `Execute` (`diversion.py` L1328–L1349). YAML forms:
  - `- Execute: [program, arg1, arg2, …]` — list of strings, each list element is one argv entry (no shell, no globbing, no `|`, no quoting/escaping layer).
  - `- Execute: program` — a bare string becomes the single-element argv `[program]`; **a string containing spaces is therefore a single (probably nonexistent) executable name, not a shell line**. The docs' own example `- Execute: xflock4` relies on this.
  - Invalid types (non-string elements) are rejected at load with a warning and the action becomes a no-op (`diversion.py` L1332–L1335).
- Execution: `subprocess.Popen(self.args)` — **asynchronous (fire-and-forget), no shell, no stdout/stderr capture, no cwd/env control, no timeout** (`diversion.py` L1345). There is no error handling: if the program does not exist, `FileNotFoundError` propagates out of the evaluate callback (raised inside the GLib idle callback, so it is printed by GLib and the GUI keeps running); exit status is ignored.
- `Execute` is an `Action`, so when it is the last component the rule "consumes" the notification and later rules are skipped for it (§1.1).
- Related actions for completeness: `KeyPress`, `MouseScroll`, `MouseClick` (all simulate input via **uinput** since 1.1.20 — "Remove use of XTest and use uinput in all cases", [release 1.1.20](https://github.com/pwr-Solaar/Solaar/releases/tag/1.1.20)), plus `Set` (change a device setting), `Later` (delayed components) (`docs/rules.md` "Actions").

---

## 2. Rule lifecycle: load, reload, parse errors

- **Load time**: `load_config_rule_file()` runs once at module import of `lib/logitech_receiver/diversion.py` (bottom of file, `diversion.py` L1560ish: `load_config_rule_file()`), i.e. when the Solaar GUI process starts. The loaded set is `[user rules from rules.yaml] + built_in_rules` (brightness-key emulation) (`diversion.py` `_load_rule_config`, L1532–L1550).
- **Reload**: there is **no file watcher** and **no CLI/IPC reload** command (verified: no `FileMonitor`/inotify for rules.yaml anywhere in `lib/`; the `solaar` CLI subcommands are only `config, pair, probe, profiles, show, unpair` — `lib/solaar/cli/__init__.py`). The only reload path is inside the GUI Rule Editor (`lib/solaar/ui/diversion_rules.py` L641–L653: `_reload_yaml_file` / `_save_yaml_file` call `diversion.load_config_rule_file()` / `_save_config_rule_file()`). **Practical consequence: editing rules.yaml by hand while Solaar runs requires killing and restarting Solaar** (the GUI "discard" button reloads from disk, but that is a GUI interaction, not scriptable). The Rule Editor has also had bugs where GUI edits were not picked up / lost, pushing users to hand-edit the YAML ([issue #3043](https://github.com/pwr-Solaar/Solaar/issues/3043)).
- **Parse error behaviour**: `_load_rule_config` wraps everything in `try/except Exception` and logs `"failed to load from %s"`. Whatever rules parsed before the exception are kept; on failure the effective rule set degrades to (partially loaded rules +) built-in rules only — **it does not crash, and it does not modify or delete the file on disk**, so a fix + restart recovers everything (`diversion.py` L1532–L1550). Saving from the GUI rewrites the whole file from in-memory rules (`_save_config_rule_file`), so the dangerous direction is GUI-save-after-bad-state, not external edits.
- The settings side is separate: device settings persist in `~/.config/solaar/config.yaml` (per-device section, e.g. `divert-keys: {82: 0, 83: 0, 86: 0, 195: 2, 196: 3}` — real MX Master values from [issue #3043](https://github.com/pwr-Solaar/Solaar/issues/3043)) and are re-applied by Solaar when a device connects.

---

## 3. Tap detection, direction quantization, latency

- **Tap**: yes, cleanly supported as `MouseGesture: []` (any gesture button) or `MouseGesture: [Mouse Gesture Button]` (MX gesture button only) — see §1.2. Real users run exactly this shape (`- Rule: [ MouseGesture: [], KeyPress: … ]` in [issue #3043](https://github.com/pwr-Solaar/Solaar/issues/3043)).
- **How direction is quantized**: while the gesture button is held, Solaar accumulates raw dx/dy from the device into DPI-normalized units (`dx += raw/dpi*15`, ≈5 units per cm of physical movement) and pushes a movement event only when the integer-truncated accumulated delta is non-zero; a pause >200 ms pushes a new movement event (`MouseGesturesXY` in `lib/logitech_receiver/settings_templates.py` L900–L945). On release the event sequence is packed and matched: each movement segment's direction is `xy_direction(x, y)`, which normalizes the segment vector and rounds to the 8 compass directions (`diversion.py` L292–L318). So:
  - there is an implicit ~2 mm dead-zone per event before a movement registers (favourable for tap detection);
  - **a hesitant swipe (pause > ~200 ms mid-gesture) produces two segments and will not match a single-segment rule** like `[Mouse Gesture Button, Mouse Up]` (documented in `docs/rules.md`: "Stopping the mouse for a little while and moving it again creates another mouse movement event");
  - a "tap" with slight hand drift can register as a directional gesture instead (tap and direction rules are mutually exclusive by construction).
- **Reliability reports**: on an MX Master 3S one user reports gesture-diversion detection failing intermittently ("it fails many times … sometimes [it] detect[s] I am pushing the mouse gesture button"), while keying on `Key: [Mouse Gesture Button, released]` worked "100%" ([issue #1904 comment](https://github.com/pwr-Solaar/Solaar/issues/1904#issuecomment-2466830653)). Treat single-segment direction matching as *probably* fine but spike-verify (§9).
- **Latency**: gestures are emitted **only on button release** (`release_action` → `process_notification`, `settings_templates.py` L919–L928), and users confirm "Mouse gesture conditions only trigger actions once and only when released" ([issue #3043](https://github.com/pwr-Solaar/Solaar/issues/3043)). After release, evaluation is queued via `GLib.idle_add` (`diversion.py` L1489–L1491) and `Execute` itself is `Popen` (async). No GitHub issue was found complaining about `Execute` latency specifically; the floor is release-to-process time plus process spawn (no hard number in sources — spike-measurable, §9). There is also no press-side or repeat action possible through this path (#3043 asked for exactly that; unsupported).
- MX Master 3S-specific quirk: Solaar ignores the first movement report after press when REPROG_CONTROLS_V4 ≥ v5 — "hack to ignore strange first movement report from MX Master 3S" (`settings_templates.py` L933–L935).

---

## 4. MX Master 3 / 3S: what must be enabled, and how, from a script

### 4.1 The one setting that matters

- **`Key/Button Diversion` (internal name `divert-keys`) must be set to `Mouse Gestures` (value 2) for the `Mouse Gesture Button` (CID 0xC3 / 195)**. Setting it makes Solaar divert the key over HID++ **REPROG_CONTROLS_V4 (0x1B04)** and attach its own raw-XY handler: diverted key press/release arrives in 0x1B04 report `0x00` (CID list), raw pointer deltas in 0x1B04 report `0x10` while held (`ActionSettingRW.handler` in `lib/logitech_receiver/settings.py` L716–L763). That synthetic stream is what becomes the `MOUSE_GESTURE` (0xFE00) notification the rules match.
- The button must have the `RAW_XY` key flag for the "Mouse Gestures" choice to be offered at all; MX Master 3/3S report `Mouse Gesture Button … raw_xy, divertable` in `solaar show` ([issue #1904](https://github.com/pwr-Solaar/Solaar/issues/1904), [issue #3043](https://github.com/pwr-Solaar/Solaar/issues/3043)).
- The old standalone "Mouse Gestures" setting is gone; "use the Key/Button Diversion setting and set a key to Mouse Gestures" (maintainer pfps, [issue #1904 comment](https://github.com/pwr-Solaar/Solaar/issues/1904#issuecomment-1334666168)). Some devices/versions only show `Regular/Diverted` for a key ([#1904 comments](https://github.com/pwr-Solaar/Solaar/issues/1904#issuecomment-1891018441)) — the choice exists only if the device supports gestures on that key (`DivertKeys.validator_class.build`, `settings_templates.py` L1000–L1020).
- **Not required**: thumb-wheel / hi-res-scroll settings, `gesture2-*` settings (feature GESTURE_2 0x6501, `hidpp20_constants.py` L138 — that path is for touchpad-style gesture diversion, not the gesture button), and `reprogrammable-keys` changes. Scroll-wheel diversion is only needed if we later want wheel rules.

### 4.2 Exact CLI invocations

`solaar config` syntax (from `lib/solaar/cli/config.py`): `solaar config <device> <setting> <key> <value>` for map-choice settings; the device is matched by serial, unitId, codename or name and **must be online** (`dev.ping()`; else `no online device found matching '<name>'`, `config.py` L174–L179).

```bash
# inspect (also lists exact internal setting + key names):
solaar config "MX Master 3S"

# divert the gesture button to Mouse Gestures (exact English value string, case-sensitive):
solaar config "MX Master 3S" divert-keys "Mouse Gesture Button" "Mouse Gestures"

# verify:
solaar show "MX Master 3S" | grep -A2 "Key/Button Diversion"
```

- Key name matching is case-insensitive (`NamedInt.__eq__` compares names lower-cased, `common.py`), but the **value string is matched case-sensitively** against the choice labels `Regular` / `Diverted` / `Mouse Gestures` (`select_choice`, `config.py` L108–L137).
- **Numeric-value gotcha**: a numeric value is interpreted *positionally* (1-based index into the choice list), not as the HID value: for a gesture-capable key `3` selects `Mouse Gestures` (value 2) while `2` selects `Diverted` (value 1) (`config.py` L112–L116). Prefer the name string; verify the resulting `divert-keys: {…195: 2…}` in `~/.config/solaar/config.yaml`.
- If the Solaar GUI is running, the CLI change is also forwarded to the GUI over its Gtk application remote; if not, the CLI writes the device directly and persists the value in `config.yaml` so it is restored at next start (`config.py` L207–L236).
- The change must be applied once per device (per host for multi-host pairs); afterwards Solaar re-applies `divert-keys` from `config.yaml` on every connection.
- Device identifiers (Solaar descriptors, `lib/logitech_receiver/descriptors.py` L407): MX Master 3 = wpid `4082`, Bluetooth id `0xB023`. MX Master 3S (wpid/BT `B034`) has no static descriptor and is probed live; both expose `Mouse Gesture Button` and `Smart Shift` as `raw_xy, divertable` keys.

### 4.3 Permission prerequisite

Solaar needs write access to the device hidraw nodes (to send 0x1B04 writes) and, for simulated-input actions, to `/dev/uinput`. Arch ships the udev rule `/usr/lib/udev/rules.d/42-logitech-unify-permissions.rules` (Arch package file list, §5); upstream recommends the same file manually otherwise (`docs/installation.md`, `docs/rules.md`). Without uinput access, diversion still works but `KeyPress`/`MouseClick` rules warn `cannot create uinput device` ([issue #2990](https://github.com/pwr-Solaar/Solaar/issues/2990)) — irrelevant for `Execute`-only rules.

---

## 5. Packaging and runtime on Arch Linux

Source: [Arch package `extra/solaar`](https://archlinux.org/packages/extra/any/solaar/) and its [file list](https://archlinux.org/packages/extra/any/solaar/files/) (1.1.20-2, 2026-07-19), plus upstream repo.

- **Package**: `extra/solaar`, version **1.1.20-2** (upstream 1.1.20 released 2026-06-28, [GitHub release](https://github.com/pwr-Solaar/Solaar/releases/tag/1.1.20)). License `GPL-2.0-or-later` — consistent with treating Solaar strictly as an external dependency.
- **Binary**: a single `/usr/bin/solaar` (console script `solaar = solaar.gtk:main`, `setup.py` L93–L97). There is **no `solaar-cli`** any more; the CLI is `solaar <command>` with commands `config, show, pair, unpair, probe, profiles` plus `--window=…`, `-ddd` etc. `solaar config`/`show` work headless from scripts; `solaar` with no subcommand starts the GTK app.
- **Service model**: **no systemd unit is shipped** and — notable for Omarchy — the Arch package ships only `/usr/share/applications/solaar.desktop`, **no autostart entry** (`/etc/xdg/autostart` / `share/autostart/solaar.desktop` exists upstream but is not in the Arch file list). Omarchy must start Solaar itself: upstream's autostart exec line is `solaar --window=hide` (`share/autostart/solaar.desktop`), or a `systemd --user` service running the same command. **Rules only fire while this GUI process runs** — the diversion/notification pipeline (`SolaarListener` → `notifications.process` → `diversion.process_notification` → `GLib.idle_add(evaluate_rules)`) lives in the GUI process (`lib/solaar/listener.py`, `lib/logitech_receiver/notifications.py` L480, `diversion.py` L1444–L1491). One-shot `solaar config`/`show` invocations do not process rules.
- **Python dependency surface** (Arch runtime deps): `python` (3.14 at packaging time), `python-gobject` + `gtk3` + `glib2` + `gdk-pixbuf2` (GUI/GLib main loop — the rules engine runs inside it), `python-yaml` (rules.yaml + config), `python-xlib`, `python-evdev`, `python-dbus`, `python-psutil`, `python-pyudev`, `python-cairo`, `libnotify`, `hicolor-icon-theme`; optional `libappindicator` (tray icon). Bundled vendored libs (`hid_parser`, `hidapi`, `keysyms`) ship inside the package. Upstream warns not to pip-install a separate `hid_parser` (`docs/installation.md`).
- **Arch-specific quirks**: udev rule ships under `/usr/lib/udev/rules.d/` (works out of the box; a reboot or `udevadm trigger` may be needed after first install — `docs/rules.md`); no autostart (above); Arch users on old versions see different behaviour — upstream refuses support below 1.1.14 (issue template).

---

## 6. Failure modes

- **Solaar not running** → no rule processing at all; the gesture button also falls back to its default firmware behaviour ("Gesture Button Navigation") because diversion is re-applied by Solaar at connection time. Omarchy's installer should own "Solaar is running at login" (autostart or user service) and can detect it via `pgrep -x solaar`.
- **Device asleep / just woken / unpaired** → `solaar config` fails with `no online device found matching '<name>'` (device must pass `dev.ping()`, `config.py` L174–L179); while asleep no notifications flow, so rules simply don't fire. Receiver-paired devices that are asleep show `Device path: None` until they wake. There are open reports of Bolt devices not coming back cleanly after system sleep ([issue #3135](https://github.com/pwr-Solaar/Solaar/issues/3135)); Solaar watches suspend/resume over D-Bus and pings devices on resume (`lib/solaar/gtk.py` L197–L199).
- **Transport differences (Bolt vs Unifying vs Bluetooth/USB)**: the gesture path only needs 0x1B04 notifications to reach Solaar, which works over Bolt receivers, Unifying receivers, and direct Bluetooth connections (Solaar enumerates "USB and Bluetooth Devices" directly; `solaar config` also works against direct-connected devices). Differences to watch: REPROG_CONTROLS_V4 version varies per device (v3 on older, v5 on MX Master 3S) and only ≥v5 gets the first-move-report hack (`settings_templates.py` L933); raw-XY report cadence may differ per transport. No source documents a hard transport block for gestures on MX Master 3/3S — spike-verify per transport (§9).
- **Older MX Masters**: a report titled "MX Master does not support Solaar mouse gestures" exists for the 1st-gen MX Master ([issue #1587](https://github.com/pwr-Solaar/Solaar/issues/1587)); do not assume gen-1/2 behaviour matches the 3/3S.
- **Wayland (Hyprland)**: `docs/rules.md` states plainly: "rule processing only fully works under X11"; under Wayland the `Process`/`MouseProcess` conditions don't work and modifier-key awareness is lost (`rules cannot access modifier keys in Wayland…` warning — cosmetic for us); simulated input goes through **uinput**, which works on Wayland but needs `/dev/uinput` write access (§4.3). **`MouseGesture` conditions and `Execute` actions do not depend on X11**, so the planned gesture→CLI dispatch is Wayland-safe; avoid `Process:`/`Modifiers:` conditions in Omarchy's shipped rules. (The GNOME-extension workaround for process conditions is irrelevant on Hyprland.)
- **Rule editor is not a reliable CRUD surface** (bugs reported in [#3043](https://github.com/pwr-Solaar/Solaar/issues/3043)); ship rules.yaml as a file, treat Solaar as needing a restart after edits.
- **YAML footguns**: literal `No-op` string is invalid ([#3317](https://github.com/pwr-Solaar/Solaar/issues/3317)); `Execute:` with a quoted full command line becomes one argv element (use the list form); numeric `divert-keys` CLI values are positional, not HID values (§4.2).

---

## 7. Proposed minimal rules.yaml for Omalogi V1

**This IS cleanly possible.** Five documents, one per event, all on the MX gesture button (CID 0xC3). The list form of `Execute` keeps argv exact; the tap rule must precede nothing special since direction rules require movement segments and the tap rule requires none — they are mutually exclusive.

```yaml
# ~/.config/solaar/rules.yaml — Omalogi gesture dispatch (MX Master 3 / 3S)
# Requires: `solaar config "MX Master 3S" divert-keys "Mouse Gesture Button" "Mouse Gestures"`
%YAML 1.3
---
- MouseGesture: [Mouse Gesture Button]
- Execute: [omalogi, trigger, gesture.click]
...
---
- MouseGesture: [Mouse Gesture Button, Mouse Up]
- Execute: [omalogi, trigger, gesture.up]
...
---
- MouseGesture: [Mouse Gesture Button, Mouse Down]
- Execute: [omalogi, trigger, gesture.down]
...
---
- MouseGesture: [Mouse Gesture Button, Mouse Left]
- Execute: [omalogi, trigger, gesture.left]
...
---
- MouseGesture: [Mouse Gesture Button, Mouse Right]
- Execute: [omalogi, trigger, gesture.right]
...
```

Known limits (all from §3): actions fire on **button release**; a direction swipe interrupted by a >200 ms pause will not match (event falls through silently); a tap with ~2 mm+ of drift may register as a direction; if another "Mouse Gestures" button were also diverted, the tap rule above still only matches `Mouse Gesture Button`, and `MouseGesture: []` would be the variant matching any button. If omalogi ever needs the *host default* behaviour preserved for some events, diverting to plain `Diverted` (value 1) and using `Key: [Mouse Gesture Button, pressed/released]` conditions is the alternative path — but it does not give directions.

---

## 8. Decision-relevant open questions → hardware spike

1. **Tap reliability on real MX Master 3/3S hardware**: how much hand drift kills `MouseGesture: [Mouse Gesture Button]` (≈2 mm per-event threshold, no configurable dead-zone for rule gestures)? Frequency of "tap became a direction" vs "direction became nothing".
2. **End-to-end latency** on Hyprland/Wayland: button-release → Popen → `omalogi trigger` → visible effect; measure with `solaar -ddd` timestamps and a timestamping CLI.
3. **Transport matrix**: repeat the spike over Bolt, direct Bluetooth, and (if available) Unifying — confirm 0x1B04 raw-XY reporting and gesture recognition on each, and note REPROG_CONTROLS_V4 version differences (v3 vs v5 first-move hack).
4. **CLI value scripting**: confirm `solaar config <dev> divert-keys "Mouse Gesture Button" "Mouse Gestures"` (name form) works non-interactively with GUI running *and* stopped, and that `config.yaml` ends up with `195: 2`; check behaviour under non-English locales (labels come from gettext `_()`), and whether the positional-number form (`3`) is a safer fallback.
5. **Persistence across reconnects/reboots** with the GUI running from a `systemd --user` unit or Omarchy autostart: does diversion re-apply on every wake, and does the #3135-style Bolt-after-sleep stall affect gesture reporting?
6. **Coexistence**: does diverting the gesture button break the firmware's built-in gesture-button navigation entirely (expected), and does Smart Shift keep working untouched?
7. **Headless-run shape**: does `solaar --window=hide` run fine in an Omarchy/Hyprland session without a system tray (libappindicator optional), and do rules process identically with the window hidden?
8. **Restart-on-edit UX**: confirm the GUI picks up externally-edited rules.yaml only after restart (per source reading) and that restart is cheap/safe (no device re-configuration storm).

---

## 9. Source index

- Solaar docs: [rules.md](https://github.com/pwr-Solaar/Solaar/blob/master/docs/rules.md), [usage.md](https://github.com/pwr-Solaar/Solaar/blob/master/docs/usage.md), [installation.md](https://github.com/pwr-Solaar/Solaar/blob/master/docs/installation.md)
- Solaar source @ `e7304c4c` (master, 2026-08-18): `lib/logitech_receiver/diversion.py`, `settings.py`, `settings_templates.py`, `special_keys.py`, `hidpp20_constants.py`, `common.py`, `descriptors.py`; `lib/solaar/cli/__init__.py`, `cli/config.py`, `listener.py`, `gtk.py`, `ui/rule_conditions.py`, `ui/diversion_rules.py`; `setup.py`; `share/autostart/solaar.desktop`
- Releases: [1.1.20](https://github.com/pwr-Solaar/Solaar/releases/tag/1.1.20) (2026-06-28)
- Arch: [extra/solaar](https://archlinux.org/packages/extra/any/solaar/), [file list](https://archlinux.org/packages/extra/any/solaar/files/)
- Issues: [#1587](https://github.com/pwr-Solaar/Solaar/issues/1587), [#1904](https://github.com/pwr-Solaar/Solaar/issues/1904), [#2990](https://github.com/pwr-Solaar/Solaar/issues/2990), [#3043](https://github.com/pwr-Solaar/Solaar/issues/3043), [#3135](https://github.com/pwr-Solaar/Solaar/issues/3135), [#3317](https://github.com/pwr-Solaar/Solaar/issues/3317)
