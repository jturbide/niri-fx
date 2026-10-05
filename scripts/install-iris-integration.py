#!/usr/bin/env python3
"""Remove the retired iRiS source patch, or restore its historical snapshot.

NiriFX no longer installs code into an iNiR checkout. The supported app and
external preset registry work without changing the shell's tracked files.
Removal recognizes only the original patch and fingerprints its two assets;
unrelated upstream and local edits survive in a new, reversible transaction.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from niri_fx.integration import default_inir_root
from niri_fx.setup import apply_plan, change, default_state, restore, summarize

PRESETS = b"    readonly property var presets: NiriAnimationPresets.presets"
FILTER = b'.filter(p => p.generator !== "niri-fx" || !nirifx.available)'
BLOCK = (
    b"    // NiriFX compact entry\n    IrisNiriFXSection { id: nirifx; Layout.fillWidth: true }\n\n"
)
DECLARATION = b"IrisNiriFXSection 1.0 IrisNiriFXSection.qml\n"
ASSETS = {
    "IrisNiriFXSection.qml": ROOT / "integrations/iris/IrisNiriFXSection.qml",
    "niri-fx.svg": ROOT / "niri_fx/assets/niri-fx.svg",
}


def removal_plan(source):
    root = Path(source).expanduser().resolve()
    folder = root / "modules/iris/settings"
    # Deletion must not follow a borrowed file or module tree into another owner.
    for path in (root / "modules", root / "modules/iris", folder):
        if path.is_symlink():
            raise ValueError(f"Refusing a linked iRiS module directory: {path}")
    paths = [folder / name for name in ("IrisNiriMotionGallery.qml", "qmldir", *ASSETS)]
    if any(path.is_symlink() for path in paths):
        raise ValueError("Refusing linked iRiS integration files; review their owners first")
    gallery, module, *assets = paths
    before = gallery.read_bytes()
    module_before = module.read_bytes()
    present = [path.exists() for path in assets]
    signals = (
        b"NiriFX compact entry" in before
        or b"IrisNiriFXSection" in before
        or b"nirifx" in before
        or b"IrisNiriFXSection" in module_before
        or any(present)
    )
    after, module_after = before, module_before
    if signals:
        if (
            before.count(PRESETS + FILTER + b"\n") != 1
            or before.count(BLOCK) != 1
            or module_before.splitlines(keepends=True).count(DECLARATION) != 1
            or not all(present)
        ):
            raise ValueError("Partial or unfamiliar iRiS source patch; review it before removal")
        after = before.replace(PRESETS + FILTER + b"\n", PRESETS + b"\n", 1).replace(BLOCK, b"", 1)
        module_after = module_before.replace(DECLARATION, b"", 1)
        if any(
            token in after for token in (b"NiriFX compact entry", b"IrisNiriFXSection", b"nirifx")
        ):
            raise ValueError("Ambiguous iRiS gallery references; review them before removal")
        if b"IrisNiriFXSection" in module_after:
            raise ValueError("Ambiguous iRiS module registration; review it before removal")
        for asset in assets:
            if asset.read_bytes() != ASSETS[asset.name].read_bytes():
                raise ValueError(
                    f"Customized integration asset; leaving it untouched: {asset.name}"
                )
    observed = [
        change(gallery, after, before),
        change(module, module_after, module_before),
        *(
            change(asset, None, ASSETS[asset.name].read_bytes() if signals else None)
            for asset in assets
        ),
    ]
    return {
        "target": "iris-ui-removal",
        "selection": "Remove the legacy NiriFX iRiS source patch",
        "notes": [
            "Removes only the recognized NiriFX gallery patch and unchanged component/icon.",
            "Preserves other shell edits, registered presets and active Niri settings.",
            "Launch niri-fx studio --target inir --active for the shared app.",
            "Reopen settings or use the shell's normal restart to load the updated UI.",
        ],
        "activation": "iRiS source patch removal; no shell restart",
        "validation_config": None,
        "changes": [item for item in observed if item["before"] != item["after"]],
        "observed": observed,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=default_inir_root())
    parser.add_argument(
        "--state", type=Path, help="Override the selected operation's snapshot folder"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Apply the reviewed removal or restore"
    )
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument(
        "--remove", action="store_true", help="Review removal of the legacy patch"
    )
    operation.add_argument(
        "--restore",
        action="store_true",
        help="Restore an original installer snapshot, if unchanged",
    )
    args = parser.parse_args()
    if not (args.remove or args.restore):
        parser.error(
            "Source installation is retired. Use niri-fx studio --target inir --active. "
            "To review removal of an existing patch, pass --remove."
        )
    state = args.state or default_state().parent / (
        "iris-integration" if args.restore else "iris-integration-removal"
    )
    import json

    try:
        if args.restore:
            result = restore(state, apply=args.apply)
        else:
            plan = removal_plan(args.source)
            result = apply_plan(plan, state) if args.apply else summarize(plan)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
