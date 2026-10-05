#!/usr/bin/env python3
"""Check an explicit native matrix in fresh attempts, without installation or selection."""

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from lib.native_build import DESKTOP_FEATURES, REVISION, STACKS, digest, fingerprint, inspect
from lib.native_candidates import Candidate

spec = importlib.util.spec_from_file_location(
    "compatibility_builder", ROOT / "scripts/build-niri-movement.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
MATRIX = ROOT / "experimental/native-compatibility.json"
UPSTREAM = "https://github.com/niri-wm/niri.git"


def load_matrix(path=MATRIX):
    value = json.loads(path.read_text())
    fields = {
        "schema",
        "upstream_revision",
        "cargo_lock_sha256",
        "rust_toolchain",
        "target",
        "runner",
        "default_case",
        "patch_variants",
        "cases",
    }
    if (
        not isinstance(value, dict)
        or set(value) != fields
        or type(value["schema"]) is not int
        or value["schema"] != 1
    ):
        raise ValueError("Unsupported native compatibility matrix")
    if value["upstream_revision"] != REVISION:
        raise ValueError("Matrix revision differs from the supported native build contract")
    if not isinstance(value["cargo_lock_sha256"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", value["cargo_lock_sha256"]
    ):
        raise ValueError("Matrix needs an exact Cargo.lock SHA-256")
    if not isinstance(value["rust_toolchain"], str) or not re.fullmatch(
        r"[0-9]+\.[0-9]+\.[0-9]+", value["rust_toolchain"]
    ):
        raise ValueError("Matrix Rust toolchain must be an exact stable release")
    if value["target"] != "x86_64-unknown-linux-gnu" or value["runner"] != "ubuntu-24.04":
        raise ValueError("This matrix runner currently covers Ubuntu 24.04 x86_64 only")
    if value["patch_variants"] != list(STACKS):
        raise ValueError("Clean patch checks must include each supported ordered stack")
    cases = value["cases"]
    if not isinstance(cases, list) or not 1 <= len(cases) <= 8:
        raise ValueError("Expected between one and eight explicit build cases")
    identifiers = set()
    for case in cases:
        if not isinstance(case, dict) or set(case) != {
            "id",
            "variant",
            "default_features",
            "profile",
        }:
            raise ValueError("Invalid native build case")
        if (
            not isinstance(case["id"], str)
            or not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", case["id"])
            or case["id"] in identifiers
        ):
            raise ValueError("Build case IDs must be unique safe names")
        identifiers.add(case["id"])
        if (
            not isinstance(case["variant"], str)
            or case["variant"] not in STACKS
            or type(case["default_features"]) is not bool
            or case["profile"] != "debug"
        ):
            raise ValueError("Unsupported native case variant, feature policy or CI profile")
    default = next((case for case in cases if case["id"] == value["default_case"]), None)
    if default is None or default["variant"] != "fragment" or not default["default_features"]:
        raise ValueError("Default CI case must compile the full NiriFX desktop feature stack")
    return value


def actions_matrix(matrix, *, expanded=False):
    return {
        "include": [
            case | {key: matrix[key] for key in ("rust_toolchain", "target", "runner")}
            for case in matrix["cases"]
            if expanded or case["id"] == matrix["default_case"]
        ]
    }


def report_base(matrix, variant, gate):
    return {
        "schema": 1,
        "gate": gate,
        "status": "pending",
        "matrix_sha256": fingerprint(matrix),
        "upstream_revision": matrix["upstream_revision"],
        "variant": variant,
        "runtime_acceptance": "not_assessed",
        "physical_desktop_acceptance": "not_assessed",
        "distribution_support": "not_assessed",
    }


def run_patch_check(matrix, variant, *, repository=ROOT, source_cache=None, parent=None):
    """Fetch only the exact commit; a cache's working tree is never copied or changed."""
    candidate = Candidate(parent or repository / "artifacts/native-compatibility/attempts", variant)
    report = report_base(matrix, variant, "clean-patch-application")
    patches = [repository / "experimental" / name for name in STACKS[variant]]
    try:
        frozen, hashes = candidate.snapshot(patches)
        candidate.record("checkout")
        candidate.command("git", "init", str(candidate.source))
        origin = str(source_cache.resolve()) if source_cache is not None else UPSTREAM
        candidate.command("git", "remote", "add", "origin", origin)
        candidate.command(
            "git", "fetch", "--no-tags", "--depth=1", "origin", matrix["upstream_revision"]
        )
        candidate.command("git", "checkout", "--detach", "FETCH_HEAD")
        candidate.record("patch-check")
        builder.apply_patches(candidate.source, matrix["upstream_revision"], frozen)
        builder.apply_patches(
            candidate.source, matrix["upstream_revision"], frozen, verify_only=True
        )
        lock_hash = digest(candidate.source / "Cargo.lock")
        if lock_hash != matrix["cargo_lock_sha256"]:
            raise ValueError("Pinned Cargo.lock differs from the compatibility matrix")
        if any(digest(path) != hashes[path.name] for path in (*patches, *frozen)):
            raise ValueError("Patch inputs changed during the compatibility check")
        report.update(status="passed", patches=hashes, cargo_lock_sha256=lock_hash)
        candidate.record("patch-check", status="checked")
    except (Exception, SystemExit, KeyboardInterrupt) as error:
        status = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
        candidate.record(candidate.state["stage"], status=status, error=error)
        report.update(
            status=status, error_type=type(error).__name__, stage=candidate.state["stage"]
        )
    return report


def verify_case_manifest(path, matrix, case, *, repository=ROOT):
    manifest = json.loads(path.read_text())
    source = path.parent / manifest["source"]
    evidence = inspect(path, source=source, repository=repository)
    if evidence["status"] != "metadata-match":
        raise ValueError("Candidate build evidence does not match current inputs")
    inputs = manifest["native_build"]["inputs"]
    expected_features = sorted({"default", *DESKTOP_FEATURES}) if case["default_features"] else []
    expected = {
        "variant": case["variant"],
        "profile": case["profile"],
        "default_features": case["default_features"],
        "enabled_features": expected_features,
        "target": matrix["target"],
        "cargo_lock_sha256": matrix["cargo_lock_sha256"],
    }
    if any(inputs[key] != value for key, value in expected.items()) or not inputs[
        "rustc"
    ].startswith(f"rustc {matrix['rust_toolchain']} "):
        raise ValueError("Compiled candidate does not match the selected matrix case")
    # Reports can be CI artifacts or public evidence. Retain identities without
    # local executable/source paths, logs, configurations or environment values.
    return {
        "build_id": manifest["native_build"]["build_id"],
        "binary_sha256": manifest["binary_sha256"],
        "inputs": inputs,
    }


def run_build(matrix, case, *, repository=ROOT, parent=None):
    candidate = Candidate(parent or repository / "artifacts/native-builds", case["variant"])
    report = report_base(matrix, case["variant"], "compile-and-regression") | {"case": case["id"]}
    args = SimpleNamespace(
        release=False,
        desktop=case["default_features"],
        test=True,
        unmodified=case["variant"] == "unmodified",
        pointer_wobble=case["variant"] == "pointer",
        fragment_drag=case["variant"] == "fragment",
    )
    patches = [repository / "experimental" / name for name in STACKS[case["variant"]]]
    try:
        # A precise rustup selection applies only to this command. The existing
        # builder resolves that compiler, records its actual host/features and
        # isolates source, target and intermediate output for the attempt.
        previous = os.environ.get("RUSTUP_TOOLCHAIN")
        os.environ["RUSTUP_TOOLCHAIN"] = matrix["rust_toolchain"]
        try:
            manifest = builder.build_candidate(args, case["variant"], patches, candidate)
        finally:
            if previous is None:
                os.environ.pop("RUSTUP_TOOLCHAIN", None)
            else:
                os.environ["RUSTUP_TOOLCHAIN"] = previous
        report["build"] = verify_case_manifest(manifest, matrix, case, repository=repository)
        report["status"] = "passed"
    except (Exception, SystemExit, KeyboardInterrupt) as error:
        status = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
        candidate.record(candidate.state["stage"], status=status, error=error)
        report.update(
            status=status, error_type=type(error).__name__, stage=candidate.state["stage"]
        )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("matrix", "patches", "build"))
    parser.add_argument(
        "--expanded",
        action="store_true",
        help="Print internal compile controls as well (matrix only)",
    )
    parser.add_argument("--case", help="Exact case ID for a compile/regression run")
    parser.add_argument(
        "--source-cache", type=Path, help="Read an existing Git repository for patch checks only"
    )
    parser.add_argument(
        "--report", type=Path, help="Write a new JSON report; existing files are refused"
    )
    args = parser.parse_args()
    matrix = load_matrix()
    if args.expanded and args.mode != "matrix":
        parser.error("--expanded is only used to print the CI matrix")
    if args.source_cache is not None and args.mode != "patches":
        parser.error("--source-cache is only used by clean patch checks")
    if args.report is not None and args.report.exists():
        parser.error("Report already exists; choose a new output path")
    if args.mode == "matrix":
        if args.case or args.report:
            parser.error("matrix only prints the validated CI matrix")
        print(json.dumps(actions_matrix(matrix, expanded=args.expanded), separators=(",", ":")))
        return 0
    if args.mode == "build":
        case = next((case for case in matrix["cases"] if case["id"] == args.case), None)
        if case is None:
            parser.error("--case must select an exact matrix case")
        report = run_build(matrix, case)
    else:
        if args.case:
            parser.error("--case applies only to compile/regression runs")
        reports = []
        for variant in matrix["patch_variants"]:
            reports.append(run_patch_check(matrix, variant, source_cache=args.source_cache))
            if reports[-1]["status"] == "interrupted":
                break
        report = {
            "schema": 1,
            "status": "passed" if all(item["status"] == "passed" for item in reports) else "failed",
            "checks": reports,
        }
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x") as output:
            output.write(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
