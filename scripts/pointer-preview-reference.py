#!/usr/bin/env python3
"""Generate browser parity vectors from the actual native Rust spring.

Only the two data types used by the source are stubbed. No spring equations are
copied into this generator. Rust compiles the unchanged source extracted from
the checked-in patch in a temporary directory; no compositor build is required.
Run with --check to compare a fresh reference against the checked-in fixture.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "experimental/niri-pointer-wobble.patch"
FIXTURE = ROOT / "tests/fixtures/pointer-native-reference.json"
SPRING_PATH = "src/animation/pointer_wobble.rs"
SHADER_PATH = "src/render_helpers/shaders/pointer_wobble.frag"


def added_file(path):
    """Read the complete added file, failing if it stops being a new-file hunk."""
    patch = PATCH.read_text()
    section = patch.split(f"diff --git a/{path} b/{path}\n", 1)[1].split("\ndiff --git ", 1)[0]
    if "--- /dev/null\n" not in section:
        raise ValueError(f"Expected a complete added file: {path}")
    hunk = section.split("\n@@ ", 1)[1].split("\n", 1)[1]
    lines = hunk.splitlines()
    if any(not line.startswith("+") for line in lines):
        raise ValueError(f"Expected only added source lines: {path}")
    return "\n".join(line[1:] for line in lines) + "\n"


def event(op, at, value=None):
    return {"op": op, "at": at} | ({"value": value} if value is not None else {})


def cases():
    default = {"strength": 0.7, "damping": 65, "frequency": 8}
    traces = [
        {
            "name": "impulse-release-and-long-frame",
            "events": [
                event("push", 0, [40, -15]),
                event("sample", 0),
                event("sample", 16),
                event("sample", 16),
                event("release", 16),
                event("sample", 16),
                event("sample", 75),
                event("sample", 270),
                event("sample", 7000),
            ],
        },
        {
            "name": "reversal-and-anchor-blend",
            "events": [
                event("push", 0, [60, 40]),
                event("sample", 30),
                event("push", 30, [-105, -40]),
                event("sample", 60),
                event("release", 60),
                event("sample", 76),
                event("grab", 76, [0.8, 0.9]),
                event("sample", 76),
                event("sample", 96),
                event("sample", 116),
                event("sample", 156),
                event("push", 160, [15, 25]),
                event("sample", 190),
            ],
        },
        {
            "name": "slow-release-taper-regrab",
            "config": {"strength": 2, "damping": 10, "frequency": 2},
            "events": [
                event("push", 0, [300, -80]),
                event("sample", 50),
                event("release", 50),
                event("sample", 1500),
                event("sample", 1550),
                event("sample", 1800),
                event("grab", 1800, [0.1, 0.75]),
                event("sample", 1800),
                event("sample", 1820),
                event("push", 1820, [75, 40]),
                event("sample", 1880),
                event("release", 1880),
                event("sample", 3880),
            ],
        },
        {
            "name": "slow-release-exact-deadline",
            "config": {"strength": 2, "damping": 10, "frequency": 2},
            "events": [
                event("push", 0, [300, 0]),
                event("release", 0),
                *[event("sample", t) for t in [100, 1499, 1500, 1750, 1900, 1999, 2000, 9000]],
            ],
        },
        {
            "name": "critical-damping",
            "config": {"strength": 0.9, "damping": 100, "frequency": 2},
            "events": [
                event("push", 0, [200, -150]),
                *[event("sample", t) for t in [0, 1, 16, 70, 140]],
                event("release", 140),
                event("sample", 200),
                event("sample", 2140),
            ],
        },
        {
            "name": "maximum-frequency",
            "config": {"strength": 2, "damping": 10, "frequency": 16},
            "events": [
                event("push", 0, [1e308, -1e308]),
                *[event("sample", t) for t in [0, 1, 7, 16, 42, 70]],
                event("push", 70, [-1e308, 1e308]),
                event("sample", 71),
                event("release", 71),
                event("sample", 2071),
            ],
        },
        {
            "name": "disabled",
            "config": {"strength": 0, "damping": 65, "frequency": 8},
            "events": [
                event("push", 0, [1e308, -1e308]),
                event("sample", 16),
                event("release", 16),
                event("sample", 100),
            ],
        },
        {
            "name": "defensive-resume-after-release",
            "events": [
                event("push", 0, [50, 0]),
                event("release", 16),
                event("sample", 70),
                event("push", 70, [10, 25]),
                event("sample", 70),
                event("sample", 100),
                event("sample", 90),
                event("sample", 100),
            ],
        },
        {
            "name": "adversarial-saturation",
            "config": {"strength": 2, "damping": 10, "frequency": 2},
            "events": [
                item
                for i in range(80)
                for item in [
                    event("push", i, [1e6 * (-1 if i % 2 else 1), -1e6]),
                    event("sample", i + 1),
                ]
            ]
            + [event("release", 80), event("sample", 2080)],
        },
    ]
    for trace in traces:
        trace.setdefault("config", default.copy())
        trace["anchor"] = [0.2, 0.3]
    return traces


# These arithmetic/container types stand in for Smithay and niri-config, without
# changing a line of the extracted GPL native implementation compiled below.
STUBS = """
extern crate self as niri_config;
extern crate self as smithay;
pub mod animations {
    #[derive(Debug, Clone, Copy)] pub struct Strength(pub f64);
    #[derive(Debug, Clone, Copy)] pub struct PointerWobble {
        pub strength: Strength, pub damping: u32, pub frequency: u32,
    }
}
pub mod utils {
    use std::{marker::PhantomData, ops::{Add, Sub, SubAssign}};
    #[derive(Debug, Clone, Copy)] pub struct Logical;
    #[derive(Debug, Clone, Copy)] pub struct Point<T, K> {
        pub x: T, pub y: T, kind: PhantomData<K>,
    }
    impl From<(f64, f64)> for Point<f64, Logical> {
        fn from((x, y): (f64, f64)) -> Self { Self { x, y, kind: PhantomData } }
    }
    impl Point<f64, Logical> {
        pub fn upscale(self, scale: f64) -> Self { (self.x * scale, self.y * scale).into() }
    }
    impl Add for Point<f64, Logical> {
        type Output = Self;
        fn add(self, rhs: Self) -> Self { (self.x + rhs.x, self.y + rhs.y).into() }
    }
    impl Sub for Point<f64, Logical> {
        type Output = Self;
        fn sub(self, rhs: Self) -> Self { (self.x - rhs.x, self.y - rhs.y).into() }
    }
    impl SubAssign for Point<f64, Logical> {
        fn sub_assign(&mut self, rhs: Self) { self.x -= rhs.x; self.y -= rhs.y; }
    }
}
#[path = "native.rs"] mod native;
use std::time::Duration;
use animations::{PointerWobble as Config, Strength};
fn at(ms: u64) -> Duration { Duration::from_millis(ms) }
"""


def reference_program(traces):
    lines = [STUBS, "fn main() {"]
    for trace in traces:
        config = trace["config"]
        x, y = trace["anchor"]
        lines += [
            "{",
            f"let config = Config {{ strength: Strength({float(config['strength'])}), "
            f"damping: {config['damping']}, frequency: {config['frequency']} }};",
            f"let mut state = native::PointerWobble::new(config, ({x}, {y}).into(), at(0));",
        ]
        for item in trace["events"]:
            op, at = item["op"], item["at"]
            if op in ("push", "grab"):
                x, y = (repr(float(value)) for value in item["value"])
                lines.append(f"state.{op}(({x}, {y}).into(), at({at}));")
            elif op == "release":
                lines.append(f"state.release(at({at}));")
            elif op == "sample":
                lines += [
                    f"state.advance(at({at}));",
                    "let d = state.deformation();",
                    f"let a = state.anchor(at({at}));",
                    'println!("{{\\"deformation\\":[{:?},{:?}],\\"anchor\\":[{:?},{:?}],'
                    '\\"released\\":{},\\"moving\\":{}}}", '
                    "d.x, d.y, a.x, a.y, state.released(), state.is_moving());",
                ]
        lines.append("}")
    lines.append("}")
    return "\n".join(lines)


def generate():
    spring, shader = added_file(SPRING_PATH), added_file(SHADER_PATH)
    traces = cases()
    env = os.environ.copy()
    compiler = shutil.which("rustc")
    bundled = ROOT / "artifacts/toolchain"
    # Match the native build helper's optional project-local toolchain.
    if (bundled / "cargo/bin/rustc").exists():
        compiler = str(bundled / "cargo/bin/rustc")
        env.update(RUSTUP_HOME=str(bundled / "rustup"), CARGO_HOME=str(bundled / "cargo"))
    if compiler is None:
        raise SystemExit("rustc is required to regenerate the native pointer reference")
    with tempfile.TemporaryDirectory(prefix="nirifx-pointer-reference-") as directory:
        path = Path(directory)
        (path / "native.rs").write_text(spring)
        (path / "main.rs").write_text(reference_program(traces))
        subprocess.run(
            [compiler, "--edition=2021", "-o", str(path / "reference"), str(path / "main.rs")],
            check=True,
            env=env,
        )
        result = subprocess.check_output([str(path / "reference")], text=True)
    samples = iter(json.loads(line) for line in result.splitlines())
    for trace in traces:
        for item in trace["events"]:
            if item["op"] == "sample":
                item["expected"] = next(samples)
    assert next(samples, None) is None
    return {
        "schema": 1,
        "provenance": "Native Rust compiled unchanged from experimental/niri-pointer-wobble.patch; "
        "Config and Point containers are stubbed; no graphics or desktop state.",
        "source_sha256": {
            SPRING_PATH: hashlib.sha256(spring.encode()).hexdigest(),
            SHADER_PATH: hashlib.sha256(shader.encode()).hexdigest(),
        },
        "cases": traces,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify the committed reference")
    args = parser.parse_args()
    content = json.dumps(generate(), indent=2) + "\n"
    if args.check:
        if FIXTURE.read_text() != content:
            raise SystemExit("Pointer reference differs; regenerate and review the fixture")
        print("Native pointer reference is current")
    else:
        FIXTURE.write_text(content)
        print(f"Generated {FIXTURE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
