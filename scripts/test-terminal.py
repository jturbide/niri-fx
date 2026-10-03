#!/usr/bin/env python3
"""Exercise guided selection, apply and Undo in a real PTY with temporary files.

--record uses Alacritty in an owned nested Niri output. The default runs without
a desktop terminal; both paths use the actual CLI and Niri config validator.
"""

import argparse
import os
import shlex
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.nested import NestedSession, encode_gif, record, save_clips, source_hashes, stop, wait_for

from niri_fx.catalog import STYLES
from niri_fx.effects import render_kdl

BASE = """hotkey-overlay { skip-at-startup; }
input { keyboard { repeat-rate 0; }; }
layout { background-color "#11171c"; gaps 18; }
animations { window-resize { duration-ms 170; curve "ease-out-cubic"; }; }
"""


@contextmanager
def headless():
    with tempfile.TemporaryDirectory(prefix="nirifx-terminal-") as directory:

        class Session:
            pass

        session = Session()
        session.root = Path(directory)
        session.env = os.environ.copy()
        for key, folder in (
            ("HOME", "home"),
            ("XDG_CONFIG_HOME", "config"),
            ("XDG_STATE_HOME", "state"),
            ("XDG_DATA_HOME", "data"),
        ):
            location = session.root / folder
            location.mkdir()
            session.env[key] = str(location)
        session.config = session.root / "config/niri/config.kdl"
        session.config.parent.mkdir()
        session.config.write_text(BASE)
        yield session


def exercise(session, recording):
    root = session.root
    session.env["NIRIFX_TEST_DIRECTORY"] = str(root)
    transcript = root / "terminal.txt"
    inner = [sys.executable, str(ROOT / "scripts/fixtures/terminal-session.py")]
    command = [
        "script",
        "--quiet",
        "--return",
        "--flush",
        "--command",
        shlex.join(inner),
        str(transcript),
    ]
    recorder = None
    if recording:
        session.env["GTK_THEME"] = "Adwaita:dark"
        config = root / "alacritty.toml"
        config.write_text("""[window]
padding = { x = 16, y = 16 }
[font]
size = 12
[colors.primary]
background = "#11171c"
foreground = "#b7e8db"
""")
        process = session.launch(
            [
                "alacritty",
                "--config-file",
                str(config),
                "--title",
                "NiriFX terminal guide",
                "--hold",
                "--working-directory",
                str(ROOT),
                "--command",
                *command,
            ],
            "terminal",
            private_bus=True,
        )
        window = wait_for(
            lambda: next(
                (w for w in session.windows() if w["title"] == "NiriFX terminal guide"), None
            ),
            "terminal window",
        )
        for action, value in (
            ("move-window-to-floating", None),
            ("set-window-width", "1100"),
            ("set-window-height", "870"),
        ):
            session.msg("action", action, "--id", str(window["id"]), *([value] if value else []))
    else:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=session.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )

    def content():
        return transcript.read_text(errors="replace") if transcript.exists() else ""

    def send(value):
        if recording:
            session.focus()
            session.keys(value)
            session.keys("-k", "Return")
        else:
            process.stdin.write((value + "\n").encode())
            process.stdin.flush()

    include = session.config.parent / "nirifx/animations.kdl"
    try:
        wait_for(lambda: "Choose a style" in content(), "preset prompt")
        if recording:
            recorder, video = record(session, "workflow-terminal")
            time.sleep(1)
        send("fragment-flow")
        wait_for(lambda: "Type apply" in content(), "review prompt")
        assert session.config.read_text() == BASE and not include.exists()
        if recording:
            time.sleep(2)
            session.capture("terminal-review")
        send("apply")
        wait_for((root / "completed-1").exists, "terminal apply")
        assert include.read_text().endswith(render_kdl(STYLES["fragment-flow"]))
        assert "window-resize" not in include.read_text()
        wait_for(lambda: content().count("Choose a style") == 2, "second prompt")
        send("undo")
        wait_for(lambda: "Type undo" in content(), "Undo review")
        if recording:
            time.sleep(1.5)
        send("undo")
        wait_for((root / "completed-2").exists, "terminal Undo")
        assert session.config.read_text() == BASE and not include.exists()
        assert "Previous files restored exactly" in content()
        if recording:
            time.sleep(2)
            session.capture("terminal-restored")
            stop(recorder, signal.SIGINT)
            recorder = None
            dest = ROOT / "docs/gifs/workflow-terminal.gif"
            encode_gif(video, dest, width=1000, fps=20)
            save_clips(
                [
                    {
                        "name": "workflow-terminal",
                        "backend": "real CLI terminal workflow in stock nested Niri",
                        "version": session.version,
                        "checks": [
                            "preset selection",
                            "read-only review",
                            "confirmed apply",
                            "exact Undo",
                            "resize preserved",
                        ],
                        "sources": source_hashes(
                            "niri_fx/terminal.py", "scripts/fixtures/terminal-session.py"
                        ),
                        "file": str(dest.relative_to(ROOT)),
                        "bytes": dest.stat().st_size,
                    }
                ]
            )
            session.check_render_log()
            print(f"Evidence: {root}")
        else:
            assert process.wait(timeout=10) == 0
        print("PASS real PTY selection, reviewed apply, exact Undo and base resize preservation")
    finally:
        if recorder:
            stop(recorder, signal.SIGINT)
        stop(process)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true")
    parser.add_argument(
        "--executable",
        type=Path,
        help="Test an installed niri-fx executable from outside the checkout",
    )
    args = parser.parse_args()
    with NestedSession(BASE, width=1240, height=930) if args.record else headless() as session:
        if args.executable:
            session.env["NIRIFX_TEST_EXECUTABLE"] = str(args.executable.resolve())
        exercise(session, args.record)


if __name__ == "__main__":
    main()
