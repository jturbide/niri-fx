import json
import os
import shutil
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from helpers import shell_registry

from niri_fx import setup
from niri_fx.catalog import PROFILES, STYLES
from niri_fx.cli import parser, selected_effect
from niri_fx.effects import PRESETS
from niri_fx.pointer import PointerWobble
from niri_fx.profiles import Profile

REAL_VALIDATE_CONFIG = setup.validate_config


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = self.root / "niri/config.kdl"
        self.config.parent.mkdir()
        self.original = b'// User config\ninclude "base.kdl"\n\n'
        self.config.write_bytes(self.original)
        (self.config.parent / "base.kdl").write_text("animations {}\n")
        self.args = Namespace(
            config=self.config,
            target="standalone",
            inir_root=self.root / "no-shell",
            registry=self.root / "registry.json",
            base="auto",
            launcher=False,
            name=None,
            preset="balanced",
        )
        self.state = self.root / "state"
        self.validate = patch("niri_fx.setup.validate_config")
        self.validator = self.validate.start()

    def tearDown(self):
        self.validate.stop()
        self.temp.cleanup()

    def plan(self):
        return setup.plan_setup(self.args, PRESETS["balanced"])

    def test_plan_does_not_change_configs_or_create_state(self):
        plan = self.plan()
        self.assertEqual(len(plan["changes"]), 2)
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse(self.state.exists())
        self.assertFalse((self.config.parent / "nirifx").exists())
        self.assertFalse(list(self.config.parent.glob(".nirifx-check-*")))

    def test_movement_activation_requires_verified_explicit_standalone_support(self):
        self.args.enable_movement = True
        self.args.movement_binary = Path("/trusted/niri")
        with patch(
            "niri_fx.capabilities.movement_capability", return_value={"activation_ready": False}
        ):
            with self.assertRaisesRegex(ValueError, "verified running shader contract"):
                self.plan()
        self.assertEqual(self.config.read_bytes(), self.original)
        self.args.target = "auto"
        with self.assertRaisesRegex(ValueError, "explicit --target standalone"):
            self.plan()

    def test_movement_plan_rechecks_support_before_apply_and_restores_exactly(self):
        self.args.enable_movement = True
        report = {"activation_ready": True, "binary": "/trusted/niri"}
        with patch("niri_fx.capabilities.movement_capability", return_value=report) as capability:
            plan = self.plan()
            self.assertIn(b"window-movement", plan["changes"][0]["after"])
            self.assertNotIn(b"window-resize", plan["changes"][0]["after"])
            capability.return_value = {"activation_ready": False}
            with self.assertRaisesRegex(ValueError, "support changed"):
                setup.apply_plan(plan, self.state)
            self.assertFalse(self.state.exists())
            capability.return_value = report
            result = setup.apply_plan(plan, self.state)
        setup.restore(self.state, result["transaction"], apply=True)
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse((self.config.parent / "nirifx/animations.kdl").exists())

    def test_profile_review_keeps_actions_and_desktop_timing_separate(self):
        self.args.profile = "gentle-motion"
        profile = PROFILES[self.args.profile]
        plan = setup.plan_setup(self.args, profile)
        document = profile.document("Selection")
        self.assertEqual(plan["effect"], document["actions"])
        self.assertEqual(plan["desktop_motion"], document["motion"])
        reviewed = setup.summarize(plan)
        self.assertEqual(reviewed["desktop_motion"], document["motion"])
        fingerprint = reviewed["plan_sha256"]
        plan["desktop_motion"]["camera"]["stiffness"] = 800
        self.assertNotEqual(setup.summarize(plan)["plan_sha256"], fingerprint)

    def test_pointer_requires_explicit_selection_target_and_running_contract_before_writes(self):
        profile = Profile(PRESETS["balanced"], PRESETS["balanced"], pointer=PointerWobble())
        default = setup.plan_setup(self.args, profile)
        self.assertNotIn(b"pointer-wobble", default["changes"][0]["after"])
        self.assertIn("omitted", " ".join(default["notes"]))
        self.args.enable_pointer = True
        with self.assertRaisesRegex(ValueError, "no pointer settings"):
            self.plan()
        with patch(
            "niri_fx.capabilities.pointer_capability", return_value={"activation_ready": False}
        ):
            with self.assertRaisesRegex(ValueError, "verified running pointer contract"):
                setup.plan_setup(self.args, profile)
        self.args.target = "auto"
        with self.assertRaisesRegex(ValueError, "explicit --target standalone"):
            setup.plan_setup(self.args, profile)
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse(self.state.exists())
        self.assertFalse((self.config.parent / "nirifx").exists())

    def test_pointer_apply_rechecks_session_validates_selected_binary_and_restores(self):
        profile = Profile(PRESETS["balanced"], PRESETS["balanced"], pointer=PointerWobble())
        self.args.enable_pointer = True
        self.args.movement_binary = Path("/trusted/niri")
        report = {"activation_ready": True, "binary": "/trusted/niri"}
        with (
            patch.dict(os.environ, {"NIRI_SOCKET": "/owned/session"}),
            patch("niri_fx.capabilities.pointer_capability", return_value=report) as capability,
        ):
            plan = setup.plan_setup(self.args, profile)
            self.assertIn(b"pointer-wobble", plan["changes"][0]["after"])
            self.assertNotIn(b"move_color", plan["changes"][0]["after"])
            self.assertEqual(plan["pointer"], profile.document("Selection")["pointer"])
            self.assertEqual(self.validator.call_args.args[1], "/trusted/niri")
            reviewed = setup.summarize(plan)["plan_sha256"]
            capability.return_value = {"activation_ready": False}
            with self.assertRaisesRegex(ValueError, "pointer support changed"):
                setup.apply_plan(plan, self.state, reviewed)
            self.assertFalse(self.state.exists())
            capability.return_value = report
            with patch.dict(os.environ, {"NIRI_SOCKET": "/another/session"}):
                with self.assertRaisesRegex(ValueError, "pointer support changed"):
                    setup.apply_plan(plan, self.state, reviewed)
            result = setup.apply_plan(plan, self.state, reviewed)
            self.validator.assert_called_with(str(self.config), "/trusted/niri")
        setup.restore(self.state, result["transaction"], apply=True)
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse((self.config.parent / "nirifx/animations.kdl").exists())

    def test_pointer_review_hash_binds_settings_and_activation_consent(self):
        profile = Profile(PRESETS["balanced"], PRESETS["balanced"], pointer=PointerWobble())
        omitted = setup.plan_setup(self.args, profile)
        reviewed = setup.summarize(omitted)["plan_sha256"]
        omitted["pointer"]["strength"] = 0.4
        self.assertNotEqual(setup.summarize(omitted)["plan_sha256"], reviewed)
        self.args.enable_pointer = True
        with patch(
            "niri_fx.capabilities.pointer_capability",
            return_value={"activation_ready": True, "binary": "/trusted/niri"},
        ):
            activated = setup.plan_setup(self.args, profile)
        self.assertNotEqual(setup.summarize(activated)["plan_sha256"], reviewed)

    def test_selected_validator_is_kept_for_stock_actions_on_an_experimental_config(self):
        self.args.movement_binary = Path("/trusted/niri")
        plan = self.plan()
        self.assertIsNone(plan["movement"])
        self.assertIsNone(plan["pointer_activation"])
        self.assertEqual(plan["validation_binary"], "/trusted/niri")
        self.assertEqual(self.validator.call_args.args[1], "/trusted/niri")
        reviewed = setup.summarize(plan)["plan_sha256"]
        self.args.movement_binary = Path("/another/niri")
        with self.assertRaisesRegex(ValueError, "plan changed"):
            setup.apply_plan(self.plan(), self.state, reviewed)
        setup.apply_plan(plan, self.state, reviewed)
        self.validator.assert_called_with(str(self.config), "/trusted/niri")

    def native_then_stock(self):
        self.args.enable_pointer = True
        self.args.movement_binary = Path("/trusted/niri")
        report = {"activation_ready": True, "binary": "/trusted/niri"}
        profile = Profile(PRESETS["balanced"], PRESETS["balanced"], pointer=PointerWobble())
        with patch("niri_fx.capabilities.pointer_capability", return_value=report):
            native = setup.apply_plan(setup.plan_setup(self.args, profile), self.state)
        self.args.enable_pointer = False
        stock = setup.apply_plan(self.plan(), self.state)
        return native, stock, report

    def test_restore_rechecks_native_support_and_never_blocks_removing_native_nodes(self):
        native, stock, report = self.native_then_stock()
        include = self.config.parent / "nirifx/animations.kdl"
        current = include.read_bytes()
        with patch(
            "niri_fx.capabilities.pointer_capability", return_value={"activation_ready": False}
        ) as capability:
            for apply in (False, True):
                with self.assertRaisesRegex(
                    ValueError, "Restore would reactivate experimental pointer"
                ):
                    setup.restore(self.state, stock["transaction"], apply=apply)
                self.assertEqual(include.read_bytes(), current)
            capability.return_value = report
            reviewed = setup.restore(self.state, stock["transaction"])
            self.assertEqual(reviewed["experimental"], ["pointer"])
            setup.restore(self.state, stock["transaction"], apply=True)
            self.assertIn(b"pointer-wobble", include.read_bytes())
            self.validator.assert_called_with(str(self.config), "/trusted/niri")
            capability.side_effect = AssertionError("Removing native settings needs no runtime")
            self.validator.side_effect = AssertionError("Stock restoration needs no compositor")
            setup.restore(self.state, native["transaction"], apply=True)
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse(include.exists())

    def test_failed_native_restore_validation_rolls_back_and_keeps_snapshot_applied(self):
        _, stock, report = self.native_then_stock()
        include = self.config.parent / "nirifx/animations.kdl"
        current = include.read_bytes()
        self.validator.side_effect = ValueError("An included file changed")
        with patch("niri_fx.capabilities.pointer_capability", return_value=report):
            with self.assertRaisesRegex(ValueError, "included file changed"):
                setup.restore(self.state, stock["transaction"], apply=True)
        self.assertEqual(include.read_bytes(), current)
        manifest = json.loads((self.state / stock["transaction"] / "manifest.json").read_text())
        self.assertEqual(manifest["status"], "applied")

    def test_legacy_native_snapshot_uses_explicit_validator_and_preserves_conflict_priority(self):
        _, stock, report = self.native_then_stock()
        path = self.state / stock["transaction"] / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest.pop("validation_binary")
        manifest.pop("validation_config")
        path.write_text(json.dumps(manifest))
        include = self.config.parent / "nirifx/animations.kdl"
        current = include.read_bytes()
        include.write_bytes(current + b"// Later edit\n")
        with patch("niri_fx.capabilities.pointer_capability") as capability:
            with self.assertRaisesRegex(ValueError, "File changed"):
                setup.restore(self.state, stock["transaction"], apply=True)
            capability.assert_not_called()
        include.write_bytes(current)
        with patch("niri_fx.capabilities.pointer_capability", return_value=report) as capability:
            setup.restore(self.state, stock["transaction"], apply=True, binary="/trusted/niri")
        self.assertEqual(capability.call_args.args, ("/trusted/niri",))
        self.validator.assert_called_with(str(include), "/trusted/niri")

    def test_native_restore_detects_preexisting_nodes_in_changed_include_targets(self):
        source = self.config.parent / "native settings.kdl"
        source.write_text(
            'animations { window-movement { pointer-wobble { strength 0.4; damping 85; frequency 10; }; custom-shader r"vec4 move_color(vec3 c, vec3 s) { return vec4(0.0); }"; }; }\n'
        )
        prior = b'include "native settings.kdl"\n'
        self.config.write_bytes(prior)
        plan = {
            "target": "standalone",
            "notes": [],
            "validation_config": str(self.config),
            "validation_binary": "/trusted/niri",
            "changes": [setup.change(self.config, self.original)],
        }
        changed = setup.apply_plan(plan, self.state)
        report = {"activation_ready": True, "binary": "/trusted/niri"}
        with (
            patch("niri_fx.capabilities.movement_capability", return_value=report) as movement,
            patch(
                "niri_fx.capabilities.pointer_capability", return_value={"activation_ready": False}
            ),
        ):
            with self.assertRaisesRegex(ValueError, "experimental pointer"):
                setup.restore(self.state, changed["transaction"], apply=True)
            movement.assert_called_once()
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_native_restore_scanner_ignores_comments_and_shader_text_but_finds_changed_settings(
        self,
    ):
        stock = b"""// animations { window-movement { pointer-wobble { strength 1; }; }; }
/* outer /* nested */ animations { window-movement { pointer-wobble {}; }; } */
animations {
    /- window-movement { pointer-wobble { strength 0.7; }; }
    window-movement /- { pointer-wobble { strength 0.7; }; }
    window-close { custom-shader r#"/* pointer-wobble */ window-movement { custom-shader ignored; }"#; }
}
"""
        self.config.write_bytes(stock)
        self.assertEqual(setup._native_requirements(self.config, {}), set())
        before = b'animations { "window-movement" { "pointer-wobble" { strength 0.7; }; }; }\n'
        after = before.replace(b"0.7", b"0.4")
        work = [(setup.change(self.config, after), before, after)]
        self.assertEqual(setup._restore_native_requirements(work, str(self.config)), ["pointer"])
        self.assertEqual(setup._restore_native_requirements([(work[0][0], stock, after)], None), [])
        for source in (
            b'/* quote " in comment */\n' + before + b'/* another " */\n',
            b"prefer-no-csd\r" + before.replace(b"\n", b"\r"),
            before.replace(b'"window-movement" {', b'"window-movement" \\ // comment\n{'),
        ):
            self.config.write_bytes(source)
            self.assertEqual(
                {kind for kind, _ in setup._native_requirements(self.config, {})}, {"pointer"}
            )

    def test_restore_gates_removing_an_override_that_resumes_a_native_base(self):
        base = self.config.parent / "base.kdl"
        base.write_text(
            "animations { window-movement { pointer-wobble { strength 0.4; damping 85; frequency 10; }; }; }\n"
        )
        self.args.movement_binary = Path("/trusted/niri")
        self.args.enable_pointer = True
        effect = Profile(PRESETS["balanced"], PRESETS["balanced"], pointer=PointerWobble())
        report = {"activation_ready": True, "binary": "/trusted/niri"}
        with patch("niri_fx.capabilities.pointer_capability", return_value=report):
            applied = setup.apply_plan(setup.plan_setup(self.args, effect), self.state)
        with patch(
            "niri_fx.capabilities.pointer_capability", return_value={"activation_ready": False}
        ):
            with self.assertRaisesRegex(ValueError, "experimental pointer"):
                setup.restore(self.state, applied["transaction"], apply=True)

    def test_restore_follows_includes_with_commented_properties(self):
        included = self.config.parent / "native.kdl"
        included.write_text(
            "animations { window-movement { pointer-wobble { strength 0.4; damping 85; frequency 10; }; }; }\n"
        )
        for ignored in ('ignored="comment"', '"ignored"="comment"', "ignored=true"):
            self.config.write_text(f'include /- {ignored} "native.kdl"\n')
            self.assertEqual(
                {kind for kind, _ in setup._native_requirements(self.config, {})}, {"pointer"}
            )

    def test_standalone_apply_idempotence_and_exact_restore(self):
        self.config.chmod(0o640)
        result = setup.apply_plan(self.plan(), self.state)
        self.assertTrue(result["changed"])
        self.assertIn(setup.BEGIN, self.config.read_text())
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o640)
        self.assertFalse(setup.apply_plan(self.plan(), self.state)["changed"])
        preview = setup.restore(self.state)
        self.assertTrue(preview["dry_run"])
        self.assertIn(setup.BEGIN, self.config.read_text())
        setup.restore(self.state, result["transaction"], True)
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse((self.config.parent / "nirifx/animations.kdl").exists())
        with self.assertRaisesRegex(ValueError, "No applied"):
            setup.restore(self.state)

    @unittest.skipUnless(shutil.which("niri"), "requires the real Niri config parser")
    def test_inline_base_animations_plan_apply_and_restore_with_real_niri(self):
        self.validator.side_effect = REAL_VALIDATE_CONFIG
        # JSON's ASCII Unicode escapes are not valid KDL escapes; sibling
        # includes must also work when the user's config directory is non-ASCII.
        directory = self.root / "niri é"
        self.config.parent.rename(directory)
        self.config = directory / "config.kdl"
        self.args.config = self.config
        original = b'include "base.kdl"\nanimations { window-resize { duration-ms 170; }; }\n'
        self.config.write_bytes(original)
        plan = self.plan()
        self.assertEqual(self.config.read_bytes(), original)
        self.assertFalse(list(self.config.parent.glob(".nirifx-*.kdl")))
        result = setup.apply_plan(plan, self.state)
        self.assertTrue(self.config.read_bytes().startswith(original))
        self.assertNotIn(
            "window-resize", (self.config.parent / "nirifx/animations.kdl").read_text()
        )
        setup.restore(self.state, result["transaction"], True)
        self.assertEqual(self.config.read_bytes(), original)

    def test_post_install_edits_block_all_restore_writes(self):
        setup.apply_plan(self.plan(), self.state)
        include = self.config.parent / "nirifx/animations.kdl"
        installed = include.read_bytes()
        self.config.write_text(self.config.read_text() + "// Later user edit\n")
        with self.assertRaisesRegex(ValueError, "changed"):
            setup.restore(self.state, apply=True)
        self.assertEqual(include.read_bytes(), installed)
        self.assertIn("Later user edit", self.config.read_text())

    def test_file_change_after_plan_blocks_apply(self):
        plan = self.plan()
        self.config.write_text("// Concurrent edit\n")
        with self.assertRaisesRegex(ValueError, "changed"):
            setup.apply_plan(plan, self.state)
        self.assertFalse((self.config.parent / "nirifx").exists())

    def test_review_hash_accepts_only_the_reviewed_plan(self):
        reviewed = setup.summarize(self.plan())["plan_sha256"]
        self.assertEqual(reviewed, setup.summarize(self.plan())["plan_sha256"])
        self.config.chmod(0o640)
        with self.assertRaisesRegex(ValueError, "plan changed"):
            setup.apply_plan(self.plan(), self.state, expected=reviewed)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.config.read_bytes(), self.original)
        reviewed = setup.summarize(self.plan())["plan_sha256"]
        self.assertTrue(setup.apply_plan(self.plan(), self.state, expected=reviewed)["changed"])

    def test_review_includes_config_even_when_only_shader_changes(self):
        setup.apply_plan(self.plan(), self.state)
        effect = PRESETS["explosion"]
        plan = setup.plan_setup(self.args, effect)
        self.assertEqual(len(plan["changes"]), 1)
        reviewed = setup.summarize(plan)["plan_sha256"]
        include = self.config.parent / "nirifx/animations.kdl"
        before = include.read_bytes()
        self.config.write_bytes(self.config.read_bytes() + b"// independent edit\n")
        with self.assertRaisesRegex(ValueError, "plan changed"):
            setup.apply_plan(setup.plan_setup(self.args, effect), self.state, expected=reviewed)
        # Changes between planning and writing are also refused, including the
        # root config when it would not itself have been rewritten.
        with self.assertRaisesRegex(ValueError, "File changed"):
            setup.apply_plan(plan, self.state, expected=reviewed)
        self.assertEqual(include.read_bytes(), before)

    def test_review_hash_binds_selection_and_resolved_path(self):
        reviewed = setup.summarize(self.plan())["plan_sha256"]
        different = setup.plan_setup(self.args, PRESETS["explosion"])
        with self.assertRaisesRegex(ValueError, "plan changed"):
            setup.apply_plan(different, self.state, expected=reviewed)
        target = self.root / "moved.kdl"
        self.config.rename(target)
        self.config.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "plan changed"):
            setup.apply_plan(self.plan(), self.state, expected=reviewed)
        self.assertFalse(self.state.exists())
        self.assertEqual(target.read_bytes(), self.original)

    def test_config_edit_during_validation_blocks_the_plan(self):
        self.validator.side_effect = lambda _: self.config.write_text("// Concurrent edit\n")
        with self.assertRaisesRegex(ValueError, "changed while preparing"):
            self.plan()
        self.assertEqual(self.config.read_text(), "// Concurrent edit\n")
        self.assertFalse(self.state.exists())

    def test_validation_failure_rolls_back_all_applied_files(self):
        plan = self.plan()
        self.validator.side_effect = ValueError("failed validation")
        with self.assertRaisesRegex(ValueError, "failed validation"):
            setup.apply_plan(plan, self.state)
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse((self.config.parent / "nirifx/animations.kdl").exists())
        manifest = json.loads(next(self.state.glob("*/manifest.json")).read_text())
        self.assertEqual(manifest["status"], "failed")

    def test_failed_second_write_recovers_first_file(self):
        plan = self.plan()
        real_write = setup.atomic_write

        def fail_root(path, data, mode=0o600):
            if path == self.config:
                raise OSError("disk write failed")
            return real_write(path, data, mode)

        with patch.object(setup, "atomic_write", side_effect=fail_root):
            with self.assertRaisesRegex(OSError, "disk write failed"):
                setup.apply_plan(plan, self.state)
        self.assertEqual(self.config.read_bytes(), self.original)
        self.assertFalse((self.config.parent / "nirifx/animations.kdl").exists())

    def test_unowned_include_and_damaged_markers_are_rejected(self):
        include = self.config.parent / "nirifx/animations.kdl"
        include.parent.mkdir()
        include.write_text("// Somebody else's file\n")
        with self.assertRaisesRegex(ValueError, "unowned"):
            self.plan()
        include.unlink()
        self.config.write_text(self.original.decode() + setup.BEGIN + "\n")
        with self.assertRaisesRegex(ValueError, "markers"):
            self.plan()

    def test_symlink_is_preserved_and_retargeting_blocks_restore(self):
        target = self.root / "actual.kdl"
        self.config.rename(target)
        self.config.symlink_to(target)
        setup.apply_plan(self.plan(), self.state)
        self.assertTrue(self.config.is_symlink())
        replacement = self.root / "other.kdl"
        replacement.write_text("// Another config\n")
        self.config.unlink()
        self.config.symlink_to(replacement)
        with self.assertRaisesRegex(ValueError, "changed"):
            setup.restore(self.state, apply=True)
        self.assertEqual(replacement.read_text(), "// Another config\n")

    def test_inir_setup_and_restore_preserve_original_registry(self):
        self.args.target = "inir"
        original = b'{"presets":[{"id":"other","name":"Keep"}],"note":42}\n'
        self.args.registry.write_bytes(original)
        with patch("niri_fx.setup.read_shell_presets", return_value=shell_registry()):
            setup.apply_plan(self.plan(), self.state)
            self.assertFalse(self.plan()["changes"])
        data = json.loads(self.args.registry.read_text())
        self.assertEqual(data["presets"][0]["id"], "other")
        self.assertEqual(len(data["presets"]), len(STYLES) + 1)
        setup.restore(self.state, apply=True)
        self.assertEqual(self.args.registry.read_bytes(), original)
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_tampered_snapshot_is_never_restored(self):
        setup.apply_plan(self.plan(), self.state)
        saved = next(self.state.glob("*/1.before"))
        saved.write_text("tampered")
        with self.assertRaisesRegex(ValueError, "hash check"):
            setup.restore(self.state, apply=True)
        self.assertIn(setup.BEGIN, self.config.read_text())

    def test_multiple_setups_restore_newest_first(self):
        from dataclasses import replace
        from types import SimpleNamespace

        with patch.object(
            setup.uuid,
            "uuid4",
            side_effect=[SimpleNamespace(hex="f" * 32), SimpleNamespace(hex="a" * 32)],
        ):
            first = setup.apply_plan(self.plan(), self.state)
            second_plan = setup.plan_setup(self.args, replace(PRESETS["balanced"], origin_x=0.1))
            second = setup.apply_plan(second_plan, self.state)
        self.assertEqual(
            setup.restore(self.state, apply=True)["transaction"], second["transaction"]
        )
        self.assertEqual(setup.restore(self.state, apply=True)["transaction"], first["transaction"])
        self.assertEqual(self.config.read_bytes(), self.original)

    def test_launcher_uses_xdg_and_is_removed_by_restore(self):
        self.args.launcher = True
        with patch.dict(os.environ, {"XDG_DATA_HOME": str(self.root / "data with spaces")}):
            plan = self.plan()
            setup.apply_plan(plan, self.state)
            launcher = self.root / "data with spaces/applications/niri-fx-studio.desktop"
            self.assertTrue(launcher.exists())
            self.assertFalse(self.plan()["changes"])
            setup.restore(self.state, apply=True)
            self.assertFalse(launcher.exists())

    def test_setup_requires_apply_and_custom_cli_uses_exact_document(self):
        self.assertFalse(parser().parse_args(["setup"]).apply)
        self.assertFalse(parser().parse_args(["restore"]).apply)
        document = self.root / "custom.json"
        document.write_text(
            json.dumps(
                {
                    "schema": 3,
                    "name": "Portable",
                    "effect": {"gravity": "up", "resize_mode": "edge"},
                }
            )
        )
        effect = selected_effect(
            parser().parse_args(["preview", "--custom", str(document), "--output", "unused"])
        )
        self.assertEqual(effect.gravity, "up")
        self.assertFalse(effect.resize)
        with self.assertRaisesRegex(ValueError, "combine"):
            selected_effect(
                parser().parse_args(["render", "--custom", str(document), "--particles", "100"])
            )


if __name__ == "__main__":
    unittest.main()
