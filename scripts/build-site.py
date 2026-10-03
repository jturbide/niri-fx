#!/usr/bin/env python3
"""Stage the public gallery and offline-capable Studio in a fresh directory."""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from niri_fx.effects import PRESETS
from niri_fx.preview import preview_document


def build(output):
    # Validate all generated files before staging a site. Hosted HTML is built
    # without a connection, so it cannot include local endpoints or save tokens.
    subprocess.run([sys.executable, str(ROOT / "scripts/build-gallery.py"), "--check"], check=True)
    output.mkdir(parents=True, exist_ok=False)
    gallery = output / "gallery"
    gallery.mkdir()
    for name in ("index.html", "gallery.js", "gallery.css"):
        shutil.copy2(ROOT / "docs/gallery" / name, gallery / name)
    for name in ("posters", "presets"):
        shutil.copytree(ROOT / "docs/gallery" / name, gallery / name)
    (output / "gifs").mkdir()
    for source in (ROOT / "docs/gifs").glob("*.gif"):
        shutil.copy2(source, output / "gifs" / source.name)
    (output / "studio").mkdir()
    (output / "studio/index.html").write_text(preview_document(PRESETS["balanced"], hosted=True))
    (output / "index.html").write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="refresh" content="0;url=gallery/"><title>NiriFX</title><a href="gallery/">Open the gallery</a></html>\n'
    )
    (output / ".nojekyll").touch()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="New directory; existing paths are not overwritten",
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a fresh output directory")
    build(args.output)
    print(f"Built gallery and Studio: {args.output}")


if __name__ == "__main__":
    main()
