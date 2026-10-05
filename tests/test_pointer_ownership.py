"""Fail-closed ownership acceptance oracles; native behavior is tested in Niri."""

import copy
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    spec = importlib.util.spec_from_file_location(
        "pointer_ownership", ROOT / "scripts/test-pointer-ownership.py"
    )
    ownership = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ownership)


def records():
    return {
        "scenarios": [
            {
                "scenario": scenario,
                "motion_moved_window": scenario != "owner-a-destroyed",
                "release_stopped_window": True,
                "survivor_click_recovered": True,
            }
            for scenario in (
                "idle-b-destroyed",
                "owner-a-destroyed",
                "former-owner-a-destroyed",
                "same-button-a-released",
                "same-button-a-destroyed",
            )
        ]
    }


class PointerOwnershipTests(unittest.TestCase):
    def test_every_control_requires_continuation_and_final_release_as_appropriate(self):
        passing = records()
        ownership.require_ownership(passing)
        self.assertTrue(all(record["passed"] for record in passing["scenarios"]))
        for index in range(5):
            for field in (
                "motion_moved_window",
                "release_stopped_window",
                "survivor_click_recovered",
            ):
                with self.subTest(index=index, field=field):
                    broken = copy.deepcopy(passing)
                    broken["scenarios"][index][field] = not broken["scenarios"][index][field]
                    with self.assertRaises(AssertionError):
                        ownership.require_ownership(broken)
                    self.assertTrue(broken["failed_controls"])

    def test_missing_or_duplicate_control_cannot_pass(self):
        broken = records()
        broken["scenarios"].pop()
        with self.assertRaisesRegex(AssertionError, "Incomplete ownership"):
            ownership.require_ownership(broken)
        broken["scenarios"].append(broken["scenarios"][0].copy())
        with self.assertRaisesRegex(AssertionError, "Incomplete ownership"):
            ownership.require_ownership(broken)

    def test_explicit_candidate_requires_matching_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "candidate"
            executable.write_bytes(b"candidate")
            for binary, digest in ((executable, None), (None, "bad"), (executable, "bad")):
                with self.subTest(binary=binary, digest=digest), self.assertRaises(ValueError):
                    ownership.checked_binary(binary, digest)

    def test_baseline_guard_cannot_be_combined_with_prototype_or_optional_patch(self):
        with self.assertRaises(ValueError):
            ownership.checked_binary(Path("candidate"), "sha", unmodified=True)
        with self.assertRaises(ValueError):
            ownership.checked_binary(None, None, unmodified=True, pointer_wobble=True)


if __name__ == "__main__":
    unittest.main()
