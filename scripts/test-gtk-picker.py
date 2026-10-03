#!/usr/bin/env python3
"""Test the GJS controller and GTK keyboard/lifecycle flow in private Niri sessions.

Requires GJS, GTK 4.10+, Niri and wtype. --record also needs wf-recorder/ffmpeg.
Optional --ags exercises the shipped AGS 3 entry point with the same GTK widget.
All CLI transactions use temporary configs; Studio dispatch is tested without a browser.
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.nested import NestedSession, encode_gif, record, save_clips, source_hashes, stop, wait_for

from niri_fx.effects import PRESETS, render_kdl

BASE = """hotkey-overlay { skip-at-startup; }
layout { background-color "#11171c"; gaps 18; }
animations { window-resize { duration-ms 170; curve "ease-out-cubic"; }; }
"""


def environment(root, config):
    return {
        "NIRIFX_COMMAND": json.dumps([sys.executable, "-m", "niri_fx"]),
        "NIRIFX_CONFIG": str(config),
        "NIRIFX_STATE": str(root / "state/niri-fx/gtk"),
        "GTK_THEME": "Adwaita:dark",
        # Private test buses deliberately have no activation services.
        "GTK_A11Y": "none",
    }


def controller_check(gjs):
    with tempfile.TemporaryDirectory(prefix="nirifx-gtk-") as directory:
        root = Path(directory)
        env = os.environ.copy()
        for key, folder in (
            ("HOME", "home"),
            ("XDG_CONFIG_HOME", "config"),
            ("XDG_STATE_HOME", "state"),
            ("XDG_DATA_HOME", "data"),
            ("XDG_CACHE_HOME", "cache"),
        ):
            path = root / folder
            path.mkdir(mode=0o700)
            env[key] = str(path)
        config = root / "config/niri/config.kdl"
        config.parent.mkdir()
        config.write_text(BASE)
        profile = root / "Profile with spaces.json"
        shutil.copyfile(ROOT / "examples/profiles/elastic-resize.json", profile)
        env.update(environment(root, config), NIRIFX_TEST_PROFILE=str(profile))
        subprocess.run(
            [gjs, "-m", "scripts/fixtures/gtk-controller-check.mjs"],
            cwd=ROOT,
            env=env,
            check=True,
            timeout=60,
        )
        assert config.read_text() == BASE


def keyboard(session, key):
    session.keys("-M", "ctrl", "-k", key, "-m", "ctrl")


def show_window(session):
    window = wait_for(
        lambda: next((w for w in session.windows() if w["title"] == "NiriFX GTK Picker"), None),
        "GTK picker window",
        30,
    )
    for name, value in (
        ("move-window-to-floating", None),
        ("set-window-width", "1120"),
        ("set-window-height", "850"),
    ):
        session.msg("action", name, "--id", str(window["id"]), *([value] if value else []))
    return window


def view_check(gjs, recording):
    with NestedSession(BASE, width=1200, height=900) as session:
        root, config = session.root, session.config
        original = config.read_bytes()
        include = config.parent / "nirifx/animations.kdl"
        channel = root / "channel"
        channel.mkdir()
        # Delay a real apply to prove close-request does not terminate the writer.
        wrapper = root / "command.py"
        wrapper.write_text(
            "import os,sys,time\nfrom pathlib import Path\n"
            f"root=Path({str(root)!r})\n"
            "if sys.argv[1]=='setup' and '--apply' in sys.argv and (root/'delay').exists():\n"
            " (root/'started').touch()\n time.sleep(1)\n"
            f"os.chdir({str(ROOT)!r})\n"
            f"os.execv({sys.executable!r},[{sys.executable!r},'-m','niri_fx',*sys.argv[1:]])\n"
        )
        session.env.update(environment(root, config), NIRIFX_TEST_CHANNEL=str(channel))
        session.env["NIRIFX_COMMAND"] = json.dumps([sys.executable, str(wrapper)])
        process = session.launch(
            [gjs, "-m", str(ROOT / "scripts/fixtures/gtk-host.mjs")],
            "gtk-picker",
            private_bus=True,
        )

        def settled(predicate=lambda data: True):
            def check():
                if process.poll() is not None:
                    raise RuntimeError((root / "gtk-picker.log").read_text())
                try:
                    data = json.loads((channel / "state.json").read_text())
                except (FileNotFoundError, json.JSONDecodeError):
                    return None
                return data if not data["busy"] and predicate(data) else None

            return wait_for(check, "GTK operation", 30)

        def action(method, *args):
            path = channel / "pending.json"
            path.write_text(json.dumps({"method": method, "args": args}))
            path.replace(channel / "command.json")
            wait_for(lambda: not (channel / "command.json").exists(), "test command")

        recorder = None
        try:
            settled(lambda d: d["count"] == len(PRESETS))
            window = show_window(session)
            time.sleep(0.5)
            if recording:
                recorder, video = record(session, "workflow-gtk-picker")
                time.sleep(1)
            keyboard(session, "f")
            session.keys("-d", "90", "explosion")
            session.keys("-k", "Return")
            settled(lambda d: d["selected"] == "explosion")
            if recording:
                time.sleep(1)
            keyboard(session, "r")
            settled(lambda d: d["canApply"])
            assert config.read_bytes() == original and not include.exists()
            if recording:
                time.sleep(1.5)
            session.capture("gtk-review")
            keyboard(session, "Return")
            settled(lambda d: bool(d["undo"]))
            assert include.read_text().endswith(render_kdl(PRESETS["explosion"]))
            assert "window-resize" not in include.read_text()
            if recording:
                time.sleep(1.5)
            session.keys("-M", "ctrl", "-M", "alt", "-k", "u", "-m", "alt", "-m", "ctrl")
            settled(lambda d: not d["undo"])
            assert config.read_bytes() == original and not include.exists()
            if recording:
                time.sleep(1.5)
                stop(recorder, signal.SIGINT)
                recorder = None
            session.capture("gtk-restored")

            # A close hides immediately but must let a pending transaction finish.
            action("review")
            settled(lambda d: d["canApply"])
            (root / "delay").touch()
            action("apply")
            wait_for((root / "started").exists, "delayed apply")
            session.msg("action", "close-window", "--id", str(window["id"]))
            time.sleep(0.15)
            assert process.poll() is None, "Closing terminated an active transaction"
            assert process.wait(timeout=15) == 0
            assert include.exists(), "Pending apply did not finish"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "niri_fx",
                    "restore",
                    "--state",
                    session.env["NIRIFX_STATE"],
                    "--apply",
                ],
                cwd=ROOT,
                env=session.env,
                check=True,
                capture_output=True,
                timeout=15,
            )
            assert config.read_bytes() == original and not include.exists()
            output = (root / "gtk-picker.log").read_text()
            assert not any(
                s in output for s in ("JS ERROR", "CRITICAL", "TypeError", "ReferenceError")
            ), output
            session.check_render_log()
            if recording:
                dest = ROOT / "docs/gifs/workflow-gtk-picker.gif"
                encode_gif(video, dest, width=1000, fps=20)
                save_clips(
                    [
                        {
                            "name": "workflow-gtk-picker",
                            "backend": "packaged GTK 4 picker UI in stock nested Niri",
                            "version": subprocess.check_output(
                                [gjs, "--version"], text=True
                            ).strip(),
                            "checks": [
                                "keyboard search and selection",
                                "read-only review",
                                "reviewed apply",
                                "exact undo",
                                "resize preserved",
                                "close during apply",
                            ],
                            "sources": source_hashes(
                                "niri_fx/gtk/controller.mjs",
                                "niri_fx/gtk/transport.mjs",
                                "niri_fx/gtk/picker.mjs",
                                "niri_fx/gtk/picker.css",
                                "scripts/fixtures/gtk-host.mjs",
                            ),
                            "file": str(dest.relative_to(ROOT)),
                            "bytes": dest.stat().st_size,
                        }
                    ]
                )
            print(f"PASS GTK keyboard flow and close during apply. Evidence: {root}")
        finally:
            if recorder:
                stop(recorder, signal.SIGINT)


def ags_check(ags):
    with NestedSession(BASE, width=1200, height=900) as session:
        # AGS starts GJS beside its entry file, outside the Python source root.
        # An installed niri-fx executable needs no source-checkout override.
        session.env["PYTHONPATH"] = str(ROOT)
        session.env.update(
            environment(session.root, session.config), NIRIFX_GTK_DIR=str(ROOT / "niri_fx/gtk")
        )
        process = session.launch(
            [ags, "run", str(ROOT / "integrations/ags/app.js")], "ags-picker", private_bus=True
        )
        window = show_window(session)
        include = session.config.parent / "nirifx/animations.kdl"
        time.sleep(1)
        keyboard(session, "f")
        session.keys("explosion")
        session.keys("-k", "Return")
        keyboard(session, "r")
        time.sleep(1)
        session.capture("ags-reviewed")
        assert session.config.read_text() == BASE and not include.exists()
        keyboard(session, "Return")
        wait_for(include.exists, "AGS apply")
        assert include.read_text().endswith(render_kdl(PRESETS["explosion"]))
        time.sleep(1)
        session.capture("ags-applied")
        session.keys("-M", "ctrl", "-M", "alt", "-k", "u", "-m", "alt", "-m", "ctrl")
        wait_for(lambda: not include.exists() and session.config.read_text() == BASE, "AGS Undo")
        time.sleep(0.5)
        session.msg("action", "close-window", "--id", str(window["id"]))
        assert process.wait(timeout=15) == 0
        output = (session.root / "ags-picker.log").read_text()
        assert not any(
            s in output for s in ("JS ERROR", "CRITICAL", "TypeError", "ReferenceError")
        ), output
        session.check_render_log()
        print(
            f"PASS AGS entry point, keyboard apply, Undo and clean exit. Evidence: {session.root}"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gjs", default="gjs")
    parser.add_argument("--ags", help="Also test this AGS 3 executable")
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    for executable in (args.gjs, "niri", "wtype", *([args.ags] if args.ags else [])):
        if not shutil.which(executable):
            parser.error(f"Requires {executable}")
    controller_check(args.gjs)
    view_check(args.gjs, args.record)
    if args.ags:
        ags_check(args.ags)


if __name__ == "__main__":
    main()
