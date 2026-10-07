"""Package-session review from Studio without exposing paths or commands to the browser.

Studio may be running an older retained tools package. Adoption therefore runs
the installed system tools in an isolated interpreter, never Studio's imported
copy or a program named by a request. Status only reads files and advertised IPC.
"""

import ast
import json
import os
import re
import selectors
import stat
import subprocess
import time
from pathlib import Path

from . import (
    native_build,
    native_package,
    native_session,
    native_tools,
    native_tools_launcher,
    package_session,
)
from .native_runtime import _bundle_file
from .storage import digest

SYSTEM_PYTHON = Path("/usr/bin/python3")
PACKAGE_CANDIDATE = Path("/usr/lib/niri-fx/session-candidate")
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
COMMAND_TIMEOUT = 120
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}")
_HASH = re.compile(r"[0-9a-f]{64}")
_READ_ERRORS = (
    OSError,
    ValueError,
    KeyError,
    TypeError,
    StopIteration,
    SyntaxError,
    RecursionError,
)


def _trusted(path, *, directory=False):
    """Require distribution-owned, non-writable paths before executing system tools."""
    path = Path(path)
    for part in (path, *path.parents):
        info = part.lstat()
        if info.st_uid != 0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):
            raise ValueError("The installed package contains an untrusted or writable path")
    info = path.stat()
    kind = stat.S_ISDIR if directory else stat.S_ISREG
    if not kind(info.st_mode):
        raise ValueError("An installed package path has an unexpected file type")


def _system_package():
    # Arch's system Python symlink is owned by its package; resolve this one
    # spelling explicitly, then reject symlinks in the trusted target's parents.
    info = SYSTEM_PYTHON.lstat()
    if info.st_uid != 0 or (not stat.S_ISLNK(info.st_mode) and info.st_mode & 0o022):
        raise ValueError("The system Python interpreter is not distribution-owned")
    interpreter = SYSTEM_PYTHON.resolve(strict=True)
    _trusted(interpreter)
    match = re.fullmatch(r"python(3\.\d+)", interpreter.name)
    if not match or not os.access(interpreter, os.X_OK):
        raise ValueError("The installed package needs the distribution's system Python")
    return interpreter.parent.parent / "lib" / ("python" + match[1]) / "site-packages/niri_fx"


def _installed():
    """Inspect the complete Arch package without importing or executing its tools."""
    package = _system_package()
    paths = (PACKAGE_CANDIDATE / "manifest.json", native_package.REGISTERED_ENTRY)
    if not any(path.exists() for path in (*paths, native_package.SESSION_LAUNCHER)):
        return None
    _trusted(package, directory=True)
    files = {}
    total = 0
    for path in native_tools_launcher.package_files(package):
        _trusted(path)
        data = native_session._read(path, 32 * 1024 * 1024)
        total += len(data)
        if total > 128 * 1024 * 1024:
            raise ValueError("The installed tools exceed their inspection limit")
        files[str(path.relative_to(package))] = digest(data)
        if path.name == "__init__.py" and path.parent == package:
            source = data
    if "__init__.py" not in files:
        raise ValueError("The installed tools package is incomplete")
    versions = [
        node.value.value
        for node in ast.parse(source).body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
    ]
    if (
        len(versions) != 1
        or not isinstance(versions[0], str)
        or not _VERSION.fullmatch(versions[0])
    ):
        raise ValueError("The installed tools version is unavailable")
    for path in (*paths, native_package.SESSION_LAUNCHER, PACKAGE_CANDIDATE / "bin/niri"):
        _trusted(path)
    if paths[1].read_bytes() != package_session.DESKTOP_ENTRY:
        raise ValueError("The installed package login entry has changed")
    if not os.access(native_package.SESSION_LAUNCHER, os.X_OK):
        raise ValueError("The installed package dispatcher is not executable")
    manifest = native_session._object(
        native_session._read(paths[0], native_session.MAX_METADATA_BYTES), "package candidate"
    )
    build = manifest.get("native_build")
    inputs = build.get("inputs") if isinstance(build, dict) else None
    if (
        not isinstance(inputs, dict)
        or inputs.get("variant") != "fragment"
        or native_build.patch_sequence(inputs) != native_build.STACKS["fragment"]
        or build.get("build_id") != native_build.fingerprint(inputs)
        or not isinstance(manifest.get("binary_sha256"), str)
        or not _HASH.fullmatch(manifest["binary_sha256"])
    ):
        raise ValueError("The installed package has no complete NiriFX candidate")
    _bundle_file(
        PACKAGE_CANDIDATE / "bin/niri", manifest["binary_sha256"], native_session.MAX_BINARY_BYTES
    )
    return {
        "version": versions[0],
        "build_id": build["build_id"],
        "binary_sha256": manifest["binary_sha256"],
        "files": files,
    }


