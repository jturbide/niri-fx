// SPDX-License-Identifier: MIT
// Synthetic cards for native resize comparisons; no user files or session data.
import QtQuick
import Quickshell

ShellRoot {
    FloatingWindow {
        id: window
        readonly property string label: Quickshell.env("NIRIFX_LABEL")
        readonly property color accent: Quickshell.env("NIRIFX_COLOR")
        title: "NiriFX resize / " + label
        implicitWidth: 360
        implicitHeight: 300
        color: accent
        Rectangle {
            x: 18; y: 18
            width: parent.width - 36; height: 56
            radius: 14; color: "#182735"
            Text {
                anchors.centerIn: parent
                text: window.label
                color: window.accent
                font.pixelSize: 22
                font.weight: Font.DemiBold
            }
        }
        Column {
            x: 28; y: 100
            spacing: 12
            Text {
                text: Quickshell.env("NIRIFX_CAPTION")
                color: "#182735"; font.pixelSize: 18
                font.weight: Font.DemiBold
            }
            Text {
                text: "Resize. Reverse. Settle."
                color: "#415260"; font.pixelSize: 16
            }
            Repeater {
                model: 2
                Rectangle {
                    required property int index
                    width: window.width - 56; height: 20
                    radius: 8; color: "#f6f8fc"
                }
            }
        }
    }
}
