"""Record owned native resize comparisons against a verified tagged baseline."""

import argparse
import hashlib
import json
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from lib.movement import experiment
from lib.nested import (
    NestedSession,
    encode_gif,
    record,
    save_clips,
    source_hashes,
    stop,
    wait_for,
)

DEST = ROOT / "artifacts/resize-comparison"
FIXTURE = ROOT / "scripts/fixtures/resize.qml"
BASELINE_LABEL = "Baseline 0.18"
PALETTE = {"Resizing": "#b7e8db", "Neighbor": "#d6c5ef"}
CONFIG = """hotkey-overlay { skip-at-startup; }
prefer-no-csd
layout {
    gaps 16
    default-column-width { fixed 360; }
    center-focused-column "never"
    focus-ring { off; }
    border { off; }
    background-color "#111827"
}
animations {
    window-open { off; }
    window-close { off; }
    window-resize {
        duration-ms 1200
        curve "linear"
        custom-shader r"vec4 resize_color(vec3 coords_curr_geo, vec3 size_curr_geo) {
            return texture2D(niri_tex_next, (niri_geo_to_tex_next * coords_curr_geo).xy);
        }"
    }
    window-movement {
        duration-ms 1200
        curve "linear"
        custom-shader r"vec4 move_color(vec3 coords_geo, vec3 size_geo) {
            return texture2D(niri_tex, (niri_geo_to_tex * coords_geo).xy);
        }"
    }
}
"""


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(binary, version, vertical, *, scenario="reversal"):
    axis = "height" if vertical else "width"
    name = f"{version}-{axis}" if scenario == "reversal" else f"{version}-{scenario}-{axis}"
    with NestedSession(CONFIG, binary=binary, width=1280, height=900) as session:
        for label, color in PALETTE.items():
            session.launch(
                ["qs", "-p", str(FIXTURE)],
                label,
                env=session.env
                | {
                    "NIRIFX_LABEL": label,
                    "NIRIFX_COLOR": color,
                    "NIRIFX_CAPTION": f"{BASELINE_LABEL if version == 'before' else 'Updated'}\n{axis.title()} {scenario}",
                },
                private_bus=True,
            )
            expected_windows = list(PALETTE).index(label) + 1
            wait_for(lambda expected=expected_windows: len(session.windows()) == expected, label)
        windows = session.windows()
        resizing = next(window for window in windows if window["title"].endswith("Resizing"))
        neighbor = next(window for window in windows if window["title"].endswith("Neighbor"))
        session.msg("action", "focus-window", "--id", str(resizing["id"]))
        if vertical:
            session.msg("action", "consume-window-into-column")
            session.msg("action", "set-window-width", "--id", str(resizing["id"]), "650")
            session.msg("action", "set-window-height", "--id", str(neighbor["id"]), "300")
            session.msg("action", "set-window-height", "--id", str(resizing["id"]), "300")
        time.sleep(1.5)
        initial_size = next(w for w in session.windows() if w["id"] == resizing["id"])["layout"][
            "window_size"
        ]
        assert initial_size[1 if vertical else 0] == (300 if vertical else 360), initial_size
        start = session.capture("start")
        recorder, video = record(session, name, fps=50)
        origin = time.monotonic()
        actions = []

        def resize(extent, direction=axis):
            before = time.monotonic()
            session.msg(
                "action", f"set-window-{direction}", "--id", str(resizing["id"]), str(extent)
            )
            after = time.monotonic()
            assert after - before < 0.15, "IPC missed reversal window"
            actions.append(
                {
                    "axis": direction,
                    "extent": extent,
                    "request_s": before - origin,
                    "ack_s": after - origin,
                }
            )

        time.sleep(0.7)
        resize(500 if vertical else 700)
        if scenario == "orthogonal":
            time.sleep(0.3)
            resize(800 if vertical else 600, "width" if vertical else "height")
            time.sleep(0.3)
            resize(300 if vertical else 360)
            time.sleep(0.3)
            resize(initial_size[0 if vertical else 1], "width" if vertical else "height")
        elif scenario == "timing-reload":
            time.sleep(0.3)
            before_reload = time.monotonic()
            session.reload(CONFIG.replace("duration-ms 1200", "duration-ms 350"))
            actions.append(
                {
                    "reload_duration_ms": 350,
                    "request_s": before_reload - origin,
                    "reload_complete_s": time.monotonic() - origin,
                    "includes_settle_ms": 200,
                }
            )
            time.sleep(0.1)
            resize(300 if vertical else 360)
        else:
            time.sleep(0.6)
            resize(300 if vertical else 360)
        time.sleep(1.5)
        stop(recorder, signal.SIGINT)
        end = session.capture("settled")
        settled = session.windows()
        assert {w["id"] for w in settled} == {w["id"] for w in windows}
        dimension = 1 if vertical else 0
        final_size = next(w for w in settled if w["id"] == resizing["id"])["layout"]["window_size"]
        assert final_size[dimension] == (300 if vertical else 360), final_size
        if scenario == "orthogonal":
            assert final_size == initial_size, (initial_size, final_size)
        session.check_render_log()
        output = DEST / f"{name}.mkv"
        shutil.copyfile(video, output)
        shutil.copyfile(start, DEST / f"{name}-start.png")
        shutil.copyfile(end, DEST / f"{name}-settled.png")
        encode_gif(output, DEST / f"{name}.gif", width=900, fps=50, colors=128)
        result = {
            "case": name,
            "binary_sha256": digest(binary),
            "version": session.version,
            "owned_output": "winit",
            "dimensions": [1280, 900],
            "fps": 50,
            "actions": actions,
            "final_size": final_size,
            "same_window_ids": True,
            "video_sha256": digest(output),
            "gif_sha256": digest(DEST / f"{name}.gif"),
        }
        (DEST / f"{name}.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result), flush=True)
        return result


def measure_video(source, vertical):
    """Measure solid synthetic edges before GIF scaling and palette reduction."""
    from PIL import Image, ImageChops

    expected = {name: tuple(bytes.fromhex(color[1:])) for name, color in PALETTE.items()}
    gaps, calibrated = [], None
    max_far_edge = 0
    # Decode with a bounded subprocess, then stream the temporary RGB file.
    # A pipe read could otherwise block before any timeout is reached.
    with tempfile.TemporaryDirectory(
        prefix="nirifx-resize-frames-", dir=source.parent
    ) as temporary:
        decoded = Path(temporary) / "frames.rgb"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(source),
                "-f",
                "rawvideo",
                "-pix_fmt",
                "rgb24",
                str(decoded),
            ],
            check=True,
            capture_output=True,
            timeout=120,
        )
        with decoded.open("rb") as frames:
            while data := frames.read(1280 * 900 * 3):
                if len(data) != 1280 * 900 * 3:
                    raise RuntimeError("Truncated decoded frame")
                frame = Image.frombytes("RGB", (1280, 900), data)
                if calibrated is None:
                    # Limited-range YUV conversion shifts colors. Calibrate from
                    # broad settled populations, then exclude antialiased text.
                    colors = sorted(frame.getcolors(1280 * 900), reverse=True)[:20]
                    calibrated = {
                        name: min(
                            (color for count, color in colors if count > 5000),
                            key=lambda color: sum(
                                (a - b) ** 2 for a, b in zip(color, target, strict=True)
                            ),
                        )
                        for name, target in expected.items()
                    }
                    for name, color in calibrated.items():
                        if max(abs(a - b) for a, b in zip(color, expected[name], strict=True)) > 30:
                            raise RuntimeError(f"Synthetic {name} population missing from capture")
                bounds = {}
                for name, color in calibrated.items():
                    channels = ImageChops.difference(
                        frame, Image.new("RGB", frame.size, color)
                    ).split()
                    delta = ImageChops.lighter(
                        ImageChops.lighter(channels[0], channels[1]), channels[2]
                    )
                    mask = delta.point(lambda value: 255 if value <= 6 else 0)
                    # A scanline must contain >100 solid pixels to count as an
                    # edge. This excludes isolated glyph and cursor pixels.
                    size = (1, 900) if vertical else (1280, 1)
                    minimum = 255 * 100 / (1280 if vertical else 900)
                    line = mask.resize(size, Image.Resampling.BOX).point(
                        lambda value, minimum=minimum: 255 if value > minimum else 0
                    )
                    box = line.getbbox()
                    if box is None:
                        raise RuntimeError(f"Synthetic {name} population missing from capture")
                    bounds[name] = (box[1], box[3]) if vertical else (box[0], box[2])
                gaps.append(bounds["Neighbor"][0] - bounds["Resizing"][1])
                max_far_edge = max(max_far_edge, *(bound[1] for bound in bounds.values()))
    if not gaps:
        raise RuntimeError("No video frames decoded")
    return {
        "decoded_frames": len(gaps),
        "nominal_gap_px": 16,
        "min_gap_px": min(gaps),
        "max_gap_px": max(gaps),
        "codec_edge_tolerance_px": 4,
        "max_far_edge_px": max_far_edge,
    }


