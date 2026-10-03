from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

from niri_fragments.cli import parser, selected_effect
from niri_fragments.effects import Effect, FAMILIES, PRESETS, effect_document, shader, resize_shader, movement_shader
from niri_fragments.integration import custom_document, make_custom_preset, make_presets, merge_registry
from test_fragments import shell_registry


class FamilyTests(unittest.TestCase):
    def test_rebrand_preserves_every_v05_fragment_shader(self):
        # Captured from the signed v0.5.0 tag, independent of the current generator.
        expected = json.loads(Path(__file__).with_name("legacy-v0.5-shaders.json").read_text())
        for name, signatures in expected.items():
            effect = PRESETS[name]
            sources = {"open": shader(effect, True), "close": shader(effect, False),
                       "resize": resize_shader(effect), "movement": movement_shader(effect)}
            for kind, source in sources.items():
                self.assertEqual(hashlib.sha256(source.encode()).hexdigest(), signatures[kind], f"{name}/{kind}")

    def test_legacy_import_and_fragment_export_remain_schema_one(self):
        document = {"schema": 1, "name": "Old custom", "effect": {"gravity": "up", "resize": True}}
        name, _, effect = custom_document(document)
        self.assertEqual(effect.family, "fragments")
        exported = effect_document(name, effect)
        self.assertEqual(exported["schema"], 1)
        self.assertNotIn("family", exported["effect"])
        self.assertFalse(any(key.startswith("slice_") for key in exported["effect"]))
        self.assertEqual(custom_document(exported)[2], effect)

    def test_slice_document_round_trip_and_schema_gate(self):
        effect = replace(PRESETS["diagonal-shear"], slice_angle=-33.25, open_ms=721)
        document = effect_document("My slices", effect)
        self.assertEqual(document["schema"], 2)
        self.assertEqual(custom_document(document)[2], effect)
        with self.assertRaisesRegex(ValueError, "schema: 2"):
            custom_document(dict(document, schema=1))

    def test_unsupported_resize_and_movement_fail_explicitly(self):
        effect = PRESETS["slide-apart"]
        self.assertFalse(FAMILIES[effect.family]["resize"])
        for operation in (lambda: replace(effect, resize=True), lambda: resize_shader(effect), lambda: movement_shader(effect)):
            with self.assertRaisesRegex(ValueError, "does not support"):
                operation()

    def test_slice_validation_rejects_invalid_parameters(self):
        for options in ({"family": "unknown"}, {"family": []}, {"slice_count": 1}, {"slice_count": 49},
                        {"slice_count": 2.5}, {"slice_count": True}, {"slice_angle": 91},
                        {"slice_distance": float("nan")}, {"slice_distance": 601},
                        {"slice_stagger": .76}, {"slice_rotation": -61}, {"slice_direction": "typo"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                Effect(**options)

    def test_irrelevant_cli_options_are_not_silently_ignored(self):
        for arguments in (["--preset", "slide-apart", "--particles", "400"], ["--slice-count", "20"]):
            with self.assertRaisesRegex(ValueError, "do not apply"):
                selected_effect(parser().parse_args(["render", *arguments]))
        effect = selected_effect(parser().parse_args(["render", "--family", "slices", "--slice-count", "20"]))
        self.assertEqual(effect.slice_count, 20)

    def test_preset_identity_and_base_resize_survive_rebrand(self):
        registry = shell_registry()
        old = {"id": "niri-fragments-custom-keep", "generator": "niri-fragments", "name": "Keep", "effect": {"resize": True}}
        merged = merge_registry({"presets": [old]}, make_presets(registry))
        self.assertIn(old, merged["presets"])
        self.assertEqual(sum(p["id"] == "niri-fragments-balanced" for p in merged["presets"]), 1)
        custom = make_custom_preset(registry, effect_document("Slice custom", PRESETS["slide-apart"]))
        self.assertEqual(custom["id"], "niri-fragments-custom-slice-custom")
        self.assertEqual(custom["types"]["window-resize"], registry["presets"][0]["types"]["window-resize"])

    def test_new_and_legacy_module_commands_are_identical(self):
        arguments = ["render", "--preset", "diagonal-shear"]
        outputs = [subprocess.check_output([sys.executable, "-m", module, *arguments]) for module in ("niri_fx", "niri_fragments")]
        self.assertEqual(*outputs)


if __name__ == "__main__":
    unittest.main()
