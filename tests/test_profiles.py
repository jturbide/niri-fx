import unittest
from dataclasses import replace

from helpers import shell_registry

from niri_fx.catalog import PROFILES
from niri_fx.documents import effect_document, parse_document
from niri_fx.effects import (
    PARAMETERS,
    PRESETS,
    Effect,
    animation_types,
    render_kdl,
    shader,
)
from niri_fx.integration import make_custom_preset
from niri_fx.motion import MOTION_PACKS
from niri_fx.parameters import glsl_number
from niri_fx.pointer import PointerWobble
from niri_fx.profiles import Profile


class ProfileTests(unittest.TestCase):
    def test_independent_actions_generate_their_own_shaders_and_durations(self):
        profile = Profile(PRESETS["spring-wobble"], PRESETS["core-detonation"])
        types = animation_types(profile)
        for action, effect in (("open", profile.open), ("close", profile.close)):
            self.assertEqual(
                types[f"window-{action}"]["custom-shader"], shader(effect, action == "open")
            )
            self.assertEqual(
                types[f"window-{action}"]["duration-ms"], getattr(effect, action + "_ms")
            )
        self.assertNotIn("window-resize", render_kdl(profile))
        self.assertEqual(parse_document(effect_document("My Profile", profile))[2], profile)

    def test_registration_preserves_base_resize_and_unrelated_actions(self):
        profile = Profile(
            PRESETS["iris-bloom"], PRESETS["ember-erosion"], movement=PRESETS["spring-wobble"]
        )
        base = shell_registry()
        saved = make_custom_preset(base, profile.document("My Profile"))
        for action in ("workspace-switch", "window-resize"):
            self.assertEqual(saved["types"][action], base["presets"][0]["types"][action])
        self.assertNotIn("window-movement", saved["types"])
        explicit = replace(profile, resize=replace(PRESETS["balanced"], resize_mode="edge"))
        self.assertIn("window-resize", animation_types(explicit))

    def test_profile_validation_rejects_ambiguous_or_unsupported_actions(self):
        profile = Profile(Effect(), Effect())
        for changes in (
            {"open": False},
            {"close": []},
            {"resize": PRESETS["iris-bloom"]},
            {"movement": PRESETS["noise-dissolve"]},
            {"open": Effect(resize=True)},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(profile, **changes)
        for action in ("unknown", "open"):
            document = profile.document("Valid")
            document["actions"][action] = {"injected": 1}
            with self.assertRaises(ValueError):
                parse_document(document)

    def test_catalog_defines_validation_and_rounding_boundaries(self):
        for name, spec in PARAMETERS.items():
            if spec["type"] == "number":
                with self.subTest(name=name), self.assertRaises(ValueError):
                    Effect(**{name: spec["limits"][1] + 1})
        self.assertEqual(glsl_number(0.0078125), "0.007813")
        self.assertEqual(glsl_number(-0.0078125), "-0.007813")
        self.assertEqual(glsl_number(-0.0000001), "0.000000")


class PointerProfileTests(unittest.TestCase):
    def test_pointer_inherits_when_omitted_or_null_and_builtins_never_opt_in(self):
        profile = Profile(Effect(), Effect())
        self.assertNotIn("pointer", profile.document("Plain"))
        document = {**profile.document("Plain"), "pointer": None}
        self.assertEqual(parse_document(document)[2], profile)
        self.assertTrue(all(profile.pointer is None for profile in PROFILES.values()))
        for invalid in ({}, True, Effect()):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(ValueError, "pointer"):
                replace(profile, pointer=invalid)

    def test_explicit_disabled_and_enabled_pointer_round_trip_without_stock_activation(self):
        for strength in (0, 0.7, 2):
            profile = Profile(Effect(), Effect(), pointer=PointerWobble(strength))
            document = profile.document("Pointer combo")
            self.assertEqual(document["pointer"]["strength"], strength)
            self.assertEqual(parse_document(document)[2], profile)
            self.assertNotIn("window-movement", animation_types(profile))
            self.assertNotIn("pointer-wobble", render_kdl(profile))
            saved = make_custom_preset(shell_registry(), document)
            self.assertNotIn("pointer-wobble", str(saved["types"]))

    def test_native_export_composes_a_single_movement_block_and_preserves_other_springs(self):
        for movement in (False, True):
            profile = Profile(
                Effect(),
                Effect(),
                movement=Effect(),
                pointer=PointerWobble(0.0078125),
                motion=MOTION_PACKS["gentle"],
            )
            exported = animation_types(profile, movement=movement, pointer=True)
            self.assertEqual(exported["window-movement"]["pointer-wobble"]["damping"], 65)
            self.assertEqual("custom-shader" in exported["window-movement"], movement)
            for name, spec in profile.motion.animation_types().items():
                self.assertEqual(exported[name], spec)
            kdl = render_kdl(profile, movement=movement, pointer=True)
            self.assertEqual(kdl.count("    window-movement {"), 1)
            self.assertEqual(kdl.count("pointer-wobble {"), 1)
            self.assertIn("strength 0.007813", kdl)
            self.assertNotIn("window-resize", kdl)

    def test_opt_in_requires_an_explicit_profile_override(self):
        for profile in (Effect(), Profile(Effect(), Effect())):
            with (
                self.subTest(profile=profile),
                self.assertRaisesRegex(ValueError, "explicitly choose pointer"),
            ):
                render_kdl(profile, pointer=True)
