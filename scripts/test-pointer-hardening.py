#!/usr/bin/env python3
"""Check native pointer privacy and interrupted clients in owned nested sessions.

Direct grim captures use ScreenCapture. The optional --output-targets probe uses
two nested compositors to observe Output and the debug Screencast target without
reading the user's desktop or clipboard. It is not a PipeWire transport test.
"""

import argparse
import json
import os
import shutil
import signal
import sys
import time
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.movement import experiment
from lib.nested import NestedSession, source_hashes, stop, wait_for
from lib.pointer import VirtualPointer, build_pointer, pointer_protocol
from lib.pointer_scene import click_check as click
from lib.pointer_scene import client, config, geometry, grab, place_floating, window
from lib.pointer_wobble import PRESETS

WOBBLE = PRESETS["rubber-sheet"].wobble
PROTECTED = "#f183c2"
PUBLIC = "#b7e8db"


def colors(path):
    """Count two distinct synthetic accents, including their fading close frames.

    Channel ordering survives blending into the neutral background. The minimum
    separation rejects that background and the redaction surface. Counts, rather
    than fixed coordinates, tolerate the actual spring and closing transform.
    """
    from PIL import Image

    counts = {"protected": 0, "public": 0, "redaction": 0}
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        for count, (r, g, b) in rgb.getcolors(rgb.width * rgb.height):
            if r - g > 25 and b - g > 15 and r - b > 15:
                counts["protected"] += count
            if g - r > 20 and g - b > 8 and b - r > 15:
                counts["public"] += count
            if r < 9 and g < 13 and b < 20:
                counts["redaction"] += count
    return counts


def privacy_config(policy=None, preview=False):
    text = config(WOBBLE, close_ms=1600)
    if policy:
        text += (
            'window-rule { match title=r#"^NiriFX pointer / Protected"#; '
            f'block-out-from "{policy}"; }}\n'
        )
    if preview:
        text += 'debug { preview-render "screencast"; }\n'
    return text


def capture_pair(parent, session, name, *, output_hidden, capture_hidden):
    counts = {}
    targets = [("screen_capture", capture_hidden)]
    if parent is not None:
        counts["output"] = colors(parent.capture(name + "-output"))
        targets.append(("output", output_hidden))
    counts["screen_capture"] = colors(session.capture(name + "-capture"))
    for target, hidden in targets:
        actual = counts[target]
        # A public companion is the positive control for every capture. A blank
        # or stale empty output cannot accidentally satisfy a privacy assertion.
        assert actual["public"] > 10000, (name, target, "missing public control", actual)
        assert actual["protected"] == 0 if hidden else actual["protected"] > 10000, (
            name,
            target,
            "unexpected protected visibility",
            actual,
        )
    return counts


