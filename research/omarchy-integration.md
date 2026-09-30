# Omarchy integration surface — refreshed research notes

Research date: **2026-09-29**. Official upstream inspected at `omacom/omarchy`,
default branch **`quattro`**, commit
[`8b4eae66da2938ba9559f103b18dbf85cdf28a70`][snapshot]. Omarchy source citations
below are pinned to that revision. The Hyprland wiki describes latest git and
was checked on the research date; it is not a version-pinned guarantee.

This replaces the September 21 assessment. It records verified integration
contracts and an updated project recommendation. These notes describe the integration research performed before implementation.
For the shipped CLI, QML plugin and hardware evidence, see [README](../README.md)
and [VALIDATION](../VALIDATION.md).

## 1. What changed in the assessment

| Previous note | Current finding | Classification |
| --- | --- | --- |
| Research against `master`/`HEAD` | Official development branch is `quattro`; this refresh pins a commit. | Source-reference correction. |
| File saves hot-reload all plugin code | `keepLoaded: true` preserves the service instance during hot reload; service-code changes require a shell restart. | Clarification of the current lifecycle contract. [Shell reference][shell] |
| Scoped facades might provide general cross-plugin access | Ordinary plugins control their own service/lifecycle. Replacement bars give third-party widgets a service-less facade, so those widgets cannot rely on retrieving their companion service there. | Current restriction; do not assume it was introduced after September 21. [Shell reference][shell] |
| Elsewhen proves separate-package plugin discovery | Elsewhen moved from package/id `omacom.elsewhen` into first-party `omarchy.elsewhen`. | Upstream evolution explicitly documented; move date not established here. [Migration account][shell], [Elsewhen source][elsewhen] |
| `omarchy-menu toggle launcher` opens applications | Current shipped menu and defaults use **`apps`**; no shipped `launcher` route was found. | Correction of an unverified third-party example. [Menu data][menudata], [bindings][utilities] |
| A generated Lua file and loader in `bindings.lua` are required | Solaar `Execute` → our CLI → Omarchy IPC/Hyprland actions needs no persistent Hyprland bind loader. | Correction of the proposed V1 design, not an upstream rule change. [Solaar notes](solaar-integration.md) |
| Plugin installation means binary must come from AUR | Plugin add clones/validates files and runs no build/install hooks. Binary delivery must be chosen separately; an Arch/AUR package is one option, a deliberately bundled prebuilt binary is another. | Packaging inference corrected. [Plugin installer][add] |

These are differences from the old assessment, not a dated upstream changelog:
the old notes used moving URLs and this checkout is shallow, so they do not
prove when each rule entered upstream.

There is also concrete **installed-version versus upstream** drift. Local
`/usr/share/omarchy` lacks the newer shell global-shortcut registry and fast IPC
socket present in this snapshot. Current helpers select registered global
shortcuts for known actions and fall back to commands; `omarchy-shell` prefers
its fast socket transport and falls back to Quickshell IPC when the call has
not executed (unsupported request or connection failure). It avoids retrying
an uncertain timeout after possible execution, preventing duplicate actions.
**Keep using the
wrapper**, rather than implementing its socket protocol or requiring these
newer shortcut internals. Their performance benefit remains unmeasured for our
gesture path. [Helper source][helpers], [shortcut registry][shortcuts],
[IPC wrapper][ipc], [shell host][host]

## 2. Verified plugin integration contract

The desktop runs inside one long-lived Quickshell process. A Omalogi settings
surface can be a third-party plugin inside that process, without another
standalone Quickshell instance. Entry-point QML roots are `Item`s, not
`ShellRoot`; panels expose `open(payloadJson)` and `close()`. The host injects
`omarchyPath`, `shell`, `manifest`, and the applicable registry interfaces.
Use the supplied path rather than hardcoding an installation location.
[Development contract][dev], [runtime paths][paths]

The manifest requires numeric **`schemaVersion: 1`**, namespaced `id`, `name`,
`version`, `kinds`, and `entryPoints`. The `omarchy.*` namespace is reserved for
built-ins. Entry points must be safe relative paths to existing files, with an
entry for every declared kind. No symlinks are allowed anywhere inside the
plugin folder. `bar-widget` uses the **`barWidget`** entry-point key. Check the
draft with `omarchy plugin validate .` before distribution.
[Validator][validator], [registry][registry]

