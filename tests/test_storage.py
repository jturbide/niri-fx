import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from niri_fx.storage import atomic_write, read_bytes, staged_write


class StorageTests(unittest.TestCase):
    def test_aborted_stage_preserves_original_and_removes_temporary(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "config"
            target.write_bytes(b"original")
            with self.assertRaisesRegex(ValueError, "conflict"):
                with staged_write(target, b"replacement", 0o640) as stage:
                    self.assertEqual(stage.read_bytes(), b"replacement")
                    self.assertEqual(stage.stat().st_mode & 0o777, 0o640)
                    self.assertEqual(target.read_bytes(), b"original")
                    raise ValueError("conflict")
            self.assertEqual(list(Path(temporary).iterdir()), [target])
            self.assertEqual(target.read_bytes(), b"original")

    def test_failed_rename_keeps_old_contents_and_cleans_stage(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "config"
            target.write_bytes(b"original")
            with patch("niri_fx.storage.os.replace", side_effect=OSError("rename failed")):
                with self.assertRaisesRegex(OSError, "rename failed"):
                    atomic_write(target, b"replacement")
            self.assertEqual(target.read_bytes(), b"original")
            self.assertEqual(list(Path(temporary).iterdir()), [target])

    def test_empty_file_and_absent_file_have_different_restore_meanings(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "config"
            self.assertIsNone(read_bytes(target))
            atomic_write(target, b"", 0o640)
            self.assertEqual(read_bytes(target), b"")
            self.assertEqual(target.stat().st_mode & 0o777, 0o640)
            atomic_write(target, None)
            self.assertIsNone(read_bytes(target))