def privacy(parent, binary, protocol, policy, preview):
    with patch.dict(os.environ, parent.env if parent else os.environ.copy(), clear=True):
        child = NestedSession(
            privacy_config(preview=preview), binary=binary, width=1280, height=800
        )
    with child as session:
        helper = build_pointer(session.root / "pointer", protocol)
        _, primary = client(session, "Protected", PROTECTED)
        _, secondary = client(session, "Public", PUBLIC)
        place_floating(session, primary, x=60)
        place_floating(session, secondary, x=740)
        records = []
        with VirtualPointer(session, helper) as pointer:
            counts = capture_pair(
                parent, session, "baseline", output_hidden=False, capture_hidden=False
            )
            records.append({"phase": "unblocked-control", "counts": counts})
            start = grab(session, pointer, primary)
            pointer.path((start, (start[0] + 90, start[1] + 40)), 0.2)
            session.reload(privacy_config(policy, preview))
            hidden_output = preview
            hidden_capture = policy == "screen-capture"
            for index, delta in enumerate(((150, 90), (30, 20), (140, 70))):
                pointer.move(start[0] + delta[0], start[1] + delta[1])
                pointer.sync()
                counts = capture_pair(
                    parent,
                    session,
                    f"protected-drag-{index}",
                    output_hidden=hidden_output,
                    capture_hidden=hidden_capture,
                )
                records.append({"phase": "protected-drag", "counts": counts})
            # Dynamic rules must also recover clear content without ending the
            # grab or reusing a redacted texture in the wrong render target.
            session.reload(privacy_config(preview=preview))
            counts = capture_pair(
                parent, session, "unblocked-drag", output_hidden=False, capture_hidden=False
            )
            records.append({"phase": "unblocked-during-grab", "counts": counts})
            assert geometry(session, primary)[:2] != (60, 140), "Grab did not move the fixture"
            session.reload(privacy_config(policy, preview))
            pointer.move(start[0] + 100, start[1] + 50)
            pointer.sync()
            session.msg("action", "close-window", "--id", str(primary))
            wait_for(
                lambda: all(w["id"] != primary for w in session.windows()),
                "closed protected client",
            )
            counts = capture_pair(
                parent,
                session,
                "protected-close",
                output_hidden=hidden_output,
                capture_hidden=hidden_capture,
            )
            closing = {"phase": "protected-close-snapshot", "counts": counts}
            records.append(closing)
            pointer.release()
            time.sleep(1.7)

            def after_close():
                # Child submission and the parent's presentation are separate
                # frame callbacks. Poll both targets instead of assuming a wall
                # clock sleep also presented the final child buffer upstream.
                capture = colors(session.capture("after-close-capture"))
                targets = {"screen_capture": capture}
                if parent is not None:
                    targets["output"] = colors(parent.capture("after-close-output"))
                return (
                    targets
                    if all(
                        value["protected"] == 0 and value["redaction"] < 10000
                        for value in targets.values()
                    )
                    else None
                )

            settled = wait_for(after_close, "closing snapshot disappears on observed targets")
            for target in settled:
                hidden = hidden_output if target == "output" else hidden_capture
                assert settled[target]["protected"] == 0
                assert settled[target]["public"] > 10000
                if hidden:
                    # When both targets hide content, absence of the accent
                    # alone could pass after the animation ended. The black
                    # snapshot must still exist and then disappear on settle.
                    assert counts[target]["redaction"] - settled[target]["redaction"] > 10000, (
                        target,
                        "No redacted closing snapshot",
                        counts,
                        settled,
                    )
            closing["settled_counts"] = settled
            click(session, pointer, secondary, 1)
        session.check_render_log()
        return {
            "policy": policy,
            "output_target": ("Screencast" if preview else "Output") if parent else None,
            "checks": records,
        }


def client_exit(binary, protocol, tiled):
    with NestedSession(config(WOBBLE), binary=binary, width=1280, height=800) as session:
        helper = build_pointer(session.root / "pointer", protocol)
        process, primary = client(session, "Abrupt exit", PROTECTED)
        _, secondary = client(session, "Survivor", PUBLIC)
        if not tiled:
            place_floating(session, primary)
        initial = geometry(session, primary)
        with VirtualPointer(session, helper) as pointer:
            start = grab(session, pointer, primary)
            direction = -1 if start[0] > session.width / 2 else 1
            end = (start[0] + direction * (340 if tiled else 100), start[1] + 60)
            pointer.path((start, (start[0], start[1] + 30), end), 0.4)
            assert window(session, primary)["layout"]["pos_in_scrolling_layout"] is None
            if not tiled:
                actual = geometry(session, primary)
                assert abs(actual[0] - initial[0]) > 50 and actual[1] - initial[1] > 30
            stop(process, signal.SIGKILL)
            wait_for(
                lambda: all(w["id"] != primary for w in session.windows()), "killed grabbed client"
            )
            pointer.release()
            time.sleep(0.8)
            assert [w["id"] for w in session.windows()] == [secondary]
            click(session, pointer, secondary, 1)
            place_floating(session, secondary)
            before = geometry(session, secondary)
            start = grab(session, pointer, secondary)
            end = (start[0] + 80, start[1] + 45)
            pointer.path((start, end), 0.2)
            actual = geometry(session, secondary)
            assert actual[0] - before[0] > 50 and actual[1] - before[1] > 25
            pointer.path((end, start), 0.2)
            pointer.release()
            time.sleep(0.8)
            assert geometry(session, secondary) == before
            click(session, pointer, secondary, 2)
        session.check_render_log()
    return {"layout": "tiled" if tiled else "floating", "survivor_clicks": 2, "result": "passed"}


