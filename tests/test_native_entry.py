"""Login-entry preparation never registers a system session or starts services."""

import contextlib
import io
import json
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from niri_fx import native_entry
from niri_fx.cli import main
from niri_fx.setup import apply_plan, plan_fingerprint


class NativeEntryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="native-entry-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.selection = self.root / "selection.json"
        self.selection.write_text(json.dumps({"schema": 1, "selected": "a" * 64}))
        self.selection.chmod(0o600)
        self.inspect = patch.object(native_entry, "inspect_bundle", return_value={"observed": []})
        self.inspect.start()
        self.addCleanup(self.inspect.stop)

    def test_review_apply_and_idempotence(self):
        plan = native_entry.entry_plan(self.root)
        self.assertFalse((self.root / "session").exists())
        self.assertEqual(len(plan["changes"]), 2)
        apply_plan(plan, self.root / "state", plan_fingerprint(plan))
        self.assertIn("DesktopNames=niri", (self.root / "session/niri-fx.desktop").read_text())
        self.assertIn("'launch'", (self.root / "session/launch.py").read_text())
        self.assertEqual(native_entry.entry_plan(self.root)["changes"], [])

    def test_changed_selection_invalidates_review(self):
        plan = native_entry.entry_plan(self.root)
        self.selection.write_text(json.dumps({"schema": 1, "selected": "b" * 64}))
        with self.assertRaisesRegex(ValueError, "changed"):
            apply_plan(plan, self.root / "state")
        self.assertFalse((self.root / "session").exists())

    def test_changed_launcher_and_symlink_are_preserved(self):
        plan = native_entry.entry_plan(self.root)
        apply_plan(plan, self.root / "state")
        launcher = self.root / "session/launch.py"
        launcher.write_text("personal content")
        with self.assertRaisesRegex(ValueError, "differs"):
            native_entry.entry_plan(self.root)
        self.assertEqual(launcher.read_text(), "personal content")
        launcher.unlink()
        launcher.symlink_to(self.selection)
        with self.assertRaisesRegex(ValueError, "symlink"):
            native_entry.entry_plan(self.root)

    def test_exec_arguments_use_tokens_safe_for_desktop_and_sddm(self):
        value = "/tmp/niri-fx_1.0+test:@/python"
        self.assertEqual(native_entry._exec_argument(value), value)
        for value in (
            "",
            "path with spaces",
            'quote"',
            "quote'",
            "backslash\\",
            "%f",
            "$HOME",
            "`command`",
            "a;b",
            "*",
            "?",
            "[ab]",
            "(a)",
            "a>b",
            "a<b",
            "a|b",
            "a&b",
            "#a",
            "~a",
            "a=b",
            "café",
        ):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "SDDM"):
                native_entry._exec_argument(value)
        with self.assertRaisesRegex(ValueError, "control"):
            native_entry._exec_argument("bad\npath")

    def test_unsafe_launcher_or_python_path_refuses_without_writes(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        for name in ("native storage", "native%f", 'native"quoted', "native[glob]"):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "SDDM"):
                native_entry.entry_files(self.root / name)
        with (
            patch.object(native_entry.sys, "executable", "/synthetic/python install/bin/python"),
            self.assertRaisesRegex(ValueError, "SDDM"),
        ):
            native_entry.entry_files(self.root)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        self.assertEqual(list(self.root.iterdir()), [self.selection])

    def test_generated_entry_runs_through_desktop_and_sddm_parsers(self):
        # Load a harmless package instead of native_login. Package paths are
        # Python literals, so they can still contain characters forbidden in Exec.
        package = self.root / "package with spaces %$'\\" / "niri_fx"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("")
        (package / "native_login.py").write_text(
            "import json\ndef main(args):\n    print(json.dumps(args))\n    return 0\n"
        )
        with patch.object(native_entry, "__file__", str(package / "native_entry.py")):
            plan = native_entry.entry_plan(self.root)
        apply_plan(plan, self.root / "state")
        entry = (self.root / "session/niri-fx.desktop").read_text()
        command = next(line[5:] for line in entry.splitlines() if line.startswith("Exec="))
        self.assertEqual(shlex.split(command), command.split())

        # Mirror SDDM's bash/zsh dispatch without reading system or user profiles.
        shell = self.root / "bash"
        shell.write_text('#!/bin/sh\n[ "$1" = --login ] || exit 91\nshift\nexec /bin/sh "$@"\n')
        shell.chmod(0o700)
        dispatch = "exec $SHELL --login -c 'exec \"$@\"' - $@"
        env = {"HOME": str(self.root), "SHELL": str(shell), "PATH": "/usr/bin:/bin", "LANG": "C"}
        commands = {
            "desktop": shlex.split(command),
            "sddm": ["/bin/sh", "-c", dispatch, "wayland-session", command],
        }
        for parser, argv in commands.items():
            with self.subTest(parser=parser):
                result = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), ["--root", str(self.root), "launch"])

        old_command = " ".join(f'"{argument}"' for argument in command.split())
        failed = subprocess.run(
            ["/bin/sh", "-c", dispatch, "wayland-session", old_command],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(failed.returncode, 127)
        self.assertEqual(failed.stdout, "")

    def test_old_quoted_entry_requires_reviewed_repair(self):
        plan = native_entry.entry_plan(self.root)
        apply_plan(plan, self.root / "state")
        entry = self.root / "session/niri-fx.desktop"
        lines = entry.read_text().splitlines()
        for index, line in enumerate(lines):
            if line.startswith("Exec="):
                lines[index] = "Exec=" + " ".join(f'"{word}"' for word in line[5:].split())
        old = "\n".join(lines) + "\n"
        entry.write_text(old)
        with self.assertRaisesRegex(ValueError, "differs; preserving it for review"):
            native_entry.entry_plan(self.root)
        self.assertEqual(entry.read_text(), old)

    def test_permission_change_invalidates_review(self):
        plan = native_entry.entry_plan(self.root)
        self.selection.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "permissions changed"):
            apply_plan(plan, self.root / "state")
        self.assertFalse((self.root / "session").exists())

    def test_custom_session_name_is_reviewed_and_cannot_inject_keys(self):
        plan = native_entry.entry_plan(self.root, "NiriFX (managed test)")
        self.assertEqual(plan["selection"]["name"], "NiriFX (managed test)")
        self.assertIn(b"Name=NiriFX (managed test)\n", plan["changes"][1]["after"])
        for value in ("", "x" * 81, "Bad\nExec=bad", "Bad\tName"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "Session name"):
                native_entry.entry_plan(self.root, value)

    def test_cli_requires_apply_for_fingerprint_and_explains_no_selection(self):
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(
                main(["native", "rollback", "--root", str(self.root), "--expect-plan", "abc"]),
                2,
            )
        self.assertIn("requires --apply", errors.getvalue())
        self.selection.write_text(json.dumps({"schema": 1, "selected": "a" * 64, "previous": None}))
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["native", "rollback", "--root", str(self.root)]), 0)
        self.assertIn("Choose stock Niri", json.loads(output.getvalue())["next_step"])

    def test_cli_default_is_review_and_status_does_not_create_root(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["native", "session-entry", "--root", str(self.root)]), 0)
        self.assertTrue(json.loads(output.getvalue())["dry_run"])
        self.assertFalse((self.root / "session").exists())
        empty = self.root / "empty"
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["native", "status", "--offline", "--root", str(empty)]), 0)
        self.assertEqual(json.loads(output.getvalue())["bundles"], [])
        self.assertFalse(empty.exists())

    def test_status_uses_advertised_socket_unless_offline(self):
        for offline in (False, True):
            with (
                self.subTest(offline=offline),
                patch.dict(os.environ, {"NIRI_SOCKET": "/example/niri.sock"}),
                patch("niri_fx.native_session.status", return_value={}) as inspect,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                args = ["native", "status", "--root", str(self.root)]
                self.assertEqual(main(args + (["--offline"] if offline else [])), 0)
                inspect.assert_called_once_with(
                    self.root, socket_path=None if offline else "/example/niri.sock"
                )


if __name__ == "__main__":
    unittest.main()
