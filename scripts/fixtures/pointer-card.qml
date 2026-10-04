// SPDX-License-Identifier: MIT
// Synthetic content for genuine client-requested pointer move acceptance.
import QtQuick
import Quickshell

ShellRoot {
    FloatingWindow {
        id: window
        readonly property string label: Quickshell.env("NIRIFX_LABEL") || "Pointer motion"
        readonly property color accent: Quickshell.env("NIRIFX_COLOR") || "#b7e8db"
        property int clicks: 0
        title: "NiriFX pointer / " + label + " / clicks " + clicks
        implicitWidth: 460
        implicitHeight: 460
        color: "#182735"

        Rectangle {
            anchors.fill: parent
            anchors.margins: 10
            radius: 22
            color: window.accent

            Rectangle {
                id: header
                x: 14; y: 14
                width: parent.width - 28; height: 56
                radius: 14
                color: "#182735"
                Text {
                    anchors.centerIn: parent
                    text: window.label + "  ·  drag here"
                    color: window.accent
                    font.pixelSize: 17
                    font.weight: Font.DemiBold
                }
                MouseArea {
                    anchors.fill: parent
                    onPressed: {
                        const accepted = window.startSystemMove();
                        console.log("NIRIFX_MOVE_REQUEST " + accepted);
                    }
                }
            }
            Column {
                x: 28; y: 98
                width: parent.width - 56
                spacing: 16
                Text {
                    text: "Follow the feeling."
                    color: "#182735"
                    font.pixelSize: 29
                    font.weight: Font.DemiBold
                }
                Text {
                    text: "Drag. Reverse. Let go."
                    color: "#415260"
                    font.pixelSize: 16
                }
                Repeater {
                    model: 3
                    Rectangle {
                        required property int index
                        width: parent.width; height: 40
                        radius: 9
                        color: "#f6f8fc"
                        Rectangle {
                            x: 15; y: 17
                            width: parent.width * (0.7 - parent.index * 0.13); height: 5
                            radius: 3; color: "#dce2e8"
                        }
                    }
                }
            }
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 28
                height: 50; radius: 12
                color: "#182735"
                Text {
                    anchors.centerIn: parent
                    text: window.clicks ? "Input received  ·  " + window.clicks : "Click to check input"
                    color: window.accent
                    font.pixelSize: 15
                }
                MouseArea {
                    anchors.fill: parent
                    onClicked: window.clicks++
                }
            }
        }
    }
}
