"""Standalone fragment response shares review, runtime and Restore safeguards."""

import copy
import json
import os
import unittest
from dataclasses import asdict, replace
from unittest.mock import patch

import test_setup

from niri_fx import setup
from niri_fx.fragment_motion import PRESETS
from niri_fx.profiles import Profile


class FragmentRecipeSetupTests(unittest.TestCase):
    def setUp(self):
        # Reuse the existing temporary config, mocked validator and setup args.
        test_setup.SetupTests.setUp(self)
        self.preset = PRESETS["tear"]
        self.profile = Profile(movement=self.preset.effect, fragment_motion=self.preset.settings)
        self.args.movement_binary = "/trusted/niri"
        self.report = {"activation_ready": True, "binary": "/trusted/niri"}

    def tearDown(self):
        test_setup.SetupTests.tearDown(self)

    def plan(self, profile=None):
        return setup.plan_setup(self.args, self.profile if profile is None else profile)

    def test_active_response_requires_fragment_contract_before_any_config_write(self):
        self.args.enable_movement = True
        with (
            patch.dict(os.environ, {"NIRI_SOCKET": "/owned/session"}),
            patch("niri_fx.capabilities.movement_capability", return_value=self.report),
            patch(
                "niri_fx.capabilities.fragment_capability",
                return_value={"activation_ready": False},
            ) as capability,
            self.assertRaisesRegex(ValueError, "verified running fragment contract"),
        ):
            self.plan()
        capability.assert_called_once_with("/trusted/niri", socket_path="/owned/session")
        self.validator.assert_not_called()
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse(self.state.exists())
        self.assertFalse((self.config.parent / "nirifx").exists())

    def test_stock_and_dormant_choices_retain_response_without_requesting_fragment_support(self):
        for movement, enabled in (
            (self.preset.effect, False),
            (None, False),
            ("off", True),
            (replace(self.preset.effect, fragment_shape="triangle"), True),
        ):
            with (
                self.subTest(movement=movement, enabled=enabled),
                patch("niri_fx.capabilities.movement_capability", return_value=self.report),
                patch("niri_fx.capabilities.fragment_capability") as capability,
            ):
                self.args.enable_movement = enabled
                profile = replace(self.profile, movement=movement)
                plan = self.plan(profile)
                capability.assert_not_called()
                self.assertIsNone(plan["fragment_activation"])
                self.assertEqual(plan["fragment_motion"], asdict(self.preset.settings))
                self.assertIn("Fragment response settings are retained", " ".join(plan["notes"]))
                self.assertNotIn(b"fragment-motion", plan["changes"][0]["after"])
                self.assertEqual(profile.document("Saved")["schema"], 4)

    def test_clearing_response_exports_timed_material_without_native_default_activation(self):
        self.args.enable_movement = True
        with (
            patch("niri_fx.capabilities.movement_capability", return_value=self.report),
            patch("niri_fx.capabilities.fragment_capability") as capability,
        ):
            timed = self.plan(replace(self.profile, fragment_motion=None))
        capability.assert_not_called()
        exported = timed["changes"][0]["after"]
        self.assertIn(b"custom-shader", exported)
        self.assertNotIn(b"fragment-motion", exported)
        self.assertIsNone(timed["fragment_activation"])

    def test_review_binds_response_and_runtime_proof_and_apply_rechecks_even_without_changes(self):
        self.args.enable_movement = True
        with (
            patch.dict(os.environ, {"NIRI_SOCKET": "/owned/session"}),
            patch("niri_fx.capabilities.movement_capability", return_value=self.report),
            patch(
                "niri_fx.capabilities.fragment_capability", return_value=self.report
            ) as capability,
        ):
            plan = self.plan()
            self.assertEqual(
                plan["fragment_activation"],
                {"binary": "/trusted/niri", "socket": "/owned/session"},
            )
            reviewed = setup.summarize(plan)["plan_sha256"]
            for key, value in (
                ("fragment_motion", asdict(replace(self.preset.settings, batches=65))),
                ("fragment_activation", None),
                ("fragment_activation", {"binary": "/other/niri", "socket": "/owned/session"}),
            ):
                altered = copy.deepcopy(plan)
                altered[key] = value
                self.assertNotEqual(setup.plan_fingerprint(altered), reviewed)
                with self.assertRaisesRegex(ValueError, "plan changed"):
                    setup.apply_plan(altered, self.state, reviewed)
            capability.return_value = {"activation_ready": False}
            with self.assertRaisesRegex(ValueError, "fragment support changed"):
                setup.apply_plan(plan, self.state, reviewed)
            self.assertFalse(self.state.exists())
            capability.return_value = self.report
            with patch.dict(os.environ, {"NIRI_SOCKET": "/another/session"}):
                with self.assertRaisesRegex(ValueError, "support changed"):
                    setup.apply_plan(plan, self.state, reviewed)
            result = setup.apply_plan(plan, self.state, reviewed)
            self.validator.assert_called_with(str(self.config), "/trusted/niri")
            unchanged = self.plan()
            self.assertEqual(unchanged["changes"], [])
            capability.return_value = {"activation_ready": False}
            with self.assertRaisesRegex(ValueError, "fragment support changed"):
                setup.apply_plan(unchanged, self.state)
            # Removing all native settings remains possible without a renderer.
            capability.side_effect = AssertionError("Removing fragments needs no runtime")
            self.validator.side_effect = AssertionError("Stock Restore needs no compositor")
            setup.restore(self.state, result["transaction"], apply=True)
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_restore_reactivation_cannot_bypass_fragment_verification_or_change_snapshots(self):
        self.args.enable_movement = True
        with (
            patch("niri_fx.capabilities.movement_capability", return_value=self.report),
            patch("niri_fx.capabilities.fragment_capability", return_value=self.report),
        ):
            setup.apply_plan(self.plan(), self.state)
        self.args.enable_movement = False
        stock = setup.apply_plan(test_setup.SetupTests.plan(self), self.state)
        include = self.config.parent / "nirifx/animations.kdl"
        current = include.read_bytes()
        manifest = self.state / stock["transaction"] / "manifest.json"
        snapshot = manifest.read_bytes()
        with (
            patch("niri_fx.capabilities.movement_capability", return_value=self.report),
            patch(
                "niri_fx.capabilities.fragment_capability",
                return_value={"activation_ready": False},
            ) as capability,
        ):
            for apply in (False, True):
                with self.assertRaisesRegex(ValueError, "experimental fragment"):
                    setup.restore(self.state, stock["transaction"], apply=apply)
                self.assertEqual(include.read_bytes(), current)
                self.assertEqual(manifest.read_bytes(), snapshot)
            capability.return_value = self.report
            review = setup.restore(self.state, stock["transaction"])
            self.assertEqual(review["experimental"], ["fragment", "movement"])
            setup.restore(self.state, stock["transaction"], apply=True)
        self.assertIn(b"fragment-motion {", include.read_bytes())
        self.assertEqual(json.loads(manifest.read_bytes())["status"], "restored")

    def test_restore_scanner_detects_changed_fragment_controls_without_matching_shader_changes(
        self,
    ):
        before = b'animations { "window-movement" { "fragment-motion" { batches 64; }; }; }\n'
        after = before.replace(b"64", b"32")
        self.config.write_bytes(after)
        work = [(setup.change(self.config, before), before, after)]
        self.assertEqual(setup._restore_native_requirements(work, str(self.config)), ["fragment"])
        ignored = (
            b"// animations { window-movement { fragment-motion {}; }; }\n"
            b'animations { window-close { custom-shader r#"fragment-motion {}"#; }; '
            b"/- window-movement { fragment-motion {}; }; }\n"
        )
        self.config.write_bytes(ignored)
        self.assertEqual(setup._native_requirements(self.config, {}), set())


if __name__ == "__main__":
    unittest.main()