Illustrative manifest shape, **not a shipped manifest**; final namespace is
still to be selected:

```json
{
  "schemaVersion": 1,
  "id": "omalogi.mouse",
  "name": "Omalogi",
  "version": "0.1.0",
  "kinds": ["panel", "bar-widget"],
  "entryPoints": {
    "panel": "OmalogiPanel.qml",
    "barWidget": "OmalogiWidget.qml"
  },
  "barWidget": {
    "displayName": "Omalogi",
    "category": "Hardware",
    "defaultSection": "right",
    "allowMultiple": false
  }
}
```

Third-party facades are API boundaries, **not a QML sandbox**. Plugins retain
user-level process/file access and share ordinary scene objects, so calling a
CLI through QML `Process` is compatible with the model. Use public IPC for
desktop actions, rather than treating the injected facade as access to another
plugin's live service. Avoid requiring a shell service for the V1 widget until
its behavior under replacement bars is designed. [Shell reference][shell]

For native appearance, use `Color`, `Style`, and `Border` from `qs.Commons`,
`BorderSurface` where appropriate, semantic spacing/font tokens, and the shared
normal, hover-cursor, focus, and selected control states. These are the current
theme contract; literal pixel/color values would lose user scaling/theme
integration. [Theme reference][theming], [token implementation][style]

## 3. Commands the gesture executor can invoke

The canonical shell entry point is **`omarchy-shell`**. It talks to the running
shell; it does not launch it. The host IPC target is `shell`, and **there is no
`bar` target**. Exit status alone is insufficient for every method: documented
replies can include `unknown` or an error string with exit zero, so our CLI must
inspect the reply as well. [IPC wrapper][ipc], [shell reference][shell]

| Action | Current invocation |
| --- | --- |
| Root menu | `omarchy menu toggle root` |
| Applications menu | `omarchy menu toggle apps` |
| System menu | `omarchy menu toggle system` |
| Clipboard | `omarchy-shell shell toggle omarchy.clipboard` |
| Emoji picker | `omarchy-shell shell toggle omarchy.emojis` |
| Audio/network/Bluetooth/display panel | `omarchy-shell shell toggle <plugin-id>` with `omarchy.audio`, `omarchy.network`, `omarchy.bluetooth`, or `omarchy.monitor` |
| Omalogi settings panel | `omarchy-shell shell toggle <our-plugin-id>` |
| Screenshot | `omarchy-capture-screenshot` |
| Next workspace | `hyprctl dispatch 'hl.dsp.focus({ workspace = "e+1" })'` |
| Previous workspace | `hyprctl dispatch 'hl.dsp.focus({ workspace = "e-1" })'` |
| Former workspace | `hyprctl dispatch 'hl.dsp.focus({ workspace = "previous" })'` |
| Scratchpad | `hyprctl dispatch 'hl.dsp.workspace.toggle_special("scratchpad")'` |

Menu invocations follow the shipped routes and wrapper; workspace expressions
come from the stock Lua bindings. The current Hyprland wiki defines `dispatch`
as a shorthand for evaluating `hl.dispatch(...)`; these commands have **not**
been executed against the local compositor in this refresh.
[Menu wrapper][menucli], [utilities][utilities], [tiling bindings][tiling],
[Hyprland hyprctl reference][hyprctl]

For desktop actions, execute the corresponding command/dispatcher directly.
The project should not depend on synthetic Super shortcuts activating desktop
bindings. Stock actions may now use global shortcuts internally, but those
bindings are an implementation detail, not a reason to require input injection.
Unknown actions should report failure rather than silently use an unverified
route. [Current action resolver][helpers]

A menu entry is optional through the user's
`~/.config/omarchy/extensions/omarchy-menu.jsonc`. New entries use dotted IDs,
labels, descriptions and actions; **do not add new aliases**. Only whole-line
`//` comments are accepted by its parser. [Menu extension reference][menu]

## 4. Updated project direction — proposed, not implemented

**V1 remains Solaar-backed:** MX Master 3/3S gesture button → tap or four
directions → Solaar `Execute: [omalogi, trigger, <gesture>]` → project CLI
→ configured Omarchy command or Hyprland Lua dispatcher. This preserves the
external Solaar boundary described in [Solaar integration](solaar-integration.md).
Keep the input-capture backend separate from action execution so a future
backend can reuse the same actions and UI.

