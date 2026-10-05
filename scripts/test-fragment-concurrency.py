#!/usr/bin/env python3
"""Check independent simultaneous fragment materials in an owned compositor.

Synthetic source colors and full-card resting comparisons detect cross-window
state/texture mistakes. Submission cadence is diagnostic, not GPU duration,
physical latency or a compositor performance budget.
"""

import argparse
import hashlib
import json
import math
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.fragment import FragmentSession, config, experiment
from lib.nested import source_hashes, wait_for
from lib.pointer import VirtualPointer, build_pointer, pointer_protocol
from lib.pointer_scene import changed_pixels, click_check, geometry, place_floating

COLORS = ("#b7e8db", "#d6c5ef", "#eab5c8", "#d8dd9d")
SIZE = (420, 330)


class CaptureSession(FragmentSession):
    def capture(self, name):
        # Encoding is kept off the retarget schedule; these are native pixels.
        path = self.root / (name + ".ppm")
        subprocess.run(
            ["grim", "-t", "ppm", "-o", "winit", str(path)], env=self.env, check=True, timeout=10
        )
        return path


def client(session, index, point):
    label = "Material " + chr(ord("A") + index)
    session.launch(
        ["qs", "-p", str(ROOT / "scripts/fixtures/fragment-concurrency.qml")],
        label,
        env=session.env | {"NIRIFX_LABEL": label, "NIRIFX_COLOR": COLORS[index]},
        private_bus=True,
    )
    window = wait_for(
        lambda: next(
            (w for w in session.windows() if w["title"].startswith("NiriFX pointer / " + label)),
            None,
        ),
        "owned concurrency card",
    )
    place_floating(session, window["id"], x=point[0], y=point[1], width=SIZE[0], height=SIZE[1])
    return window["id"]


def move(session, ids, points):
    """Issue a short batch of native actions, recording the actual dispatch span."""
    started = time.monotonic()
    for window_id, (x, y) in zip(ids, points, strict=True):
        session.msg(
            "action", "move-floating-window", "--id", str(window_id), "--x", str(x), "--y", str(y)
        )
    ended = time.monotonic()
    assert ended - started < 0.08, ("movement batch did not overlap", ended - started)
    return started, (ended - started) * 1000


def at(started, seconds):
    time.sleep(max(0, started + seconds - time.monotonic()))


def timed_capture(session, name, started, seconds, *, latest):
    at(started, seconds)
    path = session.capture(name)
    elapsed = time.monotonic() - started
    assert elapsed < latest, (name, "missed intended moving interval", elapsed)
    return {"path": str(path), "elapsed_ms": elapsed * 1000}


def frame_timings(session, started, ended):
    samples = [
        item
        for item in json.loads(session.msg("-j", "niri-fx-frame-timings"))["NiriFxFrameTimings"]
        if int(started * 1e9) <= item["timestamp_ns"] <= int(ended * 1e9)
    ]
    assert samples and all(item["source"] == "winit-submit" for item in samples)
    stamps = sorted(item["timestamp_ns"] for item in samples)
    gaps = sorted((b - a) / 1e6 for a, b in zip(stamps[:-1], stamps[1:], strict=True))
    return {
        "source": "winit-submit",
        "scope": "Owned nested output submission cadence, not GPU duration or physical latency",
        "observation_ms": (ended - started) * 1000,
        "sample_count": len(samples),
        "interval_ms": {
            "median": statistics.median(gaps) if gaps else None,
            "p95": gaps[math.ceil(len(gaps) * 0.95) - 1] if gaps else None,
            "maximum": max(gaps) if gaps else None,
        },
        "samples": samples,
    }


