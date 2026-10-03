#!/usr/bin/env python3
"""Exercise transparency, window shapes and fractional scale in nested stock Niri."""

import argparse
import json
import signal
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.nested import NestedSession, encode_gif, record, save_clips, stop, wait_for

from niri_fx.effects import PRESETS, render_kdl

BASE = """hotkey-overlay { skip-at-startup; }
prefer-no-csd
layout { background-color "#111827"; focus-ring { off; }; border { off; }; }
window-rule {
    match title=r#"^NiriFX fixture /"#
    open-floating true
    default-floating-position x=60 y=60 relative-to="top-left"
}
"""


def changed_pixels(path, baseline):
    from PIL import Image, ImageChops

    with Image.open(path) as image, Image.open(baseline) as empty:
        delta = ImageChops.difference(image.convert("RGB"), empty.convert("RGB"))
        return sum(
            count for count, color in delta.getcolors(delta.width * delta.height) if max(color) > 16
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="store_true", help="Write the verified synthetic GIFs")
    args = parser.parse_args()
    cases = (
        ("stock-transparent-fragments", "explosion", 600, 400, 1.0),
        ("stock-transparent-wisps", "ghost-wisps", 600, 400, 1.0),
        ("stock-wide-shockwave", "shockwave", 900, 280, 1.0),
        ("stock-tall-pixels", "pixel-wipe", 300, 660, 1.0),
        ("stock-fractional-frost", "frost-vanish", 600, 400, 1.5),
    )
    results = []
    with NestedSession(BASE + render_kdl(PRESETS["balanced"])) as session:
        for name, preset, width, height, scale in cases:
            effect = replace(PRESETS[preset], open_ms=1400, close_ms=1400)
            session.reload(BASE + f'output "winit" {{ scale {scale}; }}\n' + render_kdl(effect))
            outputs = json.loads(session.msg("-j", "outputs"))
            assert outputs["winit"]["logical"]["scale"] == scale, outputs
            empty = session.capture(name + "-empty")
            recorder = video = None
            if args.record:
                recorder, video = record(session, name)
            time.sleep(0.3)
            client = session.launch(
                ["qs", "-p", str(ROOT / "scripts/fixtures/window.qml")],
                name,
                env=session.env
                | {"NIRIFX_LABEL": name, "NIRIFX_WIDTH": str(width), "NIRIFX_HEIGHT": str(height)},
                private_bus=True,
            )
            windows = wait_for(session.windows, "synthetic window")
            assert len(windows) == 1 and windows[0]["title"] == f"NiriFX fixture / {name}"
            time.sleep(0.5)
            opening = session.capture(name + "-opening")
            time.sleep(1.2)
            intact = session.capture(name + "-intact")
            session.msg("action", "close-window", "--id", str(windows[0]["id"]))
            time.sleep(0.65)
            closing = session.capture(name + "-closing")
            time.sleep(1.1)
            gone = session.capture(name + "-gone")
            if recorder:
                stop(recorder, signal.SIGINT)
            stop(client)
            counts = {
                stage: changed_pixels(path, empty)
                for stage, path in (
                    ("opening", opening),
                    ("intact", intact),
                    ("closing", closing),
                    ("gone", gone),
                )
            }
            assert counts["intact"] > 1000 and counts["gone"] == 0, counts
            assert 0 < counts["opening"] < counts["intact"], counts
            assert 0 < counts["closing"] < counts["intact"], counts
            assert not session.windows()
            result = {
                "name": name,
                "preset": preset,
                "effect": asdict(effect),
                "scale": scale,
                "overrides": {"open_ms": 1400, "close_ms": 1400},
                "logical_size": [width, height],
                "counts": counts,
                "checks": [
                    "partial open/close",
                    "intact window",
                    "empty close endpoint",
                    "output scale",
                ],
                "backend": f"stock {session.version} nested winit; transparent synthetic Quickshell client",
            }
            if video:
                dest = ROOT / "docs/gifs" / f"{name}.gif"
                encode_gif(video, dest)
                result.update(file=str(dest.relative_to(ROOT)), bytes=dest.stat().st_size)
            results.append(result)
            print(f"PASS {name}: {counts}", flush=True)
        session.check_render_log()
        (session.root / "checks.json").write_text(json.dumps(results, indent=2) + "\n")
        print(f"Evidence: {session.root}", flush=True)
    if args.record:
        save_clips(results)


if __name__ == "__main__":
    main()
