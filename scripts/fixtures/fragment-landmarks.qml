// SPDX-License-Identifier: MIT
// Independent cell landmarks measure world-space motion in an owned native test.
import QtQuick
import Quickshell

ShellRoot {
    FloatingWindow {
        id: window
        property int moveRequests: 0
        readonly property var landmarks: JSON.parse(Quickshell.env("NIRIFX_LANDMARKS") || "[]")
        title: "NiriFX fragment landmarks" + (moveRequests ? " / moves " + moveRequests : "")
        implicitWidth: 500
        implicitHeight: 500
        color: "#252525"

        // Match the selected 800-piece grid. A small symmetric color patch at
        // each source-cell center keeps its centroid meaningful under rotation.
        readonly property real tile: Math.max(4, Math.sqrt(width * height / 800))
        function cellCenter(value, extent) {
            const origin = (extent - Math.ceil(extent / tile) * tile) / 2;
            return origin + (Math.floor((value - origin) / tile) + 0.5) * tile;
        }

        Rectangle {
            x: 14; y: 14
            width: parent.width - 28; height: 62
            color: "#414141"
            Text {
                anchors.centerIn: parent
                text: "Hold, pull, pause, reverse"
                color: "#eeeeee"
                font.pixelSize: 17
            }
            MouseArea {
                anchors.fill: parent
                onPressed: {
                    const accepted = window.startSystemMove();
                    console.log("NIRIFX_MOVE_REQUEST " + accepted);
                    if (accepted) window.moveRequests++;
                }
            }
        }

        Text {
            x: 30; y: 120
            text: "World-space fragment tracking"
            color: "#b8b8b8"
            font.pixelSize: 20
        }

        Repeater {
            model: window.landmarks
            Rectangle {
                required property var modelData
                x: window.cellCenter(modelData.x, window.width) - width / 2
                y: window.cellCenter(modelData.y, window.height) - height / 2
                width: 7; height: 7
                color: modelData.color
            }
        }
    }
}
