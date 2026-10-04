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
from lib.pointer_wobble import PRESETS as POINTER_PRESETS
from lib.pointer_wobble import render_node

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


def config(effect, duration, source, *, pointer_wobble=None):
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
        + (render_node(pointer_wobble) if pointer_wobble is not None else "")
        + "    }\n}\n"
    )


def selection(args):
    """Resolve one action document before starting a compositor or any clients."""
    default = "momentum-glide" if getattr(args, "pointer_wobble", None) else "explosion"
    document = (
        parse_document(load_document(args.custom))[2]
        if args.custom
        else PRESETS[args.preset or default]
    )
    movement = document.movement if isinstance(document, Profile) else document
    pointer = pointer_selection(args, document)
    # A named pointer demo selects open/close styling only. A custom profile
    # declares its timed movement independently of its pointer settings.
    if pointer is not None and not args.custom and not args.preset:
        movement = None
    if movement is None:
        if pointer is None:
            raise ValueError(
                "The profile must explicitly include a movement action or pointer settings"
            )
        if args.movement_strength is not None or getattr(args, "duration_ms", None) is not None:
            raise ValueError(
                "Movement overrides require an explicit timed movement action or preset"
            )
    elif not FAMILIES[movement.family]["movement"]:
        raise ValueError("This family does not support experimental movement")
    if args.movement_strength is not None:
        movement = replace(movement, movement_strength=args.movement_strength)
    # A profile already names its resize action; no override may silently replace it.
    if args.resize and isinstance(document, Profile):
        raise ValueError(
            "Set the profile's resize action instead of combining --custom with --resize"
        )
    if not isinstance(document, Profile):
        document = movement if movement is not None else document
        if args.resize and not FAMILIES[document.family]["resize"]:
            raise ValueError("This family does not support resize")
        document = replace(document, resize=args.resize)
    return document, movement


def pointer_selection(args, document):
    """A command-line preset overrides the portable profile only for this demo."""
    if name := getattr(args, "pointer_wobble", None):
        return POINTER_PRESETS[name].wobble
    return document.pointer if isinstance(document, Profile) else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choices = parser.add_mutually_exclusive_group()
    choices.add_argument(
        "--preset",
        choices=[name for name, effect in PRESETS.items() if FAMILIES[effect.family]["movement"]],
    )
    choices.add_argument(
        "--custom",
        type=Path,
        help="Portable effect or profile with explicit movement or pointer settings",
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
    parser.add_argument(
        "--pointer-wobble",
        choices=list(POINTER_PRESETS),
        help="Select a pointer preset; overrides a custom profile's pointer settings for this demo",
    )
    args = parser.parse_args()
    if args.duration_ms is not None and not 100 <= args.duration_ms <= 3000:
        parser.error("duration must be 100 to 3000 ms")
    try:
        document, movement = selection(args)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    pointer = pointer_selection(args, document)
    duration = args.duration_ms or (movement.movement_ms if movement is not None else 250)
    binary, _, _ = experiment(pointer_wobble=pointer is not None)
    # The standalone pointer demo isolates actual dragging. An explicit style
    # selection can also exercise the existing timed movement shader.
    source = movement_shader(movement) if movement is not None else None
    with NestedSession(
        config(document, duration, source, pointer_wobble=pointer), binary=binary
    ) as session:
        windows = launch_cards(session, pointer_wobble=pointer is not None)
        if pointer is not None and not args.smoke:
            # Start with immediate drag feedback. Niri's tiled title-bar gesture
            # first chooses between viewport panning and detaching a window.
            for index, window in enumerate(windows):
                for action in (
                    ("move-window-to-floating",),
                    ("set-window-width", "500"),
                    ("set-window-height", "500"),
                    ("move-floating-window", "--x", str(150 + index * 610), "--y", "160"),
                ):
                    session.msg("action", action[0], "--id", str(window["id"]), *action[1:])
        controls = (
            "Drag a card by its title bar; Alt+Q to close."
            if pointer is not None
            else "Alt+Left/Right to swap columns, Alt+R to resize, Alt+Q to close."
        )
        print(f"Nested demo: {controls}\nLogs: {session.root}", flush=True)
        if pointer is not None:
            label = (
                POINTER_PRESETS[args.pointer_wobble].name
                if args.pointer_wobble
                else "Custom profile settings"
            )
            print(
                f"Pointer wobble: {label} "
                f"(strength {pointer.strength:g}, damping {pointer.damping}%, frequency {pointer.frequency} Hz). "
                "Drag a card by its title bar with the left button. "
                "Release it to settle.",
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
        started = time.monotonic()
        # At the exact crossing, source colors can be blended or occluded by the
        # other window. Sample on either side and verify both intact endpoints.
        for fraction in (0.25, 0.75):
            time.sleep(max(0, started + duration / 1000 * fraction - time.monotonic()))
            middle = color_counts(session.capture(f"middle-{fraction}"))
            assert all(count > 0 for count in middle.values()), (fraction, middle)
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
        victim = right["title"].split(" / ")[1]
        assert counts[victim] == 0 and sum(counts.values()) > 1000
        session.check_render_log()
        print(
            "PASS: native swap, seven interrupted reversals, fallback and close cleanup", flush=True
        )


if __name__ == "__main__":
    main()
