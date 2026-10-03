import json
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from niri_fx import picker
from niri_fx.documents import load_document, parse_document
from niri_fx.effects import render_kdl

ROOT = Path(__file__).resolve().parents[1]


class PickerTests(unittest.TestCase):
    def test_inspect_preserves_profile_actions_without_writing(self):
        source = ROOT / "examples/profiles/frost-and-fragments.json"
        original = source.read_bytes()
        result = subprocess.run(
            [sys.executable, "-m", "niri_fx", "inspect", "--custom", str(source)],
            capture_output=True,
            text=True,
            check=True,
        )
        inspected = json.loads(result.stdout)
        self.assertEqual(
            render_kdl(parse_document(inspected)[2]),
            render_kdl(parse_document(load_document(source))[2]),
        )
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(inspected["kind"], "profile")

    def test_invalid_inspect_reports_error_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            document = Path(directory) / "invalid.json"
            document.write_text('{"schema":3,"name":"Invalid","effect":{"particles":-1}}')
            result = subprocess.run(
                [sys.executable, "-m", "niri_fx", "inspect", "--custom", str(document)],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertIn("particles", result.stderr)

    def test_launcher_uses_arrays_and_packaged_resources(self):
        args = Namespace(
            config=Path("/tmp/config with spaces.kdl"),
            state=Path("/tmp/state"),
            custom=Path("/tmp/style ; literal.json"),
        )
        with (
            patch.object(picker.shutil, "which", return_value="/usr/bin/qs"),
            patch.object(picker.subprocess, "run") as run,
        ):
            picker.launch_picker(args)
        command = run.call_args.args[0]
        self.assertEqual(
            command, ["/usr/bin/qs", "--path", str(picker.qml_directory() / "shell.qml")]
        )
        env = run.call_args.kwargs["env"]
        self.assertEqual(json.loads(env["NIRIFX_COMMAND"]), [sys.executable, "-m", "niri_fx"])
        self.assertEqual(env["NIRIFX_CUSTOM"], str(args.custom))
        self.assertTrue(run.call_args.kwargs["check"])
        for name in ("shell.qml", "NiriFXController.qml", "NiriFXPicker.qml"):
            self.assertTrue((picker.qml_directory() / name).is_file())

    def test_missing_quickshell_has_an_actionable_error(self):
        with patch.object(picker.shutil, "which", return_value=None):
            with self.assertRaisesRegex(ValueError, "requires Quickshell"):
                picker.launch_picker(Namespace())

    def test_component_location_does_not_require_quickshell(self):
        output = subprocess.check_output(
            [sys.executable, "-m", "niri_fx", "picker", "--qml-dir"], text=True
        )
        self.assertEqual(Path(output.strip()), picker.qml_directory())


if __name__ == "__main__":
    unittest.main()
