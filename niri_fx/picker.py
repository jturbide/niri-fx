"""Launch optional desktop pickers; all configuration writes remain in setup."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def qml_directory():
    return Path(__file__).with_name("qml")


def gtk_directory():
    return Path(__file__).with_name("gtk")


def picker_checks():
    """Probe optional interfaces without opening windows or changing settings.

    An absent desktop toolkit is information, not an unhealthy core install:
    the terminal workflow and shader generator only require Python and Niri.
    """
    checks = []
    for name, binary, flags, missing in (
        (
            "quickshell-picker",
            "qs",
            ["--version"],
            "Install Quickshell only to use the optional QML picker.",
        ),
        (
            "gtk-picker",
            "gjs",
            [
                "-c",
                "imports.gi.versions.Gtk='4.0'; const Gtk=imports.gi.Gtk; print([Gtk.get_major_version(),Gtk.get_minor_version(),Gtk.get_micro_version()].join('.'));",
            ],
            "Install GJS and GTK 4.10+ with introspection data only to use the optional GTK picker.",
        ),
    ):
        available, detail = False, missing
        executable = shutil.which(binary)
        if executable:
            try:
                result = subprocess.run(
                    [executable, *flags], text=True, capture_output=True, timeout=5
                )
                if result.returncode:
                    detail = f"{binary} could not load this interface. {missing}"
                elif binary == "gjs":
                    version = tuple(int(part) for part in result.stdout.strip().split("."))
                    available = len(version) == 3 and version >= (4, 10, 0)
                    detail = f"GTK {result.stdout.strip()}; " + (
                        "niri-fx picker --toolkit gtk" if available else "GTK 4.10+ is required."
                    )
                else:
                    available = True
                    detail = f"{(result.stdout or result.stderr).strip()}; niri-fx picker"
            except (OSError, ValueError, subprocess.SubprocessError):
                detail = f"Could not query {binary}. {missing}"
        checks.append({"check": name, "ok": None, "available": available, "detail": detail})
    return checks


def launch_picker(arguments):
    from .setup import default_state

    gtk = arguments.toolkit == "gtk"
    executable = shutil.which("gjs" if gtk else "qs")
    if not executable:
        requirement = "GJS (gjs) and GTK 4.10+" if gtk else "Quickshell (qs)"
        raise ValueError(f"This picker requires {requirement}. Studio and standalone setup do not.")
    state = arguments.state or default_state().parent / ("gtk" if gtk else "quickshell")
    environment = os.environ | {
        "NIRIFX_COMMAND": json.dumps([sys.executable, "-m", "niri_fx"]),
        "NIRIFX_CONFIG": str(arguments.config.expanduser().absolute()),
        "NIRIFX_STATE": str(state.expanduser().absolute()),
        "NIRIFX_CUSTOM": str(arguments.custom.expanduser().absolute()) if arguments.custom else "",
    }
    # The same module invocation works from source and an installed wheel. A
    # command array also preserves spaces/metacharacters in interpreter paths.
    subprocess.run(
        [executable, "-m", str(gtk_directory() / "app.mjs")]
        if gtk
        else [executable, "--path", str(qml_directory() / "shell.qml")],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        check=True,
    )
