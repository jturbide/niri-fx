"""Synthetic pointer scenes shared by native acceptance and capture checks."""

import time

from niri_fx.pointer import render_node

from .nested import ROOT, wait_for

BASE = """layout {
    gaps 24
    default-column-width { fixed 500; }
    center-focused-column "never"
    focus-ring { off; }
    border { off; }
    background-color "#111827"
}
prefer-no-csd
hotkey-overlay { skip-at-startup; }
"""


def config(wobble, *, global_off=False, movement_off=False, close_ms=180):
    return (
        BASE
        + "animations {\n"
        + ("    off\n" if global_off else "")
        + "    window-open { duration-ms 180; }\n"
        + f"    window-close {{ duration-ms {close_ms}; }}\n"
        + "    window-movement {\n"
        + ("        off\n" if movement_off else "")
        + (render_node(wobble) if wobble else "")
        + "    }\n}\n"
    )


def geometry(session, window_id):
    layout = window(session, window_id)["layout"]
    tile = layout["tile_pos_in_workspace_view"]
    offset = layout["window_offset_in_tile"]
    if tile is None:
        # Pinned Niri reports a tiled window's column, but omits its screen
        # coordinates. Locate our own uniquely coloured fixture in an owned
        # screenshot rather than assuming the user's viewport or injecting a
        # click at guessed coordinates. Its inset is exactly 10 logical pixels.
        from PIL import Image, ImageChops

        session.msg("action", "focus-window", "--id", str(window_id))
        time.sleep(0.35)
        image_path = session.capture(f"locate-{window_id}")
        color = tuple(bytes.fromhex(session.fixture_colors[window_id][1:]))
        with Image.open(image_path) as image:
            rgb = image.convert("RGB")
            channels = ImageChops.difference(rgb, Image.new("RGB", image.size, color)).split()
            mask = ImageChops.lighter(
                ImageChops.lighter(channels[0], channels[1]), channels[2]
            ).point(lambda value: 255 if value == 0 else 0)
            bounds = mask.getbbox()
        if bounds is None:
            raise RuntimeError("Synthetic tiled fixture is not visible in the owned output")
        return (bounds[0] - 10, bounds[1] - 10, *layout["window_size"])
    return (*[a + b for a, b in zip(tile, offset, strict=True)], *layout["window_size"])


def client(session, title, color):
    process = session.launch(
        ["qs", "-p", str(ROOT / "scripts/fixtures/pointer-card.qml")],
        title,
        env=session.env | {"NIRIFX_LABEL": title, "NIRIFX_COLOR": color},
        private_bus=True,
    )
    window = wait_for(
        lambda: next(
            (w for w in session.windows() if w["title"].startswith("NiriFX pointer / " + title)),
            None,
        ),
        "synthetic pointer client",
    )
    if not hasattr(session, "fixture_colors"):
        session.fixture_colors = {}
    session.fixture_colors[window["id"]] = color
    return process, window["id"]


def window(session, window_id):
    return next(w for w in session.windows() if w["id"] == window_id)


def place_floating(session, window_id, *, x=180, y=140, width=500, height=500):
    for action in (
        ("move-window-to-floating",),
        ("set-window-width", str(width)),
        ("set-window-height", str(height)),
        ("move-floating-window", "--x", str(x), "--y", str(y)),
    ):
        session.msg("action", action[0], "--id", str(window_id), *action[1:])
    time.sleep(0.8)


def grab(session, pointer, window_id):
    x, y, width, _ = geometry(session, window_id)
    point = (round(x + width / 2), round(y + 52))
    pointer.move(*point)
    time.sleep(0.05)
    pointer.press()
    # Qt handles the press and sends the xdg_toplevel.move request asynchronously.
    time.sleep(0.08)
    return point


def click_check(session, pointer, window_id, expected):
    x, y, width, height = geometry(session, window_id)
    pointer.click(round(x + width / 2), round(y + height - 63))
    wait_for(
        lambda: window(session, window_id)["title"].endswith(f"clicks {expected}"),
        "client input after pointer grab",
    )


def changed_pixels(a, b):
    from PIL import Image, ImageChops

    with Image.open(a) as first, Image.open(b) as second:
        diff = ImageChops.difference(first.convert("RGB"), second.convert("RGB"))
        return sum(
            count for count, color in diff.getcolors(diff.width * diff.height) if max(color) > 8
        )
