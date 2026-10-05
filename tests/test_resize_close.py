"""Resize-close observations must prove material continuity through independent fade."""

import importlib.util
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    spec = importlib.util.spec_from_file_location(
        "resize_close", ROOT / "scripts/test-resize-close.py"
    )
    close = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(close)
    spec = importlib.util.spec_from_file_location(
        "record_resize_close", ROOT / "scripts/record-resize-close.py"
    )
    recorder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(recorder)


class ResizeCloseEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def image(self, phase=0.4, opacity=1, original=(400, 360), reference=(700, 360)):
        frame = Image.new("RGB", (500, 300), close.BACKGROUND)
        draw = ImageDraw.Draw(frame)
        for left, right, rgb in (
            (20, 69, close.CALIBRATION),
            (70, 169, (16, *(round(value * 255 / 1024) for value in original))),
            (170, 269, (32, *(round(value * 255 / 1024) for value in reference))),
            (
                270,
                419,
                (
                    round((0.25 + 0.5 * phase) * 255),
                    *(round(value * 255 / 1024) for value in reference),
                ),
            ),
        ):
            visible = tuple(
                round(base + opacity * (value - base))
                for value, base in zip(rgb, close.BACKGROUND, strict=True)
            )
            draw.rectangle((left, 40, right, 239), fill=visible)
        path = self.root / "frame.png"
        frame.save(path)
        return path

    def test_decode_separates_fade_from_original_material_phase_and_geometry(self):
        for alpha in (1, 0.92, 0.75, 0.5):
            with self.subTest(alpha=alpha):
                observation = close.decode(self.image(opacity=alpha))
                self.assertAlmostEqual(observation["phase"], 0.4, delta=0.015)
                self.assertAlmostEqual(observation["alpha"], alpha, delta=0.005)
                self.assertEqual(observation["size"], [400, 200])
                self.assertEqual(observation["bounds"], [20, 40, 420, 240])

    def test_references_and_missing_continuation_cannot_pass(self):
        for change in ({"reference": (600, 460)}, {"original": (520, 360)}):
            with self.subTest(change=change), self.assertRaises(AssertionError):
                close.decode(self.image(opacity=0.8, **change))
        blank = self.root / "blank.png"
        Image.new("RGB", (500, 300), close.BACKGROUND).save(blank)
        with self.assertRaises(AssertionError):
            close.decode(blank)

    def test_phase_clock_rejects_frozen_or_restarted_material(self):
        before = close.decode(self.image(phase=0.4))
        after = close.decode(self.image(phase=0.6, opacity=0.8))
        close.continues(before, after, 0.6)
        for phase in (0.4, 0.1):
            with self.subTest(phase=phase), self.assertRaises(AssertionError):
                close.continues(before, close.decode(self.image(phase=phase, opacity=0.8)), 0.6)

    def test_first_frame_comparison_allows_rounding_but_rejects_displacement(self):
        before = self.image()
        after = self.root / "after.png"
        with Image.open(before) as image:
            draw = ImageDraw.Draw(image)
            draw.point((25, 50), fill=(239, 220, 30))
            image.save(after)
        self.assertEqual(
            close.first_frame_difference(before, after)["maximum_channel_difference"], 1
        )
        with Image.open(after) as image:
            draw = ImageDraw.Draw(image)
            draw.rectangle((20, 40, 24, 239), fill=close.BACKGROUND)
            image.save(after)
        with self.assertRaisesRegex(AssertionError, "first frame changed"):
            close.first_frame_difference(before, after)

    def boundary_frame(self, *, points=(), interior=None, shift=0):
        frame = Image.new("RGB", (80, 80), close.BACKGROUND)
        ImageDraw.Draw(frame).rectangle((20 + shift, 10, 59 + shift, 69), fill=(240, 220, 30))
        for point in points:
            frame.putpixel(point, (141, 145, 154))
        if interior:
            frame.putpixel(interior, close.BACKGROUND)
        path = self.root / f"boundary-{len(list(self.root.iterdir()))}.png"
        frame.save(path)
        return path

    def test_first_close_allows_only_four_isolated_silhouette_pixels(self):
        before = self.boundary_frame()
        points = [(19, y) for y in (20, 30, 40, 50)]
        report = close.first_frame_difference(
            before, self.boundary_frame(points=points), allow_silhouette=True
        )
        self.assertEqual(report["exceptional_pixel_count"], 4)
        self.assertEqual(report["interior_exception_count"], 0)
        self.assertEqual(report["allowed_silhouette_exceptions"], 4)
        self.assertEqual(
            [item["coordinate"] for item in report["exceptional_pixels"]],
            [list(point) for point in points],
        )
        with self.assertRaisesRegex(AssertionError, "first frame changed"):
            close.first_frame_difference(
                before,
                self.boundary_frame(points=[*points, (19, 60)]),
                allow_silhouette=True,
            )

    def test_silhouette_rule_rejects_interior_corruption_and_whole_edge_translation(self):
        before = self.boundary_frame()
        for after in (self.boundary_frame(interior=(40, 40)), self.boundary_frame(shift=1)):
            with (
                self.subTest(after=after),
                self.assertRaisesRegex(AssertionError, "first frame changed"),
            ):
                close.first_frame_difference(before, after, allow_silhouette=True)

    def test_silhouette_rule_requires_background_and_stable_neighbors_in_both_frames(self):
        before = self.boundary_frame()
        after = self.root / "edge-color.png"
        with Image.open(before) as image:
            # A color change on foreground stays forbidden even at an edge.
            image.putpixel((20, 30), (100, 100, 100))
            image.save(after)
        with self.assertRaisesRegex(AssertionError, "first frame changed"):
            close.first_frame_difference(before, after, allow_silhouette=True)
        isolated = self.root / "isolated.png"
        with Image.open(before) as image:
            image.putpixel((5, 5), (240, 220, 30))
            image.save(isolated)
        with self.assertRaisesRegex(AssertionError, "first frame changed"):
            close.first_frame_difference(before, isolated, allow_silhouette=True)

    def test_small_translated_fragment_fails_even_within_four_pixel_budget(self):
        paths = []
        for x in (10, 11):
            frame = Image.new("RGB", (30, 30), close.BACKGROUND)
            ImageDraw.Draw(frame).line((x, 10, x, 11), fill=(240, 220, 30))
            path = self.root / f"segment-{x}.png"
            frame.save(path)
            paths.append(path)
        evidence = {}
        with self.assertRaisesRegex(AssertionError, "first frame changed"):
            close.first_frame_difference(*paths, allow_silhouette=True, evidence=evidence)
        self.assertEqual(evidence["exceptional_pixel_count"], 4)
        self.assertEqual(evidence["interior_exception_count"], 4)
        self.assertFalse(evidence["accepted"])

    def test_stationary_control_is_exact_even_when_silhouette_option_is_requested(self):
        before = self.boundary_frame()
        close.first_frame_difference(before, before, stationary=True)
        after = self.root / "one-step.png"
        with Image.open(before) as image:
            image.putpixel((30, 30), (239, 220, 30))
            image.save(after)
        with self.assertRaisesRegex(AssertionError, "stationary control changed"):
            close.first_frame_difference(before, after, stationary=True, allow_silhouette=True)

    def test_failed_native_observation_remains_failed_in_partial_report(self):
        report = self.root / "partial.json"

        def failed(_binary, _parent, cases, **_options):
            cases.append({"status": "failed", "checks": [{"phase": 0.1}]})
            raise AssertionError("material restarted")

        with (
            patch.object(sys, "argv", ["probe", "--suite", "material", "--report", str(report)]),
            patch.object(close.material, "checked_binary", return_value=(self.root / "niri", {})),
            patch.object(close, "diagnostic", side_effect=failed),
            self.assertRaisesRegex(AssertionError, "restarted"),
        ):
            close.main()
        evidence = json.loads(report.read_text())
        self.assertEqual(evidence["status"], "failed")
        self.assertEqual(evidence["cases"][0]["checks"], [{"phase": 0.1}])

    def acceptance(self):
        cases = [
            {"case": name, "status": "passed", "checks": [{"targets": {"output": {}}}]}
            for name in (
                "material",
                "material-open",
                "material-movement",
                "disable-resize",
                "disable-close",
                "disable-global",
                *(["privacy"] * 6),
            )
        ]
        cases.extend(
            {
                "case": "same-context-scale-change",
                "protected": protected,
                "status": "passed",
                "checks": [],
            }
            for protected in (False, True)
        )
        frame = self.boundary_frame()
        for origin in ([0, 0], [24, 24]):
            for preset in ("balanced", "slide-apart", "spring-wobble"):
                cases.append(
                    {
                        "case": "generated",
                        "status": "passed",
                        "checks": [],
                        "preset": preset,
                        "explicit_geometry_origin": origin,
                        "frozen_control": close.first_frame_difference(
                            frame, frame, stationary=True
                        ),
                        "unmap_boundary": close.first_frame_difference(
                            frame, frame, allow_silhouette=True
                        ),
                    }
                )
        for flag in ("popup", "native_border_and_shadow"):
            case = deepcopy(cases[-1])
            case[flag] = True
            cases.append(case)
        return {
            "status": "passed",
            "cases": cases,
            "parent_build": {"unmodified": True},
            "first_frame_oracle": close.FIRST_FRAME_ORACLE,
        }

    def test_recording_requires_popup_decorations_and_exact_stationary_evidence(self):
        acceptance = self.acceptance()
        recorder.require_complete_acceptance(acceptance)
        for flag in ("popup", "native_border_and_shadow"):
            missing = deepcopy(acceptance)
            missing["cases"] = [case for case in missing["cases"] if not case.get(flag)]
            with self.subTest(flag=flag), self.assertRaises(AssertionError):
                recorder.require_complete_acceptance(missing)
        changed = deepcopy(acceptance)
        changed["cases"][-1]["frozen_control"]["maximum_channel_difference"] = 1
        with self.assertRaises(AssertionError):
            recorder.require_complete_acceptance(changed)

    def test_recording_rejects_relaxed_or_failed_boundary_evidence(self):
        for field, value in (
            ("allowed_silhouette_exceptions", 5),
            ("accepted", False),
            ("interior_exception_count", 1),
            ("exceptional_pixel_count", 5),
        ):
            acceptance = self.acceptance()
            acceptance["cases"][-1]["unmap_boundary"][field] = value
            with self.subTest(field=field), self.assertRaises(AssertionError):
                recorder.require_complete_acceptance(acceptance)
