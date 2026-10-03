#!/usr/bin/env python3
"""Record retargeting and close-during-movement in the pinned Niri experiment."""

import signal
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.movement import PALETTE, color_counts, experiment
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

    binary, build, config = experiment()
    palette = PALETTE
    rgb = {name: tuple(bytes.fromhex(color[1:])) for name, color in palette.items()}
    clips = []
    for scenario in ("interrupted", "rapid-reversals", "close-during-move"):
        preset = "spring-wobble" if scenario == "rapid-reversals" else "explosion"
        effect = PRESETS[preset]
        cfg = config(effect, 1200, movement_shader(effect))
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
            if scenario == "rapid-reversals":
                for index in range(7):
                    time.sleep(0.12)
                    timed_action(
                        session,
                        actions,
                        "move-column-right" if index % 2 == 0 else "move-column-left",
                    )
            elif scenario == "interrupted":
                time.sleep(0.35)
                timed_action(session, actions, "move-column-right")
                time.sleep(0.35)
                timed_action(session, actions, "move-column-left")
            else:
                time.sleep(0.35)
                timed_action(session, actions, "close-window", "--id", str(right["id"]))
            time.sleep(1.5)
            after = session.capture("after")
            # Keep verification work outside the recording: pixel counting can
            # otherwise add long, machine-dependent holds at the end of the GIF.
            stop(recorder, signal.SIGINT)
            settled = session.windows()
            if scenario in {"interrupted", "rapid-reversals"}:
                assert len(settled) == 2
                assert all(
                    (
                        next(w for w in settled if w["id"] == old["id"])["layout"][
                            "pos_in_scrolling_layout"
                        ][0]
                        != old["layout"]["pos_in_scrolling_layout"][0]
                    )
                    == (scenario == "interrupted")
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
                    "preset": preset,
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
            save_clips([clips[-1]])
            print(f"PASS {name}; evidence: {session.root}", flush=True)
    # Close an opening client before it can finish reconstruction. The native
    # continuation reuses its opening seed/clock instead of re-fragmenting a
    # baked intermediate texture with the closing shader.
    name = "native-close-during-open"
    effect = replace(PRESETS["explosion"], open_ms=1500, close_ms=1200)
    with NestedSession(
        config(effect, 1200, movement_shader(effect)), binary=binary, width=1280, height=800
    ) as session:
        recorder, video = record(session, name, fps=50)
        session.launch(
            ["qs", "-p", str(ROOT / "scripts/fixtures/movement.qml")],
            "Notes",
            env=session.env | {"NIRIFX_LABEL": "Notes", "NIRIFX_COLOR": PALETTE["Notes"]},
            private_bus=True,
        )
        windows = wait_for(lambda: session.windows() or None, "opening client")
        time.sleep(0.45)
        before = session.capture("opening-before-close")
        started = time.monotonic()
        session.msg("action", "close-window", "--id", str(windows[0]["id"]))
        assert time.monotonic() - started < 0.15
        time.sleep(0.12)
        continuing = session.capture("opening-after-close")
        time.sleep(1.5)
        stop(recorder, signal.SIGINT)
        assert not session.windows()
        assert color_counts(session.capture("settled"))["Notes"] == 0
        for frame in (before, continuing):
            with Image.open(frame) as image:
                # Intermediate shader alpha changes the exact palette color.
                # Mint remains distinguishable from the dark navy background.
                visible = sum(
                    count
                    for count, (r, g, b) in image.convert("RGB").getcolors(
                        image.width * image.height
                    )
                    if g > r * 1.07 and g > b and g > 60
                )
                assert visible > 100, "Interrupted opening must remain visibly animated"
        session.check_render_log()
        dest = ROOT / "docs/gifs" / f"{name}.gif"
        encode_gif(video, dest, width=720, fps=50, colors=32)
        clips.append(
            {
                "name": name,
                "file": str(dest.relative_to(ROOT)),
                "bytes": dest.stat().st_size,
                "preset": "explosion",
                "overrides": {"open_ms": 1500, "close_ms": 1200},
                "effect": asdict(effect),
                "fps": 50,
                "width": 720,
                "colors": 32,
                "palette": PALETTE,
                "build_profile": binary.parent.name,
                "sources": source_hashes("scripts/fixtures/movement.qml"),
                "revision": build["revision"],
                "patch_sha256": build["patch_sha256"],
                "backend": "pinned patched Niri nested winit; synthetic client",
                "checks": [
                    "close before opening duration",
                    "visible pre-close and continuing frames",
                    "no surviving surface",
                    "shader render log",
                ],
            }
        )
        print(f"PASS {name}; evidence: {session.root}", flush=True)
    save_clips(clips)


if __name__ == "__main__":
    main()
