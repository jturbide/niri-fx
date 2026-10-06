"""Workflow coverage requires demonstrated profiles and their captured bytes."""

import hashlib
import importlib.util
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check-docs.py"
SPEC = importlib.util.spec_from_file_location("document_showcase_checks", SCRIPT)
checks = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checks)


class DocumentShowcaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.sources = {f"examples/profiles/{name}.json" for name in ("gentle", "custom")}
        for source in self.sources:
            path = self.root / source
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"kind":"profile","name":"Captured input"}\n')
        self.clip = {
            "file": "docs/gifs/workflow.gif",
            "document_sources": sorted(self.sources),
            "sources": {
                source: hashlib.sha256((self.root / source).read_bytes()).hexdigest()
                for source in self.sources
            },
            "capture": {"schema": 1, "preview_sha256": "a" * 64, "inputs_sha256": "b" * 64},
        }
        root = patch.object(checks, "ROOT", self.root)
        root.start()
        self.addCleanup(root.stop)

    def validate(self, clip):
        errors = []
        verified = checks.recorded_documents(clip, self.sources, errors)
        return verified, errors

    def test_only_explicit_demonstrations_count_and_legacy_metadata_is_unchanged(self):
        before = deepcopy(self.clip)
        self.assertEqual(self.validate(self.clip), (self.sources, []))
        self.assertEqual(self.clip, before)
        del self.clip["document_sources"]
        self.assertEqual(self.validate(self.clip), (set(), []))
        self.clip["source"] = next(iter(self.sources))
        self.assertEqual(self.validate(self.clip), (set(), []))

    def test_duplicate_and_malformed_declarations_cannot_claim_coverage(self):
        source = next(iter(self.sources))
        for documents in ([], source, None, [source, source], [source, {}], [source, True]):
            with self.subTest(documents=documents):
                verified, errors = self.validate({**self.clip, "document_sources": documents})
                self.assertFalse(verified)
                self.assertEqual(len(errors), 1)
        for source in ("../outside.json", "/tmp/outside.json", "examples/profiles/../unknown.json"):
            verified, errors = self.validate({**self.clip, "document_sources": [source]})
            self.assertFalse(verified)
            self.assertIn("valid profile example", errors[0])

    def test_missing_capture_and_unrecorded_or_stale_bytes_fail(self):
        for capture in (
            None,
            {},
            {**self.clip["capture"], "schema": True},
            {**self.clip["capture"], "schema": 2},
            {**self.clip["capture"], "inputs_sha256": "invalid"},
        ):
            with self.subTest(capture=capture):
                verified, errors = self.validate({**self.clip, "capture": capture})
                self.assertFalse(verified)
                self.assertIn("guarded capture provenance", errors[0])
        for recorded in (None, {}, {source: "c" * 64 for source in self.sources}):
            with self.subTest(recorded=recorded):
                verified, errors = self.validate({**self.clip, "sources": recorded})
                self.assertFalse(verified)
                self.assertTrue(errors)
        source = next(iter(self.sources))
        path = self.root / source
        path.write_text("changed after recording")
        verified, errors = self.validate(self.clip)
        self.assertNotIn(source, verified)
        self.assertIn("source missing or changed", errors[0])
        path.unlink()
        verified, errors = self.validate(self.clip)
        self.assertNotIn(source, verified)
        self.assertTrue(errors)

    def test_symlink_cannot_substitute_even_identical_recorded_bytes(self):
        source = next(iter(self.sources))
        path = self.root / source
        replacement = self.root / "replacement.json"
        path.rename(replacement)
        path.symlink_to(replacement)
        verified, errors = self.validate(self.clip)
        self.assertNotIn(source, verified)
        self.assertIn("source missing or changed", errors[0])


if __name__ == "__main__":
    unittest.main()
