"""Native retained-material observations reject missing or reset evidence."""

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
        "resize_material", ROOT / "scripts/test-resize-material.py"
    )
    material = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(material)


class ResizeMaterialEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def image(self, *, phase=0.4, reference=(700, 360), original=(400, 360)):
        frame = Image.new("RGB", (400, 200), "#111827")
        draw = ImageDraw.Draw(frame)
        for left, right, red, size in (
            (0, 99, 16, original),
            (100, 199, 32, reference),
            (200, 399, round((0.25 + 0.5 * phase) * 255), reference),
        ):
            draw.rectangle(
                (left, 0, right, 199),
                fill=(red, *(round(value * 255 / 1024) for value in size)),
            )
        path = self.root / "diagnostic.png"
        frame.save(path)
        return path

    def test_rendered_uniforms_decode_but_changed_or_missing_bands_fail(self):
        result = material.diagnostic(self.image())
        self.assertAlmostEqual(result["phase"], 0.4, delta=0.008)
        self.assertEqual(result["from"], [400, 360])
        self.assertEqual(result["reference"], [700, 360])
        for replacement in ({"reference": (520, 360)}, {"original": (700, 360)}):
            with self.subTest(replacement=replacement), self.assertRaises(AssertionError):
                material.diagnostic(self.image(**replacement))
        blank = self.root / "blank.png"
        Image.new("RGB", (400, 200), "#111827").save(blank)
        with self.assertRaises(AssertionError):
            material.diagnostic(blank)

    def test_phase_oracle_rejects_reset_and_changed_clock(self):
        material.phase_continues({"phase": 0.25}, {"phase": 0.4}, 0.45, 3)
        for after, elapsed in ((0.05, 0.1), (0.9, 0.1), (0.25, 1.2)):
            with self.subTest(after=after, elapsed=elapsed), self.assertRaises(AssertionError):
                material.phase_continues({"phase": 0.25}, {"phase": after}, elapsed, 3)

    def test_privacy_requires_a_live_public_control_and_advancing_parent(self):
        visible = {"public": 105000, "protected": 65000}
        hidden = {"public": 105000, "protected": 0}
        self.assertTrue(material.privacy_valid(visible, hidden=False))
        self.assertTrue(material.privacy_valid(hidden, hidden=True))
        for counts, blocked, advanced in (
            (visible, False, False),
            (hidden, True, False),
            (visible, True, True),
            ({"public": 0, "protected": 0}, True, True),
        ):
            with self.subTest(counts=counts, blocked=blocked, advanced=advanced):
                self.assertFalse(material.privacy_valid(counts, hidden=blocked, advanced=advanced))

    def test_prototype_hash_cannot_bypass_default_manifest_checks(self):
        binary = self.root / "niri"
        binary.write_bytes(b"owned prototype")
        with patch.object(material, "experiment", side_effect=RuntimeError("stale patch")):
            with self.assertRaisesRegex(RuntimeError, "stale patch"):
                material.checked_binary(None, None)
        for path, digest in ((binary, None), (None, "a" * 64), (binary, "a" * 64)):
            with self.subTest(path=path, digest=digest), self.assertRaises(ValueError):
                material.checked_binary(path, digest)
        digest = material.hashlib.sha256(binary.read_bytes()).hexdigest()
        actual, evidence = material.checked_binary(binary, digest)
        self.assertEqual(actual, binary)
        self.assertEqual(evidence["binary_sha256"], digest)
        self.assertIn("prototype", evidence["scope"])
        with self.assertRaisesRegex(ValueError, "cannot be combined"):
            material.checked_binary(binary, digest, unmodified=True)

    def test_failed_privacy_run_preserves_observations_and_nonzero_outcome(self):
        report = self.root / "partial.json"

        def failed(_parent, _binary, _policy, _preview, results):
            results.append({"status": "failed", "checks": [{"protected": 12345}]})
            raise AssertionError("protected content remained visible")

        with (
            patch.object(sys, "argv", ["probe", "--suite", "privacy", "--report", str(report)]),
            patch.object(material, "checked_binary", return_value=(self.root / "niri", {})),
            patch.object(material, "privacy", side_effect=failed),
            self.assertRaisesRegex(AssertionError, "remained visible"),
        ):
            material.main()
        evidence = json.loads(report.read_text())
        self.assertEqual(evidence["status"], "failed")
        self.assertEqual(evidence["privacy"][0]["checks"], [{"protected": 12345}])


if __name__ == "__main__":
    unittest.main()
