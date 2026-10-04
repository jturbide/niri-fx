#!/usr/bin/env python3
"""Build the pinned experiment locally; never install a compositor or service."""

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REVISION = "8ed0da44d974c32c6877d2f4630c314da0717ecb"
PATCH = ROOT / "experimental/niri-movement.patch"
SOURCE = ROOT / "artifacts/niri-src"
POINTER_PATCH = ROOT / "experimental/niri-pointer-wobble.patch"
POINTER_SOURCE = ROOT / "artifacts/niri-pointer-src"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def apply_patches(source, revision, patches):
    """Accept only the pinned tree or the exact selected patch stack.

    A temporary index composes the expected result without changing the checkout.
    Comparing complete diffs also catches local edits outside the experiment;
    applying a new patch must never silently overwrite a contributor's work.
    """
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if head != revision:
        raise SystemExit(
            f"Source revision differs from {revision}; keep it and use a fresh checkout."
        )
    diff_args = ["git", "diff", "HEAD", "--binary", "--full-index"]
    diff = subprocess.check_output(diff_args, cwd=source)
    unknown = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=source
    )
    with tempfile.TemporaryDirectory(prefix="nirifx-patch-index-") as directory:
        env = os.environ | {"GIT_INDEX_FILE": str(Path(directory) / "index")}
        run("git", "read-tree", revision, cwd=source, env=env)
        for patch in patches:
            run("git", "apply", "--cached", str(patch), cwd=source, env=env)
        expected = subprocess.check_output([*diff_args, "--cached"], cwd=source, env=env)
    if unknown or (diff and diff != expected):
        raise SystemExit(
            "Source has changes outside the selected patches; refusing to overwrite them."
        )
    if not diff:
        for patch in patches:
            run("git", "apply", "--index", str(patch), cwd=source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true", help="Build an optimized binary")
    parser.add_argument(
        "--test", action="store_true", help="Run config and animation regression tests"
    )
    parser.add_argument(
        "--pointer-wobble",
        action="store_true",
        help="Build the optional pointer extension in its own checkout and target directory",
    )
    args = parser.parse_args()
    source = POINTER_SOURCE if args.pointer_wobble else SOURCE
    patches = [PATCH, POINTER_PATCH] if args.pointer_wobble else [PATCH]
    # Resolve every input before creating a checkout or invoking Git.
    patch_hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in patches}
    source.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        run("git", "init", str(source))
        run(
            "git",
            "-C",
            str(source),
            "remote",
            "add",
            "origin",
            "https://github.com/niri-wm/niri.git",
        )
        run("git", "-C", str(source), "fetch", "--depth=1", "origin", REVISION)
        run("git", "-C", str(source), "checkout", "-b", "fragments-movement", "FETCH_HEAD")
    apply_patches(source, REVISION, patches)
    env = os.environ.copy()
    toolchain = ROOT / "artifacts/toolchain"
    if (toolchain / "cargo/bin/rustc").exists():
        env.update(RUSTUP_HOME=str(toolchain / "rustup"), CARGO_HOME=str(toolchain / "cargo"))
        env["PATH"] = str(toolchain / "cargo/bin") + os.pathsep + env["PATH"]
    run("rustc", "--version", env=env)
    env.setdefault("CARGO_BUILD_JOBS", "8")
    env.setdefault("CARGO_PROFILE_DEV_DEBUG", "0")
    env["CARGO_TARGET_DIR"] = str(source / "target")
    flags = ["--locked", "--no-default-features"]
    if args.test:
        run("cargo", "test", "--locked", "-p", "niri-config", cwd=source, env=env)
        run("cargo", "test", *flags, "--lib", "layout::tests::animations", cwd=source, env=env)
        run("cargo", "test", *flags, "--lib", "animation::movement::tests", cwd=source, env=env)
        run(
            "cargo", "test", *flags, "--lib", "render_helpers::movement::tests", cwd=source, env=env
        )
        if args.pointer_wobble:
            run("cargo", "test", *flags, "--lib", "pointer_wobble", cwd=source, env=env)
    run("cargo", "build", *flags, *(["--release"] if args.release else []), cwd=source, env=env)
    profile = "release" if args.release else "debug"
    binary = source / "target" / profile / "niri"
    manifest = {
        "revision": REVISION,
        "patch_sha256": patch_hashes[PATCH.name],
        "binary": str(binary),
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    }
    name = "niri-movement-build.json"
    if args.pointer_wobble:
        manifest["pointer_patch_sha256"] = patch_hashes[POINTER_PATCH.name]
        name = "niri-pointer-wobble-build.json"
    (ROOT / "artifacts" / name).write_text(json.dumps(manifest, indent=2) + "\n")
    option = " --pointer-wobble gentle" if args.pointer_wobble else ""
    print(f"Built {binary}\nRun: python3 scripts/nested-demo.py{option}")


if __name__ == "__main__":
    main()
