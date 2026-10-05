"""Launcher link transactions never write through an existing runtime target."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from niri_fx import setup


class SetupLinkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"
        self.link = self.root / "bin/niri-fx"
        self.old = self.root / "old-runtime"
        self.old.write_bytes(b"original executable")
        self.new = self.root / "new-runtime"
        self.new.write_bytes(b"replacement executable")

    def plan(self, *items, target="launcher-test"):
        observed = list(items) or [setup.link_change(self.link, self.new)]
        return {
            "target": target,
            "notes": [],
            "validation_config": None,
            "observed": observed,
            "changes": [item for item in observed if item["before"] != item["after"]],
        }

    def existing(self, target=None):
        self.link.parent.mkdir()
        self.link.symlink_to(self.old if target is None else target)

    def manifest(self, result):
        return json.loads((self.state / result["transaction"] / "manifest.json").read_text())

    def test_first_install_review_is_read_only_and_restore_removes_only_link(self):
        plan = self.plan()
        self.assertFalse(self.link.parent.exists())
        self.assertFalse(self.state.exists())
        self.assertEqual(plan["changes"][0]["logical"], str(self.link))
        self.assertEqual(plan["changes"][0]["target"], str(self.link))
        result = setup.apply_plan(plan, self.state, setup.plan_fingerprint(plan))
        self.assertEqual(os.readlink(self.link), str(self.new))
        self.assertEqual(self.manifest(result)["files"][0]["kind"], "symlink")
        reviewed = setup.restore(self.state, result["transaction"])
        self.assertTrue(reviewed["dry_run"])
        self.assertTrue(self.link.is_symlink())
        setup.restore(self.state, result["transaction"], apply=True)
        self.assertFalse(self.link.is_symlink())
        self.assertEqual(self.new.read_bytes(), b"replacement executable")

    def test_replacement_and_restore_preserve_relative_target_and_file_contents(self):
        self.existing("../old-runtime")
        plan = self.plan()
        self.assertEqual(plan["changes"][0]["before"], b"../old-runtime")
        result = setup.apply_plan(plan, self.state)
        self.assertEqual(self.old.read_bytes(), b"original executable")
        self.assertEqual(self.new.read_bytes(), b"replacement executable")
        setup.restore(self.state, result["transaction"], apply=True)
        self.assertEqual(os.readlink(self.link), "../old-runtime")
        self.assertEqual(self.old.read_bytes(), b"original executable")
        self.assertEqual(self.new.read_bytes(), b"replacement executable")

    def test_dangling_link_can_be_repointed_and_restored_exactly(self):
        self.existing("../absent-runtime")
        result = setup.apply_plan(self.plan(), self.state)
        setup.restore(self.state, result["transaction"], apply=True)
        self.assertEqual(os.readlink(self.link), "../absent-runtime")
        self.assertFalse(self.link.exists())
        self.assertTrue(self.link.is_symlink())

    def test_deletion_restores_exact_link(self):
        self.existing()
        result = setup.apply_plan(self.plan(setup.link_change(self.link, None)), self.state)
        self.assertFalse(self.link.is_symlink())
        setup.restore(self.state, result["transaction"], apply=True)
        self.assertEqual(os.readlink(self.link), str(self.old))
        self.assertEqual(self.old.read_bytes(), b"original executable")

    def test_matching_target_is_idempotent(self):
        setup.apply_plan(self.plan(), self.state)
        count = len(list(self.state.glob("*/manifest.json")))
        result = setup.apply_plan(self.plan(), self.state)
        self.assertFalse(result["changed"])
        self.assertIsNone(result["transaction"])
        self.assertEqual(len(list(self.state.glob("*/manifest.json"))), count)

    def test_regular_file_and_directory_collisions_are_refused(self):
        self.link.parent.mkdir()
        self.link.write_bytes(b"user command")
        with self.assertRaisesRegex(ValueError, "non-symlink"):
            self.plan()
        self.assertEqual(self.link.read_bytes(), b"user command")
        self.link.unlink()
        self.link.mkdir()
        with self.assertRaisesRegex(ValueError, "non-symlink"):
            self.plan()

    def test_linked_ancestor_is_rejected_even_for_missing_link(self):
        actual = self.root / "actual-bin"
        actual.mkdir()
        self.link.parent.symlink_to(actual)
        with self.assertRaisesRegex(ValueError, "directory ancestors"):
            self.plan()
        self.assertFalse((actual / self.link.name).exists())

    def test_parent_retarget_after_review_is_refused(self):
        plan = self.plan()
        actual = self.root / "actual-bin"
        actual.mkdir()
        self.link.parent.symlink_to(actual)
        with self.assertRaisesRegex(ValueError, "directory ancestors"):
            setup.apply_plan(plan, self.state)
        self.assertEqual(list(actual.iterdir()), [])

    def test_retarget_after_review_is_refused_without_touching_either_file(self):
        self.existing()
        plan = self.plan()
        self.link.unlink()
        self.link.symlink_to("../external")
        with self.assertRaisesRegex(ValueError, "Link changed"):
            setup.apply_plan(plan, self.state)
        self.assertEqual(os.readlink(self.link), "../external")
        self.assertEqual(self.old.read_bytes(), b"original executable")
        self.assertEqual(self.new.read_bytes(), b"replacement executable")

    def test_file_created_after_review_is_refused(self):
        plan = self.plan()
        self.link.parent.mkdir()
        self.link.write_bytes(b"external command")
        with self.assertRaisesRegex(ValueError, "non-symlink"):
            setup.apply_plan(plan, self.state)
        self.assertEqual(self.link.read_bytes(), b"external command")

    def test_link_kind_and_target_are_bound_to_review(self):
        link_plan = self.plan()
        file_plan = self.plan(setup.change(self.link, os.fsencode(self.new)))
        file_plan["changes"][0]["mode"] = None
        self.assertNotEqual(setup.plan_fingerprint(link_plan), setup.plan_fingerprint(file_plan))
        alternate = self.plan(setup.link_change(self.link, self.old))
        with self.assertRaisesRegex(ValueError, "plan changed"):
            setup.apply_plan(alternate, self.state, setup.plan_fingerprint(link_plan))
        self.assertFalse(self.link.parent.exists())

    def test_handled_failure_restores_link_and_regular_files(self):
        self.existing()
        config = self.root / "config.kdl"
        config.write_bytes(b"old config")
        plan = self.plan(
            setup.link_change(self.link, self.new), setup.change(config, b"new config")
        )
        plan["validation_config"] = str(config)
        with patch.object(setup, "validate_config", side_effect=ValueError("invalid config")):
            with self.assertRaisesRegex(ValueError, "invalid config"):
                setup.apply_plan(plan, self.state)
        self.assertEqual(os.readlink(self.link), str(self.old))
        self.assertEqual(config.read_bytes(), b"old config")
        self.assertEqual(self.old.read_bytes(), b"original executable")
        self.assertEqual(self.new.read_bytes(), b"replacement executable")
        manifest = json.loads(next(self.state.glob("*/manifest.json")).read_text())
        self.assertEqual(manifest["status"], "failed")

    def test_failed_transaction_preserves_concurrent_link_edit(self):
        self.existing()
        config = self.root / "config.kdl"
        plan = self.plan()
        plan["validation_config"] = str(config)

        def fail(_):
            self.link.unlink()
            self.link.symlink_to("../external")
            raise ValueError("validation failed")

        with patch.object(setup, "validate_config", side_effect=fail):
            with self.assertRaisesRegex(ValueError, "validation failed"):
                setup.apply_plan(plan, self.state)
        self.assertEqual(os.readlink(self.link), "../external")
        self.assertEqual(self.old.read_bytes(), b"original executable")

    def test_staged_link_is_cleaned_if_atomic_replacement_fails(self):
        self.existing()
        original_replace = setup.os.replace

        def fail_link(source, destination):
            if destination == self.link:
                raise OSError("rename failed")
            return original_replace(source, destination)

        with patch.object(setup.os, "replace", side_effect=fail_link):
            with self.assertRaisesRegex(OSError, "rename failed"):
                setup.apply_plan(self.plan(), self.state)
        self.assertEqual(os.readlink(self.link), str(self.old))
        self.assertEqual(list(self.link.parent.iterdir()), [self.link])

    def test_retarget_while_staging_is_preserved(self):
        self.existing()
        original_symlink = setup.os.symlink

        def create_then_retarget(target, path):
            original_symlink(target, path)
            self.link.unlink()
            original_symlink("../external", self.link)

        with patch.object(setup.os, "symlink", side_effect=create_then_retarget):
            with self.assertRaisesRegex(ValueError, "Link changed"):
                setup.apply_plan(self.plan(), self.state)
        self.assertEqual(os.readlink(self.link), "../external")
        self.assertEqual(list(self.link.parent.iterdir()), [self.link])

    def test_failed_restore_recovers_already_restored_link(self):
        self.existing()
        config = self.root / "config"
        config.write_bytes(b"old config")
        plan = self.plan(
            setup.change(config, b"new config"), setup.link_change(self.link, self.new)
        )
        result = setup.apply_plan(plan, self.state)
        original_write = setup.atomic_write

        def fail_restore(path, data, mode=0o600):
            if path == config and data == b"old config":
                raise OSError("restore failed")
            return original_write(path, data, mode)

        with patch.object(setup, "atomic_write", side_effect=fail_restore):
            with self.assertRaisesRegex(OSError, "restore failed"):
                setup.restore(self.state, result["transaction"], apply=True)
        self.assertEqual(os.readlink(self.link), str(self.new))
        self.assertEqual(config.read_bytes(), b"new config")
        self.assertEqual(self.manifest(result)["status"], "applied")

    def test_restore_refuses_external_link_retarget_or_regular_file_collision(self):
        result = setup.apply_plan(self.plan(), self.state)
        self.link.unlink()
        self.link.symlink_to("../external")
        with self.assertRaisesRegex(ValueError, "Link changed"):
            setup.restore(self.state, result["transaction"], apply=True)
        self.link.unlink()
        self.link.write_bytes(b"external command")
        with self.assertRaisesRegex(ValueError, "non-symlink"):
            setup.restore(self.state, result["transaction"], apply=True)
        self.assertEqual(self.link.read_bytes(), b"external command")

    def test_restore_checks_saved_link_target_hash(self):
        self.existing()
        result = setup.apply_plan(self.plan(), self.state)
        (self.state / result["transaction"] / "0.before").write_bytes(b"../tampered")
        with self.assertRaisesRegex(ValueError, "hash check"):
            setup.restore(self.state, result["transaction"], apply=True)
        self.assertEqual(os.readlink(self.link), str(self.new))

    def test_native_tools_require_specialized_rollback(self):
        result = setup.apply_plan(self.plan(target="native-tools-update"), self.state)
        with self.assertRaisesRegex(ValueError, "compatibility-checked runtime rollback"):
            setup.restore(self.state, result["transaction"], apply=True)
        self.assertEqual(os.readlink(self.link), str(self.new))


if __name__ == "__main__":
    unittest.main()