def baseline(manifest_path, tag, updated_build, *, revision=None):
    """Keep historical identities explicit instead of assigning current hashes."""
    build = json.loads(manifest_path.read_text())
    if "pointer_patch_sha256" in build or build.get("unmodified"):
        raise ValueError("Baseline must be the movement-only experimental build")
    binary = Path(build["binary"])
    if digest(binary) != build["binary_sha256"]:
        raise ValueError("Baseline executable differs from its build manifest")
    if build["revision"] != updated_build["revision"]:
        raise ValueError("Compare the same pinned compositor revision")
    comparable = ("build_profile", "build_flags", "rustc")
    for field in comparable:
        if field in build and field in updated_build and build[field] != updated_build[field]:
            raise ValueError(f"Baseline and updated build differ in {field}")
    # Resolve the tag first; interpolation into the later revision/path argument
    # uses the resulting object ID, never user-supplied Git revision syntax.
    revision_args = (
        ["--end-of-options", f"{revision}^{{commit}}"]
        if revision is not None
        else [f"refs/tags/{tag}^{{commit}}"]
    )
    commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", *revision_args],
        cwd=ROOT,
        text=True,
        timeout=15,
    ).strip()
    tagged_patch = subprocess.check_output(
        ["git", "show", f"{commit}:experimental/niri-movement.patch"], cwd=ROOT, timeout=15
    )
    if hashlib.sha256(tagged_patch).hexdigest() != build["patch_sha256"]:
        raise ValueError("Baseline movement patch does not match the selected source revision")
    return binary, {
        **({"source_revision": revision} if revision is not None else {"tag": tag}),
        "commit": commit,
        "revision": build["revision"],
        "patch_sha256": build["patch_sha256"],
        "binary_sha256": build["binary_sha256"],
        "build_metadata": {field: build[field] for field in comparable if field in build},
        "metadata_not_comparable": [
            field for field in comparable if field not in build or field not in updated_build
        ],
    }


