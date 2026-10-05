#!/usr/bin/env python3
"""Observe retained resize materials in owned nested compositors.

The diagnostic reads shader phase/reference uniforms from actual pixels. Privacy
uses synthetic protected/public cards. Optional Output/debug Screencast checks
capture only an owned nested parent, not the login desktop or PipeWire transport.
Closing snapshots and blurred backgrounds are outside this harness's scope.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.movement import experiment
from lib.nested import NestedSession, source_hashes, wait_for
from lib.pointer_scene import BASE, client, place_floating, window

from niri_fx.effects import resize_shader
from niri_fx.presets import PRESETS

spec = importlib.util.spec_from_file_location(
    "pointer_hardening", ROOT / "scripts/test-pointer-hardening.py"
)
hardening = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hardening)

MARKER = "// niri-fx resize-continuity: 1"
PASSTHROUGH = (
    MARKER
    + """
vec4 resize_color(vec3 coords_curr_geo, vec3 size_curr_geo) {
    vec2 previous = (niri_geo_to_tex_prev * coords_curr_geo).xy;
    vec2 current = (niri_geo_to_tex_next * coords_curr_geo).xy;
    return mix(texture2D(niri_tex_prev, previous), texture2D(niri_tex_next, current),
               niri_clamped_progress);
}
"""
)
DIAGNOSTIC = (
    MARKER
    + """
vec4 resize_color(vec3 coords_curr_geo, vec3 size_curr_geo) {
#ifdef NIRIFX_RESIZE_CONTINUITY_V1
    if (niri_resize_retained > 0.5) {
        if (coords_curr_geo.x < 0.25)
            return vec4(16.0 / 255.0, niri_resize_reference_from_size / 1024.0, 1.0);
        if (coords_curr_geo.x < 0.5)
            return vec4(32.0 / 255.0, niri_resize_reference_to_size / 1024.0, 1.0);
        return vec4(0.25 + 0.5 * niri_clamped_progress,
                    niri_resize_reference_size / 1024.0, 1.0);
    }
#endif
    return vec4(1.0, 0.0, 0.0, 1.0);
}
"""
)
REPLACEMENT_RGB = (56, 109, 241)
REPLACEMENT = (
    MARKER
    + """
