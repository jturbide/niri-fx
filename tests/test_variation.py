import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from niri_fx.cli import parser, selected_effect
from niri_fx.effects import PRESETS, Effect, movement_shader, shader
from niri_fx.pack import plan_pack
from niri_fx.setup import apply_plan, restore


class VariationTests(unittest.TestCase):
    def test_alternating_slices_and_outward_curtain_are_distinct(self):
        self.assertEqual(PRESETS["slide-apart"].slice_direction, "alternate")
        self.assertEqual(PRESETS["split-curtain"].slice_direction, "outward")

    def test_invalid_and_inapplicable_controls_are_rejected(self):
        for field, value in (
            ("wave_strength", 1.01),
            ("wave_frequency", 0),
            ("wave_speed", -1),
            ("size_variation", float("nan")),
            ("direction_variation", True),
            ("slice_order", "typo"),
            ("slice_travel_variation", 2),
            ("slice_rotation_variation", -1),
            ("elastic_axis", []),
            ("elastic_frequency", 0),
            ("elastic_damping", 9),
            ("fragment_roundness", -0.01),
            ("fragment_shrink", 1.1),
            ("slice_pivot", -1.1),
            ("slice_collapse", True),
            ("elastic_twist", 91),
            ("elastic_stretch", float("inf")),
            ("elastic_ripple", 0),
            ("elastic_anchor", []),
            ("elastic_anchor", "missing"),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                Effect(**{field: value})
        for options in (
            ["--preset", "spring-wobble", "--particles", "400"],
            ["--preset", "slide-apart", "--elastic-strength", ".5"],
            ["--slice-order", "random"],
            ["--preset", "jelly", "--fragment-shrink", "0.5"],
            ["--preset", "slide-apart", "--fragment-roundness", "1"],
            ["--slice-pivot", "-1"],
            ["--elastic-anchor", "top-left"],
        ):
            with self.assertRaises(ValueError):
                selected_effect(parser().parse_args(["render", *options]))

    def test_waves_and_elastic_movement_route_to_distinct_renderers(self):
        self.assertNotEqual(
            shader(Effect(), False), shader(replace(Effect(), wave_strength=1), False)
        )
        self.assertIn("fragments_wave", movement_shader(PRESETS["crosswind"]))
        wobble = movement_shader(PRESETS["spring-wobble"])
        self.assertIn("niri_move_impulse", wobble)
        self.assertIn("niri_clamped_progress, 0.0, impulse", wobble)
        self.assertNotIn("fragments_color", wobble)
        self.assertNotIn("niri_move_impulse", shader(PRESETS["spring-wobble"], False))


class PackTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.output, self.state = self.root / "presets", self.root / "state"

    def tearDown(self):
        self.directory.cleanup()

    def test_preview_apply_idempotence_and_exact_restore(self):
        plan = plan_pack(self.output)
        self.assertFalse(self.output.exists())
        self.assertEqual(len(plan["changes"]), len(PRESETS) + 1)
        self.output.mkdir()
        foreign = self.output / "another-provider.kdl"
        foreign.write_text("animations {}\n")
        apply_plan(plan, self.state)
        self.assertEqual(len(list(self.output.glob("nirifx-*.kdl"))), len(PRESETS))
        self.assertFalse(plan_pack(self.output)["changes"])
        self.assertTrue(
            all(
                "window-resize" not in path.read_text() for path in self.output.glob("nirifx-*.kdl")
            )
        )
        restore(self.state, apply=True)
        self.assertEqual(list(self.output.iterdir()), [foreign])

    def test_collision_or_user_edit_blocks_all_pack_updates(self):
        self.output.mkdir()
        collision = self.output / "nirifx-balanced.kdl"
        collision.write_text("// mine\n")
        with self.assertRaisesRegex(ValueError, "unowned"):
            plan_pack(self.output)
        self.assertEqual(collision.read_text(), "// mine\n")
        collision.unlink()
        apply_plan(plan_pack(self.output), self.state)
        collision.write_text("// later edit\n")
        with self.assertRaisesRegex(ValueError, "changed"):
            plan_pack(self.output)
        with self.assertRaisesRegex(ValueError, "changed"):
            restore(self.state, apply=True)
        self.assertEqual(collision.read_text(), "// later edit\n")

    def test_symlinks_and_manifest_traversal_never_write_outside_pack(self):
        self.output.mkdir()
        external = self.root / "external.kdl"
        external.write_text("// untouched\n")
        path = self.output / "nirifx-balanced.kdl"
        path.symlink_to(external)
        with self.assertRaises(ValueError):
            plan_pack(self.output)
        path.unlink()
        (self.output / ".nirifx-pack.json").write_text(
            json.dumps({"schema": 1, "files": {"../external.kdl": "fake"}})
        )
        with self.assertRaisesRegex(ValueError, "entry"):
            plan_pack(self.output)
        self.assertEqual(external.read_text(), "// untouched\n")


if __name__ == "__main__":
    unittest.main()
