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
from niri_fx.pointer import PointerWobble
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
        self.library.store({"document": self.doc, "expected": None})
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
            self.library.store({"document": dict(self.doc, name="../outside"), "expected": None})
        self.library.folder.mkdir(parents=True)
        other = self.root / "other"
        other.write_text("Keep me")
        (self.library.folder / "demo-combo.json").symlink_to(other)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.library.store({"document": self.doc, "expected": None})
        self.assertEqual(other.read_text(), "Keep me")
        for request in (
            {},
            dict(self.selection, path="elsewhere"),
            dict(self.selection, allow_resize="yes"),
        ):
            with self.assertRaises(ValueError):
                self.library.review(request)

    def test_pointer_consent_preserves_portable_settings_and_rejects_stock_adapters(self):
        self.selection["document"] = effect_document(
            "Pointer Combo",
            Profile(PRESETS["zipper"], PRESETS["frost-vanish"], pointer=PointerWobble()),
        )
        self.library.store({"document": self.selection["document"], "expected": None})
        self.assertEqual(
            self.library.listing()["customs"]["custom-pointer-combo"]["pointer"],
            self.selection["document"]["pointer"],
        )
        with patch("niri_fx.setup.validate_config"):
            omitted = self.library.plan(self.selection)
        self.assertIsNone(omitted["pointer_activation"])
        self.assertNotIn(b"pointer-wobble", omitted["changes"][0]["after"])
        self.assertIn("omitted", " ".join(omitted["notes"]))
        self.selection["allow_pointer"] = True
        with patch(
            "niri_fx.capabilities.pointer_capability", return_value={"activation_ready": False}
        ):
            with self.assertRaisesRegex(ValueError, "verified running pointer"):
                self.library.review(self.selection)
        for target in ("inir", "noctalia"):
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, "standalone"):
                Library(self.args, target).review(self.selection)
        self.selection["allow_pointer"] = 1
        with self.assertRaisesRegex(ValueError, "boolean"):
            self.library.review(self.selection)
        self.selection.update(allow_pointer=True, document=self.doc)
        with self.assertRaisesRegex(ValueError, "no pointer settings"):
            self.library.review(self.selection)
        self.assertFalse(self.library.state.exists())

    def test_pointer_review_apply_restore_is_bound_to_the_same_consent(self):
        self.selection.update(
            document=effect_document(
                "Pointer Combo",
                Profile(
                    PRESETS["zipper"], PRESETS["frost-vanish"], pointer=PointerWobble(strength=0)
                ),
            ),
            allow_pointer=True,
        )
        original = self.config.read_bytes()
        with (
            patch("niri_fx.setup.validate_config"),
            patch(
                "niri_fx.capabilities.pointer_capability",
                return_value={"activation_ready": True, "binary": "/trusted/niri"},
            ),
        ):
            review = self.library.review(self.selection)
            with self.assertRaisesRegex(ValueError, "plan changed"):
                self.library.apply(
                    {
                        "selection": dict(self.selection, allow_pointer=False),
                        "expected": review["plan_sha256"],
                    }
                )
            self.library.apply({"selection": self.selection, "expected": review["plan_sha256"]})
        included = (self.config.parent / "nirifx/animations.kdl").read_text()
        self.assertIn("pointer-wobble", included)
        self.assertIn("strength 0", included)
        self.assertEqual(self.library.listing()["active"], self.selection["document"])
        self.library.undo()
        self.assertEqual(self.config.read_bytes(), original)

    def test_active_stock_profile_stays_recognized_when_native_restore_is_unavailable(self):
        pointer_selection = dict(
            self.selection,
            document=effect_document(
                "Pointer",
                Profile(PRESETS["zipper"], PRESETS["frost-vanish"], pointer=PointerWobble()),
            ),
            allow_pointer=True,
        )
        report = {"activation_ready": True, "binary": "/trusted/niri"}
        with (
            patch("niri_fx.setup.validate_config"),
            patch("niri_fx.capabilities.pointer_capability", return_value=report) as capability,
        ):
            reviewed = self.library.review(pointer_selection)
            self.library.apply(
                {"selection": pointer_selection, "expected": reviewed["plan_sha256"]}
            )
            reviewed = self.library.review(self.selection)
            self.library.apply({"selection": self.selection, "expected": reviewed["plan_sha256"]})
            capability.return_value = {"activation_ready": False}
            listing = self.library.listing()
            self.assertEqual(listing["active"], self.doc)
            self.assertTrue(listing["restore"])
            with self.assertRaisesRegex(ValueError, "experimental pointer"):
                self.library.undo()
            from niri_fx.setup import restore

            with self.assertRaisesRegex(ValueError, "experimental pointer"):
                restore(
                    self.library.state, self.library.transaction(), apply=True, verify_native=False
                )
            self.assertNotIn(
                "pointer-wobble", (self.config.parent / "nirifx/animations.kdl").read_text()
            )

    def test_profile_management_is_owned_and_rejects_stale_changes_and_name_collisions(self):
        original = self.config.read_bytes()
        self.library.store({"document": self.doc, "expected": None})
        entry = self.library.listing()["managed"]["custom-demo-combo"]
        path = self.library.folder / "demo-combo.json"
        with self.assertRaisesRegex(ValueError, "changed"):
            self.library.store({"document": self.doc, "expected": None})
        renamed = {
            "action": "rename",
            "id": "custom-demo-combo",
            "expected": entry["expected"],
            "name": "My Night",
        }
        self.library.manage(renamed)
        self.assertFalse(path.exists())
        night = self.library.listing()["managed"]["custom-my-night"]
        self.assertEqual(night["document"], dict(self.doc, name="My Night"))
        self.library.store({"document": self.doc, "expected": None})
        with self.assertRaisesRegex(ValueError, "already belongs"):
            self.library.manage(
                dict(renamed, id="custom-my-night", expected=night["expected"], name="Demo_Combo")
            )
        changed = self.library.folder / "my-night.json"
        changed.write_text(
            json.dumps(
                dict(
                    self.doc,
                    name="My Night",
                    actions=dict(self.doc["actions"], close=self.doc["actions"]["open"]),
                )
            )
        )
        external = changed.read_bytes()
        with self.assertRaisesRegex(ValueError, "changed"):
            self.library.manage(
                {"action": "remove", "id": "custom-my-night", "expected": night["expected"]}
            )
        self.assertEqual(changed.read_bytes(), external)
        fresh = self.library.listing()["managed"]["custom-my-night"]
        self.library.manage(
            {"action": "remove", "id": "custom-my-night", "expected": fresh["expected"]}
        )
        self.assertFalse(changed.exists())
        self.assertIn("custom-demo-combo", self.library.listing()["customs"])
        self.assertEqual(self.config.read_bytes(), original)
        self.assertFalse(self.args.registry.exists())

    def test_profile_management_rejects_paths_unknown_fields_and_foreign_files(self):
        self.library.store({"document": self.doc, "expected": None})
        expected = self.library.listing()["managed"]["custom-demo-combo"]["expected"]
        remove = {"action": "remove", "id": "custom-demo-combo", "expected": expected}
        for request in (
            dict(remove, id="../../outside"),
            dict(remove, path="outside"),
            dict(remove, action="execute"),
            dict(remove, expected=None),
            dict(remove, expected=True),
            dict(remove, id="custom-unknown"),
            dict(remove, action="rename", name="../outside"),
        ):
            with self.subTest(request=request), self.assertRaises(ValueError):
                self.library.manage(request)
        self.assertTrue((self.library.folder / "demo-combo.json").exists())
        outside = self.root / "outside.json"
        outside.write_text(json.dumps(self.doc))
        linked = self.library.folder / "linked.json"
        linked.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.library.manage(dict(remove, id="custom-linked"))
        self.assertTrue(outside.exists())

    def test_broken_profiles_are_skipped_individually_without_mutation(self):
        self.library.store({"document": self.doc, "expected": None})
        broken = self.library.folder / "broken.json"
        broken.write_text("{incomplete")
        mismatch = self.library.folder / "wrong-name.json"
        mismatch.write_text(json.dumps(self.doc))
        large = self.library.folder / "large.json"
        large.write_bytes(b" " * 17000)
        listing = self.library.listing()
        self.assertEqual(list(listing["managed"]), ["custom-demo-combo"])
        self.assertIn("3 saved profile", listing["warnings"][0])
        self.assertEqual(broken.read_text(), "{incomplete")
        self.assertEqual(mismatch.read_text(), json.dumps(self.doc))
        self.assertEqual(large.stat().st_size, 17000)

    def test_profile_limit_allows_replacement_and_rename_at_capacity(self):
        self.library.store({"document": self.doc, "expected": None})
        for index in range(99):
            (self.library.folder / f"broken-{index}.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "full"):
            self.library.store({"document": dict(self.doc, name="New"), "expected": None})
        expected = self.library.listing()["managed"]["custom-demo-combo"]["expected"]
        self.library.store({"document": self.doc, "expected": expected})
        self.library.manage(
            {"action": "rename", "id": "custom-demo-combo", "expected": expected, "name": "Renamed"}
        )
        self.assertEqual(len(list(self.library.folder.glob("*.json"))), 100)

    def test_noctalia_uses_connected_picker_and_preserves_speed(self):
        self.selection["document"] = dict(
            self.doc, pointer={"strength": 0.7, "damping": 65, "frequency": 8}
        )
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
        self.assertIn("not activated", " ".join(review["notes"]))
        self.assertEqual(target.read_bytes(), original)
        with patch("niri_fx.setup.validate_config"):
            library.apply({"selection": self.selection, "expected": review["plan_sha256"]})
        self.assertEqual(self.config.read_bytes(), root)
        self.assertIn("slowdown 1.25", target.read_text())
        self.assertIn("niri-fx-custom-demo-combo.kdl", target.read_text())
        self.assertNotIn(
            "pointer-wobble", (self.args.preset_dir / "niri-fx-custom-demo-combo.kdl").read_text()
        )
        self.assertEqual(
            library.listing()["active"]["pointer"], self.selection["document"]["pointer"]
        )
        library.undo()
        self.assertEqual(target.read_bytes(), original)
        self.assertFalse((self.args.preset_dir / "niri-fx-custom-demo-combo.kdl").exists())
        target.write_text("input { keyboard {} }\n")
        with self.assertRaisesRegex(ValueError, "independent settings"):
            library.review(self.selection)

    def test_iris_uses_serializer_without_live_writes_and_rolls_back_validation_failure(self):
        self.selection["document"] = dict(
            self.doc, pointer={"strength": 0.7, "damping": 65, "frequency": 8}
        )
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
                registry["presets"][0]["profile"]["pointer"], self.selection["document"]["pointer"]
            )
            self.assertNotIn("pointer-wobble", json.dumps(registry["presets"][0]["types"]))
            self.assertEqual(
                registry["presets"][0]["types"]["workspace-switch"],
                shell_registry()["presets"][0]["types"]["workspace-switch"],
            )
            library.undo()
            self.assertEqual(animation.read_bytes(), original)
            self.assertEqual(self.args.registry.read_bytes(), old_registry)


if __name__ == "__main__":
    unittest.main()
