import QtQuick
import Quickshell.Io
import qs.Ui
import qs.Commons

Panel {
    id: root
    property var shell: null
    property var manifest: null
    moduleName: "omalogi.mouse"
    manageIpc: false
    implicitWidth: button.implicitWidth
    implicitHeight: button.implicitHeight
    // The persistent panel owns the process; hiding only releases the popup input layer.
    function close() { controller.hide() }
    BarIconButton {
        id: button
        bar: root.bar
        text: "󰍽"
        tooltipText: "Omalogi · configure MX Master"
        onPressed: function(button) { if (button === Qt.LeftButton) root.toggle() }
    }
    OmalogiPanel { id: panel; ownerWidget: root; anchorItem: button; bar: root.bar }
    // Monitor-scoped UI navigation and geometry for local diagnostics/captures.
    IpcHandler {
        enabled: root.opened
        target: "omalogi.mouse." + (panel.screen ? panel.screen.name : "unknown")
        function view(name: string): void { if (name === "Mouse" || name === "Extras") panel.page = name }
        function geometry(): string {
            return JSON.stringify({screen:panel.screen ? panel.screen.name : "",x:panel.cardOrigin.x,y:panel.cardOrigin.y,width:panel.contentWidth,height:panel.contentHeight,page:panel.page,dirty:panel.dirty,busy:panel.busy})
        }
    }
}
