"""Dependency-free command line interface."""

import argparse
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from . import __version__
from .effects import (
    ELASTIC_ANCHORS,
    ELASTIC_AXES,
    ELASTIC_FIELDS,
    FAMILIES,
    FAMILY_FIELDS,
    GRAVITIES,
    MOTION_FIELDS,
    PRESETS,
    RELEASES,
    RESIZE_MODES,
    ROTATIONS,
    SLICE_DIRECTIONS,
    SLICE_ORDERS,
    describe_presets,
    effect_document,
    render_kdl,
)
from .integration import (
    custom_document,
    default_inir_root,
    default_registry,
    make_custom_preset,
    make_presets,
    read_shell_presets,
    update_registry,
)

EFFECT_FIELDS = (
    FAMILY_FIELDS
    + MOTION_FIELDS
    + ELASTIC_FIELDS
    + (
        "tile_size",
        "scatter",
        "open_ms",
        "close_ms",
        "gravity",
        "gravity_strength",
        "particles",
        "rotation",
        "spin",
        "swirl",
        "dispersion",
        "stagger",
        "resize",
        "resize_ms",
        "resize_strength",
        "release",
        "wave_span",
        "origin_x",
        "origin_y",
        "resize_mode",
        "fragment_shrink",
        "fragment_roundness",
    )
)


def effect_options(command):
    command.add_argument("--preset", choices=PRESETS, default="balanced")
    command.add_argument("--family", choices=FAMILIES, help="Effect family")
    command.add_argument("--slice-count", type=int, help="Number of strips (2–48)")
    command.add_argument(
        "--slice-angle", type=float, help="Strip angle: 0 horizontal, ±90 vertical"
    )
    command.add_argument(
        "--slice-distance", type=float, help="Strip travel in logical pixels (0–600)"
    )
    command.add_argument("--slice-stagger", type=float, help="First-to-last release delay (0–0.75)")
    command.add_argument(
        "--slice-rotation", type=float, help="Strip rotation during travel (-60–60 degrees)"
    )
    command.add_argument("--slice-direction", choices=SLICE_DIRECTIONS)
    command.add_argument(
        "--slice-order", choices=SLICE_ORDERS, help="Release sequence across the strips"
    )
    command.add_argument(
        "--slice-travel-variation", type=float, help="Random strip travel distance (0–1)"
    )
    command.add_argument("--slice-rotation-variation", type=float, help="Random strip spin (0–1)")
    command.add_argument("--slice-pivot", type=float, help="Strip hinge along its length (-1–1)")
    command.add_argument(
        "--slice-collapse", type=float, help="Strip width collapse during flight (0–1)"
    )
    command.add_argument(
        "--fragment-shrink", type=float, help="Extra fragment shrink during flight (0–1)"
    )
    command.add_argument(
        "--fragment-roundness", type=float, help="Square-to-rounded fragment corners (0–1)"
    )
    command.add_argument(
        "--size-variation", type=float, help="Unequal strip widths or fragment grid cells (0–1)"
    )
    command.add_argument("--direction-variation", type=float, help="Random heading spread (0–1)")
    command.add_argument(
        "--wave-strength", type=float, help="Rigid-piece wave amplitude (0–1); zero disables waves"
    )
    command.add_argument(
        "--wave-frequency", type=float, help="Wave cycles across the window (0.25–4)"
    )
    command.add_argument("--wave-speed", type=float, help="Wave cycles during the animation (0–4)")
    command.add_argument(
        "--elastic-strength", type=float, help="Whole-window wobble strength (0–1)"
    )
    command.add_argument("--elastic-frequency", type=float, help="Spring oscillations (1–5)")
    command.add_argument("--elastic-damping", type=float, help="Spring settling rate (0–8)")
    command.add_argument("--elastic-axis", choices=ELASTIC_AXES)
    command.add_argument("--elastic-twist", type=float, help="Spring rotation (-90–90 degrees)")
    command.add_argument("--elastic-stretch", type=float, help="Additional spring stretching (0–1)")
    command.add_argument(
        "--elastic-ripple", type=float, help="Spatial bend frequency multiplier (0.5–4)"
    )
    command.add_argument(
        "--elastic-anchor",
        choices=ELASTIC_ANCHORS,
        help="Rotation/stretch/collapse origin; not a pinned edge",
    )
    density = command.add_mutually_exclusive_group()
    density.add_argument(
        "--tile-size",
        type=float,
        help="Square size in logical pixels (8–128); disables target count",
    )
    density.add_argument(
        "--particles",
        type=int,
        help="Approximate particle count (16–4096), or 0 for tile-size mode",
    )
    command.add_argument("--scatter", type=float, help="Radial scatter in logical pixels (0–240)")
    command.add_argument("--gravity", choices=GRAVITIES)
    command.add_argument("--gravity-strength", type=float, help="Gravity multiplier (0–3)")
    command.add_argument(
        "--rotation",
        choices=ROTATIONS,
        help="No spin, random spin, or face the direction of travel",
    )
    command.add_argument(
        "--spin", type=float, help="Random spin range or alignment limit in degrees (0–720)"
    )
    command.add_argument(
        "--swirl", type=float, help="Orbit around the window center in degrees (-360–360)"
    )
    command.add_argument(
        "--dispersion", type=float, help="Independent fragment path variation (0–1)"
    )
    command.add_argument("--stagger", type=float, help="Variation in fragment release time (0–0.4)")
    command.add_argument("--open-ms", type=int)
    command.add_argument("--close-ms", type=int)
    command.add_argument(
        "--resize",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Include the stock Niri resize effect",
    )
    command.add_argument("--resize-ms", type=int)
    command.add_argument("--resize-strength", type=float, help="Bounded resize fragmentation (0–1)")
    command.add_argument(
        "--release", choices=RELEASES, help="Spatial release sequence across the window"
    )
    command.add_argument(
        "--wave-span", type=float, help="Fraction of time separating first/last wave (0–0.7)"
    )
    command.add_argument(
        "--origin-x", type=float, help="Burst/orbit center from left (0) to right (1)"
    )
    command.add_argument(
        "--origin-y", type=float, help="Burst/orbit center from top (0) to bottom (1)"
    )
    command.add_argument(
        "--resize-mode",
        choices=RESIZE_MODES,
        help="Full breakup, edge rebuild or soft reflow; does not enable resize",
    )


