import QtQuick
import QtQuick.Shapes
import qs.Commons

// Authored vector, traced from the user's top-view MX Master 3S reference.
Item {
    id: root
    property string highlighted: ""
    signal controlClicked(string control)
    readonly property color ink: Color.popups.text
    readonly property color outline: Qt.rgba(ink.r, ink.g, ink.b, 0.68)
    function fill(alpha) { return Qt.rgba(ink.r, ink.g, ink.b, alpha) }
    function accent(control) { return highlighted === control ? Color.accent : outline }
    function controlFill(control) { return highlighted === control ? Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.24) : fill(0.13) }
    function point(control) {
        var points = {wheel:[186,87],forward:[98,231],back:[97,252],thumb:[93,193],gesture:[44,246]}
        var p = points[control] || [160,210]
        return drawing.mapToItem(root, p[0], p[1])
    }
    implicitWidth: Style.space(320)
    implicitHeight: Style.space(420)

    Item {
        id: drawing
        width: 320; height: 420
        scale: Math.min(root.width / width, root.height / height)
        anchors.centerIn: parent
        Shape {
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            // Broad palm, rounded nose and the asymmetric thumb shelf.
            ShapePath {
                fillColor: root.fill(0.08); strokeColor: root.outline; strokeWidth: 1.8
                PathSvg { path: "M143 8 C119 4 104 16 102 43 C100 72 102 106 100 131 C98 146 91 153 75 162 L53 172 C31 185 25 215 24 249 C22 278 20 311 29 333 C39 355 73 377 110 395 C140 410 160 420 183 416 C216 411 253 389 271 366 C289 343 294 319 294 285 L287 120 C285 86 283 58 271 43 C245 24 184 10 143 8 Z" }
            }
            // Lower rim is a physical seam, rather than an extra outline around the controls.
            ShapePath {
                fillColor: root.fill(0.06); strokeColor: root.fill(0.30); strokeWidth: 1
                PathSvg { path: "M26 314 C35 344 78 370 124 393 C149 405 165 411 182 407 C222 401 263 374 279 346 C270 373 226 410 183 416 C160 420 140 410 110 395 C72 377 39 355 29 333 Z" }
            }
            // Continuous upper shell, with the thumb-side seam tucked under the wheel.
            ShapePath {
                fillColor: root.fill(0.10); strokeColor: root.fill(0.38); strokeWidth: 1.1
                PathSvg { path: "M102 43 C104 16 119 4 143 8 C184 10 245 24 271 43 C283 58 285 86 287 120 L293 282 C295 322 283 346 265 365 C243 388 208 404 181 407 C150 399 125 372 110 343 C95 313 89 283 91 254 L94 216 L96 165 L100 131 Z" }
            }
            // Sculpted thumb rest: wider at the heel, narrow at the shoulder.
            ShapePath {
                fillColor: root.fill(0.025); strokeColor: root.fill(0.36); strokeWidth: 1
                PathSvg { path: "M94 166 C76 176 61 178 51 190 C37 208 33 241 33 269 C31 292 35 313 44 326 C58 344 85 361 119 378 C100 351 85 321 81 289 C76 254 81 218 91 199 Z" }
            }
            // Left and right primary buttons follow the nearly upright photographic view.
            ShapePath {
                fillColor: root.fill(0.05); strokeColor: root.outline; strokeWidth: 1.25
                PathSvg { path: "M143 8 C119 4 104 16 102 43 L101 157 C118 156 143 151 165 145 L166 58 Q166 45 178 44 L187 45 L187 14" }
            }
            ShapePath {
                fillColor: root.fill(0.075); strokeColor: root.outline; strokeWidth: 1.25
                PathSvg { path: "M191 15 L191 45 L204 47 Q213 48 213 60 L213 151 C228 158 248 165 264 170 Q273 174 273 161 C275 122 274 76 268 43" }
            }
            // Wheel recess and vertical metal wheel, with a central rubber band.
            ShapePath {
                fillColor: root.fill(0.025); strokeColor: root.outline; strokeWidth: 1.2
                PathSvg { path: "M178 48 L202 50 Q208 51 208 59 L208 115 Q208 123 201 123 L176 122 Q170 122 170 114 L170 58 Q170 48 178 48 Z" }
            }
            ShapePath {
                fillColor: root.controlFill("wheel"); strokeColor: root.accent("wheel"); strokeWidth: 1.5
                PathSvg { path: "M177 61 Q183 58 195 61 L198 113 Q189 117 177 113 Z" }
            }
            ShapePath {
                fillColor: root.fill(0.025); strokeColor: root.accent("wheel"); strokeWidth: 0.8
                PathSvg { path: "M184 61 L190 61 L192 114 L185 114 Z" }
            }
            ShapePath {
                fillColor: "transparent"; strokeColor: root.accent("wheel"); strokeWidth: 0.75
                PathSvg { path: "M177 66 L184 66 M191 66 L195 67 M177 71 L184 71 M191 71 L196 72 M177 76 L184 76 M191 76 L196 77 M177 81 L184 81 M191 81 L196 82 M177 86 L185 86 M191 86 L196 87 M177 91 L185 91 M191 91 L197 92 M177 96 L185 96 M192 96 L197 97 M177 101 L185 101 M192 101 L197 102 M177 106 L185 106 M192 106 L197 107 M177 111 L185 111 M192 111 L197 112" }
            }
            // Mechanical wheel-mode button, preserved as an unassigned physical control.
            ShapePath {
                fillColor: root.fill(0.09); strokeColor: root.outline; strokeWidth: 1.2
                PathSvg { path: "M184 150 Q188 149 196 151 Q200 151 200 156 L200 174 Q200 179 195 179 L185 178 Q181 178 181 174 L181 155 Q181 150 184 150 Z" }
            }
            // Thumb wheel protrudes from the edge of the shell.
            ShapePath {
                fillColor: root.controlFill("thumb"); strokeColor: root.accent("thumb"); strokeWidth: 1.5
                PathSvg { path: "M87 173 Q91 169 99 172 L100 214 Q95 220 87 220 Q83 217 84 211 L85 181 Q85 175 87 173 Z" }
            }
            ShapePath {
                fillColor: "transparent"; strokeColor: root.accent("thumb"); strokeWidth: 0.8
                PathSvg { path: "M88 175 L87 189 M92 173 L91 189 M96 173 L95 189 M99 175 L98 189 M85 193 L100 191 M85 198 L100 196 M87 201 L86 216 M91 200 L90 218 M95 200 L94 217 M99 199 L98 214" }
            }
            ShapePath {
                fillColor: root.controlFill("forward"); strokeColor: root.accent("forward"); strokeWidth: 1.2
                PathSvg { path: "M94 224 Q98 220 101 222 L102 238 Q98 241 94 237 Z" }
            }
            ShapePath {
                fillColor: root.controlFill("back"); strokeColor: root.accent("back"); strokeWidth: 1.2
                PathSvg { path: "M93 242 Q97 241 101 240 L100 259 Q97 266 94 262 Z" }
            }
            // The gesture switch sits on the outer thumb rest, not on the palm shell.
            ShapePath {
                fillColor: root.controlFill("gesture"); strokeColor: root.accent("gesture"); strokeWidth: 1.2
                PathSvg { path: "M43 229 Q46 225 48 230 L47 250 Q46 256 42 254 L41 250 Z" }
            }
            ShapePath {
                fillColor: "transparent"; strokeColor: root.fill(0.12); strokeWidth: 1
                PathSvg { path: "M55 192 C45 238 48 302 79 347 M63 188 C51 239 61 309 93 356 M71 185 C58 235 70 313 107 362 M79 183 C65 238 79 306 115 357 M50 214 C40 263 48 309 62 328 M39 257 C37 288 42 311 49 319" }
            }
        }
        Text {
            x: 108; y: 137; rotation: -13; text: "logi"
            color: root.fill(0.58); font.family: Style.font.family; font.pixelSize: 14
        }
        Repeater {
            model: [
                {control:"wheel",label:"Vertical wheel",x:170,y:53,w:38,h:70},
                {control:"forward",label:"Forward button",x:92,y:221,w:14,h:20},
                {control:"back",label:"Back button",x:90,y:241,w:16,h:26},
                {control:"thumb",label:"Horizontal wheel",x:80,y:169,w:25,h:51},
                {control:"gesture",label:"Gesture button",x:35,y:222,w:19,h:40}
            ]
            Item {
                required property var modelData
                x: modelData.x; y: modelData.y; width: modelData.w; height: modelData.h
                Accessible.name: modelData.label; Accessible.role: Accessible.Button
                Accessible.onPressAction: root.controlClicked(modelData.control)
                MouseArea {
                    anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onEntered: root.highlighted = parent.modelData.control
                    onExited: root.highlighted = ""
                    onClicked: root.controlClicked(parent.modelData.control)
                }
            }
        }
    }
}
