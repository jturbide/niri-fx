"""Action capabilities, independent profiles and new control validation."""

import json
import unittest
from dataclasses import replace

from niri_fx.cli import parser, selected_effect
from niri_fx.documents import MAX_DOCUMENT_BYTES, parse_document
from niri_fx.effects import PRESETS, animation_types, movement_shader, resize_shader
from niri_fx.profiles import Profile


class ExpandedMotionTests(unittest.TestCase):
    def test_resize_families_require_explicit_opt_in(self):
        for name in ("balanced", "spring-wobble", "slice-exchange", "ripple-collapse"):
            effect = PRESETS[name]
            self.assertNotIn("window-resize", animation_types(effect))
            enabled = replace(effect, resize=True)
            self.assertEqual(
                animation_types(enabled)["window-resize"]["custom-shader"], resize_shader(effect)
            )
            selected = selected_effect(
                parser().parse_args(
                    ["render", "--preset", name, "--resize", "--resize-strength", "0.4"]
                )
            )
            self.assertTrue(selected.resize)
            self.assertEqual(selected.resize_strength, 0.4)
        self.assertTrue(all(not effect.resize for effect in PRESETS.values()))

    def test_new_movement_styles_are_never_emitted_by_stock_export(self):
        for name in ("slice-exchange", "pixel-transfer", "soft-phase"):
            effect = PRESETS[name]
            self.assertIn("vec4 move_color", movement_shader(effect))
            self.assertNotIn("vec4 open_color", movement_shader(effect))
            self.assertNotIn("window-movement", animation_types(effect))

    def test_full_profile_remains_within_document_limit(self):
        profile = Profile(
            PRESETS["hexagon-burst"],
            PRESETS["ink-spread"],
            resize=PRESETS["ripple-collapse"],
            movement=PRESETS["pixel-transfer"],
        )
        document = profile.document("Four independent actions")
        self.assertLess(len(json.dumps(document, indent=2).encode()), MAX_DOCUMENT_BYTES)
        self.assertEqual(parse_document(document)[2], profile)

    def test_new_controls_validate_and_round_trip_through_cli(self):
        for preset, option, value, field in (
            ("hexagon-burst", "--hex-size", "32", "hex_size"),
            ("ink-spread", "--dissolve-turbulence", "0.8", "dissolve_turbulence"),
            ("signal-glitch", "--glitch-chroma", "0.5", "glitch_chroma"),
            ("pixel-transfer", "--movement-strength", "0.4", "movement_strength"),
        ):
            with self.subTest(preset=preset):
                effect = selected_effect(
                    parser().parse_args(["render", "--preset", preset, option, value])
                )
                self.assertEqual(getattr(effect, field), float(value))
                with self.assertRaises(ValueError):
                    replace(effect, **{field: float("nan")})
