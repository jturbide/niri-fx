"""Hosted exports cannot accidentally inherit a local authenticated save session."""

import json
import tempfile
import unittest
from importlib.resources import files
from pathlib import Path
from unittest.mock import Mock, patch

from niri_fx import __version__
from niri_fx.effects import PRESETS, Effect
from niri_fx.preview import preview_catalog, preview_document
from niri_fx.profiles import Profile


class HostedStudioTests(unittest.TestCase):
    def test_hosted_studio_has_no_local_connection(self):
        catalog = preview_catalog(PRESETS["balanced"], hosted=True)
        self.assertTrue(catalog["hosted"])
        self.assertIsNone(catalog["connection"])
        self.assertEqual(catalog["save_target"], "standalone")
        self.assertFalse(catalog["parameters"]["resize"])

    def test_authenticated_connections_cannot_be_published(self):
        for build in (preview_catalog, preview_document):
            with (
                self.subTest(build=build.__name__),
                self.assertRaisesRegex(ValueError, "local session"),
            ):
                build(PRESETS["balanced"], connection={"token": "test-token"}, hosted=True)

    def test_identity_is_public_and_independent_of_user_and_session_state(self):
        expected = preview_catalog(PRESETS["balanced"])["studio"]
        self.assertEqual(set(expected), {"version", "build"})
        self.assertEqual(expected["version"], __version__)
        self.assertRegex(expected["build"], r"^[0-9a-f]{12}$")
        private = {
            "token": "private-session-token",
            "origin": "http://127.0.0.1:54321",
            "target": "native",
            "native": {"path": "/private/session/config.kdl"},
        }
        for effect, options in (
            (PRESETS["frost-vanish"], {"hosted": True}),
            (Effect(spin=211), {"name": "My private draft"}),
            (
                Profile(open="off", swap=PRESETS["pixel-relay"]),
                {
                    "name": "My private combo",
                    "connection": private,
                    "preferences": {"favorites": ["custom-private-favorite"]},
                },
            ),
        ):
            with self.subTest(options=options):
                identity = preview_catalog(effect, **options)["studio"]
                self.assertEqual(identity, expected)
                self.assertNotIn("private", json.dumps(identity))

    def test_identity_changes_with_packaged_assets(self):
        expected = preview_catalog(PRESETS["balanced"])["studio"]
        original = files("niri_fx")
        with tempfile.TemporaryDirectory() as directory:
            stylesheet = Path(directory) / "studio.css"
            stylesheet.write_bytes(
                original.joinpath("studio.css").read_bytes() + b"\n/* changed */"
            )
            resources = Mock()
            resources.joinpath.side_effect = lambda name: (
                stylesheet if name == "studio.css" else original.joinpath(name)
            )
            with patch("niri_fx.preview.files", return_value=resources):
                changed = preview_catalog(PRESETS["balanced"])["studio"]
        self.assertEqual(changed["version"], expected["version"])
        self.assertNotEqual(changed["build"], expected["build"])

    def test_identity_changes_with_builtin_catalog(self):
        expected = preview_catalog(PRESETS["balanced"])["studio"]
        with patch("niri_fx.preview.RECOMMENDED", ["frost-vanish"]):
            changed = preview_catalog(PRESETS["balanced"])["studio"]
        self.assertNotEqual(changed["build"], expected["build"])

    def test_about_explains_each_mode_without_conflating_compositor_identity(self):
        for options, explanation in (
            ({"hosted": True}, "Reload this page after a site update."),
            ({"connection": {"target": "inir"}}, "Close and reopen Studio"),
            ({}, "Generate a new HTML file"),
        ):
            with self.subTest(options=options):
                html = preview_document(PRESETS["balanced"], **options)
                self.assertIn(explanation, html)
                self.assertIn("Compositor identity and support are separate.", html)
                self.assertIn(f"Studio {__version__} · UI build", html)
                self.assertNotIn("@STUDIO_", html)
