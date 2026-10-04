"""Activation and persistence contracts using temporary configs only."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from helpers import shell_registry

from niri_fx.documents import effect_document
from niri_fx.effects import render_kdl
from niri_fx.library import Library
from niri_fx.presets import PRESETS
from niri_fx.profiles import Profile


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.config = self.root / "config/niri/config.kdl"
        self.config.parent.mkdir(parents=True)
        self.config.write_text("animations { window-resize { duration-ms 170; }; }\n")
        self.args = SimpleNamespace(
            config=self.config,
            state=self.root / "state",
            registry=self.root / "registry.json",
            inir_root=self.root / "shell",
            base="auto",
        )
        self.library = Library(self.args, "standalone")
        self.doc = effect_document(
            "Demo Combo", Profile(PRESETS["zipper"], PRESETS["frost-vanish"])
        )
        self.selection = {"document": self.doc, "allow_resize": False, "allow_movement": False}

    def tearDown(self):
        self.temp.cleanup()

    def test_save_and_review_do_not_activate_then_apply_and_restore_exact_bytes(self):
        original = self.config.read_bytes()
        self.library.store(self.doc)
        self.assertEqual(self.library.listing()["customs"]["custom-demo-combo"], self.doc)
        with patch("niri_fx.setup.validate_config"):
            review = self.library.review(self.selection)
            self.assertEqual(self.config.read_bytes(), original)
            self.assertFalse((self.config.parent / "nirifx").exists())
            result = self.library.apply(
                {"selection": self.selection, "expected": review["plan_sha256"]}
            )
        self.assertTrue(result["changed"])
        rendered = (self.config.parent / "nirifx/animations.kdl").read_text()
        self.assertIn("slices_color", rendered)
        self.assertTrue(
            rendered.endswith(render_kdl(Profile(PRESETS["zipper"], PRESETS["frost-vanish"])))
        )
        self.assertNotIn("window-resize", rendered)
        self.assertEqual(self.library.listing()["active"], self.doc)
        self.library.undo()
        self.assertEqual(self.config.read_bytes(), original)
        self.assertFalse((self.config.parent / "nirifx/animations.kdl").exists())
        self.assertIsNone(self.library.listing()["active"])

    def test_stale_review_and_restore_conflicts_preserve_external_edits(self):
        with patch("niri_fx.setup.validate_config"):
            review = self.library.review(self.selection)
            edited = self.config.read_bytes() + b"// User edit\n"
            self.config.write_bytes(edited)
            with self.assertRaisesRegex(ValueError, "plan changed"):
                self.library.apply({"selection": self.selection, "expected": review["plan_sha256"]})
            self.assertEqual(self.config.read_bytes(), edited)
            review = self.library.review(self.selection)
            self.library.apply({"selection": self.selection, "expected": review["plan_sha256"]})
        final = self.config.read_bytes() + b"// Another user edit\n"
        self.config.write_bytes(final)
        with self.assertRaisesRegex(ValueError, "File changed"):
            self.library.undo()
        self.assertEqual(self.config.read_bytes(), final)

    def test_restore_is_scoped_to_the_config_and_adapter(self):
        with patch("niri_fx.setup.validate_config"):
            review = self.library.review(self.selection)
            self.library.apply({"selection": self.selection, "expected": review["plan_sha256"]})
        applied = self.config.read_bytes()
        foreign = Library(self.args, "noctalia")
        self.assertFalse(foreign.listing()["restore"])
        with self.assertRaisesRegex(ValueError, "for this setup"):
            foreign.undo()
        second_config = self.root / "other/config.kdl"
        second_config.parent.mkdir()
        second_config.write_text("// Another session\n")
        other = Library(
            SimpleNamespace(**(vars(self.args) | {"config": second_config})), "standalone"
        )
        self.assertFalse(other.listing()["restore"])
        with self.assertRaisesRegex(ValueError, "for this setup"):
            other.undo()
        self.assertEqual(self.config.read_bytes(), applied)
        self.library.undo()

    def test_resize_consent_and_movement_contract_cannot_be_bypassed(self):
        self.selection["document"] = effect_document(
            "Optional",
            Profile(
                PRESETS["zipper"],
                PRESETS["frost-vanish"],
                resize=PRESETS["balanced"],
                movement=PRESETS["fragment-wake"],
            ),
        )
        with self.assertRaisesRegex(ValueError, "resize"):
            self.library.review(self.selection)
        self.selection.update(allow_resize=True, allow_movement=True)
        with patch(
            "niri_fx.capabilities.movement_capability", return_value={"activation_ready": False}
        ):
            with self.assertRaisesRegex(ValueError, "verified running"):
                self.library.review(self.selection)
        with self.assertRaisesRegex(ValueError, "stock Niri"):
            Library(self.args, "inir").review(self.selection)
        with self.assertRaisesRegex(ValueError, "stock Niri"):
            Library(self.args, "noctalia").review(self.selection)

    def test_invalid_documents_and_symlinks_cannot_redirect_save(self):
        with self.assertRaises(ValueError):
            self.library.store(dict(self.doc, name="../outside"))
        self.library.folder.mkdir(parents=True)
        other = self.root / "other"
        other.write_text("Keep me")
        (self.library.folder / "demo-combo.json").symlink_to(other)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.library.store(self.doc)
        self.assertEqual(other.read_text(), "Keep me")
        for request in (
            {},
            dict(self.selection, path="elsewhere"),
            dict(self.selection, allow_resize="yes"),
        ):
            with self.assertRaises(ValueError):
                self.library.review(request)

    def test_noctalia_uses_connected_picker_and_preserves_speed(self):
        target = self.config.parent / "picker.kdl"
        original = (
            b'// Plugin-owned target\ninclude "presets/base.kdl"\nanimations { slowdown 1.25; }\n'
        )
        # No semicolons in the plugin's actual output.
        original = original.replace(b"1.25;", b"1.25")
        target.write_bytes(original)
        root = b'include "picker.kdl"\n'
        self.config.write_bytes(root)
        self.args.preset_dir = self.config.parent / "presets"
        self.args.picker_file = target
        library = Library(self.args, "noctalia")
        review = library.review(self.selection)
        self.assertEqual(target.read_bytes(), original)
        with patch("niri_fx.setup.validate_config"):
            library.apply({"selection": self.selection, "expected": review["plan_sha256"]})
        self.assertEqual(self.config.read_bytes(), root)
        self.assertIn("slowdown 1.25", target.read_text())
        self.assertIn("niri-fx-custom-demo-combo.kdl", target.read_text())
        library.undo()
        self.assertEqual(target.read_bytes(), original)
        self.assertFalse((self.args.preset_dir / "niri-fx-custom-demo-combo.kdl").exists())
        target.write_text("input { keyboard {} }\n")
        with self.assertRaisesRegex(ValueError, "independent settings"):
            library.review(self.selection)

    def test_iris_uses_serializer_without_live_writes_and_rolls_back_validation_failure(self):
        scripts = self.args.inir_root / "scripts"
        scripts.mkdir(parents=True)
        animation = self.config.parent / "config.d/60-animations.kdl"
        animation.parent.mkdir()
        original = b"// Keep this header\nanimations { slowdown 1.5; }\n"
        animation.write_bytes(original)
        self.config.write_text('include "config.d/60-animations.kdl"\n')
        helper = scripts / "niri-config.py"
        helper.write_text(
            "from pathlib import Path\nimport os\n"
            "def resolve_niri_section_file(path): return Path(os.environ['XDG_CONFIG_HOME'])/'niri'/path\n"
            "def cmd_apply_animation_preset(ids):\n"
            " p = _load_animation_presets()['presets'][0]\n"
            " return _write_validated(resolve_niri_section_file('config.d/60-animations.kdl'), 'animations { /* '+p['id']+' */ }\\n')\n"
        )
        self.args.registry = self.root / "config/inir/niri-animation-presets.json"
        self.args.registry.parent.mkdir()
        old_registry = b'{"presets":[]}\n'
        self.args.registry.write_bytes(old_registry)
        library = Library(self.args, "inir")
        with (
            patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "config")}),
            patch("niri_fx.library.read_shell_presets", return_value=shell_registry()),
        ):
            review = library.review(self.selection)
            self.assertEqual(animation.read_bytes(), original)
            self.assertEqual(self.args.registry.read_bytes(), old_registry)
            with patch(
                "niri_fx.setup.validate_config", side_effect=ValueError("Invalid configuration")
            ):
                with self.assertRaisesRegex(ValueError, "Invalid configuration"):
                    library.apply({"selection": self.selection, "expected": review["plan_sha256"]})
            self.assertEqual(animation.read_bytes(), original)
            self.assertEqual(self.args.registry.read_bytes(), old_registry)
            with patch("niri_fx.setup.validate_config"):
                library.apply({"selection": self.selection, "expected": review["plan_sha256"]})
            self.assertIn("niri-fx-custom-demo-combo", animation.read_text())
            registry = json.loads(self.args.registry.read_text())
            self.assertEqual(
                registry["presets"][0]["types"]["workspace-switch"],
                shell_registry()["presets"][0]["types"]["workspace-switch"],
            )
            library.undo()
            self.assertEqual(animation.read_bytes(), original)
            self.assertEqual(self.args.registry.read_bytes(), old_registry)


if __name__ == "__main__":
    unittest.main()