vec4 resize_color(vec3 coords_curr_geo, vec3 size_curr_geo) {
    return vec4(56.0 / 255.0, 109.0 / 255.0, 241.0 / 255.0, 1.0);
}
"""
)


def config(shader, *, duration=3000, policy=None, preview=False):
    text = (
        BASE
        + "animations {\n"
        + "    window-open { off; }\n    window-close { off; }\n"
        + "    window-movement { off; }\n"
        + f'    window-resize {{ duration-ms {duration}; curve "linear";\n'
        + (f'        custom-shader r#"{shader}"#\n' if shader else "")
        + "    }\n}\n"
    )
    if policy:
        text += (
            'window-rule { match title=r#"^NiriFX pointer / Protected"#; '
            f'block-out-from "{policy}"; }}\n'
        )
    if preview:
        text += 'debug { preview-render "screencast"; }\n'
    return text


def pixels(path):
    from PIL import Image

    with Image.open(path) as image:
        return image.convert("RGB").getcolors(image.width * image.height)


def pixel_hash(path):
    from PIL import Image

    with Image.open(path) as image:
        return hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()


def uniform_pixels(path, rgb, tolerance=2):
    return sum(
        count
        for count, actual in pixels(path)
        if all(abs(a - b) <= tolerance for a, b in zip(actual, rgb, strict=True))
    )


def diagnostic(path, *, original=(400, 360), reference=(700, 360)):
    """Decode three independently visible uniform bands, rejecting missing data."""
    colors = pixels(path)
    for red, size in ((16, original), (32, reference)):
        expected = (red, *(round(value * 255 / 1024) for value in size))
        assert (
            sum(
                count
                for count, rgb in colors
                if all(abs(a - b) <= 2 for a, b in zip(rgb, expected, strict=True))
            )
            > 2500
        ), ("missing or changed material reference", red, size)
    green, blue = (round(value * 255 / 1024) for value in reference)
    candidates = [
        (count, rgb)
        for count, rgb in colors
        if 62 <= rgb[0] <= 194 and abs(rgb[1] - green) <= 2 and abs(rgb[2] - blue) <= 2
    ]
    assert candidates and max(candidates)[0] > 5000, "missing retained material phase band"
    count, rgb = max(candidates)
    return {
        "phase": (rgb[0] / 255 - 0.25) / 0.5,
        "phase_pixels": count,
        "from": list(original),
        "reference": list(reference),
    }


def phase_continues(before, after, elapsed, duration):
    delta = after["phase"] - before["phase"]
    assert delta >= -0.025, ("material phase restarted", before, after)
    assert abs(delta - elapsed / duration) < 0.10, (
        "material phase changed clock",
        delta,
        elapsed,
        duration,
    )


def privacy_valid(counts, *, hidden, advanced=True):
    return (
        advanced
        and counts["public"] > 10000
        and (counts["protected"] == 0 if hidden else counts["protected"] > 10000)
    )


def resize(session, primary, axis, extent):
    session.msg("action", f"set-window-{axis}", "--id", str(primary), str(extent))
    index = 0 if axis == "width" else 1
    wait_for(
        lambda: window(session, primary)["layout"]["window_size"][index] == extent,
        "owned client resize commit",
    )


def cards(session):
    _, primary = client(session, "Protected", hardening.PROTECTED)
    _, secondary = client(session, "Public", hardening.PUBLIC)
    place_floating(session, primary, x=40, y=120, width=400, height=360)
    place_floating(session, secondary, x=800, y=120, width=400, height=500)
    return primary


def material_contract(binary, parent=None):
    duration = 3000
    with patch.dict(os.environ, parent.env if parent else os.environ.copy(), clear=True):
        child = NestedSession(config(None, duration=1), binary=binary, width=1280, height=800)
    with child as session:
        primary = cards(session)
        session.reload(config(DIAGNOSTIC, duration=duration))
        resize(session, primary, "width", 700)
        time.sleep(0.45)
        records = []

        def captures(name):
            paths = {"screen_capture": session.capture(name)}
            if parent is not None:
                paths["output"] = parent.capture(name + "-output")
            return paths

        def sample(name):
            start = time.monotonic()
            paths = captures(name)
            measured = diagnostic(paths["screen_capture"])
            measured["time"] = (start + time.monotonic()) / 2
            if parent is not None:
                measured["output"] = diagnostic(paths["output"])
                if records:
                    previous = records[-1]
                    phase_continues(
                        previous["output"],
                        measured["output"],
                        measured["time"] - previous["time"],
                        duration / 1000,
                    )
            records.append({"step": name, **measured})
            return measured

        before = sample("initial-material")
        assert 0.08 < before["phase"] < 0.4, before
        for axis, extent in (("width", 520), ("height", 460)):
            resize(session, primary, axis, extent)
            after = sample(f"retarget-{axis}")
            phase_continues(before, after, after["time"] - before["time"], duration / 1000)
            before = after
        session.reload(config(REPLACEMENT, duration=duration))
        resize(session, primary, "width", 640)
        after = sample("shader-reload-retarget")
        phase_continues(before, after, after["time"] - before["time"], duration / 1000)
        time.sleep(duration / 1000 + 0.3)
        resize(session, primary, "width", 480)
        time.sleep(0.35)
        for target, path in captures("replacement-next-episode").items():
            assert uniform_pixels(path, REPLACEMENT_RGB) > 20000, (
                target,
                "replacement shader was not adopted at rest",
            )
        session.reload(config(None, duration=duration))
        resize(session, primary, "height", 380)
        for target, path in captures("removed-shader-retarget").items():
            assert uniform_pixels(path, REPLACEMENT_RGB) > 20000, (
                target,
                "active material program changed on removal",
            )
        time.sleep(duration / 1000 + 0.3)
        resize(session, primary, "width", 600)
        time.sleep(0.35)
        for target, path in captures("removed-shader-next-episode").items():
            assert uniform_pixels(path, REPLACEMENT_RGB) == 0, (
                target,
                "removed program leaked into next episode",
            )
            assert hardening.colors(path)["protected"] > 10000, (
                target,
                "removed shader lost live content",
            )
        session.check_render_log()
        origin = records[0]["time"]
        for record in records:
            record["elapsed_s"] = round(record.pop("time") - origin, 4)
        return {
            "checks": records,
            "replacement_adopted_at_rest": True,
            "removal_preserved_active_program": True,
            "removal_adopted_at_rest": True,
        }


def privacy(parent, binary, policy, preview, results):
    result = {
        "policy": policy,
        "output_target": ("Screencast" if preview else "Output") if parent else None,
        "checks": [],
        "status": "failed",
    }
    results.append(result)
    with patch.dict(os.environ, parent.env if parent else os.environ.copy(), clear=True):
        child = NestedSession(
            config(None, duration=1, preview=preview), binary=binary, width=1280, height=800
        )
    with child as session:
        primary = cards(session)
        session.reload(config(PASSTHROUGH, preview=preview))
        previous_output = None

        def capture(name):
            paths = {}
            if parent is not None:
                paths["output"] = parent.capture(name + "-output")
            paths["screen_capture"] = session.capture(name + "-capture")
            return {
                "counts": {target: hardening.colors(path) for target, path in paths.items()},
                "pixels_sha256": {target: pixel_hash(path) for target, path in paths.items()},
            }

        for name, selected, axis, extent in (
            ("unblocked-control", None, "width", 680),
            ("blocked-retarget", policy, "height", 480),
            ("unblocked-retarget", None, "width", 520),
            ("blocked-again-retarget", policy, "height", 420),
        ):
            session.reload(config(PASSTHROUGH, policy=selected, preview=preview))
            resize(session, primary, axis, extent)
            observation = {"step": name, **capture(name)}
            result["checks"].append(observation)
            for target, counts in observation["counts"].items():
                hidden = (
                    bool(selected and preview)
                    if target == "output"
                    else selected == "screen-capture"
                )
                advanced = (
                    target != "output"
                    or previous_output is None
                    or observation["pixels_sha256"][target] != previous_output
                )
                if target == "output":
                    observation["output_advanced"] = advanced
                valid = privacy_valid(counts, hidden=hidden, advanced=advanced)
                if not valid:
                    # Preserve the failing immediate observation. Follow-up
                    # captures identify stale presentation; they never turn an
                    # observed privacy failure into a passing result.
                    observation["follow_up"] = []
                    for index in range(3):
                        time.sleep(0.2)
                        observation["follow_up"].append(capture(f"{name}-follow-up-{index}"))
                assert valid, (
                    name,
                    target,
                    "unexpected privacy visibility or stale output",
                    counts,
                    {"advanced": advanced},
                )
            previous_output = observation["pixels_sha256"].get("output")
        session.check_render_log()
        result["status"] = "passed"
        return result


def first_capture_after_unblock(binary, results):
    """A target first rendered after unblock must not inherit a blocked snapshot."""
    result = {"case": "first-screen-capture-after-unblock", "checks": [], "status": "failed"}
    results.append(result)
    with NestedSession(
        config(None, duration=1, policy="screen-capture"),
        binary=binary,
        width=1280,
        height=800,
    ) as session:
        primary = cards(session)
        session.reload(config(PASSTHROUGH, policy="screen-capture"))
        resize(session, primary, "width", 680)
        # Output renders throughout, but ScreenCapture has never rendered this
        # episode. Its first-use cache must not revive the blocked old snapshot.
        time.sleep(0.25)
        for name, policy, axis, extent in (
            ("first-unblocked-capture", None, "height", 480),
            ("blocked-again-capture", "screen-capture", "width", 520),
        ):
            session.reload(config(PASSTHROUGH, policy=policy))
            resize(session, primary, axis, extent)
            path = session.capture(name)
            counts = hardening.colors(path)
            result["checks"].append(
                {"step": name, "counts": counts, "pixels_sha256": pixel_hash(path)}
            )
            assert privacy_valid(counts, hidden=bool(policy)), (name, counts)
        session.check_render_log()
    result["status"] = "passed"


def background_pixels(path):
    from PIL import Image

    # This rectangle lies within both client sizes and excludes the card border.
    # Empty breakup pixels must reveal the output background, not merely change
    # the client bounds or replace a missing positive-control window.
    with Image.open(path) as image:
        area = image.convert("RGB").crop((90, 220, 390, 410))
        return sum(
            count for count, rgb in area.getcolors(area.width * area.height) if rgb == (17, 24, 39)
        )


def generated(binary, name):
    effect = replace(PRESETS[name], resize=True, resize_ms=1500, resize_strength=0.9)
    shader = resize_shader(effect)
    assert MARKER in shader
    with NestedSession(config(None, duration=1), binary=binary, width=1280, height=800) as session:
        primary = cards(session)
        baseline = session.capture("intact")
        session.reload(config(shader, duration=1500))
        resize(session, primary, "width", 700)
        time.sleep(0.6)
        during = session.capture("generated-deformation")
        counts = hardening.colors(during)
        assert counts["public"] > 10000 and counts["protected"] > 5000, counts
        intact_background = background_pixels(baseline)
        deformed_background = background_pixels(during)
        assert deformed_background > intact_background + 500, (
            "generated resize did not visibly break up the card interior",
            name,
            intact_background,
            deformed_background,
        )
        resize(session, primary, "height", 440)
        retarget = session.capture("generated-retarget")
        assert hardening.colors(retarget)["public"] > 10000
        time.sleep(1.8)
        settled = session.capture("generated-settled")
        assert background_pixels(settled) <= intact_background + 20, (
            "generated material did not settle intact"
        )
        session.check_render_log()
        return {
            "preset": name,
            "shader_sha256": hashlib.sha256(shader.encode()).hexdigest(),
            "interior_background_pixels": {
                "intact": intact_background,
                "deformed": deformed_background,
                "settled": background_pixels(settled),
            },
            "counts": counts,
        }


def checked_binary(binary, expected, unmodified=False):
    if unmodified:
        if binary is not None or expected is not None:
            raise ValueError("--unmodified cannot be combined with an explicit executable")
        baseline_spec = importlib.util.spec_from_file_location(
            "native_baseline", ROOT / "scripts/test-native-baseline.py"
        )
        baseline = importlib.util.module_from_spec(baseline_spec)
        baseline_spec.loader.exec_module(baseline)
        executable, build = baseline.baseline()
        return executable, {key: value for key, value in build.items() if key != "binary"}
    if binary is None and expected is None:
        executable, build, _ = experiment()
        return executable, {key: value for key, value in build.items() if key != "binary"}
    if binary is None or expected is None:
        raise ValueError("Explicit prototype binary requires --binary and --binary-sha256 together")
    executable = binary.resolve()
    digest = hashlib.sha256(executable.read_bytes()).hexdigest()
    if digest != expected:
        raise ValueError("Prototype executable changed from the expected SHA-256")
    return executable, {
        "scope": "explicit prototype; canonical patch manifest not asserted",
        "binary_sha256": digest,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--binary", type=Path, help="Explicit prototype executable; requires its expected hash"
    )
    parser.add_argument("--binary-sha256")
    parser.add_argument(
        "--unmodified",
        action="store_true",
        help="Use the strictly verified unmodified pinned source/binary for privacy diagnosis",
    )
    parser.add_argument(
        "--suite", choices=("all", "material", "generated", "privacy"), default="all"
    )
    parser.add_argument(
        "--output-targets",
        action="store_true",
        help="Observe child Output/debug Screencast through an owned nested parent",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.unmodified and args.suite != "privacy":
        parser.error("--unmodified supports only --suite privacy")
    binary, build = checked_binary(args.binary, args.binary_sha256, args.unmodified)
    evidence = {
        "schema": 1,
        "date": date.today().isoformat(),
        "build": build,
        "status": "failed",
        "scope": "Owned nested winit compositors, synthetic cards, IPC resize only; no physical input or desktop capture.",
        "limits": [
            "No closing snapshot continuation acceptance.",
            "No blurred-background, popup, mixed-scale, graphics-reset or PipeWire transport acceptance.",
        ],
        "sources": source_hashes(
            "scripts/test-resize-material.py",
            "scripts/test-native-baseline.py",
            "scripts/build-niri-movement.py",
            "scripts/test-pointer-hardening.py",
            "scripts/lib/nested.py",
            "scripts/lib/pointer_scene.py",
            "scripts/fixtures/pointer-card.qml",
            "niri_fx/effects.py",
            "niri_fx/shaders/resize-state.glsl",
            "niri_fx/shaders/resize.glsl",
            "niri_fx/shaders/resize-shaped.glsl",
        ),
    }
    try:
        if args.suite in ("all", "material"):
            if args.output_targets:
                with NestedSession(
                    config(None, duration=1), binary=binary, width=1440, height=1000
                ) as parent:
                    evidence["material"] = material_contract(binary, parent)
                    parent.check_render_log()
            else:
                evidence["material"] = material_contract(binary)
            print(
                "PASS retained phase/reference, shader reload/removal and episode boundaries",
                flush=True,
            )
        if args.suite in ("all", "generated"):
            evidence["generated"] = []
            for name in ("balanced", "triangle-shatter"):
                evidence["generated"].append(generated(binary, name))
            print("PASS generated fragment and triangle material deformation", flush=True)
        if args.suite in ("all", "privacy"):
            evidence["privacy"] = []
            if args.output_targets:
                with NestedSession(
                    config(None, duration=1), binary=binary, width=1440, height=1000
                ) as parent:
                    for policy in ("screen-capture", "screencast"):
                        for preview in (False, True):
                            privacy(parent, binary, policy, preview, evidence["privacy"])
                    parent.check_render_log()
            else:
                for policy in ("screen-capture", "screencast"):
                    privacy(None, binary, policy, False, evidence["privacy"])
            first_capture_after_unblock(binary, evidence["privacy"])
            print("PASS dynamic privacy during retained resize retargets", flush=True)
        evidence["status"] = "passed"
    finally:
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    main()
