"""Desktop timing must travel with profiles without enabling extra shader actions."""

import unittest
from copy import deepcopy

from helpers import shell_registry

from niri_fx.catalog import PROFILES
from niri_fx.documents import parse_document
from niri_fx.effects import animation_types, render_kdl
from niri_fx.integration import make_custom_preset
from niri_fx.motion import MOTION_PACKS


class DesktopMotionTests(unittest.TestCase):
    def test_finished_packs_round_trip_and_leave_resize_and_movement_unset(self):
        for key, motion in MOTION_PACKS.items():
            with self.subTest(key=key):
                profile = PROFILES[key + "-motion"]
                doc = profile.document("Desktop Motion")
                self.assertEqual(parse_document(doc)[2], profile)
                types = animation_types(profile)
                self.assertEqual(
                    types["workspace-switch"]["spring"],
                    list(motion.workspace.specification().values()),
                )
                self.assertNotIn("window-resize", types)
                self.assertNotIn("window-movement", types)
                self.assertIn("overview-open-close", render_kdl(profile))

    def test_invalid_springs_and_extra_fields_are_rejected(self):
        valid = PROFILES["gentle-motion"].document("Motion")
        for key, value in (
            ("stiffness", True),
            ("stiffness", float("nan")),
            ("damping_ratio", 1.1),
            ("epsilon", 0),
            ("unknown", 1),
        ):
            with self.subTest(key=key, value=value):
                doc = deepcopy(valid)
                doc["motion"]["camera"][key] = value
                with self.assertRaises(ValueError):
                    parse_document(doc)
        valid["motion"]["other"] = {}
        with self.assertRaises(ValueError):
            parse_document(valid)

    def test_shell_registration_changes_only_requested_timing_and_effects(self):
        base = shell_registry()
        saved = make_custom_preset(base, PROFILES["playful-motion"].document("Playful"))
        for key, value in base["presets"][0]["types"].items():
            if key not in {
                "window-open",
                "window-close",
                "workspace-switch",
                "horizontal-view-movement",
                "overview-open-close",
            }:
                self.assertEqual(saved["types"][key], value)
        self.assertEqual(saved["types"]["workspace-switch"]["spring"], [0.85, 650, 0.0001])
