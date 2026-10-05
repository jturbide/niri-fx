"""Independent action choices, migration and recovery against nondefault bases."""

import contextlib
import copy
import io
import json
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from helpers import shell_registry

from niri_fx.catalog import PROFILES, families
from niri_fx.cli import main
from niri_fx.documents import parse_document
from niri_fx.effects import animation_types, render_kdl
from niri_fx.integration import make_custom_preset
from niri_fx.library import Library
from niri_fx.model import Effect
from niri_fx.pointer import PointerWobble
from niri_fx.preview import preview_catalog
from niri_fx.profiles import ACTIONS, Profile


class ActionModeTests(unittest.TestCase):
    def test_legacy_profiles_migrate_without_changing_export_or_optional_settings(self):
        for name, profile in PROFILES.items():
            with self.subTest(profile=name):
                legacy = dict(profile.document(name), schema=1)
                migrated = parse_document(legacy)[2]
                self.assertEqual(migrated, profile)
                self.assertEqual(render_kdl(migrated), render_kdl(profile))
                self.assertEqual(migrated.document(name)["schema"], 2)
        invalid = dict(Profile().document("Invalid legacy"), schema=1)
        with self.assertRaises(ValueError):
            parse_document(invalid)

    def test_every_shader_action_round_trips_preserve_style_and_off_independently(self):
        for action in ACTIONS:
            for value in (None, "off", Effect()):
                with self.subTest(action=action, value=value):
                    profile = replace(Profile(), **{action: value})
                    self.assertEqual(parse_document(profile.document("Choices"))[2], profile)
                    native = action == "movement" and value is not None
                    exported = animation_types(profile, movement=native)
                    if value is None:
                        self.assertEqual(exported, {})
                    elif value == "off":
                        self.assertTrue(exported[f"window-{action}"]["off"])
                        self.assertNotIn("custom-shader", exported[f"window-{action}"])
                    else:
                        self.assertIn("custom-shader", exported[f"window-{action}"])
                    self.assertEqual(
                        families(profile), ("fragments",) if isinstance(value, Effect) else ()
                    )
                    self.assertIsInstance(preview_catalog(profile)["parameters"], dict)

    def test_preserve_uses_shell_base_and_off_overrides_only_selected_actions(self):
        base = shell_registry()
        original = copy.deepcopy(base["presets"][0]["types"])
        profile = Profile(close="off", resize="off")
        saved = make_custom_preset(base, profile.document("Quiet exit"))
        self.assertEqual(saved["types"]["window-open"], original["window-open"])
        self.assertEqual(saved["types"]["window-close"], {"duration-ms": 0, "curve": "linear"})
        self.assertEqual(saved["types"]["window-resize"], {"duration-ms": 0, "curve": "linear"})
        self.assertEqual(parse_document(saved["profile"])[2], profile)
        self.assertEqual(base["presets"][0]["types"], original)
        self.assertNotIn("window-open", render_kdl(profile))

    def test_shell_off_is_serializable_and_preserved_when_inherited(self):
        base = shell_registry()
        base["presets"][0]["types"]["window-open"] = {"duration-ms": 0, "curve": "linear"}
        profile = Profile(close=Effect(), resize="off")
        saved = make_custom_preset(base, profile.document("Shell choices"))
        self.assertEqual(saved["types"]["window-open"], base["presets"][0]["types"]["window-open"])
        # The installed shell serializes every non-spring spec using these two
        # required keys. Its matcher uses the same representation after Apply.
        for action, spec in saved["types"].items():
            if "spring" not in spec:
                self.assertIsInstance(spec["duration-ms"], int, action)
                self.assertIsInstance(spec["curve"], str, action)
        self.assertNotIn("custom-shader", saved["types"]["window-resize"])
        self.assertEqual(
            saved["types"]["workspace-switch"], base["presets"][0]["types"]["workspace-switch"]
        )
        self.assertEqual(parse_document(saved["profile"])[2], profile)
        self.assertEqual(animation_types(profile)["window-resize"], {"off": True})

    def test_native_siblings_have_explicit_preservation_and_independent_off(self):
        for movement in (None, "off", Effect()):
            for pointer in (None, PointerWobble(0), PointerWobble()):
                with self.subTest(movement=movement, pointer=pointer):
                    profile = Profile(movement=movement, pointer=pointer)
                    self.assertEqual(animation_types(profile), {})
                    result = animation_types(
                        profile, movement=movement is not None, pointer=pointer is not None
                    )
                    if movement is None and pointer is None:
                        self.assertEqual(result, {})
                        continue
                    node = result["window-movement"]
                    self.assertEqual(node.get("preserve-movement", False), movement is None)
                    self.assertEqual(node.get("preserve-pointer", False), pointer is None)
                    self.assertEqual(node.get("off", False), movement == "off")
                    if pointer is not None:
                        self.assertEqual(node["pointer-wobble"]["strength"], pointer.strength)

    def test_cli_composes_explicit_modes_and_preserves_existing_preset_aliases(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = main(
                [
                    "profile",
                    "--open",
                    "preserve",
                    "--close-preset",
                    "frost-vanish",
                    "--resize",
                    "off",
                    "--movement",
                    "off",
                    "--pointer",
                    "off",
                ]
            )
        self.assertEqual(result, 0)
        profile = parse_document(json.loads(out.getvalue()))[2]
        self.assertIsNone(profile.open)
        self.assertEqual(profile.close.family, "dissolve")
        self.assertEqual(profile.resize, "off")
        self.assertEqual(profile.movement, "off")
        self.assertEqual(profile.pointer.strength, 0)

    @unittest.skipUnless(shutil.which("niri"), "Requires stock Niri config validation")
    def test_partial_and_all_off_apply_restore_with_nondefault_base(self):
        for profile in (
            Profile(close="off"),
            Profile(open="off", close="off", resize="off"),
            Profile(),
        ):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                config = root / "config.kdl"
                original = b"// Existing desktop\nanimations { window-open { duration-ms 170; }; window-close { duration-ms 240; }; window-resize { duration-ms 310; }; }\n"
                config.write_bytes(original)
                library = Library(
                    SimpleNamespace(
                        config=config,
                        state=root / "state",
                        registry=root / "registry.json",
                        inir_root=root / "no-shell",
                        base="auto",
                    ),
                    "standalone",
                )
                selection = {
                    "document": profile.document("Choices"),
                    "allow_resize": profile.resize is not None,
                    "allow_movement": False,
                }
                review = library.review(selection)
                self.assertEqual(config.read_bytes(), original)
                library.apply({"selection": selection, "expected": review["plan_sha256"]})
                generated = (root / "nirifx/animations.kdl").read_text()
                for action in ("open", "close", "resize"):
                    self.assertEqual(
                        f"window-{action}" in generated, getattr(profile, action) is not None
                    )
                library.undo()
                self.assertEqual(config.read_bytes(), original)
                self.assertFalse((root / "nirifx/animations.kdl").exists())
