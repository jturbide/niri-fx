"""Separate confirmed immutable reloads from shared configuration file updates.

The process command line identifies the startup bundle forever. A separate,
process-bound receipt records only our last confirmed reload; it cannot observe
configuration changes made by other IPC clients. Niri's ConfigLoaded event has
no request ID or path, so confirmation is scoped to this serialized reload.
Shared settings use watched includes and never claim this IPC confirmation.
"""

import fcntl
import json
import os
import re
import select
import socket
import stat
import struct
import time
from pathlib import Path

from . import capabilities, native_runtime, native_session
from .storage import atomic_write, digest

RELOAD_TIMEOUT = 5
MAX_EVENT_BYTES = 1024 * 1024
MAX_EVENTS = 1024
RECEIPT = "live-session.json"


def activation_plan(plan, root, base_bundle, *, socket_path=None, require_live=False):
    """Bind desktop reload intent and session identity into the shared review.

    Studio can offer next-login saving when no managed desktop is available.
    An explicit CLI live request must instead fail before the selection writer.
    """
    if plan.get("shared"):
        if require_live:
            raise ValueError(
                "Shared settings use automatic config reload, whose active result is not "
                "verified. Review and apply without --live."
            )
        plan.pop("native_live", None)
        plan["activation"] = "config-written"
        plan["notes"] = [
            "Writes the reviewed shared settings. Sessions already using this shared "
            "wrapper watch its includes; other NiriFX sessions need the next login. "
            "The active compositor configuration is not verified.",
            *plan["notes"],
        ]
        return plan
    plan["activation"] = "next-login"
    if base_bundle is None:
        if require_live:
            raise ValueError(
                "Live Apply requires a retained bundle; no live rollback target exists"
            )
        return plan
    live = context(root, base_bundle, socket_path=socket_path)
    if live["ready"]:
        plan["native_live"] = live["identity"]
        plan["activation"] = "live-and-next-login"
        plan["notes"] = [
            "Applies these effects to the verified running NiriFX session and the next login.",
            *plan["notes"],
        ]
    elif require_live:
        raise ValueError(f"Live Apply is unavailable: {live['detail']}")
    else:
        plan["notes"].append(live["detail"])
    return plan


def activation_result(plan, result, root, base_bundle, *, socket_path=None):
    """Report retained selection separately from a confirmed desktop reload."""
    if plan.get("shared"):
        result["activation"] = "config-written"
        result["live"] = {
            "status": "unverified",
            "detail": "Shared configuration files were written. Sessions already using this "
            "shared wrapper watch its includes; other NiriFX sessions need the next login. "
            "The active compositor configuration has not been verified.",
        }
        return result
    result["activation"] = "next-login"
    if plan.get("native_live"):
        live = apply(
            root,
            base_bundle,
            plan["selection"]["selected"],
            socket_path=socket_path,
            expected_identity=plan["native_live"],
        )
        result["live"] = live
        if live["status"] == "applied":
            result["activation"] = "live-and-next-login"
    return result


def _baseline(bundle):
    return bundle.get("customization", {}).get("baseline_bundle", bundle["bundle_id"])


def _process(pid):
    binary, identity = native_runtime._executable(pid)
    return {
        "uid": os.geteuid(),
        "pid": pid,
        "start_ticks": native_runtime._process_start(pid),
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
        "binary": binary,
        "binary_identity": list(identity),
        "arguments": list(native_runtime._arguments(pid)),
    }


def _receipt(root):
    path = native_session._path(root / RECEIPT)
    if not path.exists():
        return None, None
    if path.stat().st_uid != os.geteuid():
        raise ValueError("The live-session receipt belongs to another user")
    raw = native_session._read(path, 65536, mode=0o600)
    value = native_session._object(raw, "live-session receipt")
    if (
        set(value) != {"schema", "identity", "status", "requested_bundle", "loaded_bundle"}
        or type(value["schema"]) is not int
        or value["schema"] != 1
        or not _valid_identity(value["identity"])
        or value["status"] not in {"pending", "applied", "failed", "unconfirmed"}
        or not isinstance(value["requested_bundle"], str)
        or not native_session._ID.fullmatch(value["requested_bundle"])
        or (
            value["loaded_bundle"] is not None
            and (
                not isinstance(value["loaded_bundle"], str)
                or not native_session._ID.fullmatch(value["loaded_bundle"])
            )
        )
        or (value["status"] == "applied") != (value["loaded_bundle"] is not None)
        or (value["status"] == "applied" and value["loaded_bundle"] != value["requested_bundle"])
    ):
        raise ValueError("The live-session receipt is invalid")
    return value, raw


