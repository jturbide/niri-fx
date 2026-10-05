"""An advertised IPC process is matched without execution or service changes."""

import hashlib
import json
import os
import socket
import struct
import subprocess
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from niri_fx import native_runtime


@contextmanager
def ipc(payload=b'{"Ok":{"Version":"niri test"}}\n'):
    with tempfile.TemporaryDirectory(prefix="native-ipc-") as directory:
        path = str(Path(directory) / "not-a-pid.sock")
        requests, errors = [], []
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(path)
            listener.listen(1)
            listener.settimeout(1)

            def serve():
                try:
                    with listener.accept()[0] as client:
                        client.settimeout(0.2)
                        request = client.recv(256)
                        if not request:
                            return
                        requests.append(request)
                        if payload is None:
                            client.recv(256)
                        else:
                            client.sendall(payload)
                except (BrokenPipeError, ConnectionResetError, TimeoutError):
                    pass
                except OSError as error:
                    errors.append(error)

            worker = threading.Thread(target=serve, daemon=True)
            worker.start()
            try:
                yield path, requests
            finally:
                worker.join(timeout=2)
                if worker.is_alive() or errors:
                    raise AssertionError(f"IPC fixture did not finish: {errors}")


class NativeRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="native runtime tests ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.binary = self.root / "bin/niri"
        self.binary.parent.mkdir()
        self.binary.write_bytes(b"synthetic binary, never execute")
        self.binary.chmod(0o755)
        self.config = self.root / "config.kdl"
        self.config.write_bytes(b"animations {}\n")
        self.bundle = {
            "bundle_id": "a" * 64,
            "binary": str(self.binary),
            "config": str(self.config),
            "binary_sha256": hashlib.sha256(self.binary.read_bytes()).hexdigest(),
            "config_sha256": hashlib.sha256(self.config.read_bytes()).hexdigest(),
        }
        for helper, options in (
            ("_process_start", {"return_value": 123}),
            (
                "_executable",
                {
                    "side_effect": lambda pid: (
                        str(self.binary),
                        native_runtime._identity(self.binary),
                    )
                },
            ),
            (
                "_arguments",
                {"return_value": (str(self.binary), "--session", "--config", str(self.config))},
            ),
        ):
            mocker = patch.object(native_runtime, helper, **options)
            mocker.start()
            self.addCleanup(mocker.stop)

    def inspect(self, bundles=None, payload=b'{"Ok":{"Version":"niri test"}}\n'):
        with ipc(payload) as (path, requests):
            result = native_runtime.inspect_running(
                [self.bundle] if bundles is None else bundles, socket_path=path
            )
        return result, requests

    def test_matching_session_uses_kernel_peer_and_recorded_pair_without_executing(self):
        with (
            patch.object(subprocess, "run", side_effect=AssertionError("must not execute")),
            patch.object(subprocess, "Popen", side_effect=AssertionError("must not execute")),
        ):
            result, requests = self.inspect()
        self.assertEqual(result["scope"], "advertised-ipc-session")
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["bundle_id"], self.bundle["bundle_id"])
        self.assertEqual(result["pid"], os.getpid())
        self.assertEqual(result["binary"], str(self.binary))
        self.assertEqual(result["config"], str(self.config))
        self.assertEqual(requests, [b'"Version"\n'])
        self.assertNotIn("socket", result)
        self.assertNotIn("token", result)
        self.assertNotIn("safe_to_delete", result)

    def test_no_explicit_socket_is_offline_even_when_environment_advertises_one(self):
        with (
            patch.dict(os.environ, {"NIRI_SOCKET": "/private/socket-token"}),
            patch.object(native_runtime.socket, "socket") as factory,
        ):
            report = native_runtime.inspect_running([self.bundle])
        factory.assert_not_called()
        self.assertEqual(report["status"], "offline")
        self.assertIsNone(report["pid"])

    def test_supported_config_argument_forms_are_equivalent(self):
        for arguments in (
            ("-c", str(self.config)),
            ("--config", str(self.config)),
            ("--config=" + str(self.config),),
            ("-c" + str(self.config),),
            ("-c=" + str(self.config),),
        ):
            with (
                self.subTest(arguments=arguments),
                patch.object(
                    native_runtime, "_arguments", return_value=(str(self.binary), *arguments)
                ),
            ):
                self.assertEqual(self.inspect()[0]["status"], "matched")

    def test_missing_relative_duplicated_and_ambiguous_arguments_remain_unknown(self):
        for arguments in (
            (),
            ("-c", "relative.kdl"),
            ("-c", str(self.config), "--config=" + str(self.config)),
            ("--config",),
            ("--config=",),
            ("--config-file", str(self.config)),
            ("--", "-c", str(self.config)),
        ):
            with (
                self.subTest(arguments=arguments),
                patch.object(
                    native_runtime, "_arguments", return_value=(str(self.binary), *arguments)
                ),
            ):
                self.assertEqual(self.inspect()[0]["status"], "unknown")

    def test_same_binary_with_different_absolute_config_is_external(self):
        other = self.root / "different.kdl"
        other.write_bytes(self.config.read_bytes())
        with patch.object(
            native_runtime, "_arguments", return_value=(str(self.binary), "-c", str(other))
        ):
            report, _ = self.inspect()
        self.assertEqual(report["status"], "external")
        self.assertIsNone(report["bundle_id"])
        self.assertEqual(report["config"], str(other))

    def test_existing_parent_traversal_in_bundle_root_does_not_hide_a_matching_config(self):
        directory = self.root / "directory"
        directory.mkdir()
        bundle = self.bundle | {
            "binary": str(directory / "../bin/niri"),
            "config": str(directory / "../config.kdl"),
        }
        for argument in (str(self.config), str(directory / "../config.kdl")):
            with (
                self.subTest(argument=argument),
                patch.object(
                    native_runtime, "_arguments", return_value=(str(self.binary), "-c", argument)
                ),
            ):
                report, _ = self.inspect([bundle])
                self.assertEqual(report["status"], "matched")
                self.assertEqual(report["config"], str(self.config))

    def test_external_executable_can_use_its_implicit_default_config(self):
        other = self.root / "stock-niri"
        other.write_bytes(b"another synthetic binary")
        with (
            patch.object(
                native_runtime,
                "_executable",
                return_value=(str(other), native_runtime._identity(other)),
            ),
            patch.object(native_runtime, "_arguments", return_value=(str(other), "--session")),
            patch.object(
                native_runtime,
                "_hash_stream",
                side_effect=AssertionError("unrelated binary must not be rehashed"),
            ),
        ):
            report, _ = self.inspect()
        self.assertEqual(report["status"], "external")
        self.assertNotIn("config", report)

    def test_ambiguous_duplicate_bundle_matches_are_not_arbitrarily_selected(self):
        report, _ = self.inspect([self.bundle, self.bundle | {"bundle_id": "b" * 64}])
        self.assertEqual(report["status"], "unknown")
        self.assertIsNone(report["bundle_id"])

    def test_changed_bundle_bytes_since_inventory_are_unknown(self):
        for path in (self.binary, self.config):
            original = path.read_bytes()
            with self.subTest(path=path.name):
                path.write_bytes(original + b"changed")
                report, _ = self.inspect()
                self.assertEqual(report["status"], "unknown")
                path.write_bytes(original)

    def test_deleted_or_symlinked_config_is_unknown(self):
        original = self.config.read_bytes()
        self.config.unlink()
        self.assertEqual(self.inspect()[0]["status"], "unknown")
        alternate = self.root / "alias.kdl"
        alternate.write_bytes(original)
        self.config.symlink_to(alternate)
        self.assertEqual(self.inspect()[0]["status"], "unknown")

    def test_process_reuse_or_argument_changes_during_inspection_are_unknown(self):
        cases = (
            ("_process_start", [123, 124]),
            ("_arguments", [(str(self.binary), "-c", str(self.config)), (str(self.binary),)]),
            (
                "_executable",
                [
                    (str(self.binary), native_runtime._identity(self.binary)),
                    ("/replaced/niri", (1, 2, 3, 4, 5, 6)),
                ],
            ),
        )
        for helper, values in cases:
            with (
                self.subTest(helper=helper),
                patch.object(native_runtime, helper, side_effect=values),
            ):
                self.assertEqual(self.inspect()[0]["status"], "unknown")

    def test_inaccessible_proc_is_unknown_without_querying_or_executing(self):
        with patch.object(native_runtime, "_process_start", side_effect=PermissionError()):
            report, requests = self.inspect()
        self.assertEqual(report["status"], "unknown")
        self.assertEqual(requests, [])

    def test_deleted_or_replaced_executable_is_unknown(self):
        for error in (ValueError("deleted"), FileNotFoundError(), PermissionError()):
            with (
                self.subTest(error=type(error).__name__),
                patch.object(native_runtime, "_executable", side_effect=error),
            ):
                self.assertEqual(self.inspect()[0]["status"], "unknown")

    def test_cross_user_peer_is_not_queried_and_does_not_disclose_pid(self):
        with patch.object(native_runtime.socket, "socket") as factory:
            connection = factory.return_value.__enter__.return_value
            connection.getsockopt.return_value = struct.pack("3i", 42, os.geteuid() + 1, 0)
            report = native_runtime.inspect_running([self.bundle], socket_path="/foreign")
        connection.sendall.assert_not_called()
        self.assertEqual(report["status"], "unknown")
        self.assertIsNone(report["pid"])

    def test_malformed_incomplete_oversized_or_control_character_replies_are_unknown(self):
        for payload in (
            b"not-json\n",
            b"[]\n",
            b'{"Err":"private-server-message"}\n',
            b'{"Ok":{"Version":null}}\n',
            b'{"Ok":{"Version":""}}\n',
            b'{"Ok":{"Version":"missing newline"}}',
            b'{"Ok":{"Version":"line\\nbreak"}}\n',
            json.dumps({"Ok": {"Version": "x" * 9000}}).encode() + b"\n",
        ):
            with self.subTest(payload=payload[:40]):
                report, _ = self.inspect(payload=payload)
                self.assertEqual(report["status"], "unknown")
                self.assertNotIn("private-server-message", report["detail"])

    def test_timeout_and_unavailable_socket_remain_unknown(self):
        with patch("niri_fx.capabilities.IPC_TIMEOUT", 0.02):
            self.assertEqual(self.inspect(payload=None)[0]["status"], "unknown")
        result = native_runtime.inspect_running([self.bundle], socket_path=self.root / "absent")
        self.assertEqual(result["status"], "unknown")
        self.assertNotIn(str(self.root), result["detail"])

    def test_file_changed_during_query_does_not_create_a_false_match(self):
        from niri_fx.capabilities import _reply

        def reply_then_mutate(connection, request):
            result = _reply(connection, request)
            self.config.write_bytes(b"changed while inspecting\n")
            return result

        with patch.object(native_runtime, "_reply", side_effect=reply_then_mutate):
            report, _ = self.inspect()
        self.assertEqual(report["status"], "unknown")


