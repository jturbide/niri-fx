#!/usr/bin/env python3
"""Check native rearrangement and overlapping actions with owned synthetic clients."""

import argparse
import json
import signal
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.movement import PALETTE, color_counts, experiment, launch_cards
from lib.nested import NestedSession, encode_gif, record, save_clips, source_hashes, stop, wait_for

from niri_fx.documents import load_document, parse_document
from niri_fx.effects import PRESETS, movement_shader
from niri_fx.profiles import Profile


def positions(windows):
    return {w["id"]: w["layout"]["pos_in_scrolling_layout"] for w in windows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preset",
        choices=("fragment-wake", "ribbon-transfer", "momentum-glide"),
        default="fragment-wake",
    )
    parser.add_argument(
        "--record", action="store_true", help="Save a native rearrangement gallery clip"
    )
    args = parser.parse_args()
    if args.record and args.preset != "fragment-wake":
        parser.error("Recording uses the documented Fragment Wake overlap profile")
    binary, build, config = experiment()
    effect = PRESETS[args.preset]
    duration = effect.movement_ms
    # Explicit fixture opt-in; built-in styles never enable resize themselves.
    profile = Profile(
        effect,
        effect,
        replace(
            PRESETS["triangle-shatter"], resize_mode="edge", resize_strength=0.45, resize_ms=800
        ),
        effect,
    )
    if args.record:
        documented = parse_document(
            load_document(ROOT / "examples/profiles/movement-overlaps.json")
        )[2]
        assert documented == profile, "Recording fixture differs from the portable example"
    with NestedSession(
        config(profile, duration, movement_shader(effect)), binary=binary, width=1280, height=800
    ) as session:
        empty = session.capture("empty")
        windows = launch_cards(session)
        time.sleep(1.5)
        ids = set(positions(windows))
        results, latencies = [], []
        recording = False

        def action(*arguments):
            # winit can stop delivering frames when its host window is occluded.
            # Keep the owned test window visible before timing its own IPC.
            session.focus()
            started = time.monotonic()
            session.msg("action", *arguments)
            elapsed = (time.monotonic() - started) * 1000
            latencies.append({"action": arguments, "milliseconds": elapsed, "recording": recording})
            # Capture drives regular frames. Idle winit scheduling is not a
            # compositor performance measurement; functional calls have a
            # separate ten-second subprocess timeout in NestedSession.msg.
            if recording:
                assert elapsed < 150, (arguments, elapsed)

        def settled(label):
            time.sleep(duration / 1000 + 0.4)
            current = session.windows()
            assert set(positions(current)) == ids, label
            assert all(count > 1000 for count in color_counts(session.capture(label)).values())
            session.check_render_log()
            results.append({"case": label, "positions": positions(current), "clients_intact": True})
            return current

        right = max(windows, key=lambda w: w["layout"]["pos_in_scrolling_layout"][0])
        action("focus-window", "--id", str(right["id"]))
        recorder = None
        if args.record:
            recorder, video = record(session, "rearrangement", fps=50)
            recording = True
            time.sleep(0.35)
        action("consume-or-expel-window-left")
        time.sleep(0.2)
        session.capture("consume-middle")
        consumed = settled("consumed")
        assert len({p[0] for p in positions(consumed).values()}) == 1
        bottom = max(consumed, key=lambda w: w["layout"]["pos_in_scrolling_layout"][1])
        action("focus-window", "--id", str(bottom["id"]))
        action("move-window-up")
        time.sleep(0.2)
        session.capture("vertical-middle")
        vertical = settled("vertical-reorder")
        assert positions(vertical)[bottom["id"]][1] < positions(consumed)[bottom["id"]][1]
        action("expel-window-from-column")
        expelled = settled("expelled")
        assert len({p[0] for p in positions(expelled).values()}) == 2
        if recorder:
            recording = False
            stop(recorder, signal.SIGINT)
            dest = ROOT / "docs/gifs/native-rearrangement.gif"
            encode_gif(video, dest, width=640, fps=50, colors=32)
            save_clips(
                [
                    {
                        "name": "native-rearrangement",
                        "file": str(dest.relative_to(ROOT)),
                        "title": "Consume, vertical reorder and expel",
                        "mode": "movement",
                        "preset": args.preset,
                        "source": "examples/profiles/movement-overlaps.json",
                        "effect": asdict(effect),
                        "duration_ms": duration,
                        "fps": 50,
                        "bytes": dest.stat().st_size,
                        "palette": PALETTE,
                        "backend": "pinned patched Niri nested winit; synthetic clients",
                        "revision": build["revision"],
                        "patch_sha256": build["patch_sha256"],
                        "sources": source_hashes(
                            "scripts/test-movement.py",
                            "scripts/fixtures/movement.qml",
                            "examples/profiles/movement-overlaps.json",
                        ),
                        "checks": [
                            "bounded IPC",
                            "same window IDs",
                            "vertical and horizontal positions",
                            "settled colors",
                            "render log",
                        ],
                    }
                ]
            )
        # Explicit layout changes exercise movement continuation around the
        # floating boundary. Endpoint/ID checks do not assert velocity equality.
        floating_id = expelled[0]["id"]
        float_recorder = None
        if args.record:
            float_recorder, float_video = record(session, "floating-cycle", fps=50)
            recording = True
            time.sleep(0.35)
        action("move-window-to-floating", "--id", str(floating_id))
        time.sleep(0.18)
        action("set-window-width", "--id", str(floating_id), "650")
        time.sleep(0.18)
        floating = settled("floating-resize")
        assert next(w for w in floating if w["id"] == floating_id)["is_floating"]
        action("move-window-to-tiling", "--id", str(floating_id))
        expelled = settled("retiled")
        assert not any(w["is_floating"] for w in expelled)
        if float_recorder:
            recording = False
            stop(float_recorder, signal.SIGINT)
            dest = ROOT / "docs/gifs/native-floating-cycle.gif"
            encode_gif(float_video, dest, width=640, fps=50, colors=32)
            save_clips(
                [
                    {
                        "name": "native-floating-cycle",
                        "file": str(dest.relative_to(ROOT)),
                        "title": "Tiled to floating, resize and return",
                        "mode": "movement",
                        "preset": args.preset,
                        "source": "examples/profiles/movement-overlaps.json",
                        "effect": asdict(effect),
                        "duration_ms": duration,
                        "fps": 50,
                        "bytes": dest.stat().st_size,
                        "palette": PALETTE,
                        "backend": "pinned patched Niri nested winit; synthetic clients",
                        "revision": build["revision"],
                        "patch_sha256": build["patch_sha256"],
                        "sources": source_hashes(
                            "scripts/test-movement.py",
                            "scripts/fixtures/movement.qml",
                            "examples/profiles/movement-overlaps.json",
                        ),
                        "checks": [
                            "bounded IPC",
                            "same window IDs",
                            "floating and tiled states",
                            "settled colors",
                            "render log",
                        ],
                    }
                ]
            )
        session.focus()
        right = max(expelled, key=lambda w: w["layout"]["pos_in_scrolling_layout"][0])
        action("focus-window", "--id", str(right["id"]))
        start = positions(expelled)
        for index in range(6):
            action("move-column-left" if index % 2 == 0 else "move-column-right")
            time.sleep(0.12)
        assert positions(settled("six-reversals")) == start
        action("move-column-left")
        time.sleep(0.12)
        action("set-column-width", "55%")
        time.sleep(0.15)
        session.capture("resize-during-move")
        settled("resize-and-move-settled")
        # Inserting and closing a third client must preserve both existing IDs.
        third = session.launch(
            ["qs", "-p", str(ROOT / "scripts/fixtures/movement.qml")],
            "Inserted",
            env=session.env | {"NIRIFX_LABEL": "Inserted", "NIRIFX_COLOR": "#d6dbe4"},
            private_bus=True,
        )
        added = wait_for(
            lambda: session.windows() if len(session.windows()) == 3 else None, "inserted client"
        )
        newcomer = next(w for w in added if w["id"] not in ids)
        time.sleep(0.15)
        action("set-window-width", "--id", str(newcomer["id"]), "800")
        time.sleep(0.12)
        action("close-window", "--id", str(newcomer["id"]))
        settled("insertion-resize-close-during-open")
        stop(third)
        # Closing a moving client exercises deformation continuation and removal.
        action("focus-window", "--id", str(right["id"]))
        action("move-column-right")
        time.sleep(0.15)
        action("close-window", "--id", str(right["id"]))
        time.sleep(max(duration, effect.close_ms) / 1000 + 0.5)
        remaining = session.windows()
        assert len(remaining) == 1 and remaining[0]["id"] != right["id"]
        victim = right["title"].split(" / ")[-1]
        assert color_counts(session.capture("close-during-move"))[victim] == 0
        action("close-window", "--id", str(remaining[0]["id"]))
        time.sleep(effect.close_ms / 1000 + 0.5)
        assert not session.windows()
        from PIL import Image, ImageChops

        with Image.open(empty) as initial, Image.open(session.capture("empty-again")) as final:
            assert (
                ImageChops.difference(initial.convert("RGB"), final.convert("RGB")).getbbox()
                is None
            )
        session.check_render_log()
        (session.root / "checks.json").write_text(
            json.dumps(
                {
                    "preset": args.preset,
                    "results": results,
                    "ipc_ms": latencies,
                    "clean_endpoint": True,
                    "build": build,
                    "scope": "single nested output; position/cleanup checks do not prove velocity continuity",
                },
                indent=2,
            )
            + "\n"
        )
        print(
            f"PASS {args.preset}: consume/expel, vertical reorder, reversals, floating/tiled, move+resize, insertion/resize/removal and cleanup; evidence: {session.root}",
            flush=True,
        )


if __name__ == "__main__":
    main()
