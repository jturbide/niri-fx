#!/usr/bin/env python3
"""Record an actual-speed resize-to-close comparison after strict acceptance."""

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
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from lib.movement import experiment
from lib.nested import encode_gif, record, save_clips, source_hashes, stop, wait_for
from lib.pointer_scene import place_floating


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


close = load("resize_close", "test-resize-close.py")
comparison = load("resize_comparison", "record-resize-comparison.py")
FPS = 50
WIDTH = 900
COLORS = 64
RESIZE_MS = 1500
CLOSE_MS = 1200
PRESET = "triangle-shatter"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def client(session, label, color):
    session.launch(
        ["qs", "-p", str(ROOT / "scripts/fixtures/resize-close.qml")],
        label,
        env=session.env | {"NIRIFX_LABEL": label, "NIRIFX_COLOR": color},
        private_bus=True,
    )
    return wait_for(
        lambda: next(
            (
                window["id"]
                for window in session.windows()
                if window["title"] == "NiriFX resize close / " + label
            ),
            None,
        ),
        "owned showcase client",
    )


def capture(binary, version, destination):
    effect = replace(close.PRESETS[PRESET], resize=True, resize_ms=RESIZE_MS, resize_strength=0.75)
    shader = close.resize_shader(effect)
    text = close.config(shader, duration=RESIZE_MS, close_ms=CLOSE_MS)
    with close.NestedSession(
        close.config(None, duration=1), binary=binary, width=1280, height=800
    ) as session:
        primary = client(session, "Resize, then close", close.hardening.PROTECTED)
        public = client(session, "Still open", close.hardening.PUBLIC)
        place_floating(session, primary, x=60, y=120, width=400, height=360)
        place_floating(session, public, x=860, y=120, width=360, height=500)
        session.reload(text)
        recorder, raw = record(session, version, fps=FPS)
        origin = time.monotonic()
        actions = []
        for at, kind, extent in ((0.6, "width", 680), (0.9, "height", 440), (1.3, "close", None)):
            time.sleep(max(0, origin + at - time.monotonic()))
            started = time.monotonic()
            if kind == "close":
                close.closed(session, primary)
            else:
                close.material.resize(session, primary, kind, extent)
            ended = time.monotonic()
            assert started - origin - at < 0.1, "Missed configured action time"
            assert ended - started < 0.2, "Action missed the configured close overlap"
            actions.append(
                {
                    "action": kind,
                    "extent": extent,
                    "request_s": round(started - origin, 4),
                    "complete_s": round(ended - origin, 4),
                }
            )
        time.sleep(max(0, origin + 1.52 - time.monotonic()))
        closing = session.capture("closing")
        counts = close.hardening.colors(closing)
        assert counts["protected"] > 5000 and counts["public"] > 10000, counts
        time.sleep(max(0, origin + 3.1 - time.monotonic()))
        stop(recorder, signal.SIGINT)
        settled = session.capture("settled")
        settled_counts = close.hardening.colors(settled)
        assert settled_counts["protected"] == 0 and settled_counts["public"] > 10000, settled_counts
        assert [window["id"] for window in session.windows()] == [public]
        session.check_render_log()
        video = destination / f"{version}.mkv"
        shutil.copyfile(raw, video)
        shutil.copyfile(closing, destination / f"{version}-closing.png")
        shutil.copyfile(settled, destination / f"{version}-settled.png")
        return {
            "side": version,
            "binary_sha256": digest(binary),
            "shader_sha256": hashlib.sha256(shader.encode()).hexdigest(),
            "config_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "video_sha256": digest(video),
            "actions": actions,
            "fps": FPS,
            "dimensions": [1280, 800],
            "closing_counts": counts,
            "settled_counts": settled_counts,
        }


def compose(destination):
    stem = destination / "native-resize-close-comparison"
    filters = []
    for index, label in enumerate(("Before | Resize to close", "Updated | Resize to close")):
        filters.append(
            f"[{index}:v]fps={FPS},crop=840:680:0:0,scale=600:-2:flags=lanczos,"
            "pad=iw:ih+48:0:48:color=0x111827,"
            f"drawtext=text='{label}':fontcolor=white:fontsize=30:x=18:y=9[{index}v]"
        )
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(destination / "before.mkv"),
            "-i",
            str(destination / "after.mkv"),
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
        stem.with_suffix(".mkv"), stem.with_suffix(".gif"), width=WIDTH, fps=FPS, colors=COLORS
    )
    return stem.with_suffix(".gif")