def _valid_identity(identity):
    fields = {
        "uid",
        "pid",
        "start_ticks",
        "boot_id",
        "binary",
        "binary_identity",
        "arguments",
        "startup_bundle",
        "baseline_bundle",
        "binary_sha256",
        "socket",
    }
    return (
        isinstance(identity, dict)
        and set(identity) == fields
        and type(identity["uid"]) is int
        and identity["uid"] == os.geteuid()
        and type(identity["pid"]) is int
        and identity["pid"] > 0
        and type(identity["start_ticks"]) is int
        and identity["start_ticks"] >= 0
        and isinstance(identity["boot_id"], str)
        and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", identity["boot_id"])
        is not None
        and isinstance(identity["binary"], str)
        and Path(identity["binary"]).is_absolute()
        and isinstance(identity["socket"], str)
        and bool(identity["socket"])
        and isinstance(identity["binary_identity"], list)
        and len(identity["binary_identity"]) == 6
        and all(type(item) is int for item in identity["binary_identity"])
        and isinstance(identity["arguments"], list)
        and bool(identity["arguments"])
        and all(isinstance(item, str) for item in identity["arguments"])
        and all(
            isinstance(identity[key], str) and native_session._ID.fullmatch(identity[key])
            for key in ("startup_bundle", "baseline_bundle", "binary_sha256")
        )
    )


def _receipt_owner_alive(identity):
    """Only a positively stale process identity releases another session's receipt."""
    if identity["boot_id"] != Path("/proc/sys/kernel/random/boot_id").read_text().strip():
        return False
    try:
        started = native_runtime._process_start(identity["pid"])
    except FileNotFoundError:
        return False
    if started != identity["start_ticks"]:
        return False
    process = _process(identity["pid"])
    return all(identity.get(key) == value for key, value in process.items())


def context(root, base_bundle, *, socket_path=None):
    """Read-only readiness and stable review identity; never reload or infer a socket."""
    result = {
        "ready": False,
        "status": "offline" if not socket_path else "unavailable",
        "identity": None,
        "startup_bundle": None,
        "loaded_bundle": None,
        "effective_bundle": None,
        "baseline_bundle": None,
        "detail": "No Niri IPC socket was supplied. Settings can be saved for the next login.",
    }
    if not socket_path:
        return result
    try:
        root = native_session._path(root)
        base = native_session.inspect_bundle(root, base_bundle)
        report = native_session.status(root, socket_path=socket_path)
        running = report["running"]
        if running["status"] != "matched":
            return result | {"status": running["status"], "detail": running["detail"]}
        startup = next(
            item for item in report["bundles"] if item["bundle_id"] == running["bundle_id"]
        )
        if base["binary_sha256"] != startup["binary_sha256"] or _baseline(base) != _baseline(
            startup
        ):
            raise ValueError("The running session has a different build or retained baseline")
        if startup["variant"] != "fragment":
            raise ValueError("Live Apply requires the complete NiriFX compositor")
        process = _process(running["pid"])
        if (
            process["binary"] != startup["binary"]
            or native_runtime._configuration(process["arguments"]) != startup["config"]
        ):
            raise ValueError("The startup process changed after bundle inspection")
        identity = process | {
            "startup_bundle": startup["bundle_id"],
            "baseline_bundle": _baseline(startup),
            "binary_sha256": startup["binary_sha256"],
            "socket": str(socket_path),
        }
        if base.get("shared") or startup.get("shared"):
            from .native_shared import inspect_settings

            settings = inspect_settings(base if base.get("shared") else startup)
            if _process(running["pid"]) != process:
                raise ValueError("The running process changed during shared settings inspection")
            # A watcher can reload any included file between observations. Do
            # not let its uncorrelated ConfigLoaded event confirm an IPC Apply.
            return result | {
                "status": "shared-config",
                "configuration_mode": "shared",
                "startup_bundle": startup["bundle_id"],
                "baseline_bundle": _baseline(startup),
                "shared_settings": {
                    "status": settings["status"],
                    "projections_match": settings["projections_match"],
                },
                "detail": "This session follows shared configuration files automatically. "
                "The process and startup wrapper are identified; active settings and "
                "renderer acceptance are not verified.",
            }
        receipt, raw = _receipt(root)
        loaded = None
        if (
            receipt is not None
            and receipt["identity"] != identity
            and _receipt_owner_alive(receipt["identity"])
        ):
            raise ValueError("Another running session owns the live Apply receipt")
        if receipt is not None and receipt["identity"] == identity:
            if receipt["status"] != "applied":
                return result | {
                    "status": receipt["status"],
                    "startup_bundle": startup["bundle_id"],
                    "baseline_bundle": _baseline(startup),
                    "detail": "The previous live reload was not confirmed. Settings remain "
                    "available for the next login; log in again before another live Apply.",
                }
            loaded = native_session.inspect_bundle(root, receipt["loaded_bundle"])
            if loaded["binary_sha256"] != startup["binary_sha256"] or _baseline(
                loaded
            ) != _baseline(startup):
                raise ValueError("The recorded live bundle no longer matches the session")
        # Only the retained executable already matched through SO_PEERCRED is
        # trusted for parser probes. A copied target binary has a different inode.
        for probe in (
            capabilities.movement_capability,
            capabilities.pointer_capability,
            capabilities.fragment_capability,
            *((capabilities.swap_capability,) if base.get("swap_supported") else ()),
        ):
            if not probe(startup["binary"], socket_path=socket_path)["activation_ready"]:
                raise ValueError("The running renderer could not verify every NiriFX interface")
        if _process(running["pid"]) != process:
            raise ValueError("The running process changed during review")
        if _receipt(root)[1] != raw:
            raise ValueError("Another live Apply changed the session during review")
        return result | {
            "ready": True,
            "status": "ready",
            "identity": identity | {"receipt_sha256": digest(raw)},
            "startup_bundle": startup["bundle_id"],
            "loaded_bundle": loaded["bundle_id"] if loaded else None,
            "effective_bundle": loaded["bundle_id"] if loaded else startup["bundle_id"],
            "baseline_bundle": _baseline(startup),
            "detail": "The managed compositor and renderer support live Apply. The recorded "
            "bundle reflects startup or the last confirmed NiriFX reload, not external IPC changes.",
        }
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        return result | {
            "status": "unavailable",
            "detail": "The managed process, renderer, retained baseline or live receipt could "
            "not be verified. Settings can still be saved for the next login.",
        }


