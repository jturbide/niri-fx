#!/usr/bin/env python3
"""Check continuous-fragment ScreenCapture privacy in an owned nested compositor.

The two synthetic accents make clear content and protected content distinguishable.
Every capture requires a visible public control. Direct grim screenshots exercise
ScreenCapture only; they do not establish Output, Screencast or PipeWire privacy.
"""

import argparse
import hashlib
import importlib.util
import json
import signal
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.fragment import FragmentSession, config, experiment
from lib.nested import source_hashes, stop, wait_for
from lib.pointer import VirtualPointer, build_pointer, pointer_protocol
from lib.pointer_scene import click_check, client, geometry, grab, place_floating

# Keep the same fading-accent and redaction classification used by the pointer
# hardening suite. Its target-specific acceptance remains separate from ours.
spec = importlib.util.spec_from_file_location(
    "pointer_hardening", ROOT / "scripts/test-pointer-hardening.py"
)
hardening = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hardening)
CLOSE_MS = 1600
PROTECTED = "#f183c2"
PUBLIC = "#b7e8db"


def privacy_config(policy=None):
    text = config("tear")
    disabled = "    window-close {\n        off\n    }"
    assert text.count(disabled) == 1
    text = text.replace(
        disabled, f'    window-close {{ duration-ms {CLOSE_MS}; curve "linear"; }}', 1
    )
    if policy:
        assert policy in ("screen-capture", "screencast")
        text += (
            'window-rule { match title=r#"^NiriFX pointer / Protected"#; '
            f'block-out-from "{policy}"; }}\n'
        )
    return text


def contract(session):
    value = json.loads(session.msg("-j", "niri-fx-fragment-capabilities"))[
        "NiriFxFragmentCapabilities"
    ]
    assert value["fragment_motion"] == 3, value
    assert all(
        value[key] for key in ("fragment_configured", "fragment_enabled", "renderer_verified")
    ), value
    return value


class Evidence:
    def __init__(self, session, build, case):
        self.path = session.root / "fragment-privacy-acceptance.json"
        self.value = {
            "status": "incomplete",
            "case": case,
            "build": build,
            "capabilities": contract(session),
            "target": "ScreenCapture",
            "scope": "Owned nested compositor, synthetic clients and virtual pointer only",
            "config_sha256": {
                str(policy): hashlib.sha256(privacy_config(policy).encode()).hexdigest()
                for policy in (None, "screen-capture", "screencast")
            },
            "checks": [],
            "limits": [
                "Direct grim captures do not validate Output, Screencast or PipeWire transport.",
                "A screencast-only rule must leave direct ScreenCapture content visible.",
                "Baked close snapshots are checked; fragment springs do not continue through unmap.",
                "No physical desktop or physical device unplug acceptance.",
            ],
            "sources": source_hashes(
                "scripts/test-fragment-privacy.py",
                "scripts/test-pointer-hardening.py",
                "scripts/lib/fragment.py",
                "scripts/lib/nested.py",
                "scripts/lib/pointer.py",
                "scripts/lib/pointer_scene.py",
                "scripts/fixtures/pointer-card.qml",
                "niri_fx/fragment_motion.py",
                "niri_fx/effects.py",
                "niri_fx/shaders/fragment-motion.glsl",
            ),
        }
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.value, indent=2) + "\n")

    def record(self, check):
        self.value["checks"].append(check)
        self.save()
        return check

    def finish(self):
        self.value["status"] = "passed"
        self.save()


def capture(session, evidence, name, *, hidden=False, absent=False, **extra):
    path = session.capture(name)
    counts = hardening.colors(path)
    record = evidence.record({"phase": name, "path": str(path), "counts": counts, **extra})
    assert counts["public"] > 10000, (name, "missing public positive control", counts)
    if hidden or absent:
        assert counts["protected"] == 0, (name, "protected accent leaked", counts)
    else:
        assert counts["protected"] > 10000, (name, "missing visible protected control", counts)
    if hidden and not absent:
        assert counts["redaction"] > 10000, (name, "missing redaction surface", counts)
    return path, record


def fragment_proof(session, evidence, primary, name):
    """Require actual transparent breakup inside the moving source rectangle.

    Merely verifying shader selection or comparing translated windows would not
    show that the continuous mesh was active when the policy changed. The solid
    fixture contains no output-background pixels inside this region at rest.
    """
    from PIL import Image

    bounds = geometry(session, primary)
    path, record = capture(session, evidence, name)
    x, y, width, height = bounds
    with Image.open(path) as image:
        crop = image.convert("RGB").crop(
            tuple(round(v) for v in (x + 30, y + 110, x + width - 30, y + height - 30))
        )
        holes = sum(
            count
            for count, color in crop.getcolors(crop.width * crop.height)
            if all(abs(a - b) <= 2 for a, b in zip(color, (17, 24, 39), strict=True))
        )
    record["interior_background_pixels"] = holes
    record["geometry"] = bounds
    evidence.save()
    assert holes > 120, (name, "continuous fragment breakup not observed", holes)
    return record


