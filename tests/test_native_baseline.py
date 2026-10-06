"""A baseline must be comparable and its privacy control must remain observable."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    spec = importlib.util.spec_from_file_location(
        "native_baseline", ROOT / "scripts/test-native-baseline.py"
    )
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)


class BaselineComparisonTests(unittest.TestCase):
    def test_mismatched_or_missing_build_settings_stop_comparison(self):
        expected = {
            "revision": "pinned",
            "build_profile": "release",
            "build_flags": ["--locked", "--no-default-features"],
            "rustc": "rustc test",
        }
        self.assertEqual(baseline.comparable_builds(expected, expected.copy()), expected)
        for key in expected:
            with self.subTest(key=key):
                missing = expected.copy()
                del missing[key]
                for changed in (missing, expected | {key: "different"}):
                    with self.assertRaisesRegex(RuntimeError, key):
                        baseline.comparable_builds(expected, changed)

    def test_both_targets_require_their_public_positive_control(self):
        present = {"protected": 0, "public": 12000, "redaction": 0}
        missing = present | {"public": 0}
        for counts in ((missing, present), (present, missing)):
            with self.subTest(counts=counts):
                with patch.object(baseline.hardening, "colors", side_effect=counts):
                    with self.assertRaisesRegex(AssertionError, "missing public control"):
                        baseline.observation(Mock(), Mock(), "sample")

    def test_one_protected_pixel_cannot_be_reported_as_cleared(self):
        self.assertTrue(baseline.cleared({"protected": 0, "redaction": 0}))
        self.assertFalse(baseline.cleared({"protected": 1, "redaction": 0}))
        self.assertFalse(baseline.cleared({"protected": 0, "redaction": 20000}))

    def test_capture_orders_are_executed_and_each_capture_is_bracketed(self):
        for order, expected in baseline.CAPTURE_ORDERS.items():
            with self.subTest(order=order):
                calls = []
                parent, child, trace = Mock(), Mock(), Mock()
                parent.capture.side_effect = lambda _, calls=calls: (
                    calls.append("output") or "output"
                )

                child.capture.side_effect = lambda _, calls=calls: (
                    calls.append("screen_capture") or "child"
                )
                counts = {"public": 20000, "protected": 0, "redaction": 0}
                with patch.object(baseline.hardening, "colors", return_value=counts):
                    result = baseline.observation(parent, child, "sample", order, trace)
                self.assertEqual(calls, list(expected))
                self.assertEqual(set(result), {"output", "screen_capture"})
                self.assertEqual(
                    [call.args[0] for call in trace.mark.call_args_list],
                    [
                        name
                        for target in expected
                        for name in (f"before-sample-{target}", f"capture-sample-{target}")
                    ],
                )

    def test_protocol_logging_is_scoped_to_the_owned_compositor_launch(self):
        for mode in ("client", "server"):
            with self.subTest(mode=mode):
                session = baseline.ObservedSession.__new__(baseline.ObservedSession)
                session.protocol_trace = mode
                original = {"PATH": "/synthetic/bin"}
                with patch.object(baseline.NestedSession, "launch") as launch:
                    session.launch(["owned-niri"], "niri", env=original)
                    self.assertEqual(launch.call_args.kwargs["env"]["WAYLAND_DEBUG"], mode)
                    self.assertNotIn("WAYLAND_DEBUG", original)
                    session.launch(["owned-client"], "card", env=original)
                    self.assertNotIn("WAYLAND_DEBUG", launch.call_args.kwargs["env"])

    def test_trace_phase_boundaries_count_only_new_log_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            parent, child = Mock(), Mock()
            parent.root, child.root = Path(directory) / "parent", Path(directory) / "child"
            for owner, arrow in ((parent, ""), (child, "->")):
                owner.root.mkdir()
                (owner.root / "niri.log").write_text(f"[1.000] {arrow} wl_surface#7.commit()\n")
            with patch.object(baseline.time, "monotonic", side_effect=[10.0, 10.5, 10.8]):
                trace = baseline.OutputTrace(parent, child, 10.0)
                with (child.root / "niri.log").open("a") as stream:
                    stream.write("[1.500] -> wl_surface#7.commit()\n")
                trace.mark("child-request")
                with (parent.root / "niri.log").open("a") as stream:
                    stream.write("[1.800] wl_surface#7.commit()\n")
                trace.mark("parent-receipt")
            report = trace.report()
        sent = report["child_sent"]["phases"]
        received = report["parent_received"]["phases"]
        self.assertEqual([p["all_surface_requests"]["commit"] for p in sent], [1, 0])
        self.assertEqual([p["all_surface_requests"]["commit"] for p in received], [0, 1])
        self.assertEqual(sent[1]["begin_ms_after_close"], 500)
        self.assertEqual(sent[1]["end_ms_after_close"], 800)

    def test_output_comparison_uses_fresh_order_cases_and_retains_strict_exit(self):
        settings = {
            "revision": "pinned",
            "build_profile": "release",
            "build_flags": [],
            "rustc": "test",
            "binary_sha256": "test",
        }
        probes = []

        def output(binary, protocol, enabled, preview, order):
            probes.append((binary, enabled, preview, order))
            return {
                "renderer": "test-renderer",
                "target": "test-target",
                "capture_order": order,
                "stale_parent_output_reproduced": len(probes) == 1,
            }

        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            with (
                patch.object(
                    sys, "argv", ["baseline", "--probe", "output", "--report", str(report)]
                ),
                patch.object(baseline, "baseline", return_value=("base", settings)),
                patch.object(baseline, "experiment", return_value=("fx", settings, None)),
                patch.object(baseline, "pointer_protocol", return_value="protocol"),
                patch.object(baseline, "source_hashes", return_value={}),
                patch.object(baseline, "output_probe", side_effect=output),
                patch("builtins.print"),
            ):
                self.assertEqual(baseline.main(), 1)
            evidence = json.loads(report.read_text())
        self.assertEqual(len(probes), 12)
        self.assertEqual(len(set(probes)), 12)
        self.assertTrue(evidence["completed_comparison"])
        self.assertTrue(evidence["defect_reproduced"])
        self.assertEqual([len(item["output"]) for item in evidence["results"]], [4, 4, 4])

    def test_missing_renderer_evidence_still_cleans_up_the_owned_session(self):
        sessions = []

        def disconnected(*_):
            # Exercise the diagnostic's real exit wrapper without starting Niri.
            session_type = baseline.hardening.NestedSession
            session = session_type.__new__(session_type)
            sessions.append(session)
            session.__exit__(None, None, None)

        with (
            patch.object(baseline.hardening, "disconnected_pointer", side_effect=disconnected),
            patch.object(
                baseline.ObservedSession,
                "renderer",
                side_effect=RuntimeError("Missing GL Renderer evidence"),
            ),
            patch.object(baseline.ObservedSession, "__exit__", autospec=True) as cleanup,
        ):
            with self.assertRaisesRegex(RuntimeError, "Missing GL Renderer evidence"):
                baseline.disconnect_probe(None, None, False)
        cleanup.assert_called_once_with(sessions[0], None, None, None)

    def test_overlapping_scenarios_cannot_silently_change_renderer(self):
        def overlapping(*_):
            for _ in range(2):
                session_type = baseline.hardening.NestedSession
                session = session_type.__new__(session_type)
                session.__exit__(None, None, None)
            return {"scenarios": []}

        with (
            patch.object(baseline.hardening, "overlapping_pointers", side_effect=overlapping),
            patch.object(baseline.ObservedSession, "renderer", side_effect=["first", "second"]),
            patch.object(baseline.ObservedSession, "__exit__", autospec=True) as cleanup,
        ):
            with self.assertRaisesRegex(AssertionError, "changed renderer"):
                baseline.disconnect_probe(None, None, False, overlapping=True)
        self.assertEqual(cleanup.call_count, 2)


if __name__ == "__main__":
    unittest.main()
