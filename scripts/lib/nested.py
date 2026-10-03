"""Owned nested Niri sessions for synthetic acceptance tests and recordings.

Only the newly launched compositor's output may be captured or receive input.
Clients get fresh HOME/XDG directories and shells get a private D-Bus session.
Evidence stays in artifacts; process groups and runtime sockets are cleaned up.
"""

import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def wait_for(predicate, description, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.05)
    raise RuntimeError(f"Timed out waiting for {description}")


def stop(process, sig=signal.SIGTERM):
    try:
        os.killpg(process.pid, sig)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


class NestedSession:
    def __init__(self, config, *, binary="niri", width=1440, height=900):
        self.binary = str(binary)
        self.host = os.environ.copy()
        if not self.host.get("WAYLAND_DISPLAY") or not self.host.get("NIRI_SOCKET"):
            raise RuntimeError("Run inside Niri; this harness only launches a nested window")
        (ROOT / "artifacts").mkdir(exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="scenario-", dir=ROOT / "artifacts"))
        self.runtime = tempfile.TemporaryDirectory(prefix="nirifx-scenario-")
        self.config = self.root / "config/niri/config.kdl"
        self.config.parent.mkdir(parents=True)
        self.config.write_text(config)
        self.width, self.height = width, height
        self.processes = []
        self.logs = []
        self.env = None

    def __enter__(self):
        try:
            subprocess.run(
                [self.binary, "validate", "-c", str(self.config)],
                check=True,
                capture_output=True,
                timeout=10,
            )
            parent = self.host.copy()
            for key in ("DISPLAY", "NIRI_SOCKET"):
                parent.pop(key, None)
            # Readiness comes from Niri's INFO socket announcements. A desktop
            # RUST_LOG=warn must not hide those messages and cause a false timeout.
            parent["RUST_LOG"] = "warn,niri=info"
            self.compositor = self.launch([self.binary, "-c", str(self.config)], "niri", env=parent)

            def sockets():
                if self.compositor.poll() is not None:
                    raise RuntimeError(f"Nested Niri exited; see {self.root / 'niri.log'}")
                log = (self.root / "niri.log").read_text()
                ipc = re.search(r"IPC listening on: (\S+)", log)
                display = re.search(r"listening on Wayland socket: (\S+)", log)
                return (ipc[1], display[1]) if ipc and display else None

            ipc, display = wait_for(sockets, "nested sockets")
            if ipc == self.host["NIRI_SOCKET"] or display == self.host["WAYLAND_DISPLAY"]:
                raise RuntimeError("Refusing to use the parent compositor")
            (Path(self.runtime.name) / display).symlink_to(
                Path(self.host["XDG_RUNTIME_DIR"]) / display
            )
            self.env = self.host | {
                "NIRI_SOCKET": ipc,
                "WAYLAND_DISPLAY": display,
                "XDG_RUNTIME_DIR": self.runtime.name,
                "XDG_CURRENT_DESKTOP": "niri",
                "QT_QPA_PLATFORM": "wayland",
            }
            for key in ("DISPLAY", "DBUS_SESSION_BUS_ADDRESS", "HYPRLAND_INSTANCE_SIGNATURE"):
                self.env.pop(key, None)
            for key, folder in (
                ("HOME", "home"),
                ("XDG_CONFIG_HOME", "config"),
                ("XDG_STATE_HOME", "state"),
                ("XDG_DATA_HOME", "data"),
                ("XDG_CACHE_HOME", "cache"),
            ):
                path = self.root / folder
                path.mkdir(exist_ok=True, mode=0o700)
                self.env[key] = str(path)
            # No session activation services: an isolated test must not launch
            # desktop daemons into the user's real graphical session.
            self.bus = self.root / "bus.conf"
            self.bus.write_text(
                "<busconfig><type>session</type><listen>unix:tmpdir=/tmp</listen>"
                '<auth>EXTERNAL</auth><policy context="default">'
                '<allow send_destination="*" eavesdrop="true"/>'
                '<allow receive_sender="*" eavesdrop="true"/>'
                '<allow own="*"/></policy></busconfig>'
            )

            def outer_window():
                windows = json.loads(
                    subprocess.check_output(
                        ["niri", "msg", "-j", "windows"], env=self.host, text=True, timeout=10
                    )
                )
                return next((w for w in windows if w["pid"] == self.compositor.pid), None)

            outer = wait_for(outer_window, "owned outer window")
            self.outer_id = outer["id"]
            for action in (
                ("move-window-to-floating",),
                ("set-window-width", str(self.width)),
                ("set-window-height", str(self.height)),
                # An occluded winit window can wait for host frame callbacks,
                # stalling both rendering and IPC. Raise only our owned window.
                ("focus-window",),
            ):
                subprocess.run(
                    ["niri", "msg", "action", action[0], "--id", str(outer["id"]), *action[1:]],
                    env=self.host,
                    check=True,
                    capture_output=True,
                    timeout=10,
                )
            time.sleep(0.5)
            self.outputs = json.loads(self.msg("-j", "outputs"))
            if list(self.outputs) != ["winit"]:
                raise RuntimeError("Expected only the isolated winit output")
            self.version = subprocess.check_output(
                [self.binary, "--version"], text=True, timeout=10
            ).strip()
            (self.root / "session.json").write_text(
                json.dumps(
                    {
                        "pid": self.compositor.pid,
                        "socket": ipc,
                        "display": display,
                        "version": self.version,
                        "outputs": self.outputs,
                    },
                    indent=2,
                )
                + "\n"
            )
            return self
        except BaseException as error:
            self.__exit__(type(error), error, error.__traceback__)
            raise

    def launch(self, command, name, *, env=None, private_bus=False):
        if private_bus:
            command = ["dbus-run-session", "--config-file", str(self.bus), *command]
        log = (self.root / f"{name}.log").open("w")
        self.logs.append(log)
        process = subprocess.Popen(
            command, env=env or self.env, stdout=log, stderr=log, start_new_session=True
        )
        self.processes.append(process)
        return process

    def msg(self, *args):
        return subprocess.check_output(
            [self.binary, "msg", *args], env=self.env, text=True, timeout=10
        )

    def windows(self):
        return json.loads(self.msg("-j", "windows"))

    def capture(self, name):
        dest = self.root / f"{name}.png"
        subprocess.run(["grim", "-o", "winit", str(dest)], env=self.env, check=True, timeout=10)
        return dest

    def focus(self):
        """Raise only this session's outer window before a timed recording."""
        subprocess.run(
            ["niri", "msg", "action", "focus-window", "--id", str(self.outer_id)],
            env=self.host,
            check=True,
            capture_output=True,
            timeout=10,
        )

    def keys(self, *args):
        subprocess.run(["wtype", *args], env=self.env, check=True, timeout=15)

    def reload(self, config):
        self.config.write_text(config)
        subprocess.run(
            [self.binary, "validate", "-c", str(self.config)],
            check=True,
            capture_output=True,
            timeout=10,
        )
        self.msg("action", "load-config-file")
        time.sleep(0.2)

    def check_render_log(self):
        """Treat compositor errors as failures, including shader compile failures."""
        log = (self.root / "niri.log").read_text()
        # A WARN from smithay::backend::egl::error is not an ERROR record.
        # Match the log level as a whitespace-delimited field, not a module name.
        if re.search(r"(?:^|\s)ERROR(?:\s|$)|panicked at|error compiling|error linking", log, re.I):
            raise RuntimeError(f"Compositor reported errors; inspect {self.root / 'niri.log'}")

    def __exit__(self, exc_type, *_):
        failures = []
        try:
            for process in reversed(self.processes):
                try:
                    stop(process)
                except (OSError, subprocess.TimeoutExpired) as error:
                    failures.append(error)
        finally:
            for log in self.logs:
                log.close()
            self.runtime.cleanup()
        if failures:
            # Do not mask an acceptance failure, but report incomplete cleanup.
            if exc_type is None:
                raise RuntimeError(f"Could not stop all owned clients: {failures}")
            print(f"Cleanup failures: {failures}", file=sys.stderr)


