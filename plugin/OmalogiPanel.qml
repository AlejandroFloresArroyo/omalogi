import QtQuick
import QtQuick.Controls as QQC
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Ui
import qs.Commons

Item {
    id: root
    required property Item anchorItem
    required property QtObject bar
    required property QtObject ownerWidget
    property var profile: null
    property var device: null
    property var actionOptions: []
    property var events: []
    property string page: "Mouse"
    property string message: "Checking mouse…"
    property bool error: false
    property bool applied: false
    property bool daemon: false
    property bool dirty: false
    readonly property bool mutating: mutate.running
    readonly property var screen: window.screen
    readonly property point cardOrigin: window.cardOrigin
    readonly property int contentWidth: window.contentWidth
    readonly property int contentHeight: window.contentHeight
    readonly property bool opened: ownerWidget.opened
    property string pendingInput: ""
    property string mutation: ""
    property int revision: 0
    property int sentRevision: 0
    property bool failed: false
    property bool recoveryRequired: false
    readonly property bool editable: !!profile && !status.running && !(mutating && mutation === "restore")
    readonly property string binary: Quickshell.env("HOME") + "/.local/bin/omalogi"
    readonly property bool busy: mutate.running || status.running || binaryCheck.running
    readonly property color secondary: Qt.rgba(Color.popups.text.r, Color.popups.text.g, Color.popups.text.b, 0.78)
    // A CLI older than this panel reports no transport; show the remaining facts.
    readonly property string connection: device ? (device.transport ? device.transport + " · " : "") + device.id + " · " + (daemon ? "Connected" : "Event capture stopped") : "Connect and turn on your MX Master"

    function requestClose() { ownerWidget.close() }
    function refresh() {
        if (!busy && !dirty) { message = "Checking mouse…"; binaryCheck.running = true }
    }
    function update(next) {
        if (!editable || JSON.stringify(next) === JSON.stringify(profile)) return
        profile = next; revision++; dirty = true; failed = false; error = false
        message = recoveryRequired ? "Restore the mouse before saving changes." : mutating ? "Applying · next changes queued…" : "Saving automatically…"
        autoApply.restart()
    }
    function patch(group, key, value) {
        if (!profile) return
        var c = JSON.parse(JSON.stringify(profile)); c[group][key] = value
        update(c)
    }
    function flush() {
        if (dirty && !busy && !failed && !recoveryRequired && !dpiSlider.dragging) command("apply")
    }
    function binding(event) { return profile && profile.bindings[event] ? profile.bindings[event] : "native" }
    function hardware(key) { return profile && profile.hardware[key] ? profile.hardware[key] : "" }
    function supported(key) { return device && !!device.settings[key] }
    function choices(key) { return supported(key) ? device.settings[key].choices : [] }
    function gestureEnabled() { return profile && binding("gesture.click") !== "native" }
    function gestureToggle() {
        var enabled = !gestureEnabled()
        var c = JSON.parse(JSON.stringify(profile))
        var defaults = {click:"apps",up:"menu",down:"scratchpad",left:"workspace.previous",right:"workspace.next"}
        for (var d in defaults) c.bindings["gesture." + d] = enabled ? defaults[d] : "native"
        update(c)
    }
    function wheelBinding(event, value) {
        if (!profile) return
        var names = event.indexOf("thumb.") === 0 ? ["thumb.left", "thumb.right"] : ["wheel.up", "wheel.down"]
        var c = JSON.parse(JSON.stringify(profile))
        c.bindings[event] = value
        names.forEach(function(n) {
            if (value === "native") c.bindings[n] = "native"
            else if (c.bindings[n] === "native") c.bindings[n] = "none"
        })
        update(c)
    }
    function dpi(value) {
        var values = choices("dpi").map(Number)
        if (!values.length) return
        var nearest = values.reduce(function(a,b) { return Math.abs(b-value) < Math.abs(a-value) ? b : a })
        patch("hardware", "dpi", String(nearest))
    }
    function wheelOptions() {
        return actionOptions.map(function(a) { return a.value === "native" ? {value:"native",label:"Normal scrolling"} : a })
    }
    function gestureOptions() {
        return gestureEnabled() ? actionOptions.filter(function(a) { return a.value !== "native" }) : [{value:"native",label:"Default behavior"}]
    }
    Connections {
        target: root.ownerWidget
        function onOpenedChanged() {
            if (root.opened && !root.dirty) root.refresh()
            if (root.opened) Qt.callLater(function() { leaders.requestPaint() })
        }
    }
    function command(operation) {
        if (busy || !profile || (operation === "apply" && recoveryRequired)) return
        autoApply.stop()
        mutation = operation; sentRevision = revision; failed = false
        pendingInput = operation === "apply" || operation === "config" ? JSON.stringify(profile) : ""
        mutate.command = [binary, operation].concat(pendingInput ? ["--stdin"] : [])
        mutate.stdinEnabled = pendingInput !== ""
        message = operation === "restore" ? "Restoring previous settings…" : "Applying and verifying… You can close the panel."
        error = false; mutate.running = true
    }
    function diagnosis() {
        if (!profile || busy) return
        var c = JSON.parse(JSON.stringify(profile))
        Object.keys(c.bindings).forEach(function(e) { c.bindings[e] = "diagnostic" })
        page = "Extras"; update(c)
    }
    Process {
        id: binaryCheck
        command: ["test", "-x", root.binary]
        onExited: function(exitCode) {
            if (exitCode === 0) status.running = true
            else {
                root.error = true
                root.message = "Complete Omalogi setup using the instructions in the README."
            }
        }
    }
    Process {
        id: status
        command: [root.binary, "status"]
        stdout: StdioCollector { id: statusOut; waitForEnd: true }
        onExited: {
            try {
                var result = JSON.parse(statusOut.text)
                if (!result.ok) throw new Error(result.error)
                root.device = result.devices[0]
                if (!root.dirty) root.profile = result.config
                root.actionOptions = result.actions.map(function(a) { return {value:a.id,label:a.label} })
                root.events = result.events; root.applied = result.applied; root.daemon = result.daemon
                root.recoveryRequired = result.pending; root.error = result.pending
                root.message = result.pending ? "Incomplete operation · click Restore" : (root.applied ? "Profile active · event capture " + (root.daemon ? "connected" : "stopped") : "Original settings · changes are saved automatically")
            } catch (e) { root.error = true; root.message = String(e.message || e) }
            if (root.dirty) autoApply.restart()
        }
    }
    Timer { id: autoApply; interval: 450; onTriggered: root.flush() }
    Process {
        id: mutate
        onStarted: { if (root.pendingInput) { write(root.pendingInput); stdinEnabled = false } }
        stdout: StdioCollector { id: mutateOut; waitForEnd: true }
        onExited: {
            try {
                var result = JSON.parse(mutateOut.text)
                if (!result.ok) {
                    // CLI rollback errors explicitly ask for recovery; do not retry in a loop.
                    if ((result.error || "").indexOf("Run Restore") >= 0 || (result.error || "").indexOf("incomplete operation") >= 0) root.recoveryRequired = true
                    throw new Error(result.error)
                }
                root.error = false; root.failed = false; root.recoveryRequired = false
                if (root.mutation === "restore") {
                    root.dirty = false; root.applied = false
                    root.message = "Original settings restored"
                    Qt.callLater(root.refresh)
                } else {
                    root.applied = true; root.daemon = true
                    root.dirty = root.revision !== root.sentRevision
                    root.message = root.dirty ? "Next changes queued…" : "Saved · profile active"
                    if (root.dirty) autoApply.restart()
                }
            } catch (e) {
                root.error = true; root.failed = true
                root.message = String(e.message || e)
            }
        }
    }
    Process {
        id: eventPoll
        command: [root.binary, "events"]
        stdout: StdioCollector { id: eventsOut; waitForEnd: true }
        onExited: { try { root.events = JSON.parse(eventsOut.text).events || [] } catch (e) {} }
    }
    Timer { interval: 1200; repeat: true; running: root.opened && root.page === "Extras"; onTriggered: if (!eventPoll.running) eventPoll.running = true }

    KeyboardPanel {
        id: window
        anchorItem: root.anchorItem
        bar: root.bar
        owner: root.ownerWidget
        open: root.opened
        focusTarget: content
        contentWidth: fittedContentWidth(Style.space(920))
        contentHeight: cappedContentHeight(Style.space(690))

        FocusScope {
            id: content
            anchors.fill: parent
            focus: true
            Keys.onEscapePressed: root.requestClose()
            ColumnLayout {
                anchors.fill: parent
                spacing: Style.spacing.controlGap
                RowLayout {
                    Layout.fillWidth: true
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: Style.spacing.labelGap
                        Text { text: root.device ? root.device.name : "Omalogi"; color: Color.popups.text; font.family: Style.font.family; font.pixelSize: Style.font.heading; font.bold: true }
                        Text { text: root.connection; color: root.secondary; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Button { text: "Mouse"; selected: root.page === "Mouse"; focusable: true; onClicked: root.page = "Mouse" }
                    Button { text: "Extras"; selected: root.page === "Extras"; focusable: true; onClicked: root.page = "Extras" }
                    Item { Layout.fillWidth: true }
                    Text { text: root.error ? "Check the error" : root.mutating ? "Applying…" : root.dirty ? "Saving…" : root.applied ? "Profile active" : "Original settings"; color: root.dirty ? Color.accent : root.secondary; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                }
                PanelSeparator { Layout.fillWidth: true }
                ColumnLayout {
                    visible: root.page === "Mouse"
                    Layout.fillWidth: true; Layout.fillHeight: true
                    spacing: Style.spacing.controlGap
                    enabled: root.editable
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Style.spacing.panelGap
                        Text { text: "Sensitivity · DPI"; color: Color.popups.text; font.family: Style.font.family; font.pixelSize: Style.font.body }
                        PanelSlider {
                            id: dpiSlider
                            Layout.fillWidth: true
                            bar: root.bar
                            value: Number(root.hardware("dpi"))
                            minimum: root.choices("dpi").length ? Number(root.choices("dpi")[0]) : 200
                            maximum: root.choices("dpi").length ? Number(root.choices("dpi").slice(-1)[0]) : 8000
                            step: 50; integer: true
                            enabled: root.supported("dpi")
                            activeFocusOnTab: true
                            Accessible.name: "DPI sensitivity"
                            Accessible.role: Accessible.Slider
                            Keys.onLeftPressed: root.dpi(Number(root.hardware("dpi")) - 50)
                            Keys.onRightPressed: root.dpi(Number(root.hardware("dpi")) + 50)
                            onMoved: function(value) { root.dpi(value) }
                            onReleased: function(value) { root.dpi(value); if (root.dirty) autoApply.restart() }
                        }
                        SearchableDropdown {
                            Layout.preferredWidth: Style.space(130)
                            showLabel: false
                            value: root.hardware("dpi")
                            triggerLabel: root.hardware("dpi") + " DPI"
                            options: root.choices("dpi")
                            placeholderText: "Search DPI…"; emptyText: "No matches"
                            enabled: root.supported("dpi")
                            onChanged: function(value) { root.patch("hardware", "dpi", value) }
                        }
                    }
                    Item {
                        id: mapArea
                        Layout.fillWidth: true; Layout.fillHeight: true
                        Layout.minimumHeight: Style.space(380)
                        Canvas {
                            id: leaders
                            anchors.fill: parent
                            onWidthChanged: requestPaint()
                            onHeightChanged: requestPaint()
                            onPaint: {
                                var ctx = getContext("2d"); ctx.reset()
                                function trace(editor,control) {
                                    var p = diagram.point(control); p = diagram.mapToItem(leaders, p.x, p.y)
                                    var a = editor.mapToItem(leaders, editor.width, editor.height / 2)
                                    ctx.strokeStyle = diagram.highlighted === control ? Color.accent : Qt.rgba(Color.popups.text.r,Color.popups.text.g,Color.popups.text.b,0.2)
                                    ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(a.x,a.y)
                                    ctx.lineTo(a.x + Style.space(14), a.y); ctx.lineTo(p.x,p.y); ctx.stroke()
                                    ctx.beginPath(); ctx.arc(p.x,p.y,2,0,Math.PI*2); ctx.stroke()
                                }
                                trace(forwardEditor,"forward"); trace(backEditor,"back")
                                trace(thumbLeftEditor,"thumb"); trace(thumbRightEditor,"thumb")
                                trace(wheelUpEditor,"wheel"); trace(wheelDownEditor,"wheel")
                            }
                        }
                        RowLayout {
                            anchors.fill: parent
                            spacing: Style.space(18)
                            ColumnLayout {
                                Layout.preferredWidth: mapArea.width * 0.28
                                Layout.alignment: Qt.AlignVCenter
                                spacing: Style.space(10)
                                MouseBinding { id: forwardEditor; Layout.fillWidth: true; label: "Forward"; value: root.binding("button.forward"); options: root.actionOptions; onChanged: function(value) { root.patch("bindings","button.forward",value) }; onHovered: function(hovered) { diagram.highlighted = hovered ? "forward" : "" } }
                                MouseBinding { id: backEditor; Layout.fillWidth: true; label: "Back"; value: root.binding("button.back"); options: root.actionOptions; onChanged: function(value) { root.patch("bindings","button.back",value) }; onHovered: function(hovered) { diagram.highlighted = hovered ? "back" : "" } }
                                PanelSeparator { Layout.fillWidth: true }
                                MouseBinding { id: thumbLeftEditor; Layout.fillWidth: true; label: "Horizontal wheel · left"; value: root.binding("thumb.left"); options: root.wheelOptions(); enabled: root.supported("thumb-scroll-mode"); onChanged: function(value) { root.wheelBinding("thumb.left",value) }; onHovered: function(hovered) { diagram.highlighted = hovered ? "thumb" : "" } }
                                MouseBinding { id: thumbRightEditor; Layout.fillWidth: true; label: "Horizontal wheel · right"; value: root.binding("thumb.right"); options: root.wheelOptions(); enabled: root.supported("thumb-scroll-mode"); onChanged: function(value) { root.wheelBinding("thumb.right",value) }; onHovered: function(hovered) { diagram.highlighted = hovered ? "thumb" : "" } }
                                PanelSeparator { Layout.fillWidth: true }
                                MouseBinding { id: wheelUpEditor; Layout.fillWidth: true; label: "Vertical wheel · up"; value: root.binding("wheel.up"); options: root.wheelOptions(); enabled: root.supported("hires-scroll-mode") || root.supported("lowres-scroll-mode"); onChanged: function(value) { root.wheelBinding("wheel.up",value) }; onHovered: function(hovered) { diagram.highlighted = hovered ? "wheel" : "" } }
                                MouseBinding { id: wheelDownEditor; Layout.fillWidth: true; label: "Vertical wheel · down"; value: root.binding("wheel.down"); options: root.wheelOptions(); enabled: root.supported("hires-scroll-mode") || root.supported("lowres-scroll-mode"); onChanged: function(value) { root.wheelBinding("wheel.down",value) }; onHovered: function(hovered) { diagram.highlighted = hovered ? "wheel" : "" } }
                            }
                            MouseDiagram {
                                id: diagram
                                Layout.fillWidth: true; Layout.fillHeight: true
                                Layout.minimumWidth: Style.space(180)
                                onHighlightedChanged: leaders.requestPaint()
                                onControlClicked: function(control) {
                                    if (control === "forward") forwardEditor.openEditor()
                                    else if (control === "back") backEditor.openEditor()
                                    else if (control === "thumb") thumbLeftEditor.openEditor()
                                    else if (control === "wheel") wheelUpEditor.openEditor()
                                    else { if (!root.gestureEnabled()) root.gestureToggle(); Qt.callLater(function() { gestureClickEditor.openEditor() }) }
                                }
                            }
                            ColumnLayout {
                                Layout.preferredWidth: mapArea.width * 0.30
                                Layout.alignment: Qt.AlignVCenter
                                spacing: Style.space(10)
                                Toggle { Layout.fillWidth: true; label: "Gestures"; checked: root.gestureEnabled(); onClicked: root.gestureToggle() }
                                Text { Layout.fillWidth: true; text: "Hold, move and release."; color: root.secondary; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                                MouseBinding { id: gestureClickEditor; Layout.fillWidth: true; label: "Click without moving"; value: root.binding("gesture.click"); enabled: root.gestureEnabled(); options: root.gestureOptions(); onChanged: function(value) { root.patch("bindings","gesture.click",value) }; onHovered: function(hovered) { diagram.highlighted = hovered ? "gesture" : "" } }
                                MouseBinding { Layout.fillWidth: true; label: "Up"; value: root.binding("gesture.up"); enabled: root.gestureEnabled(); options: root.gestureOptions(); onChanged: function(value) { root.patch("bindings","gesture.up",value) }; onHovered: function(hovered) { diagram.highlighted = hovered ? "gesture" : "" } }
                                MouseBinding { Layout.fillWidth: true; label: "Down"; value: root.binding("gesture.down"); enabled: root.gestureEnabled(); options: root.gestureOptions(); onChanged: function(value) { root.patch("bindings","gesture.down",value) }; onHovered: function(hovered) { diagram.highlighted = hovered ? "gesture" : "" } }
                                MouseBinding { Layout.fillWidth: true; label: "Left"; value: root.binding("gesture.left"); enabled: root.gestureEnabled(); options: root.gestureOptions(); onChanged: function(value) { root.patch("bindings","gesture.left",value) }; onHovered: function(hovered) { diagram.highlighted = hovered ? "gesture" : "" } }
                                MouseBinding { Layout.fillWidth: true; label: "Right"; value: root.binding("gesture.right"); enabled: root.gestureEnabled(); options: root.gestureOptions(); onChanged: function(value) { root.patch("bindings","gesture.right",value) }; onHovered: function(hovered) { diagram.highlighted = hovered ? "gesture" : "" } }
                            }
                        }
                    }
                    Text { Layout.fillWidth: true; text: "Assigning a wheel action replaces normal scrolling. Middle click keeps its function."; color: root.secondary; font.family: Style.font.family; font.pixelSize: Style.font.caption; wrapMode: Text.WordWrap }
                }
                QQC.ScrollView {
                    visible: root.page === "Extras"
                    Layout.fillWidth: true; Layout.fillHeight: true
                    contentWidth: availableWidth; clip: true
                    ColumnLayout {
                        width: parent.width
                        spacing: Style.spacing.panelGap
                        enabled: root.editable
                        Text { text: "Scroll wheels"; color: Color.popups.text; font.family: Style.font.family; font.pixelSize: Style.font.subtitle; font.bold: true }
                        Toggle { Layout.fillWidth: true; label: "Invert vertical scrolling"; checked: root.hardware("hires-smooth-invert") === "true"; enabled: root.supported("hires-smooth-invert"); onClicked: root.patch("hardware", "hires-smooth-invert", checked ? "false" : "true") }
                        Toggle { Layout.fillWidth: true; label: "Higher vertical resolution"; checked: root.hardware("hires-smooth-resolution") === "true"; enabled: root.supported("hires-smooth-resolution"); onClicked: root.patch("hardware", "hires-smooth-resolution", checked ? "false" : "true") }
                        Toggle { Layout.fillWidth: true; label: "Invert horizontal scrolling"; checked: root.hardware("thumb-scroll-invert") === "true"; enabled: root.supported("thumb-scroll-invert"); onClicked: root.patch("hardware", "thumb-scroll-invert", checked ? "false" : "true") }
                        ActionRow { Layout.fillWidth: true; label: "Vertical scroll mode"; options: [{value:"Ratcheted",label:"Ratcheted"},{value:"Freespinning",label:"Free spin"}]; value: root.hardware("scroll-ratchet"); enabled: root.supported("scroll-ratchet"); onChanged: function(value) { root.patch("hardware", "scroll-ratchet", value) } }
                        RowLayout {
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: "SmartShift · spin threshold"; color: Color.popups.text; font.family: Style.font.family; font.pixelSize: Style.font.body }
                            NumberField { from: 1; to: 50; value: Number(root.hardware("smart-shift")); enabled: root.supported("smart-shift") && root.hardware("scroll-ratchet") === "Ratcheted"; onModified: function(value) { root.patch("hardware", "smart-shift", String(value)) } }
                        }
                        Text { Layout.fillWidth: true; text: root.hardware("scroll-ratchet") === "Freespinning" ? "The saved threshold is used when returning to ratcheted mode." : "1–50; 50 keeps the wheel in ratcheted mode."; color: root.secondary; font.family: Style.font.family; font.pixelSize: Style.font.caption; wrapMode: Text.WordWrap }
                        PanelSeparator { Layout.fillWidth: true }
                        RowLayout {
                            Layout.fillWidth: true
                            Text { Layout.fillWidth: true; text: "Mouse diagnostics"; color: Color.popups.text; font.family: Style.font.family; font.pixelSize: Style.font.subtitle; font.bold: true }
                            Button { text: "Enable temporary logging"; focusable: true; onClicked: root.diagnosis() }
                        }
                        Text { Layout.fillWidth: true; text: "Temporary logging replaces all actions. Reassign your controls or restore the original settings afterward."; wrapMode: Text.WordWrap; color: root.secondary; font.family: Style.font.family; font.pixelSize: Style.font.body }
                        PanelSeparator { Layout.fillWidth: true }
                        Button { text: "Restore original settings"; focusable: true; enabled: !root.busy && !!root.profile; onClicked: root.command("restore") }
                        Text { visible: root.events.length === 0; text: "No events recorded yet."; color: root.secondary; font.family: Style.font.family; font.pixelSize: Style.font.body }
                        Repeater {
                            model: root.events.slice(-8).reverse()
                            Text { required property var modelData; Layout.fillWidth: true; textFormat: Text.PlainText; text: modelData.event + " → " + modelData.action + " · " + modelData.source + (modelData.ok ? " ✓" : " · " + modelData.error); wrapMode: Text.WordWrap; color: modelData.ok ? Color.popups.text : Color.urgent; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                        }
                    }
                }
                Text { Layout.fillWidth: true; textFormat: Text.PlainText; text: root.message; wrapMode: Text.WordWrap; color: root.error ? Color.urgent : root.secondary; font.family: Style.font.family; font.pixelSize: Style.font.caption }
                Button {
                    text: "Restore to recover"; visible: root.recoveryRequired
                    focusable: true; enabled: !root.busy && !!root.profile
                    onClicked: root.command("restore")
                }
                Button {
                    text: "Retry changes"; focusable: true
                    visible: root.failed && root.dirty && !root.recoveryRequired
                    enabled: !root.busy
                    onClicked: root.command("apply")
                }

            }
        }
    }
}
