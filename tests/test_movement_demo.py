"""Profile boundaries in the isolated movement launcher, without starting Niri."""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from niri_fx.effects import PRESETS, render_kdl
from niri_fx.profiles import Profile

ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    spec = importlib.util.spec_from_file_location("movement_demo", ROOT / "scripts/nested-demo.py")
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    recorder_spec = importlib.util.spec_from_file_location(
        "movement_recorder", ROOT / "scripts/record-native-gif.py"
    )
    recorder = importlib.util.module_from_spec(recorder_spec)
    recorder_spec.loader.exec_module(recorder)


class MovementDemoTests(unittest.TestCase):
    def test_recorder_preserves_profile_actions_and_requires_public_explicit_movement(self):
        from niri_fx.action_sets import ACTION_SETS

        for name, recipe in ACTION_SETS.items():
            source = ROOT / f"examples/profiles/{name}-native.json"
            document, effect, relative, duration = recorder.selection(custom=source)
            self.assertEqual(document, recipe.profile(include_resize=True, include_movement=True))
            self.assertEqual(effect, recipe.movement)
            self.assertEqual(relative, str(source.relative_to(ROOT)))
            self.assertEqual(duration, recipe.movement.movement_ms)
            with self.assertRaisesRegex(ValueError, "explicitly include"):
                recorder.selection(custom=ROOT / f"examples/profiles/{name}.json")
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "private.json"
            source.write_text(json.dumps(document.document("Private")))
            with self.assertRaises(ValueError):
                recorder.selection(custom=source)
        self.assertEqual(recorder.selection()[3], 1200)
        self.assertEqual(recorder.selection(duration=500)[3], 500)

    def args(self):
        return SimpleNamespace(custom=None, preset=None, movement_strength=None, resize=False)

    def test_style_defaults_leave_resize_disabled(self):
        document, movement = demo.selection(self.args())
        self.assertEqual(document, PRESETS["explosion"])
        self.assertEqual(document, movement)
        self.assertNotIn("window-resize", render_kdl(document))

    def test_movement_override_preserves_other_profile_actions(self):
        profile = Profile(
            PRESETS["frost-vanish"], PRESETS["pixelate"], movement=PRESETS["fragment-wake"]
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "profile.json"
            path.write_text(json.dumps(profile.document("Independent motion")))
            args = self.args()
            args.custom, args.movement_strength = path, 0.2
            document, movement = demo.selection(args)
        self.assertEqual(document, profile)
        self.assertEqual(movement.movement_strength, 0.2)
        self.assertEqual(movement.movement_ms, 850)
        self.assertEqual(movement.fragment_shape, "triangle")
        self.assertNotIn("window-movement", render_kdl(document))

    def test_unset_movement_is_rejected_before_launch(self):
        profile = Profile(PRESETS["balanced"], PRESETS["balanced"])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "profile.json"
            path.write_text(json.dumps(profile.document("Stock only")))
            args = self.args()
            args.custom = path
            with self.assertRaisesRegex(ValueError, "explicitly include a movement"):
                demo.selection(args)

    def test_unsupported_resize_is_rejected_before_launch(self):
        args = self.args()
        args.preset, args.resize = "pixel-transfer", True
        with self.assertRaisesRegex(ValueError, "does not support resize"):
            demo.selection(args)
