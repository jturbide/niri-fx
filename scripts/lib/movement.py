"""Shared synthetic fixtures and pinned-build checks for native movement demos."""

import hashlib
import importlib.util
import json
from pathlib import Path

from .native_selection import explicit_manifest
from .nested import ROOT, wait_for

PALETTE = {"Notes": "#b7e8db", "Library": "#d6c5ef"}


def experiment(*, pointer_wobble=False):
    name = "niri-pointer-wobble-build.json" if pointer_wobble else "niri-movement-build.json"
    selected = explicit_manifest("pointer" if pointer_wobble else "movement", repository=ROOT)
    manifest = selected[1] if selected else json.loads((ROOT / "artifacts" / name).read_text())
    binary = selected[0] if selected else Path(manifest["binary"])
    inputs = [
        (binary, manifest["binary_sha256"]),
        (ROOT / "experimental/niri-movement.patch", manifest["patch_sha256"]),
    ]
    if pointer_wobble:
        inputs.append(
            (ROOT / "experimental/niri-pointer-wobble.patch", manifest["pointer_patch_sha256"])
        )
    for path, expected in inputs:
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            option = " --pointer-wobble" if pointer_wobble else ""
            raise RuntimeError(
                f"Experiment changed; run scripts/build-niri-movement.py{option} first"
            )
    spec = importlib.util.spec_from_file_location("nested_demo", ROOT / "scripts/nested-demo.py")
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    return binary, manifest, demo.config


def launch_cards(session, *, pointer_wobble=False):
    fixture = "pointer-card.qml" if pointer_wobble else "movement.qml"
    for label, color in PALETTE.items():
        session.launch(
            ["qs", "-p", str(ROOT / "scripts/fixtures" / fixture)],
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
