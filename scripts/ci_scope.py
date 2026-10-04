#!/usr/bin/env python3
"""Keep full rendering checks unless every changed path is known to be unrelated."""

import argparse
import os
import re
import subprocess
from pathlib import Path, PurePosixPath

# These files are not runtime inputs to the skipped GLSL/browser suites. Native
# pointer math still shares a browser contract: always-on Node tests check the
# patch's Rust/GLSL against the recorded traces and browser adapter. Regenerating
# those traces or changing the adapter requires full rendering checks below.
# Keep exact paths: new tools need review before skipping rendering. Native
# changes also need CONTRIBUTING's compositor checks; WebGL cannot certify them.
NON_RENDERING_FILES = {
    "niri_fx/agent.py",
    "niri_fx/agent_data/nirifx/SKILL.md",
    "tests/test_agent.py",
    "experimental/niri-movement.patch",
    "experimental/niri-pointer-wobble.patch",
    "experimental/README.md",
    "experimental/COPYING-NIRI",
    "scripts/build-niri-movement.py",
    "scripts/nested-demo.py",
    "scripts/measure-native-movement.py",
    "scripts/record-desktop-motion.py",
    "scripts/record-movement-scenarios.py",
    "scripts/record-native-gif.py",
    "scripts/test-interruptions.py",
    "scripts/test-movement.py",
    "scripts/test-native-baseline.py",
    "scripts/test-pointer-hardening.py",
    "scripts/test-pointer-integration.py",
    "scripts/test-pointer-wobble.py",
    "scripts/test-stock-scenarios.py",
    "scripts/lib/movement.py",
    "scripts/lib/nested.py",
    "scripts/lib/pointer.py",
    "scripts/lib/pointer_scene.py",
    "scripts/lib/pointer_wobble.py",
    "scripts/fixtures/movement.qml",
    "scripts/fixtures/pointer-card.qml",
    "scripts/fixtures/pointer.c",
    "scripts/fixtures/window.qml",
    "tests/test_experimental_build.py",
    "tests/test_movement_demo.py",
    "tests/test_native_baseline.py",
    "tests/test_native_timing.py",
    "tests/test_nested.py",
    "tests/test_pointer_hardening.py",
    "tests/test_pointer_wobble.py",
    "docs/benchmarks/native-baseline.json",
    "docs/benchmarks/native-continuity.json",
    "docs/benchmarks/native-output-feedback.json",
    "docs/benchmarks/pointer-hardening.json",
    "docs/benchmarks/pointer-wobble.json",
}


def documentation_only(paths):
    """Unknown files, examples and executable gallery assets require the full suite."""
    if not paths:
        return False
    root_docs = {
        "README.md",
        "ROADMAP.md",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "THIRD_PARTY.md",
        ".github/pull_request_template.md",
    }
    for name in paths:
        path = PurePosixPath(name)
        if name in root_docs or name.startswith(".github/ISSUE_TEMPLATE/"):
            continue
        if name.startswith("docs/") and path.suffix in {
            ".md",
            ".gif",
            ".png",
            ".svg",
            ".webp",
            ".mp4",
            ".webm",
        }:
            continue
        if name in {
            "docs/gifs/manifest.json",
            "docs/gifs/native-manifest.json",
            "docs/gifs/scenario-manifest.json",
            "docs/gallery/posters.json",
        }:
            continue
        return False
    return True


def required_checks(paths):
    """Return (application, renderer); unknown or mixed changes require both."""
    if documentation_only(paths):
        return False, False
    if paths and all(path in NON_RENDERING_FILES or documentation_only([path]) for path in paths):
        return True, False
    return True, True


def release_ref(ref):
    """PR head refs are plain branch names; push refs are fully qualified."""
    branch = ref.removeprefix("refs/heads/")
    return ref.startswith("refs/tags/") or branch == "release" or branch.startswith("release/")


def changed_paths(base, head):
    # --no-renames exposes both the removed and added path. A renamed source
    # file must not disappear behind a documentation-looking destination.
    if not all(re.fullmatch(r"[0-9a-f]{40,64}", revision or "") for revision in (base, head)):
        raise ValueError("Missing or invalid comparison revision")
    result = subprocess.run(
        ["git", "diff", "--name-only", "--no-renames", "-z", base, head],
        check=True,
        capture_output=True,
        timeout=20,
    )
    return [os.fsdecode(path) for path in result.stdout.split(b"\0") if path]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="")
    parser.add_argument("--event", required=True)
    parser.add_argument("--ref", default="", help="PR head branch or full push ref")
    args = parser.parse_args()
    full, renderer = True, True
    reason = "Manual or unrecognized event: run the complete suite."
    if release_ref(args.ref):
        reason = "Release branch or tag: run the complete suite."
    elif args.event in {"pull_request", "push"}:
        try:
            paths = changed_paths(args.base, args.head)
            full, renderer = required_checks(paths)
            if renderer:
                reason = (
                    "Renderer, editor, shared contracts or unknown paths changed: "
                    "run the complete suite."
                )
            elif full:
                reason = (
                    "Only known native/agent paths and documentation changed: keep unit, "
                    "package, lint and docs checks; skip portable rendering and Studio E2E."
                )
            else:
                reason = (
                    "Only documentation/media changed: keep lint, Node and documentation checks."
                )
        except (ValueError, OSError, subprocess.SubprocessError):
            # Missing history is never evidence that testing is unnecessary.
            full, renderer = True, True
            reason = "Comparison unavailable: run the complete suite."
    print(reason)
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a") as stream:
            stream.write(f"full={'true' if full else 'false'}\n")
            stream.write(f"renderer={'true' if renderer else 'false'}\n")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a") as stream:
            stream.write(f"## Check selection\n\n{reason}\n")


if __name__ == "__main__":
    main()
