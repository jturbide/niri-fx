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
from lib.nested import NestedSession, encode_gif, record, save_clips, source_hashes, stop

from niri_fx.documents import load_document, parse_document
from niri_fx.effects import FAMILIES, PRESETS, movement_shader
from niri_fx.profiles import Profile

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


def selection(preset=None, custom=None, duration=None):
    """Validate settings and their public source before starting the recorder."""
    document = (
        parse_document(load_document(custom))[2] if custom else PRESETS[preset or "explosion"]
    )
    effect = document.movement if isinstance(document, Profile) else document
    if effect is None:
        raise ValueError("The profile must explicitly include a movement action")
    if not FAMILIES[effect.family]["movement"]:
        raise ValueError("This family does not support experimental movement")
    source = str(custom.resolve().relative_to(ROOT)) if custom else None
    return document, effect, source, duration or (effect.movement_ms if custom else 1200)


def record_swap(preset, name, duration=None, custom=None):
    document, effect, source, duration = selection(preset, custom, duration)
    binary, build, config = experiment()
    with NestedSession(
        config(document, duration, movement_shader(effect)), binary=binary, width=1280, height=800
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
            "effect": asdict(effect),
            "duration_ms": duration,
            "bytes": dest.stat().st_size,
            "fps": 50,
            "width": 640,
            "colors": 32,
            "palette": PALETTE,
            "build_profile": binary.parent.name,
            "sources": source_hashes(
                "scripts/fixtures/movement.qml",
                "scripts/record-native-gif.py",
                *([source] if source else []),
            ),
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
        if source:
            # Full-profile recordings retain every action and a verifiable source.
            clip.update(name=name, source=source, mode="movement")
            save_clips([clip])
        else:
            clip["preset"] = preset or "explosion"
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
    choices = parser.add_mutually_exclusive_group()
    choices.add_argument(
        "--preset",
        choices=[name for name, effect in PRESETS.items() if FAMILIES[effect.family]["movement"]],
    )
    choices.add_argument(
        "--custom", type=Path, help="Public settings document with explicit movement"
    )
    parser.add_argument("--name", default="native-swap")
    parser.add_argument(
        "--all", action="store_true", help="Refresh the complete curated native swap gallery"
    )
    parser.add_argument("--duration-ms", type=int, help="Override movement time for this recording")
    args = parser.parse_args()
    if args.duration_ms is not None and not 100 <= args.duration_ms <= 3000:
        parser.error("duration must be 100 to 3000 ms")
    if not re.fullmatch(r"native-swap(?:-[a-z0-9-]+)?", args.name):
        parser.error("name must be native-swap or native-swap-NAME")
    if args.custom and (args.all or args.name == "native-swap"):
        parser.error("custom recordings require a distinct --name and cannot use --all")
    try:
        selection(args.preset, args.custom, args.duration_ms)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.all:
        for preset in SHOWCASE_PRESETS:
            record_swap(preset, "native-swap" + ("" if preset == "explosion" else "-" + preset))
    else:
        record_swap(args.preset, args.name, args.duration_ms, args.custom)


if __name__ == "__main__":
    main()