class ProcReaderTests(unittest.TestCase):
    def test_continuously_growing_file_cannot_make_hash_inspection_unbounded(self):
        class Growing:
            total = 0

            def read(self, size):
                self.total += size
                return b"x" * size

        stream = Growing()
        with self.assertRaisesRegex(ValueError, "inspection limit"):
            native_runtime._hash_stream(stream, 32)
        self.assertEqual(stream.total, 33)

    def test_current_process_identity_and_executable_are_readable(self):
        self.assertGreater(native_runtime._process_start(os.getpid()), 0)
        binary, identity = native_runtime._executable(os.getpid())
        self.assertTrue(Path(binary).is_absolute())
        self.assertEqual(identity, native_runtime._identity(f"/proc/{os.getpid()}/exe"))
        self.assertTrue(native_runtime._arguments(os.getpid()))

    def test_executable_path_replacement_or_deleted_suffix_refuses_at_identity_boundary(self):
        with patch.object(native_runtime.os, "readlink", return_value="/old/niri (deleted)"):
            with self.assertRaisesRegex(ValueError, "deleted"):
                native_runtime._executable(42)
        with (
            patch.object(native_runtime.os, "readlink", return_value="/replaced/niri"),
            patch.object(native_runtime, "_identity", side_effect=[(1,), (2,)]),
        ):
            with self.assertRaisesRegex(ValueError, "differs"):
                native_runtime._executable(42)


if __name__ == "__main__":
    unittest.main()
