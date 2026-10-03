#!/usr/bin/env python3
"""Add an on-demand Studio launcher for this checkout, without starting it."""

import argparse
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--movement-demo",
    action="store_true",
    help="Install a launcher for the separately built nested experiment",
)
args = parser.parse_args()
if args.movement_demo and not (root / "artifacts/niri-movement-build.json").exists():
    parser.error("Build the experiment first: python3 scripts/build-niri-movement.py")
data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
target = data / (
    "applications/niri-fragments-movement-demo.desktop"
    if args.movement_demo
    else "applications/niri-fragments-studio.desktop"
)
python = (
    sys.executable.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
)
working_directory = str(root).replace("\\", "\\\\").replace("\n", "\\n")
name = "NiriFX Movement Demo" if args.movement_demo else "NiriFX Studio"
comment = (
    "Try experimental particle swaps in a separate Niri window"
    if args.movement_demo
    else "Customize fragment, slice and elastic window animations"
)
command = "scripts/nested-demo.py" if args.movement_demo else "-m niri_fx studio"
content = f"""[Desktop Entry]
Type=Application
Name={name}
Comment={comment}
Exec="{python}" {command}
Path={working_directory}
Icon=preferences-desktop-effects
Terminal=false
Categories=Settings;DesktopSettings;
Keywords=Niri;iNiR;iRiS;animation;gravity;particles;
StartupNotify=false
"""
target.parent.mkdir(parents=True, exist_ok=True)
if target.exists():
    if target.read_text() != content:
        raise SystemExit(f"Existing launcher differs; refusing to replace {target}")
else:
    with target.open("x") as output:
        output.write(content)
print(target)
