"""Selected checks must not hide renderer changes or pass after failed selection."""

import importlib.util
import os
import re
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

    def test_known_native_and_agent_files_keep_application_checks(self):
        for path in scope.NON_RENDERING_FILES:
            with self.subTest(path=path):
                self.assertTrue(
                    (ROOT / path).is_file(), "Review removed or renamed allowlist paths"
                )
                self.assertEqual(scope.required_checks([path]), (True, False))
                self.assertEqual(scope.required_checks([path, "docs/validation.md"]), (True, False))
        self.assertEqual(scope.required_checks(["README.md"]), (False, False))

    def test_shared_contracts_rendering_and_unknown_paths_force_the_full_suite(self):
        for path in (
            "niri_fx/cli.py",
            "niri_fx/model.py",
            "niri_fx/pointer.py",
            "niri_fx/profiles.py",
            "niri_fx/catalog.py",
            "niri_fx/parameters.py",
            "niri_fx/effects.py",
            "niri_fx/preview.py",
            "niri_fx/studio.py",
            "niri_fx/library.py",
            "niri_fx/preview.html",
            "niri_fx/effect-core.js",
            "niri_fx/pointer-preview.js",
            "niri_fx/fragment-preview.js",
            "niri_fx/fragment-controls.js",
            "niri_fx/studio.css",
            "niri_fx/shaders/compact.glsl",
            "niri_fx/new-agent-module.py",
            "scripts/ci_scope.py",
            "tests/test_ci_scope.py",
            ".github/workflows/checks.yml",
            "scripts/build-gallery.py",
            "scripts/build-site.py",
            "scripts/browser-smoke.mjs",
            "scripts/lib/browser.mjs",
            "scripts/pointer-preview-reference.py",
            "tests/fixtures/pointer-native-reference.json",
            "tests/pointer-preview.test.mjs",
            "tests/pointer-preview-browser.test.mjs",
            "tests/fragment-motion-render.test.mjs",
            "scripts/fragment-preview-reference.py",
            "tests/fixtures/fragment-native-reference.json",
            "tests/fragment-preview.test.mjs",
            "tests/fragment-preview-browser.test.mjs",
            "tests/fragment-controls-browser.test.mjs",
            "niri_fx/shaders/fragment-motion.glsl",
            "tests/future-native-test.py",
            "scripts/test-new-native-feature.py",
            "experimental/future.patch",
            "docs/gallery/index.html",
            "docs/gallery/gallery.js",
            "docs/gallery/gallery.css",
            "docs/benchmarks/future-result.json",
            "examples/profiles/pointer-preview-gentle.json",
            "niri_fx/__init__.py",
            "pyproject.toml",
            "MANIFEST.in",
            "requirements-dev.txt",
            "package-lock.json",
            "future-feature/file.txt",
        ):
            with self.subTest(path=path):
                self.assertEqual(scope.required_checks([path]), (True, True))
                self.assertEqual(
                    scope.required_checks(["docs/validation.md", "niri_fx/agent.py", path]),
                    (True, True),
                )
        self.assertEqual(scope.required_checks([]), (True, True))

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
            self.assertEqual(scope.required_checks(paths), (True, True))

    def test_known_file_rename_to_unknown_destination_still_requires_rendering(self):
        # Git's no-renames comparison includes both paths; a new module cannot
        # inherit the old module's reviewed exemption merely by being renamed.
        self.assertEqual(
            scope.required_checks(["niri_fx/agent.py", "niri_fx/automation.py"]), (True, True)
        )

    def test_manual_runs_and_missing_history_always_emit_full_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            for event in ("workflow_dispatch", "release", "push", "pull_request", "future_event"):
                output.write_text("")
                subprocess.run(
                    ["python3", str(ROOT / "scripts/ci_scope.py"), "--event", event],
                    env=os.environ | {"GITHUB_OUTPUT": str(output)},
                    check=True,
                    capture_output=True,
                )
                self.assertEqual(output.read_text(), "full=true\nrenderer=true\n")

    def test_manual_and_release_runs_ignore_an_otherwise_cheap_diff(self):
        for event, ref in (
            ("workflow_dispatch", "main"),
            ("release", ""),
            ("pull_request", "release/0.19.0"),
            ("pull_request", "release"),
            ("push", "refs/heads/release/0.19.0"),
            ("push", "refs/tags/v0.19.0"),
        ):
            with self.subTest(event=event, ref=ref):
                with tempfile.TemporaryDirectory() as directory:
                    output = Path(directory) / "output"
                    with (
                        patch.object(scope, "changed_paths", return_value=["README.md"]) as changed,
                        patch.dict(os.environ, {"GITHUB_OUTPUT": str(output)}),
                        patch("sys.argv", ["ci_scope.py", "--event", event, "--ref", ref]),
                        patch("builtins.print"),
                    ):
                        scope.main()
                    changed.assert_not_called()
                    self.assertEqual(output.read_text(), "full=true\nrenderer=true\n")

    def test_successful_comparison_emits_both_outputs_for_every_scope(self):
        for paths, expected in (
            (["README.md"], "full=false\nrenderer=false\n"),
            (["niri_fx/agent.py"], "full=true\nrenderer=false\n"),
            (["experimental/niri-movement.patch"], "full=true\nrenderer=false\n"),
            (["niri_fx/model.py"], "full=true\nrenderer=true\n"),
            ([], "full=true\nrenderer=true\n"),
        ):
            with self.subTest(paths=paths), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "output"
                with (
                    patch.object(scope, "changed_paths", return_value=paths),
                    patch.dict(os.environ, {"GITHUB_OUTPUT": str(output)}),
                    patch(
                        "sys.argv", ["ci_scope.py", "--event", "pull_request", "--ref", "fix/ui"]
                    ),
                    patch("builtins.print"),
                ):
                    scope.main()
                self.assertEqual(output.read_text(), expected)

    def test_required_workflow_jobs_reject_failed_or_malformed_selection(self):
        # Execute the actual guards instead of testing a second implementation.
        # No YAML dependency is needed for these literal, indented shell blocks.
        workflow = (ROOT / ".github/workflows/checks.yml").read_text()
        guards = workflow.split("      - name: Require successful check selection\n")[1:]
        self.assertEqual(len(guards), 2, "Both validate and browser must keep their guard")
        for block in guards:
            lines = []
            for line in block.split("        run: |\n", 1)[1].splitlines():
                if not line.startswith("          "):
                    break
                lines.append(line[10:])
            for result, full, renderer, succeeds in (
                ("success", "true", "true", True),
                ("success", "true", "false", True),
                ("success", "false", "false", True),
                ("success", "false", "true", False),
                ("success", "", "false", False),
                ("success", "true", "", False),
                ("success", "false", "maybe", False),
                ("failure", "true", "true", False),
                ("cancelled", "false", "false", False),
                ("skipped", "false", "false", False),
            ):
                with self.subTest(result=result, full=full, renderer=renderer):
                    checked = subprocess.run(
                        ["bash", "-e", "-c", "\n".join(lines)],
                        env=os.environ
                        | {
                            "SELECTION_RESULT": result,
                            "FULL_CHECKS": full,
                            "RENDER_CHECKS": renderer,
                        },
                        capture_output=True,
                        timeout=5,
                    )
                    self.assertEqual(checked.returncode == 0, succeeds)

    def test_browser_aggregate_requires_every_selected_suite(self):
        workflow = (ROOT / ".github/workflows/checks.yml").read_text()
        browser = workflow.split("  browser:\n", 1)[1]
        self.assertIn("needs: [changes, browser-tests, browser-render]", browser)
        self.assertIn("    if: always()\n", browser)
        block = browser.split("      - name: Require every selected browser suite\n", 1)[1]
        lines = []
        for line in block.split("        run: |\n", 1)[1].splitlines():
            if not line.startswith("          "):
                break
            lines.append(line[10:])
        states = ("success", "failure", "cancelled", "skipped", "")
        for renderer in ("true", "false", "", "maybe"):
            for tests_result in states:
                for render_result in states:
                    with self.subTest(renderer=renderer, tests=tests_result, render=render_result):
                        expected = "success" if renderer == "true" else "skipped"
                        checked = subprocess.run(
                            ["bash", "-e", "-c", "\n".join(lines)],
                            env=os.environ
                            | {
                                "RENDER_CHECKS": renderer,
                                "BROWSER_TESTS_RESULT": tests_result,
                                "BROWSER_RENDER_RESULT": render_result,
                            },
                            capture_output=True,
                            timeout=5,
                        )
                        self.assertEqual(
                            checked.returncode == 0,
                            renderer in {"true", "false"}
                            and tests_result == expected
                            and render_result == expected,
                        )

    def test_rendering_jobs_cover_all_independent_matrices(self):
        workflow = (ROOT / ".github/workflows/checks.yml").read_text()
        render = workflow.split("  browser-render:\n", 1)[1].split("  browser:\n", 1)[0]
        cases = re.findall(r'suite: (\w+)\n\s+aspect: "([^"]*)"', render)
        self.assertCountEqual(
            cases,
            [("shapes", "0.25"), ("shapes", "1"), ("shapes", "4"), ("motion", ""), ("studio", "")],
        )
        self.assertIn("fail-fast: false", render)
        self.assertIn(
            'render_command=(python scripts/studio-e2e.py --suite "$RENDER_SUITE")', render
        )
        self.assertIn('render_command+=(--shape-aspect "$SHAPE_ASPECT")', render)
        self.assertIn("npm run test:browser", workflow.split("  browser-tests:\n", 1)[1])

    def test_invalid_revision_cannot_be_interpreted_as_a_git_option(self):
        with self.assertRaises(ValueError):
            scope.changed_paths("--output=somewhere", "a" * 40)
