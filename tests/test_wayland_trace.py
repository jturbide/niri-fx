"""Protocol diagnostics must stay directional, bounded and safe to publish."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "wayland_trace", ROOT / "scripts/lib/wayland_trace.py"
)
trace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace)


class WaylandTraceTests(unittest.TestCase):
    def summarize(self, lines, direction="sent", intervals=None):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "owned.log"
            path.write_bytes(lines)
            return trace.surface_trace(path, direction, intervals or [])

    def test_rust_client_trace_selects_toplevel_and_excludes_cursor_and_events(self):
        startup = (
            b"[100.100][rs] -> xdg_wm_base@8.get_xdg_surface(xdg_surface@9, wl_surface@7)\n"
            b"[100.200][rs] -> xdg_surface@9.get_toplevel(xdg_toplevel@10)\n"
            b"[100.300][rs] -> wl_surface@7.commit()\n"
        )
        active = (
            b"[101.100][rs] -> wl_surface@7.attach(wl_buffer@12, 0, 0)\n"
            b"[101.200][rs] -> wl_surface@7.damage_buffer(0, 0, 1280, 800)\n"
            b"[101.300][rs] -> wl_surface@7.commit()\n"
            b"[101.400][rs] -> wl_surface@20.commit()\n"
            b"[101.500][rs] <- wl_surface@7.enter, (wl_output@4)\n"
        )
        result = self.summarize(
            startup + active,
            intervals=[
                {
                    "phase": "capture",
                    "begin_ms_after_close": 0,
                    "end_ms_after_close": 10,
                    "start_offset": len(startup),
                    "end_offset": len(startup + active),
                }
            ],
        )
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["all_surface_requests"]["commit"], 3)
        self.assertEqual(result["toplevel_requests"]["commit"], 2)
        phase = result["phases"][0]
        self.assertEqual(phase["toplevel_requests"]["commit"], 1)
        self.assertEqual(phase["toplevel_requests"]["damage_buffer"], 1)

    def test_rust_server_receipt_and_c_library_formats_do_not_count_sends(self):
        for separator, arrow, annotation in ((b"@", b"<-", b"[rs]"), (b"#", b"", b"")):
            with self.subTest(separator=separator):
                lines = (
                    b"[200.100]" + annotation + b" " + arrow + b" xdg_wm_base@8.get_xdg_surface, "
                    b"(new id xdg_surface@9, wl_surface@7[2])\n"
                    b"[200.200]" + annotation + b" " + arrow + b" xdg_surface@9.get_toplevel, "
                    b"(new id xdg_toplevel@10)\n"
                    b"[200.300]" + annotation + b" " + arrow + b" wl_surface@7.commit, ()\n"
                    b"[200.400]" + annotation + b" -> wl_surface@7.commit()\n"
                ).replace(b"@", separator)
                result = self.summarize(lines, "received")
                self.assertEqual(result["status"], "available")
                self.assertEqual(result["toplevel_requests"]["commit"], 1)
                self.assertFalse(result["proves_presentation"])
                self.assertIn("unverified", result["surface_selection"])

    def test_raw_titles_paths_buffer_arguments_and_object_ids_are_not_exported(self):
        result = self.summarize(
            b'[123.000][rs] -> xdg_toplevel@9000.set_title("/home/private/secret")\n'
            b"[123.100][rs] -> wl_surface@8000.attach(secret_token, 0, 0)\n"
            b"[123.200][rs] -> wl_surface@8000.commit()\n"
        )
        serialized = json.dumps(result)
        for private in ("/home", "private", "secret", "9000", "8000", "123.200"):
            self.assertNotIn(private, serialized)
        self.assertEqual(result["all_surface_requests"]["attach"], 1)

    def test_libwayland_wall_clock_timestamp_is_supported(self):
        lines = (
            b"[03:48:45.231189] -> xdg_wm_base#13.get_xdg_surface(new id xdg_surface#29, wl_surface#28)\n"
            b"[03:48:45.231192] -> xdg_surface#29.get_toplevel(new id xdg_toplevel#30)\n"
            b"[03:48:45.231231] -> wl_surface#28.commit()\n"
            b"[03:48:45.515353] {EGLSurface(28)} -> wl_surface#28.damage_buffer(0, 0, 500, 952)\n"
            b"[03:48:45.515359] {EGLSurface(28)} -> wl_surface#28.attach(wl_buffer#4278190080, 0, 0)\n"
            b"[03:48:45.515367] {EGLSurface(28)} -> wl_surface#28.commit()\n"
        )
        result = self.summarize(lines)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["toplevel_requests"]["commit"], 2)
        self.assertEqual(result["toplevel_requests"]["damage_buffer"], 1)
        self.assertEqual(result["toplevel_requests"]["attach"], 1)
        self.assertNotIn("EGLSurface", json.dumps(result))
        received = self.summarize(lines.replace(b"-> ", b""), "received")
        self.assertEqual(received["toplevel_requests"]["commit"], 2)

    def test_missing_or_unknown_logging_is_not_zero_traffic_evidence(self):
        for data in (b"", b"INFO renderer ready\n", b"unknown wl_surface@7.commit()\n"):
            with self.subTest(data=data):
                result = self.summarize(data)
                self.assertEqual(result["status"], "unavailable")
                self.assertIn("absence of traffic is not established", result["reason"])
        with tempfile.TemporaryDirectory() as directory:
            result = trace.surface_trace(Path(directory) / "missing", "sent", [])
            self.assertEqual(result["reason"], "log unavailable")

    def test_partial_or_ambiguous_logs_cannot_claim_precise_toplevel_counts(self):
        duplicate = (
            b"[1.000][rs] -> xdg_wm_base@8.get_xdg_surface(xdg_surface@9, wl_surface@7)\n"
            b"[1.100][rs] -> xdg_surface@9.get_toplevel(xdg_toplevel@10)\n"
        )
        result = self.summarize(duplicate * 2 + b"[1.200][rs] -> wl_surface@7.commit()\n")
        self.assertIsNone(result["toplevel_requests"])
        self.assertEqual(result["surface_selection"], "unavailable or ambiguous")
        result = self.summarize(
            b"[1.200][rs] -> wl_surface@7.commit()\ninterleaved wl_surface@7.damage(0, 0)\n"
        )
        self.assertEqual(result["status"], "limited")
        self.assertEqual(result["unparsed_surface_lines"], 1)

    def test_bounded_reads_and_invalid_intervals_fail_honestly(self):
        with patch.object(trace, "MAX_LOG_BYTES", 10):
            result = self.summarize(b"x" * 11)
        self.assertEqual(result["reason"], "log exceeds diagnostic size limit")
        with self.assertRaisesRegex(ValueError, "outside"):
            self.summarize(b"", intervals=[{"start_offset": 0, "end_offset": 1}])
        with self.assertRaisesRegex(ValueError, "direction"):
            self.summarize(b"", "unknown")


if __name__ == "__main__":
    unittest.main()
