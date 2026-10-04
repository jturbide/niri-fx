"""A baseline must be comparable and its privacy control must remain observable."""

import importlib.util
import sys
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


if __name__ == "__main__":
    unittest.main()
