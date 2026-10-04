"""Guard the real-pointer harness boundary and deterministic reversal schedule."""

import socket
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from lib.pointer import VirtualPointer, owned_socket, path_samples, pointer_protocol  # noqa: E402


class PointerProtocolTests(unittest.TestCase):
    def test_normal_cargo_cache_is_discovered(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            path = (
                base
                / "cargo/registry/src/index/wayland-protocols-wlr-0.3/wlr-protocols/unstable/wlr-virtual-pointer-unstable-v1.xml"
            )
            path.parent.mkdir(parents=True)
            path.write_text(
                '<protocol name="wlr_virtual_pointer_unstable_v1"><interface name="zwlr_virtual_pointer_manager_v1"/></protocol>'
            )
            is_file = Path.is_file
            installed = Path(
                "/usr/share/wlr-protocols/unstable/wlr-virtual-pointer-unstable-v1.xml"
            )
            with (
                patch("lib.pointer.ROOT", base / "repo"),
                patch.dict("os.environ", {"CARGO_HOME": str(base / "cargo")}),
                patch.object(
                    Path,
                    "is_file",
                    autospec=True,
                    side_effect=lambda candidate: candidate != installed and is_file(candidate),
                ),
            ):
                self.assertEqual(pointer_protocol(), path.resolve())

    def test_explicit_protocol_is_validated_before_compiling(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "protocol.xml"
            for document in (
                "<invalid",
                '<protocol name="other"/>',
                '<protocol name="wlr_virtual_pointer_unstable_v1"/>',
            ):
                path.write_text(document)
                with self.subTest(document=document):
                    with self.assertRaises(ValueError):
                        pointer_protocol(path)
            path.write_text(
                '<protocol name="wlr_virtual_pointer_unstable_v1"><interface name="zwlr_virtual_pointer_manager_v1"/></protocol>'
            )
            self.assertEqual(pointer_protocol(path), path.resolve())

    def test_missing_override_never_falls_back_to_another_protocol(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "was not found"):
                pointer_protocol(Path(directory) / "missing.xml")


class PointerScopeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.bind(str(self.root / "nested"))
        self.addCleanup(self.socket.close)
        self.session = SimpleNamespace(
            host={
                "XDG_RUNTIME_DIR": str(self.root),
                "WAYLAND_DISPLAY": "host",
                "NIRI_SOCKET": "host-ipc",
            },
            env={
                "XDG_RUNTIME_DIR": str(self.root),
                "WAYLAND_DISPLAY": "nested",
                "NIRI_SOCKET": "nested-ipc",
            },
            compositor=SimpleNamespace(poll=lambda: None),
            outputs={"winit": {}},
        )

    def test_only_owned_nested_socket_is_accepted(self):
        self.assertEqual(owned_socket(self.session), self.root / "nested")
        for key in ("WAYLAND_DISPLAY", "NIRI_SOCKET"):
            with self.subTest(key=key):
                value = self.session.env[key]
                self.session.env[key] = self.session.host[key]
                with self.assertRaisesRegex(ValueError, "parent compositor"):
                    owned_socket(self.session)
                self.session.env[key] = value

    def test_alias_to_parent_socket_is_rejected(self):
        (self.root / "host").symlink_to(self.root / "nested")
        with self.assertRaisesRegex(ValueError, "owned nested socket"):
            owned_socket(self.session)

    def test_dead_session_and_wrong_output_are_rejected(self):
        self.session.compositor = SimpleNamespace(poll=lambda: 0)
        with self.assertRaisesRegex(ValueError, "running nested compositor"):
            owned_socket(self.session)
        self.session.compositor = SimpleNamespace(poll=lambda: None)
        self.session.outputs = {"DP-1": {}}
        with self.assertRaisesRegex(ValueError, "owned winit output"):
            owned_socket(self.session)

    def test_missing_socket_is_rejected(self):
        self.session.env["WAYLAND_DISPLAY"] = "missing"
        with self.assertRaisesRegex(ValueError, "owned nested socket"):
            owned_socket(self.session)

    def test_outside_coordinates_do_not_reach_the_helper(self):
        pointer = object.__new__(VirtualPointer)
        pointer.session = SimpleNamespace(width=1280, height=800)
        pointer.command = Mock()
        for point in ((-1, 0), (0, -1), (1280, 0), (1279.9, 0), (0, 800), (float("nan"), 0)):
            with self.assertRaisesRegex(ValueError, "inside the owned output"):
                pointer.move(*point)
        pointer.command.assert_not_called()


class PointerPathTests(unittest.TestCase):
    def test_reversal_visits_turn_and_finishes_at_exact_endpoint(self):
        samples = list(path_samples(((100, 100), (300, 200), (100, 100)), 1, fps=4))
        self.assertEqual(
            samples, [(0.25, (200, 150)), (0.5, (300, 200)), (0.75, (200, 150)), (1, (100, 100))]
        )

    def test_short_paths_still_submit_the_endpoint(self):
        self.assertEqual(list(path_samples(((0, 0), (2, 3)), 0.001)), [(0.001, (2, 3))])

    def test_bad_schedules_fail_before_input(self):
        for points, duration, fps in (
            (((0, 0),), 1, 60),
            (((0, 0), (1, 1)), 0, 60),
            (((0, 0), (1, 1)), float("nan"), 60),
            (((0, 0), (1, 1)), 1, 0),
        ):
            with self.subTest(points=points, duration=duration, fps=fps):
                with self.assertRaises(ValueError):
                    list(path_samples(points, duration, fps))
