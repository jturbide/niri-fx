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
