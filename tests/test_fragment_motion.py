"""Square mesh eligibility, metadata and portable timed export contract."""

import re
import unittest
from dataclasses import asdict, replace

from niri_fx.effects import (
    PRESETS,
    _expand,
    fragment_motion_eligible,
    movement_shader,
    renderer_name,
    shader_templates,
)
from niri_fx.fragment_motion import (
    CONTROLS,
    FragmentMotionSettings,
    fragment_documents,
    parse_fragment_motion,
    parse_settings,
)
from niri_fx.fragment_motion import PRESETS as FRAGMENT_PRESETS
from niri_fx.preview import preview_catalog


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


class PortableFragmentResponseTests(unittest.TestCase):
    def test_portable_response_is_complete_and_normalizes_json_integer_values(self):
        original = asdict(FragmentMotionSettings())
        document = {
            name: float(value) if CONTROLS[name].kind == "integer" else value
            for name, value in original.items()
        }
        self.assertEqual(parse_fragment_motion(document), FragmentMotionSettings())
        self.assertTrue(type(document["batches"]) is float)
        self.assertTrue(type(parse_fragment_motion(document).batches) is int)
        with self.assertRaises(ValueError):
            parse_settings(document)
        self.assertIsNone(parse_fragment_motion(None))
        for invalid in (
            {},
            False,
            [],
            "tear",
            original | {"unknown": 1},
            {name: value for name, value in original.items() if name != "batches"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_fragment_motion(invalid)

    def test_portable_numeric_bounds_ordering_and_choices_are_not_coerced(self):
        defaults = asdict(FragmentMotionSettings())
        for boundary in ("minimum", "maximum"):
            document = {
                name: control.default
                if control.kind == "choice"
                else 1e-12
                if boundary == "minimum" and control.exclusive_min
                else getattr(control, boundary)
                for name, control in CONTROLS.items()
            }
            self.assertEqual(asdict(parse_fragment_motion(document)), document)
        for name, control in CONTROLS.items():
            invalid = [False, None, "1", float("nan"), float("inf"), 10**1000]
            if control.kind == "choice":
                invalid.append("gravity")
            else:
                invalid.extend((control.minimum - 1, control.maximum + 1))
                if control.kind == "integer":
                    invalid.append(control.default + 0.5)
                if control.exclusive_min:
                    invalid.append(control.minimum)
            for value in invalid:
                with self.subTest(name=name, value=repr(value)[:20]), self.assertRaises(ValueError):
                    parse_fragment_motion(defaults | {name: value})
        for changes in (
            {"delay_near_ms": 301, "delay_far_ms": 300},
            {"response_near_ms": 301, "response_far_ms": 300},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                parse_fragment_motion(defaults | changes)

    def test_browser_catalog_expands_starting_points_without_shared_mutable_values(self):
        documents = fragment_documents()
        catalog = preview_catalog(PRESETS["balanced"])
        self.assertEqual(catalog["fragment_presets"], documents)
        self.assertEqual(
            catalog["fragment_controls"],
            {name: asdict(control) for name, control in CONTROLS.items()},
        )
        for name, preset in FRAGMENT_PRESETS.items():
            self.assertEqual(documents[name]["effect"], asdict(preset.effect))
            self.assertEqual(parse_fragment_motion(documents[name]["settings"]), preset.settings)
        documents["tear"]["settings"]["batches"] = 1
        documents["tear"]["effect"]["particles"] = 16
        self.assertEqual(fragment_documents()["tear"]["settings"]["batches"], 64)
        self.assertEqual(fragment_documents()["tear"]["effect"]["particles"], 800)


if __name__ == "__main__":
    unittest.main()