**UI recommendation:** a themed QML `panel` plus optional `bar-widget`, opened
through ordinary shell IPC. **CLI recommendation:** Rust `omalogi` as the
single place for configuration, action execution, validation and apply/revert
operations. These remain architecture recommendations from research.

For this gesture-only V1, **no generated `bindings.lua`, loader insertion, or
`hyprctl reload` is inherently necessary**. Solaar already launches the action
process. If we later offer ordinary button remappings through device-scoped
Hyprland binds, that is a separate optional feature: generated Lua belongs in
project state, with a reversible user-config loader and validation. It should
not be a prerequisite for gesture capture. Solaar rule lifecycle and preserving
existing rules remain separate implementation work; the prior Solaar research
identifies its lack of a scriptable rule-file reload.

**Distribution recommendation:** plugin git repository for QML, explicitly
provisioned CLI and Solaar dependencies. `omarchy plugin add` performs no builds
or install hooks. A package for the Rust binary is practical; final Arch/AUR
versus bundled-binary delivery is still open. Enabling/removing the plugin
does not substitute for managing external Solaar rules, background startup or
their cleanup. [Plugin add source][add], [remove source][remove]

User plugin checkouts live in `~/.config/omarchy/plugins/<id>/`; `shell.json`
stores enabled state and widget placement. Once customized, this file is
canonical, without deep-merging new defaults. Prefer the supported enable/bar
commands to hand-replacing it. Package-owned files under `/usr/share/omarchy`
must not be the target of our installer. [Plugin manual][manual],
[configuration implementation][config], [file layout][layout]

**V2 remains future exploration:** native user-space HID++ gesture capture,
with reconnection/coexistence requirements from
[the native-path assessment](hidpp-native-path.md). This refresh does not
authorize replacing Solaar or prove the hardware behavior.

## 5. Validation and remaining work

Read-only local inspection found **Omarchy `4.0.4-1`, Hyprland `0.56.2-2`, and
Quickshell `0.3.1-1`** installed; Solaar is absent. The installed files support
the plugin architecture, but the compositor socket was inaccessible from this
session, so no live gesture, dispatcher, panel, or latency test was possible.
No user desktop configuration was changed. Installed release behavior must be
tested separately from the latest upstream branch inspected here.

Next implementation gate: a hardware spike validating tap + four directions,
release-to-action latency, Bolt/Bluetooth naming and reconnection. Then validate
a minimal plugin/CLI pair on the actual supported release, including missing
CLI/Solaar, shell-offline behavior, apply/revert preserving user rules, and the
widget's behavior with a replacement bar. Select the plugin ID, packaging and
supported-version floor before publishing. There is no need to run a desktop
update merely to establish these contracts.

## Sources

[snapshot]: https://github.com/omacom/omarchy/tree/8b4eae66da2938ba9559f103b18dbf85cdf28a70
[shell]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/docs/omarchy-shell.md
[manual]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/manual/32-shell-plugins.md
[validator]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/bin/omarchy-plugin-validate
[registry]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/shell/services/PluginRegistry.qml
[add]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/bin/omarchy-plugin-add
[remove]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/bin/omarchy-plugin-remove
[ipc]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/bin/omarchy-shell
[host]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/shell/shell.qml
[helpers]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/default/hypr/helpers.lua
[shortcuts]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/default/omarchy/shortcuts
[dev]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/agents/skills/shell-dev.md
[paths]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/default/hypr/paths.lua
[theming]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/docs/theming.md
[style]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/shell/Commons/Style.qml
[menu]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/docs/menu.md
[menudata]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/default/omarchy/omarchy-menu.jsonc
[menucli]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/bin/omarchy-menu
[utilities]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/default/hypr/bindings/utilities.lua
[tiling]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/default/hypr/bindings/tiling.lua
[elsewhen]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/docs/elsewhen.md
[layout]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/docs/file-layout.md
[config]: https://github.com/omacom/omarchy/blob/8b4eae66da2938ba9559f103b18dbf85cdf28a70/shell/shell.qml
[hyprctl]: https://wiki.hypr.land/configuring/core/advanced-configuration/using-hyprctl/
