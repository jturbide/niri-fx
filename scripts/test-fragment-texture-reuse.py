#!/usr/bin/env python3
"""Check resized continuous-fragment textures in an owned nested compositor.

Moving to a smaller output can shrink window content while its offscreen texture
keeps a larger allocation. Resize a held synthetic window to exercise that same
renderer path; compare its pixels with the regular renderer after release.
This does not establish physical monitor handoff or input-to-photon latency.
"""

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.fragment import FragmentSession, config, experiment
from lib.nested import source_hashes, wait_for
from lib.pointer import VirtualPointer, build_pointer, pointer_protocol
from lib.pointer_scene import changed_pixels, client, grab, place_floating, window

from niri_fx.fragment_motion import PRESETS


def exercise(protocol):
    binary, build = experiment()
    # A stationary held material has no deformation, so its rendered pixels must
    # match the ordinary window exactly. Keep native fragmentation selected.
    settings = replace(
        PRESETS["tear"].settings,
        press_spread=0,
        rotation_mode="none",
        rotation_degrees=0,
        tilt=0,
    )
    with FragmentSession(
        config("tear", settings=settings), binary=binary, width=1100, height=850
    ) as session:
        _, primary = client(session, "Texture reuse", "#b7e8db")
        helper = build_pointer(session.root / "pointer", protocol)
        checks = []
        evidence = {
            "status": "incomplete",
            "build": build,
            "scope": "Owned nested output, synthetic window and virtual pointer only",
            "limits": ["Physical cross-monitor handoff still requires desktop testing."],
            "sources": source_hashes(
                "scripts/test-fragment-texture-reuse.py",
                "scripts/lib/fragment.py",
                "scripts/lib/pointer_scene.py",
                "scripts/fixtures/pointer-card.qml",
            ),
            "checks": checks,
        }
        path = session.root / "fragment-texture-reuse.json"
        path.write_text(json.dumps(evidence, indent=2) + "\n")
        with VirtualPointer(session, helper) as pointer:
            for name, size in (
                ("width", [450, 600]),
                ("height", [700, 350]),
                ("both", [450, 350]),
            ):
                place_floating(session, primary, x=180, y=140, width=700, height=600)
                capabilities = json.loads(session.msg("-j", "niri-fx-fragment-capabilities"))[
                    "NiriFxFragmentCapabilities"
                ]
                assert capabilities["fragment_motion"] == 3, capabilities
                assert all(
                    capabilities[key]
                    for key in ("fragment_configured", "fragment_enabled", "renderer_verified")
                ), capabilities
                log = session.root / "Texture reuse.log"
                requests = log.read_text().count("NIRIFX_MOVE_REQUEST true")
                grab(session, pointer, primary)
                wait_for(
                    lambda log=log, requests=requests: (
                        log.read_text().count("NIRIFX_MOVE_REQUEST true") > requests
                    ),
                    "accepted synthetic move request",
                )
                session.capture(name + "-before-shrink")
                for action, value in zip(
                    ("set-window-width", "set-window-height"), size, strict=True
                ):
                    session.msg("action", action, "--id", str(primary), str(value))
                wait_for(
                    lambda size=size: window(session, primary)["layout"]["window_size"] == size,
                    "synthetic resized content",
                )
                time.sleep(0.25)
                held = session.capture(name + "-held")
                pointer.release()
                # The fragment release contract bounds its tail to two seconds.
                time.sleep(2.15)
                released = session.capture(name + "-released")
                assert window(session, primary)["layout"]["window_size"] == size
                different = changed_pixels(held, released)
                check = {"case": name, "content_size": size, "changed_pixels": different}
                checks.append(check)
                path.write_text(json.dumps(evidence, indent=2) + "\n")
                assert different < 30, (name, "retained texture changed window pixels", different)
                session.check_render_log()
        evidence["status"] = "passed"
        path.write_text(json.dumps(evidence, indent=2) + "\n")
        print(f"PASS fragment texture reuse; private evidence: {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pointer-protocol", type=Path)
    arguments = parser.parse_args()
    exercise(pointer_protocol(arguments.pointer_protocol))
