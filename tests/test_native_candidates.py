"""Fresh attempts preserve accepted outputs and retain failed build evidence."""

import contextlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "candidate_builder_test", ROOT / "scripts/build-niri-movement.py"
)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
Candidate = build.Candidate
native = sys.modules["lib.native_build"]


class NativeCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="native candidate tests ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.parent = self.root / "artifacts/native-builds"

    def candidate(self):
        return Candidate(self.parent, "movement")

    def output(self, candidate):
        binary = candidate.target / "release/niri"
        binary.parent.mkdir()
        binary.write_bytes(b"synthetic native executable bytes")
        return {"binary": str(binary), "binary_sha256": native.digest(binary)}

    def test_concurrent_and_repeated_attempts_are_unique(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            attempts = list(pool.map(lambda _: self.candidate(), range(24)))
        self.assertEqual(len({candidate.root for candidate in attempts}), 24)
        for candidate in attempts:
            self.assertTrue(candidate.source.is_dir())
            self.assertTrue(candidate.target.is_dir())
            self.assertFalse((candidate.root / "manifest.json").exists())
        self.assertFalse((self.parent / "latest").exists())
        self.assertFalse((self.parent / "current").exists())

    def test_snapshot_and_output_copy_are_independent_inodes(self):
        candidate = self.candidate()
        source_patch = self.root / "movement.patch"
        source_patch.write_text("original patch\n")
        frozen, hashes = candidate.snapshot([source_patch])
        self.assertNotEqual(source_patch.stat().st_ino, frozen[0].stat().st_ino)
        source_patch.write_text("next patch\n")
        self.assertEqual(frozen[0].read_text(), "original patch\n")
        self.assertEqual(native.digest(frozen[0]), hashes[source_patch.name])
        manifest = self.output(candidate)
        cargo_output = Path(manifest["binary"])
        published = candidate.publish(manifest)
        result = json.loads(published.read_text())
        binary = Path(result["binary"])
        self.assertNotEqual(binary.stat().st_ino, cargo_output.stat().st_ino)
        cargo_output.write_bytes(b"a later manual build")
        self.assertEqual(native.digest(binary), manifest["binary_sha256"])
        self.assertEqual(binary.stat().st_mode & 0o777, 0o755)
        self.assertEqual(result["source"], "source")
        self.assertEqual(published.parent / result["source"], candidate.source)
        # Existing recorder sanitizers remove binary and retain other fields.
        public_evidence = {key: value for key, value in result.items() if key != "binary"}
        self.assertFalse(Path(public_evidence["source"]).is_absolute())
        self.assertNotIn(str(self.root), json.dumps(public_evidence))
        before = published.read_bytes()
        with self.assertRaises((ValueError, FileExistsError)):
            candidate.publish(manifest)
        self.assertEqual(published.read_bytes(), before)

    def test_changed_or_foreign_output_is_not_published(self):
        candidate = self.candidate()
        manifest = self.output(candidate)
        Path(manifest["binary"]).write_bytes(b"unexpected replacement")
        with self.assertRaisesRegex(ValueError, "changed"):
            candidate.publish(manifest)
        self.assertFalse((candidate.root / "manifest.json").exists())
        foreign = self.root / "accepted-binary"
        foreign.write_bytes(b"preserve me")
        with self.assertRaisesRegex(ValueError, "outside"):
            candidate.publish({"binary": str(foreign), "binary_sha256": native.digest(foreign)})
        self.assertEqual(foreign.read_bytes(), b"preserve me")

    def test_existing_success_manifest_is_never_replaced(self):
        candidate = self.candidate()
        manifest = self.output(candidate)
        destination = candidate.root / "manifest.json"
        destination.write_text("unexpected existing evidence\n")
        with self.assertRaises(FileExistsError):
            candidate.publish(manifest)
        self.assertEqual(destination.read_text(), "unexpected existing evidence\n")

    def test_failures_and_interruptions_retain_attempts_and_legacy_sentinels(self):
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        legacy = artifacts / "niri-movement-build.json"
        legacy.write_text("accepted metadata\n")
        legacy_binary = artifacts / "niri-src/target/release/niri"
        legacy_binary.parent.mkdir(parents=True)
        legacy_binary.write_bytes(b"accepted executable")
        for error, status in (
            (RuntimeError("failed after link"), "failed"),
            (KeyboardInterrupt(), "interrupted"),
        ):

            def fail(args, variant, patches, candidate, error=error):
                candidate.record("verify-output")
                self.output(candidate)
                raise error

            with (
                patch.object(build, "ROOT", self.root),
                patch.object(build, "build_candidate", side_effect=fail),
                patch.object(sys, "argv", ["build"]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(type(error)):
                    build.main()
            attempts = [
                path
                for path in self.parent.iterdir()
                if json.loads((path / "attempt.json").read_text())["status"] == status
            ]
            self.assertEqual(len(attempts), 1)
            self.assertTrue((attempts[0] / "target/release/niri").exists())
            self.assertFalse((attempts[0] / "manifest.json").exists())
            self.assertEqual(legacy.read_text(), "accepted metadata\n")
            self.assertEqual(legacy_binary.read_bytes(), b"accepted executable")

    def test_command_logs_survive_failure_and_interruption(self):
        candidate = self.candidate()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(subprocess.CalledProcessError):
                candidate.command(
                    sys.executable, "-c", "print('specific failure'); raise SystemExit(7)"
                )
        self.assertIn("specific failure", (candidate.logs / "001.log").read_text())

        def interrupt(*args, **kwargs):
            kwargs["stdout"].write("partial output before interruption\n")
            raise KeyboardInterrupt

        with (
            patch.object(subprocess, "run", side_effect=interrupt),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            with self.assertRaises(KeyboardInterrupt):
                candidate.command("fixture-command")
        self.assertIn("partial output", (candidate.logs / "002.log").read_text())
        self.assertFalse((candidate.root / "manifest.json").exists())
