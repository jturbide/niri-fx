#!/usr/bin/env python3
"""Record retargeting and close-during-movement in the pinned Niri experiment."""

import hashlib
import importlib.util
import json
import signal
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.nested import NestedSession, encode_gif, record, save_clips, source_hashes, stop, wait_for

from niri_fx.effects import PRESETS, movement_shader


def timed_action(session, actions, *arguments):
    requested = time.monotonic()
    session.msg("action", *arguments)
    acknowledged = time.monotonic()
    # Occlusion or a busy compositor can postpone IPC until after the animation
    # ends. Reject that capture instead of labelling completed moves as interrupted.
    assert acknowledged - requested < 0.15, "Movement IPC stalled during capture"
    if actions:
        assert acknowledged - actions[-1][1] < 0.6, "Missed interruption window"
    actions.append((arguments[0], acknowledged))


def main():
    from PIL import Image

    build = json.loads((ROOT / "artifacts/niri-movement-build.json").read_text())
    binary = Path(build["binary"])
    for path, expected in (
        (binary, build["binary_sha256"]),
        (ROOT / "experimental/niri-movement.patch", build["patch_sha256"]),
    ):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SystemExit("Movement build changed; run scripts/build-niri-movement.py first")
    spec = importlib.util.spec_from_file_location("nested_demo", ROOT / "scripts/nested-demo.py")
    demo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(demo)
    effect = PRESETS["explosion"]
    cfg = demo.config(effect, 1200, movement_shader(effect))
    palette = {"Notes": "#b7e8db", "Library": "#d6c5ef"}
    rgb = {name: tuple(bytes.fromhex(color[1:])) for name, color in palette.items()}
    clips = []
    for scenario in ("interrupted", "close-during-move"):
        name = "native-" + scenario
        with NestedSession(cfg, binary=binary, width=1280, height=800) as session:
            for label, color in palette.items():
                session.launch(
                    ["qs", "-p", str(ROOT / "scripts/fixtures/movement.qml")],
                    label,
                    env=session.env | {"NIRIFX_LABEL": label, "NIRIFX_COLOR": color},
                    private_bus=True,
                )
            windows = wait_for(
                lambda: session.windows() if len(session.windows()) == 2 else None,
                "two synthetic windows",
            )
            time.sleep(1.5)
            right = max(windows, key=lambda w: w["layout"]["pos_in_scrolling_layout"][0])
            session.msg("action", "focus-window", "--id", str(right["id"]))
            before = session.capture("before")
            recorder, video = record(session, name, fps=50)
            actions = []

            time.sleep(0.5)
            timed_action(session, actions, "move-column-left")
            time.sleep(0.35)
            if scenario == "interrupted":
                timed_action(session, actions, "move-column-right")
                time.sleep(0.35)
                timed_action(session, actions, "move-column-left")
            else:
                timed_action(session, actions, "close-window", "--id", str(right["id"]))
            time.sleep(1.5)
            after = session.capture("after")
            # Keep verification work outside the recording: pixel counting can
            # otherwise add long, machine-dependent holds at the end of the GIF.
            stop(recorder, signal.SIGINT)
            settled = session.windows()
            if scenario == "interrupted":
                assert len(settled) == 2
                assert all(
                    next(w for w in settled if w["id"] == old["id"])["layout"][
                        "pos_in_scrolling_layout"
                    ][0]
                    != old["layout"]["pos_in_scrolling_layout"][0]
                    for old in windows
                )
                with Image.open(before) as a, Image.open(after) as b:
                    # Arrangement changes but both fully reconstructed surfaces
                    # keep the same color population; tolerate antialiasing edges.
                    first = dict((c, n) for n, c in a.convert("RGB").getcolors(a.width * a.height))
                    last = dict((c, n) for n, c in b.convert("RGB").getcolors(b.width * b.height))
                    for color in rgb.values():
                        assert first.get(color, 0) > 1000
                        assert abs(first[color] - last.get(color, 0)) < first[color] * 0.02
            else:
                assert len(settled) == 1 and settled[0]["id"] != right["id"]
                victim = rgb[right["title"].removeprefix("NiriFX fixture / ")]
                with Image.open(after) as image:
                    colors = {
                        c: n for n, c in image.convert("RGB").getcolors(image.width * image.height)
                    }
                    assert colors.get(victim, 0) == 0
                    survivor = next(color for color in rgb.values() if color != victim)
                    assert colors.get(survivor, 0) > 1000
            session.check_render_log()
            dest = ROOT / "docs/gifs" / f"{name}.gif"
            encode_gif(video, dest, width=720, fps=50, colors=32)
            clips.append(
                {
                    "name": name,
                    "file": str(dest.relative_to(ROOT)),
                    "bytes": dest.stat().st_size,
                    "preset": "explosion",
                    "effect": asdict(effect),
                    "duration_ms": 1200,
                    "fps": 50,
                    "width": 720,
                    "colors": 32,
                    "palette": palette,
                    "build_profile": binary.parent.name,
                    "actions": [
                        {"action": name, "offset_ms": round((at - actions[0][1]) * 1000)}
                        for name, at in actions
                    ],
                    "sources": source_hashes("scripts/fixtures/movement.qml"),
                    "revision": build["revision"],
                    "patch_sha256": build["patch_sha256"],
                    "backend": "pinned patched Niri nested winit; synthetic clients",
                    "checks": [
                        "interruption timing",
                        "final window IDs and positions",
                        "settled color populations",
                    ],
                }
            )
            print(f"PASS {name}; evidence: {session.root}", flush=True)
    save_clips(clips)


if __name__ == "__main__":
    main()
