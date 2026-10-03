"""Read-only movement diagnostics, separate from effect and export capabilities.

A version string cannot distinguish stock Niri from a patched build. Validate a
small isolated config instead, and only attribute that result to a running
session when its IPC peer is the same executable. Parser acceptance says nothing
about shader compilation, the movement ABI or which effects are active.
"""

import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
from pathlib import Path

PROBE_TIMEOUT = 5
IPC_TIMEOUT = 2
MAX_REPLY = 8192
BASE_CONFIG = "animations { window-movement { duration-ms 200; %s }; }\n"
SHADER_NODE = 'custom-shader "vec4 move_color(vec3 c, vec3 s) { return vec4(0.0); }";'


def _identity(path):
    """Compare executables, including a replaced/deleted running binary."""
    stat = os.stat(path)
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def _probe(binary):
    # The baseline separates a missing config node or broken executable from a
    # specific rejection of custom-shader. Neither config touches the desktop.
    try:
        with tempfile.TemporaryDirectory(prefix="nirifx-capability-") as directory:
            path = Path(directory) / "probe.kdl"
            for shader in ("", SHADER_NODE):
                path.write_text(BASE_CONFIG % shader)
                result = subprocess.run(
                    [binary, "validate", "-c", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=PROBE_TIMEOUT,
                    env=os.environ | {"NO_COLOR": "1"},
                )
                if result.returncode:
                    if shader and "unexpected node `custom-shader`" in result.stderr:
                        return "unsupported", "Rejects custom-shader in window-movement."
                    return "unknown", "Could not validate the isolated movement config."
    except (OSError, subprocess.SubprocessError) as error:
        return "unknown", f"Movement config probe failed: {error}"
    return "supported", "Accepts custom-shader in window-movement (parser check only)."


def _session(socket_path, identity):
    result = {"connected": False, "version": None, "same_binary": None}
    if not socket_path:
        return result | {"detail": "No Niri socket advertised; offline/SSH preview is available."}
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(IPC_TIMEOUT)
            connection.connect(socket_path)
            # Ask the kernel, never infer a PID from the socket filename. Only
            # inspect /proc; do not execute a binary discovered through IPC.
            pid, uid, _ = struct.unpack(
                "3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            )
            if uid != os.geteuid():
                return result | {"detail": "IPC socket belongs to another user; not inspected."}
            connection.sendall(b'"Version"\n')
            reply = bytearray()
            deadline = time.monotonic() + IPC_TIMEOUT
            while b"\n" not in reply:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("IPC version reply timed out")
                connection.settimeout(remaining)
                chunk = connection.recv(min(4096, MAX_REPLY + 1 - len(reply)))
                if not chunk or len(reply) + len(chunk) > MAX_REPLY:
                    raise ValueError("incomplete or oversized IPC version reply")
                reply.extend(chunk)
            version = json.loads(reply.split(b"\n", 1)[0])["Ok"]["Version"]
            if not isinstance(version, str) or not version.strip():
                raise ValueError("invalid IPC version reply")
            result.update(connected=True, version=version)
            try:
                result["same_binary"] = (
                    _identity(f"/proc/{pid}/exe") == identity if identity is not None else None
                )
            except OSError:
                pass  # Sandboxed /proc or an exited peer is unknown, not a match.
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        return result | {"detail": f"Could not inspect the advertised Niri session: {error}"}
    return result | {"detail": f"Connected to Niri {version}."}


def movement_capability(binary=None, *, socket_path=None):
    """Inspect the selected binary and optionally a session, without activation.

    Callers pass the socket explicitly so offline rendering never queries the
    desktop. A different running executable remains unknown, even if its version
    matches; only the selected executable is ever run, using `validate`.
    """
    requested = str(Path(binary).expanduser().absolute()) if binary is not None else "niri"
    selected = shutil.which(requested)
    status, detail = "unknown", f"Movement probe binary not found: {requested}"
    identity = None
    if selected:
        selected = os.path.abspath(selected)
        try:
            identity = _identity(selected)
            status, detail = _probe(selected)
            if identity != _identity(selected):
                identity = None
                status, detail = "unknown", "Binary changed during the movement config probe."
        except OSError as error:
            identity = None
            status, detail = "unknown", f"Could not inspect the movement binary: {error}"
    session = _session(socket_path, identity)
    session["status"] = status if session["same_binary"] is True else "unknown"
    if session["same_binary"] is True:
        session["detail"] += f" Same executable as the movement probe: {status}."
    elif session["same_binary"] is False:
        session["detail"] += " Different executable from the movement probe; support is unknown."
    elif session["connected"]:
        session["detail"] += " Executable identity unavailable; support is unknown."
    return {
        "binary": selected,
        "status": status,
        "scope": "configuration-parser",
        "detail": detail,
        "session": session,
    }
