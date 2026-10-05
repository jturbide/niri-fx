#!/usr/bin/env python3
"""Inspect native build evidence without executing or installing a compositor."""

import argparse
import json
from pathlib import Path

from lib.native_build import inspect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--source", type=Path, required=True, help="Source tree containing Cargo.lock"
    )
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="Require release/default-feature build metadata; does not verify desktop acceptance",
    )
    args = parser.parse_args()
    result = inspect(
        args.manifest,
        source=args.source,
        repository=Path(__file__).resolve().parents[1],
        desktop=args.desktop,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "metadata-match" else 2


if __name__ == "__main__":
    raise SystemExit(main())
