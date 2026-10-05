#!/usr/bin/env python3
"""Check continuous square-fragment motion with owned synthetic native windows.

A long real pointer gesture must still expose breakup after the timed movement
duration has elapsed. At a fixed endpoint, gaps must close and pixels become
stable. Captures and raw evidence stay private under ignored artifacts/.
"""

import argparse
import colorsys
import hashlib
import json
import math
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.fragment import experiment
from lib.nested import NestedSession, source_hashes, wait_for
from lib.pointer import VirtualPointer, build_pointer, pointer_protocol
from lib.pointer_scene import (
    BASE,
    changed_pixels,
    click_check,
    client,
    geometry,
    grab,
    place_floating,
    window,
)

from niri_fx.effects import fragment_motion_eligible, movement_shader, render_kdl
from niri_fx.presets import PRESETS
from niri_fx.profiles import Profile

# Deliberately cover several similar far distances as well as the full radius.
# A few common follower bands must not satisfy the distributed-delay oracle.
LANDMARKS = [
    {"name": name, "role": role, "x": x, "y": y}
    for name, role, x, y in (
        ("pinned", "pinned", 250, 52),
        ("near0", "near", 250, 130),
        ("near1", "near", 185, 155),
        ("near2", "near", 320, 165),
        ("middle0", "middle", 125, 230),
        ("middle1", "middle", 240, 235),
        ("middle2", "middle", 365, 230),
        ("middle3", "middle", 250, 305),
        ("far0", "far", 40, 375),
        ("far1", "far", 130, 400),
        ("far2", "far", 220, 415),
        ("far3", "far", 310, 410),
        ("far4", "far", 410, 390),
        ("far5", "far", 80, 460),
        ("far6", "far", 265, 465),
        ("far7", "far", 435, 455),
    )
]
for index, marker in enumerate(LANDMARKS):
    rgb = [
        round(channel * 255) for channel in colorsys.hsv_to_rgb(index / len(LANDMARKS), 0.9, 0.95)
    ]
    marker["color"] = "#" + "".join(f"{channel:02x}" for channel in rgb)

# Explicit fixture values make acceptance reproducible as native defaults evolve.
# These belong only to the patched compositor's experimental configuration.
FRAGMENT_SETTINGS = {
    "batches": 64,
    "delay-near-ms": 0,
    "delay-far-ms": 360,
    "delay-jitter": 0.25,
    "response-near-ms": 120,
    "response-far-ms": 360,
    "response-jitter": 0.3,
    "distance-exponent": 1.2,
    "max-lag": 768,
    "pin-radius": 24,
    "press-spread": 20,
    "press-response-ms": 140,
    "rotation-mode": "movement",
    "rotation-degrees": 20,
    "rotation-response-ms": 180,
    "rotation-speed": 1000,
    "tilt": 0.55,
    "release-ms": 1800,
}


class FragmentSession(NestedSession):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Full-feature candidates include session integration. A nested check
        # must not publish its display/socket into the user's service manager.
        self.host["NIRI_DISABLE_SYSTEM_MANAGER_NOTIFY"] = "1"
        self.host.pop("NOTIFY_SOCKET", None)
        self.capture_timings = []

    def capture(self, name):
        # Avoid PNG compression on the short interval between motion and rest.
        destination = self.root / f"{name}.ppm"
        started = time.monotonic()
        subprocess.run(
            ["grim", "-t", "ppm", "-o", "winit", str(destination)],
            env=self.env,
            check=True,
            timeout=10,
        )
        self.capture_timings.append(
            {"sample": name, "capture_ms": (time.monotonic() - started) * 1000}
        )
        return destination


def frame_timings(session, started, ended):
    """Record nested submission cadence; this is neither GPU nor scanout timing."""
    samples = [
        sample
        for sample in json.loads(session.msg("-j", "niri-fx-frame-timings"))["NiriFxFrameTimings"]
        if int(started * 1e9) <= sample["timestamp_ns"] <= int(ended * 1e9)
    ]
    assert samples and all(sample["source"] == "winit-submit" for sample in samples)
    timestamps = sorted(sample["timestamp_ns"] for sample in samples)
    intervals = sorted((b - a) / 1e6 for a, b in zip(timestamps[:-1], timestamps[1:], strict=True))
    return {
        "source": "winit-submit",
        "scope": "Owned nested output submission cadence, not GPU duration or physical latency",
        "observation_ms": (ended - started) * 1000,
        "sample_count": len(samples),
        "interval_ms": {
            "median": statistics.median(intervals) if intervals else None,
            "p95": intervals[math.ceil(len(intervals) * 0.95) - 1] if intervals else None,
            "maximum": max(intervals) if intervals else None,
        },
        "samples": samples,
    }