def selected_effect(arguments):
    if getattr(arguments, "custom", None):
        if arguments.preset != "balanced" or any(
            getattr(arguments, k, None) is not None for k in EFFECT_FIELDS
        ):
            raise ValueError(
                "--custom uses the file's parameters; do not combine it with effect overrides"
            )
        return custom_document(read_custom(arguments.custom))[2]
    overrides = {
        k: getattr(arguments, k) for k in EFFECT_FIELDS if getattr(arguments, k, None) is not None
    }
    if overrides.get("tile_size") is not None:
        overrides["particles"] = 0
    effect = replace(PRESETS[arguments.preset], **overrides)
    common = {"family", "open_ms", "close_ms", "resize"}
    allowed = {
        "fragments": set(EFFECT_FIELDS) - set(FAMILY_FIELDS) - set(ELASTIC_FIELDS),
        "slices": set(FAMILY_FIELDS) | set(MOTION_FIELDS),
        "elastic": set(ELASTIC_FIELDS),
    }
    inactive = set(EFFECT_FIELDS) - allowed[effect.family] - common
    if inactive.intersection(overrides):
        raise ValueError(
            f"Options do not apply to the {effect.family} family: "
            + ", ".join(sorted(inactive.intersection(overrides)))
        )
    return effect


def read_custom(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(16385)
    if len(raw) > 16384:
        raise ValueError("Custom preset must be at most 16 KiB")
    data = json.loads(raw)
    custom_document(data)
    return data


def parser():
    root = argparse.ArgumentParser(
        description="NiriFX window effects and native iNiR/iRiS presets."
    )
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="Print built-in effect parameters as JSON")
    commands.add_parser("families", help="Print supported effect families and capabilities as JSON")
    for name, help_text in (
        ("render", "Print a standalone Niri KDL animation override"),
        ("preview", "Write a self-contained interactive editor; no desktop changes"),
    ):
        command = commands.add_parser(name, help=help_text)
        effect_options(command)
        command.add_argument("--custom", type=Path, help="Use an exported preset JSON document")
        if name == "preview":
            command.add_argument("--output", type=Path, required=True)
    register = commands.add_parser(
        "register", help="Add built-in or custom presets without activating them"
    )
    effect_options(register)
    custom = register.add_mutually_exclusive_group()
    custom.add_argument("--name", help="Save these parameters as a named custom preset")
    custom.add_argument(
        "--custom", type=Path, help="Import a preset JSON file exported from the editor"
    )
    unregister = commands.add_parser(
        "unregister", help="Remove NiriFX-owned entries from the user preset registry"
    )
    studio = commands.add_parser("studio", help="Open the local editor with Save to iRiS support")
    effect_options(studio)
    studio.add_argument("--custom", type=Path)
    studio.add_argument("--no-browser", action="store_true")
    studio.add_argument(
        "--browser", action="store_true", help="Open a browser tab instead of an app-style window"
    )
    studio.add_argument(
        "--port", type=int, default=0, help="Loopback port; default chooses an available port"
    )
    from .setup import default_config, default_state

    pack = commands.add_parser(
        "export-pack", help="Preview/export a KDL preset folder for Noctalia or other Niri pickers"
    )
    pack.add_argument("--output", type=Path, required=True)
    pack.add_argument("--state", type=Path, default=default_state())
    pack.add_argument(
        "--apply", action="store_true", help="Write the reviewed pack with restore snapshots"
    )
    setup = commands.add_parser(
        "setup", help="Review a setup plan; --apply writes backed-up changes"
    )
    effect_options(setup)
    setup.add_argument("--target", choices=("auto", "inir", "standalone"), default="auto")
    setup.add_argument("--custom", type=Path)
    setup.add_argument("--name", help="Name customized settings for iNiR")
    setup.add_argument("--launcher", action=argparse.BooleanOptionalAction, default=True)
    diagnose = commands.add_parser(
        "doctor", help="Check Niri, configuration and Studio prerequisites"
    )
    restore = commands.add_parser("restore", help="Review or restore the latest setup snapshot")
    restore.add_argument("--transaction", help="Restore a specific setup transaction")
    for command in (setup, restore):
        mode = command.add_mutually_exclusive_group()
        mode.add_argument("--apply", action="store_true", help="Write the reviewed changes")
        mode.add_argument(
            "--dry-run", action="store_true", help="Only review changes (the default)"
        )
        command.add_argument("--state", type=Path, default=default_state())
    for command in (setup, diagnose):
        command.add_argument("--config", type=Path, default=default_config())
    for command in (register, studio, setup, diagnose):
        command.add_argument("--inir-root", type=Path, default=default_inir_root())
    for command in (register, studio, setup):
        command.add_argument(
            "--base",
            default="auto",
            help="Base movement preset; defaults to the active recognized preset",
        )
    for command in (register, unregister, studio, setup):
        command.add_argument("--registry", type=Path, default=default_registry())
    for command in (register, unregister):
        command.add_argument(
            "--dry-run", action="store_true", help="Print the proposed registry; write nothing"
        )
    return root


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "families":
            print(json.dumps(FAMILIES, indent=2))
        elif arguments.command == "list":
            print(json.dumps(describe_presets(), indent=2))
        elif arguments.command == "doctor":
            from .setup import doctor

            report = doctor(arguments)
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 0 if report["healthy"] else 1
        elif arguments.command == "export-pack":
            from .pack import plan_pack
            from .setup import apply_plan, summarize

            plan = plan_pack(arguments.output)
            result = (
                apply_plan(plan, arguments.state)
                if arguments.apply
                else {**summarize(plan), "dry_run": True}
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif arguments.command == "restore":
            from .setup import restore

            print(
                json.dumps(
                    restore(arguments.state, arguments.transaction, arguments.apply), indent=2
                )
            )
        elif arguments.command == "setup":
            from .setup import apply_plan, plan_setup, summarize

            if arguments.custom and arguments.name:
                raise ValueError("--custom already supplies a name; omit --name")
            plan = plan_setup(
                arguments,
                selected_effect(arguments),
                read_custom(arguments.custom) if arguments.custom else None,
            )
            if (
                plan["target"] == "inir"
                and not (arguments.custom or arguments.name)
                and (
                    arguments.preset != "balanced"
                    or any(getattr(arguments, k) is not None for k in EFFECT_FIELDS)
                )
            ):
                raise ValueError(
                    "Use --name to save customized iNiR settings; built-in registration leaves resize off"
                )
            result = (
                apply_plan(plan, arguments.state)
                if arguments.apply
                else {**summarize(plan), "dry_run": True}
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif arguments.command in ("render", "preview", "studio"):
            effect = selected_effect(arguments)
            name = read_custom(arguments.custom)["name"] if arguments.custom else arguments.preset
            if arguments.command == "render":
                print(render_kdl(effect), end="")
            elif arguments.command == "preview":
                from .studio import preview_document

                with arguments.output.open("x") as output:
                    output.write(preview_document(effect, name))
                print(arguments.output.resolve())
            else:
                from .studio import serve

                arguments.custom_name = name
                serve(arguments, effect)
        else:
            generated = []
            if arguments.command == "register":
                registry = read_shell_presets(arguments.inir_root)
                if arguments.custom:
                    if arguments.preset != "balanced" or any(
                        getattr(arguments, k) is not None for k in EFFECT_FIELDS
                    ):
                        raise ValueError(
                            "--custom uses the file's parameters; do not combine it with effect overrides"
                        )
                    document = read_custom(arguments.custom)
                    generated = [make_custom_preset(registry, document, arguments.base)]
                elif arguments.name:
                    document = effect_document(arguments.name, selected_effect(arguments))
                    generated = [make_custom_preset(registry, document, arguments.base)]
                else:
                    if arguments.preset != "balanced" or any(
                        getattr(arguments, k) is not None for k in EFFECT_FIELDS
                    ):
                        raise ValueError(
                            "Add --name to save customized parameters, or omit overrides to register the built-in pack"
                        )
                    generated = make_presets(registry, arguments.base)
            result = update_registry(
                arguments.registry,
                generated,
                remove=arguments.command == "unregister",
                dry_run=arguments.dry_run,
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"niri-fx: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
