"""Verify all inputs to the isolated continuous-fragment experiment."""

import hashlib
import json
from pathlib import Path

from niri_fx.effects import render_kdl
from niri_fx.fragment_motion import PRESETS, render_node
from niri_fx.profiles import Profile

from .native_selection import explicit_manifest
from .nested import ROOT, NestedSession
from .pointer_scene import BASE


class FragmentSession(NestedSession):
    """Keep full-feature experimental builds out of the host session manager."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.host["NIRI_DISABLE_SYSTEM_MANAGER_NOTIFY"] = "1"
        self.host.pop("NOTIFY_SOCKET", None)


def config(preset_name, *, movement_off=False, effect=None, settings=None):
    """Generate only an owned demo's configuration, never a desktop installation.

    Effect/settings overrides let lifecycle checks change native dynamics without
    also replacing the source grid. The normal preset path uses both together.
    """
    preset = PRESETS[preset_name]
    profile = Profile(
        open="off",
        close="off",
        resize="off",
        movement="off" if movement_off else (effect if effect is not None else preset.effect),
    )
    generated = render_kdl(profile, movement=True)
    if not movement_off:
        node = "    window-movement {\n"
        if generated.count(node) != 1:
            raise RuntimeError("Expected exactly one generated movement node")
        generated = generated.replace(
            node, node + render_node(settings if settings is not None else preset.settings), 1
        )
    return BASE + generated


def experiment():
    selected = explicit_manifest("fragment", repository=ROOT)
    manifest = (
        selected[1]
        if selected
        else json.loads((ROOT / "artifacts/niri-fragment-drag-build.json").read_text())
    )
    binary = selected[0] if selected else Path(manifest["binary"])
    inputs = [
        (binary, manifest["binary_sha256"]),
        (ROOT / "experimental/niri-movement.patch", manifest["patch_sha256"]),
        (ROOT / "experimental/niri-pointer-wobble.patch", manifest["pointer_patch_sha256"]),
        (ROOT / "experimental/niri-fragment-drag.patch", manifest["fragment_patch_sha256"]),
    ]
    for path, expected in inputs:
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise RuntimeError(
                "Experiment changed; run scripts/build-niri-movement.py --fragment-drag first"
            )
    return binary, manifest