def _command(arguments):
    """Bound output and runtime while preserving the adoption CLI's transaction checks."""
    environment = {
        key: value
        for key, value in os.environ.items()
        if key
        not in (
            "PYTHONPATH",
            "PYTHONHOME",
            "NIRI_SOCKET",
            "WAYLAND_DISPLAY",
            "DISPLAY",
            "DBUS_SESSION_BUS_ADDRESS",
        )
    }
    command = [str(SYSTEM_PYTHON), "-I", "-B", "-m", "niri_fx", "native", "adopt", *arguments]
    with subprocess.Popen(
        command,
        cwd="/",
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ) as process:
        output = {"stdout": bytearray(), "stderr": bytearray()}
        deadline = time.monotonic() + COMMAND_TIMEOUT
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ, "stdout")
                selector.register(process.stderr, selectors.EVENT_READ, "stderr")
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ValueError("Package review timed out; review the session again")
                    for key, _ in selector.select(min(remaining, 1)):
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        output[key.data].extend(chunk)
                        if sum(map(len, output.values())) > MAX_OUTPUT_BYTES:
                            raise ValueError("Package tools returned too much output")
                process.wait(timeout=max(0.01, deadline - time.monotonic()))
        except (ValueError, subprocess.TimeoutExpired):
            process.kill()
            process.wait()
            raise
    if process.returncode:
        detail = output["stderr"].decode("utf-8", errors="replace").strip()
        raise ValueError(detail[:4096] or "The installed package could not complete this request")
    try:
        result = json.loads(output["stdout"])
    except (ValueError, UnicodeError):
        raise ValueError("The installed package returned an unreadable response") from None
    if not isinstance(result, dict):
        raise ValueError("The installed package returned an invalid response")
    return result