def accepted_grab(session, pointer, primary, label="Protected"):
    log = session.root / (label + ".log")
    before = log.read_text().count("NIRIFX_MOVE_REQUEST true")
    point = grab(session, pointer, primary)
    wait_for(
        lambda: log.read_text().count("NIRIFX_MOVE_REQUEST true") > before,
        "accepted owned client move request",
    )
    return point


def cards(session):
    process, primary = client(session, "Protected", PROTECTED)
    _, secondary = client(session, "Public", PUBLIC)
    place_floating(session, primary, x=60, y=140)
    place_floating(session, secondary, x=860, y=140)
    time.sleep(2.15)
    session.focus()
    return process, primary, secondary


def closed(session, primary):
    wait_for(lambda: all(w["id"] != primary for w in session.windows()), "closed synthetic client")


def settled_close(session, evidence, secondary, name):
    time.sleep(CLOSE_MS / 1000 + 0.2)
    _, record = capture(session, evidence, name, absent=True)
    assert record["counts"]["redaction"] < 10000, (name, "retained closing snapshot", record)
    assert {item["id"] for item in session.windows()} == {secondary}
    return record


def privacy(binary, build, protocol, policy):
    hidden = policy == "screen-capture"
    with FragmentSession(privacy_config(), binary=binary) as session:
        evidence = Evidence(
            session, build, {"kind": "dynamic-rules-and-baked-close", "policy": policy}
        )
        helper = build_pointer(session.root / "pointer", protocol)
        _, primary, secondary = cards(session)
        with VirtualPointer(session, helper) as pointer:
            capture(session, evidence, "unblocked-rest")
            start = accepted_grab(session, pointer, primary)
            middle = (start[0] + 100, start[1] + 30)
            pointer.path((start, middle), 0.25)
            fragment_proof(session, evidence, primary, "unblocked-active-fragments")

            session.reload(privacy_config(policy))
            end = (start[0] + 180, start[1] + 60)
            pointer.path((middle, end), 0.15)
            capture(session, evidence, "rule-enabled-during-held-motion", hidden=hidden)
            reverse = (start[0] + 60, start[1] + 20)
            pointer.path((end, reverse), 0.15)
            capture(session, evidence, "rule-retained-on-reversal", hidden=hidden)

            session.reload(privacy_config())
            pointer.path((reverse, middle), 0.15)
            fragment_proof(session, evidence, primary, "rule-removed-during-held-motion")
            session.reload(privacy_config(policy))
            pointer.path((middle, end), 0.15)
            pointer.release()
            released_at = time.monotonic()
            capture(session, evidence, "protected-release-start", hidden=hidden)
            session.reload(privacy_config())
            fragment_proof(session, evidence, primary, "rule-removed-during-release")
            session.reload(privacy_config(policy))
            capture(
                session,
                evidence,
                "rule-enabled-during-release",
                hidden=hidden,
                release_elapsed_ms=(time.monotonic() - released_at) * 1000,
            )
            time.sleep(2.15)
            capture(session, evidence, "protected-rest", hidden=hidden)

            # Start a fresh visible material episode, then protect and unmap it
            # while still moving. Redaction must survive its baked close frame.
            session.reload(privacy_config())
            start = accepted_grab(session, pointer, primary)
            end = (start[0] - 90, start[1] + 20)
            pointer.path((start, end), 0.2)
            fragment_proof(session, evidence, primary, "before-close-active-fragments")
            session.reload(privacy_config(policy))
            pointer.path((end, (end[0] + 40, end[1])), 0.1)
            session.msg("action", "close-window", "--id", str(primary))
            close_at = time.monotonic()
            closed(session, primary)
            for index in range(2):
                _, record = capture(session, evidence, f"baked-close-{index}", hidden=hidden)
                record["close_elapsed_ms"] = (time.monotonic() - close_at) * 1000
                evidence.save()
                assert record["close_elapsed_ms"] < 650, ("late close observation", record)
                time.sleep(0.1)
            pointer.release()
            settled_close(session, evidence, secondary, "after-close")
            click_check(session, pointer, secondary, 1)
            evidence.record({"phase": "surviving-input", "clicks": 1})
        session.check_render_log()
        evidence.finish()
        return str(evidence.path)


