#!/usr/bin/env python3
"""Exercise genuine pointer grabs inside the owned, patched Niri compositor.

Uses synthetic clients and a private virtual pointer. Optional public recordings
show compositor-rendered motion at its actual speed, never browser simulations.
"""

import argparse
import json
import signal
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.movement import experiment
from lib.nested import NestedSession, encode_gif, record, save_clips, source_hashes, stop, wait_for
from lib.pointer import VirtualPointer, build_pointer, pointer_protocol
from lib.pointer_wobble import PRESETS, render_node

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


def config(wobble, *, global_off=False, movement_off=False):
    return (
        BASE
        + "animations {\n"
        + ("    off\n" if global_off else "")
        + "    window-open { duration-ms 180; }\n"
        + "    window-close { duration-ms 180; }\n"
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


def place_floating(session, window_id):
    for action in (
        ("move-window-to-floating",),
        ("set-window-width", "500"),
        ("set-window-height", "500"),
        ("move-floating-window", "--x", "180", "--y", "140"),
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


def exercise(name, protocol, *, capture=False):
    binary, build, _ = experiment(pointer_wobble=True)
    preset = PRESETS[name]
    wobble = preset.wobble
    with NestedSession(config(wobble), binary=binary, width=1280, height=800) as session:
        capabilities = json.loads(session.msg("-j", "niri-fx-pointer-capabilities"))[
            "NiriFxPointerCapabilities"
        ]
        assert capabilities["pointer_wobble"] == 1
        assert capabilities["renderer_verified"]
        assert capabilities["configured"]
        assert capabilities["enabled"]
        helper = build_pointer(session.root / "pointer", protocol)
        _, primary = client(session, preset.name, "#b7e8db")
        place_floating(session, primary)
        checks = []
        with VirtualPointer(session, helper) as pointer:
            click_check(session, pointer, primary, 1)
            initial = geometry(session, primary)
            initial_pointer = (round(initial[0] + initial[2] / 2), round(initial[1] + 52))
            pointer.move(*initial_pointer)
            time.sleep(0.05)
            cycle_before = session.capture("cycle-before")
            recorder, video = record(session, "pointer-" + name, fps=50)
            time.sleep(0.35)
            capture_started = time.monotonic()
            start = grab(session, pointer, primary)
            right = (start[0] + 330, start[1] + 130)
            left = (start[0] + 80, start[1] + 35)
            end = (start[0] + 310, start[1] + 60)
            # A clear final flick leaves an observable release even on a 60 Hz
            # nested host. The settings and playback speed remain unchanged.
            pointer.path((start, right, left, end), 1.05, synchronize=False)
            pointer.release()
            released = session.capture("released")
            time.sleep(0.75)
            settled = session.capture("released-settled")
            time.sleep(0.25)
            capture_ended = time.monotonic()
            frame_timings = [
                sample
                for sample in json.loads(session.msg("-j", "niri-fx-frame-timings"))[
                    "NiriFxFrameTimings"
                ]
                if int(capture_started * 1e9) <= sample["timestamp_ns"] <= int(capture_ended * 1e9)
            ]
            assert len(frame_timings) > 20
            assert all(sample["source"] == "winit-submit" for sample in frame_timings)
            result = geometry(session, primary)

            # Return with real input so the public loop begins and ends on the
            # same settled frame. The first release remains captured separately
            # above; no reversed footage, retiming, or synthetic endpoint reset.
            returning = grab(session, pointer, primary)
            pointer.path((returning, initial_pointer), 0.55, synchronize=False)
            pointer.release()
            time.sleep(0.75)
            cycle_after = session.capture("cycle-after")
            time.sleep(0.15)
            stop(recorder, signal.SIGINT)

            assert max(abs(result[i] - initial[i] - (end[i] - start[i])) for i in (0, 1)) < 3
            assert result[2:] == initial[2:]
            # The endpoint is static while the spring settles. This checks that
            # the native rendered surface continues changing after release.
            release_pixels = changed_pixels(released, settled)
            assert release_pixels > 30, ("No visible release deformation", release_pixels)
            checks.append(
                {
                    "case": "floating-reversals-release",
                    "changed_pixels": release_pixels,
                    "geometry": result,
                }
            )
            assert geometry(session, primary) == initial
            cycle_pixels = changed_pixels(cycle_before, cycle_after)
            assert cycle_pixels < 30, ("Loop did not reconstruct its initial surface", cycle_pixels)
            checks.append(
                {"case": "floating-round-trip", "changed_pixels": cycle_pixels, "geometry": initial}
            )
            click_check(session, pointer, primary, 2)

            # An idle held grab must settle without receiving fresh pointer deltas.
            start = grab(session, pointer, primary)
            end = (start[0] - 120, start[1] + 30)
            pointer.path((start, end), 0.2)
            active = session.capture("held-active")
            time.sleep(1.0)
            idle = session.capture("held-idle")
            time.sleep(0.3)
            quiet = session.capture("held-quiet")
            assert changed_pixels(active, idle) > 30
            assert changed_pixels(idle, quiet) < 30
            pointer.release()
            checks.append({"case": "idle-held-grab-settles"})

            # Regrab the same surface while the previous release still has momentum.
            start = grab(session, pointer, primary)
            end = (start[0] + 60, start[1] - 50)
            pointer.path((start, end), 0.25)
            pointer.release()
            start = grab(session, pointer, primary)
            pointer.path((start, (start[0] - 60, start[1] + 50)), 0.25)
            pointer.release()
            time.sleep(1.1)
            click_check(session, pointer, primary, 3)
            checks.append({"case": "release-regrab-input"})

            _, secondary = client(session, "Companion", "#d6c5ef")
            session.msg("action", "move-window-to-tiling", "--id", str(primary))
            time.sleep(1)
            ids = {primary, secondary}
            start = grab(session, pointer, primary)
            # Pinned Niri detaches tiled grabs after 256 logical pixels. An
            # excursion below that threshold tests its initial rubberband only.
            direction = -1 if start[0] > session.width / 2 else 1
            excursion = (start[0] + direction * 340, start[1] + 90)
            # A horizontal titlebar gesture intentionally scrolls Niri's
            # viewport. Begin vertically to request its native window move.
            pointer.path((start, (start[0], start[1] + 30), excursion), 0.45)
            assert window(session, primary)["layout"]["pos_in_scrolling_layout"] is None
            session.capture("tiled-detached")
            pointer.path((excursion, start), 0.4)
            pointer.release()
            time.sleep(1.2)
            assert {w["id"] for w in session.windows()} == ids
            assert not any(w["is_floating"] for w in session.windows())
            click_check(session, pointer, primary, 4)
            checks.append({"case": "tiled-drag-layout-input"})

            # Reload each supported disable path while a live grab owns the tile.
            place_floating(session, primary)
            for label, disabled in (
                ("omitted", config(None)),
                ("strength-zero", config(replace(wobble, strength=0))),
                ("movement-off", config(wobble, movement_off=True)),
                ("animations-off", config(wobble, global_off=True)),
            ):
                start = grab(session, pointer, primary)
                pointer.path((start, (start[0] + 30, start[1] + 15)), 0.2)
                session.reload(disabled)
                disabled_capabilities = json.loads(
                    session.msg("-j", "niri-fx-pointer-capabilities")
                )["NiriFxPointerCapabilities"]
                assert not disabled_capabilities["enabled"]
                pointer.release()
                time.sleep(0.6)
                assert {w["id"] for w in session.windows()} == ids
                session.check_render_log()
                checks.append({"case": "disable-during-grab", "mode": label})
                session.reload(config(wobble))

            # Client destruction cancels the grab; input must still reach a survivor.
            start = grab(session, pointer, primary)
            pointer.path((start, (start[0] + 60, start[1] + 30)), 0.25)
            session.msg("action", "close-window", "--id", str(primary))
            time.sleep(0.1)
            pointer.release()
            wait_for(
                lambda: [w["id"] for w in session.windows()] == [secondary], "closed grabbed client"
            )
            time.sleep(0.5)
            click_check(session, pointer, secondary, 1)
            checks.append({"case": "close-cancels-grab-survivor-input"})
            session.check_render_log()
            evidence = {
                "preset": name,
                "wobble": asdict(wobble),
                "capabilities": capabilities,
                "checks": checks,
                "pointer_acknowledgements": pointer.timings,
                "native_frame_timings": frame_timings,
                "native_frame_timing_scope": "First outward drag, reversals and release settle; excludes return drag. Nested winit submission timestamps include idle holds and recording load, not physical scanout.",
                "timing_scope": "Motion measures local Wayland socket flush acknowledgement; button and sync commands measure server-roundtrip acknowledgement. Native paths include an ordered dispatch barrier before assertions. Neither measures input-to-photon latency.",
                "revision": build["revision"],
                "patch_sha256": build["patch_sha256"],
                "pointer_patch_sha256": build["pointer_patch_sha256"],
                "recorded_workload": "Floating drag with two direction reversals and a final flick, first release settle, genuine return drag and settled endpoint; input counter unchanged.",
            }
            (session.root / "checks.json").write_text(json.dumps(evidence, indent=2) + "\n")
            if capture:
                dest = ROOT / "docs/gifs" / f"native-pointer-{name}.gif"
                encode_gif(video, dest, width=800, fps=50, colors=64)
                save_clips(
                    [
                        {
                            "name": f"native-pointer-{name}",
                            "file": str(dest.relative_to(ROOT)),
                            "title": f"{preset.name} pointer drag",
                            "mode": "pointer",
                            "pointer_preset": name,
                            "config_source": f"examples/experimental/pointer-wobble-{name}.kdl",
                            "pointer_wobble": asdict(wobble),
                            "workload": "Floating drag, reversals, final flick, release settle, return drag and settled loop endpoint",
                            "bytes": dest.stat().st_size,
                            "fps": 50,
                            "width": 800,
                            "colors": 64,
                            "backend": "pinned patched Niri nested winit; virtual pointer and synthetic client",
                            "revision": build["revision"],
                            "patch_sha256": build["patch_sha256"],
                            "pointer_patch_sha256": build["pointer_patch_sha256"],
                            "sources": source_hashes(
                                "scripts/fixtures/pointer-card.qml",
                                "scripts/fixtures/pointer.c",
                                "scripts/lib/pointer.py",
                                "scripts/lib/pointer_wobble.py",
                                "scripts/test-pointer-wobble.py",
                                f"examples/experimental/pointer-wobble-{name}.kdl",
                            ),
                            "checks": [check["case"] for check in checks],
                        }
                    ]
                )
        print(f"PASS pointer {name}; evidence: {session.root}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pointer-protocol",
        type=Path,
        help="Override installed or build-cached wlr virtual pointer protocol XML",
    )
    parser.add_argument("--preset", choices=PRESETS, default="rubber-sheet")
    parser.add_argument("--all", action="store_true", help="Exercise all three pointer styles")
    parser.add_argument("--record", action="store_true", help="Publish checked native pointer GIFs")
    args = parser.parse_args()
    try:
        protocol = pointer_protocol(args.pointer_protocol)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    for name in PRESETS if args.all else (args.preset,):
        exercise(name, protocol, capture=args.record)


if __name__ == "__main__":
    main()
