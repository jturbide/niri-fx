import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from helpers import shell_registry

from niri_fx import terminal
from niri_fx.cli import main, parser
from niri_fx.effects import PRESETS


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / "config.kdl"
        self.original = (
            b"// Existing settings\nanimations { window-resize { duration-ms 170; }; }\n"
        )
        self.config.write_bytes(self.original)
        self.args = parser().parse_args(
            [
                "setup",
                "--interactive",
                "--no-launcher",
                "--config",
                str(self.config),
                "--state",
                str(self.root / "state"),
                "--inir-root",
                str(self.root / "shell"),
                "--registry",
                str(self.root / "registry.json"),
            ]
        )
        self.validation = patch("niri_fx.setup.validate_config")
        self.validation.start()
        self.addCleanup(self.validation.stop)
        self.output = []

    def run_guide(self, answers):
        replies = iter(answers)
        terminal.guide(self.args, lambda prompt: next(replies), self.output.append)

    def test_starter_selection_uses_existing_presets_without_resize(self):
        self.assertEqual(terminal.catalog(recommended=True)[0], "balanced")
        self.assertTrue(
            all(key in PRESETS and not PRESETS[key].resize for key in terminal.RECOMMENDED)
        )
        self.assertEqual(terminal.catalog("pixel wipe"), ["pixel-wipe"])
        self.assertTrue(
            all(PRESETS[key].family == "slices" for key in terminal.catalog(family="slices"))
        )

    def test_json_catalog_remains_compatible_and_text_is_optional(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["list"]), 0)
        self.assertEqual(set(json.loads(output.getvalue())), set(PRESETS))
        output = io.StringIO()
        with redirect_stdout(output):
            main(["list", "--text", "--search", "pixel wipe"])
        self.assertIn("pixel-wipe", output.getvalue())
        self.assertNotIn("explosion", output.getvalue())

    def test_search_selection_review_and_exact_undo(self):
        self.run_guide(["/pixel wipe", "1", "apply"])
        include = self.root / "nirifx/animations.kdl"
        self.assertTrue(include.exists())
        self.assertNotIn("window-resize", include.read_text())
        self.assertTrue(self.config.read_bytes().startswith(self.original))
        self.assertTrue(any("Applied pixel-wipe" in line for line in self.output))
        self.run_guide(["undo", "undo"])
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse(include.exists())

    def test_noop_apply_does_not_request_confirmation_or_make_snapshot(self):
        self.run_guide(["", "apply"])
        manifests = list(self.args.state.glob("*/manifest.json"))
        self.run_guide([""])
        self.assertEqual(list(self.args.state.glob("*/manifest.json")), manifests)
        self.assertIn("Already matches. No files need changing.", self.output)

    def test_profile_menu_applies_both_actions_and_undo_restores(self):
        from niri_fx.catalog import PROFILES
        from niri_fx.effects import render_kdl

        self.run_guide(["profiles", "burst-and-drift", "apply"])
        include = self.root / "nirifx/animations.kdl"
        self.assertTrue(include.read_text().endswith(render_kdl(PROFILES["burst-and-drift"])))
        self.assertNotIn("window-resize", include.read_text())
        self.run_guide(["undo", "undo"])
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse(include.exists())

    def test_cancel_at_selection_and_at_review_writes_nothing(self):
        for answers in (["q"], ["explosion", ""], ["explosion", "yes"]):
            self.run_guide(answers)
            self.assertEqual(self.config.read_bytes(), self.original)
            self.assertFalse(self.args.state.exists())
            self.assertFalse((self.root / "nirifx").exists())

    def test_invalid_selection_and_empty_search_can_recover(self):
        self.run_guide(["/no such style", "1", "all", "../../invalid", "balanced", ""])
        self.assertTrue(any("No matching" in line for line in self.output))
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_configuration_edit_during_confirmation_refuses_apply(self):
        def read(prompt):
            if prompt.startswith("Choose"):
                return "balanced"
            self.config.write_bytes(self.original + b"// External edit\n")
            return "apply"

        with self.assertRaisesRegex(ValueError, "plan changed"):
            terminal.guide(self.args, read, self.output.append)
        self.assertFalse(self.args.state.exists())
        self.assertFalse((self.root / "nirifx").exists())
        self.assertIn(b"External edit", self.config.read_bytes())

    def test_undo_refuses_external_edits(self):
        self.run_guide(["balanced", "apply"])
        changed = self.config.read_bytes() + b"// Later edit\n"
        self.config.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, "File changed"):
            self.run_guide(["undo"])
        self.assertEqual(self.config.read_bytes(), changed)

    def test_inir_registers_collection_without_activation(self):
        helper = self.args.inir_root / "scripts/niri-config.py"
        helper.parent.mkdir(parents=True)
        helper.touch()
        with patch("niri_fx.setup.read_shell_presets", return_value=shell_registry()):
            self.run_guide(["", "apply"])
        self.assertTrue(self.args.registry.exists())
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse((self.root / "nirifx").exists())
        self.assertIn("Collection added. Choose a style in iRiS.", self.output)
        self.run_guide(["undo", "undo"])
        self.assertFalse(self.args.registry.exists())

    def test_redirected_input_cannot_enter_interactive_mode(self):
        with (
            patch("sys.stdin.isatty", return_value=False),
            redirect_stderr(io.StringIO()) as output,
        ):
            self.assertEqual(main(["setup", "--interactive"]), 2)
        self.assertIn("needs a terminal", output.getvalue())
        with (
            patch("sys.stdin.isatty", return_value=False),
            redirect_stdout(io.StringIO()) as output,
        ):
            self.assertEqual(main([]), 0)
        self.assertIn("usage:", output.getvalue())

    def test_guide_rejects_advanced_overrides_and_automatic_apply(self):
        for flags in (
            ["--resize"],
            ["--particles", "200"],
            ["--apply"],
            ["--custom", "style.json"],
        ):
            with (
                patch("sys.stdin.isatty", return_value=True),
                patch("sys.stdout.isatty", return_value=True),
                patch("niri_fx.terminal.guide") as guide,
                redirect_stderr(io.StringIO()),
            ):
                self.assertEqual(main(["setup", "--interactive", *flags]), 2)
                guide.assert_not_called()

    def test_no_arguments_uses_guide_without_adding_launcher(self):
        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=True),
            patch("niri_fx.terminal.guide") as guide,
        ):
            self.assertEqual(main([]), 0)
        self.assertFalse(guide.call_args.args[0].launcher)


if __name__ == "__main__":
    unittest.main()
