"""A fast documentation path must never hide an application/configuration change."""

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ci_scope", ROOT / "scripts/ci_scope.py")
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)


class ScopeTests(unittest.TestCase):
    def test_only_known_documentation_and_media_skip_application_tests(self):
        self.assertTrue(
            scope.documentation_only(
                [
                    "README.md",
                    "docs/gifs/native-swap.gif",
                    "docs/gifs/native-manifest.json",
                    "docs/gallery/posters.json",
                ]
            )
        )
        for path in (
            "niri_fx/model.py",
            "docs/gallery.js",
            "examples/custom.json",
            "pyproject.toml",
            ".github/workflows/checks.yml",
            "scripts/ci_scope.py",
            "future-feature/file.txt",
        ):
            with self.subTest(path=path):
                self.assertFalse(scope.documentation_only(["README.md", path]))
        self.assertFalse(scope.documentation_only([]))

    def test_renamed_code_includes_its_deleted_source_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*args):
                return (
                    subprocess.check_output(
                        ["git", "-C", directory, *args], stderr=subprocess.DEVNULL
                    )
                    .decode()
                    .strip()
                )

            git("init")
            (root / "runtime.py").write_text("print('fixture')\n")
            git("add", ".")
            base = git("write-tree")
            git("mv", "runtime.py", "README.md")
            head = git("write-tree")
            run = subprocess.run
            with patch.object(
                scope.subprocess, "run", side_effect=lambda *a, **kw: run(*a, cwd=directory, **kw)
            ):
                paths = scope.changed_paths(base, head)
            self.assertEqual(set(paths), {"runtime.py", "README.md"})
            self.assertFalse(scope.documentation_only(paths))

    def test_manual_runs_and_missing_history_always_emit_full_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            for event in ("workflow_dispatch", "push", "pull_request", "future_event"):
                output.write_text("")
                subprocess.run(
                    ["python3", str(ROOT / "scripts/ci_scope.py"), "--event", event],
                    env=os.environ | {"GITHUB_OUTPUT": str(output)},
                    check=True,
                    capture_output=True,
                )
                self.assertEqual(output.read_text(), "full=true\n")

    def test_invalid_revision_cannot_be_interpreted_as_a_git_option(self):
        with self.assertRaises(ValueError):
            scope.changed_paths("--output=somewhere", "a" * 40)
