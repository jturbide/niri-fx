"""Metadata-only storage inspection against owned temporary filesystem trees."""

import errno
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from niri_fx import native_storage as storage


class NativeStorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nirifx-storage-test-")
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        self.root = self.parent / "bundle"
        self.root.mkdir()

    def codes(self, report):
        return {item["code"] for item in report["errors"]}

    def test_empty_directory_has_confirmed_zero_totals(self):
        report = storage.inspect_storage(self.root)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["logical_bytes"], 0)
        self.assertEqual(report["allocated_bytes"], 0)
        self.assertEqual(report["observed"]["directories"], 1)
        self.assertEqual(report["observed"]["entries"], 0)
        self.assertEqual(report["errors"], [])

    def test_regular_file_totals_are_metadata_sizes_and_blocks_only(self):
        first = self.root / "first"
        first.write_bytes(b"hello")
        folder = self.root / "config"
        folder.mkdir()
        second = folder / "second"
        second.write_bytes(b"world!")
        report = storage.inspect_storage(self.root)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["logical_bytes"], 11)
        self.assertEqual(
            report["allocated_bytes"], (first.stat().st_blocks + second.stat().st_blocks) * 512
        )
        self.assertEqual(report["observed"]["regular_files"], 2)
        self.assertEqual(report["observed"]["directories"], 2)
        self.assertEqual(report["observed"]["entries"], 3)
        self.assertEqual(report, storage.inspect_storage(self.root))

    def test_hardlinks_are_counted_but_bytes_are_deduplicated(self):
        original = self.root / "original"
        original.write_bytes(b"shared")
        (self.root / "nested").mkdir()
        os.link(original, self.root / "alias")
        os.link(original, self.root / "nested/another-alias")
        report = storage.inspect_storage(self.root)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["logical_bytes"], 6)
        self.assertEqual(report["allocated_bytes"], original.stat().st_blocks * 512)
        self.assertEqual(report["observed"]["regular_files"], 3)
        self.assertEqual(report["observed"]["unique_regular_files"], 1)
        self.assertEqual(report["observed"]["hardlink_aliases"], 2)

    def test_sparse_logical_size_is_distinct_from_allocated_size(self):
        path = self.root / "sparse"
        with path.open("wb") as stream:
            stream.truncate(8 * 1024 * 1024)
        report = storage.inspect_storage(self.root)
        self.assertEqual(report["logical_bytes"], path.stat().st_size)
        self.assertEqual(report["allocated_bytes"], path.stat().st_blocks * 512)
        self.assertEqual(report["status"], "complete")

    def test_external_symlinks_loops_and_fifo_are_never_opened(self):
        external = self.parent / "outside"
        external.mkdir()
        (external / "large").write_bytes(b"x" * 8192)
        (self.root / "external").symlink_to(external, target_is_directory=True)
        (self.root / "loop").symlink_to(self.root, target_is_directory=True)
        os.mkfifo(self.root / "pipe")
        (self.root / "owned").write_bytes(b"yes")
        opened = []
        original = os.open

        def directory_only(path, flags, *args, **kwargs):
            self.assertTrue(flags & os.O_DIRECTORY)
            self.assertTrue(flags & os.O_NOFOLLOW)
            opened.append(str(path))
            return original(path, flags, *args, **kwargs)

        with patch.object(storage.os, "open", side_effect=directory_only):
            report = storage.inspect_storage(self.root)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["logical_bytes"], 3)
        self.assertEqual(report["observed"]["symlinks"], 2)
        self.assertEqual(report["observed"]["special_files"], 1)
        self.assertEqual(
            {item["path"] for item in report["excluded"]}, {"external", "loop", "pipe"}
        )
        self.assertTrue(all(name not in opened for name in ("external", "loop", "pipe", "owned")))

    def test_root_and_ancestor_symlinks_are_unavailable(self):
        alias = self.parent / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        (self.root / "nested").mkdir()
        for path in (alias, alias / "nested", alias / ".." / "bundle"):
            with self.subTest(path=path):
                report = storage.inspect_storage(path)
                self.assertEqual(report["status"], "unavailable")
                self.assertIn("symlink-root-or-ancestor", self.codes(report))
                self.assertIsNone(report["logical_bytes"])
                self.assertIsNone(report["allocated_bytes"])

    def test_relative_traversal_does_not_normalize_away_symlink(self):
        alias = self.parent / "alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with patch.object(storage.Path, "cwd", return_value=self.parent):
            report = storage.inspect_storage(Path("alias") / ".." / "bundle")
        self.assertEqual(report["status"], "unavailable")
        self.assertIn("symlink-root-or-ancestor", self.codes(report))

    def test_missing_root_and_regular_file_root_are_not_reported_as_zero(self):
        file = self.parent / "ordinary"
        file.write_bytes(b"text")
        for path in (self.parent / "missing", file):
            with self.subTest(path=path):
                report = storage.inspect_storage(path)
                self.assertEqual(report["status"], "unavailable")
                self.assertIsNone(report["logical_bytes"])
                self.assertIsNone(report["allocated_bytes"])
                self.assertTrue(report["errors"])

    def test_unreadable_child_produces_partial_observations_and_unknown_totals(self):
        (self.root / "accessible").write_bytes(b"known")
        (self.root / "blocked").mkdir()
        original = os.open

        def fail_child(path, flags, *args, **kwargs):
            if str(path) == "blocked":
                raise PermissionError(errno.EACCES, "Test directory access refused")
            return original(path, flags, *args, **kwargs)

        with patch.object(storage.os, "open", side_effect=fail_child):
            report = storage.inspect_storage(self.root)
        self.assertEqual(report["status"], "incomplete")
        self.assertIsNone(report["logical_bytes"])
        self.assertIsNone(report["allocated_bytes"])
        self.assertEqual(report["observed"]["logical_bytes"], 5)
        self.assertEqual(report["observed"]["directories"], 2)
        self.assertIn("permission-denied", self.codes(report))

    def test_file_mutation_between_walk_and_verification_is_incomplete(self):
        file = self.root / "data"
        file.write_bytes(b"before")
        original = storage._stat_at
        calls = 0

        def mutate(parent, name):
            nonlocal calls
            if name == "data":
                calls += 1
                if calls == 2:
                    file.write_bytes(b"changed contents")
            return original(parent, name)

        with patch.object(storage, "_stat_at", side_effect=mutate):
            report = storage.inspect_storage(self.root)
        self.assertEqual(report["status"], "incomplete")
        self.assertIsNone(report["logical_bytes"])
        self.assertIn("entry-changed", self.codes(report))

    def test_directory_replaced_by_symlink_is_never_followed(self):
        child = self.root / "child"
        child.mkdir()
        external = self.parent / "external"
        external.mkdir()
        (external / "secret").write_bytes(b"must not be measured")
        original = os.open
        changed = False

        def substitute(path, flags, *args, **kwargs):
            nonlocal changed
            if str(path) == "child" and not changed:
                changed = True
                child.rename(self.root / "retained")
                child.symlink_to(external, target_is_directory=True)
            return original(path, flags, *args, **kwargs)

        with patch.object(storage.os, "open", side_effect=substitute):
            report = storage.inspect_storage(self.root)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["observed"]["regular_files"], 0)
        self.assertIsNone(report["logical_bytes"])
        self.assertTrue(report["errors"])

    def test_root_replacement_does_not_misattribute_pinned_directory(self):
        (self.root / "data").write_bytes(b"original")
        external = self.parent / "external"
        external.mkdir()
        original = storage._stat_at
        changed = False

        def substitute(parent, name):
            nonlocal changed
            if name == "data" and not changed:
                changed = True
                self.root.rename(self.parent / "retained")
                self.root.symlink_to(external, target_is_directory=True)
            return original(parent, name)

        with patch.object(storage, "_stat_at", side_effect=substitute):
            report = storage.inspect_storage(self.root)
        self.assertEqual(report["status"], "incomplete")
        self.assertIn("ancestor-changed", self.codes(report))
        self.assertIsNone(report["logical_bytes"])

    def test_exact_entry_limit_is_complete_and_one_more_is_incomplete(self):
        for i in range(3):
            (self.root / str(i)).write_bytes(b"x")
        with patch.object(storage, "MAX_ENTRIES", 3):
            exact = storage.inspect_storage(self.root)
            (self.root / "extra").write_bytes(b"x")
            exceeded = storage.inspect_storage(self.root)
        self.assertEqual(exact["status"], "complete")
        self.assertEqual(exact["logical_bytes"], 3)
        self.assertEqual(exceeded["status"], "incomplete")
        self.assertIsNone(exceeded["logical_bytes"])
        self.assertEqual(exceeded["observed"]["entries"], 3)
        self.assertIn("entry-limit", self.codes(exceeded))

    def test_nested_directory_names_share_one_global_entry_budget(self):
        for i in range(3):
            folder = self.root / f"dir-{i}"
            folder.mkdir()
            for j in range(8):
                (folder / str(j)).write_bytes(b"x")
        with patch.object(storage, "MAX_ENTRIES", 5):
            report = storage.inspect_storage(self.root)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["observed"]["entries"], 5)
        self.assertEqual(report["observed"]["regular_files"], 2)
        self.assertEqual(report["observed"]["directories"], 4)
        self.assertIsNone(report["allocated_bytes"])

    def test_depth_limit_refuses_deeper_traversal(self):
        deepest = self.root / "first/second"
        deepest.mkdir(parents=True)
        (deepest / "data").write_bytes(b"unvisited")
        with patch.object(storage, "MAX_DEPTH", 1):
            report = storage.inspect_storage(self.root)
        self.assertEqual(report["status"], "incomplete")
        self.assertIn("depth-limit", self.codes(report))
        self.assertEqual(report["observed"]["regular_files"], 0)
        self.assertEqual(report["observed"]["directories"], 3)

    def test_exclusion_details_are_bounded_without_losing_counts(self):
        for i in range(3):
            (self.root / str(i)).symlink_to(self.parent / "missing-target")
        with patch.object(storage, "MAX_DETAILS", 1):
            report = storage.inspect_storage(self.root)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["observed"]["symlinks"], 3)
        self.assertEqual(len(report["excluded"]), 1)
        self.assertEqual(report["omitted_exclusions"], 2)

    def test_regular_file_read_permission_is_not_required(self):
        file = self.root / "metadata-only"
        file.write_bytes(b"secret contents need not be opened")
        file.chmod(0)
        report = storage.inspect_storage(self.root)
        self.assertEqual(report["status"], "complete")
        self.assertEqual(report["logical_bytes"], file.stat().st_size)

    def test_unavailable_allocation_is_not_reported_as_zero(self):
        file = self.root / "data"
        file.write_bytes(b"known logical bytes")
        original = storage._stat_at

        def unsupported_blocks(parent, name):
            info = original(parent, name)
            if name != "data":
                return info
            fields = {
                key: getattr(info, key)
                for key in (
                    "st_dev",
                    "st_ino",
                    "st_mode",
                    "st_nlink",
                    "st_size",
                    "st_mtime_ns",
                    "st_ctime_ns",
                )
            }
            return SimpleNamespace(**fields)

        with patch.object(storage, "_stat_at", side_effect=unsupported_blocks):
            report = storage.inspect_storage(self.root)
        self.assertEqual(report["status"], "incomplete")
        self.assertIsNone(report["allocated_bytes"])
        self.assertIsNone(report["observed"]["allocated_bytes"])
        self.assertEqual(report["observed"]["logical_bytes"], file.stat().st_size)
        self.assertIn("allocation-unavailable", self.codes(report))

    def test_opened_directory_descriptors_are_closed_on_error(self):
        opened, closed = [], []
        original_open, original_close = os.open, os.close

        def track_open(*args, **kwargs):
            descriptor = original_open(*args, **kwargs)
            opened.append(descriptor)
            return descriptor

        def track_close(descriptor):
            closed.append(descriptor)
            original_close(descriptor)

        with (
            patch.object(storage.os, "open", side_effect=track_open),
            patch.object(storage.os, "close", side_effect=track_close),
            patch.object(
                storage.os, "scandir", side_effect=PermissionError(errno.EACCES, "No listing")
            ),
        ):
            report = storage.inspect_storage(self.root)
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(sorted(opened), sorted(closed))
        self.assertIsNone(report["logical_bytes"])


if __name__ == "__main__":
    unittest.main()
