"""Native test selection is explicit, variant-specific and read-only."""

import copy
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    from lib import fragment, movement, native_build, native_selection

    spec = importlib.util.spec_from_file_location(
        "selected_baseline", ROOT / "scripts/test-native-baseline.py"
    )
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)

NAMES = {
    "movement": "niri-movement-build.json",
    "pointer": "niri-pointer-wobble-build.json",
    "fragment": "niri-fragment-drag-build.json",
    "unmodified": "niri-unmodified-build.json",
}


class NativeSelectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="native selection ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for folder in ("experimental", "artifacts", "scripts"):
            (self.root / folder).mkdir()
        for name in native_build.PATCH_FIELDS:
            (self.root / "experimental" / name).write_text(f"synthetic {name}\n")
        (self.root / "scripts/nested-demo.py").write_text(
            "def config(*args): return 'test config'\n"
        )
        self.source = self.root / "candidate source"
        self.source.mkdir()
        (self.source / "Cargo.lock").write_text("synthetic locked inputs\n")
        self.binary = self.root / "candidate binary"
        self.binary.write_text("#!/bin/sh\nexit 99 # selection must never execute this\n")
        self.binary.chmod(0o755)
        self.path = self.root / "candidate manifest.json"
        for module in (movement, fragment, baseline):
            self.patching(patch.object(module, "ROOT", self.root))
        self.guard = self.patching(patch.object(baseline.builder, "apply_patches"))
        self.patching(patch.dict(os.environ, {}, clear=True))
        self.patching(patch.object(subprocess, "Popen", side_effect=AssertionError("executed")))
        self.patching(patch.object(subprocess, "run", side_effect=AssertionError("executed")))
        self.patching(
            patch.object(subprocess, "check_output", side_effect=AssertionError("executed"))
        )

    def patching(self, context):
        value = context.start()
        self.addCleanup(context.stop)
        return value

    def manifest(self, variant):
        value = {
            "revision": native_build.REVISION,
            "source": str(self.source),
            "binary": str(self.binary),
            "binary_sha256": native_build.digest(self.binary),
            "build_profile": "release",
            "build_flags": ["--locked", "--no-default-features"],
            "rustc": "rustc test",
        }
        if variant == "unmodified":
            value["unmodified"] = True
        for name in native_build.STACKS[variant]:
            value[native_build.PATCH_FIELDS[name]] = native_build.digest(
                self.root / "experimental" / name
            )
        value["native_build"] = native_build.metadata(
            value,
            variant=variant,
            lock_sha256=native_build.digest(self.source / "Cargo.lock"),
            target="test-host",
            features=[],
            rustc_verbose="rustc test\nhost: test-host",
        )
        return value

    def select(self, variant):
        if variant == "unmodified":
            return baseline.baseline()
        if variant == "fragment":
            return fragment.experiment()
        return movement.experiment(pointer_wobble=variant == "pointer")

    def write(self, manifest):
        self.path.write_text(json.dumps(manifest))

    def override(self, variant):
        os.environ[native_selection.OVERRIDES[variant]] = str(self.path)

    def legacy(self, variant):
        value = self.manifest(variant)
        value.pop("native_build")
        value.pop("source")
        accepted = self.root / f"accepted {variant} binary"
        accepted.write_bytes(self.binary.read_bytes())
        value["binary"] = str(accepted)
        (self.root / "artifacts" / NAMES[variant]).write_text(json.dumps(value))
        return accepted

    def snapshot(self):
        return {str(p): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}

    def test_all_explicit_variants_accept_spaces_without_running_a_program(self):
        for variant in NAMES:
            with self.subTest(variant=variant):
                value = self.manifest(variant)
                self.write(value)
                self.override(variant)
                binary, manifest, *config = self.select(variant)
                self.assertEqual(binary, self.binary)
                self.assertEqual(manifest, value)
                if config:
                    self.assertEqual(config[0](), "test config")
                if variant == "unmodified":
                    self.guard.assert_called_once_with(
                        self.source, native_build.REVISION, [], verify_only=True
                    )

    def test_unset_overrides_keep_fixed_legacy_defaults_not_newest_candidates(self):
        for variant in NAMES:
            with self.subTest(variant=variant):
                accepted = self.legacy(variant)
                self.write(self.manifest(variant))
                latest = self.root / "artifacts/native-builds/newest/manifest.json"
                latest.parent.mkdir(parents=True, exist_ok=True)
                latest.write_bytes(self.path.read_bytes())
                binary, _, *_ = self.select(variant)
                self.assertEqual(binary, accepted)
                if variant == "unmodified":
                    self.guard.assert_called_once_with(
                        baseline.builder.BASELINE_SOURCE,
                        native_build.REVISION,
                        [],
                        verify_only=True,
                    )

    def test_overrides_do_not_bleed_between_variants(self):
        for selected in NAMES:
            for requested in NAMES:
                if selected == requested:
                    continue
                with self.subTest(selected=selected, requested=requested):
                    os.environ.clear()
                    self.override(selected)
                    self.path.unlink(missing_ok=True)
                    accepted = self.legacy(requested)
                    self.assertEqual(self.select(requested)[0], accepted)

    def test_invalid_override_never_falls_back_to_a_valid_legacy_build(self):
        for variant in NAMES:
            self.legacy(variant)
            name = native_selection.OVERRIDES[variant]
            for value in ("", "   ", str(self.root / "missing manifest.json")):
                with self.subTest(variant=variant, value=value):
                    os.environ[name] = value
                    with self.assertRaisesRegex(RuntimeError, name + ".*No fallback"):
                        self.select(variant)
            self.override(variant)
            for content in ("{", "[]", "{}"):
                with self.subTest(variant=variant, content=content):
                    self.path.write_text(content)
                    with self.assertRaisesRegex(RuntimeError, name):
                        self.select(variant)

    def test_wrong_variant_and_revision_are_rejected_before_baseline_source_guard(self):
        for variant in NAMES:
            other = "pointer" if variant != "pointer" else "movement"
            self.write(self.manifest(other))
            self.override(variant)
            with self.subTest(variant=variant), self.assertRaisesRegex(RuntimeError, "Expected"):
                self.select(variant)
        self.guard.assert_not_called()
        value = self.manifest("unmodified")
        value["revision"] = "0" * 40
        value["native_build"]["inputs"]["upstream_revision"] = value["revision"]
        value["native_build"]["build_id"] = native_build.fingerprint(
            value["native_build"]["inputs"]
        )
        self.write(value)
        with self.assertRaisesRegex(RuntimeError, "different upstream revision"):
            self.select("unmodified")
        self.guard.assert_not_called()

    def test_stale_binary_each_patch_and_lockfile_refuse_execution(self):
        value = self.manifest("fragment")
        self.write(value)
        self.override("fragment")
        for file in (
            self.binary,
            self.source / "Cargo.lock",
            *(self.root / "experimental" / name for name in native_build.STACKS["fragment"]),
        ):
            with self.subTest(file=file.name):
                original = file.read_bytes()
                file.write_bytes(original + b"changed")
                with self.assertRaisesRegex(RuntimeError, "differs from the recorded"):
                    self.select("fragment")
                file.write_bytes(original)

    def test_explicit_candidates_require_current_metadata_and_source(self):
        original = self.manifest("movement")
        self.override("movement")
        for key in ("source", "native_build"):
            value = copy.deepcopy(original)
            value.pop(key)
            self.write(value)
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.select("movement")
        for source in (None, 7, "", "   "):
            self.write(original | {"source": source})
            with self.subTest(source=source), self.assertRaisesRegex(RuntimeError, "source"):
                self.select("movement")
        original["native_build"]["schema"] = 99
        self.write(original)
        with self.assertRaisesRegex(RuntimeError, "Unsupported native_build"):
            self.select("movement")

    def test_relative_paths_resolve_from_manifest_not_working_directory(self):
        value = self.manifest("fragment")
        value.update(source=self.source.name, binary=self.binary.name)
        self.write(value)
        self.override("fragment")
        self.assertEqual(self.select("fragment")[0], self.binary)

    def test_nonregular_manifest_and_binary_do_not_block(self):
        self.override("fragment")
        os.mkfifo(self.path)
        with self.assertRaisesRegex(RuntimeError, "regular file"):
            self.select("fragment")
        self.path.unlink()
        value = self.manifest("fragment")
        self.write(value)
        self.binary.unlink()
        os.mkfifo(self.binary)
        with self.assertRaisesRegex(RuntimeError, "regular file"):
            self.select("fragment")

    def test_manifest_replacement_during_inspection_is_rejected(self):
        self.write(self.manifest("fragment"))
        self.override("fragment")
        inspect = native_selection.inspect

        def replace(*args, **kwargs):
            result = inspect(*args, **kwargs)
            value = json.loads(self.path.read_text())
            value["source"] = str(self.root / "different source")
            self.write(value)
            return result

        with patch.object(native_selection, "inspect", side_effect=replace):
            with self.assertRaisesRegex(RuntimeError, "changed during selection"):
                self.select("fragment")

    def test_candidate_baseline_source_guard_refuses_changes_without_mutation(self):
        self.write(self.manifest("unmodified"))
        self.override("unmodified")
        self.guard.side_effect = SystemExit("Source has changes outside the selected patches")
        before = self.snapshot()
        with self.assertRaisesRegex(SystemExit, "Source has changes"):
            self.select("unmodified")
        self.guard.assert_called_once_with(self.source, native_build.REVISION, [], verify_only=True)
        self.assertEqual(self.snapshot(), before)


if __name__ == "__main__":
    unittest.main()