def compose(axis, *, scenario="reversal"):
    suffix = axis if scenario == "reversal" else f"{scenario}-{axis}"
    stem = DEST / f"native-resize-{suffix}-comparison"
    clip_suffix = axis if scenario == "reversal" else f"{scenario}-{axis}"
    if axis == "height" and scenario == "orthogonal":
        scaling, width = "crop=864:900:0:0,scale=500:-2", 1000
    elif axis == "height":
        scaling, width = "crop=682:900:0:0,scale=375:-2", 750
    else:
        scaling, width = "crop=1024:900:0:0,scale=600:-2", 1200
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-i",
            str(DEST / f"before-{clip_suffix}.mkv"),
            "-i",
            str(DEST / f"after-{clip_suffix}.mkv"),
            "-filter_complex",
            f"[0:v]fps=50,{scaling}:flags=lanczos[a];[1:v]fps=50,{scaling}:flags=lanczos[b];[a][b]hstack=shortest=1[v]",
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
    encode_gif(stem.with_suffix(".mkv"), stem.with_suffix(".gif"), width=width, fps=50, colors=128)
    return stem.with_suffix(".gif"), width


def check_edges(clips, axis):
    """Reject a comparison that misses the bug or hides a remaining separation."""
    pair = {clip["case"].split("-")[0]: clip for clip in clips if clip["case"].endswith(axis)}
    assert pair["before"]["edges"]["max_gap_px"] > 36, "Baseline did not reproduce the gap"
    assert pair["after"]["edges"]["max_gap_px"] <= 20, (
        "Updated edge separation exceeds codec tolerance"
    )
    assert pair["after"]["edges"]["min_gap_px"] >= 12, (
        "Updated windows overlap beyond codec tolerance"
    )
    if axis == "width":
        assert all(clip["edges"]["max_far_edge_px"] <= 1024 for clip in pair.values()), (
            "Comparison crop would hide a window edge"
        )


