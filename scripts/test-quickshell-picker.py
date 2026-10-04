#!/usr/bin/env python3
"""Exercise the packaged Quickshell controller/view with real CLI transactions.

Default: private offscreen Qt and temporary configs. --record: keyboard-driven
happy path in an owned nested Niri output, followed by the same conflict checks.
Studio dispatch is captured by a test executable; it never launches a browser.
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
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.nested import NestedSession, encode_gif, record, save_clips, source_hashes, stop, wait_for

from niri_fx.catalog import STYLES
from niri_fx.documents import load_document, parse_document
from niri_fx.effects import render_kdl

BASE = """hotkey-overlay { skip-at-startup; }
input { keyboard { repeat-rate 0; }; }
layout { background-color "#11171c"; gaps 18; }
animations { window-resize { duration-ms 170; curve "ease-out-cubic"; }; }
"""


@contextmanager
def offscreen():
    with tempfile.TemporaryDirectory(prefix="nirifx-picker-") as directory:

        class Session:
            pass

        session = Session()
        session.root = Path(directory)
        session.env = os.environ.copy()
        for key in ("WAYLAND_DISPLAY", "DISPLAY", "NIRI_SOCKET", "DBUS_SESSION_BUS_ADDRESS"):
            session.env.pop(key, None)
        for key, folder in (
            ("HOME", "home"),
            ("XDG_RUNTIME_DIR", "runtime"),
            ("XDG_CONFIG_HOME", "config"),
            ("XDG_STATE_HOME", "state"),
            ("XDG_CACHE_HOME", "cache"),
            ("XDG_DATA_HOME", "data"),
        ):
            location = session.root / folder
            location.mkdir(mode=0o700)
            session.env[key] = str(location)
        session.env["QT_QPA_PLATFORM"] = "offscreen"
        session.config = session.root / "config/niri/config.kdl"
        session.config.parent.mkdir()
        session.config.write_text(BASE)
        yield session


def exercise(session, recording):
    config, root = session.config, session.root
    original = config.read_bytes()
    include = config.parent / "nirifx/animations.kdl"
    state = root / "state/niri-fx/quickshell"
    qml = root / "picker.qml"
    shutil.copyfile(ROOT / "scripts/fixtures/picker-host.qml", qml)
    (root / "components").symlink_to(ROOT / "niri_fx/qml", target_is_directory=True)
    studio_log = root / "studio.json"
    wrapper = root / "command.py"
    wrapper.write_text(
        "import json,os,sys\n"
        f"os.chdir({str(ROOT)!r})\n"
        "if sys.argv[1] == 'studio':\n"
        f" with open({str(studio_log)!r},'w') as stream: json.dump(sys.argv[1:],stream)\n"
        "else:\n"
        f" os.execv({sys.executable!r},[{sys.executable!r},'-m','niri_fx',*sys.argv[1:]])\n"
    )
    command = [sys.executable, str(wrapper)]
    session.env.update(
        NIRIFX_COMMAND=json.dumps(command),
        NIRIFX_CONFIG=str(config),
        NIRIFX_STATE=str(state),
        QT_QUICK_CONTROLS_STYLE="Basic",
    )
    log_file = root / "picker.log"
    log = log_file.open("w")
    # No activation services: never launch the host shell or portal daemons.
    bus = root / "picker-bus.conf"
    bus.write_text(
        "<busconfig><type>session</type><listen>unix:tmpdir=/tmp</listen>"
        '<auth>EXTERNAL</auth><policy context="default">'
        '<allow send_destination="*"/><allow receive_sender="*"/>'
        '<allow own="*"/></policy></busconfig>'
    )
    process = subprocess.Popen(
        ["dbus-run-session", "--config-file", str(bus), "qs", "-p", str(qml)],
        env=session.env,
        stdout=log,
        stderr=log,
        start_new_session=True,
    )
    recorder = video = None

    def ipc(*args):
        return subprocess.check_output(
            ["qs", "ipc", "-p", str(qml), "call", "test", *args],
            env=session.env,
            text=True,
            stderr=subprocess.PIPE,
            timeout=10,
        )

    def info():
        if process.poll() is not None:
            raise RuntimeError(log_file.read_text())
        try:
            return json.loads(ipc("info"))
        except subprocess.CalledProcessError:
            return {}

    def settled(predicate=lambda data: True):
        return wait_for(
            lambda: (
                (data if data and not data["busy"] and predicate(data) else None)
                if (data := info())
                else None
            ),
            "picker operation",
            30,
        )

    def action(name, value=""):
        ipc("action", name, value)
        return settled()

    def key(letter):
        session.keys("-M", "ctrl", "-k", letter, "-m", "ctrl")

    try:
        data = settled(
            lambda data: data["count"] == len(STYLES) and "Checking" not in data["undoStatus"]
        )
        assert not data["review"] and not data["canApply"] and not data["undo"]
        assert config.read_bytes() == original and not include.exists()
        if recording:
            window = wait_for(
                lambda: next((w for w in session.windows() if w["title"] == "NiriFX Picker"), None),
                "picker window",
            )
            for name, value in (
                ("move-window-to-floating", None),
                ("set-window-width", "1120"),
                ("set-window-height", "850"),
            ):
                session.msg("action", name, "--id", str(window["id"]), *([value] if value else []))
            time.sleep(0.5)
            recorder, video = record(session, "workflow-quickshell-picker")
            time.sleep(1)
            session.focus()
            session.keys(
                "-M", "ctrl", "-k", "f", "-k", "a", "-m", "ctrl", "fragment-flow", "-k", "Return"
            )
            settled(lambda d: d["selected"] == "fragment-flow")
            time.sleep(1)
            key("r")
        else:
            data = action("query", "fragment-flow")
            assert any(row["id"] == "fragment-flow" for row in data["items"])
            action("select", "fragment-flow")
            action("review")
        data = settled(lambda d: d["canApply"])
        assert len(data["review"]["changes"]) == 2
        assert config.read_bytes() == original and not include.exists()
        if recording:
            time.sleep(1.5)
            session.capture("picker-review")
            key("Return")
        else:
            action("apply")
        data = settled(lambda d: bool(d["undo"]))
        assert include.read_text().endswith(render_kdl(STYLES["fragment-flow"]))
        assert "window-resize" not in include.read_text()
        assert config.read_bytes().startswith(original)
        if recording:
            time.sleep(1.5)
            session.keys("-M", "ctrl", "-M", "alt", "-k", "u", "-m", "alt", "-m", "ctrl")
        else:
            action("undo")
        settled(lambda d: not d["undo"])
        assert config.read_bytes() == original and not include.exists()
        if recording:
            time.sleep(1.5)
            session.capture("picker-restored")
            stop(recorder, signal.SIGINT)
            recorder = None

        # Desktop timing must be reviewed alongside the independent actions.
        action("select", "gentle-motion")
        data = action("review")
        assert data["canApply"] and data["review"]["desktop_motion"]["camera"]["stiffness"] == 450
        action("apply")
        settled(lambda d: bool(d["undo"]))
        assert include.read_text().endswith(render_kdl(STYLES["gentle-motion"]))
        assert "window-resize" not in include.read_text()
        action("undo")
        settled(lambda d: not d["undo"])
        assert config.read_bytes() == original and not include.exists()
        action("select", "fragment-flow")
        # Filtering and selecting are read-only; arbitrary IDs cannot reach CLI.
        action("query", "")
        data = action("family", "fragments")
        assert data["items"] and all("fragments" in row["families"] for row in data["items"])
        action("family", "")
        data = action("select", "../../invalid")
        assert data["selected"] == "fragment-flow" and "Unknown style" in data["error"]
        action("select", "balanced")
        action("openStudio")
        wait_for(studio_log.exists, "Studio dispatch")
        assert json.loads(studio_log.read_text()) == [
            "studio",
            "--target",
            "standalone",
            "--preset",
            "balanced",
        ]
        assert config.read_bytes() == original and not include.exists()

        # Load actual public profiles via a percent-encoded file URL.
        document = root / "home/Style with spaces.json"
        shutil.copyfile(ROOT / "examples/profiles/elastic-resize.json", document)
        data = action("loadUrl", document.as_uri())
        assert not data["selected"] and data["document"]["kind"] == "profile"
        assert data["changesResize"] and not data["allowResize"]
        data = action("review")
        assert data["review"] and not data["canApply"]
        action("apply")
        assert config.read_bytes() == original and not include.exists()
        action("resize", "true")
        action("apply")
        settled(lambda d: bool(d["undo"]))
        assert include.read_text().endswith(render_kdl(parse_document(load_document(document))[2]))
        action("undo")
        settled(lambda d: not d["undo"])
        assert config.read_bytes() == original and not include.exists()
        action("openStudio")
        wait_for(
            lambda: "--custom" in json.loads(studio_log.read_text()), "profile Studio dispatch"
        )
        assert json.loads(studio_log.read_text())[-1] == str(document)

        # A bad import keeps the previous selection, but discards its review.
        invalid = root / "invalid.json"
        invalid.write_text('{"schema":999}')
        data = action("load", str(invalid))
        assert data["error"] and data["document"]["name"] == load_document(document)["name"]
        assert not data["review"]
        action("select", "custom")
        assert not info()["allowResize"]

        # Changing a JSON after review cannot silently apply different effects.
        action("review")
        action("resize", "true")
        changed = load_document(document)
        changed["actions"]["open"]["particles"] = 300
        document.write_text(json.dumps(changed))
        data = action("apply")
        assert "plan changed" in data["error"]
        assert config.read_bytes() == original and not include.exists()
        data = action("review")
        assert "changed since loading" in data["error"] and not data["canApply"]
        action("select", "balanced")
        action("review")
        edited = original + b"// External config edit\n"
        config.write_bytes(edited)
        data = action("apply")
        assert "plan changed" in data["error"] and config.read_bytes() == edited
        assert not include.exists()
        config.write_bytes(original)

        # Consecutive transactions undo newest-first; a no-op creates no snapshot.
        action("review")
        action("apply")
        settled(lambda d: bool(d["undo"]))
        first = include.read_bytes()
        data = action("review")
        assert not data["review"]["changes"] and not data["canApply"]
        action("select", "fragment-flow")
        action("review")
        action("apply")
        settled(lambda d: bool(d["undo"]))
        action("undo")
        settled(lambda d: bool(d["undo"]))
        assert include.read_bytes() == first
        config.write_bytes(config.read_bytes() + b"// External edit after apply\n")
        before = config.read_bytes()
        data = action("undo")
        assert "File changed" in data["error"] and not data["undo"]
        assert config.read_bytes() == before and include.read_bytes() == first
        config.write_bytes(before.removesuffix(b"// External edit after apply\n"))
        action("refreshUndo")
        action("undo")
        settled(lambda d: not d["undo"])
        assert config.read_bytes() == original and not include.exists()

        # A missing executable must recover from busy without a writer timeout.
        action("command", json.dumps({"argv": [str(root / "missing-command")]}))
        data = action("reload")
        assert "Cannot start" in data["error"] and not data["busy"]
        data = action("command", json.dumps({"argv": command}))
        assert data["command"] == command, data["command"]
        action("reload")
        settled(lambda d: d["count"] == len(STYLES) and not d["error"])
        output = log_file.read_text()
        assert not any(
            error in output
            for error in (
                "ReferenceError",
                "TypeError",
                "Binding loop",
                "Failed to load configuration",
                "Cannot open:",
            )
        ), output
        return video
    except BaseException:
        print(log_file.read_text(), file=sys.stderr)
        print(
            {
                key: value
                for key, value in info().items()
                if key not in ("items", "document", "review")
            },
            file=sys.stderr,
        )
        raise
    finally:
        if recorder:
            stop(recorder, signal.SIGINT)
        stop(process)
        log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    for executable in ("qs", "niri"):
        if not shutil.which(executable):
            parser.error(f"Requires {executable}")
    with NestedSession(BASE, width=1200, height=900) if args.record else offscreen() as session:
        video = exercise(session, args.record)
        if args.record:
            session.check_render_log()
            dest = ROOT / "docs/gifs/workflow-quickshell-picker.gif"
            encode_gif(video, dest, width=1000, fps=20)
            save_clips(
                [
                    {
                        "name": "workflow-quickshell-picker",
                        "backend": "packaged Quickshell picker UI in stock nested Niri",
                        "version": subprocess.check_output(["qs", "--version"], text=True).strip(),
                        "checks": [
                            "keyboard search and selection",
                            "read-only review",
                            "reviewed apply",
                            "exact undo",
                            "resize preserved",
                        ],
                        "sources": source_hashes(
                            "niri_fx/qml/NiriFXController.qml",
                            "niri_fx/qml/NiriFXPicker.qml",
                            "scripts/fixtures/picker-host.qml",
                        ),
                        "file": str(dest.relative_to(ROOT)),
                        "bytes": dest.stat().st_size,
                    }
                ]
            )
        print(
            "PASS: picker search, review, apply, profiles, resize consent, exact Undo, stale-plan and external-edit refusal, Studio dispatch, missing-command recovery"
        )
        if args.record:
            print(f"Evidence: {session.root}")


if __name__ == "__main__":
    main()
