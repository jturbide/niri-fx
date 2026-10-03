import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from niri_fx.picker import picker_checks
from niri_fx.setup import doctor
from niri_fx.terminal import print_diagnostics

UNKNOWN_MOVEMENT = {
    "binary": None,
    "status": "unknown",
    "detail": "Unavailable",
    "session": {"detail": "Offline"},
}


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        probe = patch("niri_fx.capabilities.movement_capability", return_value=UNKNOWN_MOVEMENT)
        self.movement = probe.start()
        self.addCleanup(probe.stop)

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
        self.assertEqual(report["movement_capability"]["status"], "unknown")
        lines = []
        print_diagnostics(report, lines.append)
        self.assertIn(report["movement"], lines)

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

    def test_explicit_movement_binary_does_not_replace_stock_config_validator(self):
        from niri_fx.cli import parser

        args = parser().parse_args(["doctor", "--movement-binary", "/trusted/niri"])
        with (
            patch("niri_fx.setup.shutil.which", return_value=None),
            patch("niri_fx.setup.validate_config") as validate,
            patch("niri_fx.setup.read_shell_presets", return_value={}),
            patch.dict("os.environ", {"NIRI_SOCKET": "/test/session.sock"}),
        ):
            doctor(args)
        validate.assert_called_once_with(args.config)
        self.movement.assert_called_once_with(
            Path("/trusted/niri"), socket_path="/test/session.sock"
        )


if __name__ == "__main__":
    unittest.main()
