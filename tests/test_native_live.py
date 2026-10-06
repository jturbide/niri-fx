"""A synthetic IPC peer exercises live reloads without a desktop compositor."""

import json
import os
import socket
import struct
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import test_native_customization

from niri_fx import capabilities, native_build, native_live, native_runtime, native_session, setup
from niri_fx.profiles import Profile


@contextmanager
def ipc(path, *, failed=False, initial_failed=False, timeout=False, reply=None, initial=True):
    requests, streams, workers, errors = [], [], [], []
    stopped = threading.Event()

    def serve(client):
        try:
            with client, client.makefile("rb") as reader:
                while line := reader.readline():
                    request = json.loads(line)
                    requests.append(request)
                    if request == "Version":
                        client.sendall(b'{"Ok":{"Version":"synthetic NiriFX"}}\n')
                    elif request == "EventStream":
                        streams.append(client)
                        events = [{"Ok": "Handled"}, {"WindowsChanged": {"windows": []}}]
                        if initial:
                            events.append({"ConfigLoaded": {"failed": initial_failed}})
                        # Deliberately coalesce the acknowledgement and initial
                        # events, as an unbuffered single-reply reader loses them.
                        client.sendall(
                            b"".join(json.dumps(item).encode() + b"\n" for item in events)
                        )
                        stopped.wait(2)
                        return
                    elif isinstance(request, dict) and "Action" in request:
                        client.sendall(json.dumps(reply or {"Ok": "Handled"}).encode() + b"\n")
                        if not timeout:
                            for stream in streams:
                                stream.sendall(
                                    json.dumps({"ConfigLoaded": {"failed": failed}}).encode()
                                    + b"\n"
                                )
        except (OSError, ValueError) as error:
            if not stopped.is_set():
                errors.append(error)

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
        listener.bind(str(path))
        listener.listen(8)
        listener.settimeout(0.05)

        def accept():
            while not stopped.is_set():
                try:
                    client, _ = listener.accept()
                except TimeoutError:
                    continue
                worker = threading.Thread(target=serve, args=(client,), daemon=True)
                workers.append(worker)
                worker.start()

        acceptor = threading.Thread(target=accept, daemon=True)
        acceptor.start()
        try:
            yield requests
        finally:
            stopped.set()
            acceptor.join(2)
            for worker in workers:
                worker.join(2)
            if acceptor.is_alive() or any(worker.is_alive() for worker in workers) or errors:
                raise AssertionError(f"IPC fixture did not finish cleanly: {errors}")


class NativeLiveTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_native_customization.NativeCustomizationTests(methodName="runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.base = self.fixture.stage()
        self.startup = native_session.inspect_bundle(self.root, self.base)
        self.plan = self.fixture.plan(self.base, Profile(open="off"))
        self.fixture.apply(self.plan)
        self.target = self.plan["selection"]["bundle_id"]
        # Unix socket paths have a small platform bound, so use the shorter
        # parent fixture directory rather than the long content-addressed bundle.
        self.socket = str(self.root.parent / "ipc.sock")
        for owner, name, options in (
            (native_runtime, "_process_start", {"return_value": 123}),
            (
                native_runtime,
                "_executable",
                {
                    "side_effect": lambda pid: (
                        self.startup["binary"],
                        native_runtime._identity(self.startup["binary"]),
                    )
                },
            ),
            (
                native_runtime,
                "_arguments",
                {
                    "return_value": (
                        self.startup["binary"],
                        "--session",
                        "--config",
                        self.startup["config"],
                    )
                },
            ),
            *(
                (capabilities, name, {"return_value": {"activation_ready": True}})
                for name in (
                    "movement_capability",
                    "pointer_capability",
                    "fragment_capability",
                    "swap_capability",
                )
            ),
        ):
            mocker = patch.object(owner, name, **options)
            mocker.start()
            self.addCleanup(mocker.stop)

    def context(self, **kwargs):
        return native_live.context(self.root, self.base, socket_path=self.socket, **kwargs)

    def apply(self, identity):
        return native_live.apply(
            self.root,
            self.base,
            self.target,
            socket_path=self.socket,
            expected_identity=identity,
        )

    def read_receipt(self):
        return json.loads((self.root / native_live.RECEIPT).read_bytes())

    @staticmethod
    def actions(requests):
        return [item for item in requests if isinstance(item, dict) and "Action" in item]

    def test_offline_context_never_reads_environment_socket_or_creates_files(self):
        with (
            patch.dict(os.environ, {"NIRI_SOCKET": self.socket}),
            patch.object(socket, "socket", side_effect=AssertionError("must stay offline")),
        ):
            context = native_live.context(self.root, self.base)
        self.assertFalse(context["ready"])
        self.assertEqual(context["status"], "offline")
        self.assertFalse((self.root / native_live.RECEIPT).exists())

    def test_shared_review_and_result_never_promise_or_send_a_live_reload(self):
        plan = self.plan | {"shared": {"owner_id": "e" * 64}}
        with (
            patch.object(native_live, "context") as context,
            patch.object(native_live, "apply") as apply,
        ):
            reviewed = native_live.activation_plan(
                plan, self.root, self.base, socket_path=self.socket
            )
            result = native_live.activation_result(
                reviewed, {"applied": True}, self.root, self.base, socket_path=self.socket
            )
        context.assert_not_called()
        apply.assert_not_called()
        self.assertEqual(reviewed["activation"], "config-written")
        self.assertNotIn("native_live", reviewed)
        self.assertEqual(result["activation"], "config-written")
        self.assertEqual(result["live"]["status"], "unverified")
        self.assertIn("already using", result["live"]["detail"])
        self.assertIn("next login", result["live"]["detail"])
        self.assertFalse((self.root / native_live.RECEIPT).exists())
        with self.assertRaisesRegex(ValueError, "without --live"):
            native_live.activation_plan(plan, self.root, self.base, require_live=True)

    def test_shared_context_keeps_process_identity_separate_from_source_drift(self):
        original_inspect = native_session.inspect_bundle

        def shared_bundle(root, bundle_id):
            return original_inspect(root, bundle_id) | {"shared": {"owner_id": "e" * 64}}

        for status, projections_match in (
            ("current", True),
            ("changed", False),
            ("unavailable", False),
        ):
            self.socket = str(self.root.parent / f"ipc-{status}.sock")
            with (
                self.subTest(status=status),
                patch.object(native_session, "inspect_bundle", side_effect=shared_bundle),
                patch(
                    "niri_fx.native_shared.inspect_settings",
                    return_value={"status": status, "projections_match": projections_match},
                ),
                ipc(self.socket) as requests,
            ):
                context = self.context()
                self.assertFalse(context["ready"])
                self.assertEqual(context["status"], "shared-config")
                self.assertEqual(context["startup_bundle"], self.base)
                self.assertIsNone(context["effective_bundle"])
                self.assertIsNone(context["loaded_bundle"])
                self.assertEqual(context["shared_settings"]["status"], status)
                result = self.apply({})
                self.assertEqual(result["status"], "unavailable")
                self.assertEqual(self.actions(requests), [])
                self.assertFalse((self.root / native_live.RECEIPT).exists())

    def test_shared_source_inspection_cannot_hide_a_replaced_process(self):
        original_inspect = native_session.inspect_bundle

        def shared_bundle(root, bundle_id):
            return original_inspect(root, bundle_id) | {"shared": {"owner_id": "e" * 64}}

        def inspect_settings(_):
            native_runtime._process_start.return_value = 124
            return {"status": "current", "projections_match": True}

        with (
            patch.object(native_session, "inspect_bundle", side_effect=shared_bundle),
            patch("niri_fx.native_shared.inspect_settings", side_effect=inspect_settings),
            ipc(self.socket) as requests,
        ):
            context = self.context()
        self.assertFalse(context["ready"])
        self.assertEqual(context["status"], "unavailable")
        self.assertEqual(self.actions(requests), [])
        self.assertFalse((self.root / native_live.RECEIPT).exists())

    def test_frozen_recovery_from_shared_session_is_next_login_only(self):
        original_inspect = native_session.inspect_bundle

        def shared_startup(root, bundle_id):
            result = original_inspect(root, bundle_id)
            return result | {"shared": {"owner_id": "e" * 64}} if bundle_id == self.base else result

        with (
            patch.object(native_session, "inspect_bundle", side_effect=shared_startup),
            patch(
                "niri_fx.native_shared.inspect_settings",
                return_value={"status": "unavailable", "projections_match": False},
            ),
            ipc(self.socket) as requests,
        ):
            reviewed = native_live.activation_plan(
                self.plan, self.root, self.base, socket_path=self.socket
            )
            result = native_live.activation_result(
                reviewed, {"applied": True}, self.root, self.base, socket_path=self.socket
            )
        self.assertEqual(reviewed["activation"], "next-login")
        self.assertNotIn("native_live", reviewed)
        self.assertEqual(result["activation"], "next-login")
        self.assertNotIn("live", result)
        self.assertEqual(self.actions(requests), [])
        self.assertFalse((self.root / native_live.RECEIPT).exists())

    def test_shared_target_cannot_use_a_frozen_sessions_confirmed_reload_route(self):
        original_inspect = native_session.inspect_bundle

        def shared_target(root, bundle_id):
            result = original_inspect(root, bundle_id)
            return (
                result | {"shared": {"owner_id": "e" * 64}} if bundle_id == self.target else result
            )

        with ipc(self.socket) as requests:
            context = self.context()
            self.assertTrue(context["ready"])
            with patch.object(native_session, "inspect_bundle", side_effect=shared_target):
                result = self.apply(context["identity"])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(self.actions(requests), [])
        self.assertFalse((self.root / native_live.RECEIPT).exists())

    def test_context_probes_startup_executable_not_copied_target(self):
        with ipc(self.socket) as requests:
            before = {path: path.read_bytes() for path in self.root.rglob("*") if path.is_file()}
            context = self.context()
            self.assertEqual(before, {path: path.read_bytes() for path in before})
        self.assertTrue(context["ready"])
        self.assertEqual(context["startup_bundle"], self.base)
        self.assertEqual(context["effective_bundle"], self.base)
        self.assertIsNone(context["loaded_bundle"])
        self.assertEqual(context["identity"]["pid"], os.getpid())
        self.assertEqual(self.actions(requests), [])
        for probe in (
            capabilities.movement_capability,
            capabilities.pointer_capability,
            capabilities.fragment_capability,
            capabilities.swap_capability,
        ):
            probe.assert_called_once_with(self.startup["binary"], socket_path=self.socket)

    def test_load_confirmed_after_initial_event_records_target_and_keeps_startup(self):
        with ipc(self.socket, initial_failed=True) as requests:
            context = self.context()
            result = self.apply(context["identity"])
            later = self.context()
        self.assertEqual(result["status"], "applied")
        target = native_session.inspect_bundle(self.root, self.target)
        self.assertEqual(
            self.actions(requests), [{"Action": {"LoadConfigFile": {"path": target["config"]}}}]
        )
        self.assertEqual(later["startup_bundle"], self.base)
        self.assertEqual(later["loaded_bundle"], self.target)
        self.assertEqual(later["effective_bundle"], self.target)
        self.assertNotEqual(context["identity"], later["identity"])
        self.assertEqual(self.read_receipt()["status"], "applied")
        self.assertEqual((self.root / native_live.RECEIPT).stat().st_mode & 0o777, 0o600)

    def test_retained_three_patch_session_applies_without_probing_swap(self):
        fixture = self.fixture.fixture
        fixture.record.pop("swap_patch_sha256")
        block = fixture.record["native_build"]
        block["inputs"]["patches"].pop()
        block["build_id"] = native_build.fingerprint(block["inputs"])
        fixture.save_record()
        self.base = fixture.stage()
        self.startup = native_session.inspect_bundle(self.root, self.base)
        self.assertFalse(self.startup["swap_supported"])
        self.plan = self.fixture.plan(self.base, Profile(open="off"))
        self.fixture.apply(self.plan)
        self.target = self.plan["selection"]["bundle_id"]
        native_runtime._arguments.return_value = (
            self.startup["binary"],
            "--session",
            "--config",
            self.startup["config"],
        )
        with ipc(self.socket):
            before = self.context()
            self.assertTrue(before["ready"])
            result = self.apply(before["identity"])
            after = self.context()
        self.assertEqual(result["status"], "applied")
        self.assertTrue(after["ready"])
        self.assertEqual(after["loaded_bundle"], self.target)
        self.assertEqual(after["identity"]["pid"], before["identity"]["pid"])
        capabilities.swap_capability.assert_not_called()
        for probe in (
            capabilities.movement_capability,
            capabilities.pointer_capability,
            capabilities.fragment_capability,
        ):
            self.assertTrue(probe.called)

    def test_initial_success_is_not_a_confirmation(self):
        with (
            ipc(self.socket, timeout=True) as requests,
            patch.object(native_live, "RELOAD_TIMEOUT", 0.1),
        ):
            result = self.apply(self.context()["identity"])
            later = self.context()
        self.assertEqual(result["status"], "unconfirmed")
        self.assertEqual(len(self.actions(requests)), 1)
        self.assertFalse(later["ready"])
        self.assertIsNone(later["effective_bundle"])
        self.assertEqual(self.read_receipt()["status"], "unconfirmed")
        self.assertEqual(native_session.load_selection(self.root)["selected"], self.target)

    def test_failed_event_preserves_bundles_and_disables_live_readiness(self):
        with ipc(self.socket, failed=True):
            result = self.apply(self.context()["identity"])
            later = self.context()
        self.assertEqual(result["status"], "failed")
        self.assertFalse(later["ready"])
        self.assertIsNone(later["loaded_bundle"])
        self.assertEqual(self.read_receipt()["status"], "failed")
        self.assertTrue(Path(self.startup["binary"]).is_file())
        native_session.inspect_bundle(self.root, self.target)

    def test_missing_initial_event_sends_no_action(self):
        with (
            ipc(self.socket, initial=False) as requests,
            patch.object(native_live, "RELOAD_TIMEOUT", 0.1),
        ):
            result = self.apply(self.context()["identity"])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(self.actions(requests), [])
        self.assertFalse((self.root / native_live.RECEIPT).exists())

    def test_action_rejection_is_not_claimed_as_applied(self):
        with ipc(self.socket, reply={"Err": "synthetic refusal"}, timeout=True):
            result = self.apply(self.context()["identity"])
        self.assertEqual(result["status"], "failed")
        self.assertIsNone(self.read_receipt()["loaded_bundle"])

    def test_session_change_after_review_sends_no_action(self):
        with ipc(self.socket) as requests:
            identity = self.context()["identity"]
            with patch.object(native_runtime, "_process_start", return_value=124):
                result = self.apply(identity)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(self.actions(requests), [])

    def test_peer_rechecked_immediately_before_action(self):
        original = native_live._check_peer
        calls = 0

        def changed(connection, identity):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise ValueError("synthetic session replacement")
            original(connection, identity)

        with ipc(self.socket) as requests:
            identity = self.context()["identity"]
            with patch.object(native_live, "_check_peer", side_effect=changed):
                result = self.apply(identity)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(self.actions(requests), [])
        self.assertFalse((self.root / native_live.RECEIPT).exists())

    def test_changed_renderer_support_sends_no_action(self):
        with ipc(self.socket) as requests:
            identity = self.context()["identity"]
            with patch.object(
                capabilities, "fragment_capability", return_value={"activation_ready": False}
            ):
                result = self.apply(identity)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(self.actions(requests), [])

    def test_selection_change_sends_no_action(self):
        with ipc(self.socket) as requests:
            identity = self.context()["identity"]
            setup.apply_plan(
                native_session.select_plan(self.root, self.base),
                self.fixture.fixture.selection_state,
            )
            result = self.apply(identity)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(self.actions(requests), [])

    def test_stale_review_after_another_apply_sends_no_second_action(self):
        with ipc(self.socket) as requests:
            identity = self.context()["identity"]
            self.assertEqual(self.apply(identity)["status"], "applied")
            result = self.apply(identity)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(len(self.actions(requests)), 1)

    def test_different_baseline_cannot_be_loaded(self):
        self.fixture.fixture.config.write_text("layout {}\n")
        other = self.fixture.fixture.stage()
        setup.apply_plan(
            native_session.select_plan(self.root, other), self.fixture.fixture.selection_state
        )
        with ipc(self.socket) as requests:
            identity = self.context()["identity"]
            result = native_live.apply(
                self.root, self.base, other, socket_path=self.socket, expected_identity=identity
            )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(self.actions(requests), [])

    def test_missing_or_malformed_receipt_never_looks_confirmed(self):
        receipt = self.root / native_live.RECEIPT
        receipt.write_text('{"schema": 1}')
        receipt.chmod(0o600)
        with ipc(self.socket) as requests:
            context = self.context()
        self.assertFalse(context["ready"])
        self.assertIsNone(context["loaded_bundle"])
        self.assertEqual(self.actions(requests), [])

    def test_receipt_symlink_is_not_followed(self):
        unrelated = self.root / "unrelated.json"
        unrelated.write_bytes(b"do not change\n")
        (self.root / native_live.RECEIPT).symlink_to(unrelated)
        with ipc(self.socket):
            self.assertFalse(self.context()["ready"])
        self.assertEqual(unrelated.read_bytes(), b"do not change\n")

    def test_new_process_ignores_old_confirmation(self):
        with ipc(self.socket):
            self.assertEqual(self.apply(self.context()["identity"])["status"], "applied")
            with patch.object(native_runtime, "_process_start", return_value=124):
                later = self.context()
        self.assertTrue(later["ready"])
        self.assertIsNone(later["loaded_bundle"])
        self.assertEqual(later["effective_bundle"], self.base)

    def foreign_receipt(self):
        """Model a second managed compositor sharing the same retained root."""
        value = self.read_receipt()
        value["identity"]["pid"] = os.getpid() + 10000
        raw = native_session._json_bytes(value)
        (self.root / native_live.RECEIPT).write_bytes(raw)
        return value["identity"]["pid"], raw

    def test_another_live_process_receipt_is_preserved_and_blocks_apply(self):
        with ipc(self.socket) as requests:
            self.assertEqual(self.apply(self.context()["identity"])["status"], "applied")
            owner, raw = self.foreign_receipt()
            # The synthetic /proc helpers return the same executable and
            # arguments for both PIDs, as two real instances could have.
            context = self.context()
            result = self.apply(None)
        self.assertFalse(context["ready"])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(len(self.actions(requests)), 1)
        self.assertEqual((self.root / native_live.RECEIPT).read_bytes(), raw)
        self.assertNotEqual(owner, os.getpid())

    def test_unreadable_foreign_receipt_owner_does_not_release_ownership(self):
        original = native_live._process
        with ipc(self.socket) as requests:
            self.assertEqual(self.apply(self.context()["identity"])["status"], "applied")
            owner, raw = self.foreign_receipt()

            def inspect(pid):
                if pid == owner:
                    raise PermissionError("synthetic inaccessible process")
                return original(pid)

            with patch.object(native_live, "_process", side_effect=inspect):
                context = self.context()
                result = self.apply(None)
        self.assertFalse(context["ready"])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(len(self.actions(requests)), 1)
        self.assertEqual((self.root / native_live.RECEIPT).read_bytes(), raw)

    def test_exited_foreign_receipt_owner_allows_fresh_review_without_claiming_loaded(self):
        with ipc(self.socket):
            self.assertEqual(self.apply(self.context()["identity"])["status"], "applied")
            owner, raw = self.foreign_receipt()

            def started(pid):
                if pid == owner:
                    raise FileNotFoundError("synthetic exited process")
                return 123

            with patch.object(native_runtime, "_process_start", side_effect=started):
                context = self.context()
        self.assertTrue(context["ready"])
        self.assertIsNone(context["loaded_bundle"])
        self.assertEqual(context["effective_bundle"], self.base)
        self.assertEqual((self.root / native_live.RECEIPT).read_bytes(), raw)

    def test_startup_arguments_changed_to_external_config_stay_unavailable(self):
        other = self.root / "external.kdl"
        other.write_text("animations {}\n")
        with (
            ipc(self.socket) as requests,
            patch.object(
                native_runtime,
                "_arguments",
                return_value=(self.startup["binary"], "--config", str(other)),
            ),
        ):
            self.assertFalse(self.context()["ready"])
        self.assertEqual(self.actions(requests), [])

    def test_target_binary_tampering_cannot_be_activated(self):
        with ipc(self.socket) as requests:
            identity = self.context()["identity"]
            target = native_session.inspect_bundle(self.root, self.target)
            Path(target["binary"]).write_bytes(b"changed executable")
            result = self.apply(identity)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(self.actions(requests), [])

    def test_nonregular_selection_lock_cannot_block_or_dispatch(self):
        lock = self.root / "state/selection/.lock"
        lock.unlink()
        os.mkfifo(lock)
        with ipc(self.socket) as requests:
            result = self.apply(self.context()["identity"])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(self.actions(requests), [])

    def test_symlinked_selection_lock_is_not_followed(self):
        lock = self.root / "state/selection/.lock"
        unrelated = self.root / "unrelated-lock"
        unrelated.write_bytes(b"preserve\n")
        lock.unlink()
        lock.symlink_to(unrelated)
        with ipc(self.socket) as requests:
            result = self.apply(self.context()["identity"])
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(self.actions(requests), [])
        self.assertEqual(unrelated.read_bytes(), b"preserve\n")

    def test_pending_receipt_write_failure_sends_no_action(self):
        with ipc(self.socket) as requests:
            identity = self.context()["identity"]
            with patch.object(native_live, "atomic_write", side_effect=OSError("disk full")):
                result = self.apply(identity)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(self.actions(requests), [])
        self.assertEqual(native_session.load_selection(self.root)["selected"], self.target)

    def test_confirmation_receipt_write_failure_reports_uncertainty(self):
        original = native_live.atomic_write
        calls = 0

        def fail_after_pending(path, data):
            nonlocal calls
            calls += 1
            if calls > 1:
                raise OSError("disk full")
            return original(path, data)

        with ipc(self.socket) as requests:
            identity = self.context()["identity"]
            with patch.object(native_live, "atomic_write", side_effect=fail_after_pending):
                result = self.apply(identity)
            later = self.context()
        self.assertEqual(result["status"], "unconfirmed")
        self.assertEqual(len(self.actions(requests)), 1)
        self.assertEqual(self.read_receipt()["status"], "pending")
        self.assertFalse(later["ready"])

    def test_event_stream_rejects_malformed_config_loaded(self):
        from unittest.mock import Mock

        events = native_live._Events(Mock())
        events.buffer.extend(b'{"ConfigLoaded":{"failed":0}}\n')
        with self.assertRaisesRegex(ValueError, "Invalid ConfigLoaded"):
            events.config_loaded(0)

    def test_event_stream_bounds_unrelated_events(self):
        from unittest.mock import Mock

        events = native_live._Events(Mock())
        events.buffer.extend(b'{"unrelated":true}\n' * 4)
        with (
            patch.object(native_live, "MAX_EVENTS", 3),
            self.assertRaisesRegex(ValueError, "event limit"),
        ):
            events.config_loaded(0)

    def test_peer_credentials_reject_other_user(self):
        identity = {"pid": 111, "uid": os.geteuid()}
        from unittest.mock import Mock

        connection = Mock()
        connection.getsockopt.return_value = struct.pack("3i", 111, os.geteuid() + 1, 0)
        with self.assertRaisesRegex(ValueError, "IPC process changed"):
            native_live._check_peer(connection, identity)


if __name__ == "__main__":
    unittest.main()
