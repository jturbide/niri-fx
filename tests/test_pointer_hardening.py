"""Guard the native privacy evidence oracle with synthetic captures, without Niri."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    spec = importlib.util.spec_from_file_location(
        "pointer_hardening", ROOT / "scripts/test-pointer-hardening.py"
    )
    hardening = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hardening)


class PointerHardeningOracleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def capture(self, name, colors, *, size=(120, 100)):
        """Every stripe is larger than the live harness's positive-control gate."""
        image = Image.new("RGB", (size[0] * len(colors), size[1]))
        for index, color in enumerate(colors):
            image.paste(color, (index * size[0], 0, (index + 1) * size[0], size[1]))
        path = self.root / f"{name}.png"
        image.save(path)
        return path

    def test_original_and_early_close_accents_are_counted_separately(self):
        background = (17, 24, 39)
        for opacity in (1.0, 0.9, 0.85):
            # These are early close frames: the public and protected accents
            # both retain enough contrast to prove their respective controls.
            accents = [
                tuple(
                    round(foreground * opacity + base * (1 - opacity))
                    for foreground, base in zip(bytes.fromhex(accent[1:]), background, strict=True)
                )
                for accent in (hardening.PROTECTED, hardening.PUBLIC)
            ]
            with self.subTest(opacity=opacity):
                path = self.capture(f"faded-{opacity}", accents)
                self.assertEqual(
                    hardening.colors(path),
                    {"protected": 12000, "public": 12000, "redaction": 0},
                )

    def test_background_card_details_and_redaction_cannot_impersonate_accents(self):
        path = self.capture(
            "neutral",
            ["#111827", "#182735", "#415260", "#f6f8fc", "#dce2e8", "#000000", "#04060a"],
        )
        self.assertEqual(
            hardening.colors(path),
            {"protected": 0, "public": 0, "redaction": 24000},
        )

    def test_all_visibility_combinations_preserve_independent_capture_targets(self):
        allowed = self.capture("allowed", [hardening.PUBLIC, hardening.PROTECTED])
        blocked = self.capture("blocked", [hardening.PUBLIC, "#000000"])
        for output_hidden in (False, True):
            for capture_hidden in (False, True):
                with self.subTest(output_hidden=output_hidden, capture_hidden=capture_hidden):
                    parent = Mock(capture=Mock(return_value=blocked if output_hidden else allowed))
                    child = Mock(capture=Mock(return_value=blocked if capture_hidden else allowed))
                    counts = hardening.capture_pair(
                        parent,
                        child,
                        "sample",
                        output_hidden=output_hidden,
                        capture_hidden=capture_hidden,
                    )
                    self.assertEqual(counts["output"]["protected"], 0 if output_hidden else 12000)
                    self.assertEqual(
                        counts["screen_capture"]["protected"], 0 if capture_hidden else 12000
                    )
                    parent.capture.assert_called_once_with("sample-output")
                    child.capture.assert_called_once_with("sample-capture")

    def test_direct_capture_reports_only_the_observed_screen_capture_target(self):
        allowed = self.capture("allowed", [hardening.PUBLIC, hardening.PROTECTED])
        blocked = self.capture("blocked", [hardening.PUBLIC, "#000000"])
        for output_hidden in (False, True):
            for capture_hidden in (False, True):
                with self.subTest(output_hidden=output_hidden, capture_hidden=capture_hidden):
                    child = Mock(capture=Mock(return_value=blocked if capture_hidden else allowed))
                    counts = hardening.capture_pair(
                        None,
                        child,
                        "direct",
                        output_hidden=output_hidden,
                        capture_hidden=capture_hidden,
                    )
                    self.assertEqual(set(counts), {"screen_capture"})
                    self.assertEqual(
                        counts["screen_capture"]["protected"], 0 if capture_hidden else 12000
                    )
                    child.capture.assert_called_once_with("direct-capture")

    def test_direct_capture_still_rejects_a_single_pixel_leak(self):
        leaked = self.capture("direct-leak", [hardening.PUBLIC, "#000000"])
        with Image.open(leaked) as image:
            image.putpixel((150, 50), tuple(bytes.fromhex(hardening.PROTECTED[1:])))
            image.save(leaked)
        child = Mock(capture=Mock(return_value=leaked))
        with self.assertRaisesRegex(AssertionError, "unexpected protected visibility"):
            hardening.capture_pair(
                None, child, "direct-leak", output_hidden=False, capture_hidden=True
            )
        child.capture.assert_called_once_with("direct-leak-capture")

    def test_even_one_protected_pixel_invalidates_a_blocked_capture(self):
        blocked = self.capture("blocked", [hardening.PUBLIC, "#000000"])
        leaked = self.root / "leaked.png"
        with Image.open(blocked) as image:
            image.putpixel((150, 50), tuple(bytes.fromhex(hardening.PROTECTED[1:])))
            image.save(leaked)
        for target in ("output", "screen_capture"):
            with self.subTest(target=target):
                parent = Mock(capture=Mock(return_value=leaked if target == "output" else blocked))
                child = Mock(
                    capture=Mock(return_value=leaked if target == "screen_capture" else blocked)
                )
                with self.assertRaisesRegex(AssertionError, "unexpected protected visibility"):
                    hardening.capture_pair(
                        parent, child, "leak", output_hidden=True, capture_hidden=True
                    )

    def test_blank_or_missing_public_control_is_rejected_in_each_target(self):
        valid = self.capture("valid", [hardening.PUBLIC, hardening.PROTECTED])
        for name, content in (("blank", ["#000000"]), ("private-only", [hardening.PROTECTED])):
            invalid = self.capture(name, content)
            for target in ("output", "screen_capture"):
                with self.subTest(content=name, target=target):
                    parent = Mock(
                        capture=Mock(return_value=invalid if target == "output" else valid)
                    )
                    child = Mock(
                        capture=Mock(return_value=invalid if target == "screen_capture" else valid)
                    )
                    with self.assertRaisesRegex(AssertionError, "missing public control"):
                        hardening.capture_pair(
                            parent, child, name, output_hidden=False, capture_hidden=False
                        )

    def test_allowed_target_requires_its_protected_control(self):
        valid = self.capture("valid", [hardening.PUBLIC, hardening.PROTECTED])
        invalid = self.capture("missing-protected", [hardening.PUBLIC, "#111827"])
        for target in ("output", "screen_capture"):
            with self.subTest(target=target):
                parent = Mock(capture=Mock(return_value=invalid if target == "output" else valid))
                child = Mock(
                    capture=Mock(return_value=invalid if target == "screen_capture" else valid)
                )
                with self.assertRaisesRegex(AssertionError, "unexpected protected visibility"):
                    hardening.capture_pair(
                        parent, child, "missing", output_hidden=False, capture_hidden=False
                    )


if __name__ == "__main__":
    unittest.main()
