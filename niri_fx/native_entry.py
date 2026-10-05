"""Stage a per-user login entry without writing display-manager directories."""

import json
import sys
from pathlib import Path

from .native_session import MAX_METADATA_BYTES, _path, _read, inspect_bundle, load_selection
from .setup import change


def _exec_argument(value):
    # Desktop Entry Exec has its own quoting layer; it is not a shell command.
    # The general string parser consumes backslashes before Exec tokenization.
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Login entry paths cannot contain control characters")
    value = value.replace("%", "%%")
    for old, new in (("\\", "\\\\"), ('"', '\\"'), ("`", "\\`"), ("$", "\\$")):
        value = value.replace(old, new)
    return '"' + value.replace("\\", "\\\\") + '"'


def entry_files(root, name="NiriFX"):
    """Review launcher bytes without requiring a bundle to exist on disk yet."""
    if (
        not isinstance(name, str)
        or not name.strip()
        or len(name) > 80
        or any(ord(char) < 32 or ord(char) == 127 for char in name)
    ):
        raise ValueError("Session name must contain 1 to 80 characters without control characters")
    root = _path(root)
    directory = _path(root / "session")
    launcher = _path(directory / "launch.py")
    entry = _path(directory / "niri-fx.desktop")
    python = str(Path(sys.executable).absolute())
    package = str(Path(__file__).resolve().parent.parent)
    script = (
        '"""NiriFX generated per-user login launcher."""\n'
        "import sys\n"
        f"sys.path.insert(0, {package!r})\n"
        "from niri_fx.native_login import main\n"
        f"raise SystemExit(main(['--root', {str(root)!r}, 'launch']))\n"
    ).encode()
    escaped_name = name.replace("\\", "\\\\")
    desktop = (
        "[Desktop Entry]\n"
        f"Name={escaped_name}\n"
        "Comment=Niri with configurable NiriFX window effects\n"
        f"Exec={_exec_argument(python)} {_exec_argument(str(launcher))}\n"
        "Type=Application\nDesktopNames=niri\n"
    ).encode()
    changes = []
    for path, data in ((launcher, script), (entry, desktop)):
        if path.exists():
            if _read(path, MAX_METADATA_BYTES, mode=0o600) != data:
                raise ValueError(f"Existing login entry differs; preserving it for review: {path}")
        changes.append(change(path, data))
    observed = list(changes)
    for item in observed:
        item["regular_only"] = True
        if item["before"] is not None:
            item["expected_mode"] = item["mode"]
    return {
        "target": "native-session-entry",
        "selection": {"entry": str(entry), "launcher": str(launcher), "name": name},
        "activation": "Administrator registration, then next login",
        "notes": [
            "Stages a per-user launcher and desktop entry; no system session directory is changed.",
            "Retain this Python installation and NiriFX package path for the launcher to work.",
            "An administrator can register the reviewed desktop entry in the display manager's session directory.",
            "This entry belongs to this user; it is not a multi-user compositor package.",
        ],
        "changes": [item for item in changes if item["before"] != item["after"]],
        "observed": observed,
        "validation_config": None,
        "validation_binary": None,
    }


def entry_plan(root, name="NiriFX"):
    root = _path(root)
    selector = root / "selection.json"
    selected_bytes = _read(selector, MAX_METADATA_BYTES, mode=0o600)
    selected = load_selection(root)
    if json.loads(selected_bytes) != selected:
        raise ValueError("Native selection changed while preparing the login entry")
    if not selected.get("selected"):
        raise ValueError("Select a staged native bundle before preparing its login entry")
    bundle = inspect_bundle(root, selected["selected"])
    plan = entry_files(root, name)
    observed = change(selector, selected_bytes, expected_before=selected_bytes)
    observed["regular_only"] = True
    observed["expected_mode"] = 0o600
    plan["observed"] = [observed, *bundle["observed"], *plan["observed"]]
    return plan
