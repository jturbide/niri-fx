import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from niri_fx.cli import parser, selected_effect
from niri_fx.effects import PRESETS, movement_shader, resize_shader
from niri_fx.studio import make_server, preview_document


class RevealTests(unittest.TestCase):
    def test_ember_is_monochrome_and_frost_keeps_its_cool_palette(self):
        ember, frost = PRESETS["ember-erosion"], PRESETS["frost-vanish"]
        self.assertEqual(ember.edge_saturation, 0)
        self.assertEqual(ember.edge_brightness, 1)
        self.assertGreater(ember.edge_char, 0)
        self.assertGreater(frost.edge_saturation, 0)
        self.assertEqual(frost.edge_hue, 190)

    def test_palette_can_be_black_white_or_colored_through_cli(self):
        for saturation, brightness in ((0, 0), (0, 1), (1, 0.7)):
            effect = selected_effect(
                parser().parse_args(
                    [
                        "render",
                        "--preset",
                        "ember-erosion",
                        "--edge-saturation",
                        str(saturation),
                        "--edge-brightness",
                        str(brightness),
                        "--edge-hue",
                        "25",
                    ]
                )
            )
            self.assertEqual(effect.edge_saturation, saturation)
            self.assertEqual(effect.edge_brightness, brightness)
        with self.assertRaisesRegex(ValueError, "do not apply"):
            selected_effect(parser().parse_args(["render", "--edge-saturation", "0"]))

    def test_new_families_never_enable_unavailable_actions(self):
        for name in ("pixel-wipe", "ghost-wisps", "shockwave"):
            effect = PRESETS[name]
            self.assertFalse(effect.resize)
            for render in (resize_shader, movement_shader):
                with (
                    self.subTest(preset=name),
                    self.assertRaisesRegex(ValueError, "does not support"),
                ):
                    render(effect)

    def test_studio_targets_are_explicit_and_auto_requires_an_installed_helper(self):
        # The selection affects the first UI save action, never compositor config.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = Namespace(
                port=0, preset="balanced", inir_root=root, registry=root / "presets.json"
            )
            for target, installed in (("standalone", False), ("noctalia", False), ("inir", True)):
                if installed:
                    helper = root / "scripts/niri-config.py"
                    helper.parent.mkdir()
                    helper.write_text("# fixture\n")
                args.target = "auto" if target != "noctalia" else "noctalia"
                with make_server(args, PRESETS["balanced"]) as server:
                    self.assertEqual(server.save_target, target)
            self.assertFalse((root / "presets.json").exists())
        html = preview_document(PRESETS["balanced"])
        self.assertIn('"save_target": "standalone"', html)
        self.assertNotIn("@FAMILY_OPTIONS@", html)
        for family in ("pixels", "wisps", "distortion"):
            self.assertIn(f'<option value="{family}">', html)
