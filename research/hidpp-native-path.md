# Native V2 (`omalogid`): HID++ gesture-capture feasibility research

Researched 2026-09-21 against primary sources: the vendored Solaar tree
(`solaar-src/`, commit `e7304c4`), the Linux kernel sources
(`drivers/hid/hid-logitech-hidpp.c`, `drivers/hid/hid-logitech-dj.c`),
Peter Wu's mirror of Logitech's official HID++ spec documents, and
crates.io/GitHub metadata. Solaar source was read for facts only; **no
Solaar code was copied** (Solaar is GPL-2.0; see §3 for licensing).

---

## 1. Linux input path for MX Master 3/3S

### Kernel drivers

Two kernel modules are relevant, both GPL-2.0 (`MODULE_LICENSE("GPL")`,
[hid-logitech-hidpp.c L30-34](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-logitech-hidpp.c);
[hid-logitech-dj.c L2216-2217](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-logitech-dj.c)):

- **`hid-logitech-dj`** binds to USB *receivers* (Unifying 0xC52B/0xC532,
  Bolt 0xC548, Nano, Lightspeed — device table at
  [hid-logitech-dj.c L2096-2150](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-logitech-dj.c)).
  For each paired wireless device it calls `hid_allocate_device()` +
  `hid_add_device()` (L812-874), creating a **separate hid_device — and
  therefore a separate `/dev/hidrawN` node — per paired peripheral**. The
  device's product ID is set to the wireless PID (e.g. 0x4082 for MX
  Master 3), so user space sees the mouse itself, not the receiver.
  The driver explicitly supports HID++ routing from user space over the
  receiver's own hidraw node: *"This allows a user space application to
  implement the full HID++ routing via the receiver"* (L1732-1735).
  Bolt receivers only expose receiver reporting on one interface
  (L1911-1914) and send unpair notifications as HID++ events (L1754-1760).
