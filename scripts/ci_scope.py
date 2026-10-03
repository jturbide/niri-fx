#!/usr/bin/env python3
"""Select checks conservatively: only known documentation/media paths are cheap."""

import argparse
import os
import re
import subprocess
from pathlib import Path, PurePosixPath


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
    args = parser.parse_args()
    full, reason = True, "Manual or unrecognized event: run the complete suite."
    if args.event in {"pull_request", "push"}:
        try:
            paths = changed_paths(args.base, args.head)
            full = not documentation_only(paths)
            reason = (
                "Source, examples, configuration or unknown paths changed: run the complete suite."
                if full
                else "Only documentation/media changed: run lint and documentation checks."
            )
        except (ValueError, OSError, subprocess.SubprocessError):
            # Missing history is never evidence that testing is unnecessary.
            reason = "Comparison unavailable: run the complete suite."
    print(reason)
    if output := os.environ.get("GITHUB_OUTPUT"):
        with Path(output).open("a") as stream:
            stream.write(f"full={'true' if full else 'false'}\n")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a") as stream:
            stream.write(f"## Check selection\n\n{reason}\n")


if __name__ == "__main__":
    main()
