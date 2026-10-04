#!/usr/bin/env python3
"""Review/install the optional compact iRiS entry with snapshots and exact restore.

This source-level prototype is deliberately separate from preset registration.
The installed gallery is patched only when its known insertion points match;
unrelated iNiR files and all Niri settings remain outside this plan.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from niri_fx.integration import default_inir_root
from niri_fx.setup import apply_plan, change, default_state, restore, summarize


def plan(source):
    folder = Path(source) / "modules/iris/settings"
    gallery = folder / "IrisNiriMotionGallery.qml"
    before = gallery.read_bytes()
    text = before.decode()
    marker = "// NiriFX compact entry"
    if marker not in text:
        old = "readonly property var presets: NiriAnimationPresets.presets"
        insertion = "    GridLayout {"
        if text.count(old) != 1 or text.count(insertion) != 1:
            raise ValueError("This iRiS gallery version needs a reviewed integration update")
        text = text.replace(
            old, old + '.filter(p => p.generator !== "niri-fx" || !nirifx.available)'
        )
        text = text.replace(
            insertion,
            "    // NiriFX compact entry\n    IrisNiriFXSection { id: nirifx; Layout.fillWidth: true }\n\n"
            + insertion,
        )
    module = folder / "qmldir"
    module_before = module.read_bytes()
    declaration = b"IrisNiriFXSection 1.0 IrisNiriFXSection.qml\n"
    module_after = (
        module_before
        if declaration in module_before
        else module_before.rstrip() + b"\n" + declaration
    )
    observed = [change(gallery, text.encode(), before), change(module, module_after, module_before)]
    for name, file in (
        ("IrisNiriFXSection.qml", ROOT / "integrations/iris/IrisNiriFXSection.qml"),
        ("niri-fx.svg", ROOT / "niri_fx/assets/niri-fx.svg"),
    ):
        target = folder / name
        if target.exists() and marker not in before.decode():
            raise ValueError(
                f"Integration file already exists; review it before installing: {name}"
            )
        observed.append(change(target, file.read_bytes()))
    return {
        "target": "iris-ui",
        "selection": "Compact NiriFX entry",
        "notes": [
            "Adds Choose effects, Customize and Restore previous to the iRiS motion gallery.",
            "Reopen settings after installation. Niri configuration is not changed.",
        ],
        "activation": "iRiS settings UI",
        "validation_config": None,
        "changes": [item for item in observed if item["before"] != item["after"]],
        "observed": observed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=default_inir_root())
    parser.add_argument("--state", type=Path, default=default_state().parent / "iris-integration")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    import json

    try:
        result = (
            restore(args.state, apply=args.apply)
            if args.restore
            else (
                apply_plan(plan(args.source), args.state)
                if args.apply
                else summarize(plan(args.source))
            )
        )
        print(json.dumps(result, indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
