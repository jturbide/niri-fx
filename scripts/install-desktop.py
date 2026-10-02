#!/usr/bin/env python3
"""Add an on-demand Studio launcher for this checkout, without starting it."""

import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
target = data / "applications/niri-fragments-studio.desktop"
python = sys.executable.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$")
working_directory = str(root).replace("\\", "\\\\").replace("\n", "\\n")
content = f"""[Desktop Entry]
Type=Application
Name=Niri Fragments Studio
Comment=Customize window gravity, particles, and rotation
Exec="{python}" -m niri_fragments studio
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
