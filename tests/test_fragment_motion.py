"""Square mesh eligibility, metadata and portable timed export contract."""

import re
import unittest
from dataclasses import replace

from niri_fx.effects import (
    PRESETS,
    _expand,
    fragment_motion_eligible,
    movement_shader,
    renderer_name,
    shader_templates,
)


class FragmentMotionTests(unittest.TestCase):
    def test_only_supported_square_material_advertises_continuous_motion(self):
        base = replace(PRESETS["balanced"], particles=800)
        self.assertTrue(fragment_motion_eligible(base))
        for changes in (
            {"movement_strength": 0},
            {"family": "elastic"},
            {"fragment_shape": "triangle"},
            {"fragment_secondary": "circle", "fragment_mix": 0.5},
            {"fragment_orientation": 10},
            {"fragment_roundness": 0.2},
            {"fragment_shrink": 0.2},
            {"size_variation": 0.2},
            {"direction_variation": 0.2},
            {"wave_strength": 0.2},
            {"rotation": "gravity"},
            {"release": "left"},
        ):
            with self.subTest(changes=changes):
                effect = replace(base, **changes)
                self.assertFalse(fragment_motion_eligible(effect))
                self.assertEqual(
                    movement_shader(effect),
                    _expand(shader_templates()[f"move-{renderer_name(effect)}"], effect, False),
                )
        for changes in (
            {"fragment_shape": "circle", "fragment_secondary": "square", "fragment_mix": 1},
            {"fragment_aspect": 4},  # Aspect does not alter square cells.
            {"rotation": "none"},
        ):
            self.assertTrue(fragment_motion_eligible(replace(base, **changes)))

    def test_marker_and_bounded_grid_metadata_match_effect(self):
        for particles, tile in ((0, 8), (800, 28), (4096, 128)):
            source = movement_shader(
                replace(PRESETS["balanced"], particles=particles, tile_size=tile)
            )
            self.assertIn("// nirifx-fragment-motion: 3\n", source)
            match = re.search(r"^// nirifx-fragment-grid: (\S+) (\S+)$", source, re.M)
            self.assertIsNotNone(match)
            self.assertEqual(tuple(map(float, match.groups())), (particles, tile))
            self.assertIn("#ifdef NIRIFX_FRAGMENT_MESH", source)
            self.assertIn("fragment_motion_mesh_color", source)

    def test_mesh_addition_preserves_exact_timed_entry(self):
        for name in ("balanced", "pixel-explosion", "pixel-implosion"):
            if name not in PRESETS:
                continue
            effect = PRESETS[name]
            if not fragment_motion_eligible(effect):
                continue
            source = movement_shader(effect)
            original = _expand(shader_templates()[f"move-{renderer_name(effect)}"], effect, False)
            entry = "vec4 move_color("
            self.assertEqual(source[source.index(entry) :], original[original.index(entry) :])
            self.assertNotIn("niri_fragment_lag", source)
            self.assertNotIn("niri_fragment_active", source)


if __name__ == "__main__":
    unittest.main()
