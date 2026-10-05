import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from niri_fx.capabilities import (
    MAX_REPLY,
    fragment_capability,
    movement_capability,
    pointer_capability,
    swap_capability,
)


@contextmanager
def ipc_reply(payload):
    """One local read-only IPC exchange, including kernel peer identification."""
    with tempfile.TemporaryDirectory() as directory:
        path = str(Path(directory) / "ipc.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(path)
            listener.listen(1)
            listener.settimeout(2)
            requests = []

            def serve():
                with listener.accept()[0] as client:
                    client.settimeout(2)
                    for reply in payload if isinstance(payload, list) else [payload]:
                        request = client.recv(128)
                        if not request:
                            break
                        requests.append(request)
                        try:
                            client.sendall(reply)
                        except BrokenPipeError:
                            break

            worker = threading.Thread(target=serve, daemon=True)
            worker.start()
            try:
                yield path, requests
            finally:
                worker.join(timeout=3)


class MovementCapabilityTests(unittest.TestCase):
    def test_activation_requires_the_versioned_running_renderer_contract(self):
        contract = {
            "schema": 1,
            "movement_shader": 2,
            "renderer_verified": True,
            "movement_configured": False,
            "frame_timings": True,
        }
        cases = [
            (contract, True),
            (contract | {"schema": 2}, False),
            (contract | {"movement_shader": 1}, False),
            (contract | {"movement_shader": 3}, False),
            (contract | {"renderer_verified": False}, False),
            (contract | {"renderer_verified": 1}, False),
            (contract | {"schema": True}, False),
            ([], False),
        ]
        for value, ready in cases:
            with (
                self.subTest(value=value),
                ipc_reply(
                    [
                        b'{"Ok":{"Version":"experimental"}}\n',
                        json.dumps({"Ok": {"NiriFxCapabilities": value}}).encode() + b"\n",
                    ]
                ) as (path, requests),
                patch("niri_fx.capabilities._probe", return_value=("supported", "Accepted")),
            ):
                report = movement_capability(sys.executable, socket_path=path)
            self.assertEqual(report["activation_ready"], ready)
            self.assertEqual(requests, [b'"Version"\n', b'"NiriFxCapabilities"\n'])

    def probe(self, results):
        with patch("niri_fx.capabilities.subprocess.run", side_effect=results):
            return movement_capability(sys.executable)

    def test_validates_only_temporary_configs_and_cleans_up(self):
        paths, configs = [], []

        def validate(command, **kwargs):
            self.assertEqual(command[:3], [os.path.abspath(sys.executable), "validate", "-c"])
            self.assertEqual(kwargs["timeout"], 5)
            paths.append(Path(command[3]))
            configs.append(paths[-1].read_text())
            return subprocess.CompletedProcess(command, 0, "", "")

        report = self.probe(validate)
        self.assertEqual(report["status"], "supported")
        self.assertEqual(report["scope"], "configuration-parser")
        self.assertNotIn("custom-shader", configs[0])
        self.assertIn("custom-shader", configs[1])
        self.assertEqual(paths[0], paths[1])
        self.assertFalse(paths[0].exists())
        self.assertEqual(report["session"]["status"], "unknown")

    def test_only_specific_shader_rejection_means_unsupported(self):
        success = subprocess.CompletedProcess([], 0, "", "")
        rejection = subprocess.CompletedProcess([], 1, "", "unexpected node `custom-shader`")
        failure = subprocess.CompletedProcess([], 1, "", "error loading config")
        for results, expected in (
            ([success, rejection], "unsupported"),
            ([rejection], "unknown"),
            ([success, failure], "unknown"),
            ([failure], "unknown"),
            (subprocess.TimeoutExpired("niri", 5), "unknown"),
            (OSError("cannot execute"), "unknown"),
        ):
            with self.subTest(expected=expected, results=results):
                self.assertEqual(self.probe(results)["status"], expected)

    def test_missing_or_replaced_binary_is_unknown(self):
        with patch("niri_fx.capabilities.shutil.which", return_value=None):
            report = movement_capability("/missing/niri")
        self.assertIsNone(report["binary"])
        self.assertEqual(report["status"], "unknown")
        with (
            patch("niri_fx.capabilities._identity", side_effect=[(1, 2, 3, 4), (1, 5, 3, 4)]),
            patch("niri_fx.capabilities._probe", return_value=("supported", "Accepted")),
        ):
            report = movement_capability(sys.executable)
        self.assertEqual(report["status"], "unknown")
        self.assertIn("changed", report["detail"])

    def test_no_socket_does_not_attempt_a_connection(self):
        with (
            patch("niri_fx.capabilities._probe", return_value=("supported", "Accepted")),
            patch("niri_fx.capabilities.socket.socket") as connection,
        ):
            report = movement_capability(sys.executable)
        connection.assert_not_called()
        self.assertFalse(report["session"]["connected"])

    def test_explicit_relative_path_is_not_reinterpreted_as_a_path_search(self):
        with patch("niri_fx.capabilities.shutil.which", return_value=None) as which:
            movement_capability(Path("./niri"))
        which.assert_called_once_with(str(Path.cwd() / "niri"))

    def test_running_support_requires_same_executable_not_same_version(self):
        payload = b'{"Ok":{"Version":"same-version"}}\n'
        for binary, same, expected in (
            (sys.executable, True, "supported"),
            ("/bin/sh", False, "unknown"),
        ):
            with (
                self.subTest(binary=binary),
                ipc_reply(payload) as (path, requests),
                patch("niri_fx.capabilities._probe", return_value=("supported", "Accepted")),
            ):
                session = movement_capability(binary, socket_path=path)["session"]
            self.assertEqual(requests, [b'"Version"\n'])
            self.assertTrue(session["connected"])
            self.assertEqual(session["same_binary"], same)
            self.assertEqual(session["status"], expected)
            self.assertEqual(session["version"], "same-version")

    def test_rejected_parser_result_applies_to_matching_session(self):
        with (
            ipc_reply(b'{"Ok":{"Version":"stock"}}\n') as (path, _),
            patch("niri_fx.capabilities._probe", return_value=("unsupported", "Rejected")),
        ):
            report = movement_capability(sys.executable, socket_path=path)
        self.assertEqual(report["session"]["status"], "unsupported")

    def test_unreadable_process_identity_does_not_inherit_support(self):
        with (
            ipc_reply(b'{"Ok":{"Version":"test"}}\n') as (path, _),
            patch("niri_fx.capabilities._probe", return_value=("supported", "Accepted")),
            patch("niri_fx.capabilities._identity", side_effect=[(1,), (1,), PermissionError()]),
        ):
            session = movement_capability(sys.executable, socket_path=path)["session"]
        self.assertTrue(session["connected"])
        self.assertIsNone(session["same_binary"])
        self.assertEqual(session["status"], "unknown")

    def test_invalid_oversized_and_incomplete_replies_remain_unknown(self):
        replies = [
            b"not-json\n",
            b"[]\n",
            b'{"Err":"unavailable"}\n',
            b'{"Ok":{"Version":null}}\n',
            b'{"Ok":{"Version":""}}\n',
            json.dumps({"Ok": {"Version": "x" * MAX_REPLY}}).encode() + b"\n",
            b'{"Ok":{"Version":"missing-newline"}}',
        ]
        for payload in replies:
            with (
                self.subTest(payload=payload[:50]),
                ipc_reply(payload) as (path, _),
                patch("niri_fx.capabilities._probe", return_value=("supported", "Accepted")),
            ):
                session = movement_capability(sys.executable, socket_path=path)["session"]
            self.assertFalse(session["connected"])
            self.assertIsNone(session["same_binary"])
            self.assertEqual(session["status"], "unknown")

    def test_foreign_user_socket_is_not_queried(self):
        with (
            patch("niri_fx.capabilities._probe", return_value=("supported", "Accepted")),
            patch("niri_fx.capabilities.socket.socket") as factory,
        ):
            connection = factory.return_value.__enter__.return_value
            connection.getsockopt.return_value = struct.pack("3i", 1, os.geteuid() + 1, 1)
            report = movement_capability(sys.executable, socket_path="/socket")
        connection.sendall.assert_not_called()
        self.assertFalse(report["session"]["connected"])

    def test_unreachable_and_slow_sessions_remain_optional(self):
        for error in (FileNotFoundError(), TimeoutError("timed out")):
            with (
                self.subTest(error=error),
                patch("niri_fx.capabilities._probe", return_value=("supported", "Accepted")),
                patch("niri_fx.capabilities.socket.socket") as factory,
            ):
                factory.return_value.__enter__.return_value.connect.side_effect = error
                report = movement_capability(sys.executable, socket_path="/socket")
            self.assertEqual(report["status"], "supported")
            self.assertEqual(report["session"]["status"], "unknown")

        with (
            patch("niri_fx.capabilities._probe", return_value=("supported", "Accepted")),
            patch("niri_fx.capabilities.socket.socket") as factory,
        ):
            connection = factory.return_value.__enter__.return_value
            connection.getsockopt.return_value = struct.pack("3i", os.getpid(), os.geteuid(), 1)
            connection.recv.side_effect = TimeoutError("reply timed out")
            report = movement_capability(sys.executable, socket_path="/socket")
        self.assertFalse(report["session"]["connected"])
        self.assertEqual(report["session"]["status"], "unknown")


class PointerCapabilityTests(unittest.TestCase):
    contract = {
        "schema": 1,
        "pointer_wobble": 2,
        "renderer_verified": True,
        "configured": False,
        "enabled": False,
        "max_deformation": 64,
        "max_release_ms": 2000,
    }

    def test_only_exact_pointer_contract_can_activate_even_when_not_configured(self):
        cases = [(self.contract, True), (self.contract | {"pointer_wobble": 1}, False)]
        for key in ("schema", "pointer_wobble", "max_deformation", "max_release_ms"):
            cases.extend(
                (self.contract | {key: value}, False)
                for value in (True, str(self.contract[key]), self.contract[key] + 1)
            )
        for key in ("renderer_verified", "configured", "enabled"):
            cases.append((self.contract | {key: 1}, False))
        cases.extend(
            [
                (self.contract | {"renderer_verified": False}, False),
                (self.contract | {"configured": True, "enabled": True}, True),
                (self.contract | {"enabled": True}, False),
                (self.contract | {"unknown": 1}, False),
                (
                    {key: value for key, value in self.contract.items() if key != "configured"},
                    False,
                ),
                ([], False),
                (None, False),
            ]
        )
        for value, ready in cases:
            with (
                self.subTest(value=value),
                ipc_reply(
                    [
                        b'{"Ok":{"Version":"experimental"}}\n',
                        json.dumps({"Ok": {"NiriFxPointerCapabilities": value}}).encode() + b"\n",
                    ]
                ) as (path, requests),
                patch(
                    "niri_fx.capabilities._pointer_probe", return_value=("supported", "Accepted")
                ),
            ):
                report = pointer_capability(sys.executable, socket_path=path)
            self.assertEqual(report["activation_ready"], ready)
            self.assertEqual(requests, [b'"Version"\n', b'"NiriFxPointerCapabilities"\n'])

    def test_parser_probe_is_temporary_and_specific_to_pointer(self):
        configs, paths = [], []

        def validate(command, **kwargs):
            self.assertEqual(command[:3], [os.path.abspath(sys.executable), "validate", "-c"])
            self.assertEqual(kwargs["timeout"], 5)
            paths.append(Path(command[3]))
            configs.append(paths[-1].read_text())
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("niri_fx.capabilities.subprocess.run", side_effect=validate):
            report = pointer_capability(sys.executable)
        self.assertEqual(report["status"], "supported")
        self.assertNotIn("pointer-wobble", configs[0])
        self.assertIn("pointer-wobble", configs[1])
        self.assertNotIn("custom-shader", configs[1])
        self.assertTrue(all(not path.exists() for path in paths))
        self.assertFalse(report["activation_ready"])
        success = subprocess.CompletedProcess([], 0, "", "")
        for error, status in (
            ("unexpected node `pointer-wobble`", "unsupported"),
            ("unexpected node `custom-shader`", "unknown"),
            ("error loading config", "unknown"),
        ):
            with patch(
                "niri_fx.capabilities.subprocess.run",
                side_effect=[success, subprocess.CompletedProcess([], 1, "", error)],
            ):
                self.assertEqual(pointer_capability(sys.executable)["status"], status)

    def test_matching_version_or_parser_alone_cannot_activate_pointer(self):
        with (
            ipc_reply(b'{"Ok":{"Version":"experimental"}}\n') as (path, requests),
            patch("niri_fx.capabilities._pointer_probe", return_value=("supported", "Accepted")),
        ):
            report = pointer_capability("/bin/sh", socket_path=path)
        self.assertEqual(requests, [b'"Version"\n'])
        self.assertFalse(report["session"]["same_binary"])
        self.assertFalse(report["activation_ready"])
        with (
            ipc_reply(
                [
                    b'{"Ok":{"Version":"experimental"}}\n',
                    json.dumps({"Ok": {"NiriFxPointerCapabilities": self.contract}}).encode()
                    + b"\n",
                ]
            ) as (path, _),
            patch("niri_fx.capabilities._pointer_probe", return_value=("unsupported", "Rejected")),
        ):
            self.assertFalse(
                pointer_capability(sys.executable, socket_path=path)["activation_ready"]
            )


class FragmentCapabilityTests(unittest.TestCase):
    def test_continuous_motion_requires_its_own_exact_renderer_contract(self):
        contract = {
            "schema": 1,
            "fragment_motion": 3,
            "renderer_verified": True,
            "fragment_configured": False,
            "fragment_enabled": False,
            "max_deformation": 1024,
            "max_release_ms": 2000,
        }
        cases = [
            (contract, True),
            (contract | {"fragment_configured": True, "fragment_enabled": True}, True),
            (contract | {"fragment_enabled": True}, False),
            (contract | {"renderer_verified": False}, False),
            (contract | {"fragment_motion": 1}, False),
            (contract | {"fragment_motion": 2}, False),
            (contract | {"max_deformation": 64}, False),
            (contract | {"max_release_ms": 2500}, False),
            (contract | {"schema": True}, False),
            (contract | {"fragment_configured": 1}, False),
            (contract | {"extra": True}, False),
            ({key: value for key, value in contract.items() if key != "fragment_motion"}, False),
            (None, False),
            ([], False),
        ]
        for value, ready in cases:
            with (
                self.subTest(value=value),
                ipc_reply(
                    [
                        b'{"Ok":{"Version":"experimental"}}\n',
                        json.dumps({"Ok": {"NiriFxFragmentCapabilities": value}}).encode() + b"\n",
                    ]
                ) as (path, requests),
                patch("niri_fx.capabilities._probe", return_value=("supported", "Accepted")),
            ):
                report = fragment_capability(sys.executable, socket_path=path)
            self.assertEqual(report["activation_ready"], ready)
            self.assertEqual(requests, [b'"Version"\n', b'"NiriFxFragmentCapabilities"\n'])

    def test_timed_shader_parser_support_alone_does_not_prove_continuous_motion(self):
        with (
            ipc_reply([b'{"Ok":{"Version":"experimental"}}\n', b'{"Err":"unknown request"}\n']) as (
                path,
                _,
            ),
            patch("niri_fx.capabilities._probe", return_value=("supported", "Accepted")),
        ):
            report = fragment_capability(sys.executable, socket_path=path)
        self.assertEqual(report["status"], "supported")
        self.assertEqual(report["session"]["contract"]["status"], "unknown")
        self.assertFalse(report["activation_ready"])


class DoctorFragmentTests(unittest.TestCase):
    def test_reports_continuous_motion_separately_without_requiring_it_on_stock(self):
        from niri_fx.setup import doctor

        report = {
            "binary": "/example/niri",
            "detail": "parser accepted",
            "activation_ready": False,
            "session": {
                "detail": "matching process",
                "contract": {"status": "unknown", "detail": "continuous motion unverified"},
            },
        }
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch("niri_fx.setup.shutil.which", return_value="/example/niri"),
            patch("niri_fx.setup.subprocess.check_output", return_value="niri fixture"),
            patch("niri_fx.setup.validate_config"),
            patch("niri_fx.capabilities.movement_capability", return_value=report),
            patch("niri_fx.capabilities.pointer_capability", return_value=report),
            patch("niri_fx.capabilities.fragment_capability", return_value=report) as inspect,
            patch("niri_fx.picker.picker_checks", return_value=[]),
        ):
            result = doctor(
                SimpleNamespace(
                    config=Path(temporary) / "config.kdl",
                    inir_root=Path(temporary),
                    movement_binary=Path("/example/niri"),
                )
            )
        inspect.assert_called_once()
        self.assertEqual(result["fragment_capability"], report)
        self.assertTrue(result["healthy"])
        self.assertIn(
            {"check": "fragment-renderer", "ok": None, "detail": "continuous motion unverified"},
            result["checks"],
        )


