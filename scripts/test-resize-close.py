#!/usr/bin/env python3
"""Observe resize-to-close continuity in owned synthetic nested sessions.

Diagnostic bands recover material phase/references through closing opacity. Raw
content checks keep protected/public target evidence separate from diagnostics.
Only owned outputs are captured; debug Screencast is not PipeWire transport.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import shlex
import subprocess
import sys
import time
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.nested import NestedSession, source_hashes, wait_for
from lib.pointer_scene import BASE, client, place_floating

from niri_fx.effects import resize_shader
from niri_fx.presets import PRESETS

spec = importlib.util.spec_from_file_location(
    "resize_material", ROOT / "scripts/test-resize-material.py"
)
material = importlib.util.module_from_spec(spec)
spec.loader.exec_module(material)
hardening = material.hardening
BACKGROUND = (17, 24, 39)
CALIBRATION = (240, 220, 30)
DURATION = 3000
CLOSE_MS = 2400
SILHOUETTE_PIXEL_LIMIT = 4
FIRST_FRAME_ORACLE = {
    "ordinary_channel_tolerance": 1,
    "stationary_channel_tolerance": 0,
    "silhouette_radius_pixels": 1,
    "silhouette_exception_limit": SILHOUETTE_PIXEL_LIMIT,
    "interior_exception_limit": 0,
    "measured_normalized_coordinate_delta": {"x": 2**-24, "y": 2**-23},
    "basis": "Frozen mapped/closed GPU coordinate probes retained identical material state and UV matrices; the framebuffer projection changed. The pixel budget is a bounded acceptance limit, not a universal rasterization guarantee.",
}
DIAGNOSTIC = (
    material.MARKER
    + """
