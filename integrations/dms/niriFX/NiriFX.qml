// SPDX-License-Identifier: MIT
import QtQuick
import Quickshell
import Quickshell.Io

Item {
    id: root
    property var pluginService: null
    property string trigger: "fx"
    property string executable: "niri-fx"
    property string configPath: (Quickshell.env("XDG_CONFIG_HOME") || Quickshell.env("HOME") + "/.config") + "/niri/config.kdl"
    property string statePath: (Quickshell.env("XDG_STATE_HOME") || Quickshell.env("HOME") + "/.local/state") + "/niri-fx/dms"
    property var presets: ({})
    property string status: "Loading NiriFX styles…"
    readonly property bool busy: actionProcess.running
    signal itemsChanged()

    function reload() {
        if (!catalogProcess.running) catalogProcess.running = true;
    }
    function getItems(query) {
        const items = [
            {name: "Open NiriFX Studio", icon: "material:animation", comment: "Design independent opening and closing effects", action: "studio", categories: ["NiriFX"]},
            {name: "Undo last NiriFX change", icon: "material:undo", comment: "Restore the latest snapshot made by this plugin", action: "restore", categories: ["NiriFX"]},
            {name: "Refresh NiriFX styles", icon: "material:refresh", comment: status, action: "refresh", categories: ["NiriFX"]}
        ];
        for (const name of Object.keys(presets)) items.push({
            name: name.split("-").map(word => word[0].toUpperCase() + word.slice(1)).join(" "),
            icon: "material:animation", comment: "Apply " + presets[name].family + " · resize unchanged", action: "preset:" + name, categories: ["NiriFX"]
        });
        const text = (query || "").toLowerCase();
        return items.filter(item => (item.name + " " + item.comment).toLowerCase().includes(text));
    }
    function executeItem(item) {
        if (!item || typeof item.action !== "string" || busy) return;
        if (item.action === "studio") {
            Quickshell.execDetached([executable, "studio"]);
        } else if (item.action === "refresh") {
            reload();
        } else if (item.action === "restore") {
            actionProcess.command = [executable, "restore", "--state", statePath, "--apply"];
            actionProcess.running = true;
        } else if (item.action.startsWith("preset:")) {
            const name = item.action.slice(7);
            if (!Object.prototype.hasOwnProperty.call(presets, name)) return;
            actionProcess.command = [executable, "setup", "--target", "standalone", "--config", configPath, "--state", statePath, "--preset", name, "--no-launcher", "--apply"];
            actionProcess.running = true;
        }
    }
    Process {
        id: catalogProcess
        command: [root.executable, "list"]
        stdout: StdioCollector { id: catalogOutput }
        stderr: StdioCollector { id: catalogError }
        onExited: (code, exitStatus) => {
            try {
                if (code !== 0) throw new Error(catalogError.text || "niri-fx list failed");
                const data = JSON.parse(catalogOutput.text);
                if (!data || Array.isArray(data) || typeof data !== "object") throw new Error("Invalid catalog");
                root.presets = data;
                root.status = Object.keys(data).length + " styles available";
            } catch (error) { root.status = error.message; }
            root.itemsChanged();
        }
    }
    Process {
        id: actionProcess
        stdout: StdioCollector { id: actionOutput }
        stderr: StdioCollector { id: actionError }
        onExited: (code, exitStatus) => {
            root.status = code === 0 ? "NiriFX change applied; use Undo to restore the previous state" : (actionError.text || "NiriFX command failed");
            if (code !== 0) console.warn(root.status);
            root.itemsChanged();
        }
    }
    Component.onCompleted: reload()
}
