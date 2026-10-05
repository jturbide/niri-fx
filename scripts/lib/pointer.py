"""Virtual pointer input restricted to a live, owned NestedSession.

Motion acknowledgements cover writing to the Wayland socket; buttons and sync
barriers confirm server dispatch. Neither measures input-to-photon latency.
"""

import math
import os
import selectors
import shlex
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from .nested import ROOT, stop


def pointer_protocol(override=None):
    """Find an installed or build-cached protocol without downloading anything."""
    if override is not None:
        candidates = [Path(override)]
    else:
        caches = dict.fromkeys(
            (
                ROOT / "artifacts/toolchain/cargo/registry/src",
                Path(os.environ.get("CARGO_HOME", Path.home() / ".cargo")) / "registry/src",
            )
        )
        candidates = [
            Path("/usr/share/wlr-protocols/unstable/wlr-virtual-pointer-unstable-v1.xml"),
            *(
                path
                for cache in caches
                for path in sorted(
                    cache.glob(
                        "*/wayland-protocols-wlr-*/wlr-protocols/unstable/wlr-virtual-pointer-unstable-v1.xml"
                    )
                )
            ),
        ]
    for path in candidates:
        if path.is_file():
            try:
                root = ET.parse(path).getroot()
            except ET.ParseError as error:
                raise ValueError(f"Invalid virtual pointer protocol XML: {path}") from error
            if (
                root.tag != "protocol"
                or root.attrib.get("name") != "wlr_virtual_pointer_unstable_v1"
            ):
                raise ValueError(f"Not a wlr virtual pointer protocol: {path}")
            if root.find("interface[@name='zwlr_virtual_pointer_manager_v1']") is None:
                raise ValueError(f"Missing virtual pointer manager interface: {path}")
            return path.resolve()
    raise ValueError(
        "Virtual pointer protocol XML was not found. Install wlr-protocols, build the pinned "
        "Niri experiment, or pass --pointer-protocol PATH."
    )


def owned_socket(session):
    """Fail closed before a helper can connect to the user's login compositor."""
    if not session.env or session.compositor.poll() is not None:
        raise ValueError("Pointer input requires a running nested compositor")
    if list(session.outputs) != ["winit"]:
        raise ValueError("Pointer input requires the owned winit output")
    for key in ("NIRI_SOCKET", "WAYLAND_DISPLAY"):
        if not session.env.get(key) or session.env[key] == session.host.get(key):
            raise ValueError("Refusing pointer input on the parent compositor")
    target = (Path(session.env["XDG_RUNTIME_DIR"]) / session.env["WAYLAND_DISPLAY"]).resolve()
    parent = (Path(session.host["XDG_RUNTIME_DIR"]) / session.host["WAYLAND_DISPLAY"]).resolve()
    if target == parent or not target.is_socket():
        raise ValueError("Pointer target is not an owned nested socket")
    return target


def build_pointer(directory, protocol):
    """Generate protocol bindings locally; do not vendor external protocol code."""
    directory = Path(directory)
    directory.mkdir()
    for mode, name in (
        ("client-header", "virtual-pointer.h"),
        ("private-code", "virtual-pointer.c"),
    ):
        subprocess.run(
            ["wayland-scanner", mode, str(Path(protocol).resolve()), str(directory / name)],
            check=True,
            timeout=15,
        )
    flags = shlex.split(
        subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "wayland-client"], text=True, timeout=15
        )
    )
    binary = directory / "pointer"
    subprocess.run(
        [
            "cc",
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(directory),
            str(ROOT / "scripts/fixtures/pointer.c"),
            str(directory / "virtual-pointer.c"),
            "-o",
            str(binary),
            *flags,
        ],
        check=True,
        timeout=30,
    )
    return binary