def disconnected_pointer(binary, protocol, enabled):
    with NestedSession(
        config(WOBBLE if enabled else None), binary=binary, width=1280, height=800
    ) as session:
        helper = build_pointer(session.root / "pointer", protocol)
        _, primary = client(session, "Disconnect", PUBLIC)
        place_floating(session, primary)
        initial = geometry(session, primary)
        with VirtualPointer(session, helper) as pointer:
            start = grab(session, pointer, primary)
            pointer.path((start, (start[0] + 80, start[1] + 40)), 0.2)
            actual = geometry(session, primary)
            assert actual[0] - initial[0] > 50 and actual[1] - initial[1] > 20, (
                "Initial pointer did not grab"
            )
            stop(pointer.process, signal.SIGKILL)
        shutil.copyfile(session.root / "pointer.log", session.root / "disconnected-pointer.log")
        before = geometry(session, primary)
        with VirtualPointer(session, helper) as replacement:
            # No press: this must happen before any recovery click, which could
            # otherwise hide a stale compositor grab from the disconnected device.
            replacement.move(start[0] + 180, start[1] + 80)
            replacement.sync()
            time.sleep(0.4)
            after = geometry(session, primary)
            retained_grab = before[:2] != after[:2]
            replacement.press()
            replacement.release()
            time.sleep(0.8)
            click(session, replacement, primary, 1)
        session.check_render_log()
    return {
        "pointer_effect_enabled": enabled,
        "unpressed_motion_moved_window": retained_grab,
        "replacement_click_recovered": True,
    }


