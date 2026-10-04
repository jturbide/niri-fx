// SPDX-License-Identifier: MIT
// Optional iRiS entry point. The shared NiriFX app owns browsing and editing;
// iNiR's watched animation file remains the source of active selection.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.services
import qs.modules.common
import qs.modules.iris.style
import qs.modules.iris.components

ColumnLayout {
    id: root
    objectName: "niriFXSection"
    property bool available: false
    property bool canRestore: false
    property string error: ""
    readonly property var active: NiriAnimationPresets.activePreset
    readonly property bool selected: active?.generator === "niri-fx"
    spacing: Math.round(8 * IrisStyle.density)

    RowLayout {
        Layout.fillWidth: true
        Image {
            source: Qt.resolvedUrl("niri-fx.svg")
            sourceSize: Qt.size(36, 36)
            Layout.preferredWidth: 36
            Layout.preferredHeight: 36
        }
        ColumnLayout {
            Layout.fillWidth: true
            IrisText {
                text: "NiriFX"
                color: IrisStyle.text
                font.pixelSize: IrisStyle.typeLabel
                font.weight: Font.DemiBold
            }
            IrisText {
                Layout.fillWidth: true
                text: root.selected ? root.active.name.replace(/^NiriFX · /, "") : Translation.tr("Choose a look or create your own combo")
                color: IrisStyle.subtext
                font.pixelSize: IrisStyle.typeFootnote
                wrapMode: Text.WordWrap
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        IrisButton {
            text: Translation.tr("Choose effects")
            enabled: root.available
            onClicked: Quickshell.execDetached(["niri-fx", "studio", "--target", "inir", "--active"])
        }
        IrisButton {
            text: Translation.tr("Customize")
            quiet: true
            enabled: root.available && root.selected
            onClicked: Quickshell.execDetached(["niri-fx", "studio", "--target", "inir", "--active", "--edit"])
        }
        IrisButton {
            text: Translation.tr("Restore previous")
            quiet: true
            enabled: root.available && root.canRestore && !restoreProcess.running
            onClicked: { root.error = ""; restoreProcess.running = true; }
        }
    }
    IrisText {
        Layout.fillWidth: true
        text: root.error || (!root.available ? Translation.tr("Install NiriFX to browse effects in its app.") : Translation.tr("Pick one style or mix opening, closing and optional resize effects."))
        color: root.error ? IrisStyle.danger : IrisStyle.muted
        font.pixelSize: IrisStyle.typeFootnote
        wrapMode: Text.WordWrap
    }
    function refreshStatus() {
        if (!statusProcess.running) statusProcess.running = true;
    }
    Connections {
        target: NiriAnimationPresets
        function onActivePresetChanged() { root.refreshStatus(); }
    }
    Process {
        id: statusProcess
        command: ["niri-fx", "studio", "--target", "inir", "--status"]
        running: true
        stdout: StdioCollector {
            onStreamFinished: {
                try { root.canRestore = JSON.parse(text).restore === true; }
                catch (_) { root.canRestore = false; }
            }
        }
        onExited: (code, status) => { root.available = code === 0; }
    }
    Process {
        id: restoreProcess
        command: ["niri-fx", "studio", "--target", "inir", "--restore"]
        stderr: StdioCollector { id: restoreError }
        onExited: (code, status) => {
            if (code !== 0) root.error = restoreError.text.trim() || Translation.tr("Could not restore the previous settings.");
            root.refreshStatus();
            NiriAnimationPresets.refresh();
        }
    }
}
