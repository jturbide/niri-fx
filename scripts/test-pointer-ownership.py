#!/usr/bin/env python3
"""Require device-owned pointer cleanup in owned nested synthetic sessions.

The baseline diagnostic remains unchanged. This acceptance gate turns its paired
same-button observations into strict first-press/final-release requirements and
checks per-device binding suppression across a configuration reload.
"""

import argparse
import hashlib
import importlib.util
import json
import signal
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.movement import experiment
from lib.nested import NestedSession, source_hashes, stop, wait_for
from lib.pointer import VirtualPointer, build_pointer, pointer_protocol
from lib.pointer_scene import click_check, client, config, geometry, grab, place_floating

spec = importlib.util.spec_from_file_location(
    "ownership_baseline", ROOT / "scripts/test-native-baseline.py"
)
baseline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(baseline)
hardening = baseline.hardening


def checked_binary(binary, expected, *, unmodified=False, pointer_wobble=False):
    if unmodified:
        if binary is not None or expected is not None or pointer_wobble:
            raise ValueError("The unmodified baseline cannot use prototype or pointer options")
        executable, build = baseline.baseline()
    elif binary is None and expected is None:
        executable, build, _ = experiment(pointer_wobble=pointer_wobble)
    else:
        if binary is None or expected is None:
            raise ValueError("Explicit binary requires its expected SHA-256")
        executable = binary.resolve()
        digest = hashlib.sha256(executable.read_bytes()).hexdigest()
        if digest != expected:
            raise ValueError("Executable changed from the expected SHA-256")
        build = {
            "scope": "explicit candidate; canonical patch manifest not asserted",
            "binary_sha256": digest,
        }
    return executable, {key: value for key, value in build.items() if key != "binary"}


def require_ownership(result):
    expected = {
        "idle-b-destroyed": True,
        "owner-a-destroyed": False,
        "former-owner-a-destroyed": True,
        "same-button-a-released": True,
        "same-button-a-destroyed": True,
    }
    records = result["scenarios"]
    assert len(records) == len(expected) and {r["scenario"] for r in records} == set(expected), (
        "Incomplete ownership controls",
        records,
    )
    for record in records:
        record["expected_motion_moved_window"] = expected[record["scenario"]]
        record["passed"] = (
            record["motion_moved_window"] == record["expected_motion_moved_window"]
            and record["release_stopped_window"]
            and record["survivor_click_recovered"]
        )
    result["failed_controls"] = [r["scenario"] for r in records if not r["passed"]]
    assert not result["failed_controls"], result["failed_controls"]


def suppression(binary, protocol, enabled):
    base = config(hardening.WOBBLE if enabled else None)
    with NestedSession(base, binary=binary, width=1280, height=800) as session:
        helper = build_pointer(session.root / "pointer", protocol)
        _, primary = client(session, "Owned suppression", hardening.PUBLIC)
        place_floating(session, primary)
        session.focus()
        with (
            VirtualPointer(session, helper, label="pointer-a") as first,
            VirtualPointer(session, helper, label="pointer-b") as second,
        ):
            session.reload(base + "binds { MouseLeft { focus-window-down; }; }\n")
            initial = geometry(session, primary)
            start = grab(session, first, primary)
            first.move(start[0] + 80, start[1] + 40)
            first.sync()
            time.sleep(0.2)
            assert geometry(session, primary)[:2] == initial[:2], "Bind press reached client"
            session.reload(base)
            # A still owns a consumed LEFT press. B's identical code must reach
            # the client, and removing A must not release B or cancel its grab.
            start = grab(session, second, primary)
            second.move(start[0] + 80, start[1] + 40)
            second.sync()
            wait_for(
                lambda: geometry(session, primary)[0] - initial[0] > 50,
                "unsuppressed B starts its client grab",
            )
            before = geometry(session, primary)
            stop(first.process, signal.SIGKILL)
            second.sync()
            second.move(start[0] + 160, start[1] + 80)
            second.sync()
            wait_for(
                lambda: geometry(session, primary)[0] - before[0] > 50,
                "removing suppressed A preserves B grab",
            )
            second.release()
            time.sleep(0.3)
            settled = geometry(session, primary)
            second.move(start[0] + 200, start[1] + 100)
            second.sync()
            time.sleep(0.2)
            assert geometry(session, primary)[:2] == settled[:2], "B release retained grab"
            place_floating(session, primary)
            click_check(session, second, primary, 1)
        # A newly created resource can press and release normally after the old
        # consumed resource has gone. No cleanup click is sent on its behalf.
        with VirtualPointer(session, helper, label="pointer-recreated") as recreated:
            click_check(session, recreated, primary, 2)
        session.check_render_log()
    return {
        "pointer_effect_enabled": enabled,
        "consumed_a_did_not_grab": True,
        "b_same_button_grab_survived_a_removal": True,
        "b_release_stopped_window": True,
        "b_click_and_recreated_resource_click_recovered": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--binary-sha256")
    parser.add_argument("--unmodified", action="store_true")
    parser.add_argument("--pointer-wobble", action="store_true")
    parser.add_argument("--pointer-protocol", type=Path)
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts/pointer-ownership.json")
    args = parser.parse_args()
    binary, build = checked_binary(
        args.binary,
        args.binary_sha256,
        unmodified=args.unmodified,
        pointer_wobble=args.pointer_wobble,
    )
    protocol = pointer_protocol(args.pointer_protocol)
    report = {
        "schema": 1,
        "date": date.today().isoformat(),
        "build": build,
        "sources": source_hashes(
            "scripts/test-pointer-ownership.py",
            "scripts/test-pointer-hardening.py",
            "scripts/test-native-baseline.py",
            "scripts/lib/nested.py",
            "scripts/lib/pointer.py",
            "scripts/lib/pointer_scene.py",
            "scripts/lib/pointer_wobble.py",
            "niri_fx/pointer.py",
            "scripts/fixtures/pointer.c",
            "scripts/fixtures/pointer-card.qml",
        ),
        "scope": "Owned nested winit sessions; synthetic clients and virtual pointers only.",
        "limits": [
            "No physical unplug, touch or tablet hardware acceptance.",
            "Same-button owners share one logical seat press until the final owner releases.",
            "Native unit tests separately cover distinct button state and keyboard-started grabs.",
        ],
        "overlap": [],
        "suppression": [],
        "passed": False,
    }
    try:
        for enabled in (False, True) if args.pointer_wobble else (False,):
            result = hardening.overlapping_pointers(binary, protocol, enabled)
            report["overlap"].append(result)
            require_ownership(result)
            report["suppression"].append(suppression(binary, protocol, enabled))
        report["passed"] = True
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print("PASS pointer ownership, overlap, suppression and resource replacement", flush=True)


if __name__ == "__main__":
    main()
