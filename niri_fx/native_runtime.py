"""Read-only identification of the one advertised Niri IPC session.

Matching its executable and explicit config argument identifies a bundle, not
renderer acceptance, every running session, or permission to remove any bundle.
The observer never executes a discovered program or reads session lease tokens.
"""

import hashlib
import os
import re
import socket
import stat
import struct
from pathlib import Path

from .capabilities import IPC_TIMEOUT, _reply

MAX_CMDLINE_BYTES = 65536
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _process_start(pid):
    with Path(f"/proc/{pid}/stat").open() as stream:
        text = stream.read(4097)
    if len(text) > 4096:
        raise ValueError("Process identity is unavailable")
    fields = text.rsplit(")", 1)[1].split()
    if fields[0] == "Z":
        raise ValueError("The advertised process has exited")
    return int(fields[19])


def _identity(path):
    info = os.stat(path)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Process or bundle file is not a regular file")
    return (
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        stat.S_IMODE(info.st_mode),
    )


def _executable(pid):
    process_path = f"/proc/{pid}/exe"
    binary = os.readlink(process_path)
    if not Path(binary).is_absolute() or binary.endswith(" (deleted)"):
        raise ValueError("The running executable was deleted or cannot be identified")
    identity = _identity(process_path)
    if identity != _identity(binary):
        raise ValueError("The running executable differs from its current filesystem path")
    return binary, identity


def _arguments(pid):
    with Path(f"/proc/{pid}/cmdline").open("rb") as stream:
        data = stream.read(MAX_CMDLINE_BYTES + 1)
    if not data or len(data) > MAX_CMDLINE_BYTES or not data.endswith(b"\0"):
        raise ValueError("Process arguments are unavailable or incomplete")
    return tuple(item.decode("utf-8") for item in data[:-1].split(b"\0"))


def _configuration(arguments):
    """Accept Clap's separate and joined forms, but never guess duplicate values."""
    values, index = [], 1
    while index < len(arguments):
        argument = arguments[index]
        if argument == "--":
            if index + 1 < len(arguments):
                raise ValueError("Process arguments after -- cannot identify a session config")
            break
        if argument in ("--config", "-c"):
            index += 1
            if index == len(arguments):
                raise ValueError("The process config argument has no value")
            values.append(arguments[index])
        elif argument.startswith("--config="):
            values.append(argument[len("--config=") :])
        elif argument.startswith("-c") and not argument.startswith("--"):
            values.append(argument[2:].removeprefix("="))
        elif argument.startswith("--config"):
            raise ValueError("The process config argument is ambiguous")
        index += 1
    if not values:
        return None
    if len(values) != 1 or not Path(values[0]).is_absolute():
        raise ValueError("The process needs exactly one absolute config argument")
    path = Path(values[0])
    if any(component.is_symlink() for component in (path, *path.parents)):
        raise ValueError("A symlinked process config is ambiguous")
    # Preserve OS traversal checks before normalizing any parent components.
    path.stat()
    return os.path.abspath(path)


def _hash_stream(stream, limit):
    value, remaining = hashlib.sha256(), limit + 1
    while remaining:
        chunk = stream.read(min(1024 * 1024, remaining))
        if not chunk:
            return value.hexdigest()
        remaining -= len(chunk)
        value.update(chunk)
    raise ValueError("Bundle file grew beyond the inspection limit")


def _bundle_file(path, expected_hash, limit):
    path = Path(path)
    if not path.is_absolute() or any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("Bundle paths changed or are not absolute")
    identity = _identity(path)
    if identity[2] > limit:
        raise ValueError("Bundle file exceeds its recorded inspection scope")
    if expected_hash is not None:
        if not isinstance(expected_hash, str) or not _SHA256.fullmatch(expected_hash):
            raise ValueError("Bundle file identity is malformed")
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("Bundle file is no longer a regular file")
            current_hash = _hash_stream(stream, limit)
        if current_hash != expected_hash:
            raise ValueError("Bundle contents changed after inspection")
    if _identity(path) != identity:
        raise ValueError("Bundle file changed during session inspection")
    return identity


