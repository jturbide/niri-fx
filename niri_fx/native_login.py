"""Lease a selected native bundle for one login through the stock Niri lifecycle.

The login entry is separate, but the service stays ``niri.service`` because shell
services depend on its identity and MainPID. Only a live launcher can authorize
its runtime override. Selection changes affect the next login; stale overrides
execute stock Niri without needing a candidate bundle to exist.
"""

import argparse
import fcntl
import json
import os
import re
import signal
import socket
import stat
import struct
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .capabilities import _reply
from .native_session import inspect_bundle, load_selection

STOCK = Path("/usr/bin/niri")
UPSTREAM_SESSION = Path("/usr/bin/niri-session")
SYSTEMCTL = Path("/usr/bin/systemctl")
TOKEN = re.compile(r"[0-9a-f]{32}")
BUNDLE_ID = re.compile(r"[0-9a-f]{64}")
VERIFY_TIMEOUT = 20
ENVIRONMENT = (
    "WAYLAND_DISPLAY",
    "DISPLAY",
    "XDG_SESSION_TYPE",
    "XDG_CURRENT_DESKTOP",
    "NIRI_SOCKET",
)


def process_identity(pid):
    """Pair the PID with its kernel start time so PID reuse cannot revive a lease."""
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] == "Z":
            return None
        return {"pid": pid, "start_ticks": int(fields[19])}
    except (OSError, ValueError, IndexError):
        return None


def _read_json(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
            raise ValueError("Session metadata must be a small regular file")
        return json.load(stream)


def _directory(path, *, create=False):
    if create:
        path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o022:
        raise RuntimeError(
            "Session runtime directories must be owned and writable only by this user"
        )


def runtime_paths():
    value = os.environ.get("XDG_RUNTIME_DIR", "")
    runtime = Path(value)
    if not value or not runtime.is_absolute():
        raise RuntimeError("XDG_RUNTIME_DIR is missing or relative; use the login screen")
    _directory(runtime)
    return (
        runtime,
        runtime / "niri-fx-native-login",
        runtime / "systemd/user/niri.service.d/90-niri-fx-native-login.conf",
    )


def systemctl(*args, check=True):
    return subprocess.run(
        [str(SYSTEMCTL), "--user", *args],
        check=check,
        text=True,
        capture_output=True,
        timeout=20,
    )


def service_state():
    result = systemctl("show", "niri.service", "--property=ActiveState,MainPID,LoadState")
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if fields.get("LoadState") != "loaded":
        raise RuntimeError("The stock niri.service must be installed and readable")
    return fields.get("ActiveState", "unknown"), int(fields.get("MainPID", "0"))


def require_stopped():
    state, pid = service_state()
    if state not in ("inactive", "failed") or pid:
        raise RuntimeError(
            f"niri.service is {state}; log out and select NiriFX at the login screen. "
            "The running desktop has not been changed."
        )


def _has_start_hook(text):
    section = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            section = stripped
        elif section == "[Service]" and re.match(r"ExecStart(?:Pre|Post)?\s*=", stripped):
            return True
    return False


def require_unmodified_start(directory, own_dropin):
    """Refuse competing launch hooks while preserving harmless unit settings."""
    previous = load_lease(directory)
    owned_text = dropin_text(previous["root"], previous["token"]) if previous else None
    blocks = {}
    source = None
    # systemctl cat supplies one source marker per fragment/drop-in and includes
    # persistent overrides outside XDG_RUNTIME_DIR. Inspect files again below to
    # catch a runtime override that has not been daemon-reloaded yet.
    result = systemctl("cat", "niri.service", "--no-pager")
    for line in result.stdout.splitlines(keepends=True):
        if line.startswith("# /"):
            source = Path(line[2:].strip())
            blocks.setdefault(source, "")
        elif source is not None:
            blocks[source] += line
    if own_dropin.parent.exists():
        for path in own_dropin.parent.glob("*.conf"):
            descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
            with os.fdopen(descriptor) as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
                    raise RuntimeError(f"Cannot inspect runtime session override: {path}")
                blocks[path] = stream.read()
    for path, text in blocks.items():
        if path.suffix != ".conf" or not _has_start_hook(text):
            continue
        if path == own_dropin and owned_text is not None and text == owned_text:
            continue
        raise RuntimeError(
            f"Another niri.service start override exists: {path}. "
            "Review or remove that integration before using this NiriFX login; "
            "the override and desktop have not been changed."
        )


def _require_tools():
    for path in (STOCK, UPSTREAM_SESSION, SYSTEMCTL, Path(sys.executable)):
        if not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK):
            raise RuntimeError(f"Required session executable is unavailable: {path}")


