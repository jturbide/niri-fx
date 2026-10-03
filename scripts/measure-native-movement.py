#!/usr/bin/env python3
"""Measure native capture delivery and IPC latency, not physical presentation time."""

import argparse
import json
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.movement import experiment, launch_cards
from lib.nested import NestedSession, record, stop

from niri_fx.effects import FAMILIES, PRESETS, movement_shader


def distribution(values):
    ordered = sorted(values)
    return {
        "samples": len(values),
        "p50_ms": ordered[round((len(ordered) - 1) * 0.5)],
        "p95_ms": ordered[round((len(ordered) - 1) * 0.95)],
        "max_ms": ordered[-1],
        "raw_ms": values,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--presets", default="balanced,core-detonation")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh output filename")
    names = args.presets.split(",")
    if any(name not in PRESETS or not FAMILIES[PRESETS[name].family]["movement"] for name in names):
        parser.error("Choose movement-capable presets")
    binary, build, config = experiment()
    if binary.parent.name != "release":
        parser.error("Use a release build for measurement")
    results = []
    for name in names:
        effect = PRESETS[name]
        with NestedSession(
            config(effect, 1200, movement_shader(effect)), binary=binary, width=1280, height=800
        ) as session:
            windows = launch_cards(session)
            time.sleep(1.5)
            right = max(windows, key=lambda w: w["layout"]["pos_in_scrolling_layout"][0])
            session.msg("action", "focus-window", "--id", str(right["id"]))
            # Omit wf-recorder's fixed-rate resampling. Matroska timestamps retain
            # delivery intervals, including capture/encoder/host scheduling cost.
            recorder, video = record(session, "cadence", fps=None)
            latencies = []
            for i in range(6):
                start = time.monotonic()
                session.msg("action", "move-column-left" if i % 2 == 0 else "move-column-right")
                latencies.append((time.monotonic() - start) * 1000)
                time.sleep(1.3)
            stop(recorder, signal.SIGINT)
            session.check_render_log()
            frames = json.loads(
                subprocess.check_output(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-select_streams",
                        "v:0",
                        "-show_entries",
                        "frame=best_effort_timestamp_time",
                        "-of",
                        "json",
                        str(video),
                    ],
                    text=True,
                )
            )["frames"]
            times = [float(frame["best_effort_timestamp_time"]) for frame in frames]
            intervals = [(b - a) * 1000 for a, b in zip(times, times[1:], strict=False) if b > a]
            assert len(intervals) > 50, "Capture did not produce enough frames"
            result = {
                "preset": name,
                "output": session.outputs,
                "capture_intervals": distribution(intervals),
                "ipc_acknowledgement": distribution(latencies),
            }
            results.append(result)
            print(
                f"{name}: capture p95 {result['capture_intervals']['p95_ms']:.2f} ms; IPC p95 {result['ipc_acknowledgement']['p95_ms']:.2f} ms",
                flush=True,
            )
    args.output.write_text(
        json.dumps(
            {
                "schema": 1,
                "scope": "Nested winit capture delivery intervals without fixed-rate resampling, plus IPC acknowledgement latency. Includes host compositor, screencopy and encoder scheduling. Does not measure GPU draw time, input latency, physical scanout or dropped presentation frames.",
                "platform": platform.platform(),
                "niri_revision": build["revision"],
                "patch_sha256": build["patch_sha256"],
                "build_profile": "release",
                "results": results,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
