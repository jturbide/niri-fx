"""Build identities describe recorded inputs without executing candidate binaries."""

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
        self.temporary = tempfile.TemporaryDirectory()
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

    def test_builder_records_fake_cargo_results_without_running_candidate(self):
        # Exercise production manifest publication using command results, without
        # compiling, executing the candidate, or touching accepted artifact paths.
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        destination = artifacts / "niri-movement-build.json"
        destination.write_text("prior evidence\n")
        check_calls = []
        compiler = self.source / "fixture-rustc"
        compiler.write_text("synthetic compiler; tests supply command results\n")
        compiler.chmod(0o755)

        def tool_output(args, **kwargs):
            self.assertEqual(args[0], str(compiler))
            self.assertEqual(kwargs["env"]["RUSTC"], str(compiler))
            self.assertEqual(kwargs["cwd"], self.source)
            return RUSTC if args[1] == "--version" else VERBOSE

        def fake_build(args, **kwargs):
            self.assertEqual(kwargs["env"]["RUSTC"], str(compiler))
            self.assertEqual(
                args,
                [
                    "cargo",
                    "build",
                    "--locked",
                    "--release",
                    "--message-format=json-render-diagnostics",
                ],
            )
            return subprocess.CompletedProcess(args, 0, stdout=artifact(self.binary))

        with (
            patch.dict(os.environ, {"RUSTC": "./fixture-rustc"}),
            patch.object(build, "ROOT", self.root),
            patch.object(build, "SOURCE", self.source),
            patch.object(build, "PATCH", self.root / "experimental/niri-movement.patch"),
            patch.object(
                build, "apply_patches", side_effect=lambda *a, **kw: check_calls.append(kw)
            ),
            patch.object(build.subprocess, "check_output", side_effect=tool_output),
            patch.object(build.subprocess, "run", side_effect=fake_build),
            patch.object(sys, "argv", ["build", "--release", "--desktop"]),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            build.main()
        self.manifest = json.loads(destination.read_text())
        self.assertEqual(check_calls, [{}, {"verify_only": True}])
        self.assertEqual(self.manifest["native_build"]["inputs"]["enabled_features"], FEATURES)
        self.assertEqual(self.inspect(desktop=True)["status"], "metadata-match")
        self.assertEqual(list(artifacts.iterdir()), [destination])

    def test_failed_cargo_diagnostics_preserve_previous_manifest(self):
        artifacts = self.root / "artifacts"
        artifacts.mkdir()
        destination = artifacts / "niri-movement-build.json"
        destination.write_text("prior evidence\n")
        message = json.dumps(
            {"reason": "compiler-message", "message": {"rendered": "specific compile error\n"}}
        )
        stderr = io.StringIO()
        with (
            patch.object(build, "ROOT", self.root),
            patch.object(build, "SOURCE", self.source),
            patch.object(build, "PATCH", self.root / "experimental/niri-movement.patch"),
            patch.object(build, "apply_patches"),
            patch.object(build.shutil, "which", return_value="/fixture/rustc"),
            patch.object(build.subprocess, "check_output", side_effect=[RUSTC, VERBOSE]),
            patch.object(
                build.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(["cargo"], 101, stdout=message),
            ),
            patch.object(sys, "argv", ["build"]),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(stderr),
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                build.main()
        self.assertIn("specific compile error", stderr.getvalue())
        self.assertEqual(destination.read_text(), "prior evidence\n")