def path_samples(points, duration, fps=60):
    """Interpolate each path segment on an absolute monotonic schedule."""
    if len(points) < 2 or not math.isfinite(duration) or duration <= 0 or fps <= 0:
        raise ValueError("A path needs two points, a positive duration and positive cadence")
    steps = max(1, math.ceil(duration * fps))
    for step in range(1, steps + 1):
        progress = step / steps * (len(points) - 1)
        segment = min(int(progress), len(points) - 2)
        fraction = progress - segment
        start, end = points[segment], points[segment + 1]
        yield (
            duration * step / steps,
            tuple(round(a + (b - a) * fraction) for a, b in zip(start, end, strict=True)),
        )


class VirtualPointer:
    def __init__(self, session, binary, *, label="pointer"):
        if not label or any(
            character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in label
        ):
            raise ValueError("Pointer log label must use lowercase letters, digits or hyphens")
        socket = owned_socket(session)
        self.session = session
        self.pressed = False
        self.timings = []
        self.selector = selectors.DefaultSelector()
        log = (session.root / f"{label}.log").open("w")
        session.logs.append(log)
        self.process = subprocess.Popen(
            [str(binary), str(socket), str(session.width), str(session.height)],
            env=session.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        session.processes.append(self.process)
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        try:
            if self._read() != "ready":
                raise RuntimeError("Virtual pointer did not become ready")
        except BaseException:
            self.selector.close()
            stop(self.process)
            self.process.stdin.close()
            self.process.stdout.close()
            raise

    def _read(self):
        if not self.selector.select(timeout=3):
            raise RuntimeError("Virtual pointer acknowledgement timed out")
        result = self.process.stdout.readline().strip()
        if not result:
            raise RuntimeError("Virtual pointer disconnected; inspect pointer.log")
        return result

    def command(self, command):
        started = time.monotonic()
        self.process.stdin.write(command + "\n")
        self.process.stdin.flush()
        acknowledgement = self._read()
        if acknowledgement not in ("submitted", "dispatched"):
            raise RuntimeError("Virtual pointer rejected a command")
        elapsed = time.monotonic() - started
        self.timings.append(
            {
                "command": command,
                "acknowledgement_ms": elapsed * 1000,
                "scope": "socket-flush" if acknowledgement == "submitted" else "server-roundtrip",
            }
        )
        return elapsed

    def sync(self):
        """Confirm all previously submitted input was dispatched in order."""
        self.command("sync")

    def move(self, x, y):
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("Pointer coordinates must stay inside the owned output")
        x, y = round(x), round(y)
        if not (0 <= x < self.session.width and 0 <= y < self.session.height):
            raise ValueError("Pointer coordinates must stay inside the owned output")
        self.command(f"motion {x} {y}")

    def press(self):
        self.command("press")
        self.pressed = True

    def release(self):
        self.command("release")
        self.pressed = False

    def click(self, x, y):
        self.move(x, y)
        time.sleep(0.05)
        self.press()
        time.sleep(0.05)
        self.release()

    def path(self, points, duration, fps=60, *, synchronize=True):
        """Send real motion, rejecting a stalled session instead of speeding it up."""
        started = time.monotonic()
        for offset, point in path_samples(points, duration, fps):
            time.sleep(max(0, started + offset - time.monotonic()))
            late = time.monotonic() - started - offset
            if late > 0.1:
                raise RuntimeError("Pointer path missed its schedule by more than 100 ms")
            self.move(*point)
            self.timings[-1]["scheduled_ms"] = offset * 1000
            self.timings[-1]["late_ms"] = late * 1000
        # An immediate release already synchronizes all preceding motion. Avoid
        # spending another compositor roundtrip before a short release tail.
        if synchronize:
            self.sync()

    def close(self):
        try:
            if self.process.poll() is None:
                if self.pressed:
                    self.release()
                self.process.stdin.write("quit\n")
                self.process.stdin.flush()
                self.process.wait(timeout=3)
        finally:
            if self.process.poll() is None:
                stop(self.process)
            self.selector.close()
            self.process.stdin.close()
            self.process.stdout.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
