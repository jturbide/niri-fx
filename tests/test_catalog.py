import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from helpers import shell_registry

from niri_fx.action_sets import ACTION_SETS
from niri_fx.catalog import (
    COLLECTIONS,
    PROFILE_MOTIONS,
    PROFILE_RECIPES,
    PROFILE_TUNING,
    PROFILES,
    RECOMMENDED,
    RECOMMENDED_PROFILES,
    STYLES,
    collection_documents,
    documents,
    families,
)
from niri_fx.cli import main, parser, selected_effect
from niri_fx.documents import parse_document
from niri_fx.effects import PRESETS, animation_types, render_kdl
from niri_fx.integration import make_builtin_profile, make_presets
from niri_fx.model import FAMILIES, PARAMETERS
from niri_fx.profiles import Profile
from niri_fx.terminal import catalog


class CuratedProfileTests(unittest.TestCase):
    def test_collection_metadata_is_valid_and_does_not_modify_documents(self):
        before = documents()
        for name, collection in COLLECTIONS.items():
            with self.subTest(name=name):
                self.assertTrue(collection["label"] and collection["description"])
                members = collection["styles"]
                self.assertTrue(members)
                self.assertEqual(len(members), len(set(members)))
                self.assertFalse(set(members) - set(STYLES))
                self.assertEqual(set(catalog(collection=name)), set(members))
        self.assertTrue(
            all(any(name in c["styles"] for c in COLLECTIONS.values()) for name in PROFILES)
        )
        metadata = collection_documents()
        metadata["shapes"]["styles"].clear()
        self.assertTrue(collection_documents()["shapes"]["styles"])
        self.assertEqual(before, documents())

    def test_collection_cli_preserves_profile_actions_and_intersects_filters(self):
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["list", "--collections"]), 0)
        self.assertEqual(json.loads(output.getvalue()), collection_documents())
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["list", "--collection", "shapes"]), 0)
        exported = json.loads(output.getvalue())
        self.assertEqual(parse_document(exported["geometric-flow"])[2], PROFILES["geometric-flow"])
        self.assertEqual(catalog(collection="shapes", profiles=True), ["geometric-flow"])
        self.assertEqual(
            catalog("hexagon burst", collection="shapes", family="hexagons"), ["hexagon-burst"]
        )
        with redirect_stderr(io.StringIO()) as error:
            self.assertEqual(main(["list", "--collections", "--family", "pixels"]), 2)
        self.assertIn("cannot be combined", error.getvalue())

    def test_family_metadata_includes_resize_and_movement_actions(self):
        profile = Profile(
            PRESETS["balanced"],
            PRESETS["dust-drift"],
            resize=PRESETS["spring-wobble"],
            movement=PRESETS["shockwave"],
        )
        self.assertEqual(families(profile), ("fragments", "pixels", "elastic", "distortion"))
        self.assertEqual(families(PROFILES["ribbon-current"]), ("slices",))

    def test_movement_collection_exports_only_when_movement_is_selected(self):
        for name in COLLECTIONS["movement"]["styles"]:
            with self.subTest(name=name):
                effect = PRESETS[name]
                self.assertTrue(FAMILIES[effect.family]["movement"])
                self.assertNotIn("window-movement", animation_types(effect))
                self.assertNotIn("window-resize", animation_types(effect))
                profile = Profile(None, None, movement=effect)
                exported = animation_types(profile, movement=True)
                self.assertEqual(set(exported), {"window-movement"})
                movement = exported["window-movement"]
                self.assertEqual(movement["duration-ms"], effect.movement_ms)
                self.assertIn("vec4 move_color(", movement["custom-shader"])
                self.assertNotIn("@", movement["custom-shader"])

    def test_inir_search_keywords_cover_pairings_and_collections(self):
        registry = {p["id"]: p for p in make_presets(shell_registry())}
        keywords = registry["niri-fx-burst-and-drift"]["keywords"]
        self.assertTrue({"fragments", "pixels", "bursts"}.issubset(keywords))
        self.assertIn("shapes", registry["niri-fx-geometric-flow"]["keywords"])

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

    def test_starter_selection_is_shared_and_leaves_resize_off(self):
        self.assertEqual(set(catalog(recommended=True)), set(RECOMMENDED))
        for name, description in RECOMMENDED.items():
            self.assertIn(name, PRESETS)
            self.assertTrue(description.strip())
            self.assertFalse(PRESETS[name].resize)
            self.assertNotIn("window-resize", render_kdl(PRESETS[name]))

    def test_recommended_combos_are_complete_and_keep_optional_actions_unset(self):
        self.assertEqual(
            tuple(RECOMMENDED_PROFILES),
            (
                "fragment-flow",
                "soft-landing",
                "ribbon-current",
                "playful-motion",
                "geometric-flow",
            ),
        )
        for name, description in RECOMMENDED_PROFILES.items():
            with self.subTest(name=name):
                profile = PROFILES[name]
                self.assertEqual(description, PROFILE_RECIPES[name][2])
                self.assertTrue(description.strip())
                self.assertIsNone(profile.resize)
                self.assertIsNone(profile.movement)
                self.assertFalse(profile.open.resize or profile.close.resize)
                self.assertLessEqual(profile.open.open_ms, 800)
                self.assertLessEqual(profile.close.close_ms, 800)
                self.assertEqual(profile.motion, PROFILE_MOTIONS.get(name))
                self.assertEqual(parse_document(documents()[name])[2], profile)
                self.assertNotIn("window-resize", render_kdl(profile))

    def test_combo_refinements_are_bounded_and_apply_to_supported_action_fields(self):
        self.assertEqual(set(PROFILE_TUNING), set(RECOMMENDED_PROFILES))
        for name, tuning in PROFILE_TUNING.items():
            self.assertEqual(set(tuning), {"open", "close"})
            for index, action in enumerate(("open", "close")):
                effect = getattr(PROFILES[name], action)
                source = PRESETS[PROFILE_RECIPES[name][index]]
                self.assertEqual(effect.family, source.family)
                self.assertFalse(effect.resize)
                for field, value in tuning[action].items():
                    with self.subTest(name=name, action=action, field=field):
                        specification = PARAMETERS[field]
                        self.assertNotIn(
                            field,
                            {"family", "resize", "open_ms" if action == "close" else "close_ms"},
                        )
                        self.assertNotIn(specification["group"], {"resize", "movement"})
                        self.assertTrue(
                            not specification["families"]
                            or effect.family in specification["families"]
                        )
                        low, high = specification["limits"]
                        self.assertLessEqual(low, value)
                        self.assertLessEqual(value, high)
                # The paired action keeps following the base style's unused timing.
                other_timing = "close_ms" if action == "open" else "open_ms"
                self.assertEqual(getattr(effect, other_timing), getattr(source, other_timing))
        for name in ("fragment-flow", "geometric-flow"):
            self.assertEqual(PROFILES[name].open.particles, PROFILES[name].close.particles)
        ribbons = PROFILES["ribbon-current"]
        self.assertEqual(ribbons.open.slice_count, ribbons.close.slice_count)

    def test_combo_refinements_preserve_all_source_presets_and_other_profiles(self):
        # A fresh import detects accidental mutation even when the test process
        # already imported the finished catalog before this check.
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from dataclasses import asdict;from niri_fx.presets import PRESETS;"
                "before={name:asdict(effect) for name,effect in PRESETS.items()};"
                "import niri_fx.catalog;"
                "assert before=={name:asdict(effect) for name,effect in PRESETS.items()}",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(PRESETS), 80)
        self.assertEqual(len(PROFILES), 16)
        for name, (opening, closing, _) in PROFILE_RECIPES.items():
            if name in PROFILE_TUNING:
                continue
            with self.subTest(name=name):
                expected = (
                    ACTION_SETS[name].profile()
                    if name in ACTION_SETS
                    else Profile(
                        PRESETS[opening], PRESETS[closing], motion=PROFILE_MOTIONS.get(name)
                    )
                )
                self.assertEqual(PROFILES[name], expected)
                self.assertIs(PROFILES[name].open, PRESETS[opening])
                self.assertIs(PROFILES[name].close, PRESETS[closing])

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
        for name in ("balanced", "explosion"):
            for flags in (
                ["--preset", name, "--profile", "fragment-flow"],
                ["--profile", "fragment-flow", "--preset", name],
            ):
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    parser().parse_args(["render", *flags])
        defaults = parser().parse_args(["render"])
        self.assertEqual(defaults.preset, "balanced")
        self.assertEqual(selected_effect(defaults), PRESETS["balanced"])

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
