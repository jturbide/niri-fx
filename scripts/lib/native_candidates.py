"""Owned, non-reused build attempts; success is compilation evidence, not activation."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .native_build import STACKS, digest


def _atomic_json(path, value, *, exclusive=False):
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(json.dumps(value, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        if exclusive:
            # Publish a complete file without replacing even an unexpected
            # existing destination. The temporary file is on the same filesystem.
            os.link(temporary, path)
        else:
            os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _copy_verified(source, destination, expected, *, executable=False):
    """Copy bytes into a new inode, rejecting drift and existing destinations."""
    if digest(source) != expected:
        raise ValueError("Input changed before copying")
    with source.open("rb") as incoming, destination.open("xb") as outgoing:
        shutil.copyfileobj(incoming, outgoing)
        outgoing.flush()
        os.fsync(outgoing.fileno())
    if digest(destination) != expected or digest(source) != expected:
        raise ValueError("Input changed while copying")
    if executable:
        destination.chmod(0o755)


class Candidate:
    """A single attempt with private source, target, logs and final output paths.

    There is no resume, automatic selection or cleanup operation. A hard-killed
    process may leave status=building; only manifest.json denotes a finished
    build. Failed and interrupted source trees and logs remain available.
    """

    def __init__(self, parent, variant):
        if variant not in STACKS:
            raise ValueError("Unknown native build variant")
        parent.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix=f"{variant}-", dir=parent)).resolve()
        self.source = self.root / "source"
        self.target = self.root / "target"
        self.inputs = self.root / "patches"
        self.logs = self.root / "logs"
        for path in (self.source, self.target, self.inputs, self.logs, self.root / "bin"):
            path.mkdir()
        self.state = {
            "schema": 1,
            "variant": variant,
            "status": "building",
            "stage": "allocated",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
        }
        self.command_count = 0
        self.record("allocated")

    def record(self, stage, *, status="building", error=None):
        self.state.update(stage=stage, status=status)
        if error is not None:
            self.state["error"] = str(error)
        _atomic_json(self.root / "attempt.json", self.state)

    def snapshot(self, patches):
        self.record("snapshot-inputs")
        frozen, hashes = [], {}
        for source in patches:
            expected = digest(source)
            destination = self.inputs / source.name
            _copy_verified(source, destination, expected)
            frozen.append(destination)
            hashes[source.name] = expected
        return frozen, hashes

    def command(self, *args, cwd=None, env=None, check=True):
        """Retain command output even when a subprocess fails or is interrupted."""
        self.command_count += 1
        prefix = f"{self.command_count:03d}"
        log = self.logs / f"{prefix}.log"
        _atomic_json(
            self.logs / f"{prefix}.json",
            {"argv": list(args), "cwd": str(cwd or self.source)},
            exclusive=True,
        )
        print(f"Running {args[0]} ({self.state['stage']}); log: {log}", flush=True)
        with log.open("x") as output:
            result = subprocess.run(
                args,
                cwd=cwd or self.source,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        result.stdout = log.read_text(errors="replace")
        if check and result.returncode:
            print(result.stdout, end="", file=sys.stderr)
            result.check_returncode()
        return result

    def publish(self, manifest):
        """Publish only a verified copy, never the mutable Cargo output itself."""
        source = Path(manifest["binary"]).resolve()
        if not source.is_relative_to(self.target):
            raise ValueError("Cargo executable is outside this attempt's target directory")
        binary = self.root / "bin/niri"
        _copy_verified(source, binary, manifest["binary_sha256"], executable=True)
        # Public evidence historically omits only the executable path. Keep new
        # location metadata relative so it cannot expose a workspace path there.
        manifest = manifest | {"binary": str(binary), "source": "source"}
        destination = self.root / "manifest.json"
        # Status describes completed checks; manifest publication is the commit
        # point. A hard kill between these writes can leave advisory status only.
        self.record("publish", status="built")
        _atomic_json(destination, manifest, exclusive=True)
        return destination
