#!/usr/bin/env python3
"""Exercise the real QML adapter in offscreen Quickshell with temporary Niri files.

This tests the plugin contract, subprocesses and restore, not the DMS launcher UI.
"""

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    if not shutil.which("qs") or not shutil.which("niri"):
        raise SystemExit("Requires Quickshell (qs) and Niri")
    with tempfile.TemporaryDirectory(prefix="nirifx-dms-") as directory:
        root = Path(directory)
        config = root / "config.kdl"
        original = "layout { gaps 12; }\n"
        config.write_text(original)
        executable = root / "niri-fx"
        executable.write_text(
            f'#!/bin/sh\ncd {shlex.quote(str(ROOT))}\nexec {shlex.quote(sys.executable)} -m niri_fx "$@"\n'
        )
        executable.chmod(0o700)
        properties = {
            "executable": str(executable),
            "configPath": str(config),
            "statePath": str(root / "state"),
        }
        component = (ROOT / "integrations/dms/niriFX/NiriFX.qml").as_uri()
        (root / "shell.qml").write_text(
            """import QtQuick
import Quickshell
ShellRoot {
    property int phase: 0
    Loader { id: adapter; Component.onCompleted: setSource("""
            + json.dumps(component)
            + ", "
            + json.dumps(properties)
            + """) }
    Timer {
        interval: 100; running: true; repeat: true
        onTriggered: {
            if (!adapter.item) return;
            const item = adapter.item;
            if (phase === 0 && Object.keys(item.presets).length > 0) {
                if (!item.getItems("noise dissolve").some(entry => entry.action === "preset:noise-dissolve")) throw new Error("Catalog search failed");
                item.executeItem({action: "preset:../../bad"});
                if (item.busy) throw new Error("Unknown action was executed");
                item.executeItem({action: "preset:noise-dissolve"}); phase = 1;
            } else if (phase === 1 && !item.busy) {
                if (!item.status.startsWith("NiriFX change applied")) throw new Error(item.status);
                item.executeItem({action: "restore"}); phase = 2;
            } else if (phase === 2 && !item.busy) {
                if (!item.status.startsWith("NiriFX change applied")) throw new Error(item.status);
                console.log("NIRIFX_DMS_ADAPTER_PASS"); Qt.quit();
            }
        }
    }
}
"""
        )
        result = subprocess.run(
            ["qs", "--path", str(root / "shell.qml")],
            env={
                **os.environ,
                "QT_QPA_PLATFORM": "offscreen",
                "XDG_CONFIG_HOME": str(root / "config"),
                "XDG_STATE_HOME": str(root / "app-state"),
            },
            text=True,
            capture_output=True,
            timeout=30,
        )
        output = result.stdout + result.stderr
        if result.returncode or "NIRIFX_DMS_ADAPTER_PASS" not in output:
            raise SystemExit(output)
        assert config.read_text() == original, "Restore did not recover the exact config"
        assert not (root / "nirifx/animations.kdl").exists(), "Restore left the effect active"
        print(
            "PASS: real QML catalog/search, unknown-action rejection, CLI apply and exact restore in temporary config"
        )


if __name__ == "__main__":
    main()
