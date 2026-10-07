"""Dependency-free command line interface."""

import argparse
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from . import __version__
from .action_sets import ACTION_SETS
from .catalog import COLLECTIONS, PROFILES, STYLES, collection_documents, documents, title
from .documents import effect_document, load_document, parse_document
from .effects import (
    FAMILIES,
    PARAMETERS,
    PRESETS,
    describe_presets,
    render_kdl,
)
from .integration import (
    default_inir_root,
    default_registry,
    make_custom_preset,
    make_presets,
    read_shell_presets,
    update_registry,
)

EFFECT_FIELDS = tuple(PARAMETERS)


def effect_options(command):
    selection = command.add_mutually_exclusive_group()
    # In older argparse versions a value identical to an action's default does
    # not count toward mutual exclusion. Supply the fallback on the root parser
    # so explicitly choosing Balanced still conflicts with --profile.
    selection.add_argument("--preset", choices=PRESETS, default=argparse.SUPPRESS)
    selection.add_argument(
        "--profile", choices=PROFILES, help="Use a ready-made open/close pairing"
    )
    density = command.add_mutually_exclusive_group()
    for name, spec in PARAMETERS.items():
        options = {
            "help": spec["label"]
            + (
                f" ({spec['limits'][0]}–{spec['limits'][1]}{spec['unit']})"
                if spec["limits"]
                else ""
            )
        }
        if spec["type"] == "boolean":
            options.update(action=argparse.BooleanOptionalAction, default=None)
        elif spec["choices"]:
            options["choices"] = spec["choices"]
        else:
            options["type"] = int if spec["integer"] else float
        target = density if name in ("tile_size", "particles") else command
        target.add_argument("--" + name.replace("_", "-"), **options)


def selected_effect(arguments):
    if getattr(arguments, "custom", None):
        if (
            arguments.profile
            or arguments.preset != "balanced"
            or any(getattr(arguments, k, None) is not None for k in EFFECT_FIELDS)
        ):
            raise ValueError(
                "--custom uses the file's parameters; do not combine it with effect overrides"
            )
        return parse_document(load_document(arguments.custom))[2]
    if getattr(arguments, "profile", None):
        if getattr(arguments, "name", None):
            raise ValueError(
                "--profile uses its built-in name; omit --name or import a custom document"
            )
        if any(getattr(arguments, k, None) is not None for k in EFFECT_FIELDS):
            raise ValueError(
                "--profile uses independent action settings; customize it in Studio instead of combining effect overrides"
            )
        return PROFILES[arguments.profile]
    overrides = {
        k: getattr(arguments, k) for k in EFFECT_FIELDS if getattr(arguments, k, None) is not None
    }
    if overrides.get("tile_size") is not None:
        overrides["particles"] = 0
    effect = replace(PRESETS[arguments.preset], **overrides)
    inactive = {
        name
        for name, spec in PARAMETERS.items()
        if spec["families"] and effect.family not in spec["families"]
    }
    if inactive.intersection(overrides):
        raise ValueError(
            f"Options do not apply to the {effect.family} family: "
            + ", ".join(sorted(inactive.intersection(overrides)))
        )
    return effect


