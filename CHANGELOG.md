# Changelog

## Unreleased

- Detect and configure an MX Master paired directly over Bluetooth. Solaar reports no serial for such a mouse, so it is identified and selected by unit ID.
- The panel header and `omalogi status` report the live transport (`Bolt`, `Bluetooth`, `USB`) instead of a fixed label.
- A mouse that is off, asleep or out of range is reported with a short message instead of Solaar's traceback.

Bluetooth is covered by simulated tests and by tests against Solaar 1.1.20's own device matching. It has not been exercised on a physical Bluetooth connection; see VALIDATION.md.

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
