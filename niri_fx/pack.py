"""Reversible KDL preset folders for Noctalia and other Niri preset pickers."""

import json
import re
from pathlib import Path

from .effects import PRESETS, render_kdl
from .setup import change
from .storage import digest, read_bytes


def plan_pack(output):
    root = Path(output).expanduser().absolute()
    manifest = root / ".nirifx-pack.json"
    original = read_bytes(manifest)
    previous = json.loads(original) if original is not None else {"schema": 1, "files": {}}
    if (
        not isinstance(previous, dict)
        or type(previous.get("schema")) is not int
        or previous.get("schema") != 1
        or not isinstance(previous.get("files"), dict)
    ):
        raise ValueError("Invalid NiriFX pack manifest; refusing to replace files")
    # Never follow a per-file symlink or trust a manifest path outside the pack.
    for name, checksum in previous["files"].items():
        if (
            not re.fullmatch(r"nirifx-[a-z0-9-]+\.kdl", name)
            or not isinstance(checksum, str)
            or not re.fullmatch(r"[0-9a-f]{64}", checksum)
        ):
            raise ValueError("Invalid NiriFX pack manifest entry")
        path = root / name
        if path.is_symlink() or digest(read_bytes(path)) != checksum:
            raise ValueError(
                f"Pack file changed since export; preserve/review it before updating: {path}"
            )
    if manifest.is_symlink():
        raise ValueError("Pack manifest cannot be a symlink")
    changes, files = [], {}
    for name, effect in PRESETS.items():
        filename = f"nirifx-{name}.kdl"
        path = root / filename
        before = read_bytes(path)
        if path.is_symlink() or (before is not None and filename not in previous["files"]):
            raise ValueError(f"Refusing to replace an unowned preset: {path}")
        content = render_kdl(effect).encode()
        files[filename] = digest(content)
        changes.append(change(path, content, before))
    # Preserve previously exported names if a future catalog removes a preset:
    # users may still include that filename from their shell's active selection.
    content = (
        json.dumps({"schema": 1, "files": previous["files"] | files}, indent=2) + "\n"
    ).encode()
    changes.append(change(manifest, content, original))
    return {
        "target": "preset-pack",
        "selection": list(PRESETS),
        "effect": None,
        "activation": "Choose a preset in your shell picker or include one KDL file",
        "notes": [
            "Exports open/close presets; resize remains off. No active Niri or shell configuration is edited.",
            "Configure Noctalia Niri Animations presets_dir/include_prefix to match this folder.",
            "Restore the printed snapshot to undo this export. Preserve the pack while a preset is active.",
        ],
        "changes": [c for c in changes if c["before"] != c["after"]],
        "validation_config": None,
    }