def require_complete_acceptance(acceptance):
    assert acceptance["status"] == "passed"
    cases = acceptance["cases"]
    assert cases and all(case["status"] == "passed" for case in cases)
    assert acceptance.get("parent_build", {}).get("unmodified") is True
    names = {case["case"] for case in cases}
    assert {
        "material",
        "material-open",
        "material-movement",
        "disable-resize",
        "disable-close",
        "disable-global",
        "same-context-scale-change",
    } <= names
    assert any(
        "output" in observation.get("targets", {})
        for case in cases
        for observation in case["checks"]
    )
    assert sum(case["case"] == "privacy" for case in cases) >= 6
    assert {case["protected"] for case in cases if case["case"] == "same-context-scale-change"} == {
        False,
        True,
    }
    generated = [case for case in cases if case["case"] == "generated"]
    for origin in ([0, 0], [24, 24]):
        assert {"balanced", "slide-apart", "spring-wobble"} <= {
            case["preset"] for case in generated if case["explicit_geometry_origin"] == origin
        }
    assert any(case.get("popup") for case in generated)
    assert any(case.get("native_border_and_shadow") for case in generated)
    assert acceptance["first_frame_oracle"] == close.FIRST_FRAME_ORACLE
    for case in generated:
        control = case["frozen_control"]
        assert (
            control["accepted"]
            and control["stationary_exact"]
            and control["maximum_channel_difference"] == 0
        )
        boundary = case["unmap_boundary"]
        assert boundary["accepted"]
        assert boundary["allowed_silhouette_exceptions"] == close.SILHOUETTE_PIXEL_LIMIT
        assert (
            boundary["changed_pixels_over_one_channel_step"]
            == boundary["exceptional_pixel_count"]
            == len(boundary["exceptional_pixels"])
            <= close.SILHOUETTE_PIXEL_LIMIT
        )
        assert boundary["interior_exception_count"] == 0
        assert all(
            item["silhouette_boundary_in_both_frames"] for item in boundary["exceptional_pixels"]
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--baseline-revision", required=True)
    parser.add_argument("--acceptance-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/resize-close-comparison")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    updated, build, _ = experiment()
    before, baseline = comparison.baseline(
        args.baseline_manifest, None, build, revision=args.baseline_revision
    )
    acceptance = json.loads(args.acceptance_report.read_text())
    require_complete_acceptance(acceptance)
    assert acceptance["build"]["binary_sha256"] == build["binary_sha256"]
    assert acceptance["build"]["patch_sha256"] == build["patch_sha256"]
    for path, expected in acceptance["sources"].items():
        assert digest(ROOT / path) == expected, ("Acceptance source changed", path)
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    sources = source_hashes(
        "scripts/record-resize-close.py",
        "scripts/test-resize-close.py",
        "scripts/test-resize-material.py",
        "scripts/record-resize-comparison.py",
        "scripts/lib/nested.py",
        "scripts/lib/movement.py",
        "scripts/lib/pointer_scene.py",
        "scripts/fixtures/resize-close.qml",
        "niri_fx/effects.py",
        "niri_fx/presets.py",
        "niri_fx/shaders/resize-state.glsl",
        "niri_fx/shaders/resize-shaped.glsl",
    )
    clips = [
        capture(binary, label, destination)
        for label, binary in (("before", before), ("after", updated))
    ]
    assert clips[0]["shader_sha256"] == clips[1]["shader_sha256"]
    assert clips[0]["config_sha256"] == clips[1]["config_sha256"]
    gif = compose(destination)
    relative = f"docs/gifs/{gif.name}"
    evidence = {
        "schema": 1,
        "scope": "Sequential owned nested native captures at configured speed; same generated triangle shader, retargets and close request. Before is the preserved prehandoff build. No playback slowdown.",
        "updated": {key: value for key, value in build.items() if key != "binary"},
        "baseline": baseline,
        "sources": sources,
        "acceptance": acceptance,
        "resize_ms": RESIZE_MS,
        "close_ms": CLOSE_MS,
        "clips": clips,
        "comparison": {"file": relative, "gif_sha256": digest(gif)},
    }
    encoded = json.dumps(evidence, indent=2) + "\n"
    (destination / "checks.json").write_text(encoded)
    if args.publish:
        shutil.copyfile(gif, ROOT / relative)
        save_clips(
            [
                {
                    "name": gif.stem,
                    "file": relative,
                    "title": "Resize continues through close",
                    "mode": "resize",
                    "bytes": gif.stat().st_size,
                    "fps": FPS,
                    "width": WIDTH,
                    "colors": COLORS,
                    "duration_ms": RESIZE_MS,
                    "backend": "pinned patched Niri nested winit; synthetic clients; sequential captures at configured speed",
                    "revision": build["revision"],
                    "patch_sha256": build["patch_sha256"],
                    "baseline": baseline,
                    "sources": sources,
                    "checks": [
                        "verified prehandoff and current native identities",
                        "same shader, timings and bounded action requests",
                        "visible closing content and surviving public control",
                        "strict phase, privacy and first-frame acceptance in benchmark report",
                    ],
                }
            ]
        )
        (ROOT / "docs/benchmarks/resize-close.json").write_text(encoded)
    print(f"PASS resize-to-close comparison; evidence: {destination / 'checks.json'}")


if __name__ == "__main__":
    main()
