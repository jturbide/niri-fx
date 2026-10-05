"""Preparing and selecting native sessions never touches the running desktop."""

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from niri_fx import native_build, native_session, setup
from niri_fx.storage import digest


class NativeSessionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="native session tests ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.candidate = self.root / "candidate"
        self.source = self.candidate / "source"
        self.repository = self.root / "repository"
        self.source.mkdir(parents=True)
        (self.repository / "experimental").mkdir(parents=True)
        (self.source / "Cargo.lock").write_bytes(b"synthetic lock\n")
        for name in native_build.STACKS["fragment"]:
            (self.repository / "experimental" / name).write_bytes(name.encode())
        self.binary = self.candidate / "niri"
        self.binary.write_bytes(b"synthetic executable, never run\n")
        self.binary.chmod(0o755)
        self.config = self.root / "config.kdl"
        self.config.write_text("animations {}\n")
        self.destination = self.root / "installed"
        self.stage_state = self.destination / "state/staging"
        self.selection_state = self.destination / "state/selection"
        self.manifest_path = self.candidate / "manifest.json"
        rustc = "rustc 1.99.0 (fixture 2026-01-01)"
        self.record = {
            "revision": native_build.REVISION,
            "binary": str(self.binary),
            "binary_sha256": native_build.digest(self.binary),
            "build_profile": "release",
            "build_flags": ["--locked"],
            "rustc": rustc,
        }
        for name in native_build.STACKS["fragment"]:
            self.record[native_build.PATCH_FIELDS[name]] = native_build.digest(
                self.repository / "experimental" / name
            )
        self.record["native_build"] = native_build.metadata(
            self.record,
            variant="fragment",
            lock_sha256=native_build.digest(self.source / "Cargo.lock"),
            target="x86_64-unknown-linux-gnu",
            features=["default", *native_build.DESKTOP_FEATURES],
            rustc_verbose=f"{rustc}\nhost: x86_64-unknown-linux-gnu",
        )
        self.save_record()
        validator = patch("niri_fx.setup.validate_config")
        self.validator = validator.start()
        self.addCleanup(validator.stop)

    def save_record(self):
        self.manifest_path.write_text(json.dumps(self.record))

    def plan(self):
        return native_session.stage_plan(
            self.manifest_path, self.source, self.repository, self.config, self.destination
        )

    def stage(self):
        plan = self.plan()
        setup.apply_plan(plan, self.stage_state, setup.plan_fingerprint(plan))
        return plan["selection"]["bundle_id"]

    def apply_selection(self, plan):
        return setup.apply_plan(plan, self.selection_state, setup.plan_fingerprint(plan))

    def test_review_is_read_only_and_apply_keeps_original_inputs_independent(self):
        before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
        plan = self.plan()
        self.validator.assert_not_called()
        self.assertFalse(self.destination.exists())
        setup.apply_plan(plan, self.stage_state, setup.plan_fingerprint(plan))
        bundle_id = plan["selection"]["bundle_id"]
        report = native_session.inspect_bundle(self.destination, bundle_id)
        for path, data in before.items():
            self.assertEqual(path.read_bytes(), data)
        self.assertNotEqual(Path(report["binary"]).stat().st_ino, self.binary.stat().st_ino)
        self.assertEqual(Path(report["config"]).read_bytes(), self.config.read_bytes())
        self.assertFalse((self.destination / "selection.json").exists())
        self.validator.assert_called_once_with(report["config"], report["binary"])
        self.assertEqual(report["desktop_prerequisites"], "satisfied")
        self.assertEqual(report["runtime_acceptance"], "not_assessed")
        self.assertEqual(self.plan()["changes"], [])

    def test_frozen_bundle_survives_original_candidate_removal(self):
        bundle_id = self.stage()
        for folder in (self.candidate, self.repository):
            for path in folder.rglob("*"):
                if path.is_file():
                    path.unlink()
        self.config.unlink()
        report = native_session.inspect_bundle(self.destination, bundle_id)
        self.assertEqual(report["bundle_id"], bundle_id)
        self.apply_selection(native_session.select_plan(self.destination, bundle_id))
        self.assertEqual(native_session.load_selection(self.destination)["selected"], bundle_id)

    def test_installed_bundle_survives_next_upstream_pin_without_accepting_new_stale_stage(self):
        bundle_id = self.stage()
        with patch.object(native_build, "REVISION", "f" * 40):
            native_session.inspect_bundle(self.destination, bundle_id)
            with self.assertRaisesRegex(ValueError, "different upstream revision"):
                self.plan()

    def test_changed_or_missing_candidate_inputs_refuse_before_writing(self):
        plan = self.plan()
        (self.source / "Cargo.lock").write_text("changed\n")
        with self.assertRaisesRegex(ValueError, "File changed"):
            setup.apply_plan(plan, self.stage_state)
        self.assertFalse((self.destination / "bundles").exists())
        with self.assertRaisesRegex(ValueError, "Candidate cannot be staged"):
            self.plan()

    def test_desktop_build_gate_rejects_minimal_debug_and_missing_features(self):
        original = copy.deepcopy(self.record)
        for mode in ("minimal", "debug", "missing-feature"):
            with self.subTest(mode=mode):
                self.record = copy.deepcopy(original)
                block = self.record["native_build"]
                inputs = block["inputs"]
                if mode == "minimal":
                    self.record["build_flags"] = inputs["cargo_flags"] = [
                        "--locked",
                        "--no-default-features",
                    ]
                    inputs["default_features"] = False
                    inputs["enabled_features"] = []
                elif mode == "debug":
                    self.record["build_profile"] = inputs["profile"] = "debug"
                else:
                    inputs["enabled_features"].remove("pipewire")
                block["build_id"] = native_build.fingerprint(inputs)
                self.save_record()
                with self.assertRaisesRegex(ValueError, "Desktop build requires"):
                    self.plan()
        self.assertFalse(self.destination.exists())
        self.validator.assert_not_called()

    def test_includes_rejected_but_comments_and_shader_strings_are_opaque(self):
        for text in (
            'include "base.kdl"\n',
            '"include" "base.kdl"\n',
            'r#"include"# "base.kdl"\n',
            'animations { include "base.kdl"; }\n',
        ):
            self.config.write_text(text)
            with self.assertRaisesRegex(ValueError, "no active include"):
                self.plan()
        for text in (
            '// include "base.kdl"\nanimations {}\n',
            '/- include "base.kdl"\nanimations {}\n',
            'animations { custom-shader r#"include something"#; }\n',
        ):
            self.config.write_text(text)
            self.plan()
        self.assertFalse(self.destination.exists())

    def test_typed_includes_are_rejected_including_quoted_and_spaced_annotations(self):
        for text in (
            '(custom)include "base.kdl"\n',
            '("custom type")"include" "base.kdl"\n',
            '(custom) include "base.kdl"\n',
        ):
            self.config.write_text(text)
            with self.assertRaisesRegex(ValueError, "node type annotations"):
                self.plan()
        self.config.write_text('/- (custom)include "base.kdl"\nanimations {}\n')
        self.plan()

    def test_symlinks_special_files_and_nonexecutable_candidates_rejected(self):
        data = self.config.read_bytes()
        self.config.unlink()
        self.config.symlink_to(self.source / "Cargo.lock")
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.plan()
        self.config.unlink()
        os.mkfifo(self.config)
        with self.assertRaisesRegex(ValueError, "regular file"):
            self.plan()
        self.config.unlink()
        self.config.write_bytes(data)
        self.binary.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "not executable"):
            self.plan()
        self.binary.chmod(0o755)
        self.destination.symlink_to(self.candidate)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            self.plan()

    def test_failed_stage_removes_partial_files_and_can_be_retried(self):
        plan = self.plan()
        self.validator.side_effect = ValueError("invalid config")
        with self.assertRaisesRegex(ValueError, "invalid config"):
            setup.apply_plan(plan, self.stage_state)
        folder = self.destination / "bundles" / plan["selection"]["bundle_id"]
        self.assertFalse(any(path.is_file() for path in folder.rglob("*")))
        self.validator.side_effect = None
        self.stage()

    def test_generic_restore_does_not_remove_retained_session_bundles(self):
        bundle_id = self.stage()
        with self.assertRaisesRegex(ValueError, "native rollback"):
            setup.restore(self.stage_state, apply=True)
        native_session.inspect_bundle(self.destination, bundle_id)
        self.apply_selection(native_session.select_plan(self.destination, bundle_id))
        with self.assertRaisesRegex(ValueError, "native rollback"):
            setup.restore(self.selection_state, apply=True)
        self.assertEqual(native_session.load_selection(self.destination)["selected"], bundle_id)

    def test_partial_or_edited_bundle_is_never_overwritten(self):
        plan = self.plan()
        folder = self.destination / "bundles" / plan["selection"]["bundle_id"]
        folder.mkdir(parents=True)
        (folder / "config.kdl").write_text("unowned\n")
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            self.plan()
        (folder / "config.kdl").unlink()
        bundle_id = self.stage()
        (folder / "config.kdl").write_text("edited\n")
        with self.assertRaisesRegex(ValueError, "contents changed"):
            native_session.select_plan(self.destination, bundle_id)
        self.assertEqual(
            native_session.status(self.destination)["bundles"][0]["status"], "unavailable"
        )
        with self.assertRaisesRegex(ValueError, "contents changed"):
            self.plan()

    def test_bundle_config_binary_mode_and_provenance_drift_are_detected(self):
        bundle_id = self.stage()
        folder = self.destination / "bundles" / bundle_id
        for relative in (
            "config.kdl",
            "bin/niri",
            "provenance/Cargo.lock",
            "provenance/experimental/niri-movement.patch",
        ):
            path = folder / relative
            original = path.read_bytes()
            path.write_bytes(original + b"changed")
            with self.assertRaises(ValueError):
                native_session.inspect_bundle(self.destination, bundle_id)
            path.write_bytes(original)
        binary = folder / "bin/niri"
        binary.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "permissions"):
            native_session.inspect_bundle(self.destination, bundle_id)
        binary.chmod(0o755)
        (folder / "config.kdl").unlink()
        (folder / "config.kdl").symlink_to(self.config)
        with self.assertRaisesRegex(ValueError, "symlinks"):
            native_session.inspect_bundle(self.destination, bundle_id)

    def test_selection_and_rollback_retain_binary_and_config_pairs(self):
        first = self.stage()
        self.config.write_text("animations { slowdown 0.8; }\n")
        second = self.stage()
        self.assertNotEqual(first, second)
        self.validator.reset_mock()
        select = native_session.select_plan(self.destination, first)
        self.validator.assert_not_called()
        self.apply_selection(select)
        self.assertEqual(
            native_session.load_selection(self.destination),
            {"schema": 1, "selected": first, "previous": None},
        )
        self.assertEqual(native_session.select_plan(self.destination, first)["changes"], [])
        self.apply_selection(native_session.select_plan(self.destination, second))
        self.apply_selection(native_session.rollback_plan(self.destination))
        self.assertEqual(
            native_session.load_selection(self.destination),
            {"schema": 1, "selected": first, "previous": second},
        )
        self.assertEqual(len(native_session.status(self.destination)["bundles"]), 2)
        for bundle_id in (first, second):
            native_session.inspect_bundle(self.destination, bundle_id)

    def test_first_selection_rolls_back_to_no_selection_without_deleting_bundle(self):
        self.assertEqual(
            native_session.status(self.destination)["selection"], {"schema": 1, "selected": None}
        )
        with self.assertRaisesRegex(ValueError, "No previous"):
            native_session.rollback_plan(self.destination)
        bundle_id = self.stage()
        self.apply_selection(native_session.select_plan(self.destination, bundle_id))
        self.apply_selection(native_session.rollback_plan(self.destination))
        self.assertIsNone(native_session.load_selection(self.destination)["selected"])
        native_session.inspect_bundle(self.destination, bundle_id)
        self.apply_selection(native_session.rollback_plan(self.destination))
        self.assertEqual(native_session.load_selection(self.destination)["selected"], bundle_id)

    def test_selection_conflict_and_plan_fingerprint_prevent_stale_apply(self):
        first = self.stage()
        first_plan = native_session.select_plan(self.destination, first)
        self.config.write_text("animations { slowdown 0.9; }\n")
        second = self.stage()
        second_plan = native_session.select_plan(self.destination, second)
        with self.assertRaisesRegex(ValueError, "plan changed"):
            setup.apply_plan(second_plan, self.selection_state, setup.plan_fingerprint(first_plan))
        self.apply_selection(first_plan)
        with self.assertRaisesRegex(ValueError, "File changed"):
            setup.apply_plan(second_plan, self.selection_state)
        self.assertEqual(native_session.load_selection(self.destination)["selected"], first)

    def test_file_permissions_changed_after_review_refuse_stage_and_selection(self):
        plan = self.plan()
        self.binary.chmod(0o700)
        with self.assertRaisesRegex(ValueError, "permissions changed"):
            setup.apply_plan(plan, self.stage_state)
        self.binary.chmod(0o755)
        bundle_id = self.stage()
        plan = native_session.select_plan(self.destination, bundle_id)
        (self.destination / "bundles" / bundle_id / "bin/niri").chmod(0o700)
        with self.assertRaisesRegex(ValueError, "permissions changed"):
            self.apply_selection(plan)
        self.assertFalse((self.destination / "selection.json").exists())

    def test_fifo_replacement_after_review_refuses_without_blocking(self):
        plan = self.plan()
        self.config.unlink()
        os.mkfifo(self.config)
        with self.assertRaisesRegex(ValueError, "no longer a regular file"):
            setup.apply_plan(plan, self.stage_state)
        self.config.unlink()
        self.config.write_text("animations {}\n")
        bundle_id = self.stage()
        plan = native_session.select_plan(self.destination, bundle_id)
        config = self.destination / "bundles" / bundle_id / "config.kdl"
        config.unlink()
        os.mkfifo(config)
        with self.assertRaisesRegex(ValueError, "no longer a regular file"):
            self.apply_selection(plan)

    def test_pointer_created_during_review_does_not_replace_previous_history(self):
        bundle_id = self.stage()
        inspect = native_session.inspect_bundle

        def competing_selection(root, identifier):
            report = inspect(root, identifier)
            path = root / "selection.json"
            path.write_text(json.dumps({"schema": 1, "selected": identifier, "previous": None}))
            path.chmod(0o600)
            return report

        with patch.object(native_session, "inspect_bundle", side_effect=competing_selection):
            with self.assertRaisesRegex(ValueError, "File changed"):
                native_session.select_plan(self.destination, bundle_id)
        self.assertEqual(native_session.load_selection(self.destination)["selected"], bundle_id)

    def test_validation_failure_restores_prior_selector_and_keeps_both_bundles(self):
        first = self.stage()
        self.apply_selection(native_session.select_plan(self.destination, first))
        selection_before = (self.destination / "selection.json").read_bytes()
        self.config.write_text("animations { slowdown 0.9; }\n")
        second = self.stage()
        self.validator.side_effect = ValueError("library dependency unavailable")
        with self.assertRaisesRegex(ValueError, "dependency unavailable"):
            self.apply_selection(native_session.select_plan(self.destination, second))
        self.assertEqual((self.destination / "selection.json").read_bytes(), selection_before)
        for bundle_id in (first, second):
            native_session.inspect_bundle(self.destination, bundle_id)

    def test_selection_cannot_follow_mutated_bundle_or_edited_pointer(self):
        bundle_id = self.stage()
        plan = native_session.select_plan(self.destination, bundle_id)
        config = self.destination / "bundles" / bundle_id / "config.kdl"
        config.write_text("edited\n")
        with self.assertRaisesRegex(ValueError, "File changed"):
            self.apply_selection(plan)
        selection = self.destination / "selection.json"
        selection.write_text(json.dumps({"schema": 1, "selected": "../../foreign"}))
        selection.chmod(0o600)
        with self.assertRaisesRegex(ValueError, "Invalid native session selection"):
            native_session.load_selection(self.destination)
        with self.assertRaisesRegex(ValueError, "Invalid native session bundle ID"):
            native_session.inspect_bundle(self.destination, "../../foreign")

    def test_receipt_identity_cannot_be_repaired_by_rehashing_only_config(self):
        bundle_id = self.stage()
        folder = self.destination / "bundles" / bundle_id
        config = folder / "config.kdl"
        config.write_text("edited\n")
        receipt_file = folder / "bundle.json"
        receipt = json.loads(receipt_file.read_text())
        receipt["config_sha256"] = digest(config.read_bytes())
        receipt_file.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "identity is invalid"):
            native_session.inspect_bundle(self.destination, bundle_id)


if __name__ == "__main__":
    unittest.main()