- **`hid-logitech-hidpp`** binds to devices **directly** — over Bluetooth
  (HID-BT) or wired USB — and speaks HID++ itself for a hardcoded set of
  features. MX Master 3 (BT PID 0xB023), 3S (0xB034), MX Master (0xB012),
  2S (0xB019) all appear in its Bluetooth device table
  ([hid-logitech-hidpp.c L4970-5002](https://github.com/torvalds/linux/blob/master/drivers/hid/hid-logitech-hidpp.c)).
  It does **not** implement diversion: its `hidpp20_reprog_controls_raw_event`
  (L3771-3810) only maps *already-diverted* control-ID notifications to
  `input_report_key()` for devices with the
  `HIDPP_QUIRK_HIDPP_REPROG_CONTROLS_BTNS` quirk (Signature M650 and
  similar); it never sets the divert flags itself. Gesture diversion
  remains a user-space job.

### hidraw nodes per connection type

- **Bolt (0xC548) / Unifying (0xC52B) receivers:** the receiver itself gets
  hidraw node(s) (Bolt exposes its DJ/HID++ interface plus possibly generic
  HID interfaces), **and** each paired device gets its own hidraw node
  created by hid-logitech-dj (see above). Writing HID++ to the *device's*
  node is the normal path (Solaar does this); the receiver node also works
  with an explicit device index (Solaar uses it for pairing only).
- **Bluetooth:** one hidraw node for the mouse (bus type BUS_BLUETOOTH,
  BT PID 0xB023/0xB034 for MX Master 3/3S — kernel table above; Solaar's
  descriptor confirms `btid=0xB023` for MX Master 3, `solaar-src/lib/logitech_receiver/descriptors.py` L407).
- hidraw gives unmodified reports with read/write plus feature-report
  ioctls; it is the documented interface for *"userspace applications [that]
  know exactly how to communicate with the hardware device"* —
  [kernel HIDRAW docs](https://docs.kernel.org/hid/hidraw.html).

### How Solaar talks to devices: yes, user-space HID++ over hidraw

Solaar's transport opens `/dev/hidrawN` nodes directly with `os.open(path,
O_RDWR|O_SYNC)` (`solaar-src/lib/hidapi/udev_impl.py` L319-340; the open
path is asserted to start with `/dev/hidraw`, L327). It enumerates devices
via `pyudev` filtering on `subsystem="hidraw"` (L216, L234). Its HID++
framing is short (7-byte, report id 0x10) and long (20-byte, report id
0x11) messages (`solaar-src/lib/logitech_receiver/base.py` L90-96). No
kernel assistance is used for feature configuration.

## 2. HID++ 2.0 feature inventory for gesture capture

### The gesture-button mechanism is 0x1B04, not 0x6500/0x6501 — ground truth

The official Logitech spec page for feature **0x1B04 (SpecialKeysMseButtons
/ REPROG_CONTROLS_V4)**, mirrored at
[lekensteyn.nl/files/logitech/x1b04_specialkeysmsebuttons.html](https://lekensteyn.nl/files/logitech/x1b04_specialkeysmsebuttons.html),
defines the complete mechanism:

- `[1] getCidInfo(index)` returns each control's cid, tid and capability
  flags. Byte 8 bit 0 is the **rawXY flag**: *"This control has capability
  of being a programmed as a gesture button… Control can be diverted along
  with raw mouse xy reports to SW. SW performs gesture detection and
  gesture task injection."*
- `[3] setCidReporting(cid, divert, dvalid, persist, pvalid, rawXY, rvalid,
  remap)` sets diversion. Setting **rawXY=1** makes the control temporarily
  diverted *together with* raw mouse XY reports.
- `[event0] divertedButtonsEvent` (function 0x00): 8 bytes = up to four
  pressed diverted control IDs (u16 BE each). This carries press/release.
- `[event1] divertedRawMouseXYEvent` (function 0x10): `dx msb, dx lsb, dy
  msb, dy lsb` (i32 BE pairs, 4 bytes). *"This event does not report button
  pressed/released information"* — press/release still arrives via event0.

So the candidate feature IDs in the question are answered: **0x6500
(GESTURE) and 0x6501 (GESTURE_2) are separate features for tap/edge/circle
gestures on touchpads and touch-mice** (Solaar lists both as "Unsupported"/
"Partial Support" and unrelated to the MX Master thumb-button raw-XY path —
`solaar-src/docs/features.md` L102-103). **0x6100 TOUCHPAD_RAW_XY /
0x6110 TOUCHMOUSE_RAW_POINTS** are the raw-XY features for actual touchpad
hardware, not for a diverted mouse button. The MX Master 3/3S gesture
button is captured entirely through **0x1B04 rawXY diversion**; Solaar's
`MouseGesturesXY` handler only listens to REPROG_CONTROLS_V4 notifications
(`solaar-src/lib/logitech_receiver/settings.py` L797-845).

Notification addressing: the feature-indexed notification arrives with the
feature's dynamically assigned index in `sub_id` (Solaar checks
`device.features.get_feature(n.sub_id) == REPROG_CONTROLS_V4`,
settings.py L806), address 0x00 = diverted buttons, 0x10 = raw XY.

### Gesture button control ID on MX Master 3/3S

Control ID **0x00C3 "Mouse_Gesture_Button"** — Solaar comments it as
*"Thumb_Button on MX Master - Logitech name App_Switch_Gesture"*
(`solaar-src/lib/logitech_receiver/special_keys.py` L218). Related IDs in
the same family: 0x00C4 "Smart_Shift" (top button), 0x00D0
"MultiPlatform_Gesture_Button". The 0x1B04 spec's example table shows cid
195 (0xC3) = AppSwitchGesture / tid 156 (0x9C) = GestureButton, confirming
the pairing. The gesture button should be found dynamically by scanning
`getCidInfo` for the rawXY capability flag rather than hardcoding 0xC3
(the flag is what identifies it; Solaar does exactly this by checking
`KeyFlag.RAW_XY in key.flags`, `settings_templates.py` L1011-1021).

### Supporting features

| Purpose | Feature | Notes |
|---|---|---|
| Protocol ping / keepalive | 0x0000 ROOT `getProtocolVersion` | [x0000 spec](https://lekensteyn.nl/files/logitech/x0000_root.html); ping data also resyncs after collisions |
| Feature enumeration | 0x0001 FEATURE_SET, 0x0002 FEATURE_INFO | standard discovery |
| Device identification | 0x0003 DEVICE_INFO (`unitId`, `transport` bits, `modelId`), 0x0005 DEVICE_NAME, 0x0007 FRIENDLY_NAME | [x0003 spec](https://lekensteyn.nl/files/logitech/x0003_deviceinfo.html); multi-protocol devices (USB/eQuad/BTLE/BT) answer with the active-link PID |
| Control enumeration + diversion + raw XY | **0x1B04 REPROG_CONTROLS_V4** | the gesture path, above |
| Thumb wheel (horizontal scroll) | 0x2150 THUMB_WHEEL | Solaar supports (`docs/features.md` L69); only needed if we also handle horizontal scroll — **not needed for gesture capture** |
| SmartShift (ratchet/free-wheel mode) | 0x2110 SMART_SHIFT, 0x2111 SMART_SHIFT_ENHANCED | only if we manage the maglev button; not needed for gesture capture |
| Battery | 0x1000 BATTERY_STATUS, 0x1001 BATTERY_VOLTAGE, 0x1004 UNIFIED_BATTERY | Solaar tries unified first, falls back (`docs/features.md` L31-33); nice-to-have for a tray indicator, orthogonal to gestures |
| High-res wheel events | 0x2121 HIRES_WHEEL | kernel driver may already claim this; see §6 |

### Raw XY semantics

`divertedRawMouseXYEvent` deltas are raw counts, not pixels. Solaar
converts with the device DPI: `dx = float(dx) / float(dpi) * 15.0` to get a
roughly DPI-independent unit (`solaar-src/lib/logitech_receiver/settings_templates.py`
L939-941). It also drops the first movement report on MX Master 3S when
feature version ≥ 5 (*"hack to ignore strange first movement report from
MX Master 3S"*, L936-938) — a real firmware-variation data point to copy
behaviorally, not literally.

## 3. The Logitech HID++ 2.0 spec document: existence, access, licensing

- **It exists.** `logitech_hidpp_2.0_specification_draft_2012-06-04.pdf`
  (the 2011/2012 "draft" spec, ~128 KB) plus per-feature documents
  (0x1B04, 0x2110, 0x2121, 0x2201, 0x6100/0x6110, HID++ 1.0 for Unifying
  receivers, the Unifying DJ collection spec) are hosted in Peter Wu's
  mirror: [lekensteyn.nl/files/logitech/](https://lekensteyn.nl/files/logitech/).
  The README there states the originals are © Logitech and were retrieved
  from Logitech's own public Google Drive folder
  (`https://drive.google.com/.../folders/0BxbRzx7vEV7eWmgwazJ3NUFfQ28`,
  found via a Chromium bug tracker); the mirror is a conversion of
  Logitech-authored .doc/.docx/PDF files. Solaar's docs point to the same
  Drive folder (`solaar-src/docs/hidpp-documentation.txt`), and Solaar's
  0x1B04 code cites the same Drive file ID
  (`solaar-src/lib/logitech_receiver/hidpp20.py` L449).
- **What that implies for clean-room implementation.** The spec is
  publicly available documentation of the protocol, not proprietary
  secret, but it is **© Logitech with no grant of redistribution or
  derivative rights**. The clean posture for an MIT/Apache project is:
  - **Protocol facts are not copyrightable** — feature IDs, message
    layouts, control IDs, and behavioral constants may be implemented
    from the spec (this is the same position kernel and libratbag
    developers took; the kernel driver's HID++ work was authored by
    Logitech engineers Nestor Lopez Casado & Benjamin Tissoires,
    hid-logitech-hidpp.c L32-33).
  - **Do not copy prose, tables, or code** from the spec or from GPL
    sources (Solaar, the kernel driver, logiops) into the MIT/Apache
    implementation.
  - Citing the spec URL as documentation reference is fine; embedding the
    PDF in the repo is not advisable without permission.
- There is no other official public location; Logitech has never published
  the spec through a formal program. Everything routes back to that Drive
  folder / its mirrors.

## 4. Solaar's gesture-path surface (facts for scope estimation)

Solaar is GPL-2.0 (`solaar-src/LICENSE.txt`); we study its structure, not
its text. Sizes from `wc -l` on the vendored tree:

**The actual gesture path is narrow:**

- `lib/logitech_receiver/settings.py` class `RawXYProcessing` (~65 lines,
  L797-861): sets rawXY reporting on a key, registers a notification
  handler, dispatches press/release/move. The entire notification-side
  parsing is `struct.unpack("!HHHH", ...)` for event0 and
  `struct.unpack("!hh", ...)` for event1.
- `lib/logitech_receiver/settings_templates.py` class `MouseGesturesXY`
  (~55 lines, L900-960): accumulates deltas into a gesture polyline with
  DPI normalization and a 200 ms gap-based segment split.
- `lib/logitech_receiver/hidpp20.py` REPROG_CONTROLS_V4 support:
  `ReprogrammableKeyV4` (~135 lines, L445-610) — getCidInfo/get/set
  cidReporting — plus key enumeration (~50 lines).
- Feature discovery infrastructure that the above depends on: ROOT ping +
  FEATURE_SET iteration in `hidpp20.py` (~200 lines) and the framing/
  routing layer in `base.py` (`write`/`read`, ~150 relevant lines) and
  `notifications.py` (routing only, ~40 relevant lines).

**A minimal gesture capture therefore needs roughly: frame encode/decode,
ping, feature-set walk, 0x1B04 getCidInfo/getCidReporting/setCidReporting,
notification demux — a few hundred lines of Rust, not thousands.**

**Parts of Solaar we must NOT reimplement** (and which would drag GPL
contamination risk and huge scope if we tried):

- Pairing / unpairing (`receiver.py`, 635 lines; pairing register flows in
  `hidpp10.py`) — user pairs via the OS or Solaar once; we only talk to an
  already-paired device.
- Unifying/Bolt/Nano/Lightspeed receiver management and the entire
  receiver device-index routing layer (`base_usb.py`, most of
  `receiver.py`) — Bolt's DJ routing is handled by the kernel for us.
- Firmware/DFU updates — never.
- The settings surface: `settings_templates.py` (4737 lines),
  `settings.py` (888), `settings_validator.py` (861), `special_keys.py`
  (1560, mostly Task/CID name tables), `diversion.py` (1573, the X11/
  Wayland action-execution engine). Solaar's whole `lib/logitech_receiver`
  is ~21k lines; the gesture-relevant fraction is well under 1k.
- GESTURE_2 (0x6501) touchpad gesture handling (`hidpp20.py` Gestures
  classes, ~250 lines) — irrelevant to MX Master thumb button.

## 5. Prior art beyond Solaar

- **libratbag / piper** — [github.com/libratbag/libratbag](https://github.com/libratbag/libratbag),
  **MIT-licensed** C daemon for configuring gaming mice (2576 stars,
  actively pushed 2026-08). It implements HID++ over hidraw for Logitech
  devices (DPI, buttons, reports) and is the best permissive-licensed
  reference for protocol facts and hidraw handling. It does not implement
  rawXY gesture diversion, but its HID++ transaction code demonstrates the
  clean-room pattern. Piper is its GTK frontend.
- **logiops** (C++, GPL) — configuration daemon (SmartShift, gestures via
  gesture config); GPL, so a license reference only, not a code reference.
- **Rust crates:**
  - [`hidapi`](https://crates.io/crates/hidapi) (MIT, 2.6.7) — the
    standard hidraw-backed HID transport for Rust; `linux-native` feature
    uses udev directly instead of bundling C hidapi. This covers our
    device-open/read/write needs entirely.
  - [`hidpp`](https://crates.io/crates/hidpp) v0.2.0 — "An implementation
    of the HID++ protocol used by Logitech devices" — licensed **BSD-2-Clause**
    ([LICENSE](https://github.com/lus/logy/blob/main/LICENSE), repo
    `lus/logy`). Tiny adoption (1.5k downloads) but a permissive protocol
    reference.
  - **OpenLogi** family ([AprilNEA/OpenLogi](https://github.com/AprilNEA/OpenLogi),
    **Apache-2.0**, `openlogi-hidpp`, `openlogi-hid`, `openlogi-device`,
    0.8.6, actively developed 2026): a Rust "local-first alternative to
    Logitech Options+" doing remap/DPI/SmartShift over HID++ — explicitly
    an MX-Master-focused permissive-licensed Rust implementation that
    proves the whole approach is feasible.
  - `hidpp-transport` v0.1.0 (repo `ahmetbarut/logiops-rs`) — transport
    layer only, negligible adoption.
- **Kernel documentation and code:** [hidraw API](https://docs.kernel.org/hid/hidraw.html)
  (the read/write/ioctls contract), `hid-logitech-dj.c` (Bolt/Unifying
  node creation), `hid-logitech-hidpp.c` (protocol constants, quirks).
  Kernel sample `samples/hid-example.c` is explicitly *"may be used by
  anyone for any purpose"* per the hidraw doc — a safe template for the
  ioctl plumbing.
- **ltunify** (Peter Wu, GPL) — Unifying pairing tool; documentation of
  HID++ 1.0 receiver registers only.

## 6. Risks

1. **Firmware variation.** Solaar carries device-specific quirks even
   within one model: the *"strange first movement report"* hack for MX
   Master 3S rawXY (`settings_templates.py` L936-938) and a descriptor
   system keyed on wireless PID (`descriptors.py`: MX Master 3 = wpid
   0x4082 / btid 0xB023). Feature *versions* differ per firmware
   (Solaar checks `get_feature_version(REPROG_CONTROLS_V4) >= 5`). Mitigation:
   read feature version at init; treat unknown versions as "no first-report
   quirk"; verify on real hardware.
2. **Bolt vs Bluetooth behavior.** Over BT the mouse exposes a single
   hidraw node and the kernel `hid-logitech-hidpp` driver binds to it;
   over Bolt/Unifying the kernel `hid-logitech-dj` creates a per-device
   node and the *receiver* node also carries HID++. The HID++ payload
   should be identical (0x1B04 exists on both paths per Solaar's unified
   device model), but report framing, device-index addressing
   (receiver-node path needs the device index; device-node path uses
   index 0xFF), and connection notifications differ. BT also means no
   receiver status notifications — reconnection detection must be
   poll/ping-based.
3. **Reconnection / sleep.** Wireless mice power-cycle: HID++ feature
   indexes are stable across reconnection (per-device, not per-session)
   but diversion flags are **temporary** — the 0x1B04 spec says the
   divert/rawXY state is *"reset to 'not diverted' when a HID++
   configuration reset occurs"* (feature 0x0020 policy), and power loss
   counts. A helper must re-apply diversion on (re)connection and drop
   stale deltas. Solaar handles this via connection-notification
   listeners on receivers; on BT we need periodic pings (0x0000
   getProtocolVersion with ping data) or udev add/remove events.
4. **Coexistence with other HID++ clients.** Multiple openers of the same
   hidraw node both receive the input stream, but concurrent *command*
   streams can interleave/collide — the spec's ping-echo mechanism exists
   precisely to recover from collisions, and Solaar's docs warn:
   *"Solaar expects that it has exclusive control over settings… Running
   other programs that modify these settings, such as logiops, will likely
   result in unexpected device behavior"*
   ([solaar docs/issues.md](https://github.com/pwr-Solaar/Solaar/blob/master/docs/issues.md)).
   The kernel driver also writes HID++ itself (e.g. it manages hi-res
   wheel mode on supported devices — Solaar documents scroll-resolution
   fights with it). Practical rules: **if Solaar runs, don't fight it** —
   either require it to not manage the device, or only set diversion flags
   (which Solaar only touches when a divert-setting is configured);
   re-check flag state before writing (getCidReporting) to avoid clobbering.
   With *nothing* else running, the risk is only the kernel's own feature
   claims (hi-res wheel), which we don't touch.
5. **Kernel driver quirks table drift.** hid-logitech-hidpp decides per
   PID whether to enable its own features; a future kernel could grow
   interaction with 0x1B04 for more devices (it already handles
   diverted-button events for the M650 quirk). Keep our usage strictly
   additive (we only consume notifications the kernel ignores for our
   PIDs today) and pin a hardware-spike check on the running kernel.

---

## Assessment

### (a) Size of the minimal V2 gesture-capture surface: **small**

Evidence: the complete mechanism is one HID++ 2.0 feature (0x1B04) with
four functions/events (getCidInfo, getCidReporting, setCidReporting,
divertedButtonsEvent, divertedRawMouseXYEvent) plus the generic envelope
(short/long report framing, ROOT ping, FEATURE_SET walk, device-name
identification). Solaar implements the equivalent of all of this in
roughly 250–400 lines of Python *including* its DPI-normalization and
first-report quirk, inside files that are 99% unrelated surface. A Rust
helper with `hidapi` (or raw udev/hidraw) doing: enumerate → identify MX
Master 3/3S (wpid 0x4082 / btid 0xB023 / modelId via 0x0003) → find
rawXY-capable control → setCidReporting(rawXY) → demux event0/event1 →
emit gestures is a **few hundred lines**. It is "small" with two
caveats that push it to small-medium: (1) reconnection/sleep
re-arming logic, and (2) coexistence policy with Solaar/kernel drivers,
both of which are mostly *engineering hardening* rather than protocol
complexity.

### (b) Feasibility of a permissively-licensed clean-room implementation: **yes, clearly feasible**

- The protocol is documented in Logitech's own public spec documents
  (feature-level, packet-layout level) that Logitech itself released
  publicly; implementing from them creates no derivative work of any GPL
  code.
- Permissive-licensed prior art already exists and is maintained: libratbag
  (MIT) proves the hidraw+HID++ pattern in C; OpenLogi (Apache-2.0, Rust)
  proves it in Rust for exactly these devices; the `hidpp` crate (BSD-2)
  and `hidapi` crate (MIT) provide transport and a protocol starting
  point. We are not pioneering.
- The contamination discipline is straightforward: never copy code or
  prose from Solaar/logiops/kernel sources; derive facts from the spec
  documents and from permissively-licensed code; attribute the spec URL
  in comments as documentation (not embedded).
- The only genuinely uncertain technical area is *runtime behavior
  details* (first-movement-report quirk, diversion persistence across
  sleep, exact deltas/DPI normalization) which require hardware
  validation regardless of licensing.

### (c) Open questions for a hardware spike

1. Does the MX Master 3S over **Bolt** expose the rawXY capability flag on
   cid 0x00C3 in getCidInfo, and does the feature version of 0x1B04 match
   the BT path (≥5, per Solaar's 3S quirk)? Same question on MX Master 3
   (non-S) — Solaar's quirk is only known to apply to 3S.
2. Does diversion survive host suspend/resume and mouse power-off/on, or
   must we re-apply on every connection event? (Spec says temporary flags
   reset on configuration reset — confirm empirically which events count.)
3. What are the raw delta units vs reported DPI on this firmware — does
   Solaar's `dx/dpi*15` normalization hold, and does the
   "ignore first movement report" quirk reproduce?
4. On the Bolt receiver node vs the per-device node: does writing
   setCidReporting to the per-device hidraw node work identically to the
   receiver node with device-index addressing (kernel routes both), and
   are notifications delivered on both?
5. Concurrent-client behavior: open the node simultaneously with Solaar
   and issue setCidReporting — do diverted events reach both readers, and
   do commands collide (ping-echo recovery) in practice?
6. Does the kernel hid-logitech-hidpp driver on the BT path emit anything
   for the diverted 0x1B04 notifications for our PIDs (it does for the
   M650 quirk), and would that duplicate input events we also consume?
7. Thumb wheel (0x2150) and SmartShift (0x2110/0x2111): are they affected
   by rawXY diversion on the thumb button, or fully independent?
8. Battery via 0x1004 UNIFIED_BATTERY on Bolt vs BT — needed for a tray
   indicator; confirm it doesn't require HID++ 1.0 register fallbacks on
   this firmware.
