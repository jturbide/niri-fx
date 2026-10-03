#!/usr/bin/env python3
"""Check overlapping actions in an owned nested compositor, without installing it."""

import argparse
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.movement import experiment, launch_cards
from lib.nested import NestedSession, stop, wait_for

from niri_fx.documents import load_document, parse_document
from niri_fx.effects import PRESETS, movement_shader, render_kdl
from niri_fx.profiles import Profile

BASE = """hotkey-overlay { skip-at-startup; }
prefer-no-csd
layout { background-color "#111827"; focus-ring { off; }; border { off; }; }
window-rule { match title=r#"^NiriFX fixture /"#; open-floating true; }
"""


def changed_pixels(path, baseline):
    from PIL import Image, ImageChops

    with Image.open(path) as image, Image.open(baseline) as empty:
        delta = ImageChops.difference(image.convert("RGB"), empty.convert("RGB"))
        return sum(n for n, color in delta.getcolors(delta.width * delta.height) if max(color) > 16)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experimental", action="store_true", help="Use the pinned native build")
    parser.add_argument("--resize-profile", type=Path, help="Exercise an explicit resize profile")
    args = parser.parse_args()
    binary, build = "niri", None
    if args.experimental:
        binary, build, _ = experiment()
    # Resize is explicit in this test fixture; catalog defaults stay disabled.
    effect = replace(PRESETS["spring-wobble"], open_ms=1000, close_ms=1000, resize=True)
    if args.resize_profile:
        profile = parse_document(load_document(args.resize_profile))[2]
        if not isinstance(profile, Profile) or profile.resize is None:
            parser.error("--resize-profile requires a profile with an enabled resize slot")
        effect = profile
    config = BASE + render_kdl(effect)
    results = []
    with NestedSession(config, binary=binary) as session:
        for scale in (1.0, 1.5, 2.0):
            session.reload(config + f'output "winit" {{ scale {scale}; }}\n')
            outputs = json.loads(session.msg("-j", "outputs"))
            assert outputs["winit"]["logical"]["scale"] == scale
            time.sleep(0.5)
            empty = session.capture(f"scale-{scale}-empty")

            def launch(label):
                process = session.launch(
                    ["qs", "-p", str(ROOT / "scripts/fixtures/window.qml")],
                    label,
                    env=session.env | {"NIRIFX_LABEL": label},
                    private_bus=True,
                )
                window = wait_for(session.windows, "transparent fixture")[0]
                return process, window["id"]

            def close_and_check(process, window_id, label, *, baseline=empty, output_scale=scale):
                session.msg("action", "close-window", "--id", str(window_id))
                time.sleep(1.4)
                assert not session.windows(), label
                assert changed_pixels(session.capture(label + "-gone"), baseline) == 0, label
                stop(process)
                results.append({"case": label, "scale": output_scale, "empty_endpoint": True})

            for repeat in range(3):
                label = f"rapid-open-close-{scale}-{repeat}"
                process, window_id = launch(label)
                time.sleep(0.15)
                assert changed_pixels(session.capture(label + "-partial"), empty) > 100
                close_and_check(process, window_id, label)

            process, window_id = launch(f"resize-close-{scale}")
            time.sleep(1.3)
            session.msg("action", "set-window-width", "--id", str(window_id), "900")
            time.sleep(0.12)
            session.msg("action", "set-window-width", "--id", str(window_id), "400")
            time.sleep(0.12)
            close_and_check(process, window_id, f"close-during-resize-{scale}")

            process, window_id = launch(f"fullscreen-{scale}")
            time.sleep(1.3)
            for width in (850, 350, 700, 450):
                session.msg("action", "set-window-width", "--id", str(window_id), str(width))
                time.sleep(0.12)
            session.msg("action", "fullscreen-window", "--id", str(window_id))
            time.sleep(1.3)
            logical = outputs["winit"]["logical"]
            assert session.windows()[0]["layout"]["window_size"] == [
                logical["width"],
                logical["height"],
            ]
            session.capture(f"fullscreen-{scale}")
            session.msg("action", "fullscreen-window", "--id", str(window_id))
            time.sleep(1.3)
            assert session.windows()[0]["is_floating"]
            assert session.windows()[0]["layout"]["window_size"][0] == 450
            close_and_check(process, window_id, f"resize-reversal-fullscreen-{scale}")
            session.check_render_log()
            print(f"PASS transparent interruption cases at {scale}x", flush=True)
        if args.experimental:
            _, _, native_config = experiment()
            native_effect = PRESETS["spring-wobble"]
            session.reload(native_config(native_effect, 1200, movement_shader(native_effect)))
            windows = launch_cards(session)
            time.sleep(1.5)
            right = max(windows, key=lambda w: w["layout"]["pos_in_scrolling_layout"][0])
            session.msg("action", "focus-window", "--id", str(right["id"]))
            for index in range(8):
                session.msg("action", "move-column-left" if index % 2 == 0 else "move-column-right")
                time.sleep(0.12)
            time.sleep(1.5)
            settled = {w["id"]: w["layout"]["pos_in_scrolling_layout"] for w in session.windows()}
            assert settled == {w["id"]: w["layout"]["pos_in_scrolling_layout"] for w in windows}
            session.capture("rapid-reversals-settled")
            results.append({"case": "eight-rapid-reversals", "same_ids_and_columns": True})
            session.msg("action", "move-column-left")
            time.sleep(0.15)
            session.reload(render_kdl(native_effect))
            time.sleep(1.5)
            assert {w["id"] for w in session.windows()} == {w["id"] for w in windows}
            session.capture("shader-removal-fallback")
            session.check_render_log()
            results.append({"case": "remove-movement-shader", "windows_survive": True})
        (session.root / "checks.json").write_text(
            json.dumps(
                {
                    "backend": session.version,
                    "build": build,
                    "resize_profile": str(args.resize_profile) if args.resize_profile else None,
                    "results": results,
                    "scope": "single nested output; sequential scales, not mixed physical outputs",
                },
                indent=2,
            )
            + "\n"
        )
        print(f"Evidence: {session.root}", flush=True)


if __name__ == "__main__":
    main()
