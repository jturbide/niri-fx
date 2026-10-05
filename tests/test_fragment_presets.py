"""Native settings parity, validation and eligible experimental preset materials."""

import json
import re
import unittest
from dataclasses import FrozenInstanceError, asdict, replace
from pathlib import Path

from niri_fx.effects import PRESETS as EFFECT_PRESETS
from niri_fx.effects import fragment_motion_eligible, movement_shader
from niri_fx.fragment_motion import (
    CONTROLS,
    PRESETS,
    FragmentMotionSettings,
    parse_settings,
    render_node,
)

ROOT = Path(__file__).resolve().parents[1]


def native_config_source():
    # The shipped additive patch is available in CI; a private native checkout
    # or compiled compositor is deliberately not a unit-test prerequisite.
    patch = (ROOT / "experimental/niri-fragment-drag.patch").read_text()
    section = patch.split("\ndiff --git ", 1)[0]
    return "\n".join(
        line[1:]
        for line in section.splitlines()
        if line.startswith("+") and not line.startswith("+++")
    )


class FragmentPresetTests(unittest.TestCase):
    def test_tear_matches_native_defaults_and_accepted_square_material(self):
        source = native_config_source()
        match = re.search(
            r"impl Default for FragmentMotion\s*\{\s*fn default\(\) -> Self\s*\{\s*Self\s*\{(.*?)\n\s*\}",
            source,
            re.S,
        )
        self.assertIsNotNone(match, "native defaults were not found in the shipped patch")
        native = {}
        for name, value in re.findall(r"(\w+):\s*([^,\n]+),", match[1]):
            if value.startswith("FragmentRotation::"):
                native[name] = value.split("::")[1].lower()
            else:
                value = value.removeprefix("FloatOrInt(").removesuffix(")")
                native[name] = float(value) if "." in value else int(value)
        self.assertEqual(len(native), 18)
        self.assertEqual(asdict(PRESETS["tear"].settings), native)
        self.assertEqual(PRESETS["tear"].particles, 800)
        self.assertEqual(
            PRESETS["tear"].effect,
            replace(
                EFFECT_PRESETS["balanced"],
                fragment_shape="square",
                particles=800,
                spin=100,
                stagger=0.08,
                dispersion=0.65,
                movement_ms=350,
                movement_strength=0.48,
                movement_focus=0.65,
                scatter=100,
                gravity_strength=0.35,
            ),
        )

    def test_control_metadata_matches_native_types_and_bound_predicates(self):
        compact = re.sub(r"\s+", "", native_config_source())
        expected = {
            "batches": (1, 4096, "(1..=4096).contains(&self.batches)"),
            "delay_near_ms": (0, 600, "self.delay_near_ms<=self.delay_far_ms"),
            "delay_far_ms": (0, 600, "self.delay_far_ms<=600"),
            "response_near_ms": (20, 800, "(20..=800).contains(&self.response_near_ms)"),
            "response_far_ms": (
                20,
                800,
                "(self.response_near_ms..=800).contains(&self.response_far_ms)",
            ),
            "max_lag": (1, 1024, "(1..=1024).contains(&self.max_lag)"),
            "press_response_ms": (20, 800, "(20..=800).contains(&self.press_response_ms)"),
            "rotation_response_ms": (20, 800, "(20..=800).contains(&self.rotation_response_ms)"),
            "rotation_speed": (1, 5000, "(1..=5000).contains(&self.rotation_speed)"),
            "release_ms": (200, 2000, "(200..=2000).contains(&self.release_ms)"),
        }
        for name, (minimum, maximum, predicate) in expected.items():
            with self.subTest(name=name):
                control = CONTROLS[name]
                self.assertEqual(
                    (control.kind, control.minimum, control.maximum), ("integer", minimum, maximum)
                )
                self.assertIn(f"pub{name}:u32", compact)
                self.assertIn(predicate, compact)
        floats = {
            "delay_jitter": (0, 1),
            "response_jitter": (0, 1),
            "distance_exponent": (0, 4),
            "pin_radius": (0, 256),
            "press_spread": (0, 128),
            "rotation_degrees": (0, 60),
            "tilt": (0, 2),
        }
        for name, (minimum, native_type_maximum) in floats.items():
            control = CONTROLS[name]
            self.assertEqual(control.kind, "number")
            self.assertEqual(control.minimum, minimum)
            self.assertEqual(control.maximum, 1.1 if name == "tilt" else native_type_maximum)
            self.assertIn(f"pub{name}:FloatOrInt<{minimum},{native_type_maximum}>", compact)
        self.assertIn("self.distance_exponent.0>0.", compact)
        self.assertIn("self.tilt.0<=1.1", compact)
        self.assertTrue(CONTROLS["distance_exponent"].exclusive_min)
        self.assertEqual(CONTROLS["rotation_mode"].choices, ("movement", "random", "none"))
        self.assertEqual(set(CONTROLS), set(expected) | set(floats) | {"rotation_mode"})

    def test_every_numeric_control_rejects_invalid_values_and_accepts_boundaries(self):
        for name, control in CONTROLS.items():
            if control.kind == "choice":
                continue
            invalid = [
                False,
                True,
                None,
                "1",
                float("nan"),
                float("inf"),
                -float("inf"),
                10**1000,
                control.minimum - 1,
                control.maximum + 1,
            ]
            if control.kind == "integer":
                invalid.append(float(control.default))
            if control.exclusive_min:
                invalid.append(control.minimum)
            for value in invalid:
                with self.subTest(name=name, value=repr(value)[:30]):
                    with self.assertRaises(ValueError):
                        parse_settings({name: value})
            for value in (control.minimum if not control.exclusive_min else 1e-12, control.maximum):
                changes = {name: value}
                # Exercise the boundary rather than fail an unrelated pair rule.
                if name == "delay_near_ms":
                    changes["delay_far_ms"] = max(360, value)
                elif name == "delay_far_ms":
                    changes["delay_near_ms"] = 0
                elif name == "response_near_ms":
                    changes["response_far_ms"] = max(360, value)
                elif name == "response_far_ms":
                    changes["response_near_ms"] = min(120, value)
                with self.subTest(name=name, boundary=value):
                    self.assertEqual(getattr(parse_settings(changes), name), value)

    def test_pairings_choices_and_unknown_keys_are_explicit(self):
        for changes in (
            {"delay_near_ms": 401, "delay_far_ms": 400},
            {"response_near_ms": 401, "response_far_ms": 400},
            {"rotation_mode": "gravity"},
            {"rotation_mode": True},
            {"delay-far-ms": 360},
            {"schema": 1},
            {"enabled": True},
            {17: 1},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                parse_settings(changes)
        for value in (None, [], "tear"):
            with self.assertRaises(ValueError):
                parse_settings(value)
        for mode in CONTROLS["rotation_mode"].choices:
            self.assertEqual(parse_settings({"rotation_mode": mode}).rotation_mode, mode)
        self.assertEqual(parse_settings({}), FragmentMotionSettings())

    def test_kdl_export_is_ordered_complete_and_preserves_native_precision(self):
        settings = parse_settings({"distance_exponent": 1e-12, "press_spread": 0.0})
        node = render_node(settings)
        self.assertEqual(
            node, render_node(parse_settings(dict(reversed(asdict(settings).items()))))
        )
        self.assertTrue(node.startswith("        fragment-motion {\n"))
        exported = {}
        for line in node.splitlines()[1:-1]:
            name, value = line.strip().split(" ", 1)
            exported[name.replace("-", "_")] = json.loads(value)
        self.assertEqual(list(exported), list(CONTROLS))
        self.assertEqual(exported, asdict(settings))
        self.assertGreater(exported["distance_exponent"], 0)
        self.assertEqual(render_node(settings, indent=0).splitlines()[0], "fragment-motion {")
        self.assertEqual(render_node(replace(settings, press_spread=0)), node)
        for indent in (-1, True, "        "):
            with self.assertRaises(ValueError):
                render_node(settings, indent)
        with self.assertRaises(ValueError):
            render_node(asdict(settings))

    def test_presets_are_immutable_distinct_and_emit_supported_materials(self):
        self.assertEqual(tuple(PRESETS), ("gentle", "tear", "cascade"))
        self.assertEqual([preset.particles for preset in PRESETS.values()], [600, 800, 1200])
        for preset in PRESETS.values():
            self.assertTrue(fragment_motion_eligible(preset.effect))
            shader = movement_shader(preset.effect)
            self.assertIn("// nirifx-fragment-motion: 3\n", shader)
            self.assertRegex(shader, rf"// nirifx-fragment-grid: {preset.particles}\.0+ ")
            self.assertEqual(parse_settings(asdict(preset.settings)), preset.settings)
            with self.assertRaises(FrozenInstanceError):
                preset.settings.press_spread = 50
        for name in ("delay_far_ms", "response_far_ms", "press_spread", "rotation_degrees", "tilt"):
            values = [getattr(preset.settings, name) for preset in PRESETS.values()]
            self.assertEqual(values, sorted(set(values)), name)
        with self.assertRaises(TypeError):
            PRESETS["other"] = PRESETS["tear"]
        with self.assertRaises(TypeError):
            CONTROLS["other"] = CONTROLS["tilt"]
        with self.assertRaises(FrozenInstanceError):
            CONTROLS["tilt"].maximum = 2


if __name__ == "__main__":
    unittest.main()
