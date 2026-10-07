#!/usr/bin/env python3
"""Record the actual native continuous-fragment model for browser parity.

Extracts unchanged Rust from the patch and stubs only configuration/container
arithmetic types. It never starts a compositor or reads desktop configuration.
Use --stage DIR to compile the generated standalone source in a separate Rust
build environment, then --from-output FILE to assemble its JSON output.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys  # noqa: E402

sys.path.insert(0, str(ROOT))
from niri_fx.fragment_motion import CONTROLS, PRESETS, FragmentMotionSettings  # noqa: E402

PATCH = ROOT / "experimental/niri-fragment-drag.patch"
FIXTURE = ROOT / "tests/fixtures/fragment-native-reference.json"
MOTION_PATH = "src/animation/fragment_motion.rs"
MESH_PATH = "src/render_helpers/movement.rs#fragment_mesh_vertices"


def added_file(path):
    section = (
        PATCH.read_text()
        .split(f"diff --git a/{path} b/{path}\n", 1)[1]
        .split("\ndiff --git ", 1)[0]
    )
    if "--- /dev/null\n" not in section:
        raise ValueError(f"Expected a complete added file: {path}")
    lines = section.split("\n@@ ", 1)[1].split("\n", 1)[1].splitlines()
    if any(not line.startswith("+") for line in lines):
        raise ValueError(f"Expected only added source: {path}")
    return "\n".join(line[1:] for line in lines) + "\n"


def mesh_source():
    patch = PATCH.read_text()
    start = patch.index("+fn fragment_mesh_vertices(")
    end = patch.index("\n+}\n", start) + 3
    lines = patch[start:end].splitlines()
    if any(not line.startswith("+") for line in lines):
        raise ValueError("Expected a complete added native mesh function")
    return "\n".join(line[1:] for line in lines) + "\n"


def event(op, at, value=None):
    return {"op": op, "at": at} | ({"value": value} if value is not None else {})


def cases():
    events = [
        event("sample", 0),
        event("grab", 0, [0.18, 0.2]),
        event("sample", 0),
        event("sample", 80),
        event("sample", 240),
        event("push", 240, [140, 60]),
        event("sample", 240),
        event("sample", 248),
        event("sample", 264),
        event("sample", 400),
        event("push", 400, [-220, -70]),
        event("sample", 400),
        event("sample", 416),
        event("sample", 700),
        event("release", 700),
        event("sample", 700),
        event("sample", 850),
        event("grab", 850, [0.88, 0.72]),
        event("sample", 850),
        event("sample", 930),
        event("push", 930, [130, -45]),
        event("sample", 946),
        event("release", 950),
        event("sample", 1100),
        event("sample", 1600),
        event("sample", 2600),
        event("sample", 2950),
        event("sample", 9000),
    ]
    traces = [
        {
            "name": name + "-press-reversal-regrab",
            "config": asdict(preset.settings),
            "particles": preset.particles,
            "events": events,
        }
        for name, preset in PRESETS.items()
    ]
    for name, settings in [
        (
            "random",
            FragmentMotionSettings(
                rotation_mode="random",
                delay_near_ms=200,
                delay_far_ms=600,
                delay_jitter=1,
                response_near_ms=800,
                response_far_ms=800,
                response_jitter=1,
                distance_exponent=0.01,
                pin_radius=0,
                press_spread=128,
                rotation_degrees=60,
                rotation_response_ms=800,
                rotation_speed=1,
                tilt=1.1,
            ),
        ),
        (
            "none",
            FragmentMotionSettings(
                rotation_mode="none",
                press_spread=0,
                delay_far_ms=0,
                response_near_ms=20,
                response_far_ms=20,
                batches=4096,
                release_ms=200,
                distance_exponent=4,
                pin_radius=256,
            ),
        ),
    ]:
        traces.append(
            {
                "name": name + "-custom-extremes",
                "config": asdict(settings),
                "particles": 72,
                "events": events,
            }
        )
    traces.append(
        {
            "name": "dense-history-and-long-hold",
            "config": asdict(PRESETS["tear"].settings),
            "particles": 48,
            "events": [
                event("grab", 0, [0.4, 0.2]),
                *[
                    item
                    for ms in range(1, 800)
                    for item in [event("push", ms, [(-1 if ms % 3 else 2) * 0.4, 0.15])]
                ],
                event("sample", 800),
                event("sample", 1000),
                event("sample", 3000),
                event("sample", 9000),
                event("push", 9000, [40, 10]),
                event("sample", 9016),
                event("release", 9016),
                event("sample", 10816),
            ],
        }
    )
    traces.append(
        {
            "name": "release-taper-regrab",
            "config": asdict(
                FragmentMotionSettings(
                    response_near_ms=800,
                    response_far_ms=800,
                    press_response_ms=800,
                    rotation_response_ms=800,
                    release_ms=600,
                )
            ),
            "particles": 120,
            "events": [
                event("grab", 0, [0.3, 0.3]),
                event("push", 20, [180, 60]),
                event("release", 40),
                event("sample", 450),
                event("grab", 450, [0.9, 0.9]),
                event("sample", 450),
                event("sample", 466),
                event("push", 480, [-100, -30]),
                event("sample", 496),
                event("release", 510),
                event("sample", 1110),
            ],
        }
    )
    traces.append(
        {
            "name": "tile-sized-grab-anchor",
            "config": asdict(PRESETS["gentle"].settings),
            "particles": 0,
            "anchor": [0.18, 0.2],
            "tile": 32,
            "size": [610, 393],
            "events": [
                event("grab", 0, [0.18, 0.2]),
                event("sample", 0),
                event("sample", 16),
                event("sample", 200),
                event("push", 200, [100, 20]),
                event("sample", 216),
                event("release", 250),
                event("sample", 1350),
            ],
        }
    )
    for trace in traces:
        trace.setdefault("size", [600, 380])
        trace.setdefault("anchor", [0.5, 0.5])
        trace.setdefault("tile", 28)
        trace["events"] = [item.copy() for item in trace["events"]]
    return traces


STUBS = """
extern crate self as niri_config;
extern crate self as smithay;
pub mod animations {
    #[derive(Debug, Clone, Copy, PartialEq)] pub struct Number(pub f64);
    #[derive(Debug, Clone, Copy, PartialEq)] pub enum FragmentRotation { Movement, Random, None }
    #[derive(Debug, Clone, Copy, PartialEq)] pub struct FragmentMotion { CONFIG_FIELDS }
    impl Default for FragmentMotion { fn default() -> Self { CONFIG_DEFAULT } }
}
pub mod utils {
    use std::{marker::PhantomData, ops::{Add, Sub, AddAssign}};
    #[derive(Debug, Clone, Copy, Default, PartialEq)] pub struct Logical;
    #[derive(Debug, Clone, Copy, Default, PartialEq)] pub struct Point<T, K> { pub x:T, pub y:T, kind:PhantomData<K> }
    impl From<(f64,f64)> for Point<f64, Logical> {
        fn from((x,y):(f64,f64))->Self { Self{x,y,kind:PhantomData} }
    }
    impl Point<f64, Logical> {
        pub fn upscale(self,s:f64)->Self {(self.x*s,self.y*s).into()}
        pub fn downscale(self,s:f64)->Self {(self.x/s,self.y/s).into()}
    }
    impl Add for Point<f64,Logical> { type Output=Self; fn add(self,rhs:Self)->Self {(self.x+rhs.x,self.y+rhs.y).into()} }
    impl Sub for Point<f64,Logical> { type Output=Self; fn sub(self,rhs:Self)->Self {(self.x-rhs.x,self.y-rhs.y).into()} }
    impl AddAssign for Point<f64,Logical> { fn add_assign(&mut self,rhs:Self){self.x+=rhs.x;self.y+=rhs.y;} }
    #[derive(Debug, Clone, Copy, PartialEq)] pub struct Size<T,K> { pub w:T, pub h:T, kind:PhantomData<K> }
    impl From<(f64,f64)> for Size<f64,Logical> { fn from((w,h):(f64,f64))->Self{Self{w,h,kind:PhantomData}} }
    #[derive(Debug, Clone, Copy)] pub struct Rectangle<T,K>{pub loc:Point<T,K>,pub size:Size<T,K>}
}
#[path="native.rs"] mod native;
use std::time::Duration;
use animations::{Number,FragmentMotion as Config,FragmentRotation};
fn at(ms:u64)->Duration {Duration::from_millis(ms)}
"""


MESH_STUBS = """
extern crate self as anyhow;
pub type Result<T> = std::result::Result<T, String>;
#[macro_export] macro_rules! ensure { ($condition:expr,$message:expr $(,)?)=>{
    if !$condition { return Err($message.to_string()); }
}; }
trait Context<T> { fn context(self,message:&str)->Result<T>; }
impl<T,E:std::fmt::Debug> Context<T> for std::result::Result<T,E> {
    fn context(self,message:&str)->Result<T>{ self.map_err(|e|format!("{message}: {e:?}")) }
}
mod animation {pub mod fragment_motion {pub use crate::native::MAX_CELLS;}}
use std::rc::Rc;
use utils::{Size,Logical,Rectangle};
use native::FragmentSample;
#[derive(Clone,Copy)] struct Scale<T>{x:T,y:T}
#[derive(Clone,Copy)] struct Vec2 {x:f32,y:f32}
impl Vec2 {
    fn new(x:f32,y:f32)->Self{Self{x,y}}
    fn from_array([x,y]:[f32;2])->Self{Self{x,y}}
    fn is_finite(self)->bool{self.x.is_finite() && self.y.is_finite()}
}
impl std::ops::Add for Vec2{type Output=Self;fn add(self,rhs:Self)->Self{Self::new(self.x+rhs.x,self.y+rhs.y)}}
impl std::ops::Mul for Vec2{type Output=Self;fn mul(self,rhs:Self)->Self{Self::new(self.x*rhs.x,self.y*rhs.y)}}
impl Size<f64,Logical> {fn to_point(self)->utils::Point<f64,Logical>{(self.w,self.h).into()}}
impl Rectangle<f64,Logical> {
    fn from_extremities(lower:utils::Point<f64,Logical>,upper:utils::Point<f64,Logical>)->Self{
        Self{loc:lower,size:(upper.x-lower.x,upper.y-lower.y).into()}
    }
}
"""


def config_literal(config):
    parts = []
    for key, value in config.items():
        literal = (
            f"FragmentRotation::{value.title()}"
            if isinstance(value, str)
            else str(value)
            if CONTROLS[key].kind == "integer"
            else f"Number({float(value)!r})"
        )
        parts.append(f"{key}: {literal}")
    return "Config {" + ", ".join(parts) + "}"


def reference_program(traces):
    defaults = asdict(FragmentMotionSettings())
    fields = ", ".join(
        f"pub {key}: "
        + (
            "FragmentRotation"
            if isinstance(value, str)
            else "u32"
            if CONTROLS[key].kind == "integer"
            else "Number"
        )
        for key, value in defaults.items()
    )
    stubs = STUBS.replace("CONFIG_FIELDS", fields).replace(
        "CONFIG_DEFAULT", config_literal(defaults).replace("Config {", "Self {")
    )
    lines = [stubs, MESH_STUBS, mesh_source(), "fn main() {"]
    for trace in traces:
        x, y = trace["anchor"]
        w, h = trace["size"]
        lines += [
            "{",
            f"let config = {config_literal(trace['config'])};",
            f"let mut state = native::FragmentMotion::with_anchor(({x},{y}).into(),at(0));",
            f"state.configure(config,native::FragmentGrid{{particles:{trace['particles']},tile:{float(trace['tile'])}}});",
            f"let size=({float(w)},{float(h)}).into();",
            "let rect=utils::Rectangle {loc:(0.,0.).into(),size};",
            "state.sample(at(0),size,rect).unwrap();",
        ]
        for item in trace["events"]:
            op, time = item["op"], item["at"]
            if op in ("push", "grab"):
                x, y = (repr(float(value)) for value in item["value"])
                lines.append(f"state.{op}(({x},{y}).into(),at({time}));")
            elif op == "release":
                lines.append(f"state.release(at({time}));")
            else:
                lines += [
                    f"let sample=state.sample(at({time}),size,rect).unwrap();",
                    'print!("{{\\"held\\":{},\\"moving\\":{},\\"max_lag\\":{},\\"count\\":{},\\"cells\\":[", state.held(),state.moving(),sample.max_lag,sample.cells.len());',
                    "let count=sample.cells.len();",
                    "let mut indices=vec![0,1,count/8,count/4,count/2,count*3/4,count-2,count-1];",
                    "indices.sort_unstable(); indices.dedup();",
                    "for (n,index) in indices.into_iter().enumerate() {let c=&sample.cells[index];",
                    'if n>0 { print!(","); }',
                    'print!("{{\\"index\\":{},\\"center\\":{:?},\\"half_extent\\":{:?},\\"translation\\":{:?},\\"rotation\\":{:?},\\"tilt\\":{:?},\\"edge_blend\\":{:?},\\"pin_weight\\":{:?}}}",index,c.center,c.half_extent,c.translation,c.rotation,c.tilt,c.edge_blend,c.pin_weight);',
                    "}",
                    "let (mesh,bounds)=fragment_mesh_vertices(&sample,rect,size,Scale{x:1.,y:1.}).unwrap();",
                    'print!("],\\"bounds\\":[{:?},{:?},{:?},{:?}],\\"mesh_count\\":{},\\"mesh\\":[",bounds.loc.x,bounds.loc.y,bounds.size.w,bounds.size.h,mesh.len());',
                    "let mut indices=vec![0,1,2,mesh.len()/2,mesh.len()-2,mesh.len()-1];",
                    "indices.sort_unstable(); indices.dedup();",
                    "for (n,index) in indices.into_iter().enumerate() {",
                    'if n>0 {print!(",");}',
                    'print!("{{\\"index\\":{},\\"vertex\\":{:?}}}",index,mesh[index]);',
                    "}",
                    'println!("]}}");',
                ]
        lines.append("}")
    lines.append("}")
    return "\n".join(lines)


def finish(source, traces, output):
    samples = iter(json.loads(line) for line in output.splitlines())
    for trace in traces:
        for item in trace["events"]:
            if item["op"] == "sample":
                item["expected"] = next(samples)
    assert next(samples, None) is None
    return {
        "schema": 1,
        "provenance": "Native Rust compiled unchanged from experimental/niri-fragment-drag.patch; configuration and arithmetic containers are stubbed; fixed synthetic geometry, no desktop state.",
        "source_sha256": {
            MOTION_PATH: hashlib.sha256(source.encode()).hexdigest(),
            MESH_PATH: hashlib.sha256(mesh_source().encode()).hexdigest(),
        },
        "cases": traces,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path)
    parser.add_argument("--from-output", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    source, traces = added_file(MOTION_PATH), cases()
    if args.stage:
        args.stage.mkdir(parents=True, exist_ok=True)
        (args.stage / "native.rs").write_text(source)
        (args.stage / "main.rs").write_text(reference_program(traces))
        (args.stage / "mesh.sha256").write_text(
            hashlib.sha256(mesh_source().encode()).hexdigest() + "\n"
        )
        (args.stage / "source.sha256").write_text(
            hashlib.sha256(source.encode()).hexdigest() + "\n"
        )
        return
    if args.from_output:
        if (
            args.from_output.with_name("source.sha256").read_text().strip()
            != hashlib.sha256(source.encode()).hexdigest()
        ):
            raise SystemExit("Staged native source changed; regenerate the reference")
        if (
            args.from_output.with_name("mesh.sha256").read_text().strip()
            != hashlib.sha256(mesh_source().encode()).hexdigest()
        ):
            raise SystemExit("Staged native mesh source changed; regenerate the reference")
        output = args.from_output.read_text()
    else:
        env = os.environ.copy()
        compiler = shutil.which("rustc")
        bundled = ROOT / "artifacts/toolchain"
        if (bundled / "cargo/bin/rustc").exists():
            compiler = str(bundled / "cargo/bin/rustc")
            env.update(RUSTUP_HOME=str(bundled / "rustup"), CARGO_HOME=str(bundled / "cargo"))
        if not compiler:
            raise SystemExit("rustc is required for the native fragment reference")
        with tempfile.TemporaryDirectory(prefix="nirifx-fragment-reference-") as directory:
            path = Path(directory)
            (path / "native.rs").write_text(source)
            (path / "main.rs").write_text(reference_program(traces))
            subprocess.run(
                [compiler, "--edition=2021", "-o", str(path / "reference"), str(path / "main.rs")],
                check=True,
                env=env,
            )
            output = subprocess.check_output([str(path / "reference")], text=True)
    content = json.dumps(finish(source, traces, output), indent=2) + "\n"
    if args.check:
        if FIXTURE.read_text() != content:
            raise SystemExit("Fragment reference differs; regenerate and review the fixture")
        print("Native fragment reference is current")
    else:
        FIXTURE.write_text(content)
        print(f"Generated {FIXTURE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
