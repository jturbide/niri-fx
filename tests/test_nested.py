"""Keep native acceptance failures tied to actual compositor error records."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("nested", ROOT / "scripts/lib/nested.py")
nested = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nested)


class NativeLogTests(unittest.TestCase):
    def test_warning_module_names_do_not_hide_real_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            session = object.__new__(nested.NestedSession)
            session.root = Path(directory)
            log = session.root / "niri.log"
            warning = "2026-10-03T12:00:00Z WARN smithay::backend::egl::error: EGL warning\n"
            log.write_text(warning)
            session.check_render_log()
            for failure in (
                "2026-10-03T12:00:01Z ERROR niri::render: failed\n",
                "thread 'main' panicked at render.rs:42\n",
                "error compiling fragment shader\n",
                "error linking shader program\n",
            ):
                with self.subTest(failure=failure):
                    log.write_text(warning + failure)
                    with self.assertRaisesRegex(RuntimeError, "Compositor reported errors"):
                        session.check_render_log()
