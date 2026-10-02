#!/usr/bin/env python3
"""Compile GLSL ES 1.00 and parse generated KDL when native tools are present."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from niri_fragments.effects import PRESETS, render_kdl, shader

HEADER = """#version 100
precision highp float;
uniform sampler2D niri_tex;
uniform mat3 niri_geo_to_tex;
uniform float niri_clamped_progress;
uniform float niri_random_seed;
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-glsl", action="store_true")
    parser.add_argument("--require-niri", action="store_true")
    args = parser.parse_args()
    validator, niri = shutil.which("glslangValidator"), shutil.which("niri")
    for binary, required, name in ((validator, args.require_glsl, "glslangValidator"), (niri, args.require_niri, "niri")):
        if not binary:
            if required:
                raise SystemExit(f"Required tool missing: {name}")
            print(f"SKIP {name}: not installed")
    with tempfile.TemporaryDirectory(prefix="niri-fragments-validate-") as directory:
        root = Path(directory)
        for name, effect in PRESETS.items():
            if validator:
                for opening in (True, False):
                    entry = "open_color" if opening else "close_color"
                    frag = root / f"{name}-{entry}.frag"
                    frag.write_text(HEADER + shader(effect, opening) + f"\nvoid main() {{ gl_FragColor = {entry}(vec3(0.5, 0.5, 1.0), vec3(800.0, 600.0, 1.0)); }}\n")
                    subprocess.run([validator, "-S", "frag", str(frag)], check=True)
            if niri:
                config = root / f"{name}.kdl"
                config.write_text(render_kdl(effect))
                subprocess.run([niri, "validate", "-c", str(config)], check=True)
            print(f"OK {name}")
    print("Validation does not prove compositor GPU performance or visual acceptance.")


if __name__ == "__main__":
    main()
