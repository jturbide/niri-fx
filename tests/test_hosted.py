"""Hosted exports cannot accidentally inherit a local authenticated save session."""

import unittest

from niri_fx.effects import PRESETS
from niri_fx.preview import preview_catalog, preview_document


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
