"""Patch-stack checks preserve local changes and isolate optional native work."""

import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "native_build", ROOT / "scripts/build-niri-movement.py"
)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


class PatchStackTests(unittest.TestCase):
    def test_layered_patches_are_repeatable_and_preserve_unrelated_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()

            def git(*args):
                return subprocess.check_output(
                    ["git", *args], cwd=source, stderr=subprocess.DEVNULL
                )

            git("init")
            original = source / "window.rs"
            original.write_text("ordinary renderer\n")
            git("add", "window.rs")
            base = git("write-tree").decode().strip()
            original.write_text("ordinary renderer\nmovement shader\n")
            git("add", "window.rs")
            movement = git("write-tree").decode().strip()
            first = root / "movement.patch"
            first.write_bytes(git("diff", "--cached", base, "--binary", "--full-index"))
            extension = source / "pointer.rs"
            extension.write_text("pointer spring\n")
            original.write_text("ordinary renderer\nmovement shader\npointer hook\n")
            git("add", "window.rs", "pointer.rs")
            second = root / "pointer.patch"
            second.write_bytes(git("diff", "--cached", movement, "--binary", "--full-index"))
            pointer = git("write-tree").decode().strip()
            fragment = source / "fragment.rs"
            fragment.write_text("continuous fragments\n")
            git("add", "fragment.rs")
            third = root / "fragment.patch"
            third.write_bytes(git("diff", "--cached", pointer, "--binary", "--full-index"))
            git("read-tree", "--reset", "-u", base)

            # Fixtures use trees, not unsigned commits. Map the production HEAD
            # read to that original tree; every diff/apply still runs real Git.
            output = subprocess.check_output

            def from_tree(args, **kwargs):
                if args == ["git", "rev-parse", "HEAD"]:
                    return base + "\n"
                return output([base if arg == "HEAD" else arg for arg in args], **kwargs)

            with patch.object(build.subprocess, "check_output", side_effect=from_tree):
                # An unmodified baseline must accept a clean tree and reject
                # even the exact, otherwise supported experiment patch stack.
                build.apply_patches(source, base, [])
                self.assertEqual(original.read_text(), "ordinary renderer\n")
                build.apply_patches(source, base, [first, second])
                self.assertEqual(extension.read_text(), "pointer spring\n")
                self.assertIn("pointer hook", original.read_text())
                build.apply_patches(source, base, [first, second])
                with self.assertRaisesRegex(SystemExit, "refusing to overwrite"):
                    build.apply_patches(source, base, [])
                # Adding the third layer needs a separate checkout, preserving
                # a previously accepted pointer build and its evidence.
                with self.assertRaisesRegex(SystemExit, "refusing to overwrite"):
                    build.apply_patches(source, base, [first, second, third])

                # A base-only request cannot overwrite the optional extension.
                with self.assertRaisesRegex(SystemExit, "refusing to overwrite"):
                    build.apply_patches(source, base, [first])
                original.write_text(original.read_text() + "contributor edit\n")
                before = original.read_bytes()
                with self.assertRaisesRegex(SystemExit, "refusing to overwrite"):
                    build.apply_patches(source, base, [first, second])
                self.assertEqual(original.read_bytes(), before)
                original.write_bytes(before.removesuffix(b"contributor edit\n"))
                private = source / "untracked.rs"
                private.write_text("keep this work\n")
                with self.assertRaisesRegex(SystemExit, "refusing to overwrite"):
                    build.apply_patches(source, base, [first, second])
                self.assertEqual(private.read_text(), "keep this work\n")
                private.unlink()
                git("read-tree", "--reset", "-u", base)
                build.apply_patches(source, base, [first, second, third])
                build.apply_patches(source, base, [first, second, third])
                build.apply_patches(source, base, [first, second, third], verify_only=True)
                self.assertEqual(fragment.read_text(), "continuous fragments\n")
                with self.assertRaisesRegex(SystemExit, "refusing to overwrite"):
                    build.apply_patches(source, base, [first, second])
                # A concurrent pristine reset after compilation must fail the
                # verification step without applying patches to hide that reset.
                git("read-tree", "--reset", "-u", base)
                with self.assertRaisesRegex(SystemExit, "refusing to overwrite"):
                    build.apply_patches(source, base, [first, second, third], verify_only=True)
                self.assertEqual(original.read_text(), "ordinary renderer\n")
                self.assertFalse(fragment.exists())

    def test_wrong_revision_stops_before_applying(self):
        with patch.object(build.subprocess, "check_output", return_value="unexpected\n"):
            with self.assertRaisesRegex(SystemExit, "Source revision differs"):
                build.apply_patches(Path("unused"), "expected", [])
