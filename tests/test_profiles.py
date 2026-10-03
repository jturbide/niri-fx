import unittest
from dataclasses import replace

from helpers import shell_registry

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
from niri_fx.parameters import glsl_number
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
            {"open": None},
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
