#!/usr/bin/env python3
import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(
    description="Exercise the adapter through an existing DMS QML release, without running your desktop shell."
)
parser.add_argument("--source", type=Path, required=True)
source = parser.parse_args().source.resolve()
if not (source / "Services/PluginService.qml").is_file():
    raise SystemExit("DMS QML root is missing Services/PluginService.qml")
scratch = tempfile.TemporaryDirectory(prefix="nirifx-dms-service-")
root = Path(scratch.name)
qml_root = root / "qml"
qml_root.mkdir()
for folder in source.iterdir():
    if folder.is_dir():
        (qml_root / folder.name).symlink_to(folder, target_is_directory=True)
for folder in ("config", "state", "data", "cache", "runtime", "bin"):
    (root / folder).mkdir(mode=0o700)
shutil.copytree(repo / "integrations/dms/niriFX", root / "config/DankMaterialShell/plugins/niriFX")
(root / "config/niri").mkdir()
(root / "config/niri/config.kdl").write_text("layout { gaps 12; }\n")
exe = root / "bin/niri-fx"
exe.write_text(
    f'#!/bin/sh\ncd {shlex.quote(str(repo))}\nexec {shlex.quote(sys.executable)} -m niri_fx "$@"\n'
)
exe.chmod(0o700)
qml = qml_root / "shell.qml"
qml.write_text("""import QtQuick
import Quickshell
import qs.Services
ShellRoot {
 property int phase: 0
 property var instance: null
 Timer { interval: 100; running: true; repeat: true
 onTriggered: {
  if (phase===0 && PluginService.availablePlugins.niriFX) {
    if (!PluginService.loadPlugin("niriFX")) throw new Error("Could not load plugin");
    instance=PluginService.ensureLauncherInstance("niriFX");phase=1;
  } else if (phase===1 && instance && Object.keys(instance.presets).length > 0) {
    if (!instance.getItems("iris bloom").some(item=>item.action==="preset:iris-bloom")) throw new Error("Search failed");
    instance.executeItem({action:"preset:iris-bloom"});phase=2;
  } else if (phase===2 && !instance.busy) {
    if (!instance.status.startsWith("NiriFX change applied")) throw new Error(instance.status);
    instance.executeItem({action:"restore"});phase=3;
  } else if (phase===3 && !instance.busy) {
    if (!instance.status.startsWith("NiriFX change applied")) throw new Error(instance.status);
    console.log("NIRIFX_DMS_SERVICE_PASS");Qt.quit();
  }
 }
 }
}
""")
env = {
    **os.environ,
    "XDG_CONFIG_HOME": str(root / "config"),
    "XDG_STATE_HOME": str(root / "state"),
    "XDG_DATA_HOME": str(root / "data"),
    "XDG_CACHE_HOME": str(root / "cache"),
    "XDG_RUNTIME_DIR": str(root / "runtime"),
    "QT_QPA_PLATFORM": "offscreen",
    "PATH": str(root / "bin") + ":" + os.environ["PATH"],
}
for key in ("NIRI_SOCKET", "WAYLAND_DISPLAY", "DISPLAY", "HYPRLAND_INSTANCE_SIGNATURE"):
    env.pop(key, None)
try:
    r = subprocess.run(
        ["dbus-run-session", "qs", "-p", str(qml)],
        env=env,
        timeout=40,
        text=True,
        capture_output=True,
    )
    if r.returncode or "NIRIFX_DMS_SERVICE_PASS" not in r.stdout + r.stderr:
        raise SystemExit(r.stdout + r.stderr)
    assert (root / "config/niri/config.kdl").read_text() == "layout { gaps 12; }\n"
    print(
        "PASS: DMS 1.6.2 real plugin discovery, launcher instantiation, search, apply and exact restore"
    )
except subprocess.TimeoutExpired as e:
    print((e.stdout or b"").decode() + (e.stderr or b"").decode())
    raise
finally:
    scratch.cleanup()
