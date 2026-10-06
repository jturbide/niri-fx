import unittest
from dataclasses import asdict, replace

from helpers import shell_registry

from niri_fx.catalog import PROFILES
from niri_fx.documents import effect_document, parse_document
from niri_fx.effects import (
    PARAMETERS,
    PRESETS,
    Effect,
    animation_types,
    movement_shader,
    render_kdl,
    shader,
)
from niri_fx.fragment_motion import PRESETS as FRAGMENT_PRESETS
from niri_fx.fragment_motion import FragmentMotionSettings
from niri_fx.integration import make_custom_preset
from niri_fx.motion import MOTION_PACKS
from niri_fx.parameters import glsl_number
from niri_fx.pointer import PointerWobble
from niri_fx.profiles import Profile


class ProfileTests(unittest.TestCase):
    def test_swap_override_round_trips_without_migrating_unchanged_profiles(self):
        previous = Profile(open=Effect(), movement=PRESETS["fragment-wake"])
        self.assertEqual(previous.document("Saved")["schema"], 2)
        self.assertNotIn("swap", previous.document("Saved")["actions"])
        for choice in (PRESETS["pixel-relay"], "off"):
            with self.subTest(choice=choice):
                profile = replace(previous, swap=choice)
                doc = profile.document("Saved")
                self.assertEqual(doc["schema"], 3)
                self.assertEqual(parse_document(doc)[2], profile)
                self.assertNotIn("window-swap", animation_types(profile))
                native = animation_types(profile, movement=True, swap=True)
                self.assertEqual(
                    native["window-movement"]["custom-shader"], movement_shader(previous.movement)
                )
                if choice == "off":
                    self.assertEqual(native["window-swap"], {"off": True})
                else:
                    self.assertEqual(native["window-swap"]["duration-ms"], choice.movement_ms)
                    self.assertEqual(
                        native["window-swap"]["custom-shader"],
                        movement_shader(choice, continuous_fragments=False),
                    )
        kept = previous.document("Saved")
        kept["schema"] = 3
        kept["actions"]["swap"] = None
        self.assertEqual(parse_document(kept)[2].document("Saved"), previous.document("Saved"))
        kept["schema"] = 2
        with self.assertRaises(ValueError):
            parse_document(kept)
        with self.assertRaises(ValueError):
            Profile(swap=PRESETS["frost-vanish"])

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


class FragmentResponseProfileTests(unittest.TestCase):
    def test_explicit_response_keeps_all_five_actions_and_survives_dormant_choices(self):
        for preset in FRAGMENT_PRESETS.values():
            for movement in (
                None,
                "off",
                replace(preset.effect, fragment_shape="triangle"),
                preset.effect,
            ):
                with self.subTest(preset=preset.name, movement=movement):
                    profile = Profile(movement=movement, fragment_motion=preset.settings)
                    document = profile.document("Portable response")
                    self.assertEqual(document["schema"], 4)
                    self.assertEqual(
                        set(document["actions"]), {"open", "close", "resize", "movement", "swap"}
                    )
                    self.assertIsNone(document["actions"]["swap"])
                    self.assertEqual(document["fragment_motion"], asdict(preset.settings))
                    self.assertEqual(parse_document(document)[2], profile)
                    self.assertEqual(
                        parse_document(document)[2].document(document["name"]), document
                    )
                    cleared = replace(profile, fragment_motion=None)
                    self.assertEqual(cleared.document("Timed")["schema"], 2)
                    self.assertEqual(replace(cleared, swap="off").document("Timed")["schema"], 3)

    def test_only_schema_four_accepts_complete_response_settings(self):
        document = Profile(fragment_motion=FragmentMotionSettings()).document("Response")
        for schema in (1, 2, 3):
            legacy = dict(document, schema=schema)
            if schema < 3:
                legacy["actions"] = {
                    key: value for key, value in document["actions"].items() if key != "swap"
                }
            with self.subTest(schema=schema), self.assertRaises(ValueError):
                parse_document(legacy)
        for invalid in (
            {key: value for key, value in document.items() if key != "fragment_motion"},
            document | {"fragment_motion": None},
            document | {"fragment_motion": {}},
            document
            | {
                "actions": {
                    key: value for key, value in document["actions"].items() if key != "swap"
                }
            },
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_document(invalid)
        with self.assertRaisesRegex(ValueError, "fragment_motion"):
            Profile(fragment_motion={})

    def test_stock_and_dormant_native_exports_keep_response_in_document_only(self):
        preset = FRAGMENT_PRESETS["tear"]
        for movement in (None, "off", replace(preset.effect, fragment_shape="triangle")):
            profile = Profile(
                movement=movement, fragment_motion=preset.settings, pointer=PointerWobble()
            )
            stock = render_kdl(profile)
            self.assertNotIn("window-movement", stock)
            self.assertNotIn("fragment-motion", stock)
            native = render_kdl(profile, movement=movement is not None, pointer=True)
            self.assertNotIn("fragment-motion", native)
            self.assertIn("pointer-wobble", native)
            self.assertEqual(
                parse_document(profile.document("Dormant"))[2].fragment_motion, preset.settings
            )

    def test_native_export_combines_response_pointer_and_independent_timed_swap(self):
        preset = FRAGMENT_PRESETS["tear"]
        response = replace(
            preset.settings, distance_exponent=1e-12, rotation_degrees=12.3456789012345
        )
        profile = Profile(
            movement=preset.effect,
            swap=preset.effect,
            pointer=PointerWobble(),
            fragment_motion=response,
        )
        exported = animation_types(profile, movement=True, pointer=True, swap=True)
        self.assertEqual(exported["window-movement"]["fragment-motion"], asdict(response))
        self.assertNotIn("fragment-motion", exported["window-swap"])
        self.assertNotIn("nirifx-fragment-motion", exported["window-swap"]["custom-shader"])
        native = render_kdl(profile, movement=True, pointer=True, swap=True)
        self.assertEqual(native.count("    window-movement {"), 1)
        self.assertEqual(native.count("        fragment-motion {"), 1)
        self.assertIn("distance-exponent 1e-12", native)
        self.assertIn("rotation-degrees 12.3456789012345", native)
        self.assertIn("nirifx-fragment-motion: 3", native)
        timed = render_kdl(profile, movement=True, pointer=True, continuous_fragments=False)
        self.assertNotIn("fragment-motion", timed)
        self.assertIn("pointer-wobble", timed)
        pointer_only = render_kdl(profile, pointer=True)
        self.assertNotIn("fragment-motion", pointer_only)
        self.assertIn("preserve-movement", pointer_only)

    def test_legacy_default_export_behavior_stays_unchanged(self):
        profile = Profile(movement=FRAGMENT_PRESETS["tear"].effect)
        legacy = render_kdl(profile, movement=True)
        self.assertIn("nirifx-fragment-motion: 3", legacy)
        self.assertNotIn("        fragment-motion {", legacy)
