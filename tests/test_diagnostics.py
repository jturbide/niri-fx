import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from niri_fx.cli import parser
from niri_fx.picker import picker_checks
from niri_fx.setup import default_config, doctor
from niri_fx.terminal import print_diagnostics

UNKNOWN_MOVEMENT = {
    "binary": None,
    "status": "unknown",
    "detail": "Unavailable",
    "session": {"detail": "Offline", "contract": {"status": "unknown", "detail": "Unverified"}},
    "activation_ready": False,
}


class DiagnosticsFixture(unittest.TestCase):
    def setUp(self):
        probe = patch("niri_fx.capabilities.movement_capability", return_value=UNKNOWN_MOVEMENT)
        self.movement = probe.start()
        self.addCleanup(probe.stop)
        probe = patch("niri_fx.capabilities.pointer_capability", return_value=UNKNOWN_MOVEMENT)
        self.pointer = probe.start()
        self.addCleanup(probe.stop)
        probe = patch("niri_fx.capabilities.fragment_capability", return_value=UNKNOWN_MOVEMENT)
        self.fragment = probe.start()
        self.addCleanup(probe.stop)
        probe = patch("niri_fx.capabilities.swap_capability", return_value=UNKNOWN_MOVEMENT)
        self.swap = probe.start()
        self.addCleanup(probe.stop)
        probe = patch(
            "niri_fx.diagnostics.native_session.status",
            return_value={
                "selection": {"selected": None},
                "bundles": [],
                "running": {"status": "offline", "bundle_id": None, "detail": "No session."},
            },
        )
        self.native = probe.start()
        self.addCleanup(probe.stop)


class DiagnosticsTests(DiagnosticsFixture):
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
        self.assertEqual(report["pointer_capability"]["status"], "unknown")
        self.assertEqual(report["swap_capability"]["status"], "unknown")
        lines = []
        print_diagnostics(report, lines.append)
        self.assertIn(report["movement"], lines)
        self.assertIn("INFO health-scope: " + report["health_scope"], lines)
        self.assertIn("INFO diagnostic-scope: " + report["diagnostic_scope"]["detail"], lines)

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

    def test_explicit_binary_validates_selected_config_and_reports_its_own_version(self):
        args = parser().parse_args(["doctor", "--niri-binary", "/trusted/niri"])
        with (
            patch(
                "niri_fx.setup.shutil.which",
                side_effect=lambda requested: requested if requested == "/trusted/niri" else None,
            ),
            patch(
                "niri_fx.setup.subprocess.check_output", return_value="niri experimental"
            ) as version,
            patch("niri_fx.setup.validate_config") as validate,
            patch("niri_fx.setup.read_shell_presets", return_value={}),
            patch.dict("os.environ", {"NIRI_SOCKET": "/test/session.sock"}),
        ):
            report = doctor(args)
        validate.assert_called_once_with(default_config(), "/trusted/niri")
        self.assertEqual(version.call_args.args[0], ["/trusted/niri", "--version"])
        self.assertEqual(report["checks"][0]["detail"], "niri experimental")
        self.movement.assert_called_once_with(
            Path("/trusted/niri"), socket_path="/test/session.sock"
        )
        self.pointer.assert_called_once_with(
            Path("/trusted/niri"), socket_path="/test/session.sock"
        )


