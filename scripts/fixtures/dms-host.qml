// Test host for the unmodified DMS launcher and PluginService, on a private bus.
import QtQuick
import Quickshell
import Quickshell.Io
import qs.Common
import qs.Services
import qs.DankCommon.Common as DC
import qs.Modals.DankLauncherV2

ShellRoot {
    id: root
    property var adapter: null
    Component.onCompleted: {
        DC.Style.theme = Theme;
        DC.Style.settings = SettingsData;
        DC.I18n.backend = I18n;
        DC.Paths.backend = Paths;
        DC.Log.backend = Log;
        DC.Host.session = SessionService;
        DC.Host.cache = CacheData;
    }
    DankLauncherV2Modal { id: launcher }
    Timer {
        interval: 100; running: true; repeat: true
        onTriggered: {
            if (!root.adapter && PluginService.availablePlugins.niriFX) {
                PluginService.loadPlugin("niriFX");
                root.adapter = PluginService.ensureLauncherInstance("niriFX");
            }
        }
    }
    IpcHandler {
        target: "record"
        // Avoid `show`: that name collides with a qs ipc subcommand.
        function present(query: string): void { launcher.showWithQuery(query); }
        function info(): string {
            return JSON.stringify({
                count: root.adapter ? Object.keys(root.adapter.presets).length : 0,
                status: root.adapter?.status || "waiting",
                busy: root.adapter?.busy || false,
                open: launcher.spotlightOpen,
                selected: launcher.spotlightContent?.controller?.selectedItem?.name || ""
            });
        }
    }
}
