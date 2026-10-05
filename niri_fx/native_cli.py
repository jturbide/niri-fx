"""Explicit native-session preparation and next-login selection commands."""

import json
import os
from pathlib import Path

from .native_session import default_root


def add_parser(commands):
    from .catalog import PROFILES
    from .fragment_motion import PRESETS as FRAGMENT_PRESETS
    from .presets import PRESETS

    native = commands.add_parser("native", help="Manage the NiriFX login session")
    actions = native.add_subparsers(dest="native_command", required=True)
    presets = actions.add_parser(
        "presets", help="List continuous fragment choices without changing settings"
    )
    presets.add_argument(
        "--text", action="store_true", help="Print concise preset names and descriptions"
    )
    status = actions.add_parser("status", help="Inspect installed bundles and next-login selection")
    status.add_argument(
        "--offline", action="store_true", help="Inspect stored bundles without connecting to Niri"
    )
    stage = actions.add_parser("stage", help="Review an isolated desktop binary/configuration pair")
    stage.add_argument("--manifest", type=Path, required=True)
    stage.add_argument(
        "--source", type=Path, required=True, help="Candidate source with Cargo.lock"
    )
    stage.add_argument(
        "--repository", type=Path, required=True, help="Checkout with the patch stack"
    )
    stage.add_argument("--config", type=Path, required=True, help="Candidate KDL config")
    stage.add_argument(
        "--snapshot-includes",
        action="store_true",
        help="Review and copy the config's include tree into the isolated bundle",
    )
    install = actions.add_parser("install", help="Prepare the complete NiriFX login session")
    install.add_argument(
        "--candidate", type=Path, required=True, help="Finished session candidate directory"
    )
    install.add_argument(
        "--config", type=Path, required=True, help="KDL config to copy with its includes"
    )
    install.add_argument("--name", default="NiriFX", help="Login chooser label")
    select = actions.add_parser("select", help="Select a staged bundle for the next NiriFX login")
    select.add_argument("bundle", help="Exact bundle ID reported by stage/status")
    configure = actions.add_parser(
        "configure", help="Review portable settings against a retained bundle for the next login"
    )
    configure.add_argument("bundle", help="Exact baseline or saved-customization bundle ID")
    choice = configure.add_mutually_exclusive_group(required=True)
    choice.add_argument("--document", type=Path, help="Portable preset/profile JSON")
    choice.add_argument(
        "--profile",
        dest="configure_profile",
        choices=PROFILES,
        help="Ready-made action combination",
    )
    choice.add_argument(
        "--preset", dest="configure_preset", choices=PRESETS, help="Ready-made open/close style"
    )
    configure.add_argument(
        "--fragment-preset",
        choices=FRAGMENT_PRESETS,
        help="Explicitly replace movement with this continuous response and its matching material",
    )
    rollback = actions.add_parser("rollback", help="Restore the previous next-login selection")
    entry = actions.add_parser(
        "session-entry", help="Stage a login launcher and display-manager entry"
    )
    entry.add_argument("--name", default="NiriFX", help="Login chooser label")
    for command in (status, stage, install, select, configure, rollback, entry):
        command.add_argument(
            "--root", type=Path, default=default_root(), help="Native session storage"
        )
    for command in (stage, install, select, configure, rollback, entry):
        command.add_argument("--apply", action="store_true", help="Write the reviewed changes")
        command.add_argument(
            "--expect-plan", help="Require this reviewed plan_sha256 when applying"
        )


def run(args):
    from . import native_session
    from .setup import apply_plan, summarize

    action = args.native_command
    if action == "presets":
        from .native_customization import fragment_choices

        choices = fragment_choices()
        if args.text:
            for key, preset in choices.items():
                print(f"{key:<10} {preset['name']}: {preset['description']}")
        else:
            print(json.dumps(choices, indent=2))
        return
    root = args.root.expanduser().absolute()
    if getattr(args, "expect_plan", None) and not args.apply:
        raise ValueError("--expect-plan requires --apply")
    if action == "status":
        result = native_session.status(
            root, socket_path=None if args.offline else os.environ.get("NIRI_SOCKET")
        )
    else:
        if action == "stage":
            plan = native_session.stage_plan(
                args.manifest,
                args.source,
                args.repository,
                args.config,
                root,
                snapshot_includes=args.snapshot_includes,
            )
            scope = "staging"
        elif action == "install":
            from .native_install import install_plan

            plan = install_plan(root, args.candidate, args.config, name=args.name)
            scope = "selection"
        elif action == "select":
            plan = native_session.select_plan(root, args.bundle)
            scope = "selection"
        elif action == "configure":
            from .documents import load_document
            from .native_customization import configuration_document, configure_plan

            document = configuration_document(
                document=load_document(args.document) if args.document is not None else None,
                profile=args.configure_profile,
                preset=args.configure_preset,
                fragment_preset=args.fragment_preset,
            )

            plan = configure_plan(
                root,
                args.bundle,
                document,
                fragment_preset=args.fragment_preset,
            )
            scope = "selection"
        elif action == "rollback":
            plan = native_session.rollback_plan(root)
            scope = "selection"
        else:
            from .native_entry import entry_plan

            plan = entry_plan(root, args.name)
            scope = "entry"
        if args.apply and action == "configure":
            from .native_customization import apply_native

            result = apply_native(plan, root, expected=args.expect_plan)
        else:
            result = (
                apply_plan(plan, root / "state" / scope, args.expect_plan)
                if args.apply
                else summarize(plan)
            )
        # Bundles are retained recovery data. Generic Restore can remove files;
        # the native command exposes selector-only rollback instead.
        result.pop("restore", None)
        result["dry_run"] = not args.apply
        result["next_step"] = (
            "Review native select with this bundle ID."
            if action == "stage"
            else (
                "Log out when ready, then choose NiriFX. The running session is unchanged."
                if plan["selection"]["selected"]
                else "No native version is selected. Choose stock Niri at the next login."
            )
            if action in ("select", "configure", "rollback")
            else "Review the staged desktop entry before administrator registration."
        )
    print(json.dumps(result, indent=2))
