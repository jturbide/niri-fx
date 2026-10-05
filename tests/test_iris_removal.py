"""Legacy shell patch removal must preserve upstream and user-owned source."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from niri_fx.setup import apply_plan, change, restore, summarize

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/install-iris-integration.py"
spec = importlib.util.spec_from_file_location("iris_removal", SCRIPT)
remover = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remover)

GALLERY = (
    b"// Upstream gallery\nColumnLayout {\n" + remover.PRESETS + b"\n\n    GridLayout { }\n}\n"
)
MODULE = b"module qs.modules.iris.settings\nIrisNiriMotionGallery 1.0 IrisNiriMotionGallery.qml\n"


class IrisRemovalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "inir"
        self.folder = self.source / "modules/iris/settings"
        self.folder.mkdir(parents=True)
        self.gallery = self.folder / "IrisNiriMotionGallery.qml"
        self.module = self.folder / "qmldir"
        self.gallery.write_bytes(GALLERY)
        self.module.write_bytes(MODULE)
        self.state = self.root / "removal-state"
        self.env = dict(os.environ, XDG_STATE_HOME=str(self.root / "state"))

    def legacy_plan(self):
        """Reproduce old installed bytes without retaining an installation API."""
        gallery = GALLERY.replace(remover.PRESETS, remover.PRESETS + remover.FILTER).replace(
            b"    GridLayout {", remover.BLOCK + b"    GridLayout {"
        )
        changes = [
            change(self.gallery, gallery),
            change(self.module, MODULE + remover.DECLARATION),
            *(
                change(self.folder / name, path.read_bytes())
                for name, path in remover.ASSETS.items()
            ),
        ]
        return {
            "target": "iris-ui",
            "selection": "Historical integration",
            "notes": [],
            "validation_config": None,
            "changes": changes,
        }

    def install_fixture(self):
        for item in self.legacy_plan()["changes"]:
            Path(item["target"]).write_bytes(item["after"])

    def snapshot(self):
        return {
            str(p.relative_to(self.source)): p.read_bytes()
            for p in self.source.rglob("*")
            if p.is_file()
        }

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--source", str(self.source), *args],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_new_installation_is_retired_without_writes(self):
        before = self.snapshot()
        for args in ((), ("--apply",)):
            with self.subTest(args=args):
                result = self.cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertIn("Source installation is retired", result.stderr)
                self.assertEqual(self.snapshot(), before)
                self.assertFalse((self.root / "state").exists())

    def test_removal_reviews_deletions_then_preserves_upstream_and_local_edits(self):
        self.install_fixture()
        unrelated = b"// Local customization survives\n"
        upstream = b"IrisSettingsWindow 1.0 IrisSettingsWindow.qml\n"
        self.gallery.write_bytes(unrelated + self.gallery.read_bytes())
        self.module.write_bytes(self.module.read_bytes() + upstream)
        other = self.source / "services/Personal.qml"
        other.parent.mkdir()
        other.write_bytes(b"// unrelated desktop source\n")
        before = self.snapshot()
        result = self.cli("--remove")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertEqual(
            [c["action"] for c in summary["changes"]], ["update", "update", "delete", "delete"]
        )
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.root / "state").exists())
        result = self.cli("--remove", "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.gallery.read_bytes(), unrelated + GALLERY)
        self.assertEqual(self.module.read_bytes(), MODULE + upstream)
        self.assertEqual(other.read_bytes(), b"// unrelated desktop source\n")
        for name in remover.ASSETS:
            self.assertFalse((self.folder / name).exists())
        state = self.root / "state/niri-fx/iris-integration-removal"
        self.assertTrue(state.exists())
        self.assertFalse((state.parent / "iris-integration").exists())
        restore(state, apply=True)
        self.assertEqual(self.snapshot(), before)

    def test_absent_patch_and_repeated_removal_are_noops(self):
        plan = remover.removal_plan(self.source)
        self.assertEqual(plan["changes"], [])
        self.install_fixture()
        apply_plan(remover.removal_plan(self.source), self.state)
        result = apply_plan(remover.removal_plan(self.source), self.state)
        self.assertFalse(result["changed"])
        self.assertIsNone(result["transaction"])
        self.assertEqual(self.gallery.read_bytes(), GALLERY)
        self.assertEqual(self.module.read_bytes(), MODULE)

    def test_partial_or_ambiguous_patch_is_not_guessed(self):
        self.install_fixture()
        installed = self.snapshot()
        cases = [
            (self.gallery, self.gallery.read_bytes().replace(remover.FILTER, b"")),
            (self.gallery, self.gallery.read_bytes().replace(remover.BLOCK, b"")),
            (self.gallery, self.gallery.read_bytes() + remover.BLOCK),
            (self.gallery, self.gallery.read_bytes() + b"// another nirifx.available owner\n"),
            (
                self.gallery,
                self.gallery.read_bytes().replace(b"!nirifx.available", b"nirifx.available"),
            ),
            (self.module, self.module.read_bytes().replace(remover.DECLARATION, b"")),
            (self.module, self.module.read_bytes() + remover.DECLARATION),
            (self.module, self.module.read_bytes() + b"// IrisNiriFXSection belongs here too\n"),
        ]
        for path, content in cases:
            with self.subTest(path=path.name, content=content[-60:]):
                path.write_bytes(content)
                before = self.snapshot()
                with self.assertRaisesRegex(ValueError, "Partial|Ambiguous"):
                    remover.removal_plan(self.source)
                self.assertEqual(self.snapshot(), before)
                for name, value in installed.items():
                    (self.source / name).write_bytes(value)
        (self.folder / "niri-fx.svg").unlink()
        with self.assertRaisesRegex(ValueError, "Partial"):
            remover.removal_plan(self.source)

    def test_changed_assets_and_orphan_assets_are_preserved(self):
        self.install_fixture()
        for name in remover.ASSETS:
            with self.subTest(name=name):
                asset = self.folder / name
                original = asset.read_bytes()
                asset.write_bytes(original + b"\n<!-- local edit -->\n")
                before = self.snapshot()
                with self.assertRaisesRegex(ValueError, "Customized integration asset"):
                    remover.removal_plan(self.source)
                self.assertEqual(self.snapshot(), before)
                asset.write_bytes(original)
        self.gallery.write_bytes(GALLERY)
        self.module.write_bytes(MODULE)
        with self.assertRaisesRegex(ValueError, "Partial"):
            remover.removal_plan(self.source)

    def test_concurrent_edits_and_restore_conflicts_do_not_overwrite(self):
        self.install_fixture()
        plan = remover.removal_plan(self.source)
        self.module.write_bytes(self.module.read_bytes() + b"NewUpstreamType 1.0 New.qml\n")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "changed since"):
            apply_plan(plan, self.state)
        self.assertEqual(self.snapshot(), before)
        plan = remover.removal_plan(self.source)
        apply_plan(plan, self.state, summarize(plan)["plan_sha256"])
        self.gallery.write_bytes(self.gallery.read_bytes() + b"// later user edit\n")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "changed since"):
            restore(self.state, apply=True)
        self.assertEqual(self.snapshot(), before)

    def test_linked_assets_and_module_trees_are_rejected(self):
        self.install_fixture()
        asset = self.folder / "niri-fx.svg"
        elsewhere = self.root / "borrowed.svg"
        elsewhere.write_bytes(asset.read_bytes())
        asset.unlink()
        asset.symlink_to(elsewhere)
        with self.assertRaisesRegex(ValueError, "linked iRiS integration files"):
            remover.removal_plan(self.source)
        self.assertEqual(elsewhere.read_bytes(), remover.ASSETS["niri-fx.svg"].read_bytes())
        moved = self.root / "borrowed-settings"
        self.folder.rename(moved)
        self.folder.symlink_to(moved, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "linked iRiS module directory"):
            remover.removal_plan(self.source)

    def test_historical_restore_keeps_its_original_default_state_and_conflict_checks(self):
        state = self.root / "state/niri-fx/iris-integration"
        apply_plan(self.legacy_plan(), state)
        before = self.snapshot()
        result = self.cli("--restore")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.snapshot(), before)
        self.module.write_bytes(self.module.read_bytes() + b"Upstream 1.0 Upstream.qml\n")
        result = self.cli("--restore", "--apply")
        self.assertEqual(result.returncode, 1)
        self.assertIn("changed since", result.stderr)
        self.module.write_bytes(before[str(self.module.relative_to(self.source))])
        result = self.cli("--restore", "--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.gallery.read_bytes(), GALLERY)
        self.assertEqual(self.module.read_bytes(), MODULE)
        self.assertFalse((self.folder / "IrisNiriFXSection.qml").exists())


if __name__ == "__main__":
    unittest.main()
