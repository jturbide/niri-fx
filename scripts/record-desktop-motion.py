#!/usr/bin/env python3
"""Record stock workspace, camera and overview springs with synthetic clients."""

import json
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.movement import PALETTE, launch_cards
from lib.nested import NestedSession, encode_gif, record, save_clips, source_hashes, stop, wait_for

from niri_fx.catalog import PROFILES
from niri_fx.effects import render_kdl

BASE = """hotkey-overlay { skip-at-startup; }
prefer-no-csd
layout {
    gaps 24
    default-column-width { proportion 0.7; }
    center-focused-column "never"
    background-color "#111827"
    focus-ring { off; }
    border { off; }
}
workspace "Home"
workspace "Away"
"""


def main():
    for key in ("gentle-motion", "balanced-motion", "playful-motion"):
        profile = PROFILES[key]
        with NestedSession(BASE + render_kdl(profile), width=1280, height=800) as session:
            windows = launch_cards(session)
            time.sleep(1.5)
            notes = next(w for w in windows if w["title"].endswith("Notes"))
            library = next(w for w in windows if w["title"].endswith("Library"))
            session.msg(
                "action", "move-window-to-workspace", "--window-id", str(library["id"]), "Away"
            )
            session.msg("action", "focus-workspace", "Home")
            session.launch(
                ["qs", "-p", str(ROOT / "scripts/fixtures/movement.qml")],
                "Draft",
                env=session.env | {"NIRIFX_LABEL": "Draft", "NIRIFX_COLOR": "#d6dbe4"},
                private_bus=True,
            )
            windows = wait_for(
                lambda: session.windows() if len(session.windows()) == 3 else None, "three clients"
            )
            draft = next(w for w in windows if w["title"].endswith("Draft"))
            session.msg("action", "focus-window", "--id", str(notes["id"]))
            time.sleep(1)
            recorder, video = record(session, key, fps=50)
            latencies = []

            def action(*args, _latencies=latencies):
                started = time.monotonic()
                session.msg("action", *args)
                elapsed = (time.monotonic() - started) * 1000
                assert elapsed < 150, "Stock IPC stalled during recording"
                _latencies.append({"action": args[0], "ack_ms": elapsed})
                time.sleep(1)

            time.sleep(0.35)
            action("focus-workspace", "Away")
            action("focus-workspace", "Home")
            action("focus-window", "--id", str(draft["id"]))
            action("focus-window", "--id", str(notes["id"]))
            action("open-overview")
            action("close-overview")
            stop(recorder, signal.SIGINT)
            assert {w["id"] for w in session.windows()} == {w["id"] for w in windows}
            assert next(w for w in session.windows() if w["id"] == notes["id"])["is_focused"]
            session.check_render_log()
            name = "stock-" + key
            dest = ROOT / f"docs/gifs/{name}.gif"
            encode_gif(video, dest, width=640, fps=50, colors=48)
            source = f"examples/profiles/{key}.json"
            save_clips(
                [
                    {
                        "name": name,
                        "file": str(dest.relative_to(ROOT)),
                        "title": key.replace("-", " ").title(),
                        "mode": "desktop",
                        "source": source,
                        "bytes": dest.stat().st_size,
                        "fps": 50,
                        "palette": PALETTE,
                        "backend": "stock Niri nested winit; synthetic clients",
                        "version": session.version,
                        "sources": source_hashes(
                            "scripts/record-desktop-motion.py",
                            "scripts/fixtures/movement.qml",
                            source,
                        ),
                        "checks": [
                            "workspace round trip",
                            "camera round trip",
                            "overview open/close",
                            "same window IDs",
                            "render log",
                        ],
                    }
                ]
            )
            (session.root / "checks.json").write_text(
                json.dumps({"profile": key, "ipc": latencies}, indent=2) + "\n"
            )
            print(f"PASS {name}; evidence: {session.root}", flush=True)


if __name__ == "__main__":
    main()
