import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from niri_fx.picker import picker_checks
from niri_fx.setup import doctor


class DiagnosticsTests(unittest.TestCase):
    def test_absent_optional_interfaces_do_not_require_installation(self):
        with patch("niri_fx.picker.shutil.which", return_value=None):
            checks = picker_checks()
        self.assertTrue(all(c["ok"] is None and not c["available"] for c in checks))
        self.assertIn("optional", checks[0]["detail"])

    def test_gtk_version_gate_and_failed_probes(self):
        for version, available in (
            ("4.8.3", False),
            ("4.10.0", True),
            ("4.22.5", True),
            ("bad", False),
        ):
            with (
                self.subTest(version=version),
                patch(
                    "niri_fx.picker.shutil.which",
                    side_effect=lambda name: "/bin/gjs" if name == "gjs" else None,
                ),
                patch(
                    "niri_fx.picker.subprocess.run",
                    return_value=subprocess.CompletedProcess([], 0, version, ""),
                ) as run,
            ):
                gtk = picker_checks()[1]
                self.assertEqual(gtk["available"], available)
                self.assertIsNone(gtk["ok"])
                self.assertEqual(run.call_args.kwargs["timeout"], 5)
        with (
            patch("niri_fx.picker.shutil.which", return_value="/bin/missing"),
            patch(
                "niri_fx.picker.subprocess.run", side_effect=subprocess.TimeoutExpired("probe", 5)
            ),
        ):
            self.assertTrue(all(not c["available"] for c in picker_checks()))

    def test_optional_tools_do_not_make_core_diagnostics_unhealthy(self):
        with tempfile.TemporaryDirectory() as directory:
            args = Namespace(
                config=Path(directory) / "config.kdl", inir_root=Path(directory) / "shell"
            )
            with (
                patch(
                    "niri_fx.setup.shutil.which",
                    side_effect=lambda name: "/bin/niri" if name == "niri" else None,
                ),
                patch("niri_fx.setup.subprocess.check_output", return_value="niri 26.04"),
                patch("niri_fx.setup.validate_config"),
            ):
                report = doctor(args)
        self.assertTrue(report["healthy"])
        self.assertTrue(all(not c["available"] for c in report["checks"] if "available" in c))

    def test_failed_niri_version_is_reported_instead_of_aborting_diagnostics(self):
        with tempfile.TemporaryDirectory() as directory:
            args = Namespace(
                config=Path(directory) / "config.kdl", inir_root=Path(directory) / "shell"
            )
            with (
                patch("niri_fx.setup.shutil.which", return_value="/bin/niri"),
                patch(
                    "niri_fx.setup.subprocess.check_output",
                    side_effect=subprocess.TimeoutExpired("niri", 10),
                ),
                patch("niri_fx.setup.validate_config"),
                patch("niri_fx.picker.picker_checks", return_value=[]),
            ):
                report = doctor(args)
        self.assertFalse(report["healthy"])
        self.assertIn("Could not query Niri", report["checks"][0]["detail"])


if __name__ == "__main__":
    unittest.main()
