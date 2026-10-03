"""Old import paths must remain aliases, not independent copies of the code."""

import importlib
import unittest
from unittest.mock import patch


class CompatibilityTests(unittest.TestCase):
    def test_legacy_modules_share_canonical_implementation(self):
        for name in ("effects", "cli", "integration", "setup", "studio", "pack"):
            with self.subTest(module=name):
                self.assertIs(
                    importlib.import_module(f"niri_fragments.{name}"),
                    importlib.import_module(f"niri_fx.{name}"),
                )
        import niri_fragments
        import niri_fx

        self.assertEqual(niri_fragments.__version__, niri_fx.__version__)

    def test_legacy_patches_reach_the_canonical_module(self):
        from niri_fx import studio

        with patch("niri_fragments.studio.read_shell_presets") as helper:
            self.assertIs(studio.read_shell_presets, helper)