def source_components(path, color):
    """Count disconnected pieces of one source accent, independent of position.

    A four-pixel original-color tolerance includes filtered interior pixels.
    Half-resolution components smaller than nine pixels are ignored to reject
    text antialiasing. The resting source provides the control for each identity.
    """
    from PIL import Image, ImageChops

    target = tuple(bytes.fromhex(color[1:]))
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        channels = ImageChops.difference(rgb, Image.new("RGB", image.size, target)).split()
        mask = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2]).point(
            lambda v: 255 if v <= 4 else 0
        )
        mask = mask.resize((mask.width // 2, mask.height // 2), Image.Resampling.NEAREST)
        width, height = mask.size
        pixels = bytearray(mask.tobytes())
    visible = sum(value != 0 for value in pixels)
    components = []
    for origin, value in enumerate(pixels):
        if not value:
            continue
        pixels[origin] = 0
        pending = [origin]
        area = 0
        while pending:
            current = pending.pop()
            area += 1
            x, y = current % width, current // width
            neighbors = []
            if x:
                neighbors.append(current - 1)
            if x + 1 < width:
                neighbors.append(current + 1)
            if y:
                neighbors.append(current - width)
            if y + 1 < height:
                neighbors.append(current + width)
            for adjacent in neighbors:
                if pixels[adjacent]:
                    pixels[adjacent] = 0
                    pending.append(adjacent)
        if area >= 9:
            components.append(area)
    return {
        "visible_pixels_half_resolution": visible,
        "components": len(components),
        "largest_component": max(components, default=0),
    }


def identity_pixels(before, after, old, new):
    from PIL import Image, ImageChops

    def crop(image, point):
        x, y = point
        return image.convert("RGB").crop((x, y, x + SIZE[0], y + SIZE[1]))

    with Image.open(before) as first, Image.open(after) as second:
        diff = ImageChops.difference(crop(first, old), crop(second, new))
        return sum(
            count for count, color in diff.getcolors(diff.width * diff.height) if max(color) > 8
        )


class Evidence:
    def __init__(self, session, build, protocol, count):
        self.path = session.root / "fragment-concurrency-acceptance.json"
        capability = json.loads(session.msg("-j", "niri-fx-fragment-capabilities"))[
            "NiriFxFragmentCapabilities"
        ]
        assert capability["fragment_motion"] == 3 and all(
            capability[k] for k in ("renderer_verified", "fragment_configured", "fragment_enabled")
        ), capability
        self.value = {
            "status": "incomplete",
            "windows": count,
            "preset": "tear",
            "build": build,
            "capabilities": capability,
            "scope": "Owned nested compositor, synthetic source cards and native movement actions",
            "checks": [],
            "config_sha256": hashlib.sha256(session.config.read_bytes()).hexdigest(),
            "protocol_sha256": hashlib.sha256(protocol.read_bytes()).hexdigest(),
            "sources": source_hashes(
                "scripts/test-fragment-concurrency.py",
                "scripts/fixtures/fragment-concurrency.qml",
                "scripts/lib/fragment.py",
                "scripts/lib/nested.py",
                "scripts/lib/pointer.py",
                "scripts/lib/pointer_scene.py",
                "niri_fx/fragment_motion.py",
                "niri_fx/effects.py",
                "niri_fx/shaders/fragment-motion.glsl",
            ),
            "limits": [
                "Sequential IPC commands overlap; they are not an atomic compositor transaction.",
                "No cross-window particle transfer or interaction is implemented or asserted.",
                "Submission intervals are not GPU time, display latency or physical desktop certification.",
            ],
        }
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.value, indent=2) + "\n")

    def record(self, value):
        self.value["checks"].append(value)
        self.save()
        return value


def settle(session, evidence, ids, original, before, points, label):
    time.sleep(2.15)
    final = session.capture(label + "-settled")
    time.sleep(0.25)
    quiet = session.capture(label + "-quiet")
    quiet_pixels = changed_pixels(final, quiet)
    observed = {w["id"] for w in session.windows()}
    geometries = [geometry(session, w) for w in ids]
    differences = [
        identity_pixels(before, final, a, b) for a, b in zip(original, points, strict=True)
    ]
    evidence.record(
        {
            "case": label + "-reconstructed-identities",
            "expected_points": points,
            "geometry": geometries,
            "ids_preserved": observed == set(ids),
            "source_difference_pixels": differences,
            "quiet_pixels": quiet_pixels,
        }
    )
    assert observed == set(ids), observed
    for actual, expected in zip(geometries, points, strict=True):
        assert tuple(actual) == (*expected, *SIZE), (actual, expected)
    assert max(differences) < 30, (label, "source texture changed or exchanged", differences)
    assert quiet_pixels < 30, (label, "material did not become stable", quiet_pixels)
    return final


def breakup(evidence, baseline, frames, count):
    controls = [source_components(baseline, color) for color in COLORS[:count]]
    records = []
    for frame in frames:
        materials = [source_components(frame["path"], color) for color in COLORS[:count]]
        records.append(frame | {"sources": materials})
    evidence.record({"case": "independent-source-breakup", "controls": controls, "frames": records})
    # Every source must fragment in the same observed frame, not merely appear
    # somewhere during the run. This excludes serial single-window coverage.
    assert any(
        all(
            value["visible_pixels_half_resolution"] > 1200
            and value["components"] > control["components"] + 12
            for value, control in zip(frame["sources"], controls, strict=True)
        )
        for frame in records
    ), ("simultaneous source breakup not observed", records, controls)


