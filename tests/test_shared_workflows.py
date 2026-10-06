"""Shared settings cross CLI, Studio and recovery without using the desktop."""

import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from threading import Thread
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

import test_native_shared
from test_native_library import snapshot

from niri_fx import native_customization, native_session, setup
from niri_fx.cli import main, parser
from niri_fx.documents import effect_document
from niri_fx.library import Library, studio_target
from niri_fx.model import Effect
from niri_fx.profiles import Profile
from niri_fx.studio import make_server


class SharedWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_native_shared.NativeSharedTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.args = parser().parse_args(
            [
                "studio",
                "--target",
                "native",
                "--native-root",
                str(self.root),
                "--shared-config",
                str(self.fixture.config),
                "--stock-binary",
                str(self.fixture.stock),
                "--state",
                str(self.root.parent / "library"),
                "--port",
                "0",
                "--no-browser",
            ]
        )
        environment = patch.dict(os.environ, {"NIRI_SOCKET": ""})
        environment.start()
        self.addCleanup(environment.stop)
        self.library = Library(self.args, "native")

    def adopt(self):
        review = self.library.shared_review({})
        return self.library.shared_apply({"expected": review["plan_sha256"]})

    def cli(self, *arguments):
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error):
            code = main(["native", *arguments, "--root", str(self.root)])
        return code, json.loads(output.getvalue()) if output.getvalue() else None, error.getvalue()

    def test_adoption_uses_latest_saved_recipe_and_requires_editor_reopen(self):
        draft = self.root.parent / "library/profiles/draft.json"
        draft.parent.mkdir(parents=True)
        draft.write_text('{"example": "untouched"}')
        document = effect_document("Latest saved", Profile(close="off", resize="off"))
        plan = native_customization.configure_plan(self.root, self.fixture.base, document)
        native_customization.apply_native(plan, self.root, expected=setup.plan_fingerprint(plan))
        before = snapshot(self.root.parent)
        review = self.library.shared_review({})
        self.assertEqual(snapshot(self.root.parent), before)
        result = self.library.shared_apply({"expected": review["plan_sha256"]})
        self.assertEqual(result["activation"], "config-written")
        self.assertEqual(result["live"]["status"], "unverified")
        self.assertEqual(draft.read_text(), '{"example": "untouched"}')
        listing = self.library.listing()
        self.assertFalse(listing["native"]["shared"])
        self.assertTrue(listing["native"]["shared_state"]["selected"])
        self.assertEqual(listing["active"], document)
        with self.assertRaisesRegex(ValueError, "reopen Studio"):
            self.library.review({"document": document})
        fresh = Library(self.args, "native")
        self.assertTrue(fresh.listing()["native"]["shared"])
        updated = {"document": effect_document("Preserve", Profile())}
        reviewed = fresh.review(updated)
        result = fresh.apply({"selection": updated, "expected": reviewed["plan_sha256"]})
        self.assertEqual(result["live"]["status"], "unverified")

    def test_source_change_invalidates_review_without_writing(self):
        reviewed = self.library.shared_review({})
        self.fixture.shell.write_text("animations { slowdown 1.1; }\n")
        before = snapshot(self.root.parent)
        with self.assertRaisesRegex(ValueError, "plan changed"):
            self.library.shared_apply({"expected": reviewed["plan_sha256"]})
        self.assertEqual(snapshot(self.root.parent), before)

    def test_adoption_blocks_standalone_review_stale_apply_and_old_restore(self):
        args = parser().parse_args(
            [
                "setup",
                "--target",
                "standalone",
                "--no-launcher",
                "--config",
                str(self.fixture.config),
            ]
        )
        profile = Profile(open=Effect(), close="off")
        initial = setup.plan_setup(args, profile)
        state = self.root.parent / "standalone-state"
        result = setup.apply_plan(initial, state, setup.plan_fingerprint(initial))
        retained = setup.plan_setup(args, Profile(open=Effect(tile_size=32)))
        unchanged = setup.plan_setup(args, profile)
        stock = self.fixture.config.parent / "nirifx/animations.kdl"
        before = (self.fixture.config.read_bytes(), stock.read_bytes())
        self.adopt()
        self.assertEqual(before, (self.fixture.config.read_bytes(), stock.read_bytes()))
        adopted = snapshot(self.root.parent)
        for operation in (
            lambda: setup.plan_setup(args, profile),
            lambda: setup.apply_plan(retained, state, setup.plan_fingerprint(retained)),
            lambda: setup.apply_plan(unchanged, state, setup.plan_fingerprint(unchanged)),
            lambda: setup.restore(state, result["transaction"]),
            lambda: setup.restore(state, result["transaction"], apply=True),
        ):
            with self.assertRaisesRegex(ValueError, "shared NiriFX settings"):
                operation()
            self.assertEqual(snapshot(self.root.parent), adopted)
        manifest = state / result["transaction"] / "manifest.json"
        legacy = json.loads(manifest.read_text())
        legacy.pop("validation_config")
        legacy.pop("validation_binary")
        manifest.write_text(json.dumps(legacy))
        before = snapshot(self.root.parent)
        with self.assertRaisesRegex(ValueError, "shared NiriFX settings"):
            setup.restore(state, result["transaction"], apply=True)
        self.assertEqual(snapshot(self.root.parent), before)

    def test_unrecognized_shared_receipts_also_block_standalone_writers(self):
        args = parser().parse_args(
            [
                "setup",
                "--target",
                "standalone",
                "--no-launcher",
                "--config",
                str(self.fixture.config),
            ]
        )
        profile = Profile(open=Effect())
        plan = setup.plan_setup(args, profile)
        receipt = self.fixture.config.parent / "nirifx/shared.json"
        receipt.parent.mkdir()
        for symlink in (False, True):
            if symlink:
                receipt.symlink_to(receipt.with_name("missing.json"))
            else:
                receipt.write_text("not valid json")
            with self.assertRaisesRegex(ValueError, "shared NiriFX settings"):
                setup.plan_setup(args, profile)
            with self.assertRaisesRegex(ValueError, "shared NiriFX settings"):
                setup.apply_plan(plan, self.root.parent / "state", setup.plan_fingerprint(plan))
            receipt.unlink()
        self.assertFalse((self.root.parent / "state").exists())

    def test_recovery_survives_missing_source_and_leaves_it_missing(self):
        self.adopt()
        fresh = Library(self.args, "native")
        self.fixture.config.unlink()
        listing = fresh.listing()
        self.assertEqual(listing["native"]["shared_state"]["source_status"], "unavailable")
        review = fresh.recovery_review({})
        result = fresh.recovery_apply({"expected": review["plan_sha256"]})
        self.assertEqual(result["activation"], "next-login")
        self.assertFalse(self.fixture.config.exists())
        selected = native_session.load_selection(self.root)["selected"]
        self.assertNotIn("shared", native_session.inspect_bundle(self.root, selected))
        with self.assertRaisesRegex(ValueError, "reopen Studio"):
            fresh.review({"document": effect_document("Preserve", Profile())})

    def test_stock_session_routes_adopted_source_to_same_recipe(self):
        self.adopt()
        args = parser().parse_args(["studio", "--config", str(self.fixture.config)])
        args.inir_root = self.root.parent / "fake-shell"
        (args.inir_root / "scripts").mkdir(parents=True)
        (args.inir_root / "scripts/niri-config.py").write_text("# synthetic helper\n")
        with patch.object(native_session, "default_root", return_value=self.root):
            self.assertEqual(studio_target(args), "native")
            args.config = self.root.parent / "another-config.kdl"
            self.assertNotEqual(studio_target(args), "native")

    def test_cli_sharing_and_shared_selection_require_exact_review(self):
        command = [
            "share",
            self.fixture.base,
            "--config",
            str(self.fixture.config),
            "--stock-binary",
            str(self.fixture.stock),
        ]
        code, review, _ = self.cli(*command)
        self.assertEqual(code, 0)
        before = snapshot(self.root.parent)
        code, _, error = self.cli(*command, "--apply")
        self.assertEqual(code, 2)
        self.assertIn("--expect-plan", error)
        self.assertEqual(snapshot(self.root.parent), before)
        code, result, _ = self.cli(*command, "--apply", "--expect-plan", review["plan_sha256"])
        self.assertEqual(code, 0)
        self.assertEqual(result["activation"], "config-written")
        self.assertIn("not independently confirmed", result["next_step"])
        selected = native_session.load_selection(self.root)["selected"]
        code, _, error = self.cli("select", selected, "--apply")
        self.assertEqual(code, 2)
        self.assertIn("review", error.lower())
        code, _, error = self.cli("configure", selected, "--preset", "balanced", "--live")
        self.assertEqual(code, 2)
        self.assertIn("shared", error.lower())

    def test_http_sharing_and_recovery_use_authorized_path_free_requests(self):
        server = make_server(self.args, Effect())
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()

        def close():
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.addCleanup(close)
        token = parse_qs(urlsplit(server.session_url).query)["token"][0]

        def post(route, value, **overrides):
            headers = {
                "Origin": server.origin,
                "Content-Type": "application/json",
                "X-NiriFX-Token": token,
            } | overrides
            request = Request(
                server.origin + route, json.dumps(value).encode(), headers, method="POST"
            )
            with urlopen(request, timeout=5) as response:
                return json.load(response)

        before = snapshot(self.root.parent)
        for route in ("/shared-review", "/shared-apply", "/recovery-review", "/recovery-apply"):
            for headers in ({"Origin": "https://example.invalid"}, {"X-NiriFX-Token": "wrong"}):
                with (
                    self.subTest(route=route, headers=headers),
                    self.assertRaises(HTTPError) as error,
                ):
                    post(route, {}, **headers)
                self.assertEqual(error.exception.code, 403)
                error.exception.close()
            with self.assertRaises(HTTPError) as error:
                post(route, {"config": "/client-chosen.kdl"})
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        self.assertEqual(snapshot(self.root.parent), before)
        review = post("/shared-review", {})
        result = post("/shared-apply", {"expected": review["plan_sha256"]})
        self.assertEqual(result["activation"], "config-written")
        self.fixture.config.unlink()
        review = post("/recovery-review", {})
        result = post("/recovery-apply", {"expected": review["plan_sha256"]})
        self.assertEqual(result["activation"], "next-login")
        self.assertFalse(self.fixture.config.exists())
