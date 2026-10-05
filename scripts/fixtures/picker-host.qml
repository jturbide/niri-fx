// Test-only IPC; the packaged picker exposes no remote mutation endpoint.
import QtQuick
import Quickshell
import Quickshell.Io
import "components"

ShellRoot {
    Component.onCompleted: Quickshell.watchFiles = false
    NiriFXController {
        id: controller
        command: JSON.parse(Quickshell.env("NIRIFX_COMMAND"))
        configPath: Quickshell.env("NIRIFX_CONFIG")
        statePath: Quickshell.env("NIRIFX_STATE")
    }
    FloatingWindow {
        title: "NiriFX Picker"
        implicitWidth: 1100
        implicitHeight: 820
        minimumSize: Qt.size(780, 600)
        NiriFXPicker {
            anchors.fill: parent
            controller: controller
        }
    }
    IpcHandler {
        target: "test"
        function action(name: string, value: string): void {
            if (name === "select")
                controller.select(value);
            else if (name === "query")
                controller.query = value;
            else if (name === "family")
                controller.family = value;
            else if (name === "load")
                controller.loadFile(value);
            else if (name === "loadUrl")
                controller.loadUrl(value);
            else if (name === "resize")
                controller.allowResize = value === "true";
            else if (name === "command")
                controller.command = JSON.parse(value).argv;
            else if (["review", "apply", "undo", "reload", "openStudio", "refreshUndo"].includes(name))
                controller[name]();
            else
                throw new Error("Unknown test action");
        }
        function info(): string {
            return JSON.stringify({
                command: controller.command,
                count: Object.keys(controller.presets).length,
                items: controller.items,
                selected: controller.selectedPreset,
                document: controller.selectedDocument,
                descriptions: {
                    open: controller.actionDescription(controller.actions.open, "open"),
                    close: controller.actionDescription(controller.actions.close, "close"),
                    resize: controller.actionDescription(controller.actions.resize, "resize"),
                    movement: controller.actionDescription(controller.actions.movement, "movement")
                },
                busy: controller.busy,
                status: controller.status,
                error: controller.error,
                review: controller.reviewPlan,
                canApply: controller.canApply,
                changesResize: controller.changesResize,
                allowResize: controller.allowResize,
                undo: controller.undoTransaction,
                undoStatus: controller.undoStatus
            });
        }
    }
}
