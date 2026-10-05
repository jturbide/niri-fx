"""Login-entry preparation never registers a system session or starts services."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from niri_fx import native_entry
from niri_fx.cli import main
from niri_fx.setup import apply_plan, plan_fingerprint


class NativeEntryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="native entry ")
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

    def test_exec_arguments_escape_both_desktop_layers(self):
        self.assertEqual(native_entry._exec_argument('a b%$`"\\'), '"a b%%\\\\$\\\\`\\\\"\\\\\\\\"')
        with self.assertRaisesRegex(ValueError, "control"):
            native_entry._exec_argument("bad\npath")

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
            self.assertEqual(main(["native", "status", "--root", str(empty)]), 0)
        self.assertEqual(json.loads(output.getvalue())["bundles"], [])
        self.assertFalse(empty.exists())


if __name__ == "__main__":
    unittest.main()