def source_hashes(*paths):
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}


def encode_gif(source, dest, width=800, crop=None, fps=20, colors=96):
    """Encode only an owned video; scaling/palette reduction is presentation, not evidence."""
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(source),
            "-filter_complex",
            (f"crop={crop}," if crop else "")
            + f"fps={fps},scale={width}:-1:flags=lanczos,split[a][b];"
            f"[a]palettegen=max_colors={colors}:stats_mode=full[p];[b][p]paletteuse=dither=none",
            "-loop",
            "0",
            str(dest),
        ],
        check=True,
        timeout=120,
    )


def save_clips(clips):
    path = ROOT / "docs/gifs/scenario-manifest.json"
    previous = json.loads(path.read_text())["clips"] if path.exists() else []
    names = {clip["name"] for clip in clips}
    path.write_text(
        json.dumps({"clips": [c for c in previous if c["name"] not in names] + clips}, indent=2)
        + "\n"
    )


def record(session, name, fps=20):
    session.focus()
    video = session.root / f"{name}.mkv"
    process = session.launch(
        [
            "wf-recorder",
            "-o",
            "winit",
            *(["-r", str(fps)] if fps is not None else []),
            "--no-damage",
            "-c",
            "libx264",
            "-p",
            "crf=16",
            "-f",
            str(video),
        ],
        "recorder",
    )

    # Matroska may buffer the first cluster until stop; file size is not a
    # readiness signal. The encoder announces its output after initialization.
    def ready():
        if process.poll() is not None:
            raise RuntimeError(f"Recorder exited; inspect {session.root / 'recorder.log'}")
        return "Output #0" in (session.root / "recorder.log").read_text()

    wait_for(ready, "recorder startup")
    if process.poll() is not None:
        raise RuntimeError(f"Recorder exited; inspect {session.root / 'recorder.log'}")
    return process, video
