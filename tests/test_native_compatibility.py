"""Exact matrix gates and the unified session build never select a compositor."""

import contextlib
import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


compatibility = module("native_compatibility_test", "check-native-compatibility.py")
session = module("native_session_builder_test", "build-nirifx-session.py")
native = sys.modules["lib.native_build"]


class NativeCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="native compatibility tests ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.matrix = compatibility.load_matrix()

    def write_matrix(self, value):
        path = self.root / "matrix.json"
        path.write_text(json.dumps(value))
        return path

    def test_matrix_rejects_mutable_or_unknown_inputs(self):
        changes = (
            ("schema", True),
            ("upstream_revision", "main"),
            ("cargo_lock_sha256", "not-a-hash"),
            ("rust_toolchain", "stable"),
            ("rust_toolchain", "nightly-2026-10-01"),
            ("target", "aarch64-unknown-linux-gnu"),
            ("runner", "ubuntu-latest"),
            ("patch_variants", ["fragment"]),
            ("default_case", "movement-desktop"),
        )
        for name, value in changes:
            with self.subTest(name=name, value=value):
                with self.assertRaises(ValueError):
                    compatibility.load_matrix(self.write_matrix(self.matrix | {name: value}))
        for change in (
            {"id": "unsafe\nname"},
            {"variant": "next-nightly"},
            {"profile": "release"},
            {"default_features": 1},
        ):
            value = copy.deepcopy(self.matrix)
            value["cases"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                compatibility.load_matrix(self.write_matrix(value))
        duplicate = copy.deepcopy(self.matrix)
        duplicate["cases"].append(duplicate["cases"][0])
        with self.assertRaisesRegex(ValueError, "unique"):
            compatibility.load_matrix(self.write_matrix(duplicate))

    def test_ci_rows_keep_explicit_target_and_feature_policy(self):
        default = compatibility.actions_matrix(self.matrix)["include"]
        self.assertEqual([case["id"] for case in default], ["nirifx-desktop"])
        self.assertEqual(default[0]["variant"], "fragment")
        self.assertTrue(default[0]["default_features"])
        rows = compatibility.actions_matrix(self.matrix, expanded=True)["include"]
        self.assertEqual(len(rows), 4)
        self.assertEqual([row["default_features"] for row in rows], [True, True, True, False])
        self.assertTrue(all(row["rust_toolchain"] == "1.99.0" for row in rows))
        self.assertTrue(all(row["target"] == self.matrix["target"] for row in rows))

    def git_fixture(self):
        source = self.root / "source cache"
        source.mkdir()
        # This disposable fixture has its own identity/config. Never consult or
        # change the user's signing setup or a project repository.
        env = os.environ | {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        }

        def git(*args):
            return subprocess.check_output(
                ["git", *args], cwd=source, env=env, stderr=subprocess.DEVNULL
            )

        git("init")
        (source / "Cargo.lock").write_text("synthetic pinned dependencies\n")
        (source / "fixture.txt").write_text("original\n")
        git("add", ".")
        tree = git("write-tree").decode().strip()
        revision = git("commit-tree", tree, "-m", "Fixture source").decode().strip()
        git("update-ref", "HEAD", revision)
        (source / "fixture.txt").write_text("patched\n")
        patch_bytes = git("diff", "--binary", "--full-index")
        (source / "fixture.txt").write_text("preserve an unrelated cache worktree edit\n")
        experiment = self.root / "experimental"
        experiment.mkdir()
        (experiment / "niri-movement.patch").write_bytes(patch_bytes)
        matrix = self.matrix | {
            "upstream_revision": revision,
            "cargo_lock_sha256": native.digest(source / "Cargo.lock"),
        }
        return source, matrix, git

    def test_clean_patch_check_uses_exact_commit_without_mutating_cache(self):
        source, matrix, git = self.git_fixture()
        before = (git("status", "--porcelain=v1"), git("show-ref"), git("diff", "HEAD"))
        index_before = (source / ".git/index").read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            report = compatibility.run_patch_check(
                matrix, "movement", repository=self.root, source_cache=source
            )
        self.assertEqual(report["status"], "passed")
        self.assertEqual(
            before, (git("status", "--porcelain=v1"), git("show-ref"), git("diff", "HEAD"))
        )
        self.assertEqual(index_before, (source / ".git/index").read_bytes())
        attempts = list((self.root / "artifacts/native-compatibility/attempts").iterdir())
        self.assertEqual(len(attempts), 1)
        self.assertEqual((attempts[0] / "source/fixture.txt").read_text(), "patched\n")
        self.assertFalse((attempts[0] / "manifest.json").exists())
        self.assertEqual(report["runtime_acceptance"], "not_assessed")
        self.assertNotIn(str(self.root), json.dumps(report))

    def test_lock_mismatch_retains_failed_attempt_without_success_manifest(self):
        source, matrix, _ = self.git_fixture()
        with contextlib.redirect_stdout(io.StringIO()):
            report = compatibility.run_patch_check(
                matrix | {"cargo_lock_sha256": "0" * 64},
                "movement",
                repository=self.root,
                source_cache=source,
            )
        self.assertEqual(report["status"], "failed")
        attempt = next((self.root / "artifacts/native-compatibility/attempts").iterdir())
        self.assertEqual(json.loads((attempt / "attempt.json").read_text())["status"], "failed")
        self.assertTrue((attempt / "source/fixture.txt").exists())
        self.assertFalse((attempt / "manifest.json").exists())

    def manifest(
        self, case, *, feature_override=None, target_override=None, compiler_override=None
    ):
        candidate = compatibility.Candidate(self.root / "attempts", case["variant"])
        (candidate.source / "Cargo.lock").write_text("synthetic pinned lock\n")
        binary = candidate.target / "debug/niri"
        binary.parent.mkdir()
        binary.write_bytes(b"synthetic bytes, never executed")
        experiment = self.root / "experimental"
        experiment.mkdir(exist_ok=True)
        value = {
            "revision": native.REVISION,
            "binary": str(binary),
            "binary_sha256": native.digest(binary),
            "build_profile": "debug",
            "build_flags": ["--locked"]
            + ([] if case["default_features"] else ["--no-default-features"]),
            "rustc": compiler_override or "rustc 1.99.0 (synthetic 2026-10-01)",
        }
        fields = {
            "niri-movement.patch": "patch_sha256",
            "niri-pointer-wobble.patch": "pointer_patch_sha256",
            "niri-fragment-drag.patch": "fragment_patch_sha256",
            "niri-swap.patch": "swap_patch_sha256",
        }
        for filename in native.STACKS[case["variant"]]:
            file = experiment / filename
            file.write_text("synthetic " + filename)
            value[fields[filename]] = native.digest(file)
        target = target_override or self.matrix["target"]
        features = sorted({"default", *native.DESKTOP_FEATURES}) if case["default_features"] else []
        value["native_build"] = native.metadata(
            value,
            variant=case["variant"],
            lock_sha256=native.digest(candidate.source / "Cargo.lock"),
            target=target,
            features=features if feature_override is None else feature_override,
            rustc_verbose=f"{value['rustc']}\nhost: {target}\n",
        )
        return candidate.publish(value), self.matrix | {
            "cargo_lock_sha256": native.digest(candidate.source / "Cargo.lock")
        }

    def test_case_verification_checks_actual_metadata_without_running_binary(self):
        for case in (self.matrix["cases"][2], self.matrix["cases"][3]):
            with self.subTest(case=case["id"]):
                path, matrix = self.manifest(case)
                with patch.object(subprocess, "run", side_effect=AssertionError("No execution")):
                    report = compatibility.verify_case_manifest(
                        path, matrix, case, repository=self.root
                    )
                self.assertEqual(report["inputs"]["default_features"], case["default_features"])
                self.assertNotIn(str(self.root), json.dumps(report))
        case = self.matrix["cases"][2]
        for changes in (
            {"feature_override": ["default", "dbus"]},
            {"target_override": "aarch64-unknown-linux-gnu"},
            {"compiler_override": "rustc 1.98.0 (synthetic 2026-09-01)"},
        ):
            with self.subTest(changes=changes):
                path, matrix = self.manifest(case, **changes)
                with self.assertRaises(ValueError):
                    compatibility.verify_case_manifest(path, matrix, case, repository=self.root)

    def test_build_uses_existing_producer_and_restores_toolchain_on_failure(self):
        case = self.matrix["cases"][2]
        seen = []

        def fail(args, variant, patches, candidate):
            seen.append((args, variant, patches, candidate))
            self.assertEqual(os.environ["RUSTUP_TOOLCHAIN"], self.matrix["rust_toolchain"])
            candidate.record("tests")
            raise RuntimeError("synthetic compile failure")

        with (
            patch.dict(os.environ, {"RUSTUP_TOOLCHAIN": "preserved"}),
            patch.object(compatibility.builder, "build_candidate", side_effect=fail),
        ):
            report = compatibility.run_build(self.matrix, case, repository=self.root)
            self.assertEqual(os.environ["RUSTUP_TOOLCHAIN"], "preserved")
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["stage"], "tests")
        args, variant, patches, candidate = seen[0]
        self.assertEqual(variant, "fragment")
        self.assertTrue(args.desktop and args.test and args.fragment_drag)
        self.assertFalse(args.release)
        self.assertEqual([path.name for path in patches], list(native.STACKS[variant]))
        self.assertFalse((candidate.root / "manifest.json").exists())
        self.assertEqual(
            json.loads((candidate.root / "attempt.json").read_text())["status"], "failed"
        )

    def test_cli_preserves_prior_reports_and_stops_on_interrupt(self):
        report_path = self.root / "report.json"
        report_path.write_text("preserve prior report\n")
        with (
            patch.object(sys, "argv", ["check", "patches", "--report", str(report_path)]),
            patch.object(compatibility, "run_patch_check") as check,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            with self.assertRaises(SystemExit):
                compatibility.main()
            check.assert_not_called()
        self.assertEqual(report_path.read_text(), "preserve prior report\n")
        with (
            patch.object(sys, "argv", ["check", "patches"]),
            patch.object(
                compatibility, "run_patch_check", return_value={"status": "interrupted"}
            ) as check,
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(compatibility.main(), 1)
            self.assertEqual(check.call_count, 1)

    def test_unified_session_command_always_builds_full_optimized_tested_candidate(self):
        for status in (0, 7):
            with (
                patch.object(sys, "argv", ["build-nirifx-session"]),
                patch.object(
                    session.subprocess, "run", return_value=subprocess.CompletedProcess([], status)
                ) as run,
                contextlib.redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(session.main(), status)
                run.assert_called_once_with(
                    [
                        sys.executable,
                        str(ROOT / "scripts/build-niri-movement.py"),
                        "--fragment-drag",
                        "--desktop",
                        "--release",
                        "--test",
                    ],
                    check=False,
                )
        with (
            patch.object(sys, "argv", ["build-nirifx-session", "--unmodified"]),
            patch.object(session.subprocess, "run") as run,
            contextlib.redirect_stderr(io.StringIO()),
        ):
            with self.assertRaises(SystemExit):
                session.main()
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
