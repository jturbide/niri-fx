#!/usr/bin/env python3
"""Record retained material retargets against the verified released baseline."""

import argparse
import hashlib
import importlib.util
import json
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from lib.movement import experiment
from lib.nested import encode_gif, record, save_clips, source_hashes, stop


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


material = load("resize_material", "test-resize-material.py")
comparison = load("resize_comparison", "record-resize-comparison.py")
DURATION = 1500
FPS = 50
GIF_WIDTH = 900
GIF_COLORS = 48
STYLES = {"balanced": "Fragments", "triangle-shatter": "Triangle"}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(binary, version, preset, destination):
    effect = replace(material.PRESETS[preset], resize=True, resize_ms=DURATION, resize_strength=0.9)
    shader = material.resize_shader(effect)
    name = f"{version}-{preset}"
    with material.NestedSession(
        material.config(None, duration=1), binary=binary, width=1280, height=800
    ) as session:
        primary = material.cards(session)
        initial = session.capture("intact")
        initial_background = material.background_pixels(initial)
        session.reload(material.config(shader, duration=DURATION))
        recorder, source = record(session, name, fps=FPS)
        origin = time.monotonic()
        actions = []
        for at, axis, extent in (
            (0.6, "width", 700),
            (1.05, "height", 460),
            (1.35, "width", 520),
        ):
            time.sleep(max(0, origin + at - time.monotonic()))
            requested = time.monotonic()
            material.resize(session, primary, axis, extent)
            committed = time.monotonic()
            assert requested - origin - at < 0.10, "Missed scheduled retarget"
            assert committed - requested < 0.20, "Client commit missed retarget interval"
            actions.append(
                {
                    "axis": axis,
                    "extent": extent,
                    "request_s": round(requested - origin, 4),
                    "committed_s": round(committed - origin, 4),
                }
            )
        # Both sides receive the same requests. The released path restarts its
        # material at each commit; the updated path keeps the original episode.
        time.sleep(max(0, origin + 1.5 - time.monotonic()))
        during = session.capture("after-two-retargets")
        counts = material.hardening.colors(during)
        background = material.background_pixels(during)
        assert counts["public"] > 10000 and counts["protected"] > 5000, counts
        assert background > initial_background + 500, "No visible material deformation"
        time.sleep(max(0, origin + 3.5 - time.monotonic()))
        stop(recorder, signal.SIGINT)
        settled = session.capture("settled")
        final_size = material.window(session, primary)["layout"]["window_size"]
        assert final_size == [520.0, 460.0], final_size
        assert material.background_pixels(settled) <= initial_background + 20
        session.check_render_log()
        video = destination / f"{name}.mkv"
        shutil.copyfile(source, video)
        for suffix, path in (("intact", initial), ("retargeted", during), ("settled", settled)):
            shutil.copyfile(path, destination / f"{name}-{suffix}.png")
        return {
            "case": name,
            "preset": preset,
            "binary_sha256": digest(binary),
            "shader_sha256": hashlib.sha256(shader.encode()).hexdigest(),
            "config_sha256": hashlib.sha256(
                material.config(shader, duration=DURATION).encode()
            ).hexdigest(),
            "video_sha256": digest(video),
            "dimensions": [1280, 800],
            "fps": FPS,
            "actions": actions,
            "final_size": final_size,
            "interior_background_pixels": {
                "intact": initial_background,
                "after_two_retargets": background,
                "settled": material.background_pixels(settled),
            },
        }


def compose(destination, preset):
    family = "fragments" if preset == "balanced" else "triangles"
    stem = destination / f"native-resize-material-{family}-comparison"
    filters = []
    for index, label in enumerate(("Baseline 0.19", "Updated")):
        filters.append(
            f"[{index}:v]fps={FPS},crop=780:640:0:0,scale=600:-2:flags=lanczos,"
            "pad=iw:ih+48:0:48:color=0x111827,"
            f"drawtext=text='{label} | {STYLES[preset]}':"
            f"fontcolor=white:fontsize=30:x=20:y=9[{index}v]"
        )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(destination / f"before-{preset}.mkv"),
            "-i",
            str(destination / f"after-{preset}.mkv"),
            "-filter_complex",
            ";".join(filters) + ";[0v][1v]hstack=shortest=1[v]",
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-crf",
            "16",
            str(stem.with_suffix(".mkv")),
        ],
        check=True,
        timeout=120,
    )
    encode_gif(
        stem.with_suffix(".mkv"),
        stem.with_suffix(".gif"),
        width=GIF_WIDTH,
        fps=FPS,
        colors=GIF_COLORS,
    )
    return stem.with_suffix(".gif")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "artifacts/resize-material-comparison"
    )
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    updated, build, _ = experiment()
    before, baseline = comparison.baseline(args.baseline_manifest, "v0.19.0", build)
    sources = source_hashes(
        "scripts/record-resize-material.py",
        "scripts/test-resize-material.py",
        "scripts/record-resize-comparison.py",
        "scripts/test-pointer-hardening.py",
        "scripts/lib/nested.py",
        "scripts/lib/movement.py",
        "scripts/lib/pointer_scene.py",
        "scripts/fixtures/pointer-card.qml",
        "niri_fx/effects.py",
        "niri_fx/presets.py",
        "niri_fx/shaders/resize-state.glsl",
        "niri_fx/shaders/resize.glsl",
        "niri_fx/shaders/resize-shaped.glsl",
    )
    evidence = {
        "schema": 1,
        "revision": build["revision"],
        "patch_sha256": build["patch_sha256"],
        "binary_sha256": build["binary_sha256"],
        "baseline": baseline,
        "sources": sources,
        "scope": "Owned nested Niri synthetic cards; identical generated shaders and timed IPC retargets, actual configured speed. No closing-continuation assertion.",
        "duration_ms": DURATION,
        "strength": 0.9,
        "clips": [],
        "comparisons": [],
    }
    for version, binary in (("before", before), ("after", updated)):
        for preset in STYLES:
            evidence["clips"].append(capture(binary, version, preset, destination))
            print(f"PASS {version} {preset} retained-material capture", flush=True)
    clips = []
    for preset in STYLES:
        pair = [clip for clip in evidence["clips"] if clip["preset"] == preset]
        assert pair[0]["shader_sha256"] == pair[1]["shader_sha256"]
        gif = compose(destination, preset)
        path = f"docs/gifs/{gif.name}"
        evidence["comparisons"].append({"file": path, "gif_sha256": digest(gif)})
        clips.append(
            {
                "name": gif.stem,
                "file": path,
                "title": f"Retained {STYLES[preset].lower()} resize after two retargets",
                "mode": "resize",
                "bytes": gif.stat().st_size,
                "fps": FPS,
                "width": GIF_WIDTH,
                "colors": GIF_COLORS,
                "duration_ms": DURATION,
                "backend": "pinned patched Niri nested winit; synthetic clients; sequential native captures shown side by side",
                "revision": build["revision"],
                "patch_sha256": build["patch_sha256"],
                "baseline": baseline,
                "sources": sources,
                "checks": [
                    "verified tagged baseline and current build identities",
                    "identical generated shader and configured duration",
                    "two bounded IPC retargets at actual speed",
                    "visible breakup and intact settled content",
                ],
            }
        )
    report = json.dumps(evidence, indent=2) + "\n"
    (destination / "checks.json").write_text(report)
    if args.publish:
        for clip in clips:
            shutil.copyfile(destination / Path(clip["file"]).name, ROOT / clip["file"])
        save_clips(clips)
        (ROOT / "docs/benchmarks/resize-material-continuity.json").write_text(report)


if __name__ == "__main__":
    main()
