"""Owned tool-runtime upgrades keep CLI, Studio and login dispatch together."""

import contextlib
import copy
import io
import json
import subprocess
import sys
import tempfile
import unittest
import venv
from pathlib import Path
from unittest.mock import patch

from niri_fx import branding, native_entry, native_tools, native_tools_launcher, setup
from niri_fx.cli import main
from niri_fx.storage import digest

PYTHON = sys.executable


class NativeToolsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="native-tools-")
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.root = self.home / "native"
        self.root.mkdir()
        self.selected = self.root / "selection.json"
        self.selected.write_text(
            json.dumps({"schema": 1, "selected": "a" * 64, "previous": "b" * 64})
        )
        self.selected.chmod(0o600)
        self.old = self.runtime("old")
        self.new = self.runtime("new")
        self.runtimes = {record["python"]: record for record in (self.old, self.new)}
        self.probes = []
        self.package_hints = []
        self.compatible = True
        self.cli = self.home / "bin/niri-fx"
        self.cli.parent.mkdir()
        self.cli.symlink_to(Path(self.old["python"]).parent / "niri-fx")
        self.desktop = self.home / "applications/niri-fx-studio.desktop"
        self.desktop.parent.mkdir()
        self.desktop.write_text(self.old["desktop"])
        self.registered = self.home / "wayland-sessions/niri-fx.desktop"
        self.registered.parent.mkdir()
        with (
            patch.object(native_entry.sys, "executable", self.old["python"]),
            patch.object(
                native_entry, "__file__", str(Path(self.old["package"]) / "native_entry.py")
            ),
        ):
            plan = native_entry.entry_files(self.root)
        setup.apply_plan(plan, self.root / "state/selection")
        self.registered.write_bytes((self.root / "session/niri-fx.desktop").read_bytes())
        self.registered.chmod(0o644)
        self.legacy_bytes = (self.root / "session/launch.py").read_bytes()
        self.real_probe = native_tools._probe
        self.patch_probe = patch.object(native_tools, "_probe", side_effect=self.probe)
        self.patch_probe.start()
        self.addCleanup(self.patch_probe.stop)
        self.patch_inspect = patch.object(
            native_tools.native_session, "inspect_bundle", side_effect=self.inspect
        )
        self.patch_inspect.start()
        self.addCleanup(self.patch_inspect.stop)
        self.python = patch.object(native_tools.sys, "executable", self.new["python"])
        self.python.start()
        self.addCleanup(self.python.stop)

    def runtime(self, name):
        prefix = self.home / name
        package = prefix / "lib/niri_fx"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text(f"__version__ = {name!r}\n")
        python = prefix / "bin/python"
        python.parent.mkdir()
        python.write_bytes(f"synthetic {name} interpreter, never executed\n".encode())
        python.chmod(0o755)
        (prefix / "pyvenv.cfg").write_text("synthetic venv\n")
        (prefix / "bin/niri-fx").write_text("original console script\n")
        with (
            patch.object(branding.sys, "executable", str(python)),
            patch.object(branding, "__file__", str(package / "branding.py")),
        ):
            desktop = branding.desktop_entry().decode()
        files = {
            str(p): digest(p.read_bytes()) for p in (prefix / "pyvenv.cfg", package / "__init__.py")
        }
        return {
            "schema": 1,
            "python": str(python),
            "package": str(package),
            "version": name,
            "files": files,
            "desktop": desktop,
        }

    def probe(self, python, root, identifiers, *, package_path=None):
        self.probes.append((str(python), tuple(identifiers)))
        self.package_hints.append((str(python), package_path))
        if not self.compatible and str(python) == self.old["python"]:
            raise ValueError("old runtime incompatible with bundle schema")
        return copy.deepcopy(self.runtimes[str(python)])

    def inspect(self, root, identifier):
        result = {"bundle_id": identifier, "observed": []}
        if identifier == "a" * 64:
            result["customization"] = {"baseline_bundle": "c" * 64}
        return result

    def plan(self, *, bootstrap=True, **values):
        return native_tools.update_plan(
            self.root,
            bootstrap_runtime=Path(self.old["python"]).parent.parent if bootstrap else None,
            registered_entry=self.registered,
            cli_path=self.cli,
            desktop_path=self.desktop,
            **values,
        )

    def apply(self, plan):
        return native_tools.apply_tools(plan, self.root, setup.plan_fingerprint(plan))

    def prepare(self):
        plan = self.plan()
        self.apply(plan)
        return plan

    def register(self):
        self.registered.write_bytes((self.root / "tools/niri-fx.desktop").read_bytes())

    def activate(self):
        self.prepare()
        self.register()
        plan = self.plan(bootstrap=False)
        self.apply(plan)
        return plan

    def test_prepare_is_reviewed_idempotent_and_does_not_edit_existing_launchers(self):
        before = self.cli.readlink(), self.desktop.read_bytes(), self.registered.read_bytes()
        plan = self.plan()
        self.assertFalse((self.root / "tools").exists())
        self.assertEqual(plan["selection"]["phase"], "prepared")
        self.assertEqual(plan["selection"]["current"], native_tools_launcher.fingerprint(self.old))
        self.assertTrue(
            all(Path(c["logical"]).is_relative_to(self.root / "tools") for c in plan["changes"])
        )
        self.apply(plan)
        self.assertEqual(
            before, (self.cli.readlink(), self.desktop.read_bytes(), self.registered.read_bytes())
        )
        self.assertEqual(self.plan()["changes"], [])
        self.assertEqual(self.legacy_bytes, (self.root / "session/launch.py").read_bytes())
        self.assertTrue(all(set(ids) == {"a" * 64, "b" * 64, "c" * 64} for _, ids in self.probes))

    def test_first_preparation_requires_explicit_bootstrap_and_fingerprint(self):
        with self.assertRaisesRegex(ValueError, "bootstrap-runtime"):
            self.plan(bootstrap=False)
        plan = self.plan()
        with self.assertRaisesRegex(ValueError, "expect-plan"):
            native_tools.apply_tools(plan, self.root, None)
        with self.assertRaisesRegex(ValueError, "plan changed"):
            native_tools.apply_tools(plan, self.root, "wrong")
        self.assertFalse((self.root / "tools").exists())

    def test_activation_waits_for_registration_and_switches_selector_last(self):
        self.prepare()
        self.assertEqual(self.plan()["selection"]["phase"], "prepared")
        self.register()
        plan = self.plan(bootstrap=False)
        self.assertEqual(plan["selection"]["phase"], "active")
        self.assertEqual(Path(plan["changes"][-1]["logical"]), self.root / "tools/selection.json")
        self.apply(plan)
        self.assertEqual(self.cli.readlink(), self.root / "tools/niri-fx")
        self.assertEqual(
            self.desktop.read_bytes(), (self.root / "tools/studio.desktop").read_bytes()
        )
        self.assertEqual(self.plan(bootstrap=False)["changes"], [])
        self.assertEqual(self.legacy_bytes, (self.root / "session/launch.py").read_bytes())
        self.assertEqual(
            (Path(self.old["python"]).parent / "niri-fx").read_text(), "original console script\n"
        )

    def test_mixed_legacy_runtimes_require_explicit_ownership(self):
        third = self.runtime("legacy-tools")
        self.runtimes[third["python"]] = third
        self.cli.unlink()
        self.cli.symlink_to(Path(third["python"]).parent / "niri-fx")
        self.desktop.write_text(
            third["desktop"].replace(" -m niri_fx studio", " -I -m niri_fx studio")
        )
        with self.assertRaisesRegex(ValueError, "CLI launcher differs"):
            self.plan()
        plan = self.plan(legacy_tools_runtime=Path(third["python"]).parent.parent)
        self.apply(plan)
        self.register()
        self.apply(self.plan(bootstrap=False))
        self.assertEqual(self.cli.readlink(), self.root / "tools/niri-fx")

    def test_selector_bundle_registration_and_external_edits_invalidate_review(self):
        for target in ("selector", "registration", "desktop", "cli", "runtime"):
            with self.subTest(target=target):
                plan = self.plan()
                path = {
                    "selector": self.selected,
                    "registration": self.registered,
                    "desktop": self.desktop,
                    "runtime": Path(self.new["package"]) / "__init__.py",
                }.get(target)
                if target == "cli":
                    original = self.cli.readlink()
                    self.cli.unlink()
                    self.cli.symlink_to(self.home / "foreign")
                else:
                    original = path.read_bytes()
                    path.write_bytes(b"external change\n")
                with self.assertRaisesRegex(ValueError, "changed"):
                    self.apply(plan)
                if target == "cli":
                    self.cli.unlink()
                    self.cli.symlink_to(original)
                else:
                    path.write_bytes(original)
                self.assertFalse((self.root / "tools").exists())

    def test_unknown_launcher_bytes_or_regular_cli_are_preserved(self):
        self.desktop.write_text("personal launcher")
        with self.assertRaisesRegex(ValueError, "Studio launcher differs"):
            self.plan()
        self.desktop.write_text(self.old["desktop"])
        self.cli.unlink()
        self.cli.write_text("personal command")
        with self.assertRaisesRegex(ValueError, "non-symlink"):
            self.plan()
        self.assertFalse((self.root / "tools").exists())

    def test_runtime_removal_file_addition_and_content_change_are_detected(self):
        self.prepare()
        record = native_tools_launcher.runtime_record(
            self.root / "tools", native_tools_launcher.fingerprint(self.old)
        )
        extra = Path(self.old["package"]) / "extra.py"
        extra.write_text("added module")
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            native_tools_launcher.verify_runtime(record)
        extra.unlink()
        target = Path(self.old["package"]) / "__init__.py"
        target.write_text("changed module")
        with self.assertRaisesRegex(ValueError, "runtime changed"):
            native_tools_launcher.verify_runtime(record)
        target.unlink()
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            native_tools_launcher.verify_runtime(record)

    def test_rollback_rechecks_compatibility_and_preserves_runtimes_and_assets(self):
        self.activate()
        paths = {p: p.read_bytes() for p in (self.root / "tools/runtimes").glob("*.json")}
        self.compatible = False
        with self.assertRaisesRegex(ValueError, "incompatible"):
            native_tools.rollback_plan(self.root, registered_entry=self.registered)
        self.compatible = True
        plan = native_tools.rollback_plan(self.root, registered_entry=self.registered)
        self.assertEqual(
            [Path(c["logical"]) for c in plan["changes"]], [self.root / "tools/selection.json"]
        )
        self.apply(plan)
        self.assertEqual(
            native_tools.status(self.root)["current"], native_tools_launcher.fingerprint(self.old)
        )
        self.assertEqual(paths, {p: p.read_bytes() for p in paths})

    def test_future_candidate_branding_does_not_replace_stable_layout(self):
        self.activate()
        self.newer = self.runtime("newer")
        self.runtimes[self.newer["python"]] = self.newer
        with (
            patch.object(native_tools.sys, "executable", self.newer["python"]),
            patch.object(native_tools, "KEYWORDS", ("new-branding",)),
        ):
            plan = self.plan(bootstrap=False)
        self.assertEqual(len(plan["changes"]), 2)
        self.assertTrue(
            all(
                Path(c["logical"]).name == "selection.json"
                or Path(c["logical"]).parent.name == "runtimes"
                for c in plan["changes"]
            )
        )

    def test_status_does_not_probe_or_write_and_reports_missing_runtime(self):
        missing = self.home / "absent"
        self.prepare()
        with patch.object(native_tools, "_probe") as command:
            self.assertFalse(native_tools.status(missing)["installed"])
            self.assertFalse(missing.exists())
            result = native_tools.status(self.root)
            self.assertFalse(result["registered"])
            command.assert_not_called()
        Path(self.old["python"]).unlink()
        self.assertEqual(native_tools.status(self.root)["runtimes"][0]["status"], "unavailable")

    def test_native_entry_reuses_managed_launcher_and_refuses_new_runtime_pin(self):
        self.activate()
        plan = native_entry.entry_files(self.root)
        self.assertEqual(plan["changes"], [])
        self.assertEqual(plan["selection"]["entry"], str(self.root / "tools/niri-fx.desktop"))
        with (
            patch.object(native_tools.sys, "executable", self.old["python"]),
            self.assertRaisesRegex(ValueError, "selected tools runtime"),
        ):
            native_entry.entry_files(self.root)

    def test_generic_restore_cannot_bypass_tools_compatibility(self):
        result = self.apply(self.plan())
        with self.assertRaisesRegex(ValueError, "tools.*rollback"):
            setup.restore(self.root / "state/selection", result["transaction"], apply=True)

    def test_cli_review_prepare_activate_status_and_rollback(self):
        arguments = [
            "native",
            "tools-update",
            "--root",
            str(self.root),
            "--bootstrap-runtime",
            str(Path(self.old["python"]).parent.parent),
            "--registered-entry",
            str(self.registered),
            "--cli-path",
            str(self.cli),
            "--desktop-path",
            str(self.desktop),
        ]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(arguments), 0)
        fingerprint = json.loads(output.getvalue())["plan_sha256"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(arguments + ["--apply", "--expect-plan", fingerprint]), 0)
        self.register()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(arguments), 0)
        fingerprint = json.loads(output.getvalue())["plan_sha256"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(arguments + ["--apply", "--expect-plan", fingerprint]), 0)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["native", "tools-status", "--root", str(self.root)]), 0)
        self.assertEqual(json.loads(output.getvalue())["phase"], "active")
        arguments = [
            "native",
            "tools-rollback",
            "--root",
            str(self.root),
            "--registered-entry",
            str(self.registered),
        ]
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(arguments), 0)
        fingerprint = json.loads(output.getvalue())["plan_sha256"]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(arguments + ["--apply", "--expect-plan", fingerprint]), 0)

    def test_dispatcher_uses_same_runtime_for_cli_studio_and_login(self):
        self.activate()
        for action, suffix in (
            ("cli", ["list"]),
            ("studio", ["studio", "--native-root", str(self.root)]),
            ("session", ["--root", str(self.root), "launch"]),
        ):
            with (
                self.subTest(action=action),
                patch.object(native_tools_launcher, "__file__", str(self.root / "tools/launch.py")),
                patch.object(native_tools_launcher.os, "execv") as execute,
            ):
                native_tools_launcher.main([action] + (["list"] if action == "cli" else []))
                python, command = execute.call_args.args
                self.assertEqual(python, self.new["python"])
                self.assertEqual(command[:4], [python, "-I", "-B", "-c"])
                self.assertIn(
                    "from niri_fx.native_login" if action == "session" else "from niri_fx.cli",
                    command[4],
                )
                self.assertEqual(command[5:], [str(Path(self.new["package"]).parent), *suffix])

    def test_missing_or_nonfile_interpreter_refuses_without_selecting_fallback(self):
        self.activate()
        selected = (self.root / "tools/selection.json").read_bytes()
        compositor = self.selected.read_bytes()
        python = Path(self.new["python"])
        python.unlink()
        for directory in (False, True):
            if directory:
                python.mkdir()
            with (
                self.subTest(directory=directory),
                patch.object(native_tools_launcher, "__file__", str(self.root / "tools/launch.py")),
                patch.object(native_tools_launcher.os, "execv") as execute,
                self.assertRaisesRegex(ValueError, "interpreter is unavailable.*repair Python"),
            ):
                native_tools_launcher.main(["session"])
            execute.assert_not_called()
            self.assertEqual((self.root / "tools/selection.json").read_bytes(), selected)
            self.assertEqual(self.selected.read_bytes(), compositor)

    def test_interpreter_exec_failure_preserves_selection_and_names_recovery(self):
        self.activate()
        selected = (self.root / "tools/selection.json").read_bytes()
        with (
            patch.object(native_tools_launcher, "__file__", str(self.root / "tools/launch.py")),
            patch.object(
                native_tools_launcher.os,
                "execv",
                side_effect=FileNotFoundError("missing interpreter loader"),
            ) as execute,
            self.assertRaisesRegex(ValueError, "interpreter could not start.*native adopt"),
        ):
            native_tools_launcher.main(["cli", "--version"])
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(execute.call_args.args[0], self.new["python"])
        self.assertEqual((self.root / "tools/selection.json").read_bytes(), selected)

    def test_bootstrap_import_and_unsupported_python_failures_have_recovery_without_traceback(self):
        self.activate()
        selected = (self.root / "tools/selection.json").read_bytes()
        compositor = self.selected.read_bytes()
        for unsupported in (False, True):
            with (
                self.subTest(unsupported=unsupported),
                patch.object(native_tools_launcher, "__file__", str(self.root / "tools/launch.py")),
                patch.object(native_tools_launcher.os, "execv") as execute,
            ):
                native_tools_launcher.main(["session"])
            command = execute.call_args.args[1]
            # The private fixture deliberately has no native_login module.
            # Simulate only the version gate; this is not a Python minor upgrade.
            if unsupported:
                command[4] = "import sys; sys.version_info = (3, 9, 0)\n" + command[4]
            result = subprocess.run(
                [PYTHON, *command[1:]], cwd=self.home, capture_output=True, text=True, timeout=10
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("NiriFX tools could not load", result.stderr)
            self.assertIn("stock Niri", result.stderr)
            self.assertIn("retained selection is unchanged", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertIn("Python 3.10" if unsupported else "native_login", result.stderr)
            self.assertEqual((self.root / "tools/selection.json").read_bytes(), selected)
            self.assertEqual(self.selected.read_bytes(), compositor)

    def test_bootstrap_executes_retained_entrypoint_outside_default_site_packages(self):
        module = Path(self.new["package"]) / "cli.py"
        module.write_text("def main():\n    print('retained private runtime')\n    return 0\n")
        self.new["files"][str(module)] = digest(module.read_bytes())
        self.activate()
        with (
            patch.object(native_tools_launcher, "__file__", str(self.root / "tools/launch.py")),
            patch.object(native_tools_launcher.os, "execv") as execute,
        ):
            native_tools_launcher.main(["cli", "--version"])
        command = execute.call_args.args[1]
        result = subprocess.run(
            [PYTHON, *command[1:]], cwd=self.home, capture_output=True, text=True, timeout=10
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "retained private runtime")
        self.assertFalse(list(Path(self.new["package"]).rglob("*.pyc")))

    def test_new_package_file_after_review_is_refused_before_writes(self):
        plan = self.plan()
        (Path(self.new["package"]) / "extra.py").write_text("new import target")
        with self.assertRaisesRegex(ValueError, "inventory changed"):
            self.apply(plan)
        self.assertFalse((self.root / "tools").exists())

    def test_failed_activation_restores_owned_links_app_and_selector(self):
        self.prepare()
        self.register()
        plan = self.plan(bootstrap=False)
        selector = self.root / "tools/selection.json"
        before = selector.read_bytes(), self.cli.readlink(), self.desktop.read_bytes()
        real_write = setup.atomic_write
        failed = False

        def write(path, data, mode=0o600):
            nonlocal failed
            if Path(path) == selector and not failed:
                failed = True
                raise OSError("simulated interrupted selector commit")
            return real_write(path, data, mode)

        with (
            patch.object(setup, "atomic_write", side_effect=write),
            self.assertRaisesRegex(OSError, "interrupted"),
        ):
            self.apply(plan)
        self.assertEqual(
            before, (selector.read_bytes(), self.cli.readlink(), self.desktop.read_bytes())
        )
        self.apply(self.plan(bootstrap=False))
        self.assertEqual(native_tools.status(self.root)["phase"], "active")

    def test_partial_preparation_can_resume_without_touching_legacy_entry(self):
        plan = self.plan()
        for item in plan["changes"][:3]:
            path = Path(item["logical"])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(item["after"])
            path.chmod(item["mode"])
        self.assertFalse((self.root / "tools/selection.json").exists())
        self.apply(self.plan())
        self.assertEqual(self.legacy_bytes, (self.root / "session/launch.py").read_bytes())
        self.assertEqual(native_tools.status(self.root)["phase"], "prepared")

    def test_idempotent_apply_still_checks_registration_and_selection(self):
        self.activate()
        plan = self.plan(bootstrap=False)
        self.assertEqual(plan["changes"], [])
        self.registered.write_text("externally replaced entry")
        with self.assertRaisesRegex(ValueError, "changed"):
            self.apply(plan)

    def test_compatible_system_python_replacement_does_not_invalidate_tools(self):
        self.activate()
        Path(self.new["python"]).write_text("compatible updated distro interpreter")
        native_tools_launcher.verify_runtime(self.new)
        self.assertEqual(native_tools.status(self.root)["runtimes"][0]["status"], "intact")
        self.assertEqual(self.plan(bootstrap=False)["changes"], [])

    def test_current_runtime_probes_bind_the_already_loaded_package_path(self):
        self.activate()
        native_entry.entry_files(self.root)
        current_hints = [
            hint for python, hint in self.package_hints if python == self.new["python"]
        ]
        self.assertTrue(current_hints)
        self.assertTrue(all(hint is not None for hint in current_hints))

    def test_isolated_probe_can_read_retained_package_after_site_directory_move(self):
        # A distro minor update changes the interpreter's default site-packages
        # directory. Retained pure-Python code remains usable through its receipt.
        prefix = self.home / "real-venv"
        venv.EnvBuilder(with_pip=False).create(prefix)
        # Never match the active interpreter's default, including Python 3.10 CI.
        package = prefix / "lib/python-retained/site-packages/niri_fx"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text('__version__ = "synthetic"\n')
        (package / "branding.py").write_text('def desktop_entry(): return b"synthetic desktop"\n')
        (package / "native_session.py").write_text(
            "def inspect_bundle(root, identifier): return {}\n"
        )
        python = prefix / "bin/python"
        with self.assertRaisesRegex(ValueError, "cannot read"):
            self.real_probe(python, self.root, [])
        result = self.real_probe(python, self.root, [], package_path=str(package))
        self.assertEqual(result["package"], str(package))
        self.assertNotIn(str(python), result["files"])
        native_tools_launcher.verify_runtime(result)

    def test_owned_asset_mode_changes_are_refused(self):
        self.prepare()
        path = self.root / "tools/niri-fx"
        path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "permissions"):
            self.plan()
        self.assertEqual(path.stat().st_mode & 0o777, 0o644)


if __name__ == "__main__":
    unittest.main()
