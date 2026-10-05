"""Reviewed CLI live changes use retained transactions and synthetic IPC only."""

import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

import test_native_live

from niri_fx import native_live, native_runtime, native_session
from niri_fx.cli import main
from niri_fx.documents import effect_document
from niri_fx.profiles import Profile


class NativeLiveCliTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_native_live.NativeLiveTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root, self.base, self.socket = (
            self.fixture.root,
            self.fixture.base,
            self.fixture.socket,
        )
        self.document = self.root.parent / "cli-combo.json"
        self.document.write_text(json.dumps(effect_document("CLI combo", Profile(close="off"))))
        self.configure = [
            "native",
            "configure",
            self.base,
            "--root",
            str(self.root),
            "--document",
            str(self.document),
        ]
        self.rollback = ["native", "rollback", "--root", str(self.root)]
        environment = patch.dict(os.environ, {"NIRI_SOCKET": self.socket})
        environment.start()
        self.addCleanup(environment.stop)

    def command(self, arguments, *, expected=0):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            self.assertEqual(main(arguments), expected, errors.getvalue())
        if expected == 2:
            self.assertEqual(output.getvalue(), "")
            return errors.getvalue()
        self.assertEqual(errors.getvalue(), "")
        return json.loads(output.getvalue())

    def snapshot(self):
        return {
            str(path.relative_to(self.root)): path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }

    def apply(self, arguments, review, *, expected=0):
        return self.command(
            [*arguments, "--apply", "--expect-plan", review["plan_sha256"]], expected=expected
        )

    def test_review_then_apply_confirms_live_reload_and_retains_next_login(self):
        with test_native_live.ipc(self.socket) as requests:
            before = self.snapshot()
            args = [*self.configure, "--live"]
            review = self.command(args)
            self.assertEqual(before, self.snapshot())
            self.assertTrue(review["dry_run"])
            self.assertEqual(review["activation"], "live-and-next-login")
            self.assertEqual(review["native_live"]["socket"], self.socket)
            notes = " ".join(review["notes"])
            self.assertIn("Global animations off or slowdown", notes)
            self.assertIn("must support bundle schema 3", notes)
            self.assertNotIn("running desktop remain unchanged", notes)
            self.assertEqual(self.fixture.actions(requests), [])
            applied = self.apply(args, review)
        target = review["selection"]["selected"]
        self.assertFalse(applied["dry_run"])
        self.assertEqual(applied["activation"], "live-and-next-login")
        self.assertEqual(applied["live"]["status"], "applied")
        self.assertNotIn("restore", applied)
        self.assertEqual(native_session.load_selection(self.root)["selected"], target)
        self.assertEqual(self.fixture.read_receipt()["loaded_bundle"], target)
        self.assertEqual(len(self.fixture.actions(requests)), 1)

    def test_without_flag_keeps_next_login_behavior_and_never_probes_live(self):
        with patch.object(native_live, "context", side_effect=AssertionError("Unexpected probe")):
            review = self.command(self.configure)
            applied = self.apply(self.configure, review)
        self.assertEqual(review["activation"], "next-login")
        self.assertEqual(applied["activation"], "next-login")
        self.assertNotIn("live", applied)
        self.assertIn("running session is unchanged", applied["next_step"])
        self.assertFalse((self.root / native_live.RECEIPT).exists())

    def test_explicit_live_refuses_offline_before_creating_or_selecting_a_bundle(self):
        before = self.snapshot()
        with patch.dict(os.environ, {"NIRI_SOCKET": ""}):
            for flags in ([], ["--apply", "--expect-plan", "0" * 64]):
                error = self.command([*self.configure, "--live", *flags], expected=2)
                self.assertIn("Live Apply is unavailable", error)
                self.assertEqual(before, self.snapshot())

    def test_live_apply_requires_fingerprint_before_session_probe_or_writes(self):
        before = self.snapshot()
        with patch.object(native_live, "context", side_effect=AssertionError("Unexpected probe")):
            for args in (self.configure, self.rollback):
                error = self.command([*args, "--live", "--apply"], expected=2)
                self.assertIn("requires --expect-plan from a live review", error)
        self.assertEqual(before, self.snapshot())

    def test_next_login_review_cannot_authorize_live_apply(self):
        review = self.command(self.configure)
        before = self.snapshot()
        with test_native_live.ipc(self.socket) as requests:
            error = self.apply([*self.configure, "--live"], review, expected=2)
        self.assertIn("changed", error)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.fixture.actions(requests), [])

    def test_changed_session_invalidates_review_before_staging(self):
        before = self.snapshot()
        with test_native_live.ipc(self.socket) as requests:
            args = [*self.configure, "--live"]
            review = self.command(args)
            with patch.object(native_runtime, "_process_start", return_value=124):
                error = self.apply(args, review, expected=2)
        self.assertIn("changed", error)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.fixture.actions(requests), [])

    def test_live_rollback_uses_previous_retained_selection(self):
        previous = native_session.load_selection(self.root)["selected"]
        with test_native_live.ipc(self.socket) as first_requests:
            args = [*self.configure, "--live"]
            self.apply(args, self.command(args))
        # Each synthetic server owns one event stream. Reopen the same endpoint
        # with the same peer process to exercise the saved reload receipt.
        os.unlink(self.socket)
        with test_native_live.ipc(self.socket) as rollback_requests:
            rollback = [*self.rollback, "--live"]
            review = self.command(rollback)
            self.assertEqual(review["selection"]["selected"], previous)
            self.assertNotIn("running sessions are unchanged", " ".join(review["notes"]))
            applied = self.apply(rollback, review)
        self.assertEqual(applied["live"]["status"], "applied")
        self.assertEqual(native_session.load_selection(self.root)["selected"], previous)
        self.assertEqual(self.fixture.read_receipt()["loaded_bundle"], previous)
        self.assertEqual(len(self.fixture.actions(first_requests + rollback_requests)), 2)

    def test_empty_live_rollback_target_refuses_without_changing_selection(self):
        self.assertIsNone(native_session.load_selection(self.root)["previous"])
        before = self.snapshot()
        error = self.command([*self.rollback, "--live"], expected=2)
        self.assertIn("no live rollback target", error)
        self.assertEqual(before, self.snapshot())

    def test_rejected_reload_returns_json_and_nonzero_with_selection_retained(self):
        with test_native_live.ipc(self.socket, failed=True):
            args = [*self.configure, "--live"]
            review = self.command(args)
            result = self.apply(args, review, expected=1)
        self.assertEqual(result["activation"], "next-login")
        self.assertEqual(result["live"]["status"], "failed")
        self.assertIn("rejected", result["next_step"])
        self.assertEqual(
            native_session.load_selection(self.root)["selected"], review["selection"]["selected"]
        )

    def test_unconfirmed_reload_is_not_reported_as_success(self):
        with (
            test_native_live.ipc(self.socket, timeout=True),
            patch.object(native_live, "RELOAD_TIMEOUT", 0.1),
        ):
            args = [*self.configure, "--live"]
            result = self.apply(args, self.command(args), expected=1)
        self.assertEqual(result["activation"], "next-login")
        self.assertEqual(result["live"]["status"], "unconfirmed")
        self.assertIn("could not be confirmed", result["next_step"])


if __name__ == "__main__":
    unittest.main()
