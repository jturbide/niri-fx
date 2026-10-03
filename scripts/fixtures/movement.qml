// Original sample app cards for public demos. No files, accounts or user data.
import QtQuick
import Quickshell

ShellRoot {
    FloatingWindow {
        id: window
        readonly property string label: Quickshell.env("NIRIFX_LABEL") || "Notes"
        readonly property color accent: Quickshell.env("NIRIFX_COLOR") || "#b7e8db"
        title: "NiriFX fixture / " + label
        implicitWidth: 520
        implicitHeight: 740
        color: "transparent"

        Rectangle {
            id: card
            anchors.fill: parent
            anchors.margins: 12
            radius: 24
            color: window.accent

            Rectangle {
                x: 20; y: 20
                width: parent.width - 40; height: 48
                radius: 14
                color: "#182735"
                Text {
                    x: 18
                    anchors.verticalCenter: parent.verticalCenter
                    text: window.label
                    color: window.accent
                    font.pixelSize: 18
                    font.weight: Font.DemiBold
                }
                Row {
                    anchors.right: parent.right
                    anchors.rightMargin: 18
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 6
                    Repeater {
                        model: 3
                        Rectangle { width: 6; height: 6; radius: 3; color: "#758891" }
                    }
                }
            }

            Column {
                x: 32; y: 106
                width: parent.width - 64
                spacing: 14
                Text {
                    text: window.label === "Notes" ? "The next idea." : "Your collection."
                    color: "#172735"
                    font.pixelSize: 34
                    font.weight: Font.DemiBold
                }
                Text {
                    text: window.label === "Notes" ? "A little space to create." : "Everything in its place."
                    color: "#415260"
                    font.pixelSize: 16
                }
                Item { width: 1; height: 10 }
                Repeater {
                    model: ["01   Sketch the motion", "02   Explore the details", "03   Make it yours"]
                    Rectangle {
                        required property string modelData
                        required property int index
                        width: card.width - 64; height: 80
                        radius: 15
                        color: "#f6f8fc"
                        Text {
                            x: 18; y: 18
                            text: parent.modelData
                            color: "#263746"
                            font.pixelSize: 15
                            font.weight: Font.Medium
                        }
                        Rectangle {
                            x: 18; y: 48
                            width: parent.width * (0.72 - parent.index * 0.12); height: 6
                            radius: 3
                            color: "#dce2e8"
                        }
                    }
                }
            }
            Text {
                x: 32
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 26
                text: "NiriFX   /   WINDOW EFFECTS"
                color: "#415260"
                font.pixelSize: 12
                font.letterSpacing: 1.5
            }
        }
    }
}
