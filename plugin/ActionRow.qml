import QtQuick
import QtQuick.Layouts
import qs.Ui
import qs.Commons

RowLayout {
    id: root
    property string label: ""
    property string value: "native"
    property var options: []
    signal changed(string value)
    spacing: Style.spacing.panelGap
    Text {
        Layout.fillWidth: true
        textFormat: Text.PlainText
        text: root.label
        color: Color.popups.text
        font.family: Style.font.family
        font.pixelSize: Style.font.body
    }
    Dropdown {
        Layout.preferredWidth: Style.spacing.dropdownWidth
        showLabel: false
        value: root.value
        options: root.options
        onChanged: function(value) { root.changed(value) }
    }
}
