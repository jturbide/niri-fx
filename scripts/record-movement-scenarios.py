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
from lib.nested import NestedSession, encode_gif, record, save_clips, stop, wait_for

from niri_fx.effects import PRESETS, movement_shader


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
    clips = []
    for scenario in ("interrupted", "close-during-move"):
        name = "native-" + scenario
        with NestedSession(cfg, binary=binary) as session:
            for label, color in (("blue", "#245d8a"), ("orange", "#985235")):
                session.launch(
                    ["qs", "-p", str(ROOT / "scripts/fixtures/window.qml")],
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
            recorder, video = record(session, name)
            time.sleep(0.5)
            session.msg("action", "move-column-left")
            time.sleep(0.35)
            if scenario == "interrupted":
                session.msg("action", "move-column-right")
                time.sleep(0.35)
                session.msg("action", "move-column-left")
            else:
                session.msg("action", "close-window", "--id", str(right["id"]))
            time.sleep(1.8)
            after = session.capture("after")
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
                    for color in ((36, 93, 138), (152, 82, 53)):
                        assert first.get(color, 0) > 1000
                        assert abs(first[color] - last.get(color, 0)) < first[color] * 0.02
            else:
                assert len(settled) == 1 and settled[0]["id"] != right["id"]
                victim = (36, 93, 138) if right["title"].endswith("blue") else (152, 82, 53)
                with Image.open(after) as image:
                    colors = {
                        c: n for n, c in image.convert("RGB").getcolors(image.width * image.height)
                    }
                    assert colors.get(victim, 0) == 0
                    survivor = (152, 82, 53) if victim == (36, 93, 138) else (36, 93, 138)
                    assert colors.get(survivor, 0) > 1000
            session.check_render_log()
            time.sleep(0.6)
            stop(recorder, signal.SIGINT)
            dest = ROOT / "docs/gifs" / f"{name}.gif"
            encode_gif(video, dest)
            clips.append(
                {
                    "name": name,
                    "file": str(dest.relative_to(ROOT)),
                    "bytes": dest.stat().st_size,
                    "preset": "explosion",
                    "effect": asdict(effect),
                    "duration_ms": 1200,
                    "revision": build["revision"],
                    "patch_sha256": build["patch_sha256"],
                    "backend": "pinned patched Niri nested winit; synthetic clients",
                    "checks": ["final window IDs and positions", "settled color populations"],
                }
            )
            print(f"PASS {name}; evidence: {session.root}", flush=True)
    save_clips(clips)


if __name__ == "__main__":
    main()