class ManagedDiagnosticsTests(DiagnosticsFixture):
    def setUp(self):
        super().setUp()
        self.running = "a" * 64
        self.selected = "b" * 64
        self.bundle = {
            "binary": "/trusted/running/bin/niri",
            "config": "/trusted/running/config.kdl",
        }
        self.native.return_value = {
            "selection": {"selected": self.selected},
            "bundles": [
                {"bundle_id": self.running, "status": "metadata-match"},
                {
                    "bundle_id": self.selected,
                    "status": "metadata-match",
                    "binary": "/must-not-run/next-login/niri",
                    "config": "/must-not-use/next-login/config.kdl",
                },
            ],
            "running": {
                "status": "matched",
                "bundle_id": self.running,
                "detail": "Retained process and startup config verified.",
                "binary": "/must-not-run/raw-ipc-path",
                "config": "/must-not-use/raw-ipc-path",
            },
        }
        for name, setting in (
            ("environment", patch.dict("os.environ", {"NIRI_SOCKET": "/synthetic/session.sock"})),
            (
                "inspection",
                patch(
                    "niri_fx.diagnostics.native_session.inspect_bundle", return_value=self.bundle
                ),
            ),
            (
                "which",
                patch(
                    "niri_fx.setup.shutil.which",
                    side_effect=lambda name: "/stock/niri" if name == "niri" else name,
                ),
            ),
            ("version", patch("niri_fx.setup.subprocess.check_output", return_value="niri test")),
            ("validate", patch("niri_fx.setup.validate_config")),
            ("picker", patch("niri_fx.picker.picker_checks", return_value=[])),
            ("shell", patch("niri_fx.setup.read_shell_presets", return_value={})),
        ):
            setattr(self, name, setting.start())
            self.addCleanup(setting.stop)

    def test_default_doctor_uses_running_bundle_instead_of_stock_or_next_login(self):
        report = doctor(parser().parse_args(["doctor"]))
        self.assertEqual(report["diagnostic_scope"]["mode"], "managed-running")
        self.assertEqual(report["diagnostic_scope"]["config"], self.bundle["config"])
        self.assertEqual(report["native_session"]["running"]["bundle_id"], self.running)
        self.assertEqual(report["native_session"]["next_login"]["bundle_id"], self.selected)
        self.assertEqual(self.inspection.call_args.args[1], self.running)
        self.assertEqual(self.version.call_args.args[0], [self.bundle["binary"], "--version"])
        self.validate.assert_called_once_with(Path(self.bundle["config"]), self.bundle["binary"])
        for capability in (self.movement, self.pointer, self.fragment, self.swap):
            capability.assert_called_once_with(
                Path(self.bundle["binary"]), socket_path="/synthetic/session.sock"
            )
        self.assertTrue(report["healthy"])
        self.assertIn("current files", report["diagnostic_scope"]["detail"])
        self.assertIn("not certify", report["health_scope"])

    def test_explicit_binary_or_config_disables_automatic_pair_substitution(self):
        for flags, binary, config in (
            (["--config", "/chosen/config.kdl"], None, Path("/chosen/config.kdl")),
            (["--config", str(default_config())], None, default_config()),
            (["--niri-binary", "/chosen/niri"], Path("/chosen/niri"), default_config()),
            (
                ["--niri-binary", "/chosen/niri", "--config", "/chosen/config.kdl"],
                Path("/chosen/niri"),
                Path("/chosen/config.kdl"),
            ),
        ):
            with self.subTest(flags=flags):
                self.validate.reset_mock()
                self.version.reset_mock()
                self.movement.reset_mock()
                report = doctor(parser().parse_args(["doctor", *flags]))
                self.assertEqual(report["diagnostic_scope"]["mode"], "explicit")
                self.assertEqual(report["native_session"]["running"]["bundle_id"], self.running)
                self.validate.assert_called_once_with(
                    config, *([str(binary)] if binary is not None else [])
                )
                self.assertEqual(
                    self.version.call_args.args[0],
                    [str(binary) if binary is not None else "/stock/niri", "--version"],
                )
                self.movement.assert_called_once_with(binary, socket_path="/synthetic/session.sock")

    def test_unverified_session_paths_are_never_selected_or_executed(self):
        for state in ("external", "unknown", "offline"):
            with self.subTest(state=state):
                self.native.return_value["running"]["status"] = state
                self.native.return_value["running"]["bundle_id"] = None
                self.inspection.reset_mock()
                self.version.reset_mock()
                self.validate.reset_mock()
                self.movement.reset_mock()
                with patch.dict(
                    "os.environ",
                    {"NIRI_SOCKET": "" if state == "offline" else "/synthetic/session.sock"},
                ):
                    report = doctor(parser().parse_args(["doctor"]))
                self.assertEqual(report["diagnostic_scope"]["mode"], "stock-default")
                self.assertEqual(report["native_session"]["running"]["status"], state)
                self.inspection.assert_not_called()
                self.assertEqual(self.version.call_args.args[0], ["/stock/niri", "--version"])
                self.validate.assert_called_once_with(default_config())
                self.assertIsNone(self.movement.call_args.args[0])

    def test_damaged_or_changed_running_bundle_never_becomes_a_probe_candidate(self):
        self.inspection.side_effect = ValueError("Bundle contents changed")
        report = doctor(parser().parse_args(["doctor"]))
        self.assertEqual(report["diagnostic_scope"]["mode"], "stock-default")
        self.assertEqual(report["native_session"]["running"]["status"], "unknown")
        self.assertIn("Bundle contents changed", report["native_session"]["running"]["detail"])
        self.assertEqual(self.version.call_args.args[0], ["/stock/niri", "--version"])
        self.validate.assert_called_once_with(default_config())
        self.movement.assert_called_once_with(None, socket_path="/synthetic/session.sock")

    def test_unavailable_next_login_does_not_replace_running_diagnostics(self):
        self.native.return_value["bundles"][1]["status"] = "unavailable"
        report = doctor(parser().parse_args(["doctor"]))
        self.assertEqual(report["diagnostic_scope"]["mode"], "managed-running")
        self.assertEqual(report["native_session"]["next_login"]["status"], "unavailable")
        self.assertIn("not run", report["native_session"]["next_login"]["detail"])
        self.assertEqual(self.version.call_args.args[0], [self.bundle["binary"], "--version"])

    def test_unsupported_swap_stays_distinct_from_an_unverified_renderer(self):
        self.swap.return_value = UNKNOWN_MOVEMENT | {
            "status": "unsupported",
            "detail": "This build does not support independent swaps.",
        }
        report = doctor(parser().parse_args(["doctor"]))
        self.assertTrue(report["healthy"])
        self.assertEqual(report["swap_capability"]["status"], "unsupported")
        self.assertEqual(report["swap_capability"]["session"]["contract"]["status"], "unknown")
        lines = []
        print_diagnostics(report, lines.append)
        self.assertTrue(any("swap-binary" in line and "does not support" in line for line in lines))
        self.assertTrue(any("swap-renderer" in line and "Unverified" in line for line in lines))

    def test_unreadable_retained_selection_keeps_default_diagnostics_available(self):
        self.native.side_effect = ValueError("Invalid selection")
        report = doctor(parser().parse_args(["doctor"]))
        self.assertEqual(report["diagnostic_scope"]["mode"], "stock-default")
        self.assertEqual(report["native_session"]["next_login"]["status"], "unknown")
        self.assertEqual(report["native_session"]["running"]["status"], "unknown")
        self.inspection.assert_not_called()
        self.assertEqual(self.version.call_args.args[0], ["/stock/niri", "--version"])


if __name__ == "__main__":
    unittest.main()