def _check_peer(connection, identity):
    pid, uid, _ = struct.unpack(
        "3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
    )
    if pid != identity["pid"] or uid != identity["uid"]:
        raise ValueError("The IPC process changed after review")
    process = _process(pid)
    if any(identity.get(key) != value for key, value in process.items()):
        raise ValueError("The IPC process identity changed after review")


class _Events:
    """Retain coalesced lines and cap both total bytes and the wall-clock deadline."""

    def __init__(self, connection):
        self.connection = connection
        self.buffer = bytearray()
        self.total = 0
        self.count = 0

    def read(self, deadline):
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("ConfigLoaded confirmation timed out")
            self.connection.settimeout(remaining)
            chunk = self.connection.recv(min(65536, MAX_EVENT_BYTES + 1 - self.total))
            self.total += len(chunk)
            if not chunk or self.total > MAX_EVENT_BYTES:
                raise ValueError("The configuration event stream ended or exceeded its limit")
            self.buffer.extend(chunk)
        line, _, rest = self.buffer.partition(b"\n")
        self.buffer = bytearray(rest)
        self.count += 1
        if self.count > MAX_EVENTS:
            raise ValueError("The configuration event stream exceeded its event limit")
        return json.loads(line)

    def config_loaded(self, deadline):
        while True:
            event = self.read(deadline)
            if isinstance(event, dict) and "ConfigLoaded" in event:
                value = event["ConfigLoaded"]
                if (
                    set(event) != {"ConfigLoaded"}
                    or not isinstance(value, dict)
                    or set(value) != {"failed"}
                    or type(value["failed"]) is not bool
                ):
                    raise ValueError("Invalid ConfigLoaded event")
                return value["failed"]

    def require_no_reload(self, deadline):
        while self.buffer or select.select([self.connection], [], [], 0)[0]:
            event = self.read(deadline)
            if isinstance(event, dict) and "ConfigLoaded" in event:
                raise ValueError("Another client reloaded the configuration before Apply")


def _directory(path):
    native_session._path(path)
    info = path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise ValueError("Live Apply state must be owned and writable only by this user")


