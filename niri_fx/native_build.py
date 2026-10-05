"""Versioned build evidence and read-only checks for local Niri experiments.

A metadata match proves recorded file identities, not executable safety, renderer
support, reproducibility, or desktop acceptance. Ambient Cargo configuration,
compiler wrappers, RUSTFLAGS and system libraries are not fully captured.
This module never runs binaries.
"""

import hashlib
import json
import os
import re
import stat
from pathlib import Path

SCHEMA = 1
REVISION = "8ed0da44d974c32c6877d2f4630c314da0717ecb"
STACKS = {
    "unmodified": (),
    "movement": ("niri-movement.patch",),
    "pointer": ("niri-movement.patch", "niri-pointer-wobble.patch"),
    "fragment": (
        "niri-movement.patch",
        "niri-pointer-wobble.patch",
        "niri-fragment-drag.patch",
    ),
}
PATCH_FIELDS = {
    "niri-movement.patch": "patch_sha256",
    "niri-pointer-wobble.patch": "pointer_patch_sha256",
    "niri-fragment-drag.patch": "fragment_patch_sha256",
}
DESKTOP_FEATURES = frozenset({"dbus", "pipewire", "systemd", "xdp-gnome-screencast"})


def digest(path):
    value = hashlib.sha256()
    with _regular_file(path) as stream:
        before = os.fstat(stream.fileno())
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
        after = os.fstat(stream.fileno())
        current = Path(path).stat()

        def identity(info):
            return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

        if identity(before) != identity(after) or identity(after) != identity(current):
            raise ValueError("File changed while hashing")
    return value.hexdigest()


def _regular_file(path):
    # A supplied manifest may name a FIFO/device. Read-only inspection must not
    # block waiting for a writer or read an unbounded device stream.
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    stream = os.fdopen(descriptor, "rb")
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        stream.close()
        raise ValueError("Expected a regular file")
    return stream


def fingerprint(inputs):
    """Stable identity for recorded inputs; paths and the output hash are separate."""
    encoded = json.dumps(inputs, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def native_host(rustc, verbose):
    """Require a consistent compiler description for the native-only producer."""
    lines = verbose.strip().splitlines()
    hosts = [line.removeprefix("host: ") for line in lines if line.startswith("host: ")]
    if not lines or lines[0] != rustc or len(hosts) != 1 or not hosts[0].strip():
        raise ValueError("Inconsistent rustc version or host metadata")
    return hosts[0]


def metadata(manifest, *, variant, lock_sha256, target, features, rustc_verbose):
    """Additive evidence; callers retain all existing flat manifest fields."""
    inputs = {
        "variant": variant,
        "upstream_revision": manifest["revision"],
        "patches": [
            {"file": name, "sha256": manifest[PATCH_FIELDS[name]]} for name in STACKS[variant]
        ],
        "cargo_lock_sha256": lock_sha256,
        "profile": manifest["build_profile"],
        "cargo_flags": list(manifest["build_flags"]),
        "default_features": "--no-default-features" not in manifest["build_flags"],
        "enabled_features": sorted(set(features)),
        "rustc": manifest["rustc"],
        "rustc_verbose": rustc_verbose.strip(),
        "target": target,
    }
    return {"schema": SCHEMA, "build_id": fingerprint(inputs), "inputs": inputs}


def cargo_artifact(output, target_directory, profile, host):
    """Read Cargo's actual binary/features, including its target-directory layout."""
    found = []
    for line in output.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict) or not isinstance(item.get("target"), dict):
            continue
        if (
            item.get("reason") == "compiler-artifact"
            and item.get("target", {}).get("name") == "niri"
            and isinstance(item["target"].get("kind"), list)
            and "bin" in item["target"]["kind"]
            and isinstance(item.get("executable"), str)
            and item["executable"]
        ):
            found.append(item)
    if len(found) != 1:
        raise ValueError("Cargo did not report exactly one niri executable")
    item = found[0]
    binary = Path(item["executable"]).resolve()
    relative = binary.relative_to(Path(target_directory).resolve())
    # A custom target specification needs additional provenance; do not guess
    # a triple from its filename or silently describe a cross-build as native.
    if relative.parts == (profile, "niri"):
        target = host
    elif relative.parts == (host, profile, "niri"):
        target = host
    else:
        raise ValueError("Only the native host target is supported by this build manifest")
    features = item.get("features")
    if not isinstance(features, list) or not all(isinstance(item, str) for item in features):
        raise ValueError("Cargo executable feature metadata is missing")
    return binary, features, target


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _read_manifest(path):
    with _regular_file(path) as stream:
        content = stream.read(1024 * 1024 + 1)
    if len(content) > 1024 * 1024:
        raise ValueError("Manifest exceeds 1 MiB")
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("Manifest must be a JSON object")
    return value


