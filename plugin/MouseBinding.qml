import QtQuick
import QtQuick.Layouts
import qs.Ui
import qs.Commons

ColumnLayout {
    id: root
    property string label: ""
    property string value: "native"
    property var options: []
    signal changed(string value)
    signal hovered(bool hovered)
    function openEditor() { if (enabled) picker.open() }
    spacing: Style.spacing.labelGap
    Text {
        Layout.fillWidth: true
        text: root.label
        textFormat: Text.PlainText
        color: Color.popups.text
        font.family: Style.font.family
        font.pixelSize: Style.font.body
    }
    Dropdown {
        id: picker
        Layout.fillWidth: true
        showLabel: false
        value: root.value
        options: root.options
        onChanged: function(value) { root.changed(value) }
        onHovered: function(hovered) { root.hovered(hovered) }
    }
}
