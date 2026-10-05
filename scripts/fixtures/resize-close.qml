// SPDX-License-Identifier: MIT
// Synthetic resize-to-close showcase; no user content or desktop integration.
import QtQuick
import Quickshell

ShellRoot {
    FloatingWindow {
        id: window

        readonly property string label: Quickshell.env("NIRIFX_LABEL")
        readonly property color accent: Quickshell.env("NIRIFX_COLOR")

        title: "NiriFX resize close / " + label
        implicitWidth: 400
        implicitHeight: 360
        color: "#182735"

        Rectangle {
            anchors.fill: parent
            anchors.margins: 10
            radius: 22
            color: window.accent

            Text {
                x: 24
                y: 24
                text: window.label
                color: "#182735"
                font.pixelSize: 28
                font.weight: Font.DemiBold
            }

            Column {
                x: 24
                y: 92
                spacing: 22

                Repeater {
                    model: 3

                    Rectangle {
                        required property int index

                        width: window.width - 68
                        height: 44
                        radius: 10
                        color: "#f6f8fc"

                        Rectangle {
                            x: 16
                            y: 19
                            width: parent.width * (0.65 - parent.index * 0.1)
                            height: 6
                            radius: 3
                            color: "#dce2e8"
                        }

                    }

                }

            }

        }

    }

}