def inspect(manifest_path, *, source, repository, desktop=False, pinned_revision=True):
    """Check bytes and recorded build prerequisites without executing any program."""
    result = {
        "status": "unknown",
        "scope": "Recorded build metadata and file identities only; no executable is run.",
        "limitations": [
            "The build_id fingerprints recorded inputs, not authenticity or reproducibility.",
            "Ambient Cargo configuration, wrappers, flags and system libraries are not fully recorded.",
            "Inspection checks the supplied lockfile, not the complete source tree or runtime ABI.",
        ],
        "reasons": [],
        "checks": {},
        "desktop_prerequisites": "unknown" if desktop else "not_requested",
        "runtime_acceptance": "not_assessed",
        "physical_desktop_acceptance": "not_assessed",
    }

    def fail(status, reason):
        result["status"] = status
        result["reasons"].append(reason)
        return result

    try:
        manifest = _read_manifest(manifest_path)
    except (OSError, ValueError, UnicodeError) as error:
        return fail("incompatible", f"Cannot read build manifest: {error}")
    block = manifest.get("native_build")
    if block is None:
        return fail("unknown", "Legacy manifest has no versioned build-input evidence.")
    if not isinstance(block, dict) or type(block.get("schema")) is not int:
        return fail("incompatible", "Malformed native_build schema.")
    if block["schema"] != SCHEMA:
        return fail("unknown", f"Unsupported native_build schema: {block['schema']}.")
    inputs = block.get("inputs")
    required = {
        "variant",
        "upstream_revision",
        "patches",
        "cargo_lock_sha256",
        "profile",
        "cargo_flags",
        "default_features",
        "enabled_features",
        "rustc",
        "rustc_verbose",
        "target",
    }
    if not isinstance(inputs, dict) or set(inputs) != required:
        return fail("incompatible", "Incomplete or unrecognized build-input fields.")
    if not _sha(block.get("build_id")) or fingerprint(inputs) != block["build_id"]:
        return fail("incompatible", "Recorded build_id does not match its inputs.")
    result["build_id"] = block["build_id"]
    variant = inputs["variant"]
    if not isinstance(variant, str) or variant not in STACKS:
        return fail("incompatible", "Unknown patch-stack variant.")
    result["variant"] = variant
    patches = inputs["patches"]
    if (
        not isinstance(patches, list)
        or any(not isinstance(item, dict) or set(item) != {"file", "sha256"} for item in patches)
        or [item["file"] for item in patches] != list(STACKS[variant])
        or any(not _sha(item["sha256"]) for item in patches)
    ):
        return fail("incompatible", "Patch sequence does not match the recorded variant.")
    flags = inputs["cargo_flags"]
    features = inputs["enabled_features"]
    if (
        flags not in (["--locked"], ["--locked", "--no-default-features"])
        or type(inputs["default_features"]) is not bool
        or inputs["default_features"] != ("--no-default-features" not in flags)
        or not isinstance(features, list)
        or any(not isinstance(item, str) or not item for item in features)
        or features != sorted(set(features))
        or inputs["default_features"] != ("default" in features)
        or inputs["profile"] not in ("release", "debug")
        or any(
            not isinstance(inputs[key], str) or not inputs[key].strip()
            for key in ("rustc", "rustc_verbose", "target")
        )
        or not _sha(inputs["cargo_lock_sha256"])
    ):
        return fail("incompatible", "Invalid or contradictory build mode, features or toolchain.")
    revision = inputs["upstream_revision"]
    if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        return fail("incompatible", "Invalid upstream revision identity.")
    # Retained bundles carry their own frozen patch/lock evidence. A new source
    # checkout pin must not silently disable rollback to an older installed pair.
    if pinned_revision and revision != REVISION:
        return fail(
            "incompatible", "Manifest uses a different upstream revision from this checkout."
        )
    try:
        if native_host(inputs["rustc"], inputs["rustc_verbose"]) != inputs["target"]:
            return fail("incompatible", "Recorded target is not the compiler's native host.")
    except ValueError as error:
        return fail("incompatible", str(error))
    mirrored = {
        "revision": inputs["upstream_revision"],
        "build_profile": inputs["profile"],
        "build_flags": flags,
        "rustc": inputs["rustc"],
        **{PATCH_FIELDS[item["file"]]: item["sha256"] for item in patches},
    }
    if any(manifest.get(key) != value for key, value in mirrored.items()):
        return fail("incompatible", "Legacy fields disagree with versioned build inputs.")
    if (manifest.get("unmodified") is True) != (variant == "unmodified") or any(
        field in manifest and name not in STACKS[variant] for name, field in PATCH_FIELDS.items()
    ):
        return fail("incompatible", "Legacy patch selection disagrees with the build variant.")
    if (
        not isinstance(manifest.get("binary"), str)
        or not manifest["binary"].strip()
        or not _sha(manifest.get("binary_sha256"))
    ):
        return fail("incompatible", "Missing binary path or SHA-256.")
    binary = Path(manifest["binary"])
    if not binary.is_absolute():
        binary = Path(manifest_path).resolve().parent / binary
    checks = [("binary", binary, manifest["binary_sha256"])]
    checks.extend(
        (item["file"], Path(repository) / "experimental" / item["file"], item["sha256"])
        for item in patches
    )
    checks.append(("cargo_lock", Path(source) / "Cargo.lock", inputs["cargo_lock_sha256"]))
    for name, path, expected in checks:
        try:
            match = digest(path) == expected
        except (OSError, ValueError) as error:
            result["checks"][name] = "unavailable"
            result["reasons"].append(f"Cannot read {name}: {error}")
        else:
            result["checks"][name] = "match" if match else "mismatch"
            if not match:
                result["reasons"].append(f"{name} differs from the recorded SHA-256.")
    if result["reasons"]:
        result["status"] = "stale"
        return result
    if desktop:
        missing = sorted(DESKTOP_FEATURES - set(features))
        result["missing_desktop_features"] = missing
        if inputs["profile"] != "release" or not inputs["default_features"] or missing:
            result["desktop_prerequisites"] = "not_satisfied"
            return fail(
                "incompatible", "Desktop build requires release mode and full default features."
            )
        result["desktop_prerequisites"] = "satisfied"
    result["status"] = "metadata-match"
    result["reasons"].append(
        "Recorded inputs and file hashes match; runtime support is unassessed."
    )
    return result
