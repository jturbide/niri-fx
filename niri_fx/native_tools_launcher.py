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
RECOVERY = (
    "Use a TTY or stock Niri to repair Python or review native adopt or native tools-update. "
    "The retained selection is unchanged."
)


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
        or type(record.get("schema")) is not int
        or record["schema"] not in (1, 2)
        or fingerprint(record) != identifier
    ):
        raise ValueError("Tool runtime receipt identity changed")
    if record["schema"] == 2:
        package = Path(record["package"])
        if package.parent.parent != directory / "packages":
            raise ValueError("Retained package does not belong to this tools installation")
    return record


def package_files(package, *, allow_bytecode=True):
    """Inventory pure-Python source/resources without following symlinks."""
    package = Path(package)
    if not package.is_absolute() or any(p.is_symlink() for p in (package, *package.parents)):
        raise ValueError("Retained package paths must be absolute and must not contain symlinks")
    files = []
    for path in package.rglob("*"):
        if path.is_symlink():
            raise ValueError("Retained package files must not be symlinks")
        if not allow_bytecode and path.suffix == ".pyc":
            raise ValueError("Retained pure-Python snapshots must not contain bytecode caches")
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        info = path.stat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_size > 32 * 1024 * 1024:
            raise ValueError("Runtime files must be bounded regular files")
        if path.suffix in {".so", ".pyd", ".dll"}:
            raise ValueError("Package adoption supports pure-Python runtimes only")
        files.append(path)
        if len(files) > 2048:
            raise ValueError("Runtime inventory exceeds its file limit")
    return sorted(files)


def verify_runtime(record):
    """Detect removed or edited runtimes before executing the retained interpreter."""
    if set(record) != {"schema", "python", "package", "version", "files", "desktop"}:
        raise ValueError("Unsupported tools runtime receipt")
    python = Path(record["python"])
    package = Path(record["package"])
    prefix = python.parent.parent
    schema = record["schema"]
    if type(schema) is not int or schema not in (1, 2):
        raise ValueError("Unsupported tools runtime receipt")
    if schema == 1:
        if (
            not python.is_absolute()
            or not package.is_absolute()
            or not package.is_relative_to(prefix)
        ):
            raise ValueError("Retained tools package must belong to its virtual environment")
    elif (
        python != Path("/usr/bin/python3")
        or package.name != "niri_fx"
        or not re.fullmatch(r"[a-f0-9]{64}", package.parent.name)
        or package.parent.parent.name != "packages"
        or package.parent.parent.parent.name != "tools"
    ):
        raise ValueError("Invalid retained package location or system interpreter")
    files = record["files"]
    if not isinstance(files, dict) or not 1 <= len(files) <= 2048:
        raise ValueError("Invalid tools runtime file inventory")
    actual = (
        {str(p) for p in package_files(package, allow_bytecode=False)}
        if schema == 2
        else {
            str(p)
            for p in package.rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        }
    )
    if schema == 1:
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
        if schema == 2 and (info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600):
            raise ValueError("Retained package files must be private and user-owned")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Retained tools runtime changed: {path}")
    if schema == 2:
        relative = {str(Path(path).relative_to(package)): value for path, value in files.items()}
        if fingerprint(relative) != package.parent.name:
            raise ValueError("Retained package content identity changed")
    python = Path(record["python"])
    package = Path(record["package"])
    if str(package / "__init__.py") not in files:
        raise ValueError("Tools runtime inventory is incomplete")
    if not python.is_file() or not os.access(python, os.X_OK):
        raise ValueError(f"Retained tools interpreter is unavailable: {python}. {RECOVERY}")


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
        "import sys\n"
        "try:\n"
        "    if sys.version_info < (3, 10):\n"
        "        raise RuntimeError('NiriFX tools require Python 3.10 or newer')\n"
        "    sys.path.insert(0, sys.argv.pop(1))\n"
        f"    from {module} import main\n"
        "except Exception as error:\n"
        f"    print('NiriFX tools could not load: ' + str(error) + '. ' + {RECOVERY!r}, file=sys.stderr)\n"
        "    raise SystemExit(1)\n"
        "raise SystemExit(main())\n"
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
    try:
        os.execv(command[0], command)
    except OSError as error:
        raise ValueError(
            f"Retained tools interpreter could not start: {error}. {RECOVERY}"
        ) from error


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"NiriFX tools: {error}", file=sys.stderr)
        raise SystemExit(1) from None
