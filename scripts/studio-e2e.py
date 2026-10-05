#!/usr/bin/env python3
"""Exercise the actual Studio CLI, browser and helper against temporary state."""

import argparse
import json
import selectors
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=("all", "studio", "shapes", "motion"), default="all")
    parser.add_argument("--shape-aspect", choices=("0.25", "1", "4"))
    args = parser.parse_args(argv)
    if args.shape_aspect is not None and args.suite != "shapes":
        parser.error("--shape-aspect requires --suite shapes")
    return args


def main():
    args = parse_args()
    saves = args.suite in {"all", "studio"}
    with tempfile.TemporaryDirectory(prefix="nirifx-e2e-") as directory:
        root = Path(directory)
        config = root / "config.kdl"
        config.write_text("animations {}\n")
        registry = root / "presets.json"
        helper = root / "scripts/niri-config.py"
        helper.parent.mkdir()
        base_types = {
            "window-resize": {"duration-ms": 210, "curve": "ease-out-cubic"},
            "workspace-switch": {"spring": [0.9, 700, 0.0001]},
        }
        source = {"active": "fixture", "presets": [{"id": "fixture", "types": base_types}]}
        helper.write_text("print(" + repr(json.dumps(source)) + ")\n")
        unrelated = {"id": "someone-elses-preset", "name": "Keep me"}
        registry.write_text(json.dumps({"presets": [unrelated]}))
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "niri_fx",
                "studio",
                "--edit",
                "--config",
                str(config),
                "--port",
                "0",
                "--no-browser",
                "--registry",
                str(registry),
                "--state",
                str(root / "studio-state"),
                "--inir-root",
                str(root),
            ],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                if not selector.select(timeout=20):
                    raise RuntimeError("Studio did not start within 20 seconds")
                line = process.stdout.readline().strip()
            if not line.startswith("NiriFX Studio: http://127.0.0.1:"):
                raise RuntimeError("Studio failed to return its local session URL")
            command = [
                "node",
                "scripts/browser-smoke.mjs",
                line.removeprefix("NiriFX Studio: "),
                "--suite",
                args.suite,
            ]
            if args.shape_aspect is not None:
                command.extend(["--shape-aspect", args.shape_aspect])
            if saves:
                command.append("--save-test")
            subprocess.run(
                command,
                cwd=ROOT,
                check=True,
                # Software WebGL also renders enlarged reference searches for
                # every shape/aspect. Slow shared CI runners need a bounded
                # whole-suite budget beyond the per-request browser deadline.
                timeout=900,
            )
            presets = json.loads(registry.read_text())["presets"]
            assert unrelated in presets, "Saving replaced an unrelated preset"
            if not saves:
                assert presets == [unrelated], "Rendering checks unexpectedly changed the registry"
                print(f"PASS: isolated {args.suite} rendering; registry unchanged")
                return
            for family in (
                "fragments",
                "slices",
                "elastic",
                "dissolve",
                "iris",
                "pixels",
                "wisps",
                "distortion",
                "hexagons",
            ):
                saved = next(p for p in presets if p["id"] == f"niri-fx-custom-browser-{family}")
                assert saved["effect"]["family"] == family
                assert not saved["effect"]["resize"]
                for kind, value in base_types.items():
                    assert saved["types"][kind] == value, kind
            profile = next(p for p in presets if p["id"] == "niri-fx-custom-browser-profile")
            assert "elastic_color" in profile["types"]["window-open"]["custom-shader"]
            assert "fx_noise" in profile["types"]["window-close"]["custom-shader"]
            assert profile["types"]["window-resize"] == base_types["window-resize"]
            print(
                "PASS: actual CLI → browser → HTTP → helper → registry; all families, base settings and unrelated presets preserved"
            )
        finally:
            process.terminate()
            try:
                process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()


if __name__ == "__main__":
    main()
