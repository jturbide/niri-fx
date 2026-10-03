"""Launch the packaged Quickshell UI; all configuration writes remain in setup."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def qml_directory():
    return Path(__file__).with_name("qml")


def launch_picker(arguments):
    executable = shutil.which("qs")
    if not executable:
        raise ValueError("The picker requires Quickshell (qs). Studio and standalone setup do not.")
    environment = os.environ | {
        "NIRIFX_COMMAND": json.dumps([sys.executable, "-m", "niri_fx"]),
        "NIRIFX_CONFIG": str(arguments.config.expanduser().absolute()),
        "NIRIFX_STATE": str(arguments.state.expanduser().absolute()),
        "NIRIFX_CUSTOM": str(arguments.custom.expanduser().absolute()) if arguments.custom else "",
    }
    # The same module invocation works from source and an installed wheel. A
    # command array also preserves spaces/metacharacters in interpreter paths.
    subprocess.run(
        [executable, "--path", str(qml_directory() / "shell.qml")],
        cwd=Path(__file__).resolve().parents[1],
        env=environment,
        check=True,
    )
