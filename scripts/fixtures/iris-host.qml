// Real iRiS style gallery and service in an isolated test window.
import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.services
import qs.modules.common
import qs.modules.iris.style
import qs.modules.iris.settings

ShellRoot {
    FloatingWindow {
        id: window
        title: "NiriFX / iRiS gallery acceptance"
        implicitWidth: 1060
        implicitHeight: 740
        color: IrisStyle.surface
        Text {
            x: 28; y: 20
            text: "NiriFX styles in iRiS"
            color: IrisStyle.text
            font.pixelSize: 24
        }
        ScrollView {
            id: scroll
            anchors.fill: parent
            anchors.margins: 28
            anchors.topMargin: 70
            IrisNiriMotionGallery { id: gallery; width: scroll.availableWidth }
        }
        IpcHandler {
            target: "record"
            function fxInfo(): string {
                function find(item) {
                    if (item.objectName === "niriFXSection") return item;
                    for (const child of item.children || []) { const found = find(child); if (found) return found; }
                    return null;
                }
                const entry = find(gallery);
                return JSON.stringify({available: entry?.available, selected: entry?.selected, restore: entry?.canRestore, active: entry?.active?.name});
            }
            function clickFX(label: string): bool {
                function find(item) {
                    if (item.text === label && typeof item.clicked === "function") return item;
                    for (const child of item.children || []) { const found = find(child); if (found) return found; }
                    return null;
                }
                const button = find(gallery);
                if (!button || !button.enabled) return false;
                button.clicked();
                return true;
            }
            function info(): string {
                return JSON.stringify({ready: NiriAnimationPresets.loaded,
                    active: NiriAnimationPresets.activeId, error: NiriAnimationPresets.error});
            }
            function locate(identifier: string): string {
                function find(item) {
                    if (item.modelData?.id === identifier) return item;
                    for (const child of item.children || []) { const found = find(child); if (found) return found; }
                    return null;
                }
                const tile = find(gallery);
                if (!tile) return "null";
                // Stay within the scrollable range. Overscrolling can rebound
                // between locating a card and delivering the pointer click.
                const maximum = Math.max(0, gallery.height - scroll.availableHeight);
                scroll.contentItem.contentY = Math.max(0, Math.min(tile.y - 40, maximum));
                const point = tile.mapToItem(window.contentItem, tile.width / 2, 35);
                return JSON.stringify({x: point.x, y: point.y});
            }
        }
    }
}
