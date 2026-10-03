import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from niri_fx.documents import MAX_DOCUMENT_BYTES, effect_document, load_document, parse_document


class DocumentTests(unittest.TestCase):
    def test_shared_python_browser_acceptance_cases(self):
        cases = json.loads((Path(__file__).parent / "fixtures/documents.json").read_text())
        for case in cases:
            with self.subTest(case=case["name"]):
                if case["valid"]:
                    name, _, effect = parse_document(case["document"])
                    self.assertEqual(parse_document(effect_document(name, effect))[2], effect)
                else:
                    with self.assertRaises(ValueError):
                        parse_document(case["document"])

    def test_document_limit_is_bytes_and_checks_before_decoding(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "style.json"
            valid = json.dumps({"schema": 3, "name": "Test", "effect": {}}).encode()
            path.write_bytes(valid + b" " * (MAX_DOCUMENT_BYTES - len(valid)))
            self.assertEqual(load_document(path)["name"], "Test")
            path.write_bytes(b"\xff" * (MAX_DOCUMENT_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "16 KiB"):
                load_document(path)

    def test_domain_imports_do_not_load_shell_or_http_layers(self):
        subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import niri_fx.documents, niri_fx.effects; "
                "assert not {'niri_fx.integration', 'niri_fx.setup', 'http.server'} & sys.modules.keys()",
            ],
            check=True,
        )
