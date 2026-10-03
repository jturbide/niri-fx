#!/usr/bin/env python3
"""Compile GLSL ES 1.00 and parse generated KDL when native tools are present."""

import argparse
import shutil
import subprocess
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from niri_fx.catalog import STYLES
from niri_fx.effects import (
    FAMILIES,
    PRESETS,
    RESIZE_MODES,
    movement_shader,
    render_kdl,
    resize_shader,
    shader,
)
from niri_fx.pack import plan_pack
from niri_fx.setup import apply_plan

HEADER = """#version 100
precision highp float;
uniform sampler2D niri_tex;
uniform mat3 niri_geo_to_tex;
uniform float niri_clamped_progress;
uniform float niri_random_seed;
uniform vec2 niri_move_delta; uniform vec2 niri_move_impulse;
uniform sampler2D niri_tex_prev;
uniform sampler2D niri_tex_next;
uniform mat3 niri_geo_to_tex_prev;
uniform mat3 niri_geo_to_tex_next;
uniform mat3 niri_curr_geo_to_next_geo;
uniform mat3 niri_curr_geo_to_prev_geo;
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--require-glsl", action="store_true")
    parser.add_argument("--require-niri", action="store_true")
    args = parser.parse_args()
    validator, niri = shutil.which("glslangValidator"), shutil.which("niri")
    for binary, required, name in (
        (validator, args.require_glsl, "glslangValidator"),
        (niri, args.require_niri, "niri"),
    ):
        if not binary:
            if required:
                raise SystemExit(f"Required tool missing: {name}")
            print(f"SKIP {name}: not installed")

    def resize_variants(effect):
        if effect.family == "distortion":
            return [
                replace(effect, distortion_resize_mode=mode)
                for mode in ("ripple", "edge-ripple", "torsion")
            ]
        return [replace(effect, resize_mode=mode) for mode in RESIZE_MODES]

    with tempfile.TemporaryDirectory(prefix="niri-fx-validate-") as directory:
        root = Path(directory)
        for name, effect in PRESETS.items():
            if validator:
                sources = [
                    ("open_color", shader(effect, True)),
                    ("close_color", shader(effect, False)),
                ]
                if FAMILIES[effect.family]["movement"]:
                    sources.append(("move_color", movement_shader(effect)))
                if FAMILIES[effect.family]["resize"]:
                    sources.extend(
                        ("resize_color", resize_shader(variant))
                        for variant in resize_variants(effect)
                    )
                for index, (entry, source) in enumerate(sources):
                    frag = root / f"{name}-{entry}-{index}.frag"
                    frag.write_text(
                        HEADER
                        + source
                        + f"\nvoid main() {{ gl_FragColor = {entry}(vec3(0.5, 0.5, 1.0), vec3(800.0, 600.0, 1.0)); }}\n"
                    )
                    subprocess.run([validator, "-S", "frag", str(frag)], check=True)
            if niri:
                config = root / f"{name}.kdl"
                variants = [effect]
                if FAMILIES[effect.family]["resize"]:
                    variants.extend(
                        replace(variant, resize=True) for variant in resize_variants(effect)
                    )
                for variant in variants:
                    config.write_text(render_kdl(variant))
                    subprocess.run(
                        [niri, "validate", "-c", str(config)], check=True, capture_output=True
                    )
            print(f"OK {name}")
        if niri:
            # Mirror the existing Noctalia picker's two-level include contract.
            pack = root / "nirifx-presets"
            apply_plan(plan_pack(pack), root / "state")
            selector = root / "animations.kdl"
            config = root / "main.kdl"
            config.write_text('include "animations.kdl"\n')
            for name in STYLES:
                selector.write_text(
                    f'include "./nirifx-presets/nirifx-{name}.kdl"\nanimations {{ slowdown 1.0; }}\n'
                )
                subprocess.run(
                    [niri, "validate", "-c", str(config)], check=True, capture_output=True
                )
            print(f"OK {len(STYLES)} exported styles and profiles through picker-style includes")
    print("Validation does not prove compositor GPU performance or visual acceptance.")


if __name__ == "__main__":
    main()