def apply(root, base_bundle, bundle_id, *, socket_path, expected_identity, state=None):
    """Reload after the shared setup transaction has validated and selected the bundle.

    A failed or uncertain reload never rolls back arbitrary desktop state. The
    next-login selection and retained bundles survive for inspection and recovery.
    """
    result = {"status": "unavailable", "bundle_id": bundle_id, "startup_bundle": None}
    try:
        root = native_session._path(root)
        _directory(root)
        state = native_session._path(state if state is not None else root / "state/selection")
        state.mkdir(parents=True, exist_ok=True, mode=0o700)
        _directory(state)
        lock_path = native_session._path(state / ".lock")
        descriptor = os.open(
            lock_path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600
        )
        with os.fdopen(descriptor, "a") as lock:
            if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
                raise ValueError("Live Apply lock is not a regular file")
            fcntl.flock(lock, fcntl.LOCK_EX)
            current = context(root, base_bundle, socket_path=socket_path)
            if not current["ready"] or current["identity"] != expected_identity:
                raise ValueError("Live Apply review changed; review the settings again")
            target = native_session.inspect_bundle(root, bundle_id)
            if target.get("shared"):
                raise ValueError(
                    "Shared configuration uses watched files, not confirmed IPC reloads"
                )
            identity = current["identity"]
            result["startup_bundle"] = current["startup_bundle"]
            if (
                target["binary_sha256"] != identity["binary_sha256"]
                or _baseline(target) != current["baseline_bundle"]
                or native_session.load_selection(root)["selected"] != bundle_id
            ):
                raise ValueError("The selected bundle changed build, baseline or selection")
            return _reload(root, target, identity, socket_path, result)
    except (OSError, ValueError, KeyError, TypeError):
        return result | {
            "detail": "The running session or reviewed selection changed. "
            "No live reload was sent; review the settings again.",
        }


def _reload(root, target, identity, socket_path, result):
    bundle_id = target["bundle_id"]
    sent = False
    pending = None
    receipt_path = None
    try:
        receipt_path = native_session._path(root / RECEIPT)
        pending = {
            "schema": 1,
            "identity": {key: value for key, value in identity.items() if key != "receipt_sha256"},
            "requested_bundle": bundle_id,
            "loaded_bundle": None,
            "status": "pending",
        }
        with (
            socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as events_socket,
            socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as action_socket,
        ):
            for connection in (events_socket, action_socket):
                connection.settimeout(capabilities.IPC_TIMEOUT)
                connection.connect(str(socket_path))
                _check_peer(connection, identity)
            events = _Events(events_socket)
            events_socket.sendall(b'"EventStream"\n')
            deadline = time.monotonic() + RELOAD_TIMEOUT
            if events.read(deadline) != {"Ok": "Handled"}:
                raise ValueError("The compositor did not accept EventStream")
            events.config_loaded(deadline)  # Initial state is not our reload confirmation.
            events.require_no_reload(deadline)
            from .setup import check_unchanged

            for item in target["observed"]:
                check_unchanged(item, item["before"])
            if native_session.load_selection(root)["selected"] != bundle_id:
                raise ValueError("The next-login selection changed before live Apply")
            if digest(_receipt(root)[1]) != identity["receipt_sha256"]:
                raise ValueError("The live-session receipt changed before Apply")
            _check_peer(action_socket, identity)
            events.require_no_reload(time.monotonic() + RELOAD_TIMEOUT)
            # Record uncertainty before writing to the socket: a process crash
            # after dispatch must never make an old recipe look confirmed.
            atomic_write(receipt_path, native_session._json_bytes(pending))
            sent = True
            _check_peer(action_socket, identity)
            reply = capabilities._reply(
                action_socket, {"Action": {"LoadConfigFile": {"path": target["config"]}}}
            )
            if reply != {"Ok": "Handled"}:
                outcome = "failed" if isinstance(reply, dict) and "Err" in reply else "unconfirmed"
            else:
                outcome = (
                    "failed"
                    if events.config_loaded(time.monotonic() + RELOAD_TIMEOUT)
                    else "applied"
                )
                _check_peer(action_socket, identity)
            receipt = pending | {
                "status": outcome,
                "loaded_bundle": bundle_id if outcome == "applied" else None,
            }
            atomic_write(receipt_path, native_session._json_bytes(receipt))
            return result | {
                "status": outcome,
                "detail": {
                    "applied": "The compositor confirmed a successful configuration reload. "
                    "The selected settings also apply at the next login.",
                    "failed": "The compositor rejected the live reload. The settings remain "
                    "selected for the next login; the active recipe is not confirmed.",
                    "unconfirmed": "The reload result could not be confirmed. The settings "
                    "remain selected for the next login; the active recipe is unknown.",
                }[outcome],
            }
    except (OSError, ValueError, KeyError, TypeError):
        if sent and pending is not None:
            try:
                atomic_write(
                    receipt_path, native_session._json_bytes(pending | {"status": "unconfirmed"})
                )
            except (OSError, ValueError):
                pass  # A persisted pending record also prevents a false success.
        return result | {
            "status": "unconfirmed" if sent else "unavailable",
            "detail": "The live reload could not be confirmed. Review the next-login settings "
            "before logging in again."
            if sent
            else "The running session or reviewed selection "
            "changed. No live reload was sent; review the settings again.",
        }