def inspect_running(bundles, *, socket_path=None):
    """Inspect only the explicitly advertised socket; absence is an offline result."""
    report = {
        "scope": "advertised-ipc-session",
        "status": "offline" if not socket_path else "unknown",
        "bundle_id": None,
        "pid": None,
        "version": None,
        "detail": "No Niri IPC socket was supplied; the running session was not inspected.",
    }
    if not socket_path:
        return report
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(IPC_TIMEOUT)
            connection.connect(str(socket_path))
            pid, uid, _ = struct.unpack(
                "3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
            )
            if pid <= 0 or uid != os.geteuid():
                report["detail"] = "The advertised IPC peer is not owned by this user."
                return report
            report["pid"] = pid
            started = _process_start(pid)
            executable = _executable(pid)
            arguments = _arguments(pid)
            response = _reply(connection, "Version")
            if (
                not isinstance(response, dict)
                or set(response) != {"Ok"}
                or not isinstance(response["Ok"], dict)
                or set(response["Ok"]) != {"Version"}
            ):
                raise ValueError("The advertised IPC peer did not return a Niri version")
            version = response["Ok"]["Version"]
            if (
                not isinstance(version, str)
                or not version.strip()
                or len(version) > 256
                or any(ord(char) < 32 or ord(char) == 127 for char in version)
            ):
                raise ValueError("The advertised IPC version is malformed")
            report["version"] = version
            config = _configuration(arguments)
            config_identity = _identity(config) if config is not None else None
            matches, same_binary, observed = [], False, []
            for bundle in bundles:
                identifier = bundle["bundle_id"]
                if not isinstance(identifier, str) or not _SHA256.fullmatch(identifier):
                    raise ValueError("Bundle identity is malformed")
                binary = str(bundle["binary"])
                binary_identity = _bundle_file(binary, None, 512 * 1024 * 1024)
                observed.append((binary, binary_identity))
                if binary_identity != executable[1]:
                    continue
                if (
                    _bundle_file(binary, bundle.get("binary_sha256"), 512 * 1024 * 1024)
                    != binary_identity
                ):
                    raise ValueError("The matching bundle executable changed during inspection")
                same_binary = True
                bundle_config = str(bundle["config"])
                saved_config_identity = _bundle_file(
                    bundle_config, bundle.get("config_sha256"), 4 * 1024 * 1024
                )
                observed.append((bundle_config, saved_config_identity))
                if (
                    config == os.path.abspath(bundle_config)
                    and config_identity == saved_config_identity
                ):
                    matches.append(identifier)
            if (
                _process_start(pid) != started
                or _executable(pid) != executable
                or _arguments(pid) != arguments
                or (config is not None and _identity(config) != config_identity)
                or any(_identity(path) != identity for path, identity in observed)
            ):
                raise ValueError("The process or bundle metadata changed during inspection")
            report["binary"] = executable[0]
            if config is not None:
                report["config"] = config
            if len(matches) > 1:
                raise ValueError("More than one bundle matches the advertised session")
            if same_binary and config is None:
                raise ValueError("The managed executable has no explicit absolute config argument")
            report.update(
                status="matched" if matches else "external",
                bundle_id=matches[0] if matches else None,
                detail=(
                    "The advertised process executable and config argument match this bundle. "
                    "This does not assess its active renderer or other sessions."
                    if matches
                    else "The advertised process uses an executable/configuration pair outside "
                    "the inspected bundles. Other sessions were not inspected."
                ),
            )
            if matches:
                matched = next(item for item in bundles if item["bundle_id"] == matches[0])
                if matched.get("shared"):
                    report["configuration_mode"] = "shared"
                    report["detail"] = (
                        "The advertised process executable and owned shared-config wrapper "
                        "match this bundle. Shared settings can change; active configuration "
                        "contents and renderer acceptance are not verified."
                    )
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
        # Paths, socket names and raw replies can contain private data. Return a
        # bounded diagnostic instead of echoing exceptions or command arguments.
        report.update(
            status="unknown",
            bundle_id=None,
            detail="The advertised session could not be matched reliably; its process, arguments "
            "or bundle files were unavailable, ambiguous or changed during inspection.",
        )
    return report
