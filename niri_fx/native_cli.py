"""Explicit native-session preparation and next-login selection commands."""

import json
from pathlib import Path

from .native_session import default_root


def add_parser(commands):
    native = commands.add_parser("native", help="Prepare experimental compositor sessions")
    actions = native.add_subparsers(dest="native_command", required=True)
    status = actions.add_parser("status", help="Inspect installed bundles and next-login selection")
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
    select = actions.add_parser("select", help="Select a staged bundle for the next NiriFX login")
    select.add_argument("bundle", help="Exact bundle ID reported by stage/status")
    rollback = actions.add_parser("rollback", help="Restore the previous next-login selection")
    entry = actions.add_parser(
        "session-entry", help="Stage a login launcher and display-manager entry"
    )
    entry.add_argument("--name", default="NiriFX (experimental)", help="Login chooser label")
    for command in (status, stage, select, rollback, entry):
        command.add_argument(
            "--root", type=Path, default=default_root(), help="Native session storage"
        )
    for command in (stage, select, rollback, entry):
        command.add_argument("--apply", action="store_true", help="Write the reviewed changes")
        command.add_argument(
            "--expect-plan", help="Require this reviewed plan_sha256 when applying"
        )


def run(args):
    from . import native_session
    from .setup import apply_plan, summarize

    action = args.native_command
    root = args.root.expanduser().absolute()
    if getattr(args, "expect_plan", None) and not args.apply:
        raise ValueError("--expect-plan requires --apply")
    if action == "status":
        result = native_session.status(root)
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
        elif action == "select":
            plan = native_session.select_plan(root, args.bundle)
            scope = "selection"
        elif action == "rollback":
            plan = native_session.rollback_plan(root)
            scope = "selection"
        else:
            from .native_entry import entry_plan

            plan = entry_plan(root, args.name)
            scope = "entry"
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
            if action in ("select", "rollback")
            else "Review the staged desktop entry before administrator registration."
        )
    print(json.dumps(result, indent=2))
