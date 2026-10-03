#!/usr/bin/env python3
"""Record only the isolated, synthetic two-window Niri demo as a looping GIF."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    if not os.environ.get("NIRI_SOCKET") or not os.environ.get("WAYLAND_DISPLAY"):
        raise SystemExit("Run from a Niri desktop with the experimental build already prepared")
    (ROOT / "artifacts").mkdir(exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="native-gif-", dir=ROOT / "artifacts"))
    recorder = None
    with (scratch / "launcher.log").open("w") as log:
        demo = subprocess.Popen([sys.executable, str(ROOT / "scripts/nested-demo.py"),
                                 "--duration-ms", "1200"], cwd=ROOT, stdout=log, stderr=log,
                                start_new_session=True)
        nested_pid = None
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                text = (scratch / "launcher.log").read_text()
                match = re.search(r"Logs: (.+)", text)
                if match:
                    session = json.loads((Path(match[1]) / "session.json").read_text())
                    nested_pid = session["pid"]
                    break
                if demo.poll() is not None:
                    raise RuntimeError(text)
                time.sleep(0.1)
            else:
                raise RuntimeError("Nested demo startup timed out")
            host = os.environ.copy()
            nested = host | {"NIRI_SOCKET": session["socket"], "WAYLAND_DISPLAY": session["display"]}
            if nested["NIRI_SOCKET"] == host["NIRI_SOCKET"] or nested["WAYLAND_DISPLAY"] == host["WAYLAND_DISPLAY"]:
                raise RuntimeError("Refusing to record the parent desktop")

            def msg(env, *args):
                return subprocess.check_output(["niri", "msg", *args], env=env, text=True)

            # Change only the newly created nested window, never a user's app.
            for _ in range(100):
                windows = json.loads(msg(host, "-j", "windows"))
                outer = next((w for w in windows if w["pid"] == nested_pid), None)
                if outer:
                    break
                time.sleep(0.1)
            if not outer:
                raise RuntimeError("Nested compositor window is missing")
            identifier = str(outer["id"])
            msg(host, "action", "move-window-to-floating", "--id", identifier)
            msg(host, "action", "set-window-width", "--id", identifier, "1280")
            msg(host, "action", "set-window-height", "--id", identifier, "800")
            time.sleep(2)
            windows = json.loads(msg(nested, "-j", "windows"))
            if len(windows) != 2 or not all(w["title"].startswith("Fragments demo /") for w in windows):
                raise RuntimeError("Refusing to record unexpected nested clients")
            right = max(windows, key=lambda w: w["layout"]["pos_in_scrolling_layout"][0])
            msg(nested, "action", "focus-window", "--id", str(right["id"]))
            video = scratch / "swap.mkv"
            with (scratch / "recorder.log").open("w") as record_log:
                recorder = subprocess.Popen(["wf-recorder", "-o", "winit", "-r", "20", "--no-damage",
                    "-c", "libx264", "-p", "crf=16", "-f", str(video)], env=nested,
                    stdout=record_log, stderr=record_log)
                time.sleep(0.8)
                if recorder.poll() is not None:
                    raise RuntimeError((scratch / "recorder.log").read_text())
                msg(nested, "action", "move-column-left")
                time.sleep(2)
                msg(nested, "action", "move-column-right")
                time.sleep(2)
                recorder.send_signal(signal.SIGINT)
                recorder.wait(timeout=10)
                recorder = None
            dest = ROOT / "docs/gifs/native-swap.gif"
            dest.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-filter_complex",
                "fps=20,scale=560:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=full[p];[b][p]paletteuse=dither=none:diff_mode=rectangle",
                "-loop", "0", str(dest)], check=True)
            print(f"Recorded {dest} ({dest.stat().st_size // 1024} KiB)\nSource video: {video}")
        finally:
            if recorder and recorder.poll() is None:
                recorder.send_signal(signal.SIGINT)
                try:
                    recorder.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    recorder.kill()
                    recorder.wait(timeout=5)
            # This isolated process group contains only our demo and clients,
            # including when startup fails before session.json can be read.
            if demo.poll() is None:
                try:
                    os.killpg(demo.pid, signal.SIGINT)
                except ProcessLookupError:
                    pass
            try:
                demo.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(demo.pid, signal.SIGKILL)
                demo.wait(timeout=5)


if __name__ == "__main__":
    main()