def overlapping_pointers(binary, protocol, enabled):
    """Observe one shared seat with two independent virtual-pointer clients.

    Distinguish a lost grab owner from an idle device, including an idle device
    with an earlier grab. Paired same-button events are observations: a Wayland
    seat has one pointer, so continuation alone does not prove device ownership.
    """
    records = []
    for scenario in (
        "idle-b-destroyed",
        "owner-a-destroyed",
        "former-owner-a-destroyed",
        "same-button-a-released",
        "same-button-a-destroyed",
    ):
        with NestedSession(
            config(WOBBLE if enabled else None), binary=binary, width=1280, height=800
        ) as session:
            helper = build_pointer(session.root / "pointer", protocol)
            _, primary = client(session, "Two pointers", PUBLIC)
            place_floating(session, primary)
            initial = geometry(session, primary)
            with (
                VirtualPointer(session, helper, label="pointer-a") as first,
                VirtualPointer(session, helper, label="pointer-b") as second,
            ):
                start = grab(session, first, primary)
                first.move(start[0] + 80, start[1] + 40)
                first.sync()
                time.sleep(0.2)
                position = geometry(session, primary)
                assert position[0] - initial[0] > 50, "Initial A grab did not move"

                survivor = first if scenario == "idle-b-destroyed" else second
                if scenario == "former-owner-a-destroyed":
                    first.release()
                    time.sleep(0.2)
                    start = grab(session, second, primary)
                    second.move(start[0] + 40, start[1] + 20)
                    second.sync()
                    time.sleep(0.2)
                    assert geometry(session, primary)[0] - position[0] > 25, "B grab did not start"
                elif scenario.startswith("same-button"):
                    second.press()

                before = geometry(session, primary)
                if scenario == "same-button-a-released":
                    first.release()
                else:
                    removed = second if scenario == "idle-b-destroyed" else first
                    stop(removed.process, signal.SIGKILL)
                # The surviving client's barrier and delay let destruction be
                # dispatched before measuring motion, without a recovery click.
                survivor.sync()
                time.sleep(0.2)
                survivor.move(start[0] + 160, start[1] + 80)
                survivor.sync()
                time.sleep(0.3)
                after = geometry(session, primary)
                continued = before[:2] != after[:2]
                record = {
                    "scenario": scenario,
                    "survivor_button_held": survivor.pressed,
                    "motion_moved_window": continued,
                    "delta": [round(after[i] - before[i], 3) for i in (0, 1)],
                }
                if scenario == "owner-a-destroyed":
                    record["expected_motion_moved_window"] = False
                elif scenario in ("idle-b-destroyed", "former-owner-a-destroyed"):
                    record["expected_motion_moved_window"] = True
                if "expected_motion_moved_window" in record:
                    record["passed"] = continued == record["expected_motion_moved_window"]

                # End any real or stale shared-seat press, then prove input
                # recovery using the synthetic client's own click counter.
                if not survivor.pressed:
                    survivor.press()
                survivor.release()
                time.sleep(0.3)
                settled = geometry(session, primary)
                survivor.move(start[0] + 200, start[1] + 100)
                survivor.sync()
                time.sleep(0.2)
                record["release_stopped_window"] = geometry(session, primary)[:2] == settled[:2]
                assert record["release_stopped_window"], "Surviving release did not end grab"
                # Reposition only after the release oracle: a retained grab can
                # have dragged the fixture's click target below the owned output.
                place_floating(session, primary)
                click(session, survivor, primary, 1)
                record["survivor_click_recovered"] = True
                print("OVERLAP: " + json.dumps(record), flush=True)
            session.check_render_log()
            records.append(record)
    return {
        "pointer_effect_enabled": enabled,
        "scenarios": records,
        "failed_controls": [
            record["scenario"] for record in records if record.get("passed") is False
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pointer-protocol", type=Path)
    parser.add_argument(
        "--output-targets",
        action="store_true",
        help="Also probe Output/Screencast through a second compositor; fails if its closing frames stay stale",
    )
    parser.add_argument(
        "--report", type=Path, help="Write a sanitized JSON record (raw captures stay in artifacts)"
    )
    args = parser.parse_args()
    protocol = pointer_protocol(args.pointer_protocol)
    binary, build, _ = experiment(pointer_wobble=True)
    results = []
    if args.output_targets:
        with NestedSession(config(None), binary=binary, width=1440, height=1000) as parent:
            for policy in ("screen-capture", "screencast"):
                for preview in (False, True):
                    results.append(privacy(parent, binary, protocol, policy, preview))
                    print(f"PASS privacy {policy}, output override={preview}", flush=True)
            parent.check_render_log()
    else:
        for policy in ("screen-capture", "screencast"):
            results.append(privacy(None, binary, protocol, policy, False))
            print(f"PASS ScreenCapture privacy {policy}", flush=True)
    exits = [client_exit(binary, protocol, tiled) for tiled in (False, True)]
    print("PASS abrupt grabbed-client exit, floating and tiled", flush=True)
    disconnects = [disconnected_pointer(binary, protocol, enabled) for enabled in (False, True)]
    baseline, enabled = disconnects
    assert baseline["unpressed_motion_moved_window"] == enabled["unpressed_motion_moved_window"], (
        disconnects
    )
    limitation = baseline["unpressed_motion_moved_window"]
    print(
        "KNOWN LIMIT: disconnected pointer retains a held grab with effects on and off"
        if limitation
        else "PASS held-pointer disconnect",
        flush=True,
    )
    evidence = {
        "schema": 1,
        "date": date.today().isoformat(),
        "revision": build["revision"],
        "patches": source_hashes(
            "experimental/niri-movement.patch", "experimental/niri-pointer-wobble.patch"
        ),
        "sources": source_hashes(
            "scripts/test-pointer-hardening.py",
            "scripts/lib/pointer_scene.py",
            "scripts/lib/nested.py",
            "scripts/lib/pointer.py",
            "niri_fx/pointer.py",
            "scripts/fixtures/pointer.c",
            "scripts/fixtures/pointer-card.qml",
        ),
        "scope": "Owned nested winit compositors; synthetic clients; real virtual-pointer grabs. ScreenCapture uses grim.",
        "output_target_probe": args.output_targets,
        "limits": [
            "Not a PipeWire transport or portal test.",
            "No physical input devices, monitor hotplug, mixed scales or graphics reset acceptance.",
            "Effect-disabled comparison uses the same pinned patched executable with pointer deformation omitted.",
            "Opaque card fixtures do not cover popup or blurred-background privacy combinations.",
            "Without --output-targets, Output and Screencast rendering are not tested.",
        ],
        "privacy": results,
        "abrupt_client_exit": exits,
        "pointer_disconnect": disconnects,
        "known_limitations": [
            "Destroying a virtual pointer with a held button retains the grab in both effect-enabled and effect-disabled runs. A replacement press/release recovers input. Device ownership and disconnect cleanup remain unresolved."
        ]
        if limitation
        else [],
    }
    if args.report:
        args.report.write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    main()
