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

    def plan(self, **kwargs):
        return native_session.stage_plan(
            self.manifest_path,
            self.source,
            self.repository,
            self.config,
            self.destination,
            **kwargs,
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
            with self.assertRaisesRegex(ValueError, "[Ii]nclude"):
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

    def test_status_distinguishes_running_next_login_and_rollback_without_writes(self):
        identifiers = []
        for slowdown in (0.8, 0.9, 1.0, 1.1):
            self.config.write_text(f"animations {{ slowdown {slowdown}; }}\n")
            identifiers.append(self.stage())
        first, previous, selected, unused = identifiers
        self.apply_selection(native_session.select_plan(self.destination, previous))
        self.apply_selection(native_session.select_plan(self.destination, selected))
        before = {path: path.read_bytes() for path in self.destination.rglob("*") if path.is_file()}
        self.validator.reset_mock()
        with patch(
            "niri_fx.native_runtime.inspect_running",
            return_value={"status": "matched", "bundle_id": first},
        ) as inspect:
            report = native_session.status(self.destination, socket_path="/example/niri.sock")
        inspect.assert_called_once()
        self.assertEqual(inspect.call_args.kwargs, {"socket_path": "/example/niri.sock"})
        self.assertEqual(len(inspect.call_args.args[0]), 4)
        by_id = {item["bundle_id"]: item for item in report["bundles"]}
        for bundle_id, roles in (
            (first, ["running"]),
            (previous, ["rollback"]),
            (selected, ["next-login"]),
            (unused, []),
        ):
            self.assertEqual(by_id[bundle_id]["roles"], roles)
            self.assertEqual(by_id[bundle_id]["storage"]["status"], "complete")
            self.assertGreater(by_id[bundle_id]["storage"]["logical_bytes"], 0)
        self.assertIn("does not establish", report["note"])
        self.assertEqual(
            before,
            {path: path.read_bytes() for path in self.destination.rglob("*") if path.is_file()},
        )
        self.validator.assert_not_called()

    def test_status_keeps_missing_selected_and_previous_bundles_visible(self):
        self.destination.mkdir()
        selection = self.destination / "selection.json"
        selection.write_text(json.dumps({"schema": 1, "selected": "a" * 64, "previous": "b" * 64}))
        selection.chmod(0o600)
        with patch(
            "niri_fx.native_runtime.inspect_running",
            return_value={"status": "unknown", "bundle_id": None},
        ) as inspect:
            report = native_session.status(self.destination)
        self.assertEqual(inspect.call_args.args[0], [])
        self.assertEqual(
            [item["roles"] for item in report["bundles"]], [["next-login"], ["rollback"]]
        )
        self.assertTrue(all(item["status"] == "unavailable" for item in report["bundles"]))
        self.assertFalse((self.destination / "bundles").exists())

    def test_status_combines_running_and_next_login_roles(self):
        selected = self.stage()
        self.apply_selection(native_session.select_plan(self.destination, selected))
        with patch(
            "niri_fx.native_runtime.inspect_running",
            return_value={"status": "matched", "bundle_id": selected},
        ):
            report = native_session.status(self.destination)
        self.assertEqual(report["bundles"][0]["roles"], ["next-login", "running"])

    def test_damaged_running_bundle_is_unknown_instead_of_external(self):
        selected = self.stage()
        self.apply_selection(native_session.select_plan(self.destination, selected))
        folder = self.destination / "bundles" / selected
        (folder / "config.kdl").write_text("changed after selection\n")
        with patch(
            "niri_fx.native_runtime.inspect_running",
            return_value={
                "status": "external",
                "bundle_id": None,
                "binary": str(folder / "bin/niri"),
            },
        ):
            report = native_session.status(self.destination)
        self.assertEqual(report["running"]["status"], "unknown")
        self.assertIsNone(report["running"]["bundle_id"])
        self.assertEqual(report["bundles"][0]["roles"], ["next-login"])
        self.assertEqual(report["bundles"][0]["status"], "unavailable")

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

    def test_include_snapshot_stages_a_closed_tree_and_survives_source_removal(self):
        included = self.root / "appearance.kdl"
        included.write_text("animations {}\n")
        self.config.write_text('include "appearance.kdl"\n')
        with self.assertRaisesRegex(ValueError, "self-contained"):
            self.plan()
        plan = self.plan(snapshot_includes=True)
        self.assertEqual(plan["selection"]["configuration"]["file_count"], 2)
        self.assertEqual(len(plan["selection"]["configuration"]["sources"]), 2)
        setup.apply_plan(plan, self.stage_state)
        bundle = plan["selection"]["bundle_id"]
        folder = self.destination / "bundles" / bundle
        receipt = json.loads((folder / "bundle.json").read_text())
        self.assertEqual(receipt["schema"], 2)
        self.assertEqual(set(receipt["config_files"]), {"config.kdl", "config/0001.kdl"})
        self.assertNotIn(str(self.root), (folder / "config.kdl").read_text())
        self.assertEqual(included.read_text(), "animations {}\n")
        self.config.unlink()
        included.unlink()
        report = native_session.inspect_bundle(self.destination, bundle)
        self.assertEqual(report["config_file_count"], 2)
        self.apply_selection(native_session.select_plan(self.destination, bundle))

    def test_changed_include_or_new_optional_file_invalidates_apply(self):
        included = self.root / "appearance.kdl"
        included.write_text("animations {}\n")
        self.config.write_text('include "appearance.kdl"\ninclude "later.kdl" optional=true\n')
        plan = self.plan(snapshot_includes=True)
        included.write_text("animations { off; }\n")
        with self.assertRaisesRegex(ValueError, "changed"):
            setup.apply_plan(plan, self.stage_state)
        plan = self.plan(snapshot_includes=True)
        (self.root / "later.kdl").write_text("animations {}\n")
        with self.assertRaisesRegex(ValueError, "changed"):
            setup.apply_plan(plan, self.stage_state)
        self.assertFalse((self.destination / "bundles").exists())

    def test_snapshot_rolls_back_to_legacy_pair_and_checks_every_file(self):
        legacy = self.stage()
        self.apply_selection(native_session.select_plan(self.destination, legacy))
        included = self.root / "appearance.kdl"
        included.write_text("animations {}\n")
        self.config.write_text('include "appearance.kdl"\n')
        plan = self.plan(snapshot_includes=True)
        setup.apply_plan(plan, self.stage_state)
        bundle = plan["selection"]["bundle_id"]
        self.apply_selection(native_session.select_plan(self.destination, bundle))
        self.apply_selection(native_session.rollback_plan(self.destination))
        self.assertEqual(native_session.load_selection(self.destination)["selected"], legacy)
        copied = self.destination / "bundles" / bundle / "config/0001.kdl"
        copied.write_text("animations { off; }\n")
        with self.assertRaisesRegex(ValueError, "included configuration changed"):
            native_session.rollback_plan(self.destination)
        self.assertEqual(native_session.load_selection(self.destination)["selected"], legacy)

    def test_snapshot_map_rejects_escaping_paths(self):
        self.config.write_text('include "appearance.kdl"\n')
        (self.root / "appearance.kdl").write_text("animations {}\n")
        plan = self.plan(snapshot_includes=True)
        setup.apply_plan(plan, self.stage_state)
        bundle = plan["selection"]["bundle_id"]
        receipt_file = self.destination / "bundles" / bundle / "bundle.json"
        receipt = json.loads(receipt_file.read_text())
        receipt["config_files"]["../../outside.kdl"] = "a" * 64
        receipt_file.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, "configuration file map"):
            native_session.inspect_bundle(self.destination, bundle)

    def test_bom_cannot_hide_external_include_in_stage_or_legacy_inspection(self):
        for node in ('include "outside.kdl"', '"include" "outside.kdl"'):
            self.config.write_text("\ufeff" + node + "\n")
            with self.subTest(node=node), self.assertRaisesRegex(ValueError, "self-contained"):
                self.plan()
        self.config.write_text("animations {}\n")
        old_id = self.stage()
        folder = self.destination / "bundles" / old_id
        config = folder / "config.kdl"
        config.write_text('\ufeffinclude "outside.kdl"\n')
        receipt_path = folder / "bundle.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["config_sha256"] = digest(config.read_bytes())
        new_id = native_session._bundle_id(
            receipt["binary_sha256"], receipt["config_sha256"], receipt["native_build"]
        )
        receipt["bundle_id"] = new_id
        receipt_path.write_text(json.dumps(receipt))
        folder.rename(folder.parent / new_id)
        with self.assertRaisesRegex(ValueError, "self-contained"):
            native_session.inspect_bundle(self.destination, new_id)


if __name__ == "__main__":
    unittest.main()
