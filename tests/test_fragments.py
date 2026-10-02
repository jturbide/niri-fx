from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from niri_fragments.effects import Effect, PRESETS, render_kdl
from niri_fragments.integration import custom_document, make_custom_preset, make_presets, merge_registry, update_registry
from niri_fragments.cli import parser, selected_effect


def shell_registry():
    return {"active": "example", "presets": [{"id": "example", "types": {
        "workspace-switch": {"spring": [0.9, 700, 0.0001]},
        "window-resize": {"duration-ms": 210, "curve": "ease-out-cubic", "custom-shader": "existing resize shader"},
        "window-open": {"duration-ms": 170, "curve": "ease-out-expo"},
        "window-close": {"duration-ms": 130, "curve": "ease-out-quad"},
    }}]}


class PresetTests(unittest.TestCase):
    def test_non_window_settings_preserved_and_base_not_mutated(self):
        registry = shell_registry()
        original = deepcopy(registry)
        presets = make_presets(registry)
        for preset in presets:
            for name in ("workspace-switch", "window-resize"):
                self.assertEqual(preset["types"][name], original["presets"][0]["types"][name])
            self.assertIn("open_color", preset["types"]["window-open"]["custom-shader"])
            self.assertIn("close_color", preset["types"]["window-close"]["custom-shader"])
        self.assertEqual(registry, original)

    def test_custom_base_requires_explicit_choice(self):
        registry = shell_registry()
        registry["active"] = ""
        with self.assertRaisesRegex(ValueError, "custom"):
            make_presets(registry)
        self.assertEqual(len(make_presets(registry, "example")), len(PRESETS))

    def test_reregistration_resolves_original_base(self):
        registry = shell_registry()
        registry["presets"].extend(make_presets(registry))
        registry["active"] = "niri-fragments-balanced"
        self.assertTrue(all(p["base-preset"] == "example" for p in make_presets(registry)))

    def test_cycle_rejected(self):
        registry = {"active": "a", "presets": [{"id": "a", "generator": "niri-fragments", "base-preset": "a"}]}
        with self.assertRaisesRegex(ValueError, "cycle"):
            make_presets(registry)

    def test_foreign_id_collision_rejected(self):
        with self.assertRaisesRegex(ValueError, "another provider"):
            merge_registry({"presets": [{"id": "niri-fragments-balanced"}]}, make_presets(shell_registry()))

    def test_unrelated_entries_metadata_and_defaults_preserved(self):
        data = {"default": "mine", "note": {"keep": True}, "presets": [{"id": "mine", "extra": 7}]}
        updated = merge_registry(data, make_presets(shell_registry()))
        self.assertEqual(merge_registry(updated, [], remove=True), data)

    def test_bad_and_duplicate_registry_entries_rejected(self):
        for data in ([], {"presets": {}}, {"presets": [None]}, {"presets": [{"id": "x"}, {"id": "x"}]}):
            with self.subTest(data=data), self.assertRaises(ValueError):
                merge_registry(data, [])

    def test_custom_presets_survive_pack_updates_and_each_other(self):
        registry = shell_registry()
        builtins = make_presets(registry)
        first = make_custom_preset(registry, {"schema": 1, "name": "My Meteor", "effect": {"gravity": "down", "particles": 300}})
        second = make_custom_preset(registry, {"schema": 1, "name": "My Orbit", "effect": {"swirl": 180}})
        data = merge_registry({}, builtins)
        data = merge_registry(data, [first])
        data = merge_registry(data, [second])
        data = merge_registry(data, builtins)
        self.assertEqual(len(data["presets"]), len(PRESETS) + 2)
        self.assertIn(first, data["presets"])
        self.assertIn(second, data["presets"])
        self.assertEqual(merge_registry(data, [], remove=True)["presets"], [])

    def test_custom_input_is_parameters_not_arbitrary_shader_code(self):
        invalid = [[], {"schema": 1, "name": "Bad", "effect": {"shader": "arbitrary"}},
                   {"schema": 1, "name": "../outside", "effect": {}},
                   {"schema": 1, "name": "Bad", "effect": {"gravity": "typo"}},
                   {"schema": 2, "name": "Future", "effect": {}}]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ValueError):
                custom_document(data)


class FileTests(unittest.TestCase):
    def test_atomic_update_backup_idempotence_and_selective_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "presets.json"
            original = b'{"presets": [{"id": "other"}], "keep": 42}\n'
            target.write_bytes(original)
            target.chmod(0o640)
            generated = make_presets(shell_registry())
            result = update_registry(target, generated)
            self.assertEqual(Path(result["backup"]).read_bytes(), original)
            self.assertEqual(target.stat().st_mode & 0o777, 0o640)
            self.assertFalse(update_registry(target, generated)["changed"])
            # Another provider's later addition must survive unregister.
            current = json.loads(target.read_text())
            current["presets"].append({"id": "added-later"})
            target.write_text(json.dumps(current))
            update_registry(target, remove=True)
            self.assertEqual(json.loads(target.read_text()), {"presets": [{"id": "other"}, {"id": "added-later"}], "keep": 42})

    def test_malformed_json_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "presets.json"
            target.write_text("broken json")
            with self.assertRaises(ValueError):
                update_registry(target, make_presets(shell_registry()))
            self.assertEqual(target.read_text(), "broken json")

    def test_dry_run_creates_no_files_or_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "missing" / "presets.json"
            result = update_registry(target, make_presets(shell_registry()), dry_run=True)
            self.assertEqual(len(result["registry"]["presets"]), len(PRESETS))
            self.assertFalse(target.parent.exists())

    def test_symlink_target_updated_without_replacing_link(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "target.json"
            target.write_text('{"presets": []}')
            link = Path(directory) / "link.json"
            link.symlink_to(target.name)
            update_registry(link, make_presets(shell_registry()))
            self.assertTrue(link.is_symlink())
            self.assertEqual(len(json.loads(target.read_text())["presets"]), len(PRESETS))


class EffectTests(unittest.TestCase):
    def test_invalid_values_rejected(self):
        for overrides in ({"tile_size": 0}, {"scatter": float("nan")}, {"scatter": float("inf")},
                          {"open_ms": 2.5}, {"close_ms": 0}, {"tile_size": True},
                          {"particles": 10}, {"particles": 100.5}, {"gravity_strength": -1},
                          {"gravity": "bad"}, {"rotation": "bad"}, {"swirl": 400}, {"spin": float("nan")}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                Effect(**overrides)

    def test_every_preset_renders_both_directions(self):
        for effect in PRESETS.values():
            kdl = render_kdl(effect)
            self.assertNotIn("@", kdl)
            self.assertEqual(kdl.count('custom-shader r"'), 2)
            self.assertIn("1.0 - niri_clamped_progress", kdl)

    def test_fixed_tile_option_replaces_preset_target_count(self):
        args = parser().parse_args(["render", "--preset", "earth", "--tile-size", "40"])
        effect = selected_effect(args)
        self.assertEqual(effect.tile_size, 40)
        self.assertEqual(effect.particles, 0)
        self.assertEqual(effect.gravity, "down")


if __name__ == "__main__":
    unittest.main()