def main():
    global DEST, FIXTURE, BASELINE_LABEL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--baseline-tag", default="v0.18.0")
    parser.add_argument("--output", type=Path, default=DEST)
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Update the two GIFs, scenario manifest entries and public comparison evidence",
    )
    args = parser.parse_args()
    DEST, FIXTURE = args.output.resolve(), args.fixture.resolve()
    BASELINE_LABEL = "Baseline " + args.baseline_tag.removeprefix("v").removesuffix(".0")
    DEST.mkdir(parents=True, exist_ok=True)
    if not FIXTURE.is_file():
        parser.error("Synthetic fixture is missing")
    updated, updated_build, _ = experiment()
    before, baseline_build = baseline(args.baseline_manifest, args.baseline_tag, updated_build)
    evidence = {
        "schema": 1,
        "revision": updated_build["revision"],
        "patch_sha256": updated_build["patch_sha256"],
        "binary_sha256": updated_build["binary_sha256"],
        "baseline": baseline_build,
        "config_sha256": hashlib.sha256(CONFIG.encode()).hexdigest(),
        "sources": source_hashes(
            str(Path(__file__).resolve().relative_to(ROOT)),
            str(FIXTURE.relative_to(ROOT)),
            "scripts/lib/nested.py",
            "scripts/lib/movement.py",
        ),
        "scope": "Native resize geometry with identical passthrough shaders; no assertion of shader-phase, close, minimum-size-clamp or config-reload continuity.",
        "clips": [],
        "comparisons": [],
    }
    for version, binary in [("before", before), ("after", updated)]:
        for vertical in (False, True):
            clip = capture(binary, version, vertical)
            clip["edges"] = measure_video(DEST / f"{clip['case']}.mkv", vertical)
            evidence["clips"].append(clip)
    # Validate both axes before touching any published media.
    for axis in ("width", "height"):
        check_edges(evidence["clips"], axis)
    clips = []
    for axis in ("width", "height"):
        gif, width = compose(axis)
        destination = ROOT / "docs/gifs" / gif.name
        evidence["comparisons"].append(
            {"file": str(destination.relative_to(ROOT)), "gif_sha256": digest(gif)}
        )
        clips.append(
            {
                "name": gif.stem,
                "file": str(destination.relative_to(ROOT)),
                "title": f"Interrupted {axis} resize: baseline and updated",
                "mode": "resize",
                "bytes": gif.stat().st_size,
                "fps": 50,
                "width": width,
                "colors": 128,
                "duration_ms": 1200,
                "backend": "pinned patched Niri nested winit; synthetic clients; sequential native captures shown side by side",
                "revision": evidence["revision"],
                "patch_sha256": evidence["patch_sha256"],
                "baseline": baseline_build,
                "sources": evidence["sources"],
                "checks": [
                    "verified build identities",
                    "bounded interruption timing",
                    "same window IDs and settled dimensions",
                    "decoded native edge separation",
                ],
            }
        )
    report = json.dumps(evidence, indent=2) + "\n"
    (DEST / "checks.json").write_text(report)
    if args.publish:
        for clip in clips:
            destination = ROOT / clip["file"]
            shutil.copyfile(DEST / destination.name, destination)
        save_clips(clips)
        (ROOT / "docs/benchmarks/resize-continuity.json").write_text(report)


if __name__ == "__main__":
    main()
