#!/usr/bin/env python3
"""Build the full NiriFX session candidate without installing or selecting it."""

import argparse
import subprocess
import sys
from pathlib import Path

from lib.native_candidates import (
    PACKAGING_OPTIONS,
    add_packaging_arguments,
    validate_packaging_arguments,
)

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_packaging_arguments(parser)
    args = parser.parse_args()
    validate_packaging_arguments(parser, args)
    # Keep one producer for isolation, source checks and manifest publication.
    # Patch subsets and minimal feature builds belong to developer regression
    # tools; the session product always carries the full reviewed native stack.
    command = [
        sys.executable,
        str(ROOT / "scripts/build-niri-movement.py"),
        "--fragment-drag",
        "--desktop",
        "--release",
        "--test",
    ]
    for option in PACKAGING_OPTIONS:
        value = getattr(args, option.replace("-", "_"))
        if value is not None:
            command.extend(["--" + option, str(value)])
    print(
        "Building a full NiriFX session candidate; installation and selection are separate.",
        flush=True,
    )
    try:
        return subprocess.run(command, check=False).returncode
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
