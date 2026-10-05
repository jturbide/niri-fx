"""Stable, standard-library-only dispatch for a retained NiriFX tools runtime.

This file is copied into native storage. Keep it independent of the package it
selects: switching or restoring that package must never strand its launcher.
"""

import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path

MAX_BYTES = 4 * 1024 * 1024


def read_owned(path):
    """Read bounded private metadata without following path-component symlinks."""
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Tool metadata paths must be absolute and must not contain symlinks")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_size > MAX_BYTES
        ):
            raise ValueError("Tool metadata must be a private, user-owned regular file")
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Tool metadata exceeds its size limit")
    return data


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def runtime_record(directory, identifier):
    if not isinstance(identifier, str) or not re.fullmatch(r"[a-f0-9]{64}", identifier):
        raise ValueError("Invalid tools runtime identifier")
    record = json.loads(read_owned(directory / "runtimes" / f"{identifier}.json"))
    if (
        not isinstance(record, dict)
        or record.get("schema") != 1
        or fingerprint(record) != identifier
    ):
        raise ValueError("Tool runtime receipt identity changed")
    return record


def verify_runtime(record):
    """Detect removed or edited runtimes before executing the retained interpreter."""
    if set(record) != {"schema", "python", "package", "version", "files", "desktop"}:
        raise ValueError("Unsupported tools runtime receipt")
    python = Path(record["python"])
    package = Path(record["package"])
    prefix = python.parent.parent
    if not python.is_absolute() or not package.is_absolute() or not package.is_relative_to(prefix):
        raise ValueError("Retained tools package must belong to its virtual environment")
    files = record["files"]
    if not isinstance(files, dict) or not 1 <= len(files) <= 2048:
        raise ValueError("Invalid tools runtime file inventory")
    actual = {
        str(p)
        for p in package.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    }
    actual.add(str(prefix / "pyvenv.cfg"))
    if actual != set(files):
        raise ValueError("Retained tools runtime file inventory changed")
    for value, expected in files.items():
        path = Path(value)
        if (
            not path.is_absolute()
            or not isinstance(expected, str)
            or not re.fullmatch(r"[a-f0-9]{64}", expected)
        ):
            raise ValueError("Invalid tools runtime file identity")
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 32 * 1024 * 1024:
            raise ValueError("Runtime files must be bounded regular files")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Retained tools runtime changed: {path}")
    python = Path(record["python"])
    package = Path(record["package"])
    if str(package / "__init__.py") not in files:
        raise ValueError("Tools runtime inventory is incomplete")
    if not os.access(python, os.X_OK):
        raise ValueError("Retained tools interpreter is unavailable")


def main(arguments=None):
    arguments = list(sys.argv[1:] if arguments is None else arguments)
    directory = Path(__file__).absolute().parent
    root = directory.parent
    if not arguments or arguments[0] not in {"cli", "studio", "session"}:
        raise ValueError("Expected a CLI, Studio or session launcher")
    action = arguments.pop(0)
    selection = json.loads(read_owned(directory / "selection.json"))
    if not isinstance(selection, dict) or selection.get("schema") != 1:
        raise ValueError("Unsupported tools selection")
    record = runtime_record(directory, selection.get("current"))
    verify_runtime(record)
    # The environment's Python may track a distro-managed executable. Pin the
    # pure-Python package explicitly so a compatible Python minor update does
    # not move it out of the new interpreter's default site-packages path.
    module = "niri_fx.native_login" if action == "session" else "niri_fx.cli"
    bootstrap = (
        "import sys; "
        "assert sys.version_info >= (3, 10), 'NiriFX tools require Python 3.10 or newer'; "
        "sys.path.insert(0, sys.argv.pop(1)); "
        f"from {module} import main; raise SystemExit(main())"
    )
    command = [record["python"], "-I", "-B", "-c", bootstrap, str(Path(record["package"]).parent)]
    if action == "session":
        if arguments:
            raise ValueError("The session launcher does not accept additional arguments")
        command += ["--root", str(root), "launch"]
    else:
        if action == "studio":
            command += ["studio", "--native-root", str(root)]
        command += arguments
    os.execv(command[0], command)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"NiriFX tools: {error}", file=sys.stderr)
        raise SystemExit(1) from None
