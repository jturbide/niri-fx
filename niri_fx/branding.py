"""Application identity and desktop metadata shared by launchers and adapters."""

import sys
from pathlib import Path

APP_ID = "niri-fx"
APP_NAME = "NiriFX"
KEYWORDS = (
    "Niri",
    "Wayland",
    "animations",
    "shaders",
    "fragments",
    "pixels",
    "particles",
    "slices",
    "wobble",
    "iNiR",
    "iRiS",
    "Quickshell",
    "Dank",
    "DankMaterialShell",
    "DMS",
    "Noctalia",
)


def desktop_entry(movement_demo=False):
    """Build a desktop entry for the current installation or source checkout."""
    root = Path(__file__).resolve().parents[1]
    icon = Path(__file__).with_name("assets") / "niri-fx.svg"
    if any(c in str(root) + sys.executable for c in "\n\r"):
        raise ValueError("Launcher paths cannot contain newlines")

    def quote(value):
        return (
            '"'
            + str(value)
            .replace("\\", "\\\\")
            .replace('"', '\\"')
            .replace("`", "\\`")
            .replace("$", "\\$")
            .replace("%", "%%")
            + '"'
        )

    label = "Movement Demo" if movement_demo else "Studio"
    command = "scripts/nested-demo.py" if movement_demo else "-m niri_fx studio"
    description = (
        "Try experimental NiriFX movement in an isolated compositor"
        if movement_demo
        else "Tune fragments, slices and springy window animations for niri"
    )
    working = str(root).replace("\\", "\\\\")
    icon_path = str(icon).replace("\\", "\\\\")
    window_class = "" if movement_demo else f"StartupWMClass={APP_ID}-studio\n"
    return (
        f"[Desktop Entry]\nType=Application\nName={APP_NAME} {label}\nComment={description}\n"
        f"Exec={quote(sys.executable)} {command}\nPath={working}\nIcon={icon_path}\n"
        "Terminal=false\nCategories=Settings;DesktopSettings;\n"
        f"Keywords={';'.join(KEYWORDS)};\n{window_class}StartupNotify=false\n"
    ).encode()
