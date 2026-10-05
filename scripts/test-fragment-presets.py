#!/usr/bin/env python3
"""Exercise native fragment presets and configuration reloads in an owned session.

The strict ten-case material baseline remains in test-fragment-drag.py. This
focused companion checks preset selection, episode-latched settings and Off
using synthetic content, private configuration and real client move requests.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.fragment import FragmentSession, config, experiment
from lib.nested import source_hashes, wait_for
from lib.pointer import VirtualPointer, build_pointer, pointer_protocol
from lib.pointer_scene import (
    changed_pixels,
    click_check,
    client,
    geometry,
    grab,
    place_floating,
    window,
)

from niri_fx.fragment_motion import PRESETS


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def contract(session, *, enabled=True):
    value = json.loads(session.msg("-j", "niri-fx-fragment-capabilities"))[
        "NiriFxFragmentCapabilities"
    ]
    for key, expected in {
        "schema": 1,
        "fragment_motion": 3,
        "max_deformation": 1024,
        "max_release_ms": 2000,
        "fragment_enabled": enabled,
    }.items():
        assert value.get(key) == expected, value
    if enabled:
        assert value["fragment_configured"] and value["renderer_verified"], value
    return value


def stable(session, label, *, since=None):
    """Sample after the supported release bound, then require a quiet endpoint."""
    deadline = (since if since is not None else time.monotonic()) + 2.15
    time.sleep(max(0, deadline - time.monotonic()))
    first = session.capture(label + "-stable")
    sample_ms = (time.monotonic() - since) * 1000 if since is not None else None
    time.sleep(0.25)
    second = session.capture(label + "-quiet")
    difference = changed_pixels(first, second)
    assert difference < 30, (label, "material did not become stable", difference)
    return first, {"quiet_pixels": difference, "sample_ms": sample_ms}


def shifted(bounds, dx, dy):
    return (bounds[0] + dx, bounds[1] + dy, *bounds[2:])


def window_difference(before, after, before_bounds, after_bounds):
    """Compare material in window coordinates without accepting translation.

    Padding includes the configured held spread. Its comparison also catches
    a retained cloud outside the normal surface after Off or release.
    """
    from PIL import Image, ImageChops

    assert before_bounds[2:] == after_bounds[2:]

    def crop(image, bounds):
        x, y, width, height = bounds
        return image.convert("RGB").crop(
            tuple(round(v) for v in (x - 64, y - 64, x + width + 64, y + height + 64))
        )

    with Image.open(before) as first, Image.open(after) as second:
        difference = ImageChops.difference(crop(first, before_bounds), crop(second, after_bounds))
        return sum(
            count
            for count, color in difference.getcolors(difference.width * difference.height)
            if max(color) > 8
        )


def accepted_grab(session, pointer, primary):
    log = session.root / "Preset lifecycle.log"
    before = log.read_text().count("NIRIFX_MOVE_REQUEST true")
    point = grab(session, pointer, primary)
    wait_for(
        lambda: log.read_text().count("NIRIFX_MOVE_REQUEST true") > before,
        "accepted owned client move request",
    )
    return point


def assert_endpoint(session, primary, expected):
    wait_for(
        lambda: window(session, primary)["layout"]["tile_pos_in_workspace_view"] is not None,
        "released floating geometry",
    )
    actual = geometry(session, primary)
    assert all(abs(a - b) <= 1 for a, b in zip(actual, expected, strict=True)), (actual, expected)
    assert session.compositor.poll() is None
    assert {item["id"] for item in session.windows()} == {primary}
    assert window(session, primary)["is_floating"]
    return actual


class Evidence:
    def __init__(self, session, build, configs):
        self.path = session.root / "fragment-presets-acceptance.json"
        self.value = {
            "status": "incomplete",
            "scope": "Owned nested compositor, synthetic card and virtual pointer only",
            "build": build,
            "config_sha256": {name: digest(value) for name, value in configs.items()},
            "presets": {
                name: {"particles": preset.particles, "settings": asdict(preset.settings)}
                for name, preset in PRESETS.items()
            },
            "checks": [],
            "limits": [
                "No physical desktop or mixed-output acceptance.",
                "Exact same-time pose, velocity and deadline continuity are native state-test gates.",
                "Settings-only held reload keeps the source lattice unchanged.",
            ],
            "sources": source_hashes(
                "scripts/test-fragment-presets.py",
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

    def append(self, check):
        self.value["checks"].append(check)
        self.save()

    def complete(self):
        self.value["status"] = "passed"
        self.save()


def preset_check(session, pointer, primary, name, click_count):
    # Reset placement and finish the old episode before testing an idle reload,
    # including the deliberate density change between curated presets.
    place_floating(session, primary, x=160, y=140)
    before, _ = stable(session, name + "-before-reload")
    initial = geometry(session, primary)
    session.reload(config(name))
    capability = contract(session)
    idle, idle_quiet = stable(session, name + "-idle")
    idle_pixels = changed_pixels(before, idle)
    assert idle_pixels < 30, (name, "idle reload changed resting material", idle_pixels)
    assert_endpoint(session, primary, initial)

    accepted_grab(session, pointer, primary)
    held, held_quiet = stable(session, name + "-press")
    press_pixels = changed_pixels(idle, held)
    assert press_pixels > 120, (name, "press did not expand the preset", press_pixels)
    assert geometry(session, primary) == initial
    pointer.release()
    released_at = time.monotonic()
    released, release_quiet = stable(session, name + "-press-release", since=released_at)
    release_pixels = changed_pixels(idle, released)
    assert release_pixels < 30, (name, "press release did not reconstruct", release_pixels)

    start = accepted_grab(session, pointer, primary)
    endpoint = (start[0] + 220, start[1] + 40)
    pointer.path((start, endpoint), 0.55)
    active = session.capture(name + "-drag-active")
    pointer.release()
    released_at = time.monotonic()
    final, final_quiet = stable(session, name + "-drag-release", since=released_at)
    actual = assert_endpoint(session, primary, shifted(initial, 220, 40))
    active_pixels = changed_pixels(active, final)
    restored_pixels = window_difference(idle, final, initial, actual)
    assert active_pixels > 120, (name, "no visible drag material", active_pixels)
    assert restored_pixels < 30, (name, "drag release changed source content", restored_pixels)
    click_check(session, pointer, primary, click_count)
    session.check_render_log()
    return {
        "case": "preset-press-drag-release",
        "preset": name,
        "capability": capability,
        "idle_reload_pixels": idle_pixels,
        "press_pixels": press_pixels,
        "press_release_pixels": release_pixels,
        "drag_pixels": active_pixels,
        "restored_pixels": restored_pixels,
        "quiet": [idle_quiet, held_quiet, release_quiet, final_quiet],
        "geometry": {"before": initial, "after": actual},
        "input_count": click_count,
    }


def held_reload_check(session, pointer, primary, click_count):
    original = PRESETS["gentle"]
    replacement = PRESETS["cascade"]
    session.reload(config("gentle"))
    place_floating(session, primary, x=160, y=140)
    idle, _ = stable(session, "held-reload-idle")
    initial = geometry(session, primary)
    start = accepted_grab(session, pointer, primary)
    old_held, _ = stable(session, "held-reload-original-spread")
    middle = (start[0] + 120, start[1] + 20)
    end = (start[0] + 220, start[1] + 40)
    pointer.path((start, middle), 0.3)
    session.capture("held-reload-before")
    same_grid = config("cascade", effect=original.effect)
    session.reload(same_grid)
    contract(session)
    pointer.path((middle, end), 0.3)
    session.capture("held-reload-after")
    retained, retained_quiet = stable(session, "held-reload-retained-spread")
    expected = shifted(initial, 220, 40)
    retained_pixels = window_difference(old_held, retained, initial, expected)
    assert retained_pixels < 30, ("held reload replaced the active episode", retained_pixels)
    pointer.release()
    released_at = time.monotonic()
    released, released_quiet = stable(session, "held-reload-release", since=released_at)
    actual = assert_endpoint(session, primary, expected)
    assert window_difference(idle, released, initial, actual) < 30

    accepted_grab(session, pointer, primary)
    next_held, next_quiet = stable(session, "held-reload-next-gesture")
    next_pixels = window_difference(old_held, next_held, initial, actual)
    assert next_pixels > 120, ("fresh gesture did not adopt new settings", next_pixels)
    pointer.release()
    released_at = time.monotonic()
    final, final_quiet = stable(session, "held-reload-final", since=released_at)
    assert changed_pixels(released, final) < 30
    click_check(session, pointer, primary, click_count)
    session.check_render_log()
    return {
        "case": "held-settings-reload-latches-until-next-gesture",
        "source_grid_particles": original.particles,
        "before_settings": asdict(original.settings),
        "requested_settings": asdict(replacement.settings),
        "config_sha256": digest(same_grid),
        "retained_pose_pixels": retained_pixels,
        "next_gesture_pixels": next_pixels,
        "quiet": [retained_quiet, released_quiet, next_quiet, final_quiet],
        "input_count": click_count,
    }


def release_reload_check(session, pointer, primary, click_count):
    original = PRESETS["tear"]
    replacement = replace(original.settings, max_lag=24, release_ms=200)
    session.reload(config("tear"))
    place_floating(session, primary, x=160, y=140)
    idle, _ = stable(session, "release-reload-idle")
    initial = geometry(session, primary)
    start = accepted_grab(session, pointer, primary)
    end = (start[0] + 300, start[1] + 30)
    pointer.path((start, end), 0.18)
    pointer.release()
    released_at = time.monotonic()
    session.capture("release-reload-before")
    changed_config = config("tear", settings=replacement)
    session.reload(changed_config)
    contract(session)
    retained = session.capture("release-reload-retained")
    retained_ms = (time.monotonic() - released_at) * 1000
    assert 200 < retained_ms < 600, (
        "release reload sample missed its useful interval",
        retained_ms,
    )
    final, final_quiet = stable(session, "release-reload-final", since=released_at)
    expected = shifted(initial, 300, 30)
    actual = assert_endpoint(session, primary, expected)
    retained_pixels = changed_pixels(retained, final)
    assert retained_pixels > 120, ("reload truncated the original release episode", retained_pixels)
    assert window_difference(idle, final, initial, actual) < 30

    # The new short release must apply to a fresh episode, proving that latching
    # did not silently discard the requested settings after protecting the tail.
    start = accepted_grab(session, pointer, primary)
    end = (start[0] + 160, start[1] - 20)
    pointer.path((start, end), 0.18)
    pointer.release()
    next_release_at = time.monotonic()
    time.sleep(0.35)
    short_release = session.capture("release-reload-next-deadline")
    deadline_ms = (time.monotonic() - next_release_at) * 1000
    assert deadline_ms < 600, ("fresh release sample was too late", deadline_ms)
    settled, next_quiet = stable(session, "release-reload-next-final", since=next_release_at)
    next_actual = assert_endpoint(session, primary, shifted(actual, 160, -20))
    deadline_pixels = changed_pixels(short_release, settled)
    assert deadline_pixels < 30, ("fresh episode ignored the shorter release", deadline_pixels)
    assert window_difference(idle, settled, initial, next_actual) < 30
    click_check(session, pointer, primary, click_count)
    session.check_render_log()
    return {
        "case": "release-reload-preserves-old-tail-and-adopts-next-settings",
        "before_settings": asdict(original.settings),
        "requested_settings": asdict(replacement),
        "config_sha256": digest(changed_config),
        "retained_sample_ms": retained_ms,
        "retained_pixels": retained_pixels,
        "next_deadline_sample_ms": deadline_ms,
        "next_deadline_pixels": deadline_pixels,
        "quiet": [final_quiet, next_quiet],
        "input_count": click_count,
    }


def off_check(session, pointer, primary, click_count):
    session.reload(config("tear"))
    place_floating(session, primary, x=160, y=140)
    idle, _ = stable(session, "off-idle")
    initial = geometry(session, primary)
    start = accepted_grab(session, pointer, primary)
    middle = (start[0] + 120, start[1] + 20)
    end = (start[0] + 200, start[1] + 40)
    pointer.path((start, middle), 0.3)
    session.capture("off-before-reload")
    session.reload(config("tear", movement_off=True))
    disabled = contract(session, enabled=False)
    after_off = session.capture("off-held")
    off_pixels = window_difference(idle, after_off, initial, shifted(initial, 120, 20))
    assert off_pixels < 30, ("Movement Off left a held deformation", off_pixels)
    pointer.path((middle, end), 0.25)
    ordinary_drag = session.capture("off-drag")
    drag_pixels = window_difference(idle, ordinary_drag, initial, shifted(initial, 200, 40))
    assert drag_pixels < 30, ("Movement Off continued deforming the window", drag_pixels)
    pointer.release()
    released_at = time.monotonic()
    final, final_quiet = stable(session, "off-release", since=released_at)
    actual = assert_endpoint(session, primary, shifted(initial, 200, 40))
    assert window_difference(idle, final, initial, actual) < 30
    accepted_grab(session, pointer, primary)
    time.sleep(0.35)
    press_off = session.capture("off-fresh-press")
    press_pixels = changed_pixels(final, press_off)
    assert press_pixels < 30, ("Movement Off still expanded a fresh press", press_pixels)
    pointer.release()
    click_check(session, pointer, primary, click_count)

    session.reload(config("gentle"))
    enabled = contract(session)
    baseline, _ = stable(session, "reenabled-idle")
    accepted_grab(session, pointer, primary)
    reenabled, held_quiet = stable(session, "reenabled-press")
    reenabled_pixels = changed_pixels(baseline, reenabled)
    assert reenabled_pixels > 120, ("re-enabled material stayed inactive", reenabled_pixels)
    pointer.release()
    released_at = time.monotonic()
    clean, release_quiet = stable(session, "reenabled-release", since=released_at)
    assert changed_pixels(baseline, clean) < 30
    click_check(session, pointer, primary, click_count + 1)
    session.check_render_log()
    return {
        "case": "movement-off-during-grab-and-reenable",
        "disabled_capability": disabled,
        "enabled_capability": enabled,
        "off_held_pixels": off_pixels,
        "off_drag_pixels": drag_pixels,
        "off_press_pixels": press_pixels,
        "reenabled_press_pixels": reenabled_pixels,
        "quiet": [final_quiet, held_quiet, release_quiet],
        "input_count": click_count + 1,
    }


def exercise(protocol):
    binary, build = experiment()
    configs = {name: config(name) for name in PRESETS}
    configs["off"] = config("tear", movement_off=True)
    with FragmentSession(configs["gentle"], binary=binary, width=1440, height=900) as session:
        # Validate every exact preset/off configuration before sending input.
        config_dir = session.root / "preset-configs"
        config_dir.mkdir()
        for name, text in configs.items():
            path = config_dir / (name + ".kdl")
            path.write_text(text)
            subprocess.run(
                [str(binary), "validate", "-c", str(path)],
                check=True,
                capture_output=True,
                timeout=10,
            )
        evidence = Evidence(session, build, configs)
        helper = build_pointer(session.root / "pointer", protocol)
        _, primary = client(session, "Preset lifecycle", "#b7e8db")
        session.focus()
        with VirtualPointer(session, helper, label="preset-lifecycle-pointer") as pointer:
            for click_count, name in enumerate(PRESETS, start=1):
                evidence.append(preset_check(session, pointer, primary, name, click_count))
            click_count = len(PRESETS) + 1
            evidence.append(held_reload_check(session, pointer, primary, click_count))
            evidence.append(release_reload_check(session, pointer, primary, click_count + 1))
            evidence.append(off_check(session, pointer, primary, click_count + 2))
            session.check_render_log()
            evidence.complete()
        print(f"PASS fragment presets and reloads; private evidence: {session.root}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pointer-protocol", type=Path)
    arguments = parser.parse_args()
    exercise(pointer_protocol(arguments.pointer_protocol))
