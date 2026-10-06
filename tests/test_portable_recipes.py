"""Complete saved recipes survive legacy migration and activation boundaries."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

import test_native_customization
import test_native_shared
from test_native_library import snapshot

from niri_fx import native_customization
from niri_fx.cli import main
from niri_fx.documents import MAX_DOCUMENT_BYTES, effect_document, load_document, parse_document
from niri_fx.fragment_motion import PRESETS
from niri_fx.model import Effect
from niri_fx.motion import MOTION_PACKS
from niri_fx.pointer import PointerWobble
from niri_fx.profiles import Profile


class PortableRecipeTests(unittest.TestCase):
    def fixture(self):
        fixture = test_native_customization.NativeCustomizationTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        return fixture

    def test_legacy_response_comes_from_retained_bytes_not_new_prefab_defaults(self):
        fixture = self.fixture()
        base = fixture.stage()
        for name, preset in PRESETS.items():
            with self.subTest(preset=name):
                plan = fixture.plan(base, Profile(movement=preset.effect), fragment_preset=name)
                fixture.apply(plan)
                bundle = plan["selection"]["bundle_id"]
                before = snapshot(fixture.root)
                replacement = replace(
                    preset, particles=100, settings=replace(preset.settings, max_lag=7)
                )
                # Replace the catalog reference, not its immutable mapping.
                with patch.object(native_customization, "FRAGMENT_PRESETS", {name: replacement}):
                    migrated = native_customization.portable_recipe(fixture.root, bundle)
                document = migrated["document"]
                self.assertEqual(document["schema"], 4)
                self.assertEqual(document["fragment_motion"], asdict(preset.settings))
                self.assertEqual(parse_document(document)[2].movement, preset.effect)
                self.assertIsNone(migrated["fragment_preset"])
                self.assertEqual(snapshot(fixture.root), before)
                self.assertEqual(
                    native_customization.read_recipe(fixture.root, bundle)["document"]["schema"], 2
                )

    def test_shared_legacy_recipe_exports_frozen_response_without_changing_sources(self):
        fixture = test_native_shared.NativeSharedTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        prepared = fixture.fixture.plan(
            fixture.plain, Profile(movement=PRESETS["tear"].effect), fragment_preset="tear"
        )
        fixture.fixture.apply(prepared)
        fixture.base = prepared["selection"]["bundle_id"]
        with patch.object(native_customization, "FRAGMENT_PRESETS", {"tear": PRESETS["gentle"]}):
            report = fixture.adopt()
        before = snapshot(fixture.fixture.fixture.root)
        portable = native_customization.portable_recipe(fixture.root, report["bundle_id"])
        self.assertEqual(portable["document"]["fragment_motion"], asdict(PRESETS["tear"].settings))
        self.assertEqual(snapshot(fixture.fixture.fixture.root), before)

    def test_explicit_custom_response_is_authoritative_and_capability_gated(self):
        fixture = self.fixture()
        response = replace(
            PRESETS["tear"].settings, batches=71, max_lag=555, distance_exponent=1e-8
        )
        material = replace(PRESETS["tear"].effect, particles=975, spin=65)
        profile = Profile(movement=material, fragment_motion=response, swap=Effect())
        base = fixture.stage()
        plan = fixture.plan(base, profile)
        fixture.apply(plan)
        recipe, files = fixture.recipe_and_files(plan)
        self.assertEqual(recipe["document"], profile.document("My desktop"))
        self.assertIsNone(recipe["fragment_preset"])
        overlay = files[recipe["overlay_file"]].decode()
        self.assertIn("max-lag 555", overlay)
        self.assertIn("distance-exponent 1e-08", overlay)
        self.assertEqual(overlay.count("fragment-motion {"), 1)
        self.assertNotIn("fragment-motion {", overlay.split("window-swap")[1])
        limited = fixture.stage(variant="movement")
        with self.assertRaisesRegex(ValueError, "fragment build"):
            fixture.plan(limited, replace(profile, swap=None))
        with self.assertRaisesRegex(ValueError, "not both"):
            fixture.plan(base, profile, fragment_preset="tear")

    def test_dormant_response_survives_off_preserve_and_material_changes(self):
        fixture = self.fixture()
        base = fixture.stage(variant="movement")
        for movement in (None, "off", Effect(family="slices")):
            with self.subTest(movement=movement):
                profile = Profile(movement=movement, fragment_motion=PRESETS["tear"].settings)
                plan = fixture.plan(base, profile)
                fixture.apply(plan)
                recipe, files = fixture.recipe_and_files(plan)
                overlay = files[recipe["overlay_file"]]
                self.assertNotIn(b"fragment-motion {", overlay)
                self.assertNotIn(b"nirifx-fragment-motion:", overlay)
                self.assertEqual(parse_document(recipe["document"])[2], profile)

    def test_cli_exports_without_writes_and_creates_complete_prefabs(self):
        fixture = self.fixture()
        base = fixture.stage()
        plan = fixture.plan(base, Profile(movement=PRESETS["tear"].effect), fragment_preset="tear")
        fixture.apply(plan)
        before = snapshot(fixture.root)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(
                main(
                    [
                        "native",
                        "export",
                        plan["selection"]["bundle_id"],
                        "--root",
                        str(fixture.root),
                    ]
                ),
                0,
            )
        document = json.loads(output.getvalue())
        self.assertEqual(document["fragment_motion"], asdict(PRESETS["tear"].settings))
        self.assertEqual(snapshot(fixture.root), before)
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(
                main(
                    [
                        "profile",
                        "--fragment-preset",
                        "cascade",
                        "--open",
                        "preserve",
                        "--close",
                        "off",
                    ]
                ),
                0,
            )
        _, _, profile = parse_document(json.loads(output.getvalue()))
        self.assertIsNone(profile.open)
        self.assertEqual(profile.close, "off")
        self.assertIsNone(profile.resize)
        self.assertEqual(profile.fragment_motion, PRESETS["cascade"].settings)

    def test_five_action_pretty_export_fits_and_reimports_without_loss(self):
        profile = Profile(
            **{action: Effect() for action in ("open", "close", "resize", "movement", "swap")},
            motion=next(iter(MOTION_PACKS.values())),
            pointer=PointerWobble(),
            fragment_motion=PRESETS["cascade"].settings,
        )
        document = effect_document("Complete portable recipe", profile)
        raw = (json.dumps(document, indent=2) + "\n").encode()
        self.assertGreater(len(raw), 16 * 1024)
        self.assertLessEqual(len(raw), MAX_DOCUMENT_BYTES)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "complete.json"
            path.write_bytes(raw)
            self.assertEqual(parse_document(load_document(path))[2], profile)
