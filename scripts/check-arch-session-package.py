#!/usr/bin/env python3
"""Audit a full-session Arch archive and its paired tools without running Niri.

This is payload/provenance validation, not package authenticity, desktop startup,
or ABI acceptance. Installation/adoption/removal belong to the container harness.
"""

import argparse
import importlib.util
import json
import os
import re
import selectors
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from niri_fx import native_build
from niri_fx.package_session import DESKTOP_ENTRY

PREFIX = "usr/lib/niri-fx/session-candidate"
DESKTOP = "usr/share/wayland-sessions/niri-fx-packaged.desktop"
DISPATCHER = "usr/bin/niri-fx-session"
LICENSES = "usr/share/licenses/niri-fx-compositor-git"
PAYLOAD = {
    DISPATCHER,
    DESKTOP,
    "usr/share/doc/niri-fx-compositor/README.Arch",
    *(
        f"{LICENSES}/{name}"
        for name in ("LICENSE.nirifx", "LICENSE.niri", "LICENSE.packaging", "THIRD_PARTY.md")
    ),
    *(
        f"{PREFIX}/{name}"
        for name in (
            "manifest.json",
            "bin/niri",
            "source/Cargo.lock",
            "source/LICENSE",
            "source/README.md",
        )
    ),
    *(f"{PREFIX}/patches/{name}" for name in native_build.STACKS["fragment"]),
}
METADATA = {".PKGINFO", ".BUILDINFO", ".MTREE"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def decompress(package, output, *, limit=512 * 1024 * 1024, timeout=60):
    """Bound both decompressed bytes and time, including a stalled decoder."""
    deadline = time.monotonic() + timeout
    with (
        subprocess.Popen(
            ["zstd", "-q", "-d", "-c", "--", str(package)],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ) as process,
        selectors.DefaultSelector() as selector,
        output.open("xb") as stream,
    ):
        selector.register(process.stdout, selectors.EVENT_READ)
        total = 0
        try:
            while True:
                remaining = deadline - time.monotonic()
                require(remaining > 0, "Package decompression timed out")
                require(selector.select(remaining), "Package decompression timed out")
                chunk = os.read(process.stdout.fileno(), 1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                require(total <= limit, "Session package exceeds the decompressed size limit")
                stream.write(chunk)
            require(
                process.wait(timeout=max(0.01, deadline - time.monotonic())) == 0,
                "Cannot decompress the session package",
            )
        finally:
            if process.poll() is None:
                process.kill()


def extract_tar(unpacked, destination):
    """Validate every member before extracting regular files into a private root."""
    with tarfile.open(unpacked, "r:") as archive:
        members = archive.getmembers()
        require(len(members) <= 128, "Session package has too many archive members")
        paths = {}
        for member in members:
            path = PurePosixPath(member.name)
            require(
                not path.is_absolute()
                and ".." not in path.parts
                and "\\" not in member.name
                and not any(ord(c) < 32 or ord(c) == 127 for c in member.name),
                f"Unsafe archive path: {member.name!r}",
            )
            name = str(path)
            if name == "." and member.isdir():
                continue
            require(name not in paths, f"Duplicate archive path: {name}")
            require(member.isfile() or member.isdir(), f"Links/devices are unsupported: {name}")
            expected_mode = (
                0o755 if member.isdir() or name in {DISPATCHER, f"{PREFIX}/bin/niri"} else 0o644
            )
            require(member.mode == expected_mode, f"Incorrect system-readable permissions: {name}")
            require(member.uid == member.gid == 0, f"Non-root package ownership: {name}")
            limit = 256 * 1024 * 1024 if name == f"{PREFIX}/bin/niri" else 8 * 1024 * 1024
            require(0 <= member.size <= limit, f"Oversized package member: {name}")
            if member.isfile():
                require(name in PAYLOAD | METADATA, f"Unexpected session package file: {name}")
            paths[name] = member
        files = {name for name, member in paths.items() if member.isfile()}
        require(files == PAYLOAD | METADATA, "Session package payload is incomplete")
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


def package_version(root, tools_pkgver):
    fields = {}
    for line in (root / ".PKGINFO").read_text().splitlines():
        if line and not line.startswith("#"):
            key, value = line.split(" = ", 1)
            fields.setdefault(key, []).append(value)
    require(fields.get("pkgname") == ["niri-fx-compositor-git"], "Wrong session package name")
    require(fields.get("arch") == ["x86_64"], "Expected the native x86_64 package")
    require(
        not any(fields.get(key) for key in ("provides", "conflict", "replaces")),
        "Session package must not provide, conflict with or replace another package",
    )
    dependencies = {re.split(r"[<>=]", value, maxsplit=1)[0] for value in fields.get("depend", [])}
    require(
        {"niri", "niri-fx-git", "python", "bash", "systemd", "dbus", "wayland", "libglvnd"}
        <= dependencies,
        "Stock session lifecycle or explicit runtime dependency is missing",
    )
    versions = fields.get("pkgver", [])
    require(len(versions) == 1, "Expected one package version")
    pattern = r"((?:[0-9]+:)?[0-9]+(?:\.[0-9]+)+\.r[0-9]+\.g[a-f0-9]+)-[0-9]+(?:\.[0-9]+)*"
    own, tools = re.fullmatch(pattern, versions[0]), re.fullmatch(pattern, tools_pkgver)
    require(own is not None and tools is not None, "Expected paired VCS package versions")
    require(own[1] == tools[1], "Compositor and tools packages come from different source versions")
    return versions[0]


def inventory(root, tools_site):
    candidate = root / PREFIX
    manifest = json.loads((candidate / "manifest.json").read_text())
    require(isinstance(manifest, dict), "Candidate manifest must be an object")
    require(
        manifest.get("binary") == "bin/niri" and manifest.get("source") == "source",
        "Candidate paths must use the fixed relative layout",
    )
    metadata = manifest.get("native_build")
    require(isinstance(metadata, dict), "Candidate build metadata must be an object")
    inputs = metadata.get("inputs")
    require(isinstance(inputs, dict), "Candidate build inputs must be an object")
    require(inputs.get("variant") == "fragment", "Candidate must contain the full patch stack")
    patches = inputs.get("patches")
    require(
        isinstance(patches, list)
        and all(isinstance(item, dict) for item in patches)
        and tuple(item.get("file") for item in patches) == native_build.STACKS["fragment"],
        "Candidate requires all four current session patches",
    )
    report = native_build.inspect(
        candidate / "manifest.json",
        source=candidate / "source",
        repository=ROOT,
        desktop=True,
        patch_directory=candidate / "patches",
    )
    require(
        report["status"] == "metadata-match", f"Candidate provenance failed: {report['reasons']}"
    )
    for name in native_build.STACKS["fragment"]:
        require(
            (candidate / "patches" / name).read_bytes()
            == (ROOT / "experimental" / name).read_bytes(),
            f"Candidate patch differs from the reviewed checkout: {name}",
        )
    binary = candidate / "bin/niri"
    require(os.access(binary, os.X_OK), "Compositor is not executable")
    with binary.open("rb") as stream:
        header = stream.read(20)
    require(
        header[:6] == b"\x7fELF\x02\x01" and header[18:20] == b"\x3e\x00",
        "Expected an x86_64 Linux ELF executable",
    )
    require((root / DESKTOP).read_bytes() == DESKTOP_ENTRY, "Incorrect packaged session entry")
    dispatcher = (root / DISPATCHER).read_bytes()
    require(
        dispatcher
        == (tools_site / "niri_fx/package_session.py").read_bytes()
        == (ROOT / "niri_fx/package_session.py").read_bytes(),
        "Dispatcher differs from its paired tools or reviewed checkout",
    )
    require(dispatcher.startswith(b"#!/usr/bin/python3\n"), "Dispatcher must use system Python")
    require(os.access(root / DISPATCHER, os.X_OK), "Dispatcher is not executable")
    for path in (root / LICENSES).iterdir():
        require(path.stat().st_size > 100, f"Empty license/notice: {path.name}")
    require(
        (root / LICENSES / "LICENSE.niri").read_bytes()
        == (candidate / "source/LICENSE").read_bytes(),
        "Upstream license differs between candidate and package notice",
    )
    require((candidate / "source/README.md").stat().st_size > 100, "Missing upstream README")
    return report, manifest["binary_sha256"]


def check(package, tools_package):
    spec = importlib.util.spec_from_file_location(
        "arch_tools_check", ROOT / "scripts/check-arch-package.py"
    )
    tools = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tools)
    with tempfile.TemporaryDirectory(prefix="nirifx-session-package-") as directory:
        temporary = Path(directory)
        tools_temp, tools_root, root = (
            temporary / name for name in ("tools", "tools-payload", "payload")
        )
        for path in (tools_temp, tools_root, root):
            path.mkdir()
        tools_files = tools.extract(tools_package, tools_root, tools_temp)
        tools_name, tools_pkgver, version = tools.package_version(tools_root)
        require(tools_name == "niri-fx-git", "Development compositor requires niri-fx-git tools")
        site = tools.inventory(tools_root, tools_files, tools_name, version)
        tar = temporary / "session.tar"
        decompress(package, tar)
        files = extract_tar(tar, root)
        pkgver = package_version(root, tools_pkgver)
        report, binary_sha256 = inventory(root, site)
        return {
            "status": "passed",
            "pkgname": "niri-fx-compositor-git",
            "pkgver": pkgver,
            "package_sha256": native_build.digest(package),
            "tools_package_sha256": native_build.digest(tools_package),
            "files": len(files),
            "build_id": report["build_id"],
            "binary_sha256": binary_sha256,
            "scope": "archive ownership and paired payload identities; no executable or session run",
            "runtime_acceptance": "not_assessed",
            "physical_desktop_acceptance": "not_assessed",
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--tools-package", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.package.resolve(), args.tools_package.resolve()), indent=2))


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        tarfile.TarError,
        subprocess.SubprocessError,
    ) as error:
        raise SystemExit(f"Arch session package check failed: {error}") from None
