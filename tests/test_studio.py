import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

from helpers import shell_registry

from niri_fx.documents import effect_document
from niri_fx.effects import PRESETS
from niri_fx.profiles import Profile
from niri_fx.studio import make_server, valid_save_request


class RequestTests(unittest.TestCase):
    def test_foreign_origins_hosts_and_missing_tokens_rejected(self):
        origin, token = "http://127.0.0.1:12345", "session-token"
        good = {
            "Host": "127.0.0.1:12345",
            "Origin": origin,
            "Content-Type": "application/json",
            "X-NiriFX-Token": token,
        }
        self.assertTrue(valid_save_request(good, origin, token))
        for key, value in (
            ("Host", "attacker.example:12345"),
            ("Origin", "https://example.com"),
            ("Origin", "null"),
            ("Content-Type", "text/plain"),
            ("X-NiriFX-Token", ""),
            ("X-NiriFX-Token", "é"),
        ):
            with self.subTest(key=key, value=value):
                self.assertFalse(valid_save_request(dict(good, **{key: value}), origin, token))


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.registry = Path(self.directory.name) / "presets.json"
        config = Path(self.directory.name) / "niri/config.kdl"
        config.parent.mkdir()
        config.write_text("animations {}\n")
        args = Namespace(
            port=0,
            preset="earth",
            base="auto",
            registry=self.registry,
            inir_root="unused",
            config=config,
        )
        self.server = make_server(args, PRESETS["earth"])
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.token = parse_qs(urlsplit(self.server.session_url).query)["token"][0]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.directory.cleanup()

    def request(self, document, **overrides):
        headers = {
            "Content-Type": "application/json",
            "Origin": self.server.origin,
            "X-NiriFX-Token": self.token,
        }
        headers.update(overrides)
        return Request(
            self.server.origin + "/save", json.dumps(document).encode(), headers, method="POST"
        )

    def test_session_page_and_actual_named_preset_save(self):
        with urlopen(self.server.session_url, timeout=5) as response:
            html = response.read().decode()
            self.assertIn("NiriFX Studio", html)
            self.assertNotIn("@EFFECT_JSON@", html)
            self.assertIn('"save_target": "standalone"', html)
        with patch("niri_fx.studio.read_shell_presets", return_value=shell_registry()):
            document = {
                "schema": 3,
                "name": "My Meteor",
                "effect": {"gravity": "down", "particles": 500, "rotation": "random"},
            }
            with urlopen(self.request(document), timeout=5) as response:
                saved = json.load(response)
        self.assertEqual(saved["id"], "niri-fx-custom-my-meteor")
        registered = json.loads(self.registry.read_text())["presets"][0]
        self.assertEqual(registered["effect"]["particles"], 500)
        self.assertEqual(
            registered["types"]["workspace-switch"],
            shell_registry()["presets"][0]["types"]["workspace-switch"],
        )
        self.assertEqual(list(Path(self.directory.name).glob("*.kdl")), [])

    def test_cross_origin_save_and_parameter_injection_do_not_write(self):
        document = {"schema": 3, "name": "Test", "effect": {}}
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.request(document, Origin="https://example.com"), timeout=5)
        self.assertEqual(caught.exception.code, 403)
        caught.exception.close()
        self.assertFalse(self.registry.exists())
        document["effect"] = {"custom-shader": "not accepted"}
        with patch("niri_fx.studio.read_shell_presets", return_value=shell_registry()):
            with self.assertRaises(HTTPError) as caught:
                urlopen(self.request(document), timeout=5)
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()
        self.assertFalse(self.registry.exists())

    def test_favorites_are_persisted_and_reject_unknown_values(self):
        request = self.request({"favorites": ["iris-bloom", "balanced"]})
        request.full_url = self.server.origin + "/preferences"
        with urlopen(request, timeout=5) as response:
            self.assertTrue(json.load(response)["ok"])
        preferences = self.registry.parent / "studio-preferences.json"
        self.assertEqual(
            json.loads(preferences.read_text())["favorites"], ["balanced", "iris-bloom"]
        )
        with urlopen(self.server.session_url, timeout=5) as response:
            self.assertIn('"favorites": ["balanced", "iris-bloom"]', response.read().decode())
        original = preferences.read_bytes()
        request = self.request({"favorites": ["../../unowned"]})
        request.full_url = self.server.origin + "/preferences"
        with self.assertRaises(HTTPError) as caught:
            urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()
        self.assertEqual(preferences.read_bytes(), original)

    def test_slice_schema_three_is_saved_without_replacing_base_resize(self):
        document = {"schema": 3, "name": "Sliced", "effect": {"family": "slices", "slice_count": 9}}
        with patch("niri_fx.studio.read_shell_presets", return_value=shell_registry()):
            with urlopen(self.request(document), timeout=5) as response:
                saved = json.load(response)
        self.assertEqual(saved["id"], "niri-fx-custom-sliced")
        registered = json.loads(self.registry.read_text())["presets"][0]
        self.assertIn("slices_color", registered["types"]["window-close"]["custom-shader"])
        self.assertEqual(
            registered["types"]["window-resize"],
            shell_registry()["presets"][0]["types"]["window-resize"],
        )

    def test_library_review_apply_and_restore_use_the_same_portable_selection(self):
        config = Path(self.directory.name) / "niri/config.kdl"
        original = config.read_bytes()
        selection = {
            "document": effect_document(
                "Night Motion", Profile(PRESETS["zipper"], PRESETS["frost-vanish"])
            ),
            "allow_resize": False,
            "allow_movement": False,
        }

        def post(route, body):
            request = self.request(body)
            request.full_url = self.server.origin + route
            with urlopen(request, timeout=5) as response:
                return json.load(response)

        review = post("/review", selection)
        self.assertEqual(config.read_bytes(), original)
        with patch("niri_fx.setup.validate_config"):
            applied = post("/apply", {"selection": selection, "expected": review["plan_sha256"]})
        self.assertTrue(applied["changed"])
        self.assertIn("niri-fx managed", config.read_text())
        rendered = (config.parent / "nirifx/animations.kdl").read_text()
        self.assertNotIn("window-resize", rendered)
        post("/restore", {})
        self.assertEqual(config.read_bytes(), original)
        self.assertFalse((config.parent / "nirifx/animations.kdl").exists())

    def test_library_routes_require_the_session_and_reject_client_paths(self):
        listing = self.server.origin + "/library?token=" + self.token
        with urlopen(listing, timeout=5) as response:
            self.assertEqual(json.load(response)["customs"], {})
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.server.origin + "/library", timeout=5)
        self.assertEqual(caught.exception.code, 403)
        caught.exception.close()
        doc = {"schema": 3, "name": "Saved Online Look", "effect": {"family": "slices"}}
        for route in ("store", "review", "apply", "restore"):
            request = self.request(doc, Origin="https://example.com")
            request.full_url = self.server.origin + "/" + route
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=5)
            self.assertEqual(caught.exception.code, 403)
            caught.exception.close()
        request = self.request(doc)
        request.full_url = self.server.origin + "/store"
        with urlopen(request, timeout=5) as response:
            self.assertEqual(json.load(response)["name"], doc["name"])
        with urlopen(listing, timeout=5) as response:
            self.assertIn("custom-saved-online-look", json.load(response)["customs"])
        self.assertFalse(self.registry.exists())
        for route in ("review", "apply", "restore"):
            request = self.request({"path": "arbitrary", "command": "arbitrary"})
            request.full_url = self.server.origin + "/" + route
            with self.assertRaises(HTTPError) as caught:
                urlopen(request, timeout=5)
            self.assertEqual(caught.exception.code, 400)
            caught.exception.close()


if __name__ == "__main__":
    unittest.main()
