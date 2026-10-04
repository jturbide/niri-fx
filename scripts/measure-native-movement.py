#!/usr/bin/env python3
"""Measure native output timing or capture delivery, with explicit source limits."""

import argparse
import json
import os
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

from niri_fx.capabilities import movement_capability
from niri_fx.effects import FAMILIES, PRESETS, movement_shader


def distribution(values):
    if not values:
        raise ValueError("No timing samples were collected")
    ordered = sorted(values)
    return {
        "samples": len(values),
        "p50_ms": ordered[round((len(ordered) - 1) * 0.5)],
        "p95_ms": ordered[round((len(ordered) - 1) * 0.95)],
        "max_ms": ordered[-1],
        "raw_ms": values,
    }


def native_timing(samples):
    """Never mix outputs or upgrade estimated timestamps into scanout evidence."""
    grouped = {}
    for sample in samples:
        grouped.setdefault((sample["output"], sample["source"]), {})[sample["timestamp_ns"]] = (
            sample
        )
    reports = []
    for (_, source), by_time in grouped.items():
        frames = sorted(by_time.values(), key=lambda sample: sample["timestamp_ns"])
        intervals = [
            (b["timestamp_ns"] - a["timestamp_ns"]) / 1e6
            for a, b in zip(frames, frames[1:], strict=False)
            if a.get("action") == b.get("action")
        ]
        if not intervals:
            continue
        hardware = source == "drm-presentation" and all(frame["flags"] & 7 == 7 for frame in frames)
        reports.append(
            {
                "output_index": len(reports),
                "source": source,
                "hardware_presentation": hardware,
                "flags": sorted({frame["flags"] for frame in frames}),
                "intervals": distribution(intervals),
                "scope": "DRM hardware presentation timestamps"
                if hardware
                else "Estimated submission timestamps; not physical scanout",
            }
        )
    if not reports:
        raise ValueError("The compositor did not report enough native timing samples")
    return reports


def frame_samples(session):
    return json.loads(session.msg("-j", "niri-fx-frame-timings"))["NiriFxFrameTimings"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--presets", default="balanced,core-detonation")
    parser.add_argument(
        "--running",
        action="store_true",
        help="Read recent feedback from a verified experimental session; do not move windows",
    )
    parser.add_argument("--movement-binary", type=Path, help="Trusted running experimental binary")
    parser.add_argument(
        "--timing-source",
        choices=("native", "capture"),
        default="native",
        help="Native output feedback by default; capture includes encoder delivery",
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Use a fresh output filename")
    if args.running:
        if args.timing_source != "native":
            parser.error("--running supports native timing only")
        support = movement_capability(
            args.movement_binary, socket_path=os.environ.get("NIRI_SOCKET")
        )
        if not support["activation_ready"] or not support["session"]["contract"]["frame_timings"]:
            parser.error("The running compositor must verify movement and frame feedback support")
        samples = json.loads(
            subprocess.check_output(
                [support["binary"], "msg", "-j", "niri-fx-frame-timings"],
                text=True,
                timeout=5,
            )
        )["NiriFxFrameTimings"]
        args.output.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "timing_source": "native",
                    "session_version": support["session"]["version"],
                    "scope": "Read-only recent output feedback, grouped by output. No workload is generated. Idle gaps are included; repeat after your chosen workload. Output names are omitted. Hardware presentation requires DRM with VSYNC, HW_CLOCK and HW_COMPLETION flags.",
                    "results": native_timing(samples),
                },
                indent=2,
            )
            + "\n"
        )
        print(f"Saved recent output feedback to {args.output}")
        return
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
            # Screencopy keeps the nested backend advancing while idle. Native
            # values come from output history, not encoder timestamps; this
            # diagnostic includes screencopy's measurement load.
            recorder, video = record(session, "cadence", fps=None)
            latencies, timings = [], []
            for i in range(6):
                session.focus()
                start = time.monotonic()
                session.msg("action", "move-column-left" if i % 2 == 0 else "move-column-right")
                latencies.append((time.monotonic() - start) * 1000)
                assert latencies[-1] < 150, "Nested IPC stalled; reject the timing run"
                time.sleep(1.3)
                if args.timing_source == "native":
                    timings.extend(
                        sample | {"action": i}
                        for sample in frame_samples(session)
                        if int(start * 1e9) <= sample["timestamp_ns"] <= int((start + 1.2) * 1e9)
                    )
            if recorder:
                stop(recorder, signal.SIGINT)
            session.check_render_log()
            if args.timing_source == "native":
                result = {
                    "preset": name,
                    "native_output_timing": native_timing(timings),
                    "ipc_acknowledgement": distribution(latencies),
                }
                results.append(result)
                for timing in result["native_output_timing"]:
                    print(
                        f"{name}: {timing['source']} p95 {timing['intervals']['p95_ms']:.2f} ms; hardware presentation: {timing['hardware_presentation']}",
                        flush=True,
                    )
                continue
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
                "scope": "Native output feedback during six owned swaps with screencopy keeping the nested backend active. Winit timestamps are estimated submissions, not hardware presentation. DRM samples qualify only with VSYNC, HW_CLOCK and HW_COMPLETION flags. Cross-action idle gaps are excluded. Includes measurement load; not GPU draw time or input latency."
                if args.timing_source == "native"
                else "Nested winit capture delivery intervals without fixed-rate resampling, plus IPC acknowledgement latency. Includes host compositor, screencopy and encoder scheduling. Does not measure GPU draw time, input latency, physical scanout or dropped presentation frames.",
                "timing_source": args.timing_source,
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
