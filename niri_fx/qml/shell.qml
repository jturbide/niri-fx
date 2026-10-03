// SPDX-License-Identifier: MIT
import QtQuick
import Quickshell

ShellRoot {
    id: root

    property bool closing: false

    Component.onCompleted: Quickshell.watchFiles = false

    NiriFXController {
        id: controller

        command: JSON.parse(Quickshell.env("NIRIFX_COMMAND") || '["niri-fx"]')
        configPath: Quickshell.env("NIRIFX_CONFIG") || (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/niri/config.kdl"
        statePath: Quickshell.env("NIRIFX_STATE") || (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state") + "/niri-fx/quickshell"
        startupFile: Quickshell.env("NIRIFX_CUSTOM") || ""
        onBusyChanged: {
            if (root.closing && !busy)
                Qt.quit();
        }
    }

    FloatingWindow {
        title: "NiriFX Picker"
        implicitWidth: 980
        implicitHeight: 780
        minimumSize: Qt.size(780, 600)
        color: "#11171c"

        NiriFXPicker {
            anchors.fill: parent
            controller: controller
        }
    }

    Connections {
        // A close request must not kill a writer between its backed-up writes.
        function onLastWindowClosed() {
            root.closing = true;
            if (!controller.busy)
                Qt.quit();
        }

        target: Quickshell
    }
}
