"""An action set must remain a stock profile until each companion is chosen."""

import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from itertools import product

from helpers import shell_registry

from niri_fx.action_sets import ACTION_SETS, companion_documents
from niri_fx.catalog import PROFILES
from niri_fx.cli import main
from niri_fx.documents import MAX_DOCUMENT_BYTES, parse_document
from niri_fx.effects import animation_types, render_kdl
from niri_fx.integration import make_custom_preset


class ActionSetTests(unittest.TestCase):
    def test_each_opt_in_is_independent_and_stock_exports_omit_movement(self):
        for name, recipe in ACTION_SETS.items():
            self.assertEqual(PROFILES[name], recipe.profile())
            for resize, movement in product((False, True), repeat=2):
                with self.subTest(name=name, resize=resize, movement=movement):
                    profile = recipe.profile(include_resize=resize, include_movement=movement)
                    document = profile.document(name)
                    self.assertEqual(parse_document(document)[2], profile)
                    self.assertLessEqual(len(json.dumps(document).encode()), MAX_DOCUMENT_BYTES)
                    self.assertEqual(profile.resize, recipe.resize if resize else None)
                    self.assertEqual(profile.movement, recipe.movement if movement else None)
                    stock = render_kdl(profile)
                    self.assertEqual("window-resize" in stock, resize)
                    self.assertNotIn("window-movement", stock)
                    if movement:
                        self.assertIn("window-movement", render_kdl(profile, movement=True))
                    else:
                        with self.assertRaisesRegex(ValueError, "explicitly choose"):
                            render_kdl(profile, movement=True)
                    self.assertEqual(PROFILES[name].resize, None)

    def test_companion_metadata_is_fresh_and_not_a_profile_field(self):
        documents = companion_documents()
        documents["fragments-motion"]["resize"]["resize_strength"] = 0
        self.assertEqual(
            companion_documents()["fragments-motion"]["resize"]["resize_strength"], 0.42
        )
        for recipe in ACTION_SETS.values():
            self.assertEqual(
                set(recipe.profile().document("Set")),
                {"kind", "schema", "name", "actions", "motion"},
            )

    def test_shell_registration_preserves_optional_actions_and_unrelated_settings(self):
        base = shell_registry()
        for name, recipe in ACTION_SETS.items():
            for resize in (False, True):
                profile = recipe.profile(include_resize=resize, include_movement=True)
                saved = make_custom_preset(base, profile.document(name))
                self.assertNotIn("window-movement", saved["types"])
                if resize:
                    self.assertEqual(
                        saved["types"]["window-resize"], animation_types(profile)["window-resize"]
                    )
                else:
                    self.assertEqual(
                        saved["types"]["window-resize"],
                        base["presets"][0]["types"]["window-resize"],
                    )

    def test_cli_creates_exact_requested_actions_and_can_rename(self):
        for name in ACTION_SETS:
            for flags in (
                [],
                ["--include-resize"],
                ["--include-movement"],
                ["--include-resize", "--include-movement"],
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(
                        main(["profile", "--action-set", name, "--name", "My Look", *flags]), 0
                    )
                doc = json.loads(output.getvalue())
                self.assertEqual(doc["name"], "My Look")
                self.assertEqual(
                    parse_document(doc)[2],
                    ACTION_SETS[name].profile(
                        include_resize="--include-resize" in flags,
                        include_movement="--include-movement" in flags,
                    ),
                )

    def test_cli_rejects_ambiguous_combinations_and_keeps_manual_defaults(self):
        for flags in (
            ["--include-resize"],
            ["--include-movement"],
            ["--action-set", "elastic-motion", "--open-preset", "balanced"],
            ["--action-set", "elastic-motion", "--resize-preset", "balanced"],
            ["--action-set", "elastic-motion", "--desktop-motion", "gentle"],
            ["--action-set", "elastic-motion", "--name", ""],
            ["--name", ""],
        ):
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                self.assertEqual(main(["profile", *flags]), 2)
            self.assertEqual(output.getvalue(), "")
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["profile"]), 0)
        doc = json.loads(output.getvalue())
        self.assertEqual(doc["name"], "My Profile")
        self.assertEqual(doc["actions"]["open"]["family"], "elastic")
        self.assertIsNone(doc["actions"]["resize"])
        self.assertIsNone(doc["actions"]["movement"])
