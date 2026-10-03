#!/usr/bin/env python3
"""Run synthetic clients in an isolated Niri window, never a login session."""

import argparse
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.movement import color_counts, experiment, launch_cards
from lib.nested import NestedSession

from niri_fx.documents import load_document, parse_document
from niri_fx.effects import FAMILIES, PRESETS, movement_shader, render_kdl
from niri_fx.profiles import Profile

BASE = """layout {
    gaps 24
    default-column-width { proportion 0.42; }
    center-focused-column "never"
    focus-ring { off; }
    border { off; }
    background-color "#111827"
}
prefer-no-csd
hotkey-overlay { skip-at-startup; }
binds {
    Alt+Left { move-column-left; }
    Alt+Right { move-column-right; }
    Alt+R { switch-preset-column-width; }
    Alt+Q { quit skip-confirmation=true; }
}
"""


def config(effect, duration, source):
    # One animations node per file. Stock exports never include this extension.
    common = render_kdl(effect).rstrip()
    assert common.endswith("}")
    return (
        BASE
        + common[:-1]
        + f"""    window-movement {{
        duration-ms {duration}
        curve "linear"
"""
        + (f'        custom-shader r"\n{source}\n"\n' if source is not None else "")
        + "    }\n}\n"
    )


def selection(args):
    """Resolve one action document before starting a compositor or any clients."""
    document = (
        parse_document(load_document(args.custom))[2]
        if args.custom
        else PRESETS[args.preset or "explosion"]
    )
    movement = document.movement if isinstance(document, Profile) else document
    if movement is None:
        raise ValueError("The profile must explicitly include a movement action")
    if not FAMILIES[movement.family]["movement"]:
        raise ValueError("This family does not support experimental movement")
    if args.movement_strength is not None:
        movement = replace(movement, movement_strength=args.movement_strength)
    # A profile already names its resize action; no override may silently replace it.
    if args.resize and not FAMILIES[movement.family]["resize"]:
        raise ValueError("This family does not support resize")
    if args.resize and isinstance(document, Profile):
        raise ValueError(
            "Set the profile's resize action instead of combining --custom with --resize"
        )
    if not isinstance(document, Profile):
        document = replace(movement, resize=args.resize)
    return document, movement


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choices = parser.add_mutually_exclusive_group()
    choices.add_argument(
        "--preset",
        choices=[name for name, effect in PRESETS.items() if FAMILIES[effect.family]["movement"]],
    )
    choices.add_argument(
        "--custom", type=Path, help="Portable effect or profile with an explicit movement action"
    )
    parser.add_argument(
        "--duration-ms", type=int, help="Override the selected movement time (100 to 3000 ms)"
    )
    parser.add_argument(
        "--movement-strength", type=float, help="Override native deformation intensity (0 to 1)"
    )
    parser.add_argument(
        "--resize",
        action="store_true",
        help="Explicitly enable resize for a single style in this demo",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Check swaps, repeated reversals, fallback and cleanup, then exit",
    )
    args = parser.parse_args()
    if args.duration_ms is not None and not 100 <= args.duration_ms <= 3000:
        parser.error("duration must be 100 to 3000 ms")
    try:
        document, movement = selection(args)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    duration = args.duration_ms or movement.movement_ms
    binary, _, _ = experiment()
    source = movement_shader(movement)
    with NestedSession(config(document, duration, source), binary=binary) as session:
        windows = launch_cards(session)
        print(
            "Nested demo: Alt+Left/Right to swap columns, Alt+R to resize, Alt+Q to close.\nLogs: "
            + str(session.root),
            flush=True,
        )
        if not args.smoke:
            session.compositor.wait()
            return
        time.sleep(1.5)
        right = max(windows, key=lambda w: w["layout"]["pos_in_scrolling_layout"][0])
        session.msg("action", "focus-window", "--id", str(right["id"]))
        before = color_counts(session.capture("before"))
        session.msg("action", "move-column-left")
        time.sleep(duration / 2000)
        middle = color_counts(session.capture("middle"))
        assert all(count > 0 for count in middle.values()), middle
        time.sleep(duration / 1000 + 0.3)
        for index in range(7):
            session.msg("action", "move-column-right" if index % 2 == 0 else "move-column-left")
            time.sleep(0.12)
        time.sleep(duration / 1000 + 0.3)
        after = color_counts(session.capture("settled"))
        assert {w["id"]: w["layout"]["pos_in_scrolling_layout"] for w in session.windows()} == {
            w["id"]: w["layout"]["pos_in_scrolling_layout"] for w in windows
        }
        for label, initial in before.items():
            assert initial > 1000 and abs(initial - after[label]) < initial * 0.02
        session.reload(config(document, duration, None))
        session.msg("action", "move-column-left")
        time.sleep(duration / 1000 + 0.3)
        session.capture("fallback")
        session.reload(config(document, duration, source))
        session.msg("action", "move-column-right")
        time.sleep(0.15)
        session.msg("action", "close-window", "--id", str(right["id"]))
        close = document.close if isinstance(document, Profile) else document
        time.sleep(max(close.close_ms, duration) / 1000 + 1)
        remaining = session.windows()
        assert len(remaining) == 1 and remaining[0]["id"] != right["id"]
        counts = color_counts(session.capture("close-during-movement"))
        victim = right["title"].split(" / ")[-1]
        assert counts[victim] == 0 and sum(counts.values()) > 1000
        session.check_render_log()
        print(
            "PASS: native swap, seven interrupted reversals, fallback and close cleanup", flush=True
        )


if __name__ == "__main__":
    main()
