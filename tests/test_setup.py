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
from niri_fx.cli import parser, selected_effect
from niri_fx.effects import PRESETS

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
        self.assertEqual(len(data["presets"]), len(PRESETS) + 1)
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
