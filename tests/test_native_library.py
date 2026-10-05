"""Managed Studio shares immutable transactions and never writes the live config."""

import json
import os
import unittest
from threading import Thread
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

import test_native_session as fixtures

from niri_fx import native_customization, native_session, setup
from niri_fx.cli import main, parser
from niri_fx.documents import effect_document
from niri_fx.fragment_motion import PRESETS
from niri_fx.library import Library, studio_target
from niri_fx.profiles import Profile
from niri_fx.studio import make_server


def snapshot(root):
    return {
        path.relative_to(root).as_posix(): (path.read_bytes(), path.stat().st_mode)
        for path in root.rglob("*")
        if path.is_file()
    }


class NativeLibraryFixture(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.NativeSessionTests()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.root = self.fixture.root
        self.native = self.fixture.destination
        self.base = self.fixture.stage()
        self.fixture.apply_selection(native_session.select_plan(self.native, self.base))
        self.args = SimpleNamespace(
            target="native",
            native_root=self.native,
            native_base=None,
            config=self.fixture.config,
            state=self.root / "library",
            registry=self.root / "registry.json",
            inir_root=self.root / "shell",
            base="auto",
            port=0,
            preset="balanced",
        )
        environment = patch.dict(os.environ, {"NIRI_SOCKET": ""})
        environment.start()
        self.addCleanup(environment.stop)
        self.library = Library(self.args, "native")
        self.document = effect_document(
            "Managed Tear", Profile(close="off", movement=PRESETS["tear"].effect)
        )
        self.selection = {"document": self.document, "fragment_preset": "tear"}

    def apply(self, selection=None):
        selection = selection or self.selection
        review = self.library.review(selection)
        result = self.library.apply({"selection": selection, "expected": review["plan_sha256"]})
        return result


class NativeLibraryTests(NativeLibraryFixture):
    def test_explicit_cli_choices_are_not_replaced_by_the_saved_recipe(self):
        for choice in (
            [],
            ["--preset", "balanced"],
            ["--profile", "fragments-motion"],
            ["--spin", "50"],
        ):
            with self.subTest(choice=choice), patch("niri_fx.studio.serve") as serve:
                self.assertEqual(
                    main(
                        ["studio", "--target", "native", "--native-root", str(self.native), *choice]
                    ),
                    0,
                )
                self.assertEqual(serve.call_args.args[0].native_document, bool(choice))

    def test_launch_root_defaults_to_shared_native_storage_and_captures_exact_base(self):
        parsed = parser().parse_args(
            [
                "studio",
                "--target",
                "native",
                "--native-root",
                str(self.native),
                "--native-base",
                self.base,
            ]
        )
        self.assertEqual(studio_target(parsed), "native")
        self.assertEqual(parsed.native_base, self.base)
        with patch.object(native_session, "default_root", return_value=self.native):
            default = Library(
                SimpleNamespace(**(vars(self.args) | {"native_root": None})), "native"
            )
        self.assertEqual(default.native_root, self.native)
        with self.assertRaisesRegex(ValueError, "require --target native"):
            studio_target(SimpleNamespace(target="standalone", native_root=self.native))
        self.apply()
        self.assertEqual(self.library.native_base["bundle_id"], self.base)
        reopened = Library(self.args, "native")
        self.assertNotEqual(reopened.native_base["bundle_id"], self.base)

    def test_review_listing_and_save_do_not_select_then_apply_keeps_base(self):
        before = snapshot(self.root)
        listing = self.library.listing()
        self.assertEqual(listing["native"]["running"]["status"], "offline")
        self.assertFalse(listing["native"]["reopen"])
        reviewed = self.library.review(self.selection)
        self.assertEqual(snapshot(self.root), before)
        self.library.store({"document": self.document, "expected": None})
        self.assertEqual(native_session.load_selection(self.native)["selected"], self.base)
        result = self.library.apply(
            {"selection": self.selection, "expected": reviewed["plan_sha256"]}
        )
        self.assertTrue(result["changed"])
        self.assertNotIn("restore", result)
        for name, value in before.items():
            if not name.endswith("/selection.json"):
                self.assertEqual(snapshot(self.root)[name], value)
        current = native_session.load_selection(self.native)
        self.assertEqual(current["previous"], self.base)
        self.assertNotEqual(current["selected"], self.base)
        listing = self.library.listing()
        self.assertEqual(listing["active"], self.document)
        self.assertTrue(listing["native"]["reopen"])
        self.assertEqual(listing["native"]["recipe"]["fragment_preset"], "tear")
        roles = {row["bundle_id"]: row["roles"] for row in listing["native"]["bundles"]}
        self.assertEqual(roles[self.base], ["rollback"])
        self.assertEqual(roles[current["selected"]], ["next-login"])

    def test_stale_selector_invalidates_apply_without_partial_bundle(self):
        reviewed = self.library.review(self.selection)
        self.fixture.apply_selection(native_session.rollback_plan(self.native))
        before = snapshot(self.root)
        with self.assertRaisesRegex(ValueError, "plan changed"):
            self.library.apply({"selection": self.selection, "expected": reviewed["plan_sha256"]})
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(self.library.native_base["bundle_id"], self.base)

    def test_reviewed_rollback_is_bound_to_current_selection(self):
        self.apply()
        before = snapshot(self.root)
        reviewed = self.library.rollback_review({})
        self.assertEqual(snapshot(self.root), before)
        with self.assertRaisesRegex(ValueError, "Review rollback"):
            self.library.undo()
        self.library.rollback_apply({"expected": reviewed["plan_sha256"]})
        self.assertEqual(native_session.load_selection(self.native)["selected"], self.base)
        retained = snapshot(self.native / "bundles")
        with self.assertRaisesRegex(ValueError, "plan changed"):
            self.library.rollback_apply({"expected": reviewed["plan_sha256"]})
        self.assertEqual(snapshot(self.native / "bundles"), retained)

    def test_native_requests_reject_paths_commands_and_implicit_fragment_replacement(self):
        before = snapshot(self.root)
        for field in (
            "root",
            "base_bundle",
            "binary",
            "config",
            "shader",
            "command",
            "allow_movement",
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.library.review(self.selection | {field: "unexpected"})
        for value in ("../tear", {}, False):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.library.review(self.selection | {"fragment_preset": value})
        with self.assertRaises(ValueError):
            self.library.review(
                {"document": effect_document("Preserve", Profile()), "fragment_preset": "tear"}
            )
        for request in ({"bundle": self.base}, {"root": "/ignored"}):
            with self.assertRaises(ValueError):
                self.library.rollback_review(request)
            with self.assertRaises(ValueError):
                self.library.rollback_apply(request)
        self.assertEqual(snapshot(self.root), before)

    def test_reopen_replaces_the_recipe_against_its_original_baseline(self):
        self.apply()
        library = Library(self.args, "native")
        self.assertEqual(library.native_base["customization"]["document"], self.document)
        document = effect_document("Preserve baseline", Profile())
        selection = {"document": document}
        reviewed = library.review(selection)
        library.apply({"selection": selection, "expected": reviewed["plan_sha256"]})
        report = library.listing()
        self.assertTrue(report["native"]["reopen"])
        self.assertEqual(report["native"]["baseline_bundle"], self.base)
        self.assertEqual(report["active"], document)

    def test_selected_recipe_from_another_baseline_requires_relaunch(self):
        self.fixture.config.write_text("animations { slowdown 1.5; }\n")
        other = self.fixture.stage()
        plan = native_customization.configure_plan(
            self.native, other, self.document, fragment_preset="tear"
        )
        native_customization.apply_native(plan, self.native, expected=setup.plan_fingerprint(plan))
        listing = self.library.listing()
        self.assertIsNotNone(listing["active"])
        self.assertFalse(listing["native"]["reopen"])


class NativeStudioHTTPTests(NativeLibraryFixture):
    def setUp(self):
        super().setUp()
        probe = patch(
            "niri_fx.studio.pointer_capability", side_effect=AssertionError("No live probe")
        )
        self.pointer_probe = probe.start()
        self.addCleanup(probe.stop)
        self.server = make_server(self.args, PRESETS["tear"].effect)
        thread = Thread(target=self.server.serve_forever, daemon=True)
        thread.start()

        def close():
            self.server.shutdown()
            self.server.server_close()
            thread.join(timeout=2)

        self.addCleanup(close)
        self.token = parse_qs(urlsplit(self.server.session_url).query)["token"][0]

    def post(self, route, value, **overrides):
        headers = {
            "Origin": self.server.origin,
            "Content-Type": "application/json",
            "X-NiriFX-Token": self.token,
        } | overrides
        request = Request(
            self.server.origin + route, json.dumps(value).encode(), headers, method="POST"
        )
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_page_defaults_to_preserve_and_never_probes_default_binary(self):
        before = snapshot(self.root)
        with urlopen(self.server.session_url, timeout=5) as response:
            html = response.read().decode()
        self.assertIn('"target": "native"', html)
        self.assertIn(
            '"actions": {"open": null, "close": null, "resize": null, "movement": null}', html
        )
        self.assertIn('"fragment_choices"', html)
        self.pointer_probe.assert_not_called()
        self.assertEqual(snapshot(self.root), before)

    def test_native_mutations_require_authorization_and_reviewed_rollback(self):
        before = snapshot(self.root)
        for route in (
            "/review",
            "/apply",
            "/restore",
            "/rollback-review",
            "/rollback-apply",
            "/save",
        ):
            with self.subTest(route=route), self.assertRaises(HTTPError) as caught:
                self.post(route, {}, Origin="https://unrelated.example")
            self.assertEqual(caught.exception.code, 403)
            caught.exception.close()
        for route in ("/restore", "/save"):
            with self.subTest(route=route), self.assertRaises(HTTPError) as caught:
                self.post(route, {})
            self.assertEqual(caught.exception.code, 400)
            caught.exception.close()
        self.assertEqual(snapshot(self.root), before)
        review = self.post("/review", self.selection)
        self.assertEqual(snapshot(self.root), before)
        self.post("/apply", {"selection": self.selection, "expected": review["plan_sha256"]})
        after = snapshot(self.root)
        rollback = self.post("/rollback-review", {})
        self.assertEqual(snapshot(self.root), after)
        self.post("/rollback-apply", {"expected": rollback["plan_sha256"]})
        self.assertEqual(native_session.load_selection(self.native)["selected"], self.base)
