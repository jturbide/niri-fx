import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from helpers import shell_registry

from niri_fx.catalog import PROFILES, STYLES, documents
from niri_fx.cli import main, parser, selected_effect
from niri_fx.documents import parse_document
from niri_fx.effects import PRESETS, animation_types, render_kdl
from niri_fx.integration import make_builtin_profile, make_presets
from niri_fx.terminal import catalog


class CuratedProfileTests(unittest.TestCase):
    def test_portable_catalog_keeps_both_actions_and_no_resize(self):
        exported = documents()
        self.assertFalse(set(PROFILES) & set(PRESETS))
        for name, style in STYLES.items():
            self.assertEqual(parse_document(exported[name])[2], style)
        for name, profile in PROFILES.items():
            self.assertIsNone(profile.resize)
            self.assertIsNone(profile.movement)
            self.assertFalse(profile.open.resize or profile.close.resize)
            types = animation_types(profile)
            self.assertEqual(types["window-open"], animation_types(profile.open)["window-open"])
            self.assertEqual(types["window-close"], animation_types(profile.close)["window-close"])
            self.assertNotIn("window-resize", render_kdl(profile), name)
        exported["burst-and-drift"]["actions"]["close"]["particles"] = 17
        self.assertNotEqual(documents()["burst-and-drift"]["actions"]["close"]["particles"], 17)

    def test_profiles_filter_by_either_action_family(self):
        self.assertIn("burst-and-drift", catalog(family="fragments", profiles=True))
        self.assertIn("burst-and-drift", catalog(family="pixels", profiles=True))
        self.assertEqual(catalog("ribbon exit", profiles=True), ["ribbon-exit"])
        self.assertEqual(set(catalog(all_styles=True)), set(STYLES))

    def test_cli_profile_selection_and_portable_export(self):
        for name, profile in PROFILES.items():
            self.assertEqual(
                selected_effect(parser().parse_args(["render", "--profile", name])), profile
            )
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["inspect", "--profile", name]), 0)
            self.assertEqual(parse_document(json.loads(output.getvalue()))[2], profile)
        for flags, expected in (
            ([], PRESETS),
            (["--profiles"], PROFILES),
            (["--documents"], STYLES),
        ):
            with redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(["list", *flags]), 0)
            self.assertEqual(set(json.loads(output.getvalue())), set(expected))

    def test_profile_overrides_are_rejected_without_writes(self):
        for extra in (["--resize"], ["--particles", "120"], ["--name", "Renamed"]):
            with redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(main(["setup", "--profile", "fragment-flow", *extra]), 2)
            self.assertIn("--profile", errors.getvalue())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "style.json"
            path.write_text(json.dumps(documents()["balanced"]))
            with redirect_stderr(io.StringIO()):
                self.assertEqual(
                    main(["render", "--profile", "fragment-flow", "--custom", str(path)]), 2
                )
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser().parse_args(["render", "--preset", "balanced", "--profile", "fragment-flow"])

    def test_one_profile_and_full_inir_pack_share_identity_and_base(self):
        shell = shell_registry()
        pack = {preset["id"]: preset for preset in make_presets(shell)}
        self.assertEqual(len(pack), len(STYLES))
        for name in PROFILES:
            preset = make_builtin_profile(shell, name)
            self.assertEqual(preset, pack["niri-fx-" + name])
            self.assertEqual(
                preset["types"]["window-resize"], shell["presets"][0]["types"]["window-resize"]
            )
            self.assertEqual(parse_document(preset["profile"])[2], PROFILES[name])
