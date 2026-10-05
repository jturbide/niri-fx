"""Partial rendering runs must be explicit and reject incomplete selections."""

import contextlib
import importlib.util
import io
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("studio_e2e", ROOT / "scripts/studio-e2e.py")
studio_e2e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(studio_e2e)


class BrowserOrchestrationTests(unittest.TestCase):
    def test_default_keeps_complete_local_and_release_coverage(self):
        args = studio_e2e.parse_args([])
        self.assertEqual(args.suite, "all")
        self.assertIsNone(args.shape_aspect)

    def test_shards_select_the_existing_full_aspect_set(self):
        for aspect in ("0.25", "1", "4"):
            args = studio_e2e.parse_args(["--suite", "shapes", "--shape-aspect", aspect])
            self.assertEqual((args.suite, args.shape_aspect), ("shapes", aspect))
        for suite in ("studio", "motion", "shapes"):
            self.assertEqual(studio_e2e.parse_args(["--suite", suite]).suite, suite)

    def test_invalid_or_incomplete_selections_fail_before_browser_startup(self):
        for arguments in (
            ["--suite", "unknown"],
            ["--shape-aspect", "1"],
            ["--suite", "studio", "--shape-aspect", "1"],
            ["--suite", "motion", "--shape-aspect", "1"],
            ["--suite", "shapes", "--shape-aspect", "0.5"],
        ):
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as rejected:
                    studio_e2e.parse_args(arguments)
                self.assertEqual(rejected.exception.code, 2)
