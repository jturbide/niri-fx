"""Shared synthetic fixtures and pinned-build checks for native movement demos."""

import hashlib
import importlib.util
import json
from pathlib import Path

from .nested import ROOT, wait_for

PALETTE = {"Notes": "#b7e8db", "Library": "#d6c5ef"}


def experiment():
    manifest = json.loads((ROOT / "artifacts/niri-movement-build.json").read_text())
    binary = Path(manifest["binary"])
    for path, expected in (
        (binary, manifest["binary_sha256"]),
        (ROOT / "experimental/niri-movement.patch", manifest["patch_sha256"]),
    ):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError("Movement build changed; run scripts/build-niri-movement.py first")
    spec = importlib.util.spec_from_file_location("nested_demo", ROOT / "scripts/nested-demo.py")
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    return binary, manifest, demo.config


def launch_cards(session):
    for label, color in PALETTE.items():
        session.launch(
            ["qs", "-p", str(ROOT / "scripts/fixtures/movement.qml")],
            label,
            env=session.env | {"NIRIFX_LABEL": label, "NIRIFX_COLOR": color},
            private_bus=True,
        )
    return wait_for(
        lambda: session.windows() if len(session.windows()) == 2 else None, "two synthetic windows"
    )


def color_counts(path):
    from PIL import Image

    with Image.open(path) as image:
        colors = {
            color: count
            for count, color in image.convert("RGB").getcolors(image.width * image.height)
        }
    return {
        label: colors.get(tuple(bytes.fromhex(color[1:])), 0) for label, color in PALETTE.items()
    }