def background_pixels(path, bounds):
    """Count genuine holes inside the card, excluding its rounded outer edge.

    Position changes alone cannot satisfy this check: the crop follows the
    window's settled rectangle and ignores a generous 64-pixel perimeter.
    A solid-sheet bend has no breakup holes this far inside the surface.
    """
    from PIL import Image

    x, y, width, height = bounds
    crop = tuple(round(value) for value in (x + 64, y + 64, x + width - 64, y + height - 64))
    with Image.open(path) as image:
        interior = image.convert("RGB").crop(crop)
        return sum(
            count
            for count, color in interior.getcolors(interior.width * interior.height)
            if max(abs(a - b) for a, b in zip(color, (17, 24, 39), strict=True)) <= 2
        )


def settled(session, primary, name, *, held_geometry=None):
    # The contract bounds the entire release tail to two seconds. This is a
    # correctness endpoint, not a claim that useful motion should last that long.
    time.sleep(2.15)
    first = session.capture(name + "-settled")
    time.sleep(0.25)
    second = session.capture(name + "-quiet")
    quiet_pixels = changed_pixels(first, second)
    assert quiet_pixels < 30, (name, "did not become stable", quiet_pixels)
    if held_geometry is not None:
        # Interactive-move IPC intentionally omits position. A held spread also
        # expands colored edge pixels, so a color bounding box is no longer a
        # valid substitute. Retain the known input endpoint, verify size here,
        # and verify logical position after release in the landmark scenario.
        assert tuple(window(session, primary)["layout"]["window_size"]) == held_geometry[2:]
        return first, held_geometry, quiet_pixels
    return first, geometry(session, primary), quiet_pixels


def compare_motion(session, primary, name, active, position, *, held=False):
    rest, final, quiet_pixels = settled(
        session, primary, name, held_geometry=position if held else None
    )
    assert final == position, (name, "geometry moved during settle", position, final)
    difference = changed_pixels(active, rest)
    active_holes = background_pixels(active, final)
    rest_holes = background_pixels(rest, final)
    assert difference > 120, (name, "no visible continuous material", difference)
    if held:
        assert active_holes > 50 and rest_holes > 50, (
            name,
            "held material lost its configured spread",
            active_holes,
            rest_holes,
        )
    else:
        assert active_holes > rest_holes + 50, (
            name,
            "no interior fragment gaps beyond solid translation/bending",
            active_holes,
            rest_holes,
        )
        assert rest_holes < 30, (name, "fragments did not reconstruct", rest_holes)
    return {
        "case": name,
        "changed_pixels": difference,
        "interior_background_pixels": {"active": active_holes, "rest": rest_holes},
        "quiet_pixels": quiet_pixels,
        "geometry": final,
        "held_spread": held,
    }