def same_executable(pid, path):
    try:
        return os.path.samefile(f"/proc/{pid}/exe", path)
    except OSError:
        return False


def load_lease(directory):
    try:
        lease = _read_json(directory / "lease.json")
        if (
            not isinstance(lease, dict)
            or type(lease.get("schema")) is not int
            or lease["schema"] != 1
            or lease.get("uid") != os.getuid()
            or type(lease.get("pid")) is not int
            or type(lease.get("start_ticks")) is not int
            or not isinstance(lease.get("token"), str)
            or not TOKEN.fullmatch(lease["token"])
            or not isinstance(lease.get("bundle_id"), str)
            or not BUNDLE_ID.fullmatch(lease["bundle_id"])
            or not isinstance(lease.get("root"), str)
            or not Path(lease["root"]).is_absolute()
            or not isinstance(lease.get("binary"), str)
            or not Path(lease["binary"]).is_absolute()
        ):
            return None
        return lease
    except (OSError, ValueError, TypeError):
        return None


def lease_alive(lease, token, root):
    if not lease or lease["token"] != token or lease["root"] != str(root):
        return False
    if process_identity(lease["pid"]) != {"pid": lease["pid"], "start_ticks": lease["start_ticks"]}:
        return False
    session_id = lease.get("session_id")
    return not session_id or os.environ.get("XDG_SESSION_ID") == session_id


def _unit_argument(value):
    # These are systemd ExecStart arguments, not shell syntax. Escape both unit
    # specifiers and environment expansion before quoting the complete argument.
    value = str(value)
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("Session paths cannot contain control characters")
    return (
        '"'
        + value.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$")
        + '"'
    )


def dropin_text(root, token):
    package_parent = str(Path(__file__).resolve().parent.parent)
    bootstrap = (
        f"import sys; sys.path.insert(0, {package_parent!r}); "
        "from niri_fx.native_login import main; raise SystemExit(main())"
    )
    command = " ".join(
        _unit_argument(part)
        for part in (sys.executable, "-I", "-B", "-c", bootstrap, "--root", root)
    )
    return (
        f"# NiriFX temporary login lease {token}\n"
        "# Stale leases execute stock Niri.\n"
        "[Service]\nExecStart=\n"
        f"ExecStart={command} compositor --token {token}\n"
        f"ExecStartPost={command} verify --token {token}\n"
    )


def write_new(path, text):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())


def _check_executable(binary):
    """Separate loader/runtime failures from configuration errors before login."""
    recovery = (
        "Use a TTY or working stock Niri session to repair system packages or rebuild the candidate, "
        "then review native adopt or native rollback. The retained selection is unchanged."
    )
    try:
        result = subprocess.run(
            [str(binary), "--version"], text=True, capture_output=True, timeout=20
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"Niri executable cannot run: {binary}: {error}. {recovery}") from error
    if result.returncode:
        detail = (result.stderr.strip() or result.stdout.strip())[-4096:]
        detail = detail or f"exited with status {result.returncode}"
        raise RuntimeError(f"Niri executable cannot run: {binary}: {detail}. {recovery}")


def _bundle(root, bundle_id, *, process_only=False):
    report = inspect_bundle(root, bundle_id)
    if not process_only:
        _check_executable(report["binary"])
    if report.get("shared"):
        if process_only:
            # Shell startup may rewrite shared includes; process verification
            # must not run new probes or revalidate those mutable settings.
            return report
        from .native_shared import preflight

        stock = report["shared"].get("stock_binary")
        if stock and stock != report["binary"]:
            _check_executable(stock)
        preflight(report)
        if inspect_bundle(root, bundle_id) != report:
            raise RuntimeError("Selected native bundle changed during configuration validation")
        return report
    result = subprocess.run(
        [str(report["binary"]), "validate", "-c", str(report["config"])],
        text=True,
        capture_output=True,
        timeout=20,
    )
    if result.returncode:
        raise RuntimeError(
            "Selected NiriFX configuration failed validation: " + result.stderr.strip()
        )
    # Validation runs a trusted, explicitly selected local build. Reject changes
    # made while that process was running before proceeding to a login.
    if inspect_bundle(root, bundle_id) != report:
        raise RuntimeError("Selected native bundle changed during configuration validation")
    return report


def _receipt_path(directory, token):
    return directory / f"compositor-{token}.json"


