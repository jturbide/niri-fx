"""One reviewed install composes a full bundle, entry and next-login selector."""

import copy
import io
import json
import os
import shutil
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import test_native_session

from niri_fx import native_build, native_session, setup
from niri_fx.cli import main
from niri_fx.native_install import install_plan


class NativeInstallTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_native_session.NativeSessionTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.destination
        self.candidate = self.fixture.candidate
        (self.candidate / "bin").mkdir()
        self.fixture.binary.rename(self.candidate / "bin/niri")
        self.fixture.binary = self.candidate / "bin/niri"
        self.fixture.record.update(binary=str(self.fixture.binary), source="source")
        self.fixture.save_record()
        (self.candidate / "patches").mkdir()
        for name in native_build.STACKS["fragment"]:
            shutil.copyfile(
                self.fixture.repository / "experimental" / name,
                self.candidate / "patches" / name,
            )
        self.validator = self.fixture.validator

    def plan(self, *, name="NiriFX"):
        return install_plan(self.root, self.candidate, self.fixture.config, name=name)

    def apply(self, plan):
        return setup.apply_plan(
            plan, self.fixture.selection_state, expected=setup.plan_fingerprint(plan)
        )

    def report(self, plan):
        return native_session.inspect_bundle(self.root, plan["selection"]["bundle_id"])

    def test_review_of_absent_storage_executes_nothing_and_creates_nothing(self):
        before = {p: p.read_bytes() for p in self.fixture.root.rglob("*") if p.is_file()}
        with patch("subprocess.run") as command, patch("subprocess.Popen") as child:
            plan = self.plan()
        command.assert_not_called()
        child.assert_not_called()
        self.validator.assert_not_called()
        self.assertFalse(self.root.exists())
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertEqual(plan["selection"]["name"], "NiriFX")
        self.assertEqual(plan["selection"]["selected"], plan["selection"]["bundle_id"])
        self.assertIsNone(plan["selection"]["previous"])
        self.assertEqual(Path(plan["changes"][-1]["target"]), self.root / "selection.json")
        self.assertTrue(all(Path(c["target"]).is_relative_to(self.root) for c in plan["changes"]))

    def test_apply_copies_candidate_config_entry_then_selects_and_validates(self):
        self.fixture.config.write_text('include "more.kdl"\nlayout {}\n')
        child = self.fixture.root / "more.kdl"
        child.write_text('environment { EXAMPLE "synthetic"; }\n')
        original = self.fixture.config.read_bytes(), child.read_bytes()
        plan = self.plan()
        self.apply(plan)
        report = self.report(plan)
        self.assertEqual(report["variant"], "fragment")
        self.assertEqual(report["config_file_count"], 2)
        self.assertEqual(native_session.load_selection(self.root)["selected"], report["bundle_id"])
        self.assertNotEqual(Path(report["binary"]).stat().st_ino, self.fixture.binary.stat().st_ino)
        self.assertEqual(original, (self.fixture.config.read_bytes(), child.read_bytes()))
        self.assertTrue((self.root / "session/launch.py").exists())
        self.assertIn("Name=NiriFX\n", (self.root / "session/niri-fx.desktop").read_text())
        self.validator.assert_called_once_with(report["config"], report["binary"])
        self.assertEqual(report["runtime_acceptance"], "not_assessed")

    def test_frozen_candidate_patches_are_used_without_mutable_repository(self):
        shutil.rmtree(self.fixture.repository)
        plan = self.plan()
        self.apply(plan)
        self.report(plan)
        observed = {Path(item["target"]) for item in plan["observed"]}
        self.assertTrue(
            all(
                self.candidate / "patches" / name in observed
                for name in native_build.STACKS["fragment"]
            )
        )

    def test_missing_or_changed_frozen_patch_refuses_even_when_checkout_matches(self):
        path = self.candidate / "patches" / native_build.STACKS["fragment"][0]
        path.write_text("changed patch")
        with self.assertRaisesRegex(ValueError, "recorded SHA-256"):
            self.plan()
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            self.plan()
        self.assertFalse(self.root.exists())

    def test_full_release_desktop_feature_stack_is_required(self):
        original = copy.deepcopy(self.fixture.record)
        for mutation in ("movement", "debug", "minimal", "missing-feature"):
            with self.subTest(mutation=mutation):
                record = copy.deepcopy(original)
                block = record["native_build"]
                inputs = block["inputs"]
                if mutation == "movement":
                    inputs["variant"] = "movement"
                elif mutation == "debug":
                    inputs["profile"] = record["build_profile"] = "debug"
                elif mutation == "minimal":
                    inputs["default_features"] = False
                    inputs["enabled_features"] = []
                    inputs["cargo_flags"] = record["build_flags"] = [
                        "--locked",
                        "--no-default-features",
                    ]
                else:
                    inputs["enabled_features"].remove("pipewire")
                block["build_id"] = native_build.fingerprint(inputs)
                self.fixture.manifest_path.write_text(json.dumps(record))
                with self.assertRaisesRegex(ValueError, "complete session|Desktop build"):
                    self.plan()
        self.assertFalse(self.root.exists())
        self.validator.assert_not_called()

    def test_candidate_paths_are_fixed_and_symlink_inputs_refuse(self):
        original = copy.deepcopy(self.fixture.record)
        for values in (
            {"binary": str(self.fixture.config)},
            {"source": "elsewhere"},
            {"binary": ""},
        ):
            self.fixture.manifest_path.write_text(json.dumps(original | values))
            with self.assertRaisesRegex(ValueError, "candidate's own"):
                self.plan()
        self.fixture.save_record()
        path = self.candidate / "patches" / native_build.STACKS["fragment"][0]
        path.unlink()
        path.symlink_to(self.fixture.repository / "experimental" / path.name)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.plan()
        self.assertFalse(self.root.exists())

    def test_relative_published_binary_is_supported_but_not_an_external_one(self):
        self.fixture.record["binary"] = "bin/niri"
        self.fixture.save_record()
        self.apply(self.plan())
        self.fixture.record["binary"] = "../external/niri"
        self.fixture.save_record()
        with self.assertRaisesRegex(ValueError, "candidate's own"):
            self.plan()

    def test_incomplete_candidate_has_no_installable_manifest(self):
        self.fixture.manifest_path.unlink()
        (self.candidate / "attempt.json").write_text(json.dumps({"status": "built"}))
        with self.assertRaises(FileNotFoundError):
            self.plan()
        self.assertFalse(self.root.exists())

    def test_reinstall_is_idempotent_and_a_config_update_retains_previous_pair(self):
        initial = self.plan()
        self.apply(initial)
        self.assertEqual(self.plan()["changes"], [])
        self.fixture.config.write_text("animations { window-close { off; }; }\n")
        update = self.plan()
        self.assertNotEqual(initial["selection"]["bundle_id"], update["selection"]["bundle_id"])
        self.assertEqual(update["selection"]["previous"], initial["selection"]["bundle_id"])
        self.assertFalse(any("/session/" in c["target"] for c in update["changes"]))
        self.apply(update)
        self.report(initial)
        self.report(update)
        self.assertEqual(self.plan()["changes"], [])
        self.assertEqual(self.plan()["selection"]["previous"], initial["selection"]["bundle_id"])

    def test_different_or_user_edited_entry_is_preserved_before_any_write(self):
        original = self.plan(name="My NiriFX")
        self.apply(original)
        with self.assertRaisesRegex(ValueError, "Existing login entry differs"):
            self.plan()
        entry = self.root / "session/niri-fx.desktop"
        entry.write_text("user-owned desktop entry\n")
        self.fixture.config.write_text("layout {}\n")
        with self.assertRaisesRegex(ValueError, "Existing login entry differs"):
            self.plan(name="My NiriFX")
        self.assertEqual(entry.read_text(), "user-owned desktop entry\n")
        self.assertEqual(
            native_session.load_selection(self.root)["selected"], original["selection"]["bundle_id"]
        )

    def test_entry_created_after_review_and_selector_races_refuse(self):
        plan = self.plan()
        entry = self.root / "session/niri-fx.desktop"
        entry.parent.mkdir(parents=True)
        entry.write_text("external entry\n")
        with self.assertRaisesRegex(ValueError, "File changed"):
            self.apply(plan)
        self.assertFalse((self.root / "bundles").exists())
        entry.unlink()
        plan = self.plan()
        selector = self.root / "selection.json"
        selector.write_text(json.dumps({"schema": 1, "selected": None, "previous": None}))
        selector.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "File changed"):
            self.apply(plan)
        self.assertFalse((self.root / "bundles").exists())

    def test_source_mode_and_fifo_drift_after_review_refuse(self):
        path = self.candidate / "patches" / native_build.STACKS["fragment"][0]
        original_mode = path.stat().st_mode & 0o777
        original_bytes = path.read_bytes()
        plan = self.plan()
        path.chmod(0o600 if original_mode != 0o600 else 0o644)
        with self.assertRaisesRegex(ValueError, "permissions changed"):
            self.apply(plan)
        path.chmod(original_mode)
        plan = self.plan()
        path.unlink()
        os.mkfifo(path)
        with self.assertRaisesRegex(ValueError, "regular file"):
            self.apply(plan)
        path.unlink()
        path.write_bytes(original_bytes)
        self.assertFalse((self.root / "bundles").exists())

    def test_failed_first_install_removes_owned_entry_bundle_and_selector(self):
        plan = self.plan()
        self.validator.side_effect = ValueError("fixture invalid configuration")
        with self.assertRaisesRegex(ValueError, "fixture invalid"):
            self.apply(plan)
        self.assertFalse((self.root / "selection.json").exists())
        self.assertFalse((self.root / "session/niri-fx.desktop").exists())
        self.assertFalse((self.root / "session/launch.py").exists())
        self.assertFalse(any(p.is_file() for p in (self.root / "bundles").rglob("*")))
        self.validator.side_effect = None
        self.apply(self.plan())

    def test_failed_update_retains_previous_bundle_selector_and_entry(self):
        first = self.plan()
        self.apply(first)
        selected_bytes = (self.root / "selection.json").read_bytes()
        entry_bytes = (self.root / "session/niri-fx.desktop").read_bytes()
        self.fixture.config.write_text("animations { off; }\n")
        update = self.plan()
        self.validator.side_effect = ValueError("fixture invalid configuration")
        with self.assertRaisesRegex(ValueError, "fixture invalid"):
            self.apply(update)
        self.assertEqual((self.root / "selection.json").read_bytes(), selected_bytes)
        self.assertEqual((self.root / "session/niri-fx.desktop").read_bytes(), entry_bytes)
        self.report(first)

    def test_rollback_changes_only_selector_and_generic_restore_is_refused(self):
        initial = self.plan()
        self.apply(initial)
        with self.assertRaisesRegex(ValueError, "native rollback"):
            setup.restore(self.fixture.selection_state, apply=True)
        rollback = native_session.rollback_plan(self.root)
        self.apply(rollback)
        self.assertIsNone(native_session.load_selection(self.root)["selected"])
        self.report(initial)
        self.assertTrue((self.root / "session/niri-fx.desktop").exists())

    def test_cli_review_and_apply_share_the_same_fingerprint(self):
        args = [
            "native",
            "install",
            "--candidate",
            str(self.candidate),
            "--config",
            str(self.fixture.config),
            "--root",
            str(self.root),
        ]
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(args), 0)
        reviewed = json.loads(output.getvalue())
        self.assertTrue(reviewed["dry_run"])
        self.assertFalse(self.root.exists())
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([*args, "--apply", "--expect-plan", reviewed["plan_sha256"]]), 0)
        applied = json.loads(output.getvalue())
        self.assertFalse(applied["dry_run"])
        self.assertNotIn("restore", applied)
        self.assertIn("administrator registration", applied["next_step"])
        self.assertEqual(
            native_session.load_selection(self.root)["selected"], reviewed["selection"]["selected"]
        )


if __name__ == "__main__":
    unittest.main()
