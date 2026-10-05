#!/usr/bin/env python3
"""Verify independent Move/Swap routing in an owned nested compositor.

Synthetic solid shader colors make accidental shared selection measurable.
This is renderer acceptance, not a claim about physical monitor behavior.
"""

import json
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.fragment import FragmentSession, experiment
from lib.nested import source_hashes
from lib.pointer_scene import BASE, client

COLORS = {"move": (0, 1, 1), "swap": (1, 0, 1), "next": (1, 1, 0)}


def shader(color):
    red, green, blue = COLORS[color]
    return (
        "vec4 move_color(vec3 c, vec3 s) { "
        "if (c.x < 0.0 || c.y < 0.0 || c.x > 1.0 || c.y > 1.0) return vec4(0.0); "
        f"return vec4({red}.0, {green}.0, {blue}.0, 1.0); }}"
    )


def config(swap="swap", *, movement_off=False):
    move = "off;" if movement_off else f'custom-shader "{shader("move")}";'
    extra = (
        ""
        if swap is None
        else "window-swap { "
        + (
            "off;"
            if swap == "off"
            else f'duration-ms 1400; curve "linear"; custom-shader "{shader(swap)}";'
        )
        + " };"
    )
    return (
        BASE
        + f"""animations {{
        window-open {{ off; }}
        window-close {{ duration-ms 800; curve "linear"; }}
        window-resize {{ off; }}
        horizontal-view-movement {{ off; }}
        window-movement {{ duration-ms 1400; curve "linear"; {move} }}
        {extra}
    }}\n"""
    )


def color_counts(path):
    counts = dict.fromkeys(COLORS, 0)
    with Image.open(path) as image:
        for red, green, blue in image.convert("RGB").getdata():
            if red < 60 and green > 120 and blue > 120:
                counts["move"] += 1
            if red > 120 and green < 60 and blue > 120:
                counts["swap"] += 1
            if red > 120 and green > 120 and blue < 60:
                counts["next"] += 1
    return counts


def main():
    binary, build = experiment()
    with FragmentSession(config(), binary=binary, width=1200, height=850) as session:
        checks = []
        evidence = {
            "status": "incomplete",
            "scope": "Owned nested output and synthetic clients only",
            "build": build,
            "sources": source_hashes("scripts/test-native-swap.py", "experimental/niri-swap.patch"),
            "checks": checks,
        }
        result = session.root / "swap-acceptance.json"

        def capture(name, expected):
            time.sleep(0.1)
            counts = color_counts(session.capture(name))
            checks.append({"case": name, "expected": expected, "colors": counts})
            result.write_text(json.dumps(evidence, indent=2) + "\n")
            if expected is None:
                assert max(counts.values()) < 1000, (name, counts)
            else:
                assert counts[expected] > 10000, (name, counts)
            session.check_render_log()

        capability = json.loads(session.msg("-j", "niri-fx-swap-capabilities"))[
            "NiriFxSwapCapabilities"
        ]
        assert capability == {
            "schema": 1,
            "swap_shader": 1,
            "renderer_verified": True,
            "configured": True,
        }, capability
        _, first = client(session, "Mint", "#b7e8db")
        _, second = client(session, "Lilac", "#decef9")
        time.sleep(1.5)
        session.msg("action", "move-column-left")
        capture("ordinary-move", "move")
        time.sleep(1.5)
        session.msg("action", "swap-window-right")
        capture("explicit-swap", "swap")
        session.reload(config("next"))
        capture("reload-retains-active-swap", "swap")
        for window_id in (first, second):
            session.msg("action", "close-window", "--id", str(window_id))
        capture("close-during-swap", "swap")
        time.sleep(1.5)
        client(session, "Mint again", "#b7e8db")
        client(session, "Peach", "#eccdc0")
        time.sleep(1.5)
        session.msg("action", "swap-window-left")
        capture("next-swap-uses-new-material", "next")
        time.sleep(1.5)
        session.reload(config("off"))
        session.msg("action", "swap-window-right")
        capture("swap-off", None)
        session.reload(config(None))
        session.msg("action", "swap-window-left")
        capture("omitted-swap-inherits-move", "move")
        time.sleep(1.5)
        session.reload(config(movement_off=True))
        session.msg("action", "swap-window-right")
        capture("swap-with-move-off", "swap")
        time.sleep(1.5)
        session.msg("action", "focus-column-left")
        session.msg("action", "consume-window-into-column")
        client(session, "Pearl", "#e7e4ed")
        time.sleep(1.5)
        session.msg("action", "swap-window-left")
        capture("stacked-column-swap", "swap")
        evidence["status"] = "passed"
        result.write_text(json.dumps(evidence, indent=2) + "\n")
        print(f"PASS independent native swap; private evidence: {result}")


if __name__ == "__main__":
    main()