def parser():
    root = argparse.ArgumentParser(
        description="NiriFX window effects and native iNiR/iRiS presets."
    )
    root.add_argument("--version", action="version", version=__version__)
    root.set_defaults(preset="balanced")
    commands = root.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="List ready-made presets (JSON by default)")
    listing.add_argument("--profiles", action="store_true", help="List curated open/close pairings")
    listing.add_argument(
        "--documents", action="store_true", help="Portable documents for all styles and profiles"
    )
    listing.add_argument(
        "--summary", action="store_true", help="Compact style and profile metadata as JSON"
    )
    listing.add_argument("--text", action="store_true", help="Readable preset names and timings")
    listing.add_argument("--recommended", action="store_true", help="Show the starter selection")
    listing.add_argument("--family", choices=FAMILIES)
    listing.add_argument("--search", default="", help="Filter preset names and families")
    collections = listing.add_mutually_exclusive_group()
    collections.add_argument("--collections", action="store_true", help="List curated collections")
    collections.add_argument(
        "--collection", choices=COLLECTIONS, help="Browse a collection of styles and pairings"
    )
    commands.add_parser("families", help="Print supported effect families and capabilities as JSON")
    agent = commands.add_parser("agent-info", help="Print automation workflows and contracts")
    agent_format = agent.add_mutually_exclusive_group()
    agent_format.add_argument("--skill", action="store_true", help="Print the packaged agent skill")
    agent_format.add_argument(
        "--parameters", action="store_true", help="Print effect and pointer controls as JSON"
    )
    inspect = commands.add_parser(
        "inspect", help="Validate and print normalized style/profile JSON"
    )
    document = inspect.add_mutually_exclusive_group(required=True)
    document.add_argument("--custom", type=Path)
    document.add_argument("--profile", choices=PROFILES)
    profile = commands.add_parser("profile", help="Create an independent action profile as JSON")
    from .fragment_motion import PRESETS as FRAGMENT_PRESETS
    from .motion import MOTION_PACKS
    from .pointer import PRESETS as POINTER_PRESETS

    profile.add_argument(
        "--fragment-preset",
        choices=FRAGMENT_PRESETS,
        help="Choose a continuous Move prefab and save all its response values in JSON",
    )
    profile.add_argument(
        "--pointer",
        choices=(*POINTER_PRESETS, "preserve", "off"),
        help="Save optional pointer wobble settings in JSON; off saves an explicit zero strength",
    )

    profile.add_argument(
        "--desktop-motion",
        choices=MOTION_PACKS,
        help="Include stock workspace, camera and overview timing",
    )
    profile.add_argument("--name")
    profile.add_argument(
        "--open",
        "--open-preset",
        dest="open_preset",
        choices=(*PRESETS, "preserve", "off"),
        help="Opening choice: a preset, preserve, or off",
    )
    profile.add_argument(
        "--close",
        "--close-preset",
        dest="close_preset",
        choices=(*PRESETS, "preserve", "off"),
        help="Closing choice: a preset, preserve, or off",
    )
    profile.add_argument("--action-set", choices=ACTION_SETS, help="Start with a coordinated look")
    profile.add_argument(
        "--include-resize", action="store_true", help="Include the set's matching resize effect"
    )
    profile.add_argument(
        "--include-movement",
        action="store_true",
        help="Include the set's NiriFX movement choice in JSON; does not activate it",
    )
    profile.add_argument(
        "--resize",
        "--resize-preset",
        dest="resize_preset",
        choices=[
            *[k for k, e in PRESETS.items() if FAMILIES[e.family]["resize"]],
            "preserve",
            "off",
        ],
    )
    profile.add_argument(
        "--movement",
        "--movement-preset",
        dest="movement_preset",
        choices=[
            *[k for k, e in PRESETS.items() if FAMILIES[e.family]["movement"]],
            "preserve",
            "off",
        ],
        help="Save a NiriFX movement action in JSON; activate it separately",
    )
    profile.add_argument(
        "--swap",
        "--swap-preset",
        dest="swap_preset",
        choices=[
            *[k for k, e in PRESETS.items() if FAMILIES[e.family]["movement"]],
            "preserve",
            "off",
        ],
        help="Independent explicit-swap style; requires the NiriFX swap contract",
    )
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
    studio = commands.add_parser(
        "studio", help="Open the NiriFX Library and Studio for standalone or shell presets"
    )
    effect_options(studio)
    studio.add_argument("--custom", type=Path)
    studio.add_argument("--no-browser", action="store_true")
    studio.add_argument("--edit", action="store_true", help="Open detailed Studio controls")
    studio_actions = studio.add_mutually_exclusive_group()
    studio_actions.add_argument(
        "--restore",
        action="store_true",
        help="Restore the last Library Apply for this setup and exit",
    )
    studio_actions.add_argument(
        "--status",
        action="store_true",
        help="Print Library active selection and restore availability as JSON",
    )
    studio.add_argument(
        "--active", action="store_true", help="Start from the recognized active profile"
    )
    studio.add_argument(
        "--target",
        choices=("auto", "inir", "noctalia", "standalone", "native"),
        default="auto",
        help="Activation target; auto follows explicit native options, a managed session or shared setup, then iNiR or standalone",
    )
    studio.add_argument(
        "--browser", action="store_true", help="Open a browser tab instead of an app-style window"
    )
    studio.add_argument(
        "--port", type=int, default=0, help="Loopback port; default chooses an available port"
    )
    from .setup import default_config, default_state

    studio.add_argument("--config", type=Path, default=default_config())
    studio.add_argument(
        "--niri-binary",
        "--movement-binary",
        dest="movement_binary",
        type=Path,
        help="Trusted NiriFX session compositor for movement and pointer activation",
    )
    studio.add_argument("--preset-dir", type=Path, help="Connected Noctalia preset directory")
    studio.add_argument("--picker-file", type=Path, help="Connected Noctalia animation target file")
    studio.add_argument(
        "--native-root",
        type=Path,
        help="Managed session storage; defaults to native command storage",
    )
    studio.add_argument(
        "--native-base",
        help="Exact retained bundle ID to customize; default is the next-login selection",
    )
    studio.add_argument(
        "--shared-config",
        type=Path,
        help="Normal Niri config to offer for reviewed sharing in the native session",
    )
    studio.add_argument(
        "--stock-binary", default="niri", help="Trusted stock Niri executable for shared validation"
    )

    picker = commands.add_parser("picker", help="Open an optional desktop style/profile picker")
    picker.add_argument("--toolkit", choices=("quickshell", "gtk"), default="quickshell")
    picker.add_argument("--config", type=Path, default=default_config())
    picker.add_argument("--state", type=Path, help="Undo snapshots (default: separate per toolkit)")
    picker.add_argument("--custom", type=Path, help="Start with an exported style or profile")
    location = picker.add_mutually_exclusive_group()
    location.add_argument(
        "--qml-dir", action="store_true", help="Print the reusable QML component directory"
    )
    location.add_argument(
        "--gtk-dir", action="store_true", help="Print the reusable GTK module directory"
    )
    studio.add_argument(
        "--state",
        type=Path,
        default=default_state().parent,
        help="Library, preferences and Apply history directory",
    )

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
    setup.add_argument(
        "--enable-movement",
        action="store_true",
        help="Explicitly activate NiriFX movement on a verified running compositor (standalone only)",
    )
    setup.add_argument(
        "--enable-pointer",
        action="store_true",
        help="Apply the profile's pointer settings on a verified running compositor (standalone only)",
    )
    setup.add_argument(
        "--niri-binary",
        "--movement-binary",
        dest="movement_binary",
        type=Path,
        help="Trusted Niri executable matching the running NiriFX session",
    )
    setup.add_argument("--launcher", action=argparse.BooleanOptionalAction, default=None)
    setup.add_argument(
        "--interactive",
        action="store_true",
        help="Guided preset selection, review and Undo in a terminal",
    )
    setup.add_argument("--expect-plan", help="Apply only if the reviewed plan_sha256 still matches")
    diagnose = commands.add_parser(
        "doctor", help="Check Niri, configuration and optional interfaces"
    )
    diagnose.add_argument("--text", action="store_true", help="Print a readable diagnostic report")
    diagnose.add_argument(
        "--niri-binary",
        "--movement-binary",
        dest="movement_binary",
        type=Path,
        help="Probe movement and pointer support in this trusted Niri binary (default: Niri on PATH)",
    )
    restore = commands.add_parser("restore", help="Review or restore the latest setup snapshot")
    restore.add_argument("--transaction", help="Restore a specific setup transaction")
    restore.add_argument(
        "--niri-binary",
        "--movement-binary",
        dest="movement_binary",
        type=Path,
        help="Trusted compositor required when Restore reintroduces NiriFX session settings",
    )
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
    from .native_cli import add_parser

    add_parser(commands)
    return root


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        if not (sys.stdin.isatty() and sys.stdout.isatty()):
            parser().print_help()
            return 0
        argv = ["setup", "--interactive"]
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "native":
            from .native_cli import run

            return run(arguments) or 0
        elif arguments.command == "families":
            print(json.dumps(FAMILIES, indent=2))
        elif arguments.command == "agent-info":
            from .agent import agent_info, parameter_info, skill_text

            if arguments.skill:
                print(skill_text())
            else:
                print(
                    json.dumps(parameter_info() if arguments.parameters else agent_info(), indent=2)
                )
        elif arguments.command == "list":
            from .terminal import catalog, print_catalog, print_collections

            if arguments.summary and (
                arguments.text or arguments.documents or arguments.collections
            ):
                raise ValueError(
                    "--summary cannot be combined with --text, --documents or --collections"
                )
            if arguments.collections:
                if (
                    arguments.profiles
                    or arguments.documents
                    or arguments.recommended
                    or arguments.family
                    or arguments.search
                ):
                    raise ValueError("--collections cannot be combined with style filters")
                if arguments.text:
                    print_collections()
                else:
                    print(json.dumps(collection_documents(), indent=2))
                return 0

            keys = catalog(
                arguments.search,
                arguments.family,
                arguments.recommended,
                profiles=arguments.profiles,
                all_styles=arguments.documents or arguments.summary,
                collection=arguments.collection,
            )
            if arguments.summary:
                from .catalog import summaries

                print(json.dumps(summaries(keys), indent=2))
            elif arguments.text:
                print_catalog(keys)
            else:
                presets = (
                    documents(PROFILES if arguments.profiles else STYLES)
                    if arguments.profiles or arguments.documents or arguments.collection
                    else describe_presets()
                )
                print(json.dumps({key: presets[key] for key in keys}, indent=2))
        elif arguments.command == "inspect":
            if arguments.profile:
                name, effect = title(arguments.profile), PROFILES[arguments.profile]
            else:
                name, _, effect = parse_document(load_document(arguments.custom))
            print(json.dumps(effect_document(name, effect), indent=2))
        elif arguments.command == "picker":
            from .picker import gtk_directory, launch_picker, qml_directory

            if arguments.qml_dir:
                print(qml_directory())
            elif arguments.gtk_dir:
                print(gtk_directory())
            else:
                launch_picker(arguments)
        elif arguments.command == "profile":
            from .motion import MOTION_PACKS
            from .pointer import PRESETS as POINTER_PRESETS
            from .pointer import PointerWobble
            from .profiles import Profile

            if arguments.action_set:
                if any(
                    getattr(arguments, key) is not None
                    for key in (
                        "open_preset",
                        "close_preset",
                        "resize_preset",
                        "movement_preset",
                        "swap_preset",
                        "desktop_motion",
                    )
                ):
                    raise ValueError(
                        "--action-set supplies the styles and timing; omit preset overrides"
                    )
                effect = ACTION_SETS[arguments.action_set].profile(
                    include_resize=arguments.include_resize,
                    include_movement=arguments.include_movement,
                )
                name = arguments.name if arguments.name is not None else title(arguments.action_set)
            else:
                if arguments.include_resize or arguments.include_movement:
                    raise ValueError("--include-resize and --include-movement require --action-set")

                def choose(value, default=None):
                    value = value if value is not None else default
                    return (
                        None
                        if value in (None, "preserve")
                        else "off"
                        if value == "off"
                        else PRESETS[value]
                    )

                effect = Profile(
                    open=choose(arguments.open_preset, "spring-wobble"),
                    close=choose(arguments.close_preset, "core-detonation"),
                    resize=choose(arguments.resize_preset),
                    movement=choose(arguments.movement_preset),
                    swap=choose(arguments.swap_preset),
                    motion=MOTION_PACKS[arguments.desktop_motion]
                    if arguments.desktop_motion
                    else None,
                )
                name = arguments.name if arguments.name is not None else "My Profile"
            if arguments.pointer:
                effect = replace(
                    effect,
                    pointer=None
                    if arguments.pointer == "preserve"
                    else PointerWobble(strength=0)
                    if arguments.pointer == "off"
                    else POINTER_PRESETS[arguments.pointer].wobble,
                )
            if arguments.fragment_preset:
                from .fragment_motion import PRESETS as FRAGMENT_PRESETS

                if arguments.movement_preset is not None:
                    raise ValueError("--fragment-preset supplies Move; omit --movement-preset")
                choice = FRAGMENT_PRESETS[arguments.fragment_preset]
                effect = replace(effect, movement=choice.effect, fragment_motion=choice.settings)
            document = effect.document(name)
            parse_document(document)
            print(json.dumps(document, indent=2))
        elif arguments.command == "doctor":
            from .setup import doctor

            report = doctor(arguments)
            if arguments.text:
                from .terminal import print_diagnostics

                print_diagnostics(report)
            else:
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
                    restore(
                        arguments.state,
                        arguments.transaction,
                        arguments.apply,
                        binary=arguments.movement_binary,
                    ),
                    indent=2,
                )
            )
        elif arguments.command == "setup":
            from .setup import apply_plan, plan_setup, summarize

            if arguments.launcher is None:
                arguments.launcher = not arguments.interactive
            if arguments.interactive:
                from .terminal import guide

                if not (sys.stdin.isatty() and sys.stdout.isatty()):
                    raise ValueError(
                        "Interactive setup needs a terminal. Use setup to review JSON, then --apply."
                    )
                if (
                    arguments.custom
                    or arguments.name
                    or arguments.enable_movement
                    or arguments.enable_pointer
                    or any(getattr(arguments, k) is not None for k in EFFECT_FIELDS)
                ):
                    raise ValueError(
                        "The guide selects built-in presets. Use Studio or setup without --interactive for custom settings."
                    )
                if arguments.apply or arguments.dry_run or arguments.expect_plan:
                    raise ValueError(
                        "The guide reviews and confirms each change; omit --apply, --dry-run and --expect-plan."
                    )
                guide(arguments)
                return 0
            if arguments.custom and arguments.name:
                raise ValueError("--custom already supplies a name; omit --name")
            if arguments.expect_plan and not arguments.apply:
                raise ValueError("--expect-plan is only used with --apply")
            plan = plan_setup(
                arguments,
                selected_effect(arguments),
                load_document(arguments.custom) if arguments.custom else None,
            )
            if (
                plan["target"] == "inir"
                and not (arguments.custom or arguments.name or arguments.profile)
                and (
                    arguments.preset != "balanced"
                    or any(getattr(arguments, k) is not None for k in EFFECT_FIELDS)
                )
            ):
                raise ValueError(
                    "Use --name to save customized iNiR settings; built-in registration preserves resize settings"
                )
            result = (
                apply_plan(plan, arguments.state, arguments.expect_plan)
                if arguments.apply
                else {**summarize(plan), "dry_run": True}
            )
            print(json.dumps(result, indent=2, ensure_ascii=False))
        elif arguments.command in ("render", "preview", "studio"):
            effect = selected_effect(arguments)
            name = (
                load_document(arguments.custom)["name"]
                if arguments.custom
                else title(arguments.profile)
                if arguments.profile
                else arguments.preset
            )
            if arguments.command == "render":
                print(render_kdl(effect), end="")
            elif arguments.command == "preview":
                from .preview import preview_document

                with arguments.output.open("x") as output:
                    output.write(preview_document(effect, name))
                print(arguments.output.resolve())
            else:
                from .studio import serve

                if arguments.restore or arguments.status:
                    from .library import Library, studio_target

                    library = Library(arguments, studio_target(arguments))
                    print(
                        json.dumps(
                            library.undo() if arguments.restore else library.listing(), indent=2
                        )
                    )
                else:
                    arguments.custom_name = name
                    arguments.native_document = bool(
                        arguments.custom
                        or arguments.profile
                        or any(
                            getattr(arguments, field, None) is not None for field in EFFECT_FIELDS
                        )
                        or any(value.split("=", 1)[0] == "--preset" for value in argv)
                    )
                    serve(arguments, effect)
        else:
            generated = []
            if arguments.command == "register":
                registry = read_shell_presets(arguments.inir_root)
                if arguments.custom:
                    if (
                        arguments.profile
                        or arguments.preset != "balanced"
                        or any(getattr(arguments, k) is not None for k in EFFECT_FIELDS)
                    ):
                        raise ValueError(
                            "--custom uses the file's parameters; do not combine it with effect overrides"
                        )
                    document = load_document(arguments.custom)
                    generated = [make_custom_preset(registry, document, arguments.base)]
                elif arguments.profile:
                    from .integration import make_builtin_profile

                    selected_effect(arguments)  # Reject ambiguous action overrides before writing.
                    generated = [make_builtin_profile(registry, arguments.profile, arguments.base)]
                elif arguments.name:
                    document = effect_document(arguments.name, selected_effect(arguments))
                    generated = [make_custom_preset(registry, document, arguments.base)]
                else:
                    if (
                        arguments.profile
                        or arguments.preset != "balanced"
                        or any(getattr(arguments, k) is not None for k in EFFECT_FIELDS)
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
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled. Completed changes remain available through restore.", file=sys.stderr)
        return 130
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"niri-fx: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
