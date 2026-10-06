#!/usr/bin/env python3
"""Native payload helpers for check-arch-package.py's complete package audit.

No executable is run here. This checks recorded provenance, not package
authenticity, desktop startup or ABI acceptance. There is no separate session
package or paired-package interface.
"""

import json
import os
import selectors
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from niri_fx import native_build
from niri_fx.package_session import DESKTOP_ENTRY

PREFIX = "usr/lib/niri-fx/session-candidate"
DESKTOP = "usr/share/wayland-sessions/niri-fx-packaged.desktop"
DISPATCHER = "usr/bin/niri-fx-session"
PAYLOAD = {
    DISPATCHER,
    DESKTOP,
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


def require(condition, message):
    if not condition:
        raise ValueError(message)


def decompress(package, output, *, limit=640 * 1024 * 1024, timeout=60):
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
                require(total <= limit, "Package exceeds the decompressed size limit")
                stream.write(chunk)
            require(
                process.wait(timeout=max(0.01, deadline - time.monotonic())) == 0,
                "Cannot decompress the package",
            )
        finally:
            if process.poll() is None:
                process.kill()


def inventory(root, site, pkgname):
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
    require(
        inputs.get("target") == "x86_64-unknown-linux-gnu",
        "Candidate build target must match the x86_64 package",
    )
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
        == (site / "niri_fx/package_session.py").read_bytes()
        == (ROOT / "niri_fx/package_session.py").read_bytes(),
        "Dispatcher differs from its packaged module or reviewed checkout",
    )
    require(dispatcher.startswith(b"#!/usr/bin/python3\n"), "Dispatcher must use system Python")
    require(os.access(root / DISPATCHER, os.X_OK), "Dispatcher is not executable")
    licenses = root / "usr/share/licenses" / pkgname
    for path in licenses.iterdir():
        require(path.stat().st_size > 100, f"Empty license/notice: {path.name}")
    require(
        (licenses / "LICENSE.niri").read_bytes() == (candidate / "source/LICENSE").read_bytes(),
        "Upstream license differs between candidate and package notice",
    )
    require((candidate / "source/README.md").stat().st_size > 100, "Missing upstream README")
    return {
        "build_id": report["build_id"],
        "manifest_sha256": native_build.digest(candidate / "manifest.json"),
        "binary_sha256": manifest["binary_sha256"],
        "cargo_lock_sha256": inputs["cargo_lock_sha256"],
        "patch_sha256": {item["file"]: item["sha256"] for item in patches},
        "runtime_acceptance": "not_assessed",
        "physical_desktop_acceptance": "not_assessed",
    }


if __name__ == "__main__":
    raise SystemExit("Use check-arch-package.py PACKAGE for the complete package audit")
