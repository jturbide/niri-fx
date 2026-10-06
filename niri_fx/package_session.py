#!/usr/bin/python3
"""Package-owned login dispatcher; adoption is always an explicit user action.

Installed as /usr/bin/niri-fx-session. Keep this standard-library-only and avoid
importing the mutable system installation before selecting the retained tools.
"""

import hashlib
import json
import os
import stat
import sys
from pathlib import Path

DESKTOP_ENTRY = (
    "[Desktop Entry]\nName=NiriFX (package)\n"
    "Comment=Niri with configurable NiriFX window effects\n"
    "Exec=/usr/bin/niri-fx-session\nType=Application\nDesktopNames=niri\n"
).encode()


def default_root():
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    if not data.is_absolute():
        raise ValueError("XDG_DATA_HOME must be absolute for the packaged session")
    return data / "niri-fx/native"


def _read_owned(path):
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("Packaged session storage must not contain symlinks")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > 4 * 1024 * 1024
        ):
            raise ValueError("Packaged session metadata must be private and user-owned")
        data = stream.read(4 * 1024 * 1024 + 1)
        if len(data) > 4 * 1024 * 1024:
            raise ValueError("Packaged session metadata exceeds its size limit")
        return data


def main(arguments=None):
    if list(sys.argv[1:] if arguments is None else arguments):
        raise ValueError("The packaged login dispatcher does not accept arguments")
    directory = default_root() / "tools"
    selection = json.loads(_read_owned(directory / "selection.json"))
    if (
        not isinstance(selection, dict)
        or selection.get("schema") != 1
        or selection.get("phase") != "active"
    ):
        raise ValueError("Package adoption is incomplete")
    launcher = directory / "launch.py"
    content = _read_owned(launcher)
    if hashlib.sha256(content).hexdigest() != selection.get("assets", {}).get("launch.py"):
        raise ValueError("Retained tools dispatcher changed")
    os.execv("/usr/bin/python3", ["/usr/bin/python3", "-I", "-B", str(launcher), "session"])


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(
            f"NiriFX package session: {error}. Use stock Niri to review native adopt or recovery.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
