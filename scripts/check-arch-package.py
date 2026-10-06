#!/usr/bin/env python3
"""Smoke-test a tools-only Arch package without installing it or opening a desktop.

Requires zstd. Extracts bounded regular files into temporary storage and runs the
packaged entry point with isolated user directories, outside the checkout.
"""

import argparse
import base64
import configparser
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath

DESKTOP = "usr/share/applications/niri-fx-studio.desktop"
ICON = "usr/share/icons/hicolor/scalable/apps/niri-fx.svg"
SITE = r"usr/lib/python[0-9]+\.[0-9]+/site-packages"
RESOURCES = (
    "preview.html",
    "studio.js",
    "studio.css",
    "library.js",
    "effect-core.js",
    "motion-preview.js",
    "pointer-preview.js",
    "combo-preview.js",
    "assets/niri-fx.svg",
    "agent_data/nirifx/SKILL.md",
    "qml/shell.qml",
    "qml/NiriFXPicker.qml",
    "qml/NiriFXController.qml",
    "gtk/app.mjs",
    "gtk/picker.mjs",
    "gtk/controller.mjs",
    "gtk/transport.mjs",
    "gtk/picker.css",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def allowed_file(name):
    return (
        name in {".PKGINFO", ".BUILDINFO", ".MTREE", "usr/bin/niri-fx", DESKTOP, ICON}
        or re.fullmatch(SITE + r"/(?:niri_fx|niri_fx-[^/]+\.dist-info)/.+", name)
        or name.startswith("usr/share/doc/niri-fx/")
        or re.fullmatch(r"usr/share/licenses/niri-fx(?:-git)?/.+", name)
    )


def extract(package, destination, temporary):
    """Validate the entire member list before writing any payload files."""
    unpacked = temporary / "package.tar"
    with unpacked.open("wb") as output:
        with subprocess.Popen(
            ["zstd", "-q", "-d", "-c", "--", str(package)], stdout=subprocess.PIPE
        ) as process:
            size = 0
            try:
                while chunk := process.stdout.read(1024 * 1024):
                    size += len(chunk)
                    require(size <= 128 * 1024 * 1024, "Tools package exceeds 128 MiB")
                    output.write(chunk)
                require(process.wait(timeout=30) == 0, "Cannot decompress the Arch package")
            finally:
                if process.poll() is None:
                    process.kill()
    with tarfile.open(unpacked, "r:") as archive:
        members = archive.getmembers()
        require(len(members) <= 4096, "Tools package has too many archive members")
        paths = {}
        for member in members:
            path = PurePosixPath(member.name)
            require(
                not path.is_absolute()
                and ".." not in path.parts
                and "\\" not in member.name
                and not any(ord(c) < 32 for c in member.name),
                f"Unsafe archive path: {member.name!r}",
            )
            name = str(path)
            if name == "." and member.isdir():
                continue
            require(name not in paths, f"Duplicate archive path: {name}")
            require(member.isfile() or member.isdir(), f"Links/devices are unsupported: {name}")
            require(not member.mode & 0o6022, f"Unsafe file permissions: {name}")
            require(member.size <= 32 * 1024 * 1024, f"Oversized package member: {name}")
            if member.isfile():
                require(bool(allowed_file(name)), f"Unexpected tools-only package file: {name}")
                require(
                    not name.endswith(".desktop") or name == DESKTOP,
                    f"Unexpected desktop/session entry: {name}",
                )
            paths[name] = member
        files = {name for name, member in paths.items() if member.isfile()}
        ancestors = {str(parent) for name in files for parent in PurePosixPath(name).parents}
        require(
            all(member.isfile() or name in ancestors for name, member in paths.items()),
            "Unexpected empty package directory",
        )
        for name, member in paths.items():
            target = destination / name
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as incoming, target.open("xb") as output:
                    shutil.copyfileobj(incoming, output)
                target.chmod(member.mode & 0o777)
    return files


def package_version(root):
    fields = {}
    for line in (root / ".PKGINFO").read_text().splitlines():
        if line and not line.startswith("#"):
            key, value = line.split(" = ", 1)
            fields.setdefault(key, []).append(value)
    names = fields.get("pkgname", [])
    require(
        len(names) == 1 and names[0] in {"niri-fx", "niri-fx-git"},
        "Expected the niri-fx or niri-fx-git tools package",
    )
    relationships = {
        key: {re.split(r"[<>=]", value, maxsplit=1)[0] for value in fields.get(key, [])}
        for key in ("provides", "conflict", "replaces")
    }
    require(not relationships["replaces"], "Tools packages must not replace another package")
    require(
        all(values <= {"niri-fx", "niri-fx-git"} for values in relationships.values()),
        "Tools packages must not provide or conflict with stock Niri or unrelated packages",
    )
    versions = fields.get("pkgver", [])
    require(len(versions) == 1, "Expected one package version")
    match = re.fullmatch(r"(?:[0-9]+:)?(.+)-[0-9]+(?:\.[0-9]+)*", versions[0])
    require(match is not None, "Unsupported package version/pkgrel")
    version = match[1]
    if names[0] == "niri-fx-git":
        vcs = re.fullmatch(r"(.+)\.r[0-9]+\.g[a-f0-9]+", version)
        require(vcs is not None, "VCS pkgver must end in .r<commit-count>.g<short-hash>")
        require(
            "niri-fx" in relationships["provides"] and "niri-fx" in relationships["conflict"],
            "niri-fx-git must provide and conflict with niri-fx",
        )
        version = vcs[1]
    return names[0], versions[0], version


def inventory(root, files, pkgname, version):
    license_prefix = f"usr/share/licenses/{pkgname}/"
    require(
        all(
            name.startswith(license_prefix)
            for name in files
            if name.startswith("usr/share/licenses/")
        ),
        "License directory must match the package name",
    )
    sites = list(root.glob("usr/lib/python*/site-packages"))
    require(len(sites) == 1, "Expected exactly one Python site-packages directory")
    site = sites[0]
    distributions = list(site.glob("niri_fx-*.dist-info"))
    require(len(distributions) == 1, "Expected exactly one NiriFX distribution")
    distribution = distributions[0]
    metadata = BytesParser().parsebytes((distribution / "METADATA").read_bytes())
    require(
        metadata["Name"] == "niri-fx" and metadata["Version"] == version,
        "Wheel metadata differs from .PKGINFO",
    )
    recorded = set()
    for name, checksum, size in csv.reader((distribution / "RECORD").read_text().splitlines()):
        path = (site / name).resolve()
        require(path.is_relative_to(root) and path.is_file(), f"Missing/unsafe RECORD file: {name}")
        require(path not in recorded, f"Duplicate RECORD file: {name}")
        recorded.add(path)
        content = path.read_bytes()
        if checksum:
            expected = "sha256=" + base64.urlsafe_b64encode(
                hashlib.sha256(content).digest()
            ).decode().rstrip("=")
            require(checksum == expected and size == str(len(content)), f"RECORD mismatch: {name}")
        else:
            require(
                path == distribution / "RECORD" or path.suffix == ".pyc",
                f"Unverified runtime resource: {name}",
            )
    runtime = {root / name for name in files if name.startswith(str(site.relative_to(root)) + "/")}
    # python-installer compiles bytecode after writing RECORD. Require source
    # for those generated caches; every other runtime file must be inventoried.
    for path in runtime:
        if path.suffix == ".pyc":
            require(
                path.parent.name == "__pycache__"
                and (path.parent.parent / (path.name.split(".", 1)[0] + ".py")).is_file(),
                f"Unexpected bytecode without source: {path.name}",
            )
    require(
        {path for path in runtime if path.suffix != ".pyc"} | {root / "usr/bin/niri-fx"}
        == {path for path in recorded if path.suffix != ".pyc"},
        "Incomplete installed RECORD inventory",
    )
    for name in RESOURCES:
        require((site / "niri_fx" / name).is_file(), f"Missing packaged resource: {name}")
    licenses = root / license_prefix
    for name in ("LICENSE", "THIRD_PARTY.md", "LICENSE.packaging"):
        require(
            (licenses / name).is_file() and (licenses / name).stat().st_size > 100,
            f"Missing license: {name}",
        )
    require(
        any(
            path.is_file() and path.stat().st_size > 100 for path in licenses.rglob("COPYING-NIRI")
        ),
        "Missing upstream COPYING-NIRI",
    )
    require(
        (root / ICON).read_bytes() == (site / "niri_fx/assets/niri-fx.svg").read_bytes(),
        "Installed application icon differs from the packaged icon",
    )
    desktop = configparser.ConfigParser(interpolation=None, strict=True)
    desktop.read(root / DESKTOP)
    require(desktop.sections() == ["Desktop Entry"], "Unexpected desktop actions/sections")
    entry = desktop["Desktop Entry"]
    for key, value in {
        "Type": "Application",
        "Exec": "/usr/bin/niri-fx studio --active",
        "Icon": "niri-fx",
        "Terminal": "false",
    }.items():
        require(entry.get(key) == value, f"Unexpected desktop {key}")
    require(
        "Path" not in entry and entry.get("TryExec", "/usr/bin/niri-fx") == "/usr/bin/niri-fx",
        "Desktop pins an unexpected path",
    )
    executable = root / "usr/bin/niri-fx"
    require(os.access(executable, os.X_OK), "Packaged CLI is not executable")
    require(
        bool(
            re.fullmatch(
                rb"#!/usr/bin/python(?:3(?:\.[0-9]+)?)?", executable.read_bytes().splitlines()[0]
            )
        ),
        "CLI shebang must use the system Python",
    )
    return site


def smoke(root, site, temporary, version):
    env = os.environ.copy()
    for key in (
        "NIRI_SOCKET",
        "WAYLAND_DISPLAY",
        "DISPLAY",
        "DBUS_SESSION_BUS_ADDRESS",
        "XDG_RUNTIME_DIR",
        "PYTHONPATH",
        "PYTHONHOME",
        "VIRTUAL_ENV",
    ):
        env.pop(key, None)
    homes = []
    for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        path = temporary / key.lower()
        path.mkdir()
        env[key] = str(path)
        homes.append(path)
    bootstrap = (
        "import pathlib,runpy,sys; sys.path.insert(0,sys.argv.pop(1)); import niri_fx; "
        "assert pathlib.Path(niri_fx.__file__).is_relative_to(sys.path[0]); "
        "runpy.run_path(sys.argv.pop(1),run_name='__main__')"
    )

    def cli(*arguments):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                bootstrap,
                str(site),
                str(root / "usr/bin/niri-fx"),
                *map(str, arguments),
            ],
            cwd=temporary,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        require(
            result.returncode == 0, f"Packaged CLI failed ({arguments[0]}): {result.stderr.strip()}"
        )
        return result.stdout

    require(cli("--version").strip() == version, "CLI version differs from .PKGINFO")
    catalog = json.loads(cli("list", "--documents"))
    require(isinstance(catalog, dict) and "balanced" in catalog, "Packaged catalog is incomplete")
    profile = json.loads(cli("profile", "--name", "Package Smoke", "--fragment-preset", "tear"))
    require(
        profile["schema"] == 4 and len(profile["fragment_motion"]) == 18,
        "Schema 4 fragment response is incomplete",
    )
    require(
        set(profile["actions"]) == {"open", "close", "resize", "movement", "swap"},
        "Schema 4 actions are incomplete",
    )
    document = temporary / "profile.json"
    document.write_text(json.dumps(profile))
    require(
        json.loads(cli("inspect", "--custom", document)) == profile, "Profile round trip changed"
    )
    kdl = cli("render", "--custom", document)
    require("window-open" in kdl and "window-close" in kdl, "Stock effects were not rendered")
    require(
        not any(value in kdl for value in ("window-movement", "window-swap", "fragment-motion")),
        "Stock export contains native response",
    )
    preview = temporary / "preview.html"
    cli("preview", "--custom", document, "--output", preview)
    match = re.search(
        r'<script id="effect-catalog" type="application/json">(.*?)</script>',
        preview.read_text(),
        re.S,
    )
    require(match is not None, "Offline preview catalog is missing")
    embedded = json.loads(match[1])
    require(
        embedded["profile"] == profile and len(embedded["fragment_controls"]) == 18,
        "Offline preview lost portable response data",
    )
    require(
        set(embedded["fragment_presets"]) == {"gentle", "tear", "cascade"},
        "Offline fragment presets are incomplete",
    )
    require("NiriFX" in cli("agent-info", "--skill"), "Packaged agent skill is unavailable")
    require(not any(list(path.rglob("*")) for path in homes), "Read-only smoke changed user files")
    return len(catalog)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path, help="Built niri-fx or niri-fx-git .pkg.tar.zst")
    args = parser.parse_args()
    require(shutil.which("zstd") is not None, "Install zstd to read the Arch package")
    package = args.package.resolve()
    require(package.is_file(), "Package must be a regular file")
    with tempfile.TemporaryDirectory(prefix="nirifx-arch-package-") as directory:
        temporary = Path(directory)
        root = temporary / "payload"
        root.mkdir()
        files = extract(package, root, temporary)
        pkgname, pkgver, version = package_version(root)
        site = inventory(root, files, pkgname, version)
        styles = smoke(root, site, temporary, version)
    print(
        json.dumps(
            {
                "package": package.name,
                "pkgname": pkgname,
                "pkgver": pkgver,
                "version": version,
                "sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
                "files": len(files),
                "catalog_entries": styles,
                "status": "passed",
                "scope": "extracted tools-only CLI/resources; no installation or desktop connection",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        KeyError,
        configparser.Error,
        csv.Error,
        tarfile.TarError,
        subprocess.SubprocessError,
    ) as error:
        raise SystemExit(f"Arch package check failed: {error}") from None
