"""A public catalog must not silently omit styles or publish different settings."""

import importlib.util
import re
import unittest
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path

from niri_fx.catalog import PROFILES, STYLES
from niri_fx.documents import effect_document
from niri_fx.effects import PRESETS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gallery", ROOT / "scripts/build-gallery.py")
gallery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gallery)


class PublicCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clips = gallery.entries()

    def test_reference_covers_every_style_with_portable_settings(self):
        reference = gallery.preset_reference(self.clips)
        identifiers = re.findall(r"^\| `([^`]+)` \|", reference, re.M)
        self.assertEqual(len(identifiers), len(STYLES))
        self.assertEqual(set(identifiers), set(STYLES))
        downloads = re.findall(r"\[JSON\]\(([^)]+)\)", reference)
        self.assertEqual(len(downloads), len(STYLES))
        self.assertTrue(all((ROOT / "docs" / name).is_file() for name in downloads))
        # Pairing timing belongs to each refined action; its opening effect's
        # close duration must not leak into the closing action's public table.
        profile = PROFILES["geometric-flow"]
        self.assertNotEqual(profile.open.close_ms, profile.close.close_ms)
        self.assertIn(
            f"| `geometric-flow` | Triangle Shatter | Hex Swarm | {profile.open.open_ms} / {profile.close.close_ms} |",
            reference,
        )

    def test_missing_or_duplicate_recordings_cannot_produce_a_catalog(self):
        for identifier in ("preset-balanced", "profile-geometric-flow"):
            with self.subTest(identifier=identifier):
                clips = [clip for clip in self.clips if clip["id"] != identifier]
                with self.assertRaisesRegex(ValueError, identifier):
                    gallery.preset_reference(clips)
        with self.assertRaisesRegex(ValueError, "Recording IDs must be unique"):
            gallery.preset_reference([*self.clips, self.clips[0]])

    def test_a_download_must_match_the_named_canonical_style(self):
        clips = deepcopy(self.clips)
        clip = next(clip for clip in clips if clip["id"] == "preset-balanced")
        clip["settings"][0]["document"] = effect_document("Balanced", PRESETS["explosion"])
        with self.assertRaisesRegex(ValueError, "Recorded settings differ.*preset-balanced"):
            gallery.preset_reference(clips)

    def test_pointer_cards_offer_native_config_without_a_studio_import_claim(self):
        preset = gallery.POINTER_PRESETS["gentle"]
        recorded = {"pointer_preset": "gentle", "pointer_wobble": asdict(preset.wobble)}
        native = gallery.pointer_settings(recorded)
        card = deepcopy(self.clips[0])
        card.update(settings=[], pointer=native, kind="experimental", action="pointer")
        html = gallery.document([card])
        self.assertIn("Download experimental KDL", html)
        self.assertIn("--pointer-wobble gentle", html)
        self.assertNotIn("Download JSON", html)
        self.assertNotIn("data-studio", html)
        self.assertNotIn("custom-shader", native["document"].split("animations {", 1)[1])
        self.assertIsNone(gallery.pointer_settings({}))
        recorded["pointer_wobble"]["strength"] = 0.9
        with self.assertRaisesRegex(ValueError, "Recorded pointer settings changed"):
            gallery.pointer_settings(recorded)
