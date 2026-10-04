"""Profile boundaries in the isolated movement launcher, without starting Niri."""

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from niri_fx.effects import PRESETS, render_kdl
from niri_fx.pointer import PointerWobble
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
        return SimpleNamespace(
            custom=None,
            preset=None,
            movement_strength=None,
            duration_ms=None,
            pointer_wobble=None,
            resize=False,
        )

    def test_style_defaults_leave_resize_disabled(self):
        document, movement = demo.selection(self.args())
        self.assertEqual(document, PRESETS["explosion"])
        self.assertEqual(document, movement)
        self.assertNotIn("window-resize", render_kdl(document))

    def test_pointer_demo_is_explicit_and_needs_no_timed_shader(self):
        from scripts.lib.pointer_wobble import PRESETS as POINTER_PRESETS

        args = self.args()
        args.pointer_wobble = "gentle"
        document, movement = demo.selection(args)
        self.assertEqual(document, PRESETS["momentum-glide"])
        self.assertIsNone(movement)
        ordinary = demo.config(document, 250, None)
        selected = demo.config(document, 250, None, pointer_wobble=POINTER_PRESETS["gentle"].wobble)
        self.assertNotIn("pointer-wobble", ordinary)
        self.assertIn("pointer-wobble", selected)
        self.assertNotIn("window-resize", selected)
        # Open/close shaders remain; the pointer hook requires no movement one.
        movement = selected.split("window-movement {", 1)[1]
        self.assertNotIn("custom-shader", movement)

    def test_custom_pointer_only_profile_is_resolved_without_a_timed_shader(self):
        profile = Profile(
            PRESETS["frost-vanish"], PRESETS["pixelate"], pointer=PointerWobble(0.4, 85, 10)
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "profile.json"
            path.write_text(json.dumps(profile.document("Pointer only")))
            args = self.args()
            args.custom = path
            document, movement = demo.selection(args)
            self.assertEqual(document, profile)
            self.assertIsNone(movement)
            pointer = demo.pointer_selection(args, document)
            self.assertEqual(pointer, profile.pointer)
            generated = demo.config(document, 250, None, pointer_wobble=pointer)
            self.assertIn("strength 0.4", generated)
            self.assertNotIn("custom-shader", generated.split("window-movement {", 1)[1])
            args.pointer_wobble = "rubber-sheet"
            self.assertEqual(demo.selection(args)[0], profile)
            self.assertEqual(
                demo.pointer_selection(args, document), demo.POINTER_PRESETS["rubber-sheet"].wobble
            )
            for field, value in (("duration_ms", 500), ("movement_strength", 0.2)):
                args = self.args()
                args.custom = path
                setattr(args, field, value)
                with (
                    self.subTest(field=field),
                    self.assertRaisesRegex(ValueError, "explicit timed movement"),
                ):
                    demo.selection(args)

    def test_profile_can_combine_pointer_and_timed_movement_without_rewriting_either(self):
        profile = Profile(
            PRESETS["frost-vanish"],
            PRESETS["pixelate"],
            movement=PRESETS["fragment-wake"],
            pointer=PointerWobble(strength=0),
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "profile.json"
            path.write_text(json.dumps(profile.document("Combined")))
            args = self.args()
            args.custom = path
            document, movement = demo.selection(args)
            self.assertEqual(document, profile)
            self.assertEqual(movement, profile.movement)
            self.assertEqual(demo.pointer_selection(args, document), profile.pointer)

    def test_custom_pointer_demo_chooses_its_isolated_build_and_floating_fixtures(self):
        profile = Profile(PRESETS["frost-vanish"], PRESETS["pixelate"], pointer=PointerWobble())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "profile.json"
            path.write_text(json.dumps(profile.document("Custom pointer")))
            with (
                patch.object(sys, "argv", ["nested-demo.py", "--custom", str(path)]),
                patch.object(
                    demo, "experiment", return_value=(Path("/isolated/niri"), {}, None)
                ) as build,
                patch.object(demo, "NestedSession") as nested,
                patch.object(demo, "launch_cards", return_value=[{"id": 1}, {"id": 2}]) as clients,
                redirect_stdout(io.StringIO()) as output,
            ):
                demo.main()
            build.assert_called_once_with(pointer_wobble=True)
            session = nested.return_value.__enter__.return_value
            clients.assert_called_once_with(session, pointer_wobble=True)
            self.assertEqual(
                session.msg.call_args_list[0].args,
                ("action", "move-window-to-floating", "--id", "1"),
            )
            self.assertIn("pointer-wobble", nested.call_args.args[0])
            self.assertNotIn(
                "custom-shader", nested.call_args.args[0].split("window-movement {", 1)[1]
            )
            self.assertIn("Custom profile settings", output.getvalue())
            session.compositor.wait.assert_called_once_with()

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