def abrupt_exit(binary, build, protocol):
    with FragmentSession(privacy_config(), binary=binary) as session:
        evidence = Evidence(session, build, {"kind": "protected-abrupt-client-exit"})
        helper = build_pointer(session.root / "pointer", protocol)
        process, primary, secondary = cards(session)
        with VirtualPointer(session, helper) as pointer:
            start = accepted_grab(session, pointer, primary)
            end = (start[0] + 120, start[1] + 40)
            pointer.path((start, end), 0.25)
            fragment_proof(session, evidence, primary, "before-abrupt-exit-active-fragments")
            session.reload(privacy_config("screen-capture"))
            pointer.path((end, (end[0] + 40, end[1] + 20)), 0.12)
            capture(session, evidence, "protected-before-abrupt-exit", hidden=True)
            stop(process, signal.SIGKILL)
            closed(session, primary)
            capture(session, evidence, "protected-abrupt-close-snapshot", hidden=True)
            pointer.release()
            settled_close(session, evidence, secondary, "after-abrupt-close")
            click_check(session, pointer, secondary, 1)
            before = geometry(session, secondary)
            start = accepted_grab(session, pointer, secondary, "Public")
            end = (start[0] - 80, start[1] + 40)
            pointer.path((start, end), 0.2)
            pointer.release()
            time.sleep(2.15)
            after = geometry(session, secondary)
            assert abs(after[0] - before[0] + 80) <= 1 and abs(after[1] - before[1] - 40) <= 1, (
                before,
                after,
            )
            click_check(session, pointer, secondary, 2)
            evidence.record(
                {"phase": "surviving-input-and-drag", "clicks": 2, "before": before, "after": after}
            )
        session.check_render_log()
        evidence.finish()
        return str(evidence.path)


def disconnected_pointer(binary, build, protocol):
    with FragmentSession(privacy_config(), binary=binary) as session:
        evidence = Evidence(session, build, {"kind": "protected-removed-pointer-owner"})
        helper = build_pointer(session.root / "pointer", protocol)
        _, primary, secondary = cards(session)
        with VirtualPointer(session, helper, label="removed-pointer") as pointer:
            start = accepted_grab(session, pointer, primary)
            end = (start[0] + 120, start[1] + 40)
            pointer.path((start, end), 0.25)
            fragment_proof(session, evidence, primary, "before-pointer-removal-active-fragments")
            session.reload(privacy_config("screen-capture"))
            pointer.path((end, (end[0] + 40, end[1] + 20)), 0.12)
            capture(session, evidence, "protected-before-pointer-removal", hidden=True)
            stop(pointer.process, signal.SIGKILL)
        before = geometry(session, primary)
        with VirtualPointer(session, helper, label="replacement-pointer") as replacement:
            # Observe unpressed input first: a recovery click could otherwise
            # cancel and conceal a stale grab belonging to the removed device.
            replacement.move(start[0] + 260, start[1] + 100)
            replacement.sync()
            time.sleep(0.3)
            after = geometry(session, primary)
            evidence.record(
                {"phase": "unpressed-replacement-motion", "before": before, "after": after}
            )
            assert before == after, ("removed pointer retained its grab", before, after)
            capture(session, evidence, "protected-after-pointer-removal", hidden=True)
            time.sleep(2.15)
            capture(session, evidence, "protected-pointer-removal-settled", hidden=True)
            session.reload(privacy_config())
            capture(session, evidence, "unblocked-after-pointer-removal")
            click_check(session, replacement, primary, 1)
            click_check(session, replacement, secondary, 1)
            evidence.record(
                {"phase": "replacement-input", "protected_clicks": 1, "public_clicks": 1}
            )
        session.check_render_log()
        evidence.finish()
        return str(evidence.path)


def exercise(protocol, suite):
    binary, build = experiment()
    paths = []
    if suite in ("all", "privacy"):
        for policy in ("screen-capture", "screencast"):
            paths.append(privacy(binary, build, protocol, policy))
    if suite in ("all", "abrupt-exit"):
        paths.append(abrupt_exit(binary, build, protocol))
    if suite in ("all", "disconnect"):
        paths.append(disconnected_pointer(binary, build, protocol))
    print(
        "PASS continuous-fragment ScreenCapture privacy; private evidence:",
        *paths,
        sep="\n",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pointer-protocol", type=Path)
    parser.add_argument(
        "--suite", choices=("all", "privacy", "abrupt-exit", "disconnect"), default="all"
    )
    args = parser.parse_args()
    exercise(pointer_protocol(args.pointer_protocol), args.suite)