class StudioSession:
    def __init__(self, root, config, *, socket_path=None):
        self.root = Path(root).expanduser().absolute()
        self.config = Path(config).expanduser().absolute()
        self.socket = socket_path
        self.pending = None
        self.reopen_required = False
        self.apply_uncertain = False

    def snapshot(self):
        result = {
            "state": "unavailable",
            "installed": None,
            "next_login": None,
            "running": {"status": "unknown", "bundle_id": None, "version": None},
            "config": {"path": str(self.config), "mode": "copy"},
            "can_review": False,
            "action": None,
            "reopen_required": self.reopen_required,
            "apply_uncertain": self.apply_uncertain,
        }
        try:
            report = native_session.status(self.root, socket_path=self.socket)
            result["running"] = {
                key: report["running"].get(key)
                for key in ("status", "bundle_id", "version", "detail")
            }
            selected = report["selection"]["selected"]
            bundle = next((row for row in report["bundles"] if row["bundle_id"] == selected), None)
            tools, version = None, None
            if selected:
                result["config"] = {
                    "path": None,
                    "mode": "preserve",
                    "detail": "Keeps your selected session's configuration and saved effects.",
                }
                if bundle["status"] != "metadata-match":
                    raise ValueError("The selected session is damaged; review recovery first")
                if (self.root / "tools/selection.json").exists():
                    selection, _ = native_tools._read_selection(self.root)
                    if selection["phase"] != "active":
                        raise ValueError(
                            "Complete the existing tools migration before package setup"
                        )
                    tools = native_tools_launcher.runtime_record(
                        self.root / "tools", selection["current"]
                    )
                    native_tools_launcher.verify_runtime(tools)
                    version = tools["version"]
                elif (self.root / "session/launch.py").exists():
                    raise ValueError(
                        "Migrate the existing per-user launcher with native tools-update first"
                    )
                result["next_login"] = {
                    "bundle_id": selected,
                    "build_id": bundle["build_id"],
                    "shared": bool(bundle.get("shared")),
                    "tools_version": version,
                }
            else:
                result["config"]["detail"] = (
                    "Copies this Niri configuration and its includes for the first NiriFX login. "
                    "Your original configuration stays unchanged; later source edits are not shared automatically."
                )
            installed = _installed()
            if installed is None:
                return result | {
                    "state": "missing",
                    "detail": "Install niri-fx or niri-fx-git with your package manager, then refresh here.",
                }
            result["installed"] = {key: installed[key] for key in ("version", "build_id")}
            if self.root != package_session.default_root().expanduser().absolute():
                raise ValueError(
                    "Package setup uses your default XDG storage; this Studio uses a custom root"
                )
            matching_tools = (
                tools is not None
                and tools["schema"] == 2
                and version == installed["version"]
                and selection.get("registered_entry") == str(native_package.REGISTERED_ENTRY)
                and installed["files"]
                == {
                    str(Path(path).relative_to(tools["package"])): value
                    for path, value in tools["files"].items()
                    if Path(path).is_relative_to(tools["package"])
                }
            )
            current = (
                matching_tools
                and bundle is not None
                and bundle["binary_sha256"] == installed["binary_sha256"]
                and bundle["build_id"] == installed["build_id"]
            )
            return result | {
                "state": "current" if current else "update" if selected else "ready",
                "can_review": not current,
                "action": None if current else "update" if selected else "setup",
                "detail": "The installed package is selected for the next NiriFX login."
                if current
                else "Review the installed package update while keeping your chosen settings."
                if selected
                else "Review setup to make the packaged NiriFX session available at your next login.",
            }
        except _READ_ERRORS as error:
            return result | {"state": "blocked", "detail": str(error)}

    def status(self, request):
        if request != {}:
            raise ValueError("Session status accepts no client-selected paths")
        return self.snapshot()

    def _arguments(self):
        if self.root != package_session.default_root().expanduser().absolute():
            raise ValueError("Package setup requires the default XDG native storage")
        if _installed() is None:
            raise ValueError("Install the complete NiriFX package before reviewing session setup")
        arguments = [
            "--root",
            str(self.root),
            "--candidate",
            str(PACKAGE_CANDIDATE),
            "--registered-entry",
            str(native_package.REGISTERED_ENTRY),
        ]
        selected = native_session.load_selection(self.root)["selected"]
        if not selected:
            arguments.extend(("--config", str(self.config)))
        return arguments, "update" if selected else "setup"

    def review(self, request):
        if request != {}:
            raise ValueError("Session review accepts no client-selected paths or settings")
        self.pending = None
        arguments, intent = self._arguments()
        result = _command(arguments)
        fingerprint = result.get("plan_sha256")
        if (
            result.get("target") != "native-session-adopt"
            or result.get("dry_run") is not True
            or not isinstance(fingerprint, str)
            or not _HASH.fullmatch(fingerprint)
        ):
            raise ValueError("The installed package did not return a valid session review")
        self.pending = fingerprint
        return result | {"intent": intent}

    def _consume(self, request):
        if (
            not isinstance(request, dict)
            or set(request) != {"expected"}
            or not isinstance(request["expected"], str)
            or not self.pending
            or request["expected"] != self.pending
        ):
            raise ValueError(
                "Review session setup again; this review is missing, cancelled or stale"
            )
        expected, self.pending = self.pending, None
        return expected

    def cancel(self, request):
        self._consume(request)
        return {"cancelled": True}

    def apply(self, request):
        expected = self._consume(request)
        arguments, _ = self._arguments()
        # A killed or disconnected child can finish some writes without a
        # readable success reply. Fence this launch's desktop writers as soon
        # as Apply starts; a fresh Studio process can inspect the outcome.
        self.reopen_required = True
        self.apply_uncertain = True
        result = _command([*arguments, "--apply", "--expect-plan", expected])
        if result.get("dry_run") is not False:
            raise ValueError(
                "The installed package did not confirm session setup; refresh its status"
            )
        self.apply_uncertain = False
        return result | {
            "activation": "next-login",
            "reopen_required": True,
            "session": self.snapshot(),
        }
