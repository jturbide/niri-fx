"""Execute the versioned public examples without freezing internal representations."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import json_subset, stock_action_contract

from niri_fx.documents import effect_document, parse_document
from niri_fx.effects import render_kdl

ROOT = Path(__file__).resolve().parents[1]
CORPORA = [
    json.loads(path.read_text())
    for path in sorted((ROOT / "tests/fixtures/compatibility").glob("*/contract.json"))
]


class CompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not CORPORA:
            raise AssertionError("The versioned compatibility corpus is missing")

    def command(self, *arguments):
        return subprocess.run(
            [sys.executable, "-m", "niri_fx", *arguments],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )

    def test_accepted_documents_retain_meaning_and_stock_export_boundaries(self):
        for corpus in CORPORA:
            for case in corpus["accepted_documents"]:
                with self.subTest(baseline=corpus["baseline"], case=case["id"]):
                    name, _, effect = parse_document(case["document"])
                    normalized = effect_document(name, effect)
                    self.assertEqual(
                        json_subset(normalized, case["normalized"]), case["normalized"]
                    )
                    self.assertTrue(set(case["absent"]).isdisjoint(normalized))
                    self.assertEqual(
                        stock_action_contract(render_kdl(effect)), case["stock_actions"]
                    )

    def test_unsupported_documents_are_rejected_without_partial_normalization(self):
        for corpus in CORPORA:
            for case in corpus["rejected_documents"]:
                with self.subTest(baseline=corpus["baseline"], case=case["id"]):
                    with self.assertRaises(ValueError):
                        parse_document(case["document"])

    def test_cli_inspect_acceptance_and_error_categories(self):
        with tempfile.TemporaryDirectory(prefix="nirifx-compatibility-") as temporary:
            path = Path(temporary) / "document.json"
            for corpus in CORPORA:
                for category in ("accepted_documents", "rejected_documents"):
                    for case in corpus[category]:
                        with self.subTest(baseline=corpus["baseline"], case=case["id"]):
                            original = json.dumps(case["document"])
                            path.write_text(original)
                            result = self.command("inspect", "--custom", str(path))
                            self.assertEqual(path.read_text(), original)
                            if category == "accepted_documents":
                                self.assertEqual(result.returncode, 0, result.stderr)
                                actual = json.loads(result.stdout)
                                self.assertEqual(
                                    json_subset(actual, case["normalized"]), case["normalized"]
                                )
                                self.assertTrue(set(case["absent"]).isdisjoint(actual))
                            else:
                                self.assertEqual(result.returncode, 2)
                                self.assertEqual(result.stdout, "")
                                self.assertTrue(result.stderr.strip())

    def test_cli_json_examples_allow_additive_response_fields(self):
        for corpus in CORPORA:
            for case in corpus["cli_json"]:
                with self.subTest(baseline=corpus["baseline"], case=case["id"]):
                    result = self.command(*case["argv"])
                    self.assertEqual(result.returncode, 0, result.stderr)
                    actual = json.loads(result.stdout)
                    expected = json.loads(json.dumps(case["expected"]))
                    formats = expected.get("document_formats", {})
                    if "max_bytes" in formats:
                        # A larger import limit accepts the historical corpus;
                        # shrinking it would remove previously supported inputs.
                        limit = actual["document_formats"]["max_bytes"]
                        self.assertGreaterEqual(limit, formats["max_bytes"])
                        formats["max_bytes"] = limit
                    self.assertEqual(json_subset(actual, expected), expected)

    def test_representative_catalog_ids_resolve_to_their_documented_intent(self):
        result = self.command("list", "--documents")
        self.assertEqual(result.returncode, 0, result.stderr)
        documents = json.loads(result.stdout)
        for corpus in CORPORA:
            for identifier, expected in corpus["catalog_documents"].items():
                with self.subTest(baseline=corpus["baseline"], identifier=identifier):
                    self.assertEqual(json_subset(documents[identifier], expected), expected)
                    parse_document(documents[identifier])

    def test_cli_invalid_requests_have_no_success_output(self):
        for corpus in CORPORA:
            for case in corpus["cli_errors"]:
                with self.subTest(baseline=corpus["baseline"], case=case["id"]):
                    result = self.command(*case["argv"])
                    self.assertEqual(result.returncode, case["exit_status"])
                    self.assertEqual(result.stdout, "")
                    self.assertTrue(result.stderr.strip())