if __name__ == "__main__":
    unittest.main()


class SwapCapabilityTests(unittest.TestCase):
    def test_swap_contract_requires_exact_version_types_and_renderer(self):
        valid = {"schema": 1, "swap_shader": 1, "renderer_verified": True, "configured": False}
        for data, expected in (
            (valid, True),
            (valid | {"swap_shader": 2}, False),
            (valid | {"schema": True}, False),
            (valid | {"renderer_verified": False}, False),
            (valid | {"configured": 1}, False),
            (valid | {"unknown": True}, False),
            ({}, False),
            ([], False),
        ):
            with (
                self.subTest(data=data),
                ipc_reply(
                    [
                        b'{"Ok":{"Version":"NiriFX"}}\n',
                        json.dumps({"Ok": {"NiriFxSwapCapabilities": data}}).encode() + b"\n",
                    ]
                ) as (path, requests),
                patch("niri_fx.capabilities._swap_probe", return_value=("supported", "Accepted")),
            ):
                result = swap_capability(sys.executable, socket_path=path)
            self.assertEqual(result["activation_ready"], expected)
            self.assertEqual(requests, [b'"Version"\n', b'"NiriFxSwapCapabilities"\n'])

    def test_parser_support_is_not_renderer_or_live_support(self):
        paths = []

        def validate(command, **kwargs):
            path = Path(command[3])
            paths.append(path)
            self.assertIn("window-swap", path.read_text())
            return subprocess.CompletedProcess(command, 0, "", "")

        with patch("niri_fx.capabilities.subprocess.run", side_effect=validate):
            result = swap_capability(sys.executable)
        self.assertEqual(result["status"], "supported")
        self.assertFalse(result["activation_ready"])
        self.assertTrue(all(not path.exists() for path in paths))
