"""Keep experimental pointer controls bounded and public snippets reproducible."""

import math
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

from niri_fx.pointer import PRESETS, PointerWobble, parse_pointer, render_example, render_node

ROOT = Path(__file__).resolve().parents[1]


class PointerWobbleTests(unittest.TestCase):
    def test_invalid_settings_are_rejected_before_config_generation(self):
        invalid = {
            "strength": [True, False, None, "0.7", [], -0.01, 2.01, math.nan, math.inf, 10**400],
            "damping": [True, None, "65", 65.0, math.nan, 9, 101],
            "frequency": [False, None, "8", 8.0, math.inf, 1, 17],
        }
        for field, values in invalid.items():
            for value in values:
                with (
                    self.subTest(field=field, value=value),
                    self.assertRaisesRegex(ValueError, field),
                ):
                    replace(PointerWobble(), **{field: value})

    def test_inclusive_bounds_and_zero_strength_are_supported(self):
        self.assertEqual(
            render_node(PointerWobble(0, 10, 2), indent=""),
            "pointer-wobble {\n    strength 0.000000\n    damping 10\n    frequency 2\n}\n",
        )
        self.assertIn("strength 2.000000\n", render_node(PointerWobble(2, 100, 16)))
        self.assertIn("strength 0.123457\n", render_node(PointerWobble(0.123456789)))

    def test_parser_requires_complete_named_controls_and_preserves_disabled(self):
        self.assertIsNone(parse_pointer(None))
        self.assertEqual(
            parse_pointer({"strength": 0, "damping": 65, "frequency": 8}), PointerWobble(0)
        )
        parsed = parse_pointer({"strength": 0.7, "damping": 65.0, "frequency": 8.0})
        self.assertEqual(parsed, PointerWobble())
        self.assertIs(type(parsed.damping), int)
        self.assertIs(type(parsed.frequency), int)
        for data in (
            {},
            {"strength": 1},
            {"strength": 1, "damping": 65, "frequency": 8, "shader": "x"},
            [],
            False,
        ):
            with self.subTest(data=data), self.assertRaises(ValueError):
                parse_pointer(data)

    def test_script_harness_uses_the_same_domain_contract(self):
        from scripts.lib.pointer_wobble import PointerWobble as HarnessWobble

        self.assertIs(HarnessWobble, PointerWobble)

    def test_overrides_cannot_mutate_builtin_presets(self):
        preset = PRESETS["gentle"]
        changed = replace(preset.wobble, strength=1.2)
        self.assertEqual(changed.strength, 1.2)
        self.assertEqual(preset.wobble.strength, 0.4)
        with self.assertRaises(FrozenInstanceError):
            preset.wobble.strength = 1.2
        with self.assertRaises(FrozenInstanceError):
            preset.name = "Changed"
        with self.assertRaises(TypeError):
            PRESETS["gentle"] = preset

    def test_checked_in_examples_match_validated_settings_and_explain_scope(self):
        paths = sorted((ROOT / "examples/experimental").glob("pointer-wobble-*.kdl"))
        self.assertEqual(len(paths), len(PRESETS))
        for name, preset in PRESETS.items():
            with self.subTest(name=name):
                source = (ROOT / f"examples/experimental/pointer-wobble-{name}.kdl").read_text()
                self.assertEqual(source, render_example(name))
                self.assertIn("stock Niri does not support", source)
                # Check the actual KDL separately from its explanatory comments.
                config = "\n".join(
                    line for line in source.splitlines() if not line.startswith("//")
                )
                self.assertTrue(config.startswith("animations {\n    window-movement {\n"))
                self.assertIn(render_node(preset.wobble).rstrip(), config)
                self.assertNotIn("custom-shader", config)
                self.assertNotIn("window-resize", config)


if __name__ == "__main__":
    unittest.main()