vec4 resize_color(vec3 coords_curr_geo, vec3 size_curr_geo) {
#ifdef NIRIFX_RESIZE_CONTINUITY_V1
    if (niri_resize_retained > 0.5) {
        if (coords_curr_geo.x < 0.125)
            return vec4(240.0 / 255.0, 220.0 / 255.0, 30.0 / 255.0, 1.0);
        if (coords_curr_geo.x < 0.375)
            return vec4(16.0 / 255.0, niri_resize_reference_from_size / 1024.0, 1.0);
        if (coords_curr_geo.x < 0.625)
            return vec4(32.0 / 255.0, niri_resize_reference_to_size / 1024.0, 1.0);
        return vec4(0.25 + 0.5 * niri_clamped_progress,
                    niri_resize_reference_size / 1024.0, 1.0);
    }
#endif
    return vec4(1.0, 0.0, 0.0, 1.0);
}
"""
)


def config(
    shader,
    *,
    duration=DURATION,
    close_ms=CLOSE_MS,
    policy=None,
    preview=False,
    opening=False,
    movement=False,
    disabled=None,
    slowdown=None,
    decorated=False,
):
    base = BASE
    if decorated:
        base = base.replace(
            "border { off; }",
            """border { width 4; active-color "#edf5ff"; inactive-color "#edf5ff"; }
    shadow { on; softness 20; spread 5; offset x=6 y=8; color "#00000080"; }""",
        )
    text = base + "animations {\n"
    if slowdown is not None:
        text += f"    slowdown {slowdown}\n"
    if disabled == "global":
        text += "    off\n"
    for action, enabled in (("open", opening), ("movement", movement)):
        if enabled:
            function = "open_color" if action == "open" else "move_color"
            shader_text = f"vec4 {function}(vec3 coords_geo, vec3 size_geo) {{ return texture2D(niri_tex, (niri_geo_to_tex * coords_geo).xy); }}"
            text += f'    window-{action} {{ duration-ms 3000; curve "linear"; custom-shader r#"{shader_text}"#; }}\n'
        else:
            text += f"    window-{action} {{ off; }}\n"
    text += f'    window-close {{ {"off; " if disabled == "close" else ""}duration-ms {close_ms}; curve "linear"; }}\n'
    text += f'    window-resize {{ {"off; " if disabled == "resize" else ""}duration-ms {duration}; curve "linear";\n'
    if shader:
        text += f'        custom-shader r#"{shader}"#\n'
    text += "    }\n}\n"
    if opening:
        text += """window-rule {
    match title=r#"^NiriFX pointer / Protected"#
    open-floating true
    default-column-width { fixed 400; }
    default-window-height { fixed 360; }
    default-floating-position x=40 y=120 relative-to="top-left"
}\n"""
    if policy:
        text += (
            'window-rule { match title=r#"^NiriFX pointer / Protected"#; '
            + f'block-out-from "{policy}"; }}\n'
        )
    if preview:
        text += 'debug { preview-render "screencast"; }\n'
    return text


def decode(path, *, original=(400, 360), reference=(700, 360)):
    """Decode retained state after correcting the independent closing fade."""
    from PIL import Image

    with Image.open(path) as image:
        image = image.convert("RGB")
        colors = image.getcolors(image.width * image.height)
        candidates = []
        for count, rgb in colors:
            alpha = (rgb[0] - BACKGROUND[0]) / (CALIBRATION[0] - BACKGROUND[0])
            if (
                count > 1500
                and 0.3 < alpha <= 1.01
                and all(
                    abs(rgb[i] - (BACKGROUND[i] + alpha * (CALIBRATION[i] - BACKGROUND[i]))) <= 2
                    for i in (1, 2)
                )
            ):
                candidates.append((count, alpha, rgb))
        assert candidates, "missing resize calibration; continuation missing or too faint"
        _, alpha, calibration = max(candidates)

        def unblend(rgb):
            return tuple(
                background + (value - background) / alpha
                for value, background in zip(rgb, BACKGROUND, strict=True)
            )

        normalized = [(count, rgb, unblend(rgb)) for count, rgb in colors]
        accepted = {calibration}
        for red, size in ((16, original), (32, reference)):
            expected = (red, *(value * 255 / 1024 for value in size))
            matches = [
                (count, rgb)
                for count, rgb, raw in normalized
                if all(abs(a - b) <= 3 for a, b in zip(raw, expected, strict=True))
            ]
            assert sum(count for count, _ in matches) > 2000, (
                "changed material reference",
                red,
                size,
            )
            accepted.update(rgb for _, rgb in matches)
        green, blue = (value * 255 / 1024 for value in reference)
        phases = [
            (count, rgb, raw)
            for count, rgb, raw in normalized
            if 62 <= raw[0] <= 194 and abs(raw[1] - green) <= 3 and abs(raw[2] - blue) <= 3
        ]
        assert phases and max(phases)[0] > 3000, "missing retained phase band"
        count, rgb, raw = max(phases)
        accepted.add(rgb)
        raw_pixels = image.tobytes()
        mask = Image.frombytes(
            "L",
            image.size,
            bytes(
                255 if rgb in accepted else 0
                for rgb in zip(raw_pixels[::3], raw_pixels[1::3], raw_pixels[2::3], strict=True)
            ),
        )
        bounds = mask.getbbox()
        return {
            "phase": (raw[0] / 255 - 0.25) / 0.5,
            "alpha": alpha,
            "phase_pixels": count,
            "from": list(original),
            "reference": list(reference),
            "bounds": list(bounds),
            "size": [bounds[2] - bounds[0], bounds[3] - bounds[1]],
        }


def continues(before, after, elapsed):
    material.phase_continues(before, after, elapsed, DURATION / 1000)
    assert before["from"] == after["from"] and before["reference"] == after["reference"]


def closed(session, primary):
    session.msg("action", "close-window", "--id", str(primary))
    wait_for(
        lambda: all(window["id"] != primary for window in session.windows()), "owned client unmap"
    )


def capture(session, parent, name):
    paths = {}
    if parent:
        paths["output"] = parent.capture(name + "-output")
    paths["screen_capture"] = session.capture(name + "-capture")
    return paths


def child_session(binary, parent, text):
    with patch.dict(os.environ, parent.env if parent else os.environ.copy(), clear=True):
        return NestedSession(text, binary=binary, width=1280, height=800)


def diagnostic(binary, parent, results, overlap=None):
    result = {
        "case": "material" + (f"-{overlap}" if overlap else ""),
        "checks": [],
        "status": "failed",
    }
    results.append(result)
    with child_session(binary, parent, config(None, duration=1)) as session:
        flags = {"opening": overlap == "open", "movement": overlap == "movement"}
        if overlap == "open":
            _, public = client(session, "Public", hardening.PUBLIC)
            place_floating(session, public, x=800, y=120, width=400, height=500)
            session.reload(config(DIAGNOSTIC, **flags))
            _, primary = client(session, "Protected", hardening.PROTECTED)
            wait_for(
                lambda: material.window(session, primary)["layout"]["window_size"] == [400, 360],
                "initial opening fixture dimensions",
            )
        else:
            primary = material.cards(session)
            session.reload(config(DIAGNOSTIC, **flags))
        material.resize(session, primary, "width", 700)
        time.sleep(0.3)
        records = result["checks"]

        def sample(name):
            before = time.monotonic()
            paths = capture(session, parent, name)
            now = time.monotonic()
            assert now - before < 0.8, ("capture exceeded observation window", name, now - before)
            entry = {
                "step": name,
                "time": (before + now) / 2,
                "targets": {target: decode(path) for target, path in paths.items()},
                "pixels_sha256": {
                    target: material.pixel_hash(path) for target, path in paths.items()
                },
            }
            if records:
                for target, current in entry["targets"].items():
                    continues(
                        records[-1]["targets"][target], current, entry["time"] - records[-1]["time"]
                    )
            records.append(entry)
            return entry

        sample("initial-resize")
        material.resize(session, primary, "width", 520)
        material.resize(session, primary, "height", 460)
        session.reload(config(material.REPLACEMENT, **flags))
        material.resize(session, primary, "width", 640)
        if overlap == "movement":
            session.msg(
                "action", "move-floating-window", "--id", str(primary), "--x", "120", "--y", "150"
            )
        before = sample("retarget-reload-before-close")
        closed(session, primary)
        time.sleep(0.12)
        sample("early-close")
        time.sleep(0.25)
        after = sample("continuing-close")
        for target in before["targets"]:
            initial, final = before["targets"][target], after["targets"][target]
            assert final["phase"] - initial["phase"] > 0.05, (
                "material phase froze during close",
                target,
                initial,
                final,
            )
            assert (
                max(abs(a - b) for a, b in zip(initial["size"], final["size"], strict=True)) > 5
            ), ("closing resize geometry froze", target, initial, final)
            assert after["pixels_sha256"][target] != before["pixels_sha256"][target], (
                "presented output froze"
            )
        session.reload(config(None, **flags))
        sample("removed-shader-during-close")
        time.sleep(CLOSE_MS / 1000 + 0.3)
        for target, path in capture(session, parent, "after-close").items():
            counts = hardening.colors(path)
            assert counts["public"] > 10000 and counts["protected"] == 0, (target, counts)
            try:
                decode(path)
            except AssertionError:
                pass
            else:
                raise AssertionError("retained material survived completed close")
        origin = records[0]["time"]
        for entry in records:
            entry["elapsed_s"] = round(entry.pop("time") - origin, 4)
        session.check_render_log()
        result["status"] = "passed"


def privacy(binary, parent, results, policy, preview):
    result = {
        "case": "privacy",
        "policy": policy,
        "preview_screencast": preview,
        "checks": [],
        "status": "failed",
    }
    results.append(result)
    with child_session(binary, parent, config(None, duration=1, preview=preview)) as session:
        primary = material.cards(session)
        session.reload(config(material.PASSTHROUGH, preview=preview))
        material.resize(session, primary, "width", 700)
        time.sleep(0.2)
        for name, selected in (("visible-retarget", None), ("blocked-before-close", policy)):
            session.reload(config(material.PASSTHROUGH, policy=selected, preview=preview))
            material.resize(session, primary, "height", 460 if selected else 420)
            paths = capture(session, parent, name)
            counts = {target: hardening.colors(path) for target, path in paths.items()}
            result["checks"].append({"step": name, "counts": counts})
            for target, value in counts.items():
                hidden = bool(
                    selected and (preview if target == "output" else policy == "screen-capture")
                )
                assert material.privacy_valid(value, hidden=hidden), (name, target, value)
        closed(session, primary)
        for index in range(2):
            time.sleep(0.12)
            paths = capture(session, parent, f"protected-close-{index}")
            counts = {target: hardening.colors(path) for target, path in paths.items()}
            result["checks"].append({"step": f"protected-close-{index}", "counts": counts})
            for target, value in counts.items():
                hidden = preview if target == "output" else policy == "screen-capture"
                assert material.privacy_valid(value, hidden=hidden), (target, value)
                if hidden:
                    assert value["redaction"] > 10000, (
                        "missing redacted close snapshot",
                        target,
                        value,
                    )
        time.sleep(CLOSE_MS / 1000 + 0.3)
        for target, path in capture(session, parent, "privacy-settled").items():
            counts = hardening.colors(path)
            assert (
                counts["public"] > 10000
                and counts["protected"] == 0
                and counts["redaction"] < 10000
            ), (target, counts)
        session.check_render_log()
        result["status"] = "passed"


def margin_cards(session, *, popup=False):
    build = session.root / "margin-client"
    build.mkdir()
    protocols = subprocess.check_output(
        ["pkg-config", "--variable=pkgdatadir", "wayland-protocols"], text=True
    ).strip()
    protocol = Path(protocols) / "stable/xdg-shell/xdg-shell.xml"
    for kind, target in (("client-header", "xdg-shell.h"), ("private-code", "xdg-shell.c")):
        subprocess.run(["wayland-scanner", kind, str(protocol), str(build / target)], check=True)
    flags = shlex.split(
        subprocess.check_output(["pkg-config", "--cflags", "--libs", "wayland-client"], text=True)
    )
    executable = build / "margin-card"
    subprocess.run(
        [
            "cc",
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(build),
            str(ROOT / "scripts/fixtures/resize-margins.c"),
            str(build / "xdg-shell.c"),
            "-o",
            str(executable),
            *flags,
        ],
        check=True,
    )
    session.launch(
        [str(executable)], "margin-card", env=session.env | ({"NIRIFX_POPUP": "1"} if popup else {})
    )
    primary = wait_for(
        lambda: next(
            (
                window["id"]
                for window in session.windows()
                if window["title"] == "NiriFX pointer / Protected / geometry margins"
            ),
            None,
        ),
        "owned margin client",
    )
    _, public = client(session, "Public", hardening.PUBLIC)
    place_floating(session, primary, x=40, y=120, width=400, height=360)
    place_floating(session, public, x=800, y=120, width=400, height=500)
    assert (
        "NIRIFX_WINDOW_GEOMETRY x=24 y=24 width=400 height=360"
        in (session.root / "margin-card.log").read_text()
    )
    if popup:
        assert "NIRIFX_POPUP_CONFIGURED" in (session.root / "margin-card.log").read_text()
    return primary


def generated(binary, results, name, *, margins=False, popup=False, decorated=False):
    result = {
        "case": "generated",
        "preset": name,
        "explicit_geometry_origin": [24, 24] if margins else [0, 0],
        "popup": popup,
        "native_border_and_shadow": decorated,
        "checks": [],
        "status": "failed",
    }
    results.append(result)
    effect = replace(PRESETS[name], resize=True, resize_ms=1500, resize_strength=0.9)
    shader = resize_shader(effect)
    result["shader_sha256"] = hashlib.sha256(shader.encode()).hexdigest()
    with NestedSession(config(None, duration=1), binary=binary, width=1280, height=800) as session:
        primary = margin_cards(session, popup=popup) if margins else material.cards(session)
        session.reload(config(shader, duration=1500, decorated=decorated))
        material.resize(session, primary, "width", 700)
        time.sleep(0.35)
        material.resize(session, primary, "height", 460)
        # Freeze compositor time rather than guessing which two asynchronous
        # captures represent the unmap boundary. The close path must preserve
        # the already rendered shape and content without a second deformation.
        session.reload(config(shader, duration=1500, slowdown=2147483647, decorated=decorated))
        before = session.capture("generated-before-close")
        stationary = session.capture("generated-frozen-control")
        first_frame_difference(
            before, stationary, stationary=True, evidence=result.setdefault("frozen_control", {})
        )
        closed(session, primary)
        early = session.capture("generated-early-close")
        first_frame_difference(
            before, early, allow_silhouette=True, evidence=result.setdefault("unmap_boundary", {})
        )
        if popup:
            for path in (before, early):
                assert material.uniform_pixels(path, (239, 212, 107)) > 5000, (
                    "popup was not visible at handoff"
                )
        session.reload(config(shader, duration=1500, decorated=decorated))
        time.sleep(0.2)
        later = session.capture("generated-later-close")
        for step, path in (("before", before), ("early", early), ("later", later)):
            counts = hardening.colors(path)
            result["checks"].append(
                {"step": step, "counts": counts, "pixels_sha256": material.pixel_hash(path)}
            )
            assert counts["protected"] > 5000 and counts["public"] > 10000, (name, step, counts)
        assert result["checks"][-1]["pixels_sha256"] != result["checks"][0]["pixels_sha256"], (
            "generated close output froze after clock resumed"
        )
        time.sleep(CLOSE_MS / 1000 + 0.3)
        counts = hardening.colors(session.capture("generated-settled"))
        assert counts["protected"] == 0 and counts["public"] > 10000, counts
        session.check_render_log()
        result["status"] = "passed"


def first_frame_difference(
    before, after, *, stationary=False, allow_silhouette=False, evidence=None
):
    """Bound framebuffer interpolation differences without allowing interior drift.

    Frozen 24-bit coordinate probes measured at most 2^-23 normalized movement
    between output and local-framebuffer interpolation, with identical uniforms.
    A discontinuous fragment silhouette can amplify that into a full color step.
    The four-pixel cap is an acceptance limit, not a mathematical GPU guarantee.
    Both frames must have stable foreground AND background neighbors within one
    pixel; an interior hole, color change, or translated edge cannot use this rule.
    """
    from PIL import Image, ImageChops

    with Image.open(before) as first, Image.open(after) as second:
        assert first.size == second.size
        first, second = first.convert("RGB"), second.convert("RGB")
        difference = ImageChops.difference(first, second)
        colors = difference.getcolors(difference.width * difference.height)
        maximum = max(max(rgb) for _, rgb in colors)
        changed = sum(count for count, rgb in colors if max(rgb) > 1)
        exceptions = []

        def background(rgb):
            return (
                max(abs(channel - base) for channel, base in zip(rgb, BACKGROUND, strict=True)) <= 1
            )

        x0, y0, x1, y1 = difference.getbbox() or (0, 0, 0, 0)
        for y in range(y0, y1):
            for x in range(x0, x1):
                delta = max(difference.getpixel((x, y)))
                if delta <= 1:
                    continue
                left, right = first.getpixel((x, y)), second.getpixel((x, y))
                neighbors = [
                    (nx, ny)
                    for ny in range(max(0, y - 1), min(first.height, y + 2))
                    for nx in range(max(0, x - 1), min(first.width, x + 2))
                    if (nx, ny) != (x, y) and max(difference.getpixel((nx, ny))) <= 1
                ]
                boundary = background(left) != background(right) and all(
                    {background(frame.getpixel(point)) for point in neighbors} == {False, True}
                    for frame in (first, second)
                )
                exceptions.append(
                    {
                        "coordinate": [x, y],
                        "before": list(left),
                        "after": list(right),
                        "maximum_channel_difference": delta,
                        "silhouette_boundary_in_both_frames": boundary,
                    }
                )
        report = {
            "changed_pixels_over_one_channel_step": changed,
            "maximum_channel_difference": maximum,
            "stationary_exact": stationary,
            "allowed_silhouette_exceptions": SILHOUETTE_PIXEL_LIMIT
            if allow_silhouette and not stationary
            else 0,
            "exceptional_pixel_count": len(exceptions),
            "interior_exception_count": sum(
                not item["silhouette_boundary_in_both_frames"] for item in exceptions
            ),
            "exceptional_pixels": exceptions,
        }
        report["accepted"] = (
            maximum == 0
            if stationary
            else changed <= report["allowed_silhouette_exceptions"]
            and report["interior_exception_count"] == 0
        )
        if evidence is not None:
            evidence.update(report)
        if stationary:
            assert report["accepted"], ("stationary control changed", report)
        else:
            assert report["accepted"], ("resize-to-close first frame changed", report)
        return report


def disable_during_close(binary, results, mode):
    result = {"case": f"disable-{mode}", "checks": [], "status": "failed"}
    results.append(result)
    with NestedSession(config(None, duration=1), binary=binary, width=1280, height=800) as session:
        primary = material.cards(session)
        session.reload(config(DIAGNOSTIC))
        material.resize(session, primary, "width", 700)
        time.sleep(0.25)
        closed(session, primary)
        before = decode(session.capture("before-disable"))
        result["checks"].append({"step": "before-disable", **before})
        session.reload(config(DIAGNOSTIC, disabled=mode))
        path = session.capture("after-disable")
        counts = hardening.colors(path)
        result["checks"].append({"step": "after-disable", "counts": counts})
        assert counts["public"] > 10000 and counts["protected"] == 0, counts
        try:
            decode(path)
        except AssertionError:
            pass
        else:
            raise AssertionError(f"{mode} Off left a closing resize material visible")
        session.check_render_log()
        result["status"] = "passed"


def content_bounds(path, *, redacted=False):
    from PIL import Image

    with Image.open(path) as image:
        image = image.convert("RGB")
        raw = image.tobytes()

        def selected(rgb):
            r, g, b = rgb
            return (
                (r < 9 and g < 13 and b < 20)
                if redacted
                else (r - g > 25 and b - g > 15 and r - b > 15)
            )

        mask = Image.frombytes(
            "L",
            image.size,
            bytes(
                255 if selected(rgb) else 0
                for rgb in zip(raw[::3], raw[1::3], raw[2::3], strict=True)
            ),
        )
        bounds = mask.getbbox()
        assert bounds, "missing closing content bounds"
        return list(bounds)


def scale_change(binary, results, protected):
    result = {
        "case": "same-context-scale-change",
        "protected": protected,
        "checks": [],
        "status": "failed",
    }
    results.append(result)
    policy = "screen-capture" if protected else None
    with NestedSession(config(None, duration=1), binary=binary, width=1280, height=800) as session:
        primary = material.cards(session)
        session.reload(config(material.PASSTHROUGH, policy=policy))
        material.resize(session, primary, "width", 700)
        time.sleep(0.3)
        frozen = config(material.PASSTHROUGH, policy=policy, slowdown=2147483647)
        session.reload(frozen)
        closed(session, primary)
        before = session.capture("scale-before")
        initial = content_bounds(before, redacted=protected)
        session.reload(frozen + 'output "winit" { scale 1.25; }\n')
        after = session.capture("scale-after")
        current = content_bounds(after, redacted=protected)
        counts = hardening.colors(after)
        result["checks"].append(
            {"scale": 1.25, "before_bounds": initial, "after_bounds": current, "counts": counts}
        )
        assert material.privacy_valid(counts, hidden=protected), counts
        assert all(
            abs(actual - expected * 1.25) <= 3
            for actual, expected in zip(current, initial, strict=True)
        ), ("scale fallback cropped or displaced frozen content", initial, current)
        session.reload(
            config(material.PASSTHROUGH, policy=policy) + 'output "winit" { scale 1.25; }\n'
        )
        time.sleep(CLOSE_MS / 1000 + 0.3)
        counts = hardening.colors(session.capture("scale-settled"))
        assert (
            counts["protected"] == 0 and counts["redaction"] < 10000 and counts["public"] > 10000
        ), counts
        session.check_render_log()
        result["status"] = "passed"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path)
    parser.add_argument("--binary-sha256")
    parser.add_argument(
        "--suite",
        choices=(
            "all",
            "material",
            "privacy",
            "generated",
            "margins",
            "popup",
            "scale",
            "decorated",
        ),
        default="all",
    )
    parser.add_argument("--output-targets", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    binary, build = material.checked_binary(args.binary, args.binary_sha256)
    evidence = {
        "schema": 1,
        "date": str(date.today()),
        "build": build,
        "status": "failed",
        "cases": [],
        "first_frame_oracle": FIRST_FRAME_ORACLE,
        "scope": "owned nested synthetic clients; optional parent Output/debug Screencast, not PipeWire transport",
        "sources": source_hashes(
            "scripts/test-resize-close.py",
            "scripts/test-resize-material.py",
            "scripts/test-pointer-hardening.py",
            "scripts/test-native-baseline.py",
            "scripts/build-niri-movement.py",
            "scripts/lib/nested.py",
            "scripts/lib/pointer_scene.py",
            "scripts/fixtures/pointer-card.qml",
            "scripts/fixtures/resize-margins.c",
        ),
    }
    try:
        if args.suite in ("all", "material"):
            diagnostic(binary, None, evidence["cases"])
            diagnostic(binary, None, evidence["cases"], overlap="open")
            diagnostic(binary, None, evidence["cases"], overlap="movement")
            for mode in ("resize", "close", "global"):
                disable_during_close(binary, evidence["cases"], mode)
        if args.suite in ("all", "generated"):
            for name in ("balanced", "slide-apart", "spring-wobble"):
                generated(binary, evidence["cases"], name)
        if args.suite in ("all", "margins"):
            for name in ("balanced", "slide-apart", "spring-wobble"):
                generated(binary, evidence["cases"], name, margins=True)
        if args.suite in ("all", "popup"):
            generated(binary, evidence["cases"], "balanced", margins=True, popup=True)
        if args.suite in ("all", "decorated"):
            generated(binary, evidence["cases"], "balanced", decorated=True)
        if args.suite in ("all", "privacy"):
            for policy in ("screen-capture", "screencast"):
                privacy(binary, None, evidence["cases"], policy, False)
        if args.suite in ("all", "scale"):
            for protected in (False, True):
                scale_change(binary, evidence["cases"], protected)
        if args.output_targets:
            # Use a strictly verified stock parent to isolate child presentation.
            parent_binary, evidence["parent_build"] = material.checked_binary(None, None, True)
            with NestedSession(
                config(None, duration=1), binary=parent_binary, width=1440, height=1000
            ) as parent:
                if args.suite in ("all", "material"):
                    diagnostic(binary, parent, evidence["cases"])
                if args.suite in ("all", "privacy"):
                    for policy in ("screen-capture", "screencast"):
                        for preview in (False, True):
                            privacy(binary, parent, evidence["cases"], policy, preview)
        evidence["status"] = "passed"
    finally:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"PASS resize-to-close {args.suite}; evidence: {args.report}")


if __name__ == "__main__":
    main()
