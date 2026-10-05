"""Build identities describe recorded inputs without executing candidate binaries."""

import contextlib
import copy
import importlib.util
import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "build_manifest_test", ROOT / "scripts/build-niri-movement.py"
)
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)
native = sys.modules["lib.native_build"]
RUSTC = "rustc 1.99.0 (fixture 2026-01-01)"
HOST = "x86_64-unknown-linux-gnu"
VERBOSE = f"{RUSTC}\nbinary: rustc\nhost: {HOST}\nrelease: 1.99.0\nLLVM version: 22.0.0"
FEATURES = ["dbus", "default", "pipewire", "systemd", "xdp-gnome-screencast"]


def artifact(binary, features=FEATURES):
    return json.dumps(
        {
            "reason": "compiler-artifact",
            "target": {"name": "niri", "kind": ["bin"]},
            "executable": str(binary),
            "features": features,
        }
    )


class NativeBuildTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="native build tests ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "Cargo.lock").write_text("synthetic locked inputs\n")
        self.binary = self.source / "target/release/niri"
        self.binary.parent.mkdir(parents=True)
        self.sentinel = self.root / "executed"
        self.binary.write_text(f"#!/bin/sh\ntouch '{self.sentinel}'\n")
        self.binary.chmod(0o755)
        (self.root / "experimental").mkdir()
        for name in native.PATCH_FIELDS:
            (self.root / "experimental" / name).write_text(f"synthetic {name}\n")
        self.path = self.root / "manifest.json"
        self.manifest = self.make_manifest()

    def make_manifest(self, variant="fragment", desktop=True, profile="release"):
        result = {
            "revision": native.REVISION,
            "binary": str(self.binary),
            "binary_sha256": native.digest(self.binary),
            "build_profile": profile,
            "build_flags": ["--locked"] + ([] if desktop else ["--no-default-features"]),
            "rustc": RUSTC,
        }
        if variant == "unmodified":
            result["unmodified"] = True
        for name in native.STACKS[variant]:
            result[native.PATCH_FIELDS[name]] = native.digest(self.root / "experimental" / name)
        result["native_build"] = native.metadata(
            result,
            variant=variant,
            lock_sha256=native.digest(self.source / "Cargo.lock"),
            target=HOST,
            features=FEATURES if desktop else [],
            rustc_verbose=VERBOSE,
        )
        return result

    def inspect(self, *, desktop=False, rehash=False):
        if rehash:
            block = self.manifest["native_build"]
            block["build_id"] = native.fingerprint(block["inputs"])
        self.path.write_text(json.dumps(self.manifest))
        before = self.path.read_bytes()
        with (
            patch.object(subprocess, "run", side_effect=AssertionError("must not execute")),
            patch.object(subprocess, "Popen", side_effect=AssertionError("must not execute")),
        ):
            result = native.inspect(
                self.path, source=self.source, repository=self.root, desktop=desktop
            )
        self.assertEqual(self.path.read_bytes(), before)
        self.assertFalse(self.sentinel.exists())
        self.assertEqual(result["runtime_acceptance"], "not_assessed")
        self.assertEqual(result["physical_desktop_acceptance"], "not_assessed")
        return result

    def test_all_stacks_and_relative_binary_are_read_only(self):
        for variant in native.STACKS:
            with self.subTest(variant=variant):
                self.manifest = self.make_manifest(variant)
                self.manifest["binary"] = str(self.binary.relative_to(self.path.parent))
                result = self.inspect(desktop=True)
                self.assertEqual(result["status"], "metadata-match")
                self.assertEqual(result["desktop_prerequisites"], "satisfied")

    def test_retained_three_patch_fragment_build_remains_inspectable(self):
        self.manifest.pop("swap_patch_sha256")
        self.manifest["native_build"]["inputs"]["patches"].pop()
        self.assertEqual(self.inspect(desktop=True, rehash=True)["status"], "metadata-match")
        self.manifest["swap_patch_sha256"] = "0" * 64
        self.assertEqual(self.inspect()["status"], "incompatible")

    def test_minimal_and_debug_match_but_do_not_satisfy_desktop(self):
        for desktop, profile in ((False, "release"), (True, "debug")):
            self.manifest = self.make_manifest(desktop=desktop, profile=profile)
            self.assertEqual(self.inspect()["status"], "metadata-match")
            result = self.inspect(desktop=True)
            self.assertEqual(result["status"], "incompatible")
            self.assertEqual(result["desktop_prerequisites"], "not_satisfied")
        self.manifest = self.make_manifest()
        self.manifest["native_build"]["inputs"]["enabled_features"].remove("pipewire")
        result = self.inspect(desktop=True, rehash=True)
        self.assertEqual(result["missing_desktop_features"], ["pipewire"])
        self.assertEqual(result["status"], "incompatible")

    def test_legacy_future_and_missing_manifests_are_not_matches(self):
        del self.manifest["native_build"]
        self.assertEqual(self.inspect()["status"], "unknown")
        self.manifest = self.make_manifest()
        self.manifest["native_build"]["schema"] = 99
        self.assertEqual(self.inspect()["status"], "unknown")
        self.path.unlink()
        self.assertEqual(
            native.inspect(self.path, source=self.source, repository=self.root)["status"],
            "incompatible",
        )

    def test_changed_or_missing_bytes_are_stale(self):
        for path in (
            self.binary,
            self.source / "Cargo.lock",
            self.root / "experimental/niri-movement.patch",
        ):
            with self.subTest(path=path.name):
                before = path.read_bytes()
                path.write_bytes(before + b"changed")
                self.assertEqual(self.inspect()["status"], "stale")
                path.unlink()
                self.assertEqual(self.inspect()["status"], "stale")
                path.write_bytes(before)

    def test_fingerprint_and_mirrored_fields_must_agree(self):
        self.manifest["native_build"]["inputs"]["profile"] = "debug"
        self.assertEqual(self.inspect()["status"], "incompatible")
        self.assertEqual(self.inspect(rehash=True)["status"], "incompatible")

    def test_patch_order_paths_revision_and_toolchain_are_strict(self):
        original = copy.deepcopy(self.manifest)
        mutations = [
            lambda i: i["patches"].reverse(),
            lambda i: i["patches"][0].update(file="../elsewhere.patch"),
            lambda i: i.update(upstream_revision="0" * 40),
            lambda i: i.update(target="aarch64-unknown-linux-gnu"),
            lambda i: i.update(rustc_verbose=VERBOSE.replace(RUSTC, "different compiler")),
            lambda i: i.update(default_features=False),
        ]
        for mutate in mutations:
            self.manifest = copy.deepcopy(original)
            mutate(self.manifest["native_build"]["inputs"])
            self.assertEqual(self.inspect(rehash=True)["status"], "incompatible")

    def test_malformed_and_nonregular_input_do_not_block(self):
        for value in ([], {"native_build": []}, {"native_build": {"schema": True}}):
            self.manifest = value
            self.assertEqual(self.inspect()["status"], "incompatible")
        self.manifest = self.make_manifest()
        self.binary.unlink()
        os.mkfifo(self.binary)
        self.assertEqual(self.inspect()["status"], "stale")
        self.path.unlink()
        os.mkfifo(self.path)
        self.assertEqual(
            native.inspect(self.path, source=self.source, repository=self.root)["status"],
            "incompatible",
        )

    def test_identity_is_order_stable_but_tracks_selected_inputs(self):
        inputs = self.manifest["native_build"]["inputs"]
        self.assertEqual(
            native.fingerprint(inputs), native.fingerprint(dict(reversed(list(inputs.items()))))
        )
        for key, value in (
            ("cargo_lock_sha256", "a" * 64),
            ("profile", "debug"),
            ("enabled_features", []),
        ):
            self.assertNotEqual(
                native.fingerprint(inputs), native.fingerprint(inputs | {key: value})
            )

    def test_cargo_record_uses_real_features_and_native_artifact_location(self):
        for binary in (self.binary, self.source / "target" / HOST / "release/niri"):
            output = "[]\nnot json\n" + artifact(binary)
            actual, features, target = native.cargo_artifact(
                output, self.source / "target", "release", HOST
            )
            self.assertEqual((actual, features, target), (binary, FEATURES, HOST))
        for output in (
            artifact(self.binary) + "\n" + artifact(self.binary),
            "{}",
            artifact(self.binary, None),
            artifact(self.source / "target/aarch64-unknown-linux-gnu/release/niri"),
            artifact(self.root / "foreign/niri"),
        ):
            with self.assertRaises(ValueError):
                native.cargo_artifact(output, self.source / "target", "release", HOST)

    def test_cli_exit_codes_never_execute_or_rewrite_candidates(self):
        spec = importlib.util.spec_from_file_location(
            "native_inspector_test", ROOT / "scripts/inspect-native-build.py"
        )
        inspector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(inspector)
        self.manifest = self.make_manifest("unmodified", desktop=False)
        for desktop, legacy, status, code in (
            (False, False, "metadata-match", 0),
            (True, False, "incompatible", 2),
            (False, True, "unknown", 2),
        ):
            if legacy:
                del self.manifest["native_build"]
            self.path.write_text(json.dumps(self.manifest))
            before = self.path.read_bytes()
            output = io.StringIO()
            argv = ["inspect", "--manifest", str(self.path), "--source", str(self.source)]
            with (
                patch.object(sys, "argv", argv + (["--desktop"] if desktop else [])),
                contextlib.redirect_stdout(output),
                patch.object(subprocess, "Popen", side_effect=AssertionError("must not execute")),
            ):
                self.assertEqual(inspector.main(), code)
            self.assertEqual(json.loads(output.getvalue())["status"], status)
            self.assertEqual(self.path.read_bytes(), before)
            self.assertFalse(self.sentinel.exists())

    def fake_command(self, candidate, *args, failure=False, **kwargs):
        if args[0] == "git":
            if args[1] == "checkout":
                (candidate.source / "Cargo.lock").write_bytes(
                    (self.source / "Cargo.lock").read_bytes()
                )
                compiler = candidate.source / "fixture-rustc"
                compiler.write_text("synthetic compiler; tests supply command results\n")
                compiler.chmod(0o755)
            return subprocess.CompletedProcess(args, 0, stdout="")
        compiler = candidate.source / "fixture-rustc"
        self.assertEqual(kwargs["env"]["RUSTC"], str(compiler))
        if args[0] == str(compiler):
            return subprocess.CompletedProcess(
                args, 0, stdout=RUSTC if args[1] == "--version" else VERBOSE
            )
        self.assertEqual(args[0:2], ("cargo", "build"))
        if failure:
            message = json.dumps(
                {"reason": "compiler-message", "message": {"rendered": "specific compile error\n"}}
            )
            return subprocess.CompletedProcess(args, 101, stdout=message)
        self.assertEqual(
            args,
            ("cargo", "build", "--locked", "--release", "--message-format=json-render-diagnostics"),
        )
        self.assertEqual(kwargs["env"]["CARGO_TARGET_DIR"], str(candidate.target))
        self.assertEqual(kwargs["env"]["CARGO_BUILD_TARGET_DIR"], str(candidate.target))
        self.assertEqual(kwargs["env"]["CARGO_BUILD_BUILD_DIR"], str(candidate.target))
        binary = candidate.target / "release/niri"
        binary.parent.mkdir()
        binary.write_bytes(self.binary.read_bytes())
        return subprocess.CompletedProcess(args, 0, stdout=artifact(binary))

    def test_builder_records_fake_cargo_results_without_running_candidate(self):
        # Actual attempts, snapshots and publication; only external commands are
        # simulated. Accepted artifact paths must remain byte-for-byte unchanged.
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        legacy = artifacts / "niri-movement-build.json"
        legacy.write_text("prior evidence\n")
        check_calls = []
        with (
            patch.dict(os.environ, {"RUSTC": "./fixture-rustc"}),
            patch.object(build, "ROOT", self.root),
            patch.object(build, "PATCH", self.root / "experimental/niri-movement.patch"),
            patch.object(
                build, "apply_patches", side_effect=lambda *a, **kw: check_calls.append((a, kw))
            ),
            patch.object(build.Candidate, "command", autospec=True, side_effect=self.fake_command),
            patch.object(sys, "argv", ["build", "--release", "--desktop"]),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            build.main()
            build.main()
        self.assertEqual(legacy.read_text(), "prior evidence\n")
        destinations = list((artifacts / "native-builds").glob("*/manifest.json"))
        self.assertEqual(len(destinations), 2)
        destination = destinations[0]
        self.manifest = json.loads(destination.read_text())
        self.assertEqual([kw for _, kw in check_calls], [{}, {"verify_only": True}] * 2)
        self.assertEqual(
            {args[2][0].parent.parent for args, _ in check_calls},
            {path.parent for path in destinations},
        )
        self.assertEqual(
            self.manifest["native_build"]["build_id"],
            json.loads(destinations[1].read_text())["native_build"]["build_id"],
        )
        self.assertEqual(self.manifest["source"], "source")
        self.assertEqual(self.manifest["binary"], str(destination.parent / "bin/niri"))
        self.assertEqual(self.manifest["native_build"]["inputs"]["enabled_features"], FEATURES)
        self.assertEqual(
            native.inspect(
                destination,
                source=destination.parent / self.manifest["source"],
                repository=self.root,
                desktop=True,
            )["status"],
            "metadata-match",
        )
        self.assertIn("NIRIFX_MOVEMENT_MANIFEST=", output.getvalue())
        invocations = [
            shlex.split(line.removeprefix("Try: "))[0]
            for line in output.getvalue().splitlines()
            if line.startswith("Try: ")
        ]
        self.assertEqual(
            set(invocations), {f"NIRIFX_MOVEMENT_MANIFEST={path}" for path in destinations}
        )
        self.assertFalse(self.sentinel.exists())

    def test_post_compile_input_drift_never_publishes_a_candidate(self):
        current = self.root / "experimental/niri-movement.patch"
        original = current.read_bytes()
        for changed in ("current-patch", "frozen-patch", "lock", "source-tree"):

            def command(candidate, *args, changed=changed, **kwargs):
                result = self.fake_command(candidate, *args, **kwargs)
                if args[0:2] == ("cargo", "build"):
                    paths = {
                        "current-patch": current,
                        "frozen-patch": candidate.inputs / current.name,
                        "lock": candidate.source / "Cargo.lock",
                    }
                    if changed in paths:
                        paths[changed].write_bytes(b"changed while building")
                return result

            def verify(*args, changed=changed, **kwargs):
                if changed == "source-tree" and kwargs.get("verify_only"):
                    raise SystemExit("source reset after compilation")

            with (
                patch.dict(os.environ, {"RUSTC": "./fixture-rustc"}),
                patch.object(build, "ROOT", self.root),
                patch.object(build, "PATCH", current),
                patch.object(build, "apply_patches", side_effect=verify),
                patch.object(build.Candidate, "command", autospec=True, side_effect=command),
                patch.object(sys, "argv", ["build", "--release", "--desktop"]),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                with self.assertRaises(SystemExit):
                    build.main()
            current.write_bytes(original)
        attempts = list((self.root / "artifacts/native-builds").iterdir())
        self.assertEqual(len(attempts), 4)
        for attempt in attempts:
            self.assertTrue((attempt / "target/release/niri").exists())
            self.assertFalse((attempt / "manifest.json").exists())
            self.assertEqual(json.loads((attempt / "attempt.json").read_text())["status"], "failed")

    def test_failed_cargo_diagnostics_preserve_previous_manifest(self):
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        destination = artifacts / "niri-movement-build.json"
        destination.write_text("prior evidence\n")
        stderr = io.StringIO()
        with (
            patch.dict(os.environ, {"RUSTC": "./fixture-rustc"}),
            patch.object(build, "ROOT", self.root),
            patch.object(build, "PATCH", self.root / "experimental/niri-movement.patch"),
            patch.object(build, "apply_patches"),
            patch.object(
                build.Candidate,
                "command",
                autospec=True,
                side_effect=lambda *a, **kw: self.fake_command(*a, failure=True, **kw),
            ),
            patch.object(sys, "argv", ["build"]),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(stderr),
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                build.main()
        self.assertIn("specific compile error", stderr.getvalue())
        self.assertEqual(destination.read_text(), "prior evidence\n")
        attempts = list((artifacts / "native-builds").iterdir())
        self.assertEqual(len(attempts), 1)
        self.assertFalse((attempts[0] / "manifest.json").exists())
        self.assertEqual(json.loads((attempts[0] / "attempt.json").read_text())["status"], "failed")
