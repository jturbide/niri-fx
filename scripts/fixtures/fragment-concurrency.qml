// SPDX-License-Identifier: MIT
// Distinct, compact synthetic surfaces for simultaneous fragment acceptance.
import QtQuick
import Quickshell

ShellRoot {
    FloatingWindow {
        id: window

        readonly property string label: Quickshell.env("NIRIFX_LABEL") || "Material A"
        readonly property color accent: Quickshell.env("NIRIFX_COLOR") || "#b7e8db"
        property int clicks: 0

        title: "NiriFX pointer / " + label + " / clicks " + clicks
        implicitWidth: 420
        implicitHeight: 330
        color: "#182735"

        Rectangle {
            anchors.fill: parent
            anchors.margins: 10
            radius: 18
            color: window.accent

            Rectangle {
                x: 14
                y: 14
                width: parent.width - 28
                height: 56
                radius: 12
                color: "#182735"

                Text {
                    anchors.centerIn: parent
                    text: window.label + "  ·  drag here"
                    color: window.accent
                    font.pixelSize: 16
                }

                MouseArea {
                    anchors.fill: parent
                    onPressed: console.log("NIRIFX_MOVE_REQUEST " + window.startSystemMove())
                }

            }

            Text {
                x: 28
                y: 98
                text: window.label
                color: "#182735"
                font.pixelSize: 30
                font.weight: Font.DemiBold
            }

            Repeater {
                model: 3

                Rectangle {
                    required property int index

                    x: 28
                    y: 151 + index * 23
                    width: (parent.width - 56) * (0.88 - index * 0.16)
                    height: 12
                    radius: 5
                    color: "#f6f8fc"
                }

            }

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.leftMargin: 28
                anchors.rightMargin: 28
                anchors.bottomMargin: 28
                height: 50
                radius: 12
                color: "#182735"

                Text {
                    anchors.centerIn: parent
                    text: "Input received  ·  " + window.clicks
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
