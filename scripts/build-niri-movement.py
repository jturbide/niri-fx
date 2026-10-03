#!/usr/bin/env python3
"""Build the pinned experiment locally; never install a compositor or service."""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = "8ed0da44d974c32c6877d2f4630c314da0717ecb"
PATCH = ROOT / "experimental/niri-movement.patch"
SOURCE = ROOT / "artifacts/niri-src"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true", help="Build an optimized binary")
    parser.add_argument(
        "--test", action="store_true", help="Run config and animation regression tests"
    )
    args = parser.parse_args()
    patch = PATCH.read_bytes()
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    if not SOURCE.exists():
        run("git", "init", str(SOURCE))
        run(
            "git",
            "-C",
            str(SOURCE),
            "remote",
            "add",
            "origin",
            "https://github.com/niri-wm/niri.git",
        )
        run("git", "-C", str(SOURCE), "fetch", "--depth=1", "origin", REVISION)
        run("git", "-C", str(SOURCE), "checkout", "-b", "fragments-movement", "FETCH_HEAD")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True).strip()
    if head != REVISION:
        raise SystemExit(
            f"Source revision differs from {REVISION}; keep it and use a fresh checkout."
        )
    diff = subprocess.check_output(["git", "diff", "HEAD", "--binary", "--full-index"], cwd=SOURCE)
    unknown = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=SOURCE
    )
    if unknown or (diff and diff != patch):
        raise SystemExit(
            "Source has changes outside the shipped patch; refusing to overwrite them."
        )
    if not diff:
        run("git", "apply", "--index", str(PATCH), cwd=SOURCE)
    env = os.environ.copy()
    toolchain = ROOT / "artifacts/toolchain"
    if (toolchain / "cargo/bin/rustc").exists():
        env.update(RUSTUP_HOME=str(toolchain / "rustup"), CARGO_HOME=str(toolchain / "cargo"))
        env["PATH"] = str(toolchain / "cargo/bin") + os.pathsep + env["PATH"]
    run("rustc", "--version", env=env)
    env.setdefault("CARGO_BUILD_JOBS", "8")
    env.setdefault("CARGO_PROFILE_DEV_DEBUG", "0")
    env["CARGO_TARGET_DIR"] = str(SOURCE / "target")
    flags = ["--locked", "--no-default-features"]
    if args.test:
        run("cargo", "test", "--locked", "-p", "niri-config", cwd=SOURCE, env=env)
        run("cargo", "test", *flags, "--lib", "layout::tests::animations", cwd=SOURCE, env=env)
        run("cargo", "test", *flags, "--lib", "animation::movement::tests", cwd=SOURCE, env=env)
        run(
            "cargo", "test", *flags, "--lib", "render_helpers::movement::tests", cwd=SOURCE, env=env
        )
    run("cargo", "build", *flags, *(["--release"] if args.release else []), cwd=SOURCE, env=env)
    profile = "release" if args.release else "debug"
    binary = SOURCE / "target" / profile / "niri"
    manifest = {
        "revision": REVISION,
        "patch_sha256": hashlib.sha256(patch).hexdigest(),
        "binary": str(binary),
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    }
    (ROOT / "artifacts/niri-movement-build.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Built {binary}\nRun: python3 scripts/nested-demo.py")


if __name__ == "__main__":
    main()
