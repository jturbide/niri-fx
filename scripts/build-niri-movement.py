#!/usr/bin/env python3
"""Build pinned Niri experiments or an unmodified baseline without installing them."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.native_build import REVISION, cargo_artifact, digest, metadata, native_host

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "experimental/niri-movement.patch"
SOURCE = ROOT / "artifacts/niri-src"
POINTER_PATCH = ROOT / "experimental/niri-pointer-wobble.patch"
POINTER_SOURCE = ROOT / "artifacts/niri-pointer-src"
FRAGMENT_PATCH = ROOT / "experimental/niri-fragment-drag.patch"
FRAGMENT_SOURCE = ROOT / "artifacts/niri-fragment-drag-src"
BASELINE_SOURCE = ROOT / "artifacts/niri-unmodified-src"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def apply_patches(source, revision, patches, *, verify_only=False):
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
    if unknown or (diff != expected if verify_only else diff and diff != expected):
        raise SystemExit(
            "Source has changes outside the selected patches; refusing to overwrite them."
        )
    if not diff and not verify_only:
        for patch in patches:
            run("git", "apply", "--index", str(patch), cwd=source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true", help="Build an optimized binary")
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="Keep upstream desktop features (D-Bus, portals and screencasting)",
    )
    parser.add_argument(
        "--test", action="store_true", help="Run config and animation regression tests"
    )
    variants = parser.add_mutually_exclusive_group()
    variants.add_argument(
        "--pointer-wobble",
        action="store_true",
        help="Build the optional pointer extension in its own checkout and target directory",
    )
    variants.add_argument(
        "--fragment-drag",
        action="store_true",
        help="Build continuous fragment motion on top of movement and pointer patches",
    )
    variants.add_argument(
        "--unmodified",
        action="store_true",
        help="Build the identical pinned revision without patches in a separate checkout",
    )
    args = parser.parse_args()
    if args.unmodified:
        source, patches = BASELINE_SOURCE, []
        variant = "unmodified"
    elif args.fragment_drag:
        source, patches = FRAGMENT_SOURCE, [PATCH, POINTER_PATCH, FRAGMENT_PATCH]
        variant = "fragment"
    else:
        source = POINTER_SOURCE if args.pointer_wobble else SOURCE
        patches = [PATCH, POINTER_PATCH] if args.pointer_wobble else [PATCH]
        variant = "pointer" if args.pointer_wobble else "movement"
    # Resolve every input before creating a checkout or invoking Git.
    patch_hashes = {path.name: digest(path) for path in patches}
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
        run("git", "-C", str(source), "checkout", "--detach", "FETCH_HEAD")
    apply_patches(source, REVISION, patches)
    lock_sha256 = digest(source / "Cargo.lock")
    env = os.environ.copy()
    toolchain = ROOT / "artifacts/toolchain"
    if (toolchain / "cargo/bin/rustc").exists():
        env.update(RUSTUP_HOME=str(toolchain / "rustup"), CARGO_HOME=str(toolchain / "cargo"))
        env["PATH"] = str(toolchain / "cargo/bin") + os.pathsep + env["PATH"]
    # Resolve once, with relative paths interpreted as Cargo sees them from the
    # source tree. Passing RUSTC explicitly prevents build.rustc from silently
    # selecting a different compiler than the one whose version we record.
    search_path = os.pathsep.join(
        str(Path(part) if Path(part).is_absolute() else source / part)
        for part in env.get("PATH", os.defpath).split(os.pathsep)
    )
    compiler = env.get("RUSTC", "rustc")
    if os.sep in compiler and not Path(compiler).is_absolute():
        compiler = str(source / compiler)
    compiler = shutil.which(compiler, path=search_path)
    if not compiler:
        raise SystemExit("Selected Rust compiler was not found on the build PATH")
    env["RUSTC"] = compiler
    rustc = subprocess.check_output([compiler, "--version"], cwd=source, env=env, text=True).strip()
    rustc_verbose = subprocess.check_output(
        [compiler, "-vV"], cwd=source, env=env, text=True
    ).strip()
    host = native_host(rustc, rustc_verbose)
    print(rustc, flush=True)
    env.setdefault("CARGO_BUILD_JOBS", "8")
    env.setdefault("CARGO_PROFILE_DEV_DEBUG", "0")
    env["CARGO_TARGET_DIR"] = str(source / "target")
    flags = ["--locked"] + ([] if args.desktop else ["--no-default-features"])
    if args.test:
        run("cargo", "test", "--locked", "-p", "niri-config", cwd=source, env=env)
        run("cargo", "test", *flags, "--lib", "layout::tests::animations", cwd=source, env=env)
        if not args.unmodified:
            run("cargo", "test", *flags, "--lib", "animation::movement::tests", cwd=source, env=env)
            run("cargo", "test", *flags, "--lib", "animation::size::tests", cwd=source, env=env)
            run("cargo", "test", *flags, "--lib", "resize_close", cwd=source, env=env)
            run(
                "cargo",
                "test",
                *flags,
                "--lib",
                "input::pointer_buttons::tests",
                cwd=source,
                env=env,
            )
            run("cargo", "test", *flags, "--lib", "tests::pointer_ownership", cwd=source, env=env)
            run(
                "cargo",
                "test",
                *flags,
                "--lib",
                "render_helpers::resize::tests",
                cwd=source,
                env=env,
            )
            run(
                "cargo",
                "test",
                *flags,
                "--lib",
                "render_helpers::movement::tests",
                cwd=source,
                env=env,
            )
        if args.pointer_wobble or args.fragment_drag:
            run("cargo", "test", *flags, "--lib", "pointer_wobble", cwd=source, env=env)
        if args.fragment_drag:
            run("cargo", "test", *flags, "--lib", "fragment_motion", cwd=source, env=env)
            run("cargo", "test", *flags, "--lib", "fragment_mesh", cwd=source, env=env)
    result = subprocess.run(
        [
            "cargo",
            "build",
            *flags,
            *(["--release"] if args.release else []),
            "--message-format=json-render-diagnostics",
        ],
        cwd=source,
        env=env,
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )
    # Cargo JSON carries rendered compiler diagnostics on stdout. Keep those
    # useful errors visible even when the build fails before artifact metadata.
    for line in result.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            print(line, file=sys.stderr)
            continue
        if isinstance(item, dict) and item.get("reason") == "compiler-message":
            rendered = item.get("message", {}).get("rendered")
            if rendered:
                print(rendered, end="", file=sys.stderr)
    result.check_returncode()
    profile = "release" if args.release else "debug"
    binary, features, target = cargo_artifact(result.stdout, source / "target", profile, host)
    # Do not publish evidence for inputs that changed while Cargo was running.
    apply_patches(source, REVISION, patches, verify_only=True)
    if digest(source / "Cargo.lock") != lock_sha256 or any(
        digest(path) != patch_hashes[path.name] for path in patches
    ):
        raise SystemExit("Build inputs changed during compilation; manifest was not updated")
    manifest = {
        "revision": REVISION,
        "binary": str(binary),
        "binary_sha256": digest(binary),
        "build_profile": profile,
        "build_flags": flags,
        "rustc": rustc,
    }
    name = "niri-movement-build.json"
    if args.unmodified:
        manifest["unmodified"] = True
        name = "niri-unmodified-build.json"
    else:
        manifest["patch_sha256"] = patch_hashes[PATCH.name]
    if args.pointer_wobble or args.fragment_drag:
        manifest["pointer_patch_sha256"] = patch_hashes[POINTER_PATCH.name]
        name = "niri-pointer-wobble-build.json"
    if args.fragment_drag:
        manifest["fragment_patch_sha256"] = patch_hashes[FRAGMENT_PATCH.name]
        name = "niri-fragment-drag-build.json"
    manifest["native_build"] = metadata(
        manifest,
        variant=variant,
        lock_sha256=lock_sha256,
        target=target,
        features=features,
        rustc_verbose=rustc_verbose,
    )
    destination = ROOT / "artifacts" / name
    with tempfile.NamedTemporaryFile(mode="w", dir=destination.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(json.dumps(manifest, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    if args.unmodified:
        print(f"Built unmodified baseline {binary}")
    elif args.fragment_drag:
        print(f"Built {binary}\nRun: python3 scripts/test-fragment-drag.py")
    else:
        option = " --pointer-wobble gentle" if args.pointer_wobble else ""
        print(f"Built {binary}\nRun: python3 scripts/nested-demo.py{option}")


if __name__ == "__main__":
    main()
