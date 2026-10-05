#!/usr/bin/env python3
"""Compare two native failures against unmodified pinned Niri in owned sessions.

This diagnostic returns nonzero when either failure reproduces, while preserving
a sanitized report. A reproduced baseline is evidence against NiriFX-specific
attribution, not a passing acceptance result or proof of an upstream root cause.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.movement import experiment
from lib.native_selection import explicit_manifest
from lib.nested import NestedSession, source_hashes, wait_for
from lib.pointer import VirtualPointer, build_pointer, pointer_protocol
from lib.pointer_scene import client, config, grab, place_floating


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


builder = module("baseline_builder", "build-niri-movement.py")
hardening = module("baseline_hardening", "test-pointer-hardening.py")


class ObservedSession(NestedSession):
    """Retain the renderer identity, without adding verbose logs to other tools."""

    def launch(self, command, name, *, env=None, private_bus=False):
        if name == "niri":
            env = env | {"RUST_LOG": "warn,niri=info,smithay::backend::renderer::gles=info"}
        return super().launch(command, name, env=env, private_bus=private_bus)

    def renderer(self):
        log = (self.root / "niri.log").read_text()
        values = {}
        for key in ("Version", "Vendor", "Renderer"):
            match = re.search(rf'GL {key}: "([^"\n]+)"', log)
            if not match:
                raise RuntimeError(f"Missing GL {key} evidence")
            values[key.lower()] = match[1]
        return values


def baseline():
    selected = explicit_manifest("unmodified", repository=ROOT)
    manifest = (
        selected[1]
        if selected
        else json.loads((ROOT / "artifacts/niri-unmodified-build.json").read_text())
    )
    if manifest.get("unmodified") is not True or manifest.get("revision") != builder.REVISION:
        raise RuntimeError("Build the pinned baseline with --unmodified first")
    if any(
        field in manifest
        for field in (
            "patch_sha256",
            "pointer_patch_sha256",
            "fragment_patch_sha256",
            "swap_patch_sha256",
        )
    ):
        raise RuntimeError("Baseline manifest unexpectedly contains an experiment patch")
    # Refuse changed sources as well as replaced binaries. The empty patch stack
    # uses the builder's complete staged, unstaged and untracked change guard.
    source = selected[2] if selected else builder.BASELINE_SOURCE
    builder.apply_patches(source, builder.REVISION, [], verify_only=True)
    binary = selected[0] if selected else Path(manifest["binary"])
    if hashlib.sha256(binary.read_bytes()).hexdigest() != manifest["binary_sha256"]:
        raise RuntimeError("Baseline binary changed; rebuild it before comparison")
    return binary, manifest


def comparable_builds(unmodified, patched):
    keys = ("revision", "build_profile", "build_flags", "rustc")
    for key in keys:
        if key not in unmodified or key not in patched or unmodified[key] != patched[key]:
            raise RuntimeError(f"Builds differ or lack {key}; rebuild both with identical options")
    return {key: unmodified[key] for key in keys}


def observation(parent, session, name):
    # Capture only the two owned outputs. A public card is required in each, so
    # an empty output cannot look like a successfully cleared closing snapshot.
    values = {
        "output": hardening.colors(parent.capture(name + "-output")),
        "screen_capture": hardening.colors(session.capture(name + "-capture")),
    }
    for target, counts in values.items():
        assert counts["public"] > 10000, (target, "missing public control", counts)
    return values


def cleared(counts):
    return counts["protected"] == 0 and counts["redaction"] < 10000


def pixel_hash(path):
    """Compare decoded pixels, independent of PNG container metadata."""
    from PIL import Image

    with Image.open(path) as image:
        return hashlib.sha256(image.convert("RGB").tobytes()).hexdigest()


def output_probe(binary, protocol, enabled, preview):
    child_config = config(hardening.WOBBLE if enabled else None, close_ms=1600)
    if preview:
        child_config += 'debug { preview-render "screencast"; }\n'
    with ObservedSession(config(None), binary=binary, width=1440, height=1000) as parent:
        with patch.dict(os.environ, parent.env, clear=True):
            child = ObservedSession(child_config, binary=binary, width=1280, height=800)
        with child as session:
            parent.focus()
            helper = build_pointer(session.root / "pointer", protocol)
            _, primary = client(session, "Protected", hardening.PROTECTED)
            _, secondary = client(session, "Public", hardening.PUBLIC)
            place_floating(session, primary, x=60)
            place_floating(session, secondary, x=740)
            controls = observation(parent, session, "unblocked")
            assert all(value["protected"] > 10000 for value in controls.values()), controls
            with VirtualPointer(session, helper) as pointer:
                start = grab(session, pointer, primary)
                pointer.path((start, (start[0] + 100, start[1] + 50)), 0.2)
                session.reload(
                    child_config
                    + 'window-rule { match title=r#"^NiriFX pointer / Protected"#; '
                    + 'block-out-from "screen-capture"; }\n'
                )
                protected = observation(parent, session, "protected-drag")
                assert protected["screen_capture"]["protected"] == 0, protected
                expected = protected["output"]["protected"]
                assert expected == 0 if preview else expected > 10000, protected
                closed_at = time.monotonic()
                session.msg("action", "close-window", "--id", str(primary))
                wait_for(
                    lambda: all(w["id"] != primary for w in session.windows()),
                    "closed protected client",
                )
                closing = observation(parent, session, "closing")
                assert closing["screen_capture"]["redaction"] > 10000, closing
                pointer.release()
                # The close duration is 1.6 s. Give presentation another second
                # before sampling six fresh pairs across a further two seconds.
                time.sleep(2.6)
                settled = []
                for index in range(6):
                    started = round((time.monotonic() - closed_at) * 1000)
                    sample = observation(parent, session, f"settled-{index}")
                    finished = round((time.monotonic() - closed_at) * 1000)
                    sample.update(
                        begin_ms_after_close=started,
                        end_ms_after_close=finished,
                        output_pixels_sha256=pixel_hash(
                            parent.root / f"settled-{index}-output.png"
                        ),
                        capture_pixels_sha256=pixel_hash(
                            session.root / f"settled-{index}-capture.png"
                        ),
                    )
                    settled.append(sample)
                    if index != 5:
                        time.sleep(0.4)
                direct_clears = all(cleared(pair["screen_capture"]) for pair in settled)
                output_clears = all(cleared(pair["output"]) for pair in settled)
                assert direct_clears, ("Direct capture did not clear", settled)
                renderer = session.renderer()
                assert parent.renderer() == renderer, "Parent and child use different renderers"
                hardening.click(session, pointer, secondary, 1)
                after_click = observation(parent, session, "after-survivor-click")
            session.check_render_log()
        parent.check_render_log()
    return {
        "target": "debug Screencast" if preview else "Output",
        "renderer": renderer,
        "unblocked_controls": controls,
        "protected_drag": protected,
        "closing_snapshot": closing,
        "close_duration_ms": 1600,
        "settled_samples": settled,
        "parent_settled_frames_identical": len(
            {sample["output_pixels_sha256"] for sample in settled}
        )
        == 1,
        "after_survivor_click": after_click,
        "direct_capture_cleared": direct_clears,
        "parent_output_cleared": output_clears,
        "stale_parent_output_reproduced": not output_clears,
    }


def disconnect_probe(binary, protocol, enabled, *, overlapping=False):
    renderers = []

    class DisconnectSession(ObservedSession):
        def __exit__(self, exc_type, *args):
            try:
                if exc_type is None:
                    renderers.append(self.renderer())
            finally:
                # Missing renderer evidence must fail without leaving owned
                # compositors and clients running after the diagnostic exits.
                super().__exit__(exc_type, *args)

    with patch.object(hardening, "NestedSession", DisconnectSession):
        probe = hardening.overlapping_pointers if overlapping else hardening.disconnected_pointer
        result = probe(binary, protocol, enabled)
    assert renderers and all(value == renderers[0] for value in renderers), "Probe changed renderer"
    result["renderer"] = renderers[0]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pointer-protocol", type=Path)
    parser.add_argument(
        "--probe", choices=("all", "disconnect", "overlap", "output"), default="all"
    )
    parser.add_argument("--report", type=Path, default=ROOT / "artifacts/native-baseline.json")
    args = parser.parse_args()
    unmodified, base_build = baseline()
    patched, fx_build, _ = experiment(pointer_wobble=True)
    settings = comparable_builds(base_build, fx_build)
    protocol = pointer_protocol(args.pointer_protocol)
    evidence = {
        "schema": 1,
        "date": date.today().isoformat(),
        "build": settings,
        "binary_sha256": {
            "unmodified": base_build["binary_sha256"],
            "patched": fx_build["binary_sha256"],
        },
        "sources": source_hashes(
            "scripts/test-native-baseline.py",
            "scripts/build-niri-movement.py",
            "scripts/test-pointer-hardening.py",
            "scripts/lib/pointer_scene.py",
            "scripts/lib/pointer.py",
            "scripts/lib/nested.py",
            "scripts/fixtures/pointer.c",
            "scripts/fixtures/pointer-card.qml",
            "experimental/niri-movement.patch",
            "experimental/niri-pointer-wobble.patch",
        ),
        "scope": "Sequential owned winit sessions on the same host; synthetic opaque clients only.",
        "limits": [
            "Baseline reproduction does not isolate compositor, driver or harness root cause.",
            "Parent grim observes child Output, or its debug Screencast override; no PipeWire transport.",
            "No physical device removal, physical displays, suspend or graphics reset acceptance.",
        ],
        "results": [],
    }
    defect = False
    renderer = None
    for name, binary, enabled in (
        ("unmodified", unmodified, False),
        ("patched-disabled", patched, False),
        ("patched-enabled", patched, True),
    ):
        result = {"variant": name}
        if args.probe in ("all", "disconnect"):
            result["disconnect"] = disconnect_probe(binary, protocol, enabled)
            defect |= result["disconnect"]["unpressed_motion_moved_window"]
            current = result["disconnect"]["renderer"]
            if renderer is not None:
                assert current == renderer, "Comparison changed renderer"
            renderer = current
            print(
                f"{name}: retained grab={result['disconnect']['unpressed_motion_moved_window']}",
                flush=True,
            )
        if args.probe in ("all", "output"):
            result["output"] = []
            for preview in (False, True):
                observation = output_probe(binary, protocol, enabled, preview)
                defect |= observation["stale_parent_output_reproduced"]
                if renderer is not None:
                    assert observation["renderer"] == renderer, "Comparison changed renderer"
                renderer = observation["renderer"]
                result["output"].append(observation)
                print(
                    f"{name}: {observation['target']} stale={observation['stale_parent_output_reproduced']}",
                    flush=True,
                )
        if args.probe in ("all", "overlap"):
            result["overlap"] = disconnect_probe(binary, protocol, enabled, overlapping=True)
            defect |= bool(result["overlap"]["failed_controls"])
            current = result["overlap"]["renderer"]
            if renderer is not None:
                assert current == renderer, "Comparison changed renderer"
            renderer = current
            print(f"{name}: overlap failures={result['overlap']['failed_controls']}", flush=True)
        evidence["results"].append(result)
        # Preserve complete variants even if a later setup or control fails.
        args.report.write_text(json.dumps(evidence, indent=2) + "\n")
    evidence["defect_reproduced"] = defect
    evidence["completed_comparison"] = True
    args.report.write_text(json.dumps(evidence, indent=2) + "\n")
    return 1 if defect else 0


if __name__ == "__main__":
    raise SystemExit(main())