def landmark_centroids(path, bounds):
    """Identify each colored source cell despite neutral overlapping content.

    Every fixture surface except the markers is gray. Subtracting the channel
    mean leaves a color direction that survives blending with gray; symmetric
    patches at cell centers retain a meaningful centroid under rotation. Decode
    after timed capture, so image analysis cannot delay the input samples.
    """
    from PIL import Image

    def chroma(color):
        mean = sum(color) / 3
        vector = tuple(channel - mean for channel in color)
        length = math.sqrt(sum(channel * channel for channel in vector))
        return vector, length

    palette = []
    for marker in LANDMARKS:
        vector, length = chroma(bytes.fromhex(marker["color"][1:]))
        palette.append((marker["name"], tuple(channel / length for channel in vector)))
    x, y, width, height = bounds
    # The step is 40 pixels and default hold spread is small. Include generous
    # rotation/spread margins without scanning unrelated parts of the output.
    crop_box = tuple(round(value) for value in (x - 64, y - 64, x + width + 104, y + height + 64))
    totals = {marker["name"]: [0.0, 0.0, 0.0, 0] for marker in LANDMARKS}
    with Image.open(path) as image:
        crop = image.convert("RGB").crop(crop_box)
        decoded = {}
        for _, color in crop.getcolors(crop.width * crop.height):
            if max(color) - min(color) < 32:
                decoded[color] = None
                continue
            vector, length = chroma(color)
            matches = [
                (sum(a * b for a, b in zip(vector, direction, strict=True)) / length, name)
                for name, direction in palette
            ]
            score, name = max(matches)
            # The colors are separated by at least 19 degrees. A six-degree
            # cone rejects foreign colors and marker/marker mixed coverage.
            decoded[color] = (name, length) if score > math.cos(math.radians(6)) else None
        for offset, color in enumerate(crop.getdata()):
            match = decoded[color]
            if match is None:
                continue
            name, weight = match
            total = totals[name]
            total[0] += (crop_box[0] + offset % crop.width) * weight
            total[1] += (crop_box[1] + offset // crop.width) * weight
            total[2] += weight
            total[3] += 1
    for name, total in totals.items():
        assert total[3] >= 16, ("fragment landmark disappeared", name, total[3], path)
    return {
        name: {"x": total[0] / total[2], "y": total[1] / total[2], "pixels": total[3]}
        for name, total in totals.items()
    }


def displacements(before, after):
    return {
        name: [after[name][axis] - origin[axis] for axis in ("x", "y")]
        for name, origin in before.items()
    }


def independent_histories(histories, names, required):
    """Find several genuinely separated trajectories, independent of cohort IDs.

    Every pair in the returned set must differ by more than three screen pixels
    at a common capture time. A renderer with only three shared translations
    cannot provide five such trajectories merely by rotating its cells.
    """
    from itertools import combinations

    for candidates in combinations(names, required):
        if all(
            max(abs(frame[a][0] - frame[b][0]) for frame in histories) > 3
            for a, b in combinations(candidates, 2)
        ):
            return list(candidates)
    raise AssertionError(("too few independently delayed fragment trajectories", names, histories))


def capture_at(session, started, seconds, name):
    time.sleep(max(0, started + seconds - time.monotonic()))
    begin_ms = (time.monotonic() - started) * 1000
    path = session.capture(name)
    end_ms = (time.monotonic() - started) * 1000
    assert end_ms <= seconds * 1000 + 70, ("delayed landmark sample", name, begin_ms, end_ms)
    return {"path": str(path), "start_ms": begin_ms, "end_ms": end_ms}


def accepted_grab(session, pointer, landmark, expected):
    start = grab(session, pointer, landmark)
    # The title follows xdg_toplevel.move on the same client socket. Seeing it
    # proves that Qt's asynchronous request reached Niri before measured input.
    wait_for(
        lambda: window(session, landmark)["title"].endswith(f" / moves {expected}"),
        "accepted synthetic client move request",
    )
    return start


def landmark_checks(session, helper):
    """Measure press expansion, held onset, distributed delay and queued reversal."""
    session.launch(
        ["qs", "-p", str(ROOT / "scripts/fixtures/fragment-landmarks.qml")],
        "fragment-landmarks",
        env=session.env | {"NIRIFX_LANDMARKS": json.dumps(LANDMARKS)},
        private_bus=True,
    )
    landmark = wait_for(
        lambda: next(
            (item for item in session.windows() if item["title"] == "NiriFX fragment landmarks"),
            None,
        ),
        "synthetic fragment landmarks",
    )["id"]
    place_floating(session, landmark, x=160, y=150)
    idle, initial_geometry, initial_quiet = settled(session, landmark, "landmark-initial")
    original = landmark_centroids(idle, initial_geometry)
    far_names = [marker["name"] for marker in LANDMARKS if marker["role"] == "far"]
    non_pinned = [marker["name"] for marker in LANDMARKS if marker["role"] != "pinned"]
    checks = []
    with VirtualPointer(session, helper, label="landmark-pointer") as pointer:
        session.focus()
        accepted_grab(session, pointer, landmark, 1)
        # A press changes material only: no pointer movement, detachment or
        # logical window translation is needed to reveal the held spread.
        expanded, held_geometry, held_quiet = settled(session, landmark, "press-expanded")
        assert held_geometry == initial_geometry, ("press changed layout", held_geometry)
        expanded_pixels = changed_pixels(idle, expanded)
        assert expanded_pixels > 120, ("press did not expand the material", expanded_pixels)
        expanded_positions = landmark_centroids(expanded, initial_geometry)
        spread = displacements(original, expanded_positions)
        assert math.hypot(*spread["pinned"]) <= 2, (
            "press moved the grabbed cell",
            spread["pinned"],
        )
        assert sum(math.hypot(*spread[name]) > 2 for name in far_names) >= 3, spread
        pointer.release()
        restored, restored_geometry, release_quiet = settled(session, landmark, "press-released")
        restored_pixels = changed_pixels(idle, restored)
        assert restored_geometry == initial_geometry and restored_pixels < 30, (
            "press without drag did not reconstruct",
            restored_geometry,
            restored_pixels,
        )
        checks.append(
            {
                "case": "press-expand-release-without-motion",
                "expanded_pixels": expanded_pixels,
                "restored_pixels": restored_pixels,
                "world_displacement": spread,
                "quiet_pixels": {
                    "initial": initial_quiet,
                    "held": held_quiet,
                    "released": release_quiet,
                },
                "geometry": initial_geometry,
            }
        )

        start = accepted_grab(session, pointer, landmark, 2)
        before, held_geometry, quiet = settled(session, landmark, "landmark-held-baseline")
        assert held_geometry == initial_geometry
        baseline = landmark_centroids(before, initial_geometry)
        started = time.monotonic()
        pointer.move(start[0] + 40, start[1])
        pointer.sync()
        onset_path = session.capture("landmark-onset")
        onset_ms = (time.monotonic() - started) * 1000
        assert onset_ms <= 60, ("landmark onset sample was late", onset_ms)
        samples = [{"path": str(onset_path), "start_ms": 0, "end_ms": onset_ms}]
        for milliseconds in (100, 160, 240, 320, 420, 550, 720, 920, 1250, 1750):
            samples.append(
                capture_at(session, started, milliseconds / 1000, f"landmark-{milliseconds}ms")
            )
        held_rest = capture_at(session, started, 2.15, "landmark-held-rest")
        held_quiet_frame = capture_at(session, started, 2.4, "landmark-held-quiet")
        assert changed_pixels(held_rest["path"], held_quiet_frame["path"]) < 30
        positions = [landmark_centroids(sample["path"], initial_geometry) for sample in samples]
        histories = [displacements(baseline, points) for points in positions]
        final_positions = landmark_centroids(held_rest["path"], initial_geometry)
        held_shift = displacements(baseline, final_positions)
        # Retain measurements even if a later assertion fails. This is raw
        # observation, not a passing acceptance report, and avoids repeating
        # native input just to recover an earlier sample's timing or positions.
        (session.root / "fragment-landmark-observation.json").write_text(
            json.dumps(
                {
                    "status": "ungraded-observation",
                    "landmarks": LANDMARKS,
                    "geometry": initial_geometry,
                    "baseline": baseline,
                    "samples": samples,
                    "histories": histories,
                    "settled_displacement": held_shift,
                },
                indent=2,
            )
            + "\n"
        )
        pinned = histories[0]["pinned"]
        assert abs(pinned[0] - 40) <= 2 and abs(pinned[1]) <= 2, (
            "grabbed cell was not pinned",
            pinned,
        )
        for name in far_names:
            assert abs(histories[0][name][0]) < 10 and abs(histories[0][name][1]) <= 2, (
                "far fragment followed the cursor at onset",
                name,
                histories[0][name],
            )
            assert math.hypot(*histories[1][name]) <= 1, (
                "far fragment has no 100ms hold plateau",
                name,
                histories[1][name],
            )
        for name, shift in held_shift.items():
            assert abs(shift[0] - 40) <= 2 and abs(shift[1]) <= 2, (
                "fragment did not catch up",
                name,
                shift,
            )
        checks.append(
            {
                "case": "world-space-onset-and-catch-up",
                "pointer_step": [40, 0],
                "move_request_accepted": True,
                "baseline": "stable held spread",
                "onset_sample_ms": onset_ms,
                "onset_displacement": histories[0],
                "plateau_sample": samples[1],
                "plateau_displacement": histories[1],
                "settled_displacement": held_shift,
                "quiet_pixels": quiet,
            }
        )
        checks.append(
            {
                "case": "distributed-fragment-delay",
                "independent_landmarks": independent_histories(histories, non_pinned, 5),
                "independent_far_landmarks": independent_histories(histories, far_names, 3),
                "landmarks": LANDMARKS,
                "samples": samples,
                "histories": histories,
            }
        )

        # A short extra rightward pulse is reversed before the far cells' queue
        # drains. They should later respond to that queued pulse even though the
        # cursor has already returned, then settle back to the held baseline.
        pulse_started = time.monotonic()
        pointer.move(start[0] + 80, start[1])
        pointer.sync()
        pre_reverse = capture_at(session, pulse_started, 0.08, "landmark-before-reversal")
        pointer.move(start[0] + 40, start[1])
        pointer.sync()
        post_reverse = session.capture("landmark-after-reversal")
        pulse_ms = (time.monotonic() - pulse_started) * 1000
        assert pulse_ms < 160, ("reversal missed the delayed-input interval", pulse_ms)
        reversed_samples = [
            capture_at(
                session, pulse_started, seconds, f"landmark-reversal-{round(seconds * 1000)}ms"
            )
            for seconds in (0.28, 0.4, 0.55, 0.75, 1.1)
        ]
        pre = landmark_centroids(pre_reverse["path"], initial_geometry)
        post = landmark_centroids(post_reverse, initial_geometry)
        reversal_step = displacements(pre, post)
        assert abs(reversal_step["pinned"][0] + 40) <= 2, reversal_step["pinned"]
        assert all(math.hypot(*reversal_step[name]) <= 2 for name in far_names), reversal_step
        reverse_histories = [
            displacements(final_positions, landmark_centroids(sample["path"], initial_geometry))
            for sample in reversed_samples
        ]
        responding = [
            name for name in far_names if max(frame[name][0] for frame in reverse_histories) > 3
        ]
        assert len(responding) >= 3, (
            "queued far-cell motion disappeared on reversal",
            reverse_histories,
        )
        pointer.release()
        released, final_geometry, final_quiet = settled(session, landmark, "landmark-final-release")
        assert abs(final_geometry[0] - initial_geometry[0] - 40) <= 1
        assert final_geometry[1:] == initial_geometry[1:]
        released_shift = displacements(original, landmark_centroids(released, initial_geometry))
        for name, shift in released_shift.items():
            assert abs(shift[0] - 40) <= 2 and abs(shift[1]) <= 2, (
                "release did not reconstruct",
                name,
                shift,
            )
        checks.append(
            {
                "case": "queued-reversal-and-release",
                "reverse_sample_ms": pulse_ms,
                "immediate_displacement": reversal_step,
                "responding_far_landmarks": responding,
                "samples": reversed_samples,
                "histories": reverse_histories,
                "released_displacement": released_shift,
                "quiet_pixels": final_quiet,
                "geometry": {"before": initial_geometry, "after": final_geometry},
            }
        )
    session.msg("action", "close-window", "--id", str(landmark))
    wait_for(lambda: all(item["id"] != landmark for item in session.windows()), "landmark close")
    return checks


def test_profile():
    """Use one eligible material for checks and an optional owned manual preview."""
    movement = replace(
        PRESETS["balanced"],
        fragment_shape="square",
        particles=800,
        spin=100,
        stagger=0.08,
        dispersion=0.65,
        movement_ms=350,
        movement_strength=0.48,
        movement_focus=0.65,
        scatter=100,
        gravity_strength=0.35,
    )
    assert fragment_motion_eligible(movement)
    assert "// nirifx-fragment-motion: 3" in movement_shader(movement)
    return Profile(open="off", close="off", resize="off", movement=movement)


def test_config(profile):
    """Add native fixture controls to one generated, temporary movement node."""
    generated = render_kdl(profile, movement=True)
    node = "    window-movement {\n"
    assert generated.count(node) == 1, "Expected exactly one generated movement node"
    settings = (
        "        fragment-motion {\n"
        + "".join(
            f"            {key} {json.dumps(value)}\n" for key, value in FRAGMENT_SETTINGS.items()
        )
        + "        }\n"
    )
    return BASE + generated.replace(node, node + settings, 1)


def exercise(protocol):
    binary, build = experiment()
    profile = test_profile()
    movement = profile.movement
    config = test_config(profile)
    with FragmentSession(config, binary=binary, width=1440, height=900) as session:
        capabilities = json.loads(session.msg("-j", "niri-fx-fragment-capabilities"))[
            "NiriFxFragmentCapabilities"
        ]
        for key, expected in {
            "schema": 1,
            "fragment_motion": 3,
            "renderer_verified": True,
            "fragment_configured": True,
            "fragment_enabled": True,
            "max_deformation": 1024,
            "max_release_ms": 2000,
        }.items():
            assert capabilities.get(key) == expected, capabilities
        helper = build_pointer(session.root / "pointer", protocol)
        checks = landmark_checks(session, helper)
        _, primary = client(session, "Continuous fragments", "#b7e8db")
        place_floating(session, primary, x=160, y=150)
        with VirtualPointer(session, helper) as pointer:
            click_check(session, pointer, primary, 1)
            session.focus()
            initial_geometry = geometry(session, primary)
            start = grab(session, pointer, primary)
            started = time.monotonic()
            end = (start[0] + 330, start[1] + 80)
            pointer.path((start, end), 0.95)
            active = session.capture("long-drag-active")
            ended = time.monotonic()
            elapsed = ended - started
            floating_timings = frame_timings(session, started, ended)
            assert elapsed > movement.movement_ms / 1000 * 2
            expected_geometry = (
                initial_geometry[0] + end[0] - start[0],
                initial_geometry[1] + end[1] - start[1],
                *initial_geometry[2:],
            )
            check = compare_motion(
                session, primary, "long-drag-held-pause", active, expected_geometry, held=True
            )
            check["sample_after_drag_start_ms"] = elapsed * 1000
            check["timed_movement_ms"] = movement.movement_ms
            check["native_frame_timings"] = floating_timings
            checks.append(check)

            # The grab remains held through the pause. New motion must reactivate
            # the same material and then settle after reversing and releasing.
            reverse = (end[0] - 260, end[1] - 50)
            pointer.path((end, reverse), 0.7)
            pointer.release()
            released = session.capture("reverse-release-active")
            checks.append(
                compare_motion(
                    session,
                    primary,
                    "reverse-release",
                    released,
                    geometry(session, primary),
                )
            )
            click_check(session, pointer, primary, 2)

            # Regrab before the bounded tail expires, then verify settled input.
            start = grab(session, pointer, primary)
            end = (start[0] + 100, start[1] - 30)
            pointer.path((start, end), 0.3)
            pointer.release()
            released_at = time.monotonic()
            again = grab(session, pointer, primary)
            regrab_ms = (time.monotonic() - released_at) * 1000
            assert regrab_ms < 500, ("regrab missed the intended interval", regrab_ms)
            pointer.path((again, (again[0] - 90, again[1] + 50)), 0.3)
            pointer.release()
            active = session.capture("regrab-active")
            check = compare_motion(session, primary, "regrab", active, geometry(session, primary))
            check["regrab_interval_ms"] = regrab_ms
            checks.append(check)
            click_check(session, pointer, primary, 3)

            # A normal compositor action drives the same marked material without
            # pointer settings. Sample after placement ends, while its tail remains.
            session.msg("action", "move-floating-window", "--id", str(primary), "--x", "+240")
            time.sleep(0.37)
            active = session.capture("timed-move-active")
            checks.append(
                compare_motion(session, primary, "timed-move", active, geometry(session, primary))
            )

            _, secondary = client(session, "Column companion", "#d6c5ef")
            session.msg("action", "move-window-to-tiling", "--id", str(primary))
            time.sleep(2.2)
            session.msg("action", "focus-window", "--id", str(primary))
            time.sleep(0.4)
            before = window(session, primary)["layout"]["pos_in_scrolling_layout"]
            companion = window(session, secondary)["layout"]["pos_in_scrolling_layout"]
            direction = "right" if before[0] < companion[0] else "left"
            session.capture("column-before")
            session.msg("action", "move-column-" + direction)
            time.sleep(0.12)
            session.capture("column-active")
            time.sleep(2.15)
            session.capture("column-settled")
            after = window(session, primary)["layout"]["pos_in_scrolling_layout"]
            assert before != after, ("column action did not reorder windows", before, after)
            assert {item["id"] for item in session.windows()} == {primary, secondary}
            assert not any(item["is_floating"] for item in session.windows())
            click_check(session, pointer, primary, 4)
            checks.append({"case": "column-reorder-input", "before": before, "after": after})

            # Keep Niri's 8-pixel gesture recognition, then bypass the separate
            # 256-pixel tiled pull threshold for eligible fragments. A vertical
            # request selects moving rather than horizontal viewport scrolling.
            request_log = session.root / "Continuous fragments.log"
            previous_requests = request_log.read_text().count("NIRIFX_MOVE_REQUEST true")
            start = grab(session, pointer, primary)
            wait_for(
                lambda: (
                    request_log.read_text().count("NIRIFX_MOVE_REQUEST true") > previous_requests
                ),
                "accepted tiled client move request",
            )
            direction = -1 if start[0] > session.width / 2 else 1
            excursion = (start[0] + direction * 340, start[1] + 70)
            later = (excursion[0] + direction * 100, excursion[1] + 20)
            started = time.monotonic()
            first_step = (start[0], start[1] + 4)
            pointer.move(*first_step)
            pointer.sync()
            time.sleep(0.05)
            assert window(session, primary)["layout"]["pos_in_scrolling_layout"] is not None
            recognized_step = (start[0], start[1] + 9)
            pointer.move(*recognized_step)
            pointer.sync()
            wait_for(
                lambda: window(session, primary)["layout"]["pos_in_scrolling_layout"] is None,
                "tiled detachment after the 9-pixel recognition step",
                timeout=0.5,
            )
            pointer.path((recognized_step, (start[0], start[1] + 30), excursion), 0.5)
            assert window(session, primary)["layout"]["pos_in_scrolling_layout"] is None
            pointer.path((excursion, later), 0.55)
            session.capture("tiled-long-drag-active")
            ended = time.monotonic()
            elapsed = ended - started
            tiled_timings = frame_timings(session, started, ended)
            assert elapsed > movement.movement_ms / 1000 * 2
            assert window(session, primary)["layout"]["pos_in_scrolling_layout"] is None
            pointer.path((later, start), 0.7)
            pointer.release()
            time.sleep(2.15)
            session.capture("tiled-drop-settled")
            assert {item["id"] for item in session.windows()} == {primary, secondary}
            assert not any(item["is_floating"] for item in session.windows())
            click_check(session, pointer, primary, 5)
            checks.append(
                {
                    "case": "tiled-long-drag-drop-input",
                    "move_request_accepted": True,
                    "attached_step": [0, 4],
                    "detachment_step": [0, 9],
                    "held_sample_ms": elapsed * 1000,
                    "native_frame_timings": tiled_timings,
                }
            )
            session.check_render_log()
            evidence = {
                "scope": "Owned nested winit with synthetic clients and real virtual-pointer input",
                "build": build,
                "movement": asdict(movement),
                "fragment_settings": FRAGMENT_SETTINGS,
                "config_sha256": hashlib.sha256(session.config.read_bytes()).hexdigest(),
                "capabilities": capabilities,
                "checks": checks,
                "capture_timings": session.capture_timings,
                "pointer_acknowledgements": pointer.timings,
                "limits": [
                    "No physical desktop, mixed-output, input-to-photon or PipeWire acceptance.",
                    "Pixel checks measure piece displacement and stable endpoints; exact velocity continuity is checked separately.",
                    "Column captures and layout checks supplement the timed floating-material check.",
                    "No interactive resize, cross-window particle simulation or public recording.",
                ],
                "sources": source_hashes(
                    "scripts/test-fragment-drag.py",
                    "scripts/lib/pointer.py",
                    "scripts/lib/pointer_scene.py",
                    "scripts/fixtures/pointer-card.qml",
                    "scripts/fixtures/fragment-landmarks.qml",
                    "niri_fx/effects.py",
                    "niri_fx/shaders/fragment-motion.glsl",
                ),
            }
            (session.root / "fragment-drag-acceptance.json").write_text(
                json.dumps(evidence, indent=2) + "\n"
            )
        print(f"PASS continuous fragments; private evidence: {session.root}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pointer-protocol", type=Path)
    arguments = parser.parse_args()
    exercise(pointer_protocol(arguments.pointer_protocol))
