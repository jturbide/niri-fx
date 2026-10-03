import unittest
from dataclasses import replace

from test_fragments import shell_registry

from niri_fx.cli import parser, selected_effect
from niri_fx.effects import (
    FAMILIES,
    PRESETS,
    Effect,
    effect_document,
    movement_shader,
    resize_shader,
)
from niri_fx.integration import custom_document, make_custom_preset, make_presets, merge_registry


class FamilyTests(unittest.TestCase):
    def test_every_family_uses_the_current_preset_document(self):
        for name, effect in PRESETS.items():
            with self.subTest(preset=name):
                document = effect_document(name, effect)
                self.assertEqual(document["schema"], 3)
                self.assertEqual(custom_document(document)[2], effect)
                self.assertEqual(document["effect"]["family"], effect.family)
        for version in (1, 2, 4, True, 3.0):
            with self.subTest(schema=version), self.assertRaisesRegex(ValueError, "schema: 3"):
                custom_document({"schema": version, "name": "Unsupported", "effect": {}})

    def test_unsupported_resize_and_movement_fail_explicitly(self):
        effect = PRESETS["slide-apart"]
        self.assertFalse(FAMILIES[effect.family]["resize"])
        for operation in (
            lambda: replace(effect, resize=True),
            lambda: resize_shader(effect),
            lambda: movement_shader(effect),
        ):
            with self.assertRaisesRegex(ValueError, "does not support"):
                operation()

    def test_slice_validation_rejects_invalid_parameters(self):
        for options in (
            {"family": "unknown"},
            {"family": []},
            {"slice_count": 1},
            {"slice_count": 49},
            {"slice_count": 2.5},
            {"slice_count": True},
            {"slice_angle": 91},
            {"slice_distance": float("nan")},
            {"slice_distance": 601},
            {"slice_stagger": 0.76},
            {"slice_rotation": -61},
            {"slice_direction": "typo"},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                Effect(**options)

    def test_irrelevant_cli_options_are_not_silently_ignored(self):
        for arguments in (
            ["--preset", "slide-apart", "--particles", "400"],
            ["--slice-count", "20"],
        ):
            with self.assertRaisesRegex(ValueError, "do not apply"):
                selected_effect(parser().parse_args(["render", *arguments]))
        effect = selected_effect(
            parser().parse_args(["render", "--family", "slices", "--slice-count", "20"])
        )
        self.assertEqual(effect.slice_count, 20)

    def test_pack_refresh_preserves_customs_and_base_resize(self):
        registry = shell_registry()
        old = {
            "id": "niri-fx-custom-keep",
            "generator": "niri-fx",
            "name": "Keep",
            "effect": {"resize": True},
        }
        merged = merge_registry({"presets": [old]}, make_presets(registry))
        self.assertIn(old, merged["presets"])
        self.assertEqual(sum(p["id"] == "niri-fx-balanced" for p in merged["presets"]), 1)
        custom = make_custom_preset(
            registry, effect_document("Slice custom", PRESETS["slide-apart"])
        )
        self.assertEqual(custom["id"], "niri-fx-custom-slice-custom")
        self.assertEqual(
            custom["types"]["window-resize"], registry["presets"][0]["types"]["window-resize"]
        )


if __name__ == "__main__":
    unittest.main()
