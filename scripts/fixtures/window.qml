// Synthetic content only. Transparent margins and a gutter expose alpha leaks.
import QtQuick
import Quickshell

ShellRoot {
    FloatingWindow {
        title: "NiriFX fixture / " + (Quickshell.env("NIRIFX_LABEL") || "transparent")
        implicitWidth: Number(Quickshell.env("NIRIFX_WIDTH") || 600)
        implicitHeight: Number(Quickshell.env("NIRIFX_HEIGHT") || 400)
        color: "transparent"

        Rectangle {
            anchors.fill: parent
            anchors.margins: 32
            color: Quickshell.env("NIRIFX_COLOR") || "#245d8a"
            radius: 24

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 22
                height: 54
                radius: 12
                color: "#367956"

                Text {
                    anchors.centerIn: parent
                    text: "NiriFX / synthetic window"
                    color: "white"
                    font.pixelSize: 20
                }

            }

        }

        // A separate tile leaves a transparent gutter beside the main rectangle.
        Rectangle {
            x: 0
            y: 8
            width: 18
            height: parent.height - 16
            radius: 8
            color: "#de8b4e"
        }

    }

}