def exercise_case(binary, build, protocol, count):
    initial = (
        [(160, 230), (860, 230)] if count == 2 else [(80, 60), (900, 60), (80, 500), (900, 500)]
    )
    with CaptureSession(config("tear"), binary=binary) as session:
        evidence = Evidence(session, build, protocol, count)
        ids = [client(session, index, point) for index, point in enumerate(initial)]
        time.sleep(2.15)
        session.focus()
        before = session.capture("source-identities")
        helper = build_pointer(session.root / "pointer", protocol)
        frames = []
        if count == 2:
            swap = list(reversed(initial))
            started, span = move(session, ids, swap)
            frames.append(timed_capture(session, "swap-outbound", started, 0.12, latest=0.20))
            at(started, 0.18)
            reversed_at, reverse_span = move(session, ids, initial)
            assert reversed_at - started < 0.30, "reversal happened after placement ended"
            frames.append(timed_capture(session, "swap-reversed", reversed_at, 0.12, latest=0.20))
            evidence.record(
                {
                    "case": "two-window-swap-reversal",
                    "batch_ms": span,
                    "reverse_batch_ms": reverse_span,
                    "reverse_after_ms": (reversed_at - started) * 1000,
                    "frame_timings": frame_timings(session, started, time.monotonic()),
                }
            )
            settle(session, evidence, ids, initial, before, initial, "reversal")
            started, span = move(session, ids, swap)
            frames.append(timed_capture(session, "completed-swap-tail", started, 0.37, latest=0.46))
            evidence.record(
                {
                    "case": "two-window-completed-swap",
                    "batch_ms": span,
                    "frame_timings": frame_timings(session, started, time.monotonic()),
                }
            )
            settle(session, evidence, ids, initial, before, swap, "completed-swap")
        else:
            first = [(260, 100), (720, 100), (260, 460), (720, 460)]
            final = [(220, 90), (760, 70), (170, 470), (750, 460)]
            started, span = move(session, ids, first)
            frames.append(timed_capture(session, "four-outbound", started, 0.12, latest=0.22))
            at(started, 0.18)
            retargeted, retarget_span = move(session, ids, final)
            assert retargeted - started < 0.30, "retarget happened after placement ended"
            frames.append(timed_capture(session, "four-retargeted", retargeted, 0.12, latest=0.22))
            frames.append(
                timed_capture(session, "four-retargeted-tail", retargeted, 0.37, latest=0.47)
            )
            evidence.record(
                {
                    "case": "four-independent-retargets",
                    "batch_ms": span,
                    "retarget_batch_ms": retarget_span,
                    "retarget_after_ms": (retargeted - started) * 1000,
                    "frame_timings": frame_timings(session, started, time.monotonic()),
                }
            )
            rest = settle(session, evidence, ids, initial, before, final, "four-retargets")
            # Move only A after concurrent settlement. Other source textures and
            # poses must stay byte-stable: this detects accidental shared state.
            started, span = move(session, ids[:1], [(final[0][0] + 60, final[0][1])])
            solo = timed_capture(session, "one-source-followup", started, 0.37, latest=0.47)
            unaffected = [identity_pixels(rest, solo["path"], point, point) for point in final[1:]]
            evidence.record(
                {
                    "case": "single-source-followup-isolation",
                    "unaffected_pixels": unaffected,
                    "batch_ms": span,
                }
            )
            assert max(unaffected) < 30, (
                "other windows changed with the selected material",
                unaffected,
            )
            points = [(final[0][0] + 60, final[0][1]), *final[1:]]
            settle(session, evidence, ids, initial, before, points, "single-followup")
        breakup(evidence, before, frames, count)
        with VirtualPointer(session, helper) as pointer:
            for window_id in ids:
                click_check(session, pointer, window_id, 1)
        evidence.record({"case": "all-client-input", "acknowledged_windows": count})
        session.check_render_log()
        evidence.value["status"] = "passed"
        evidence.save()
        return str(evidence.path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pointer-protocol", type=Path)
    parser.add_argument(
        "--windows", type=int, choices=(2, 4), help="Run one focused case instead of both"
    )
    args = parser.parse_args()
    protocol = pointer_protocol(args.pointer_protocol)
    binary, build = experiment()
    evidence = [
        exercise_case(binary, build, protocol, count)
        for count in ([args.windows] if args.windows else [2, 4])
    ]
    print("PASS fragment concurrency; private evidence:", *evidence, sep="\n", flush=True)
