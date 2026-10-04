"""Output feedback cannot be mistaken for capture or hardware scanout evidence."""

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location(
    "native_timing", ROOT / "scripts/measure-native-movement.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def frame(output, time_ms, source="winit-submit", flags=0, action=0):
    return dict(
        output=output, timestamp_ns=int(time_ms * 1e6), source=source, flags=flags, action=action
    )


class NativeTimingTests(unittest.TestCase):
    def test_outputs_and_workloads_are_not_combined(self):
        samples = [
            frame("a", 0),
            frame("b", 5),
            frame("a", 16),
            frame("b", 25),
            frame("a", 1000, action=1),
            frame("a", 1016, action=1),
            frame("a", 1016, action=1),
        ]
        report = module.native_timing(samples)
        self.assertEqual(report[0]["intervals"]["raw_ms"], [16, 16])
        self.assertEqual(report[1]["intervals"]["raw_ms"], [20])
        self.assertFalse(any(item["hardware_presentation"] for item in report))
        self.assertNotIn("output", report[0])

    def test_hardware_requires_drm_and_all_three_flags(self):
        for source, flags, expected in [
            ("winit-submit", 7, False),
            ("drm-presentation", 3, False),
            ("drm-presentation", 7, True),
            ("drm-presentation", 15, True),
        ]:
            with self.subTest(source=source, flags=flags):
                result = module.native_timing(
                    [frame("a", 0, source, flags), frame("a", 16, source, flags)]
                )[0]
                self.assertEqual(result["hardware_presentation"], expected)
        report = module.native_timing(
            [frame("a", 0, "drm-presentation", 7), frame("a", 16, "drm-presentation", 1)]
        )
        self.assertFalse(report[0]["hardware_presentation"])

    def test_empty_or_single_frame_is_not_a_measurement(self):
        for samples in ([], [frame("a", 0)]):
            with self.assertRaises(ValueError):
                module.native_timing(samples)
