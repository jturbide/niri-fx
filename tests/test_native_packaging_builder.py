"""Offline package builds reuse native checks without changing prepared sources."""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from niri_fx import native_build, native_install

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "packaging_builder_test", ROOT / "scripts/build-niri-movement.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
Candidate = builder.Candidate


class NativePackagingBuilderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="native-packaging-tests-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "prepared source"
        self.source.mkdir()
        self.environment = os.environ | {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_AUTHOR_NAME": "Fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "Fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        }
        self.git("init")
        for name, value in {
            "Cargo.lock": "synthetic pinned lock\n",
            "LICENSE": "synthetic upstream license\n",
            "README.md": "synthetic upstream notice\n",
            "window.rs": "base renderer\n",
        }.items():
            (self.source / name).write_text(value)
        self.git("add", ".")
        tree = self.git("write-tree").strip()
        self.revision = self.git("commit-tree", tree, "-m", "Fixture source").strip()
        self.git("update-ref", "HEAD", self.revision)
        self.patches = []
        for name in native_build.STACKS["fragment"]:
            path = self.source / "window.rs"
            path.write_text(path.read_text() + name + "\n")
            self.git("add", "window.rs")
            target = self.root / name
            target.write_text(self.git("diff", "--cached", tree, "--binary", "--full-index"))
            self.patches.append(target)
            tree = self.git("write-tree").strip()
        self.compiler = self.root / "host-rustc"
        self.compiler.write_text("synthetic compiler; command results supplied by tests\n")
        self.compiler.chmod(0o755)
        self.strip = self.root / "host-strip"
        self.strip.write_text("synthetic strip; command results supplied by tests\n")
        self.strip.chmod(0o755)
        self.cargo_home = self.root / "cargo"
        self.cargo_home.mkdir()
        self.args = SimpleNamespace(
            prepared_source=self.source,
            cargo_home=self.cargo_home,
            target_cache=None,
            strip_program=self.strip,
            release=True,
            desktop=True,
            test=True,
            unmodified=False,
            pointer_wobble=False,
            fragment_drag=True,
        )
        self.calls = []
        self.drift = False

    def git(self, *args):
        return subprocess.check_output(
            ["git", *args],
            cwd=self.source,
            env=self.environment,
            text=True,
            stderr=subprocess.DEVNULL,
        )

    def source_bytes(self):
        return {
            str(path.relative_to(self.source)): path.read_bytes()
            for path in self.source.rglob("*")
            if path.is_file()
        }

    def command(self, original, candidate, *args, **kwargs):
        self.calls.append(args)
        if args[0] == "git":
            self.assertNotIn("fetch", args)
            self.assertNotIn("https://github.com/niri-wm/niri.git", args)
            return original(candidate, *args, **kwargs)
        if args[0] == str(self.strip):
            self.assertTrue(any(call[:2] == ("cargo", "test") for call in self.calls))
            path = Path(args[-1])
            self.assertEqual(path, candidate.root / "processed/niri")
            path.write_bytes(path.read_bytes() + b"stripped\n")
            return subprocess.CompletedProcess(args, 0, stdout="")
        environment = kwargs["env"]
        self.assertEqual(environment["CARGO_HOME"], str(self.cargo_home))
        self.assertEqual(environment["CARGO_NET_OFFLINE"], "true")
        self.assertEqual(environment["RUSTUP_AUTO_INSTALL"], "0")
        self.assertEqual(environment["RUSTC"], str(self.compiler))
        rustc = "rustc 1.99.0 (fixture 2026-01-01)"
        if args[0] == str(self.compiler):
            value = rustc if args[1] == "--version" else rustc + "\nhost: x86_64-unknown-linux-gnu"
            return subprocess.CompletedProcess(args, 0, stdout=value)
        self.assertEqual(args[0], "cargo")
        self.assertIn("--locked", args)
        if args[1] == "test":
            return subprocess.CompletedProcess(args, 0, stdout="synthetic focused test passed\n")
        binary = candidate.target / "release/niri"
        binary.parent.mkdir(exist_ok=True)
        binary.write_bytes(b"synthetic unstripped binary\n")
        if self.drift:
            (self.source / "window.rs").write_text("changed during build\n")
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps(
                {
                    "reason": "compiler-artifact",
                    "target": {"name": "niri", "kind": ["bin"]},
                    "executable": str(binary),
                    "features": ["default", *native_build.DESKTOP_FEATURES],
                }
            ),
        )

    @contextlib.contextmanager
    def build_context(self):
        original = Candidate.command
        with (
            patch.dict(os.environ, self.environment | {"RUSTC": str(self.compiler)}),
            patch.object(builder, "ROOT", self.root),
            patch.object(builder, "REVISION", self.revision),
            patch.object(native_build, "REVISION", self.revision),
            patch.object(
                Candidate,
                "command",
                autospec=True,
                side_effect=lambda *a, **kw: self.command(original, *a, **kw),
            ),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            yield

    def build(self):
        candidate = Candidate(self.root / "attempts", "fragment")
        builder.build_candidate(self.args, "fragment", self.patches, candidate)
        return candidate

    def test_offline_source_is_unchanged_and_export_survives_relocation(self):
        before = self.source_bytes()
        # Prepared builds must not choose a repository-local toolchain/cache.
        ambient = self.root / "artifacts/toolchain/cargo/bin/rustc"
        ambient.parent.mkdir(parents=True)
        ambient.write_text("must not select this compiler\n")
        with self.build_context():
            candidate = self.build()
            exported = candidate.export(self.root / "export")
            moved = self.root / "relocated"
            shutil.move(exported.parent, moved)
            report = native_build.inspect(
                moved / "manifest.json",
                source=moved / "source",
                repository=moved,
                patch_directory=moved / "patches",
                desktop=True,
            )
            self.assertEqual(report["status"], "metadata-match")
            config = self.root / "config.kdl"
            config.write_text("input {}\n")
            with patch("subprocess.run", side_effect=AssertionError("Review must not execute")):
                plan = native_install.install_plan(self.root / "state", moved, config)
            self.assertEqual(plan["target"], "native-session-install")
        self.assertEqual(before, self.source_bytes())
        record = json.loads((moved / "manifest.json").read_text())
        self.assertEqual(record["binary"], "bin/niri")
        self.assertEqual(record["source"], "source")
        self.assertNotIn(str(self.root), json.dumps(record))
        self.assertEqual(
            (candidate.target / "release/niri").read_bytes(), b"synthetic unstripped binary\n"
        )
        self.assertEqual(
            (moved / "bin/niri").read_bytes(), b"synthetic unstripped binary\nstripped\n"
        )
        self.assertEqual(native_build.digest(moved / "bin/niri"), record["binary_sha256"])
        self.assertEqual(
            {path.name for path in (moved / "source").iterdir()},
            {"Cargo.lock", "LICENSE", "README.md"},
        )
        self.assertFalse((moved / "target").exists())
        self.assertFalse((moved / "logs").exists())

    def test_unrelated_prepared_source_changes_refuse_before_compilation(self):
        for path in (self.source / "untracked.txt", self.source / "window.rs"):
            old = path.read_bytes() if path.exists() else None
            path.write_text("preserve unrelated source work\n")
            before = self.source_bytes()
            with self.build_context(), self.assertRaisesRegex(SystemExit, "refusing to overwrite"):
                self.build()
            self.assertEqual(before, self.source_bytes())
            self.assertFalse(self.calls)
            path.unlink() if old is None else path.write_bytes(old)

    def test_prepared_source_drift_during_compile_never_publishes(self):
        self.drift = True
        with self.build_context(), self.assertRaisesRegex(SystemExit, "refusing to overwrite"):
            self.build()
        self.assertFalse(list((self.root / "attempts").glob("*/manifest.json")))

    def test_export_refuses_tampering_and_existing_output(self):
        with self.build_context():
            candidate = self.build()
            destination = self.root / "existing"
            destination.mkdir()
            with self.assertRaises(FileExistsError):
                candidate.export(destination)
            (candidate.root / "bin/niri").write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "verified desktop"):
                candidate.export(self.root / "invalid")
        self.assertFalse((self.root / "invalid").exists())

    def test_legacy_three_patch_candidate_cannot_be_a_full_session_package(self):
        with self.build_context():
            candidate = self.build()
            path = candidate.root / "manifest.json"
            record = json.loads(path.read_text())
            record.pop("swap_patch_sha256")
            block = record["native_build"]
            block["inputs"]["patches"].pop()
            block["build_id"] = native_build.fingerprint(block["inputs"])
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, "four-patch"):
                candidate.export(self.root / "incomplete")
        self.assertFalse((self.root / "incomplete").exists())

    def test_prepared_cli_refuses_partial_mode_and_source_writes(self):
        options = [
            "--prepared-source",
            str(self.source),
            "--build-root",
            str(self.root / "attempts"),
            "--cargo-home",
            str(self.cargo_home),
            "--output",
            str(self.root / "export"),
        ]
        before = self.source_bytes()
        for flags in (
            options,
            [
                "--fragment-drag",
                "--release",
                "--desktop",
                "--test",
                *options,
                "--build-root",
                str(self.source / "attempts"),
            ],
            [
                "--fragment-drag",
                "--release",
                "--desktop",
                "--test",
                *options,
                "--strip-program",
                "relative-strip",
            ],
            ["--output", str(self.root / "export")],
        ):
            with (
                patch.object(sys, "argv", ["build", *flags]),
                patch.object(builder, "Candidate") as candidate,
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                builder.main()
            candidate.assert_not_called()
        self.assertEqual(before, self.source_bytes())

    def test_target_cache_is_copied_and_links_refuse(self):
        cache = self.root / "target-cache"
        cache.mkdir()
        original = cache / "dependency"
        original.write_bytes(b"original cache bytes")
        candidate = Candidate(self.root / "attempts", "fragment")
        with contextlib.redirect_stdout(io.StringIO()):
            candidate.seed_target(cache)
        copied = candidate.target / original.name
        self.assertNotEqual(original.stat().st_ino, copied.stat().st_ino)
        copied.write_bytes(b"new build bytes")
        self.assertEqual(original.read_bytes(), b"original cache bytes")
        (cache / "unsafe-link").symlink_to(original)
        other = Candidate(self.root / "attempts", "fragment")
        with self.assertRaisesRegex(ValueError, "regular files"):
            other.seed_target(cache)
        self.assertFalse(list(other.target.iterdir()))


if __name__ == "__main__":
    unittest.main()
