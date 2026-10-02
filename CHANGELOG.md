# Changelog

## Unreleased

- Detect and configure an MX Master paired directly over Bluetooth. Solaar reports no serial for such a mouse, so it is identified and selected by unit ID.
- The panel header and `omalogi status` report the live transport (`Bolt`, `Bluetooth`, `USB`) instead of a fixed label.
- A mouse that is off, asleep or out of range is reported with a short message instead of Solaar's traceback.
- Queries wait until the Solaar service has been running for six seconds, so they no longer overlap its startup scan of the mouse. Opening the panel right after Apply or Restore can take that much longer.

Bluetooth is experimental. Hardware tests on an MX Master 3S confirmed detection, gestures, wheels, DPI, apply, restore and reconnection. The first one ended with the mouse leaving its Bluetooth channel; the cause is not established, and the sequence ran five more times without incident after the startup wait was added. See VALIDATION.md.

## 0.1.0-beta.2

- Use English throughout the desktop panel, action menus, accessibility labels, CLI and installation messages.
- Update the native preview and language specification.


## 0.1.0-beta.1

- Omalogi branding, `omalogi` CLI and `omalogi.mouse` Omarchy bar widget.
- MX Master 3S via Bolt: DPI, five gestures, side buttons, vertical and horizontal wheels, ratchet and SmartShift.
- Native Omarchy popup with automatic application, queued edits and background completion.
- Selective Solaar persistence, verified writes, rollback and restoration of the original device settings.
- Migration from the local MVP, preserving profiles, restoration snapshots and foreign Solaar rules.
- Root plugin manifest, source/prebuilt installation, GitHub checks and draft binary releases.

Validated combination: Omarchy 4.0.4, Quickshell 0.3.1, Hyprland 0.56.2, Solaar 1.1.20, MX Master 3S via Bolt. A new graphical-session startup and installation on a second clean machine remain to be verified. See VALIDATION.md.
