"""Read-only native diagnostics, separate from effect and export capabilities.

A version string cannot distinguish stock Niri from a patched build. Validate a
small isolated config instead, and only attribute that result to a running
session when its IPC peer is the same executable. The running renderer must
separately verify the versioned movement contract before live activation.
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
MOVEMENT_CONTRACT = 2
POINTER_NODE = "pointer-wobble { strength 0.7; damping 65; frequency 8; };"


def _reply(connection, request):
    """One bounded IPC reply; a slow peer cannot keep extending the deadline."""
    connection.sendall(json.dumps(request).encode() + b"\n")
    reply = bytearray()
    deadline = time.monotonic() + IPC_TIMEOUT
    while b"\n" not in reply:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("IPC reply timed out")
        connection.settimeout(remaining)
        chunk = connection.recv(min(4096, MAX_REPLY + 1 - len(reply)))
        if not chunk or len(reply) + len(chunk) > MAX_REPLY:
            raise ValueError("incomplete or oversized IPC reply")
        reply.extend(chunk)
    return json.loads(reply.split(b"\n", 1)[0])


def _contract(connection):
    """Verify an advertised ABI and an isolated compile in the running renderer.

    A response from a different interface version is unknown. This query neither
    replaces the active shader nor proves an arbitrary user shader compiles.
    """
    unknown = {"status": "unknown", "detail": "Running movement shader contract is unverified."}
    try:
        data = _reply(connection, "NiriFxCapabilities")["Ok"]["NiriFxCapabilities"]
        if (
            set(data)
            != {
                "schema",
                "movement_shader",
                "renderer_verified",
                "movement_configured",
                "frame_timings",
            }
            or type(data["schema"]) is not int
            or data["schema"] != 1
            or type(data["movement_shader"]) is not int
            or data["movement_shader"] != MOVEMENT_CONTRACT
            or any(
                type(data[key]) is not bool
                for key in ("renderer_verified", "movement_configured", "frame_timings")
            )
        ):
            return unknown
        return {
            **data,
            "status": "verified" if data["renderer_verified"] else "unavailable",
            "detail": "Movement interface compiled in the running renderer."
            if data["renderer_verified"]
            else "The running renderer could not verify the movement interface.",
        }
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return unknown


def _pointer_contract(connection):
    """Require the bounded spring contract, independently of its enabled state.

    A disabled or absent configuration can still be activated after review. The
    renderer and limits must already match; a version string alone is insufficient.
    """
    unknown = {"status": "unknown", "detail": "Running pointer wobble contract is unverified."}
    try:
        data = _reply(connection, "NiriFxPointerCapabilities")["Ok"]["NiriFxPointerCapabilities"]
        integers = {"schema": 1, "pointer_wobble": 2, "max_deformation": 64, "max_release_ms": 2000}
        booleans = {"renderer_verified", "configured", "enabled"}
        if (
            not isinstance(data, dict)
            or set(data) != set(integers) | booleans
            or any(
                type(data[key]) is not int or data[key] != value for key, value in integers.items()
            )
            or any(type(data[key]) is not bool for key in booleans)
            or (data["enabled"] and not data["configured"])
        ):
            return unknown
        return {
            **data,
            "status": "verified" if data["renderer_verified"] else "unavailable",
            "detail": "Pointer wobble compiled in the running renderer."
            if data["renderer_verified"]
            else "The running renderer could not verify pointer wobble.",
        }
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return unknown


def _identity(path):
    """Compare executables, including a replaced/deleted running binary."""
    stat = os.stat(path)
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def _fragment_contract(connection):
    """Check continuous fragments separately from the timed movement interface.

    The generated shader also compiles on older builds using its timed fallback.
    Parser acceptance therefore cannot establish continuous-motion support.
    """
    unknown = {"status": "unknown", "detail": "Running fragment motion contract is unverified."}
    try:
        data = _reply(connection, "NiriFxFragmentCapabilities")["Ok"]["NiriFxFragmentCapabilities"]
        integers = {
            "schema": 1,
            "fragment_motion": 3,
            "max_deformation": 1024,
            "max_release_ms": 2000,
        }
        booleans = {"renderer_verified", "fragment_configured", "fragment_enabled"}
        if (
            not isinstance(data, dict)
            or set(data) != set(integers) | booleans
            or any(
                type(data[key]) is not int or data[key] != value for key, value in integers.items()
            )
            or any(type(data[key]) is not bool for key in booleans)
            or (data["fragment_enabled"] and not data["fragment_configured"])
        ):
            return unknown
        return {
            **data,
            "status": "verified" if data["renderer_verified"] else "unavailable",
            "detail": "Continuous fragment motion compiled in the running renderer."
            if data["renderer_verified"]
            else "The running renderer could not verify continuous fragment motion.",
        }
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return unknown


def _probe(binary, *, node=SHADER_NODE, label="movement", node_name="custom-shader"):
    # The baseline separates a missing config node or broken executable from a
    # specific rejection of custom-shader. Neither config touches the desktop.
    try:
        with tempfile.TemporaryDirectory(prefix="nirifx-capability-") as directory:
            path = Path(directory) / "probe.kdl"
            for shader in ("", node):
                path.write_text(BASE_CONFIG % shader)
                result = subprocess.run(
                    [binary, "validate", "-c", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=PROBE_TIMEOUT,
                    env=os.environ | {"NO_COLOR": "1"},
                )
                if result.returncode:
                    if shader and f"unexpected node `{node_name}`" in result.stderr:
                        return "unsupported", f"Rejects {node_name} in window-movement."
                    return "unknown", f"Could not validate the isolated {label} config."
    except (OSError, subprocess.SubprocessError) as error:
        return "unknown", f"{label.title()} config probe failed: {error}"
    return "supported", f"Accepts {node_name} in window-movement (parser check only)."


def _pointer_probe(binary):
    return _probe(binary, node=POINTER_NODE, label="pointer", node_name="pointer-wobble")


def _session(socket_path, identity, *, contract=_contract, label="movement shader"):
    result = {
        "connected": False,
        "version": None,
        "same_binary": None,
        "contract": {
            "status": "unknown",
            "detail": f"Running {label} contract is unverified.",
        },
    }
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
            version = _reply(connection, "Version")["Ok"]["Version"]
            if not isinstance(version, str) or not version.strip():
                raise ValueError("invalid IPC version reply")
            result.update(connected=True, version=version)
            try:
                result["same_binary"] = (
                    _identity(f"/proc/{pid}/exe") == identity if identity is not None else None
                )
            except OSError:
                pass  # Sandboxed /proc or an exited peer is unknown, not a match.
            if result["same_binary"] is True:
                result["contract"] = contract(connection)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        return result | {"detail": f"Could not inspect the advertised Niri session: {error}"}
    return result | {"detail": f"Connected to Niri {version}."}


def movement_capability(binary=None, *, socket_path=None):
    """Inspect the selected binary and optionally a session, without activation.

    Callers pass the socket explicitly so offline rendering never queries the
    desktop. A different running executable remains unknown, even if its version
    matches; only the selected executable is ever run, using `validate`.
    """
    return _capability(binary, socket_path, "movement", _probe, _contract)


def pointer_capability(binary=None, *, socket_path=None):
    """Probe optional pointer support without touching the active configuration."""
    return _capability(binary, socket_path, "pointer", _pointer_probe, _pointer_contract)


def fragment_capability(binary=None, *, socket_path=None):
    """Inspect the fragment extension without changing or enabling desktop effects."""
    return _capability(binary, socket_path, "fragment motion", _probe, _fragment_contract)


def _capability(binary, socket_path, label, probe, contract):
    requested = str(Path(binary).expanduser().absolute()) if binary is not None else "niri"
    selected = shutil.which(requested)
    status, detail = "unknown", f"{label.title()} probe binary not found: {requested}"
    identity = None
    if selected:
        selected = os.path.abspath(selected)
        try:
            identity = _identity(selected)
            status, detail = probe(selected)
            if identity != _identity(selected):
                identity = None
                status, detail = "unknown", f"Binary changed during the {label} config probe."
        except OSError as error:
            identity = None
            status, detail = "unknown", f"Could not inspect the {label} binary: {error}"
    session = _session(socket_path, identity, contract=contract, label=label)
    session["status"] = status if session["same_binary"] is True else "unknown"
    if session["same_binary"] is True:
        session["detail"] += f" Same executable as the {label} probe: {status}."
    elif session["same_binary"] is False:
        session["detail"] += f" Different executable from the {label} probe; support is unknown."
    elif session["connected"]:
        session["detail"] += " Executable identity unavailable; support is unknown."
    return {
        "binary": selected,
        "status": status,
        "scope": "configuration-parser",
        "detail": detail,
        "session": session,
        "activation_ready": session["status"] == "supported"
        and session["contract"]["status"] == "verified",
    }
