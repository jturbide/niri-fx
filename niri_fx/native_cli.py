"""Reviewed native-session preparation, selection and explicit desktop reloads."""

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
    export = actions.add_parser("export", help="Export a complete saved recipe as portable JSON")
    export.add_argument("bundle", help="Retained bundle with a saved effects recipe")
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
    adopt = actions.add_parser("adopt", help="Adopt or upgrade a packaged NiriFX session")
    adopt.add_argument(
        "--candidate",
        type=Path,
        default=Path("/usr/lib/niri-fx/session-candidate"),
        help="Packaged full-session candidate directory",
    )
    adopt.add_argument("--config", type=Path, help="Configuration for first adoption only")
    adopt.add_argument(
        "--registered-entry",
        type=Path,
        default=Path("/usr/share/wayland-sessions/niri-fx-packaged.desktop"),
        help="Package-owned login entry to verify",
    )
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
    share = actions.add_parser(
        "share", help="Share normal Niri desktop settings and supported effects with NiriFX"
    )
    share.add_argument("bundle", help="Retained bundle whose saved effect choices to use")
    share.add_argument("--config", type=Path, required=True, help="Normal Niri configuration")
    share.add_argument(
        "--stock-binary", default="niri", help="Trusted stock Niri executable for validation"
    )
    recover = actions.add_parser(
        "recover", help="Select a shared session's frozen configuration for recovery"
    )
    recover.add_argument("bundle", help="Shared bundle whose frozen snapshot to recover")
    rollback = actions.add_parser("rollback", help="Restore the previous next-login selection")
    for command in (configure, rollback):
        command.add_argument(
            "--live",
            action="store_true",
            help="Also reload the verified NiriFX desktop; Apply requires --expect-plan",
        )
    entry = actions.add_parser(
        "session-entry", help="Stage a login launcher and display-manager entry"
    )
    entry.add_argument("--name", default="NiriFX", help="Login chooser label")
    tools_status = actions.add_parser(
        "tools-status", help="Inspect shared CLI, Studio and login runtime selection"
    )
    tools_update = actions.add_parser(
        "tools-update", help="Review this installed runtime as the shared NiriFX tool version"
    )
    tools_update.add_argument(
        "--bootstrap-runtime",
        type=Path,
        help="Existing trusted virtual environment to retain during first login-entry migration",
    )
    tools_update.add_argument("--cli-path", type=Path, help="Managed CLI launcher location")
    tools_update.add_argument(
        "--legacy-tools-runtime",
        type=Path,
        help="Trusted existing CLI/Studio environment if it differs from the bootstrap login runtime",
    )
    tools_update.add_argument("--desktop-path", type=Path, help="Managed Studio desktop file")
    tools_rollback = actions.add_parser(
        "tools-rollback", help="Review restoring the previous compatible NiriFX tool runtime"
    )
    for command in (tools_status, tools_update, tools_rollback):
        command.add_argument(
            "--registered-entry",
            type=Path,
            required=command is not tools_status,
            help="Display manager's NiriFX desktop file to verify without modifying it",
        )
    for command in (
        status,
        export,
        stage,
        install,
        adopt,
        select,
        configure,
        share,
        recover,
        rollback,
        entry,
        tools_status,
        tools_update,
        tools_rollback,
    ):
        command.add_argument(
            "--root", type=Path, default=default_root(), help="Native session storage"
        )
    for command in (
        stage,
        install,
        adopt,
        select,
        configure,
        share,
        recover,
        rollback,
        entry,
        tools_update,
        tools_rollback,
    ):
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
    if action == "export":
        from .native_customization import portable_recipe

        recipe = portable_recipe(root, args.bundle)
        if recipe is None:
            raise ValueError("This bundle has no saved recipe; choose and save effects first")
        print(json.dumps(recipe["document"], indent=2))
        return
    if getattr(args, "expect_plan", None) and not args.apply:
        raise ValueError("--expect-plan requires --apply")
    if action in ("share", "recover") and args.apply and not args.expect_plan:
        raise ValueError("Shared settings changes require --expect-plan from a fresh review")
    if action == "adopt":
        from .native_package import adopt_plan, apply_adoption

        if args.apply and not args.expect_plan:
            raise ValueError("Package adoption requires --expect-plan from a fresh review")
        plan = adopt_plan(root, args.candidate, args.config, registered_entry=args.registered_entry)
        result = (
            apply_adoption(plan, root, expected=args.expect_plan) if args.apply else summarize(plan)
        )
        result["dry_run"] = not args.apply
        print(json.dumps(result, indent=2))
        return 0
    if action.startswith("tools-"):
        from . import native_tools

        if action == "tools-status":
            result = native_tools.status(root, registered_entry=args.registered_entry)
        else:
            if args.apply and not args.expect_plan:
                raise ValueError("Tool runtime changes require --expect-plan from a fresh review")
            plan = (
                native_tools.update_plan(
                    root,
                    bootstrap_runtime=args.bootstrap_runtime,
                    legacy_tools_runtime=args.legacy_tools_runtime,
                    registered_entry=args.registered_entry,
                    cli_path=args.cli_path,
                    desktop_path=args.desktop_path,
                )
                if action == "tools-update"
                else native_tools.rollback_plan(root, registered_entry=args.registered_entry)
            )
            result = (
                native_tools.apply_tools(plan, root, expected=args.expect_plan)
                if args.apply
                else summarize(plan)
            )
            result.pop("restore", None)
            result["dry_run"] = not args.apply
        print(json.dumps(result, indent=2))
        return 0
    live_requested = getattr(args, "live", False)
    if live_requested and args.apply and not args.expect_plan:
        raise ValueError("--live --apply requires --expect-plan from a live review")
    # Capture the advertised socket once; review and activation must use the
    # same endpoint even if another component changes the process environment.
    live_socket = os.environ.get("NIRI_SOCKET") if live_requested else None
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
            )
            scope = "selection"
        elif action == "share":
            from .native_shared import share_plan

            plan = share_plan(root, args.bundle, args.config, stock_binary=args.stock_binary)
            scope = "selection"
        elif action == "recover":
            from .native_shared import recovery_plan

            plan = recovery_plan(root, args.bundle)
            scope = "selection"
        elif action == "rollback":
            plan = native_session.rollback_plan(root)
            scope = "selection"
        else:
            from .native_entry import entry_plan

            plan = entry_plan(root, args.name)
            scope = "entry"
        if live_requested:
            from .native_live import activation_plan

            live_base = args.bundle if action == "configure" else plan["selection"]["selected"]
            plan = activation_plan(
                plan, root, live_base, socket_path=live_socket, require_live=True
            )
        if args.apply and plan.get("shared"):
            from .native_shared import apply_shared

            result = apply_shared(plan, root, expected=args.expect_plan)
        elif args.apply and action == "configure":
            from .native_customization import apply_native

            result = apply_native(plan, root, expected=args.expect_plan)
        else:
            result = (
                apply_plan(plan, root / "state" / scope, args.expect_plan)
                if args.apply
                else summarize(plan)
            )
        if live_requested and args.apply:
            from .native_live import activation_result

            result = activation_result(plan, result, root, live_base, socket_path=live_socket)
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
            if action in ("select", "configure", "rollback", "recover")
            else "Review the staged desktop entry before administrator registration."
        )
        if action == "share" or plan.get("activation") == "config-written":
            result["next_step"] = (
                "Shared effect files were updated. Sessions already using the shared configuration "
                "reload included files automatically; first adoption or a different compositor build "
                "requires the next NiriFX login. Active settings were not independently confirmed."
                if args.apply
                else "Review both sessions' generated settings, then repeat with --apply "
                "--expect-plan and this plan_sha256."
            )
        if live_requested:
            result["next_step"] = (
                result["live"]["detail"]
                if args.apply
                else "Review these changes, then repeat this command with --apply "
                "--expect-plan and the reviewed plan_sha256."
            )
    print(json.dumps(result, indent=2))
    return 1 if live_requested and args.apply and result["live"]["status"] != "applied" else 0
