#!/usr/bin/env python3
"""Record actual swaps with synthetic app cards in the isolated pinned compositor."""

import argparse
import json
import re
import signal
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.movement import PALETTE, color_counts, experiment, launch_cards
from lib.nested import NestedSession, encode_gif, record, source_hashes, stop

from niri_fx.effects import FAMILIES, PRESETS, movement_shader

SHOWCASE_PRESETS = (
    "explosion",
    "crosswind",
    "orbital-ribbons",
    "spring-wobble",
    "bubble-burst",
    "core-detonation",
    "twist-snap",
    "slice-exchange",
    "pixel-transfer",
    "soft-phase",
    "vortex-fold",
)


def record_swap(preset, name, duration=1200):
    binary, build, config = experiment()
    effect = PRESETS[preset]
    with NestedSession(
        config(effect, duration, movement_shader(effect)), binary=binary, width=1280, height=800
    ) as session:
        windows = launch_cards(session)
        time.sleep(1.5)
        windows = session.windows()
        right = max(windows, key=lambda w: w["layout"]["pos_in_scrolling_layout"][0])
        session.msg("action", "focus-window", "--id", str(right["id"]))
        before = color_counts(session.capture("before"))
        recorder, video = record(session, name, fps=50)
        time.sleep(0.35)
        latencies = []
        for action in ("move-column-left", "move-column-right"):
            session.focus()
            session.msg("action", "focus-window", "--id", str(right["id"]))
            requested = time.monotonic()
            session.msg("action", action)
            latencies.append((time.monotonic() - requested) * 1000)
            assert latencies[-1] < 150, "Movement IPC stalled during capture"
            time.sleep(duration / 1000 + 0.25)
        stop(recorder, signal.SIGINT)
        after = color_counts(session.capture("after"))
        settled = session.windows()
        assert {w["id"]: w["layout"]["pos_in_scrolling_layout"] for w in settled} == {
            w["id"]: w["layout"]["pos_in_scrolling_layout"] for w in windows
        }, {"initial": windows, "settled": settled}
        for label, count in before.items():
            assert count > 1000 and abs(after[label] - count) < count * 0.02
        session.check_render_log()
        dest = ROOT / "docs/gifs" / f"{name}.gif"
        encode_gif(video, dest, width=640, fps=50, colors=32)
        clip = {
            "file": str(dest.relative_to(ROOT)),
            "preset": preset,
            "effect": asdict(effect),
            "duration_ms": duration,
            "bytes": dest.stat().st_size,
            "fps": 50,
            "width": 640,
            "colors": 32,
            "palette": PALETTE,
            "build_profile": binary.parent.name,
            "sources": source_hashes("scripts/fixtures/movement.qml"),
            "revision": build["revision"],
            "patch_sha256": build["patch_sha256"],
            "backend": "pinned patched Niri nested winit; synthetic clients",
            "checks": [
                "bounded IPC latency",
                "round-trip window positions",
                "settled color populations",
                "shader render log",
            ],
        }
        path = ROOT / "docs/gifs/native-manifest.json"
        clips = json.loads(path.read_text())["clips"]
        path.write_text(
            json.dumps(
                {"clips": [c for c in clips if c["file"] != clip["file"]] + [clip]}, indent=2
            )
            + "\n"
        )
        (session.root / "checks.json").write_text(
            json.dumps({"before": before, "after": after, "ipc_ms": latencies}, indent=2) + "\n"
        )
        print(f"PASS {name}; evidence: {session.root}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preset",
        choices=[name for name, effect in PRESETS.items() if FAMILIES[effect.family]["movement"]],
        default="explosion",
    )
    parser.add_argument("--name", default="native-swap")
    parser.add_argument(
        "--all", action="store_true", help="Refresh the complete curated native swap gallery"
    )
    parser.add_argument(
        "--duration-ms", type=int, default=1200, help="Movement time for this recording"
    )
    args = parser.parse_args()
    if not 100 <= args.duration_ms <= 3000:
        parser.error("duration must be 100 to 3000 ms")
    if not re.fullmatch(r"native-swap(?:-[a-z0-9-]+)?", args.name):
        parser.error("name must be native-swap or native-swap-NAME")
    if args.all:
        for preset in SHOWCASE_PRESETS:
            record_swap(preset, "native-swap" + ("" if preset == "explosion" else "-" + preset))
    else:
        record_swap(args.preset, args.name, args.duration_ms)


if __name__ == "__main__":
    main()