def _owned_compositor(directory, lease, pid):
    try:
        receipt = _read_json(_receipt_path(directory, lease["token"]))
        identity = {"pid": receipt["pid"], "start_ticks": receipt["start_ticks"]}
        return (
            receipt["token"] == lease["token"]
            and receipt["bundle_id"] == lease["bundle_id"]
            and receipt["binary"] == lease["binary"]
            and pid == identity["pid"]
            and process_identity(pid) == identity
            and same_executable(pid, receipt["binary"])
        )
    except (OSError, ValueError, TypeError, KeyError):
        return False


def owned_cleanup(directory, dropin, expected):
    """Preserve externally edited runtime files instead of guessing ownership."""
    if load_lease(directory) != expected:
        return False
    if dropin.is_symlink():
        return False
    if dropin.exists() and dropin.read_text() != dropin_text(expected["root"], expected["token"]):
        return False
    changed = dropin.exists()
    if changed:
        dropin.unlink()
    (directory / "lease.json").unlink()
    if changed:
        systemctl("daemon-reload")
    return True


def compositor(root, token):
    try:
        _, directory, _ = runtime_paths()
        lease = load_lease(directory)
        authorized = lease_alive(lease, token, root)
    except (OSError, RuntimeError):
        authorized = False
    if not authorized:
        os.execv(str(STOCK), [str(STOCK), "--session"])
        return
    report = _bundle(root, lease["bundle_id"])
    if report["binary"] != lease["binary"]:
        raise RuntimeError("The selected executable differs from its login lease")
    if not lease_alive(load_lease(directory), token, root):
        raise RuntimeError("The native login lost its launcher before execution")
    identity = process_identity(os.getpid())
    if identity is None:
        raise RuntimeError("Cannot identify the compositor process")
    write_new(
        _receipt_path(directory, token),
        json.dumps(
            {
                **identity,
                "token": token,
                "bundle_id": lease["bundle_id"],
                "binary": str(report["binary"]),
            }
        )
        + "\n",
    )
    os.execv(
        str(report["binary"]),
        [str(report["binary"]), "--session", "--config", str(report["config"])],
    )


def _socket_version(path, pid):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(2)
        connection.connect(str(path))
        peer_pid, uid, _ = struct.unpack(
            "3i", connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12)
        )
        if peer_pid != pid or uid != os.getuid():
            raise RuntimeError("Niri IPC peer does not match the selected compositor")
        version = _reply(connection, "Version")["Ok"]["Version"]
        if not isinstance(version, str) or not version.strip():
            raise ValueError("Invalid Niri version reply")
        return version


def verify(root, token):
    runtime, directory, _ = runtime_paths()
    lease = load_lease(directory)
    if not lease_alive(lease, token, root):
        _, pid = service_state()
        if not pid or not same_executable(pid, STOCK):
            raise RuntimeError("Expired native lease did not start the stock compositor")
        return
    report = _bundle(root, lease["bundle_id"], process_only=True)
    deadline = time.monotonic() + VERIFY_TIMEOUT
    while time.monotonic() < deadline:
        _, pid = service_state()
        if not lease_alive(load_lease(directory), token, root):
            raise RuntimeError("The native login lost its owning launcher")
        if not _owned_compositor(directory, lease, pid) or not same_executable(
            pid, report["binary"]
        ):
            raise RuntimeError("niri.service MainPID is not the selected native compositor")
        for candidate in runtime.glob(f"niri.*.{pid}.sock"):
            if candidate.is_symlink() or not candidate.is_socket():
                continue
            try:
                version = _socket_version(candidate, pid)
            except (OSError, ValueError, KeyError, TypeError, RuntimeError):
                continue
            if not _owned_compositor(directory, lease, service_state()[1]):
                raise RuntimeError("The native compositor changed during IPC verification")
            write_new(
                directory / f"verified-{token}.json",
                json.dumps(
                    {
                        "schema": 1,
                        "token": token,
                        "bundle_id": lease["bundle_id"],
                        "main_pid": pid,
                        "version": version,
                        "scope": "process-and-ipc",
                    }
                )
                + "\n",
            )
            return
        time.sleep(0.25)
    raise RuntimeError("The selected native compositor did not expose a matching IPC socket")


def _verified_login(directory, lease):
    """A wrapper exit code cannot prove systemd actually started the compositor."""
    try:
        report = _read_json(directory / f"verified-{lease['token']}.json")
        receipt = _read_json(_receipt_path(directory, lease["token"]))
        return (
            type(report.get("schema")) is int
            and report["schema"] == 1
            and report.get("token") == lease["token"]
            and report.get("bundle_id") == lease["bundle_id"]
            and type(report.get("main_pid")) is int
            and report["main_pid"] > 0
            and report.get("scope") == "process-and-ipc"
            and isinstance(report.get("version"), str)
            and bool(report["version"].strip())
            and receipt.get("token") == lease["token"]
            and receipt.get("bundle_id") == lease["bundle_id"]
            and receipt.get("pid") == report["main_pid"]
            and type(receipt.get("start_ticks")) is int
            and receipt.get("binary") == lease["binary"]
        )
    except (OSError, ValueError, TypeError, AttributeError):
        return False


