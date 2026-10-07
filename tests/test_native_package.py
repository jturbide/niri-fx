"""Package adoption retains tools/bundles without package-manager user writes."""

import copy
import hashlib
import io
import json
import os
import runpy
import shutil
import tempfile
import types
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import test_native_install
import test_native_tools

from niri_fx import (
    native_build,
    native_customization,
    native_package,
    native_session,
    native_shared,
    native_tools,
    native_tools_launcher,
    package_session,
    setup,
)
from niri_fx.agent import agent_info
from niri_fx.cli import main, parser
from niri_fx.documents import effect_document
from niri_fx.fragment_motion import PRESETS
from niri_fx.library import Library, studio_target
from niri_fx.profiles import Profile
from niri_fx.storage import digest


class NativePackageTests(unittest.TestCase):
    def setUp(self):
        fixture = test_native_install.NativeInstallTests(methodName="runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        temporary = tempfile.TemporaryDirectory(prefix="native-package-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.home = self.directory / "home"
        self.data = self.home / "data"
        self.root = self.data / "niri-fx/native"
        self.environment = patch.dict(
            os.environ, {"HOME": str(self.home), "XDG_DATA_HOME": str(self.data)}
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.registered = self.directory / "usr/share/wayland-sessions/niri-fx-packaged.desktop"
        self.registered.parent.mkdir(parents=True)
        self.registered.write_bytes(package_session.DESKTOP_ENTRY)
        self.registered.chmod(0o644)
        self.launcher = self.directory / "usr/bin/niri-fx-session"
        self.launcher.parent.mkdir(parents=True)
        self.launcher.write_bytes(Path(package_session.__file__).read_bytes())
        self.launcher.chmod(0o755)
        launcher_patch = patch.object(native_package, "SESSION_LAUNCHER", self.launcher)
        launcher_patch.start()
        self.addCleanup(launcher_patch.stop)
        self.source = self.directory / "source/niri_fx"
        shutil.copytree(
            native_package.PACKAGE_DIRECTORY,
            self.source,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        self.package_patch = patch.object(native_package, "PACKAGE_DIRECTORY", self.source)
        self.package_patch.start()
        self.addCleanup(self.package_patch.stop)

    def plan(self, *, config=True):
        return native_package.adopt_plan(
            self.root,
            self.fixture.candidate,
            self.fixture.fixture.config if config else None,
            registered_entry=self.registered,
        )

    def apply(self, plan):
        return native_package.apply_adoption(plan, self.root, setup.plan_fingerprint(plan))

    def runtime(self, plan):
        return native_tools_launcher.runtime_record(
            self.root / "tools", plan["selection"]["tools_runtime"]
        )

    def upgrade_candidate(self):
        binary = self.fixture.fixture.binary
        binary.write_bytes(binary.read_bytes() + b"new synthetic compositor\n")
        self.fixture.fixture.record["binary_sha256"] = digest(binary.read_bytes())
        self.fixture.fixture.save_record()

    def configure_recipe(self, identifier):
        fragment = PRESETS["tear"]
        document = effect_document(
            "Saved response",
            Profile(
                movement=fragment.effect, fragment_motion=fragment.settings, close="off", swap="off"
            ),
        )
        plan = native_customization.configure_plan(self.root, identifier, document)
        native_customization.apply_native(plan, self.root, expected=setup.plan_fingerprint(plan))
        return native_session.inspect_bundle(self.root, plan["selection"]["bundle_id"])

    def test_update_preserves_frozen_recipe_and_keeps_both_tool_runtimes(self):
        initial = self.plan()
        self.apply(initial)
        self.assertEqual(self.plan(config=False)["changes"], [])
        old = self.configure_recipe(initial["selection"]["selected"])
        recipe = native_customization.portable_recipe(self.root, old["bundle_id"])
        config = Path(old["config"]).read_bytes()
        self.upgrade_candidate()
        module = self.source / "__init__.py"
        module.write_bytes(module.read_bytes() + b"# next package build\n")
        with patch("subprocess.run") as command:
            update = self.plan(config=False)
        command.assert_not_called()
        self.apply(update)
        new = native_session.inspect_bundle(self.root, update["selection"]["selected"])
        self.assertEqual(native_customization.portable_recipe(self.root, new["bundle_id"]), recipe)
        self.assertEqual(Path(new["config"]).read_bytes(), config)
        self.assertEqual(update["selection"]["previous"], old["bundle_id"])
        tools = native_tools._read_selection(self.root)[0]
        self.assertEqual(tools["previous"], initial["selection"]["tools_runtime"])
        native_tools_launcher.verify_runtime(self.runtime(initial))
        native_tools_launcher.verify_runtime(self.runtime(update))
        rollback = native_tools.rollback_plan(self.root, registered_entry=self.registered)
        native_tools.apply_tools(rollback, self.root, setup.plan_fingerprint(rollback))
        self.assertEqual(
            native_tools._read_selection(self.root)[0]["current"],
            initial["selection"]["tools_runtime"],
        )
        self.assertEqual(native_session.load_selection(self.root)["selected"], new["bundle_id"])

    def test_shared_update_keeps_recipe_projection_and_external_settings(self):
        initial = self.plan()
        self.apply(initial)
        customized = self.configure_recipe(initial["selection"]["selected"])
        config = self.directory / "desktop/config.kdl"
        config.parent.mkdir()
        config.write_text('include "shell.kdl"\ninput {}\n')
        shell = config.with_name("shell.kdl")
        shell.write_text('environment { EXAMPLE "synthetic user edit"; }\n')
        stock = self.directory / "stock-niri"
        stock.write_bytes(b"synthetic stock, never executed\n")
        stock.chmod(0o755)
        shared_plan = native_shared.share_plan(
            self.root, customized["bundle_id"], config, stock_binary=stock
        )
        native_shared.apply_shared(
            shared_plan, self.root, expected=setup.plan_fingerprint(shared_plan)
        )
        old = native_session.inspect_bundle(self.root, shared_plan["selection"]["selected"])
        original = {path: path.read_bytes() for path in (config, shell)}
        projections = {
            key: Path(old["shared"][key]).read_bytes()
            for key in ("native_include", "stock_include")
        }
        self.upgrade_candidate()
        with patch("subprocess.run") as command:
            update = self.plan(config=False)
        command.assert_not_called()
        self.apply(update)
        new = native_session.inspect_bundle(self.root, update["selection"]["selected"])
        self.assertEqual(new["shared"]["document"], old["shared"]["document"])
        for key, data in projections.items():
            self.assertEqual(Path(new["shared"][key]).read_bytes(), data)
        self.assertEqual({path: path.read_bytes() for path in original}, original)
        self.assertEqual(update["selection"]["previous"], old["bundle_id"])
        self.assertEqual(update["validation_binary"], new["binary"])
        self.assertEqual(
            update["validation_checks"], [{"config": str(config), "binary": str(stock)}]
        )

    def test_cli_and_agent_review_apply_contract(self):
        base = [
            "native",
            "adopt",
            "--candidate",
            str(self.fixture.candidate),
            "--registered-entry",
            str(self.registered),
        ]
        fresh = [*base, "--config", str(self.fixture.fixture.config)]
        output = io.StringIO()
        with redirect_stdout(output), patch("subprocess.run") as command:
            self.assertEqual(main(fresh), 0)
        command.assert_not_called()
        review = json.loads(output.getvalue())
        self.assertTrue(review["dry_run"])
        self.assertFalse(self.home.exists())
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main([*fresh, "--apply"]), 2)
            self.assertEqual(main([*fresh, "--apply", "--expect-plan", "wrong"]), 2)
        self.assertFalse(self.home.exists())
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([*fresh, "--apply", "--expect-plan", review["plan_sha256"]]), 0)
        applied = json.loads(output.getvalue())
        self.assertFalse(applied["dry_run"])
        self.assertNotIn("restore", applied)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(fresh), 2)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(base), 0)
        self.assertEqual(json.loads(output.getvalue())["changes"], [])
        operations = agent_info()["operations"]
        review_args = parser().parse_args(operations["native_adopt_review"]["argv"])
        apply_args = parser().parse_args(operations["native_adopt_apply"]["argv"])
        self.assertEqual(review_args.native_command, "adopt")
        self.assertIsNone(review_args.config)
        self.assertFalse(review_args.apply)
        self.assertTrue(apply_args.apply)
        self.assertEqual(apply_args.expect_plan, "REVIEWED_PLAN_SHA256")

    def test_review_executes_nothing_and_creates_no_user_files(self):
        with patch("subprocess.run") as command, patch("subprocess.Popen") as child:
            plan = self.plan()
        command.assert_not_called()
        child.assert_not_called()
        self.assertFalse(self.home.exists())
        self.assertFalse(self.root.exists())
        self.assertEqual(plan["target"], "native-session-adopt")
        self.assertTrue(
            all(
                not Path(item["target"]).is_relative_to(self.directory / "usr")
                for item in plan["changes"]
            )
        )
        self.assertEqual(Path(plan["changes"][-1]["target"]), self.root / "selection.json")
        paths = [Path(item["target"]) for item in plan["changes"]]
        self.assertLess(
            paths.index(self.root / "tools/launch.py"),
            paths.index(self.root / "tools/selection.json"),
        )
        self.assertLess(
            paths.index(self.root / "tools/selection.json"),
            paths.index(self.root / "selection.json"),
        )

    def test_apply_retains_complete_tools_and_dispatches_without_system_package(self):
        plan = self.plan()
        self.apply(plan)
        record = self.runtime(plan)
        self.assertEqual(record["schema"], 2)
        self.assertEqual(record["python"], "/usr/bin/python3")
        native_tools_launcher.verify_runtime(record)
        self.assertEqual(
            (self.root / "tools/niri-fx.desktop").read_bytes(), package_session.DESKTOP_ENTRY
        )
        self.assertEqual(self.registered.read_bytes(), package_session.DESKTOP_ENTRY)
        self.assertTrue((self.home / ".local/bin/niri-fx").is_symlink())
        self.assertTrue((self.data / "applications/niri-fx-studio.desktop").is_file())
        shutil.rmtree(self.source)
        native_tools_launcher.verify_runtime(record)
        probed = native_tools._probe(
            record["python"],
            self.root,
            [plan["selection"]["selected"]],
            package_path=record["package"],
            retained=record,
        )
        self.assertEqual(probed, record)
        with patch.object(package_session.os, "execv") as execute:
            package_session.main([])
        self.assertEqual(
            execute.call_args.args,
            (
                "/usr/bin/python3",
                ["/usr/bin/python3", "-I", "-B", str(self.root / "tools/launch.py"), "session"],
            ),
        )
        with (
            patch.object(native_tools_launcher, "__file__", str(self.root / "tools/launch.py")),
            patch.object(native_tools_launcher.os, "execv") as execute,
        ):
            native_tools_launcher.main(["cli", "--version"])
        command = execute.call_args.args[1]
        self.assertEqual(command[0:3], ["/usr/bin/python3", "-I", "-B"])
        self.assertIn(str(Path(record["package"]).parent), command)

    def test_adopted_studio_launcher_opens_native_editor_before_first_login(self):
        plan = self.plan()
        self.apply(plan)
        selected = (self.root / "selection.json").read_bytes()
        config = self.fixture.fixture.config.read_bytes()
        # Exercise the copied dispatcher and real CLI parser together. Merely
        # matching argv missed the incompatible auto-target/native-root pair.
        launcher = runpy.run_path(str(self.root / "tools/launch.py"))
        with patch("os.execv") as execute:
            launcher["main"](["studio"])
        arguments = execute.call_args.args[1][6:]

        def inspect_editor(args, _effect):
            target = studio_target(args)
            self.assertEqual(target, "native")
            library = Library(args, target)
            self.assertEqual(library.native_root, self.root)
            self.assertEqual(library.native_base["bundle_id"], plan["selection"]["selected"])
            self.assertIsNone(library.native_base.get("customization"))

        for invocation in (arguments, ["studio", "--native-root", str(self.root)]):
            with (
                self.subTest(invocation=invocation),
                patch.dict(os.environ, {"NIRI_SOCKET": ""}),
                patch("niri_fx.studio.serve", side_effect=inspect_editor) as serve,
            ):
                self.assertEqual(main(invocation), 0)
            serve.assert_called_once()
        self.assertEqual((self.root / "selection.json").read_bytes(), selected)
        self.assertEqual(self.fixture.fixture.config.read_bytes(), config)

    def test_fingerprint_registration_and_source_drift_refuse_before_writes(self):
        plan = self.plan()
        for expected in (None, "wrong"):
            with self.assertRaisesRegex(ValueError, "expect-plan"):
                native_package.apply_adoption(plan, self.root, expected)
        self.registered.write_text("changed by package update\n")
        with self.assertRaisesRegex(ValueError, "File changed"):
            self.apply(plan)
        self.registered.write_bytes(package_session.DESKTOP_ENTRY)
        self.source.joinpath("added.py").write_text("pass\n")
        with self.assertRaisesRegex(ValueError, "source inventory changed"):
            self.apply(plan)
        self.assertFalse(self.home.exists())

    def test_installed_session_dispatcher_is_required_and_bound_to_review(self):
        plan = self.plan()
        original = self.launcher.read_bytes()
        self.launcher.write_bytes(original + b"# package update\n")
        with self.assertRaisesRegex(ValueError, "File changed"):
            self.apply(plan)
        self.launcher.write_bytes(original)
        self.launcher.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "permissions changed"):
            self.apply(plan)
        with self.assertRaisesRegex(ValueError, "not executable"):
            self.plan()
        self.launcher.unlink()
        with self.assertRaises(FileNotFoundError):
            self.plan()
        os.mkfifo(self.launcher)
        with self.assertRaisesRegex(ValueError, "regular file"):
            self.plan()
        self.assertFalse(self.home.exists())

    def test_destination_addition_since_review_is_rejected(self):
        plan = self.plan()
        receipt = next(
            item
            for item in plan["changes"]
            if Path(item["target"]).parent == self.root / "tools/runtimes"
        )
        record = json.loads(receipt["after"])
        package = Path(record["package"])
        package.mkdir(parents=True)
        (package / "unowned.py").write_text("pass\n")
        with self.assertRaisesRegex(ValueError, "snapshot inventory changed"):
            self.apply(plan)
        self.assertFalse((self.root / "selection.json").exists())
        self.assertEqual((package / "unowned.py").read_text(), "pass\n")

    def test_validation_failure_restores_owned_files_and_selection(self):
        plan = self.plan()
        self.fixture.validator.side_effect = ValueError("synthetic invalid configuration")
        with self.assertRaisesRegex(ValueError, "synthetic invalid"):
            self.apply(plan)
        for relative in ("selection.json", "tools/selection.json", "tools/launch.py"):
            self.assertFalse((self.root / relative).exists())
        self.assertFalse((self.home / ".local/bin/niri-fx").is_symlink())
        self.assertFalse((self.data / "applications/niri-fx-studio.desktop").exists())
        self.assertEqual(self.registered.read_bytes(), package_session.DESKTOP_ENTRY)

    def interrupt_before(self, plan, target, *, include=False):
        """Simulate a killed writer, without the handled-failure unwinder."""
        for item in plan["changes"]:
            if Path(item["target"]) == target and not include:
                break
            setup._write_change(item, item["after"], item["before"])
            if Path(item["target"]) == target:
                break

    def prepare_second_adoption(self, *, shared=False):
        initial = self.plan()
        self.apply(initial)
        old = self.configure_recipe(initial["selection"]["selected"])
        if shared:
            config = self.directory / "desktop/config.kdl"
            config.parent.mkdir()
            config.write_text('include "shell.kdl"\ninput {}\n')
            config.with_name("shell.kdl").write_text('environment { EXAMPLE "keep me"; }\n')
            stock = self.directory / "stock-niri"
            stock.write_bytes(b"synthetic stock validator, never executed\n")
            stock.chmod(0o755)
            shared_plan = native_shared.share_plan(
                self.root, old["bundle_id"], config, stock_binary=stock
            )
            native_shared.apply_shared(
                shared_plan, self.root, expected=setup.plan_fingerprint(shared_plan)
            )
            old = native_session.inspect_bundle(self.root, shared_plan["selection"]["selected"])
        self.upgrade_candidate()
        module = self.source / "__init__.py"
        module.write_bytes(module.read_bytes() + b"# next synthetic package build\n")
        return initial, old, self.plan(config=False)

    def test_interrupted_upgrade_bundle_copies_resume_exact_frozen_and_shared_outputs(self):
        for shared in (False, True):
            for cut in (0, 1, -2):
                with self.subTest(shared=shared, cut=cut):
                    case = NativePackageTests("runTest")
                    case.setUp()
                    try:
                        initial, old, plan = case.prepare_second_adoption(shared=shared)
                        old_files = native_customization._owned_files(old)
                        folder = case.root / "bundles" / plan["selection"]["selected"]
                        writes = [
                            item
                            for item in plan["changes"]
                            if Path(item["target"]).is_relative_to(folder)
                        ]
                        selectors = {
                            path: path.read_bytes()
                            for path in (
                                case.root / "selection.json",
                                case.root / "tools/selection.json",
                            )
                        }
                        case.interrupt_before(plan, Path(writes[cut]["target"]), include=True)
                        self.assertFalse((folder / "bundle.json").exists())
                        self.assertEqual({path: path.read_bytes() for path in selectors}, selectors)
                        copied = {
                            path: path.read_bytes() for path in folder.rglob("*") if path.is_file()
                        }
                        resumed = case.plan(config=False)
                        self.assertFalse(
                            any(Path(item["target"]) in copied for item in resumed["changes"])
                        )
                        self.assertTrue(
                            any(
                                item["before"] is None
                                for item in resumed["observed"]
                                if Path(item["target"]).is_relative_to(folder)
                            )
                        )
                        remaining = [
                            item
                            for item in resumed["changes"]
                            if Path(item["target"]).is_relative_to(folder)
                        ]
                        self.assertEqual(Path(remaining[-1]["target"]), folder / "bundle.json")
                        case.apply(resumed)
                        selected = native_session.load_selection(case.root)
                        self.assertEqual(selected["selected"], plan["selection"]["selected"])
                        self.assertEqual(selected["previous"], old["bundle_id"])
                        tools = native_tools._read_selection(case.root)[0]
                        self.assertEqual(tools["previous"], initial["selection"]["tools_runtime"])
                        self.assertEqual(
                            native_customization._owned_files(
                                native_session.inspect_bundle(case.root, old["bundle_id"])
                            ),
                            old_files,
                        )
                        new = native_session.inspect_bundle(case.root, selected["selected"])
                        self.assertEqual(new["customization"], old["customization"])
                    finally:
                        case.doCleanups()

    def test_second_adoption_resumes_on_both_sides_of_tools_selector(self):
        for shared in (False, True):
            for after_tools in (False, True):
                with self.subTest(shared=shared, after_tools=after_tools):
                    case = NativePackageTests("runTest")
                    case.setUp()
                    try:
                        initial, old, plan = case.prepare_second_adoption(shared=shared)
                        case.interrupt_before(
                            plan, case.root / "tools/selection.json", include=after_tools
                        )
                        self.assertEqual(
                            native_session.load_selection(case.root)["selected"], old["bundle_id"]
                        )
                        case.apply(case.plan(config=False))
                        tools = native_tools._read_selection(case.root)[0]
                        self.assertEqual(tools["current"], plan["selection"]["tools_runtime"])
                        self.assertEqual(tools["previous"], initial["selection"]["tools_runtime"])
                        self.assertEqual(
                            native_session.load_selection(case.root)["previous"], old["bundle_id"]
                        )
                        # Both independent rollback lanes remain available after retry.
                        rollback = native_session.rollback_plan(case.root)
                        setup.apply_plan(
                            rollback,
                            case.root / "state/selection",
                            setup.plan_fingerprint(rollback),
                        )
                        self.assertEqual(
                            native_session.inspect_bundle(
                                case.root, native_session.load_selection(case.root)["selected"]
                            )["binary_sha256"],
                            old["binary_sha256"],
                        )
                        rollback = native_tools.rollback_plan(
                            case.root, registered_entry=case.registered
                        )
                        native_tools.apply_tools(
                            rollback, case.root, setup.plan_fingerprint(rollback)
                        )
                        self.assertEqual(
                            native_tools._read_selection(case.root)[0]["current"],
                            initial["selection"]["tools_runtime"],
                        )
                    finally:
                        case.doCleanups()

    def test_partial_upgrade_rejects_foreign_mutated_mode_link_and_special_files(self):
        for shared in (False, True):
            for mutation in ("foreign", "empty-directory", "bytes", "mode", "symlink", "fifo"):
                with self.subTest(shared=shared, mutation=mutation):
                    case = NativePackageTests("runTest")
                    case.setUp()
                    try:
                        _, old, plan = case.prepare_second_adoption(shared=shared)
                        folder = case.root / "bundles" / plan["selection"]["selected"]
                        binary = folder / "bin/niri"
                        case.interrupt_before(plan, binary, include=True)
                        if mutation == "foreign":
                            (folder / "foreign.txt").write_text("unowned\n")
                        elif mutation == "empty-directory":
                            (folder / "foreign").mkdir()
                        elif mutation == "bytes":
                            binary.write_bytes(b"changed")
                        elif mutation == "mode":
                            binary.chmod(0o700)
                        else:
                            binary.unlink()
                            if mutation == "symlink":
                                binary.symlink_to(case.fixture.fixture.binary)
                            else:
                                os.mkfifo(binary)
                        with self.assertRaises(ValueError):
                            case.plan(config=False)
                        self.assertEqual(
                            native_session.load_selection(case.root)["selected"], old["bundle_id"]
                        )
                        self.assertFalse((folder / "bundle.json").exists())
                    finally:
                        case.doCleanups()

    def test_partial_bundle_inventory_and_missing_files_are_bound_to_review(self):
        _, old, plan = self.prepare_second_adoption()
        folder = self.root / "bundles" / plan["selection"]["selected"]
        self.interrupt_before(plan, folder / "bin/niri", include=True)
        resumed = self.plan(config=False)
        selectors = {
            path: path.read_bytes()
            for path in (self.root / "selection.json", self.root / "tools/selection.json")
        }
        for name in ("unexpected.txt", "config.kdl"):
            path = folder / name
            path.write_text("arrived after review\n")
            path.chmod(0o600)
            with self.assertRaisesRegex(ValueError, "changed since"):
                self.apply(resumed)
            self.assertEqual(path.read_text(), "arrived after review\n")
            self.assertFalse((folder / "bundle.json").exists())
            self.assertEqual({path: path.read_bytes() for path in selectors}, selectors)
            path.unlink()
        self.apply(resumed)
        self.assertEqual(native_session.load_selection(self.root)["previous"], old["bundle_id"])

    def test_first_adoption_resumes_exact_assets_before_tools_selection(self):
        plan = self.plan()
        self.interrupt_before(plan, self.root / "tools/selection.json")
        self.assertFalse((self.root / "tools/selection.json").exists())
        self.assertFalse((self.root / "selection.json").exists())
        with patch("subprocess.run") as command:
            resumed = self.plan()
        command.assert_not_called()
        self.apply(resumed)
        native_tools_launcher.verify_runtime(self.runtime(resumed))
        self.assertEqual(
            native_session.load_selection(self.root)["selected"], plan["selection"]["selected"]
        )

    def test_first_adoption_resumes_after_tools_before_compositor_selection(self):
        plan = self.plan()
        self.interrupt_before(plan, self.root / "tools/selection.json", include=True)
        self.assertEqual(
            native_tools._read_selection(self.root)[0]["current"],
            plan["selection"]["tools_runtime"],
        )
        self.assertFalse((self.root / "selection.json").exists())
        resumed = self.plan()
        self.apply(resumed)
        self.assertEqual(
            native_session.load_selection(self.root)["selected"], plan["selection"]["selected"]
        )
        self.assertIsNone(native_tools._read_selection(self.root)[0]["previous"])

    def test_interrupted_first_adoption_preserves_other_changed_assets(self):
        plan = self.plan()
        self.interrupt_before(plan, self.root / "tools/selection.json")
        icon = self.root / "tools/niri-fx.svg"
        icon.write_text("external icon edit\n")
        with self.assertRaisesRegex(ValueError, "Existing tools file differs"):
            self.plan()
        self.assertEqual(icon.read_text(), "external icon edit\n")
        self.assertFalse((self.root / "selection.json").exists())

    def test_apply_source_probe_rejects_unusable_entrypoint_before_writes(self):
        cli = self.source / "cli.py"
        cli.write_bytes(cli.read_bytes() + b"\nmain = None\n")
        with patch("subprocess.run") as command:
            plan = self.plan()
        command.assert_not_called()
        with self.assertRaisesRegex(ValueError, "session entry points"):
            self.apply(plan)
        self.assertFalse(self.home.exists())

    def test_apply_source_probe_checks_current_and_rollback_bundles(self):
        initial = self.plan()
        self.apply(initial)
        self.configure_recipe(initial["selection"]["selected"])
        module = self.source / "native_session.py"
        module.write_bytes(
            module.read_bytes()
            + b'\ndef inspect_bundle(*args):\n    raise ValueError("synthetic old schema")\n'
        )
        self.upgrade_candidate()
        plan = self.plan(config=False)
        current = (self.root / "selection.json").read_bytes()
        tools = (self.root / "tools/selection.json").read_bytes()
        self.assertGreaterEqual(len(plan["selection"]["compatible_bundles"]), 2)
        with self.assertRaisesRegex(ValueError, "synthetic old schema"):
            self.apply(plan)
        self.assertEqual((self.root / "selection.json").read_bytes(), current)
        self.assertEqual((self.root / "tools/selection.json").read_bytes(), tools)

    def test_custom_root_relative_xdg_and_missing_config_are_refused(self):
        with self.assertRaisesRegex(ValueError, "requires --config"):
            self.plan(config=False)
        with self.assertRaisesRegex(ValueError, "default XDG"):
            native_package.adopt_plan(
                self.directory / "other",
                self.fixture.candidate,
                self.fixture.fixture.config,
                registered_entry=self.registered,
            )
        with (
            patch.dict(os.environ, {"XDG_DATA_HOME": "relative"}),
            self.assertRaisesRegex(ValueError, "absolute"),
        ):
            self.plan()
        self.assertFalse(self.home.exists())

    def test_schema2_never_accepts_mutable_system_package_or_modified_snapshot(self):
        plan = self.plan()
        self.apply(plan)
        record = self.runtime(plan)
        wrong = record | {"package": "/usr/lib/python3.14/site-packages/niri_fx"}
        with self.assertRaisesRegex(ValueError, "location"):
            native_tools_launcher.verify_runtime(wrong)
        with self.assertRaisesRegex(ValueError, "interpreter"):
            native_tools_launcher.verify_runtime(record | {"python": "/usr/bin/python3.14"})
        added = Path(record["package"]) / "added.py"
        added.write_text("pass\n")
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            native_tools_launcher.verify_runtime(record)
        added.unlink()
        cache = Path(record["package"]) / "__pycache__/__init__.cpython-test.pyc"
        cache.parent.mkdir()
        cache.write_bytes(b"untracked executable bytecode")
        with self.assertRaisesRegex(ValueError, "bytecode caches"):
            native_tools_launcher.verify_runtime(record)
        with (
            patch("subprocess.run") as command,
            self.assertRaisesRegex(ValueError, "bytecode caches"),
        ):
            native_tools._record(
                self.root, plan["selection"]["tools_runtime"], [plan["selection"]["selected"]]
            )
        command.assert_not_called()
        cache.unlink()
        source = Path(record["package"]) / "__init__.py"
        source.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "private"):
            native_tools_launcher.verify_runtime(record)

    def test_generic_dispatcher_unprepared_or_modified_assets_cannot_start(self):
        with (
            self.assertRaises(FileNotFoundError),
            patch.object(package_session.os, "execv") as execute,
        ):
            package_session.main([])
        execute.assert_not_called()
        self.assertFalse(self.home.exists())
        self.apply(self.plan())
        launcher = self.root / "tools/launch.py"
        launcher.write_bytes(launcher.read_bytes() + b"# external edit\n")
        with (
            self.assertRaisesRegex(ValueError, "dispatcher changed"),
            patch.object(package_session.os, "execv") as execute,
        ):
            package_session.main([])
        execute.assert_not_called()

    def test_source_symlink_or_native_extension_refuses(self):
        link = self.source / "linked.py"
        link.symlink_to(self.source / "__init__.py")
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.plan()
        link.unlink()
        (self.source / "native.so").write_bytes(b"synthetic native extension")
        with self.assertRaisesRegex(ValueError, "pure-Python"):
            self.plan()

    def test_fresh_and_update_adoption_require_all_four_patches(self):
        fixture = self.fixture.fixture
        original = copy.deepcopy(fixture.record)

        def old_stack():
            record = copy.deepcopy(original)
            record.pop("swap_patch_sha256")
            inputs = record["native_build"]["inputs"]
            inputs["patches"].pop()
            record["native_build"]["build_id"] = native_build.fingerprint(inputs)
            fixture.manifest_path.write_text(json.dumps(record))

        old_stack()
        with self.assertRaisesRegex(ValueError, "four-patch"):
            self.plan()
        self.assertFalse(self.root.exists())
        fixture.save_record()
        initial = self.plan()
        self.apply(initial)
        old_stack()
        with self.assertRaisesRegex(ValueError, "four-patch"):
            self.plan(config=False)
        self.assertEqual(
            native_session.load_selection(self.root)["selected"], initial["selection"]["selected"]
        )

    def test_existing_owned_dispatcher_is_upgraded_before_schema2_selection(self):
        fixture = test_native_tools.NativeToolsTests(methodName="runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.activate()
        registered_before = fixture.registered.read_bytes()
        # Use the established tools fixture's exact registered ownership and
        # retained venvs, but the real package snapshot and generic entry.
        original = copy.deepcopy(native_tools._read_selection(fixture.root)[0])
        launcher = fixture.root / "tools/launch.py"
        legacy_source = launcher.read_bytes() + b"\n# synthetic previous dispatcher\n"
        launcher.write_bytes(legacy_source)
        original["assets"]["launch.py"] = hashlib.sha256(legacy_source).hexdigest()
        (fixture.root / "tools/selection.json").write_text(json.dumps(original))
        base = {
            "selection": {"selected": "c" * 64, "previous": "a" * 64, "bundle_id": "c" * 64},
            "changes": [
                setup.change(
                    fixture.root / "selection.json",
                    native_session._json_bytes(
                        {"schema": 1, "selected": "c" * 64, "previous": "a" * 64}
                    ),
                )
            ],
            "observed": [],
            "notes": [],
            "validation_config": None,
            "validation_binary": None,
        }
        module = types.ModuleType("niri_fx.native_upgrade")
        module.upgrade_plan = lambda root, candidate: base
        with (
            patch.object(package_session, "default_root", return_value=fixture.root),
            patch.dict("sys.modules", {"niri_fx.native_upgrade": module}),
        ):
            plan = native_package.adopt_plan(
                fixture.root, self.fixture.candidate, registered_entry=self.registered
            )
        targets = [Path(item["target"]) for item in plan["changes"]]
        self.assertLess(
            targets.index(launcher), targets.index(fixture.root / "tools/selection.json")
        )
        self.interrupt_before(plan, fixture.root / "tools/selection.json")
        with self.assertRaisesRegex(ValueError, "launcher changed"):
            native_tools._read_selection(fixture.root)
        with (
            patch.object(package_session, "default_root", return_value=fixture.root),
            patch.dict("sys.modules", {"niri_fx.native_upgrade": module}),
        ):
            resumed = native_package.adopt_plan(
                fixture.root, self.fixture.candidate, registered_entry=self.registered
            )
            # This fixture's bundle/venv identities are synthetic; real source
            # compatibility is covered by the frozen/shared adoption tests.
            with patch.object(native_package, "_validate_source"):
                native_package.apply_adoption(
                    resumed, fixture.root, setup.plan_fingerprint(resumed)
                )
        selected = native_tools._read_selection(fixture.root)[0]
        self.assertEqual(selected["previous"], original["current"])
        self.assertEqual(selected["bootstrap"], original["bootstrap"])
        self.assertEqual(selected["registered_entry"], str(self.registered))
        self.assertNotEqual(launcher.read_bytes(), legacy_source)
        self.assertEqual(fixture.registered.read_bytes(), registered_before)


if __name__ == "__main__":
    unittest.main()
