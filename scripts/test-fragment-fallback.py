#!/usr/bin/env python3
"""Verify real GLSL failure preserves ordinary drag routing in an owned session.

The marked shader below passes KDL validation and ordinary movement compilation,
but deliberately fails the mesh compilation. Metadata alone cannot authorize the
fragment path. A working reload must recover without restarting the compositor.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.fragment import FragmentSession, config, experiment
from lib.nested import source_hashes, wait_for
from lib.pointer import VirtualPointer, build_pointer, pointer_protocol
from lib.pointer_scene import changed_pixels, click_check, client, grab, window

FAILURE = "NIRIFX_EXPECTED_INVALID_FRAGMENT_MESH"


def broken_config():
    text = config("tear")
    marker = "#ifdef NIRIFX_FRAGMENT_MESH\n"
    assert text.count(marker) == 1
    return text.replace(marker, marker + f"#error {FAILURE}\n", 1)


def capability(session, configured):
    value = json.loads(session.msg("-j", "niri-fx-fragment-capabilities"))[
        "NiriFxFragmentCapabilities"
    ]
    assert value["fragment_motion"] == 3 and value["renderer_verified"], value
    assert value["fragment_configured"] == configured, value
    assert value["fragment_enabled"] == configured, value
    return value


def accepted_grab(session, pointer, primary):
    log = session.root / "Shader fallback.log"
    before = log.read_text().count("NIRIFX_MOVE_REQUEST true")
    point = grab(session, pointer, primary)
    wait_for(
        lambda: log.read_text().count("NIRIFX_MOVE_REQUEST true") > before,
        "owned client move request",
    )
    return point


def routing(session, pointer, primary, records, *, enabled, label):
    observation = {"phase": label}
    records.append(observation)
    time.sleep(2.15)
    before = session.capture(label + "-before")
    start = accepted_grab(session, pointer, primary)
    time.sleep(0.6)
    pressed = session.capture(label + "-pressed")
    difference = changed_pixels(before, pressed)
    observation["press_changed_pixels"] = difference
    assert difference > 120 if enabled else difference == 0, (label, difference)
    pointer.move(start[0], start[1] + 9)
    pointer.sync()
    time.sleep(0.12)
    detached = window(session, primary)["layout"]["pos_in_scrolling_layout"] is None
    observation["detached_at_9px"] = detached
    assert detached == enabled, (label, "9px gesture changed input routing", detached)
    if not enabled:
        # The ordinary Niri tiled pull still works beyond its separate 256px
        # threshold. A failed effect must not leave the window unmovable.
        pointer.path(((start[0], start[1] + 9), (start[0], start[1] + 285)), 0.4)
        wait_for(
            lambda: window(session, primary)["layout"]["pos_in_scrolling_layout"] is None,
            "ordinary tiled pull with failed fragment shader",
        )
    pointer.move(*start)
    pointer.release()
    time.sleep(2.15)
    assert window(session, primary)["layout"]["pos_in_scrolling_layout"] is not None
    observation["returned_to_layout"] = True


def exercise(protocol):
    binary, build = experiment()
    with FragmentSession(broken_config(), binary=binary) as session:
        report = {
            "scope": "Owned nested Output and real GLSL compiler; synthetic client input only",
            "build": build,
            "checks": [],
            "sources": source_hashes(
                "scripts/test-fragment-fallback.py",
                "scripts/lib/fragment.py",
                "scripts/lib/pointer_scene.py",
                "scripts/fixtures/pointer-card.qml",
                "niri_fx/fragment_motion.py",
            ),
        }
        evidence = session.root / "fragment-fallback-acceptance.json"
        try:
            _, primary = client(session, "Shader fallback", "#b7e8db")
            helper = build_pointer(session.root / "pointer", protocol)
            with VirtualPointer(session, helper) as pointer:
                for label, enabled in (
                    ("invalid-startup", False),
                    ("valid-reload", True),
                    ("invalid-reload", False),
                ):
                    if label != "invalid-startup":
                        session.reload(config("tear") if enabled else broken_config())
                    capability(session, enabled)
                    routing(
                        session, pointer, primary, report["checks"], enabled=enabled, label=label
                    )
                    click_check(session, pointer, primary, len(report["checks"]))

                session.reload(config("tear"))
                capability(session, True)
                routing(
                    session,
                    pointer,
                    primary,
                    report["checks"],
                    enabled=True,
                    label="recovered-again",
                )
                click_check(session, pointer, primary, 4)

            log = (session.root / "niri.log").read_text()
            failures = [line for line in log.splitlines() if "error compiling" in line.lower()]
            assert len(failures) >= 2, "The deliberately invalid shader never reached the compiler"
            assert all("error compiling continuous fragment mesh" in line for line in failures)
            # Smithay logs the deliberate #error at ERROR severity before Niri
            # records the failed mesh compilation. Allow only that exact tagged
            # compiler diagnostic; unrelated renderer failures must still fail.
            expected = re.compile(
                r"ERROR smithay::backend::renderer::gles::shaders: "
                r"\[GL\] [^\r\n]*\b" + FAILURE + r"$"
            )
            errors = [
                line
                for line in log.splitlines()
                if re.match(r"^\S+\s+ERROR\s", line)
                or re.search(r"panicked at|error linking", line, re.I)
            ]
            unexpected = [line for line in errors if not expected.search(line)]
            report["unexpected_errors"] = unexpected
            assert not unexpected, unexpected
            assert len(errors) == len(failures), (errors, failures)
            report["expected_compilation_failures"] = len(failures)
            report["passed"] = True
        finally:
            # A failed assertion preserves prior observations as failed evidence.
            report.setdefault("passed", False)
            evidence.write_text(json.dumps(report, indent=2) + "\n")
            print(f"Evidence: {evidence}", flush=True)
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pointer-protocol", type=Path)
    args = parser.parse_args()
    report = exercise(pointer_protocol(args.pointer_protocol))
    print(f"Passed {len(report['checks'])} shader-fallback cases")


if __name__ == "__main__":
    main()