def _stop_owned(directory, lease, root):
    _, pid = service_state()
    if lease_alive(load_lease(directory), lease["token"], root) and _owned_compositor(
        directory, lease, pid
    ):
        systemctl("stop", "niri.service")
        return True
    return False


def launch(root):
    require_stopped()
    _require_tools()
    selection = load_selection(root)
    bundle_id = selection.get("selected")
    if bundle_id is None:
        raise RuntimeError("No native bundle is selected; use the stock Niri login entry")
    report = _bundle(root, bundle_id)
    _, directory, dropin = runtime_paths()
    require_unmodified_start(directory, dropin)
    _directory(directory, create=True)
    descriptor = os.open(
        directory / "launch.lock", os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600
    )
    with os.fdopen(descriptor, "w") as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise RuntimeError("The session lock must be a regular file")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another NiriFX login launcher owns this session") from None
        require_stopped()
        require_unmodified_start(directory, dropin)
        previous = load_lease(directory)
        if previous and process_identity(previous["pid"]) == {
            "pid": previous["pid"],
            "start_ticks": previous["start_ticks"],
        }:
            raise RuntimeError("Another live launcher has a lease; refusing to replace it")
        if previous:
            owned_cleanup(directory, dropin, previous)
        if dropin.is_symlink() or dropin.exists() or (directory / "lease.json").exists():
            raise RuntimeError(
                "Unrecognized runtime session files exist; preserving them for review"
            )
        identity = process_identity(os.getpid())
        if identity is None:
            raise RuntimeError("Cannot identify the login launcher")
        lease = {
            "schema": 1,
            "token": uuid.uuid4().hex,
            "uid": os.getuid(),
            **identity,
            "root": str(root),
            "bundle_id": bundle_id,
            "binary": str(report["binary"]),
            "session_id": os.environ.get("XDG_SESSION_ID") or None,
        }
        child = None
        requested_signal = None
        interrupted_signal = None

        def on_signal(signum, _):
            nonlocal requested_signal, interrupted_signal
            requested_signal = signum
            interrupted_signal = signum

        handlers = {
            sig: signal.signal(sig, on_signal)
            for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
        }
        try:
            write_new(directory / "lease.json", json.dumps(lease) + "\n")
            for parent in reversed(dropin.parent.parents):
                if parent == directory.parent or directory.parent in parent.parents:
                    _directory(parent, create=True)
            _directory(dropin.parent, create=True)
            write_new(dropin, dropin_text(root, lease["token"]))
            systemctl("daemon-reload")
            child = subprocess.Popen([str(UPSTREAM_SESSION)])
            while child.poll() is None:
                if requested_signal is not None:
                    if not _stop_owned(directory, lease, root):
                        child.send_signal(requested_signal)
                    requested_signal = None
                time.sleep(0.2)
            if child.returncode == 0 and not _verified_login(directory, lease):
                if interrupted_signal is not None:
                    return 128 + interrupted_signal
                raise RuntimeError(
                    "NiriFX login ended before compositor process and IPC verification. "
                    "Inspect journalctl --user -b -u niri.service, or select stock Niri."
                )
            return child.returncode
        finally:
            try:
                if _stop_owned(directory, lease, root):
                    systemctl("start", "--job-mode=replace-irreversibly", "niri-shutdown.target")
                    systemctl("unset-environment", *ENVIRONMENT)
            finally:
                if child is not None and child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=5)
                try:
                    if not owned_cleanup(directory, dropin, lease):
                        print(
                            "Runtime session files changed externally; preserved for review.",
                            file=sys.stderr,
                        )
                finally:
                    for sig, handler in handlers.items():
                        signal.signal(sig, handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("command", choices=("launch", "compositor", "verify"))
    parser.add_argument("--token", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.command != "launch" and not TOKEN.fullmatch(args.token or ""):
        parser.error("Internal helpers require a valid lease token")
    root = args.root.expanduser().absolute()
    try:
        _unit_argument(root)
        if args.command == "launch":
            return launch(root)
        if args.command == "compositor":
            compositor(root, args.token)
        else:
            verify(root, args.token)
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"NiriFX login: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
