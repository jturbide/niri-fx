"""Owned, non-reused build attempts; success is compilation evidence, not activation."""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .native_build import STACKS, _read_manifest, digest, inspect

PACKAGING_OPTIONS = {
    "prepared-source": "Pinned Git tree with exactly the full session patch stack applied",
    "build-root": "Directory for fresh private build attempts",
    "cargo-home": "Prepared Cargo dependency cache; packaging builds cannot download dependencies",
    "output": "Fresh destination for the compact relocatable session candidate",
    "target-cache": "Optional trusted target cache copied into the new attempt",
    "strip-program": "Optional absolute path to strip; processes a copy before hashing",
}


def add_packaging_arguments(parser):
    for name, help_text in PACKAGING_OPTIONS.items():
        parser.add_argument("--" + name, type=Path, help=help_text)


def validate_packaging_arguments(parser, args):
    paths = {name: getattr(args, name.replace("-", "_")) for name in PACKAGING_OPTIONS}
    if paths["prepared-source"] is None:
        if any(value is not None for value in paths.values()):
            parser.error("Packaging options require --prepared-source")
        return
    missing = [name for name in ("build-root", "cargo-home", "output") if paths[name] is None]
    if missing:
        parser.error("Prepared builds require " + ", ".join("--" + name for name in missing))
    if args.strip_program is not None and not args.strip_program.is_absolute():
        parser.error("--strip-program must be an absolute executable path")
    for name, value in paths.items():
        if value is not None:
            setattr(args, name.replace("-", "_"), value.expanduser().absolute())
    if args.output.exists() or args.output.is_symlink():
        parser.error("Package output must be a fresh path")
    for name in ("prepared_source", "cargo_home", "target_cache"):
        value = getattr(args, name)
        if value is not None and not value.is_dir():
            parser.error("--" + name.replace("_", "-") + " must be an existing directory")
    source = args.prepared_source.resolve()
    if any(
        getattr(args, name).resolve().is_relative_to(source)
        for name in ("build_root", "cargo_home", "output")
    ):
        parser.error("Build, Cargo cache and output paths must stay outside the prepared source")
    if args.build_root.resolve() == args.output.resolve():
        parser.error("Build attempts and exported output require separate paths")
    if args.strip_program is not None and not (
        args.strip_program.is_file() and os.access(args.strip_program, os.X_OK)
    ):
        parser.error("--strip-program must name an executable file")


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

    def seed_target(self, cache):
        """Copy a trusted local cache; never share writable accepted build output."""
        cache = Path(cache).resolve()
        if (
            not cache.is_dir()
            or cache.is_relative_to(self.root)
            or self.root.is_relative_to(cache)
            or any(self.target.iterdir())
        ):
            raise ValueError("Target cache must be separate from a fresh build attempt")
        # Cargo's cache is an optimization, not provenance. Refuse links and
        # special files so copying cannot import references to mutable outsiders.
        for path in cache.rglob("*"):
            mode = path.lstat().st_mode
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise ValueError("Target cache may contain only regular files and directories")
        self.record("seed-target-cache")
        self.command(
            "cp",
            "-a",
            "--reflink=auto",
            "--no-preserve=ownership",
            str(cache) + "/.",
            str(self.target),
            cwd=self.root,
        )

    def process_binary(self, binary, program):
        """Strip an independent packaging copy before calculating its identity."""
        binary = Path(binary).resolve()
        if not binary.is_relative_to(self.target):
            raise ValueError("Cargo executable is outside this attempt's target directory")
        # Keep packaging output outside Cargo's reusable target cache.
        destination = self.root / "processed/niri"
        destination.parent.mkdir()
        _copy_verified(binary, destination, digest(binary), executable=True)
        self.record("process-binary")
        self.command(str(program), "--strip-unneeded", str(destination), cwd=self.root)
        return destination

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
        if not source.is_relative_to(self.target) and source != self.root / "processed/niri":
            raise ValueError("Candidate executable is outside this attempt's build output")
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

    def export(self, destination):
        """Publish a compact relocatable full-session candidate, with no logs/cache."""
        manifest_path = self.root / "manifest.json"
        manifest_hash = digest(manifest_path)
        manifest = _read_manifest(manifest_path)
        report = inspect(
            manifest_path,
            source=self.source,
            repository=self.root,
            patch_directory=self.inputs,
            desktop=True,
        )
        if report["status"] != "metadata-match":
            raise ValueError("Only a verified desktop candidate can be exported")
        inputs = manifest["native_build"]["inputs"]
        if (
            inputs["variant"] != "fragment"
            or tuple(item["file"] for item in inputs["patches"]) != STACKS["fragment"]
        ):
            raise ValueError("Package export requires the complete four-patch session stack")
        binary = self.root / "bin/niri"
        if Path(manifest["binary"]).resolve() != binary.resolve():
            raise ValueError("Package export requires this attempt's own published binary")
        files = [
            (binary, "bin/niri", manifest["binary_sha256"], True),
            (self.source / "Cargo.lock", "source/Cargo.lock", inputs["cargo_lock_sha256"], False),
        ]
        files.extend(
            (self.inputs / item["file"], "patches/" + item["file"], item["sha256"], False)
            for item in inputs["patches"]
        )
        files.extend(
            (self.source / name, "source/" + name, digest(self.source / name), False)
            for name in ("LICENSE", "README.md")
        )
        destination = Path(destination).absolute()
        # Existing output, including a dangling symlink, is never replaced.
        destination.mkdir(parents=True, exist_ok=False)
        for source, relative, expected, executable in files:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            _copy_verified(source, target, expected, executable=executable)
        if digest(manifest_path) != manifest_hash:
            raise ValueError("Candidate manifest changed during export")
        # The manifest is the commit point; failed copies remain non-installable.
        result = destination / "manifest.json"
        _atomic_json(result, manifest | {"binary": "bin/niri", "source": "source"}, exclusive=True)
        return result
