"""Resize comparisons need a verified baseline and observable native edges."""

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    spec = importlib.util.spec_from_file_location(
        "resize_comparison", ROOT / "scripts/record-resize-comparison.py"
    )
    recorder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recorder)


class ResizeBaselineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.binary = self.root / "niri"
        self.binary.write_bytes(b"synthetic binary identity")
        self.manifest = self.root / "build.json"
        self.patch_bytes = b"synthetic historical movement patch"
        self.build = {
            "binary": str(self.binary),
            "binary_sha256": recorder.digest(self.binary),
            "revision": "same-pinned-revision",
            "patch_sha256": hashlib.sha256(self.patch_bytes).hexdigest(),
        }

    def compare(self, baseline=None, updated=None):
        self.manifest.write_text(json.dumps(baseline or self.build))
        with patch.object(
            recorder.subprocess, "check_output", side_effect=["a" * 40 + "\n", self.patch_bytes]
        ) as git:
            result = recorder.baseline(self.manifest, "v0.18.0", updated or self.build)
        return result, git

    def test_missing_historical_metadata_is_explicit_and_hashes_stay_historical(self):
        (binary, evidence), git = self.compare()
        self.assertEqual(binary, self.binary)
        self.assertEqual(evidence["patch_sha256"], self.build["patch_sha256"])
        self.assertEqual(evidence["build_metadata"], {})
        self.assertEqual(
            evidence["metadata_not_comparable"], ["build_profile", "build_flags", "rustc"]
        )
        self.assertEqual(
            git.call_args_list[1].args[0][-1], "a" * 40 + ":experimental/niri-movement.patch"
        )
        self.assertTrue(all(call.kwargs["timeout"] == 15 for call in git.call_args_list))

    def test_changed_executable_or_tagged_patch_rejects_comparison(self):
        for field in ("binary_sha256", "patch_sha256"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.compare(self.build | {field: "mismatched"})

    def test_pointer_and_stock_baselines_cannot_be_compared(self):
        for extra in ({"pointer_patch_sha256": "pointer"}, {"unmodified": True}):
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, "movement-only"):
                self.compare(self.build | extra)

    def test_different_revision_and_available_build_metadata_reject_comparison(self):
        with self.assertRaisesRegex(ValueError, "same pinned"):
            self.compare(updated=self.build | {"revision": "another"})
        for field in ("build_profile", "build_flags", "rustc"):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                self.compare(self.build | {field: "old"}, self.build | {field: "new"})


def clip(version, axis, minimum, maximum, far=900):
    return {
        "case": f"{version}-{axis}",
        "edges": {"min_gap_px": minimum, "max_gap_px": maximum, "max_far_edge_px": far},
    }


class ResizeEdgeAcceptanceTests(unittest.TestCase):
    def test_acceptance_requires_a_reproduced_gap_and_an_aligned_result(self):
        good = [clip("before", "width", 8, 70), clip("after", "width", 16, 18)]
        recorder.check_edges(good, "width")
        for invalid in (
            [clip("before", "width", 16, 18), good[1]],
            [good[0], clip("after", "width", 16, 21)],
            [good[0], clip("after", "width", 11, 18)],
            [clip("before", "width", 8, 70, 1025), good[1]],
        ):
            with self.subTest(invalid=invalid), self.assertRaises(AssertionError):
                recorder.check_edges(invalid, "width")

    def test_axes_are_measured_independently(self):
        clips = [
            clip("before", "width", 8, 70),
            clip("after", "width", 16, 18),
            clip("before", "height", 10, 50),
            clip("after", "height", 16, 24),
        ]
        recorder.check_edges(clips, "width")
        with self.assertRaisesRegex(AssertionError, "separation"):
            recorder.check_edges(clips, "height")


class ResizeDecodedFramesTests(unittest.TestCase):
    @staticmethod
    def frame(vertical, gap=16, *, neighbor=True):
        frame = Image.new("RGB", (1280, 900), "#111827")
        draw = ImageDraw.Draw(frame)
        if vertical:
            draw.rectangle((16, 16, 665, 315), fill=recorder.PALETTE["Resizing"])
            if neighbor:
                draw.rectangle((16, 316 + gap, 665, 615 + gap), fill=recorder.PALETTE["Neighbor"])
        else:
            draw.rectangle((16, 16, 375, 883), fill=recorder.PALETTE["Resizing"])
            if neighbor:
                draw.rectangle((376 + gap, 16, 735 + gap, 883), fill=recorder.PALETTE["Neighbor"])
        # Stray matching pixels must not extend the measured solid edge.
        draw.rectangle((1200, 880, 1202, 882), fill=recorder.PALETTE["Resizing"])
        return frame.tobytes()

    def measure(self, data, vertical):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "synthetic.mkv"

            def decode(command, **kwargs):
                self.assertEqual(kwargs["timeout"], 120)
                self.assertTrue(kwargs["check"])
                self.assertTrue(kwargs["capture_output"])
                Path(command[-1]).write_bytes(data)

            with patch.object(recorder.subprocess, "run", side_effect=decode):
                return recorder.measure_video(source, vertical)

    def test_both_axes_report_native_gaps_and_ignore_isolated_pixels(self):
        for vertical in (False, True):
            with self.subTest(vertical=vertical):
                result = self.measure(self.frame(vertical) + self.frame(vertical, 40), vertical)
                self.assertEqual(result["decoded_frames"], 2)
                self.assertEqual(result["min_gap_px"], 16)
                self.assertEqual(result["max_gap_px"], 40)

    def test_empty_or_truncated_decodes_are_not_successful_measurements(self):
        for data in (b"", b"partial frame"):
            with self.subTest(length=len(data)), self.assertRaises(RuntimeError):
                self.measure(data, False)

    def test_missing_synthetic_card_is_not_calibrated_to_the_background(self):
        with self.assertRaisesRegex(RuntimeError, "Neighbor population missing"):
            self.measure(self.frame(False, neighbor=False), False)


if __name__ == "__main__":
    unittest.main()
