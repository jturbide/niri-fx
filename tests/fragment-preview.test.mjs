import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";

const source = readFileSync(new URL("../niri_fx/fragment-preview.js", import.meta.url), "utf8"),
  api = runInNewContext(
    source +
      "\n({createFragmentMotion,createFragmentDemo,fragmentPreviewMesh,FRAGMENT_PREVIEW_MATERIAL})",
    { structuredClone },
  ),
  patch = readFileSync(
    new URL("../experimental/niri-fragment-drag.patch", import.meta.url),
    "utf8",
  ),
  reference = JSON.parse(
    readFileSync(new URL("./fixtures/fragment-native-reference.json", import.meta.url), "utf8"),
  ),
  plain = (value) => JSON.parse(JSON.stringify(value)),
  defaults = reference.cases.find((trace) => trace.name.startsWith("tear-")).config;
function nativeSource(path) {
  if (path.endsWith("#fragment_mesh_vertices")) {
    const start = patch.indexOf("+fn fragment_mesh_vertices("),
      end = patch.indexOf("\n+}\n", start) + 3;
    return (
      patch
        .slice(start, end)
        .split("\n")
        .map((line) => line.slice(1))
        .join("\n") + "\n"
    );
  }
  const section = patch.split(`diff --git a/${path} b/${path}\n`)[1].split("\ndiff --git ")[0];
  assert(section.includes("--- /dev/null\n"));
  const lines = section
    .slice(section.indexOf("\n", section.indexOf("\n@@ ") + 1) + 1)
    .trimEnd()
    .split("\n");
  assert(lines.every((line) => line.startsWith("+")));
  return lines.map((line) => line.slice(1)).join("\n") + "\n";
}
function near(actual, expected, label) {
  assert(Number.isFinite(actual), label + " must be finite");
  // Native samples cross an f64 -> f32 rendering boundary. This small relative
  // tolerance accounts for libm operation rounding without allowing pixel drift.
  assert(
    Math.abs(actual - expected) <= Math.max(2e-6, Math.abs(expected) * 2.5e-7),
    `${label}: ${actual} differs from native ${expected}`,
  );
}

test("fragment traces bind the exact native source and all response presets", () => {
  assert.equal(reference.schema, 1);
  for (const [path, digest] of Object.entries(reference.source_sha256))
    assert.equal(
      createHash("sha256").update(nativeSource(path)).digest("hex"),
      digest,
      "Regenerate reviewed native traces with scripts/fragment-preview-reference.py",
    );
  for (const name of ["gentle", "tear", "cascade"])
    assert(reference.cases.some((trace) => trace.name.startsWith(name + "-")));
});

test("continuous fragment browser state matches actual Rust on hold, reversal, regrab and release", () => {
  let samples = 0;
  for (const trace of reference.cases) {
    const motion = api.createFragmentMotion(trace.config, trace);
    for (const event of trace.events) {
      if (event.op !== "sample") {
        if (event.op === "release") motion.release(event.at);
        else motion[event.op](event.value, event.at);
        continue;
      }
      const actual = motion.sample(event.at),
        expected = event.expected,
        label = `${trace.name} at ${event.at}`;
      assert.equal(actual.cells.length, expected.count, label + " count");
      for (const key of ["held", "moving", "max_lag"])
        assert.equal(actual[key], expected[key], label + " " + key);
      for (const cell of expected.cells) {
        const value = actual.cells[cell.index];
        for (const key of ["center", "half_extent", "translation", "tilt"])
          for (let axis = 0; axis < 2; axis++)
            near(value[key][axis], cell[key][axis], `${label} ${cell.index} ${key}[${axis}]`);
        for (const key of ["rotation", "edge_blend", "pin_weight"])
          near(value[key], cell[key], `${label} ${cell.index} ${key}`);
      }
      const mesh = api.fragmentPreviewMesh(actual);
      assert.equal(mesh.length / 9, expected.mesh_count, label + " vertexcount");
      for (const { index, vertex } of expected.mesh) {
        const ours = Array.from(mesh.slice(index * 9, index * 9 + 9));
        for (let axis = 0; axis < 2; axis++) {
          const position = vertex[axis] * expected.bounds[axis + 2] + expected.bounds[axis];
          assert(
            Math.abs(ours[axis] - position) < 0.0002,
            `${label} vertex ${index} position[${axis}] differs from native`,
          );
        }
        for (let column = 2; column < 9; column++)
          near(ours[column], vertex[column], `${label} vertex ${index} component ${column}`);
      }
      samples++;
    }
  }
  assert(samples >= 100);
});

test("fragment material is the native square texture material", () => {
  const shader = readFileSync(
      new URL("../niri_fx/shaders/fragment-motion.glsl", import.meta.url),
      "utf8",
    ),
    tokens = (value) => value.replace(/\/\/[^\n]*/g, "").replace(/\s/g, "");
  assert.equal(
    tokens(api.FRAGMENT_PREVIEW_MATERIAL),
    tokens(
      shader.slice(shader.indexOf("vec4 fragment_motion_mesh_color"), shader.indexOf("#endif")),
    ),
  );
});

test("rest mesh reconstructs the exact full texture quad; active pieces retain original UVs", () => {
  const motion = api.createFragmentMotion(defaults, { particles: 72 }),
    rest = motion.sample(0),
    mesh = api.fragmentPreviewMesh(rest);
  assert.equal(mesh.length, 6 * 9);
  assert.deepEqual(Array.from(mesh.slice(0, 9)), [0, 0, 0, 0, -300, -190, 300, 190, 0]);
  motion.grab([0.2, 0.2], 0);
  motion.push([140, 20], 200);
  const active = motion.sample(216),
    vertices = api.fragmentPreviewMesh(active);
  assert.equal(vertices.length, active.cells.length * 6 * 9);
  assert(Array.from(vertices).every(Number.isFinite));
  // Rotation changes destinations while six UV corners continue to refer to
  // their original source square, preventing texture sliding through pieces.
  const ordered = [...active.cells].sort((a, b) => a.pin_weight - b.pin_weight),
    cell = ordered[0];
  near(vertices[2], (cell.center[0] - cell.half_extent[0]) / 600, "source u");
  near(vertices[3], (cell.center[1] - cell.half_extent[1]) / 380, "source v");
  motion.release(220);
  assert.deepEqual(Array.from(api.fragmentPreviewMesh(motion.sample(2020))), Array.from(mesh));
});

test("preview snapshots own their values and invalid inputs cannot poison the native model", () => {
  const config = { ...defaults },
    motion = api.createFragmentMotion(config),
    other = api.createFragmentMotion(defaults);
  config.press_spread = 0;
  motion.grab([0.2, 0.2], 0);
  other.grab([0.2, 0.2], 0);
  for (const delta of [[NaN, 1], [Infinity, 1], null, [1]]) motion.push(delta, 100);
  const first = plain(motion.sample(16));
  assert.deepEqual(first, plain(other.sample(16)));
  first.cells[0].translation[0] = 1e10;
  first.target[0] = 1e10;
  assert.deepEqual(plain(motion.sample(16)), plain(other.sample(16)));
  for (const time of [NaN, -1, Infinity]) assert.throws(() => motion.sample(time), /time must be/);
  for (const config of [
    {},
    { ...defaults, press_spread: NaN },
    { ...defaults, delay_near_ms: 500 },
    { ...defaults, rotation_mode: "wrong" },
    { ...defaults, batches: true },
  ])
    assert.throws(() => api.createFragmentMotion(config), /complete valid response/);
  assert.throws(() => api.createFragmentMotion(defaults, { particles: 4096 }), /4096 cell limit/);
  assert.throws(() => api.createFragmentMotion(defaults, { size: [0, 380] }), /valid size/);
});

test("deterministic demo preserves press, forward travel, reversal and exact settled reconstruction", () => {
  const demo = api.createFragmentDemo(defaults, { particles: 48 }),
    times = [0, 120, 240, 648, 840, 1280, 1600, 2000, 3400],
    frames = times.map((at) => plain(demo.sample(at)));
  assert.equal(demo.dragMs, 1600);
  assert.equal(demo.durationMs, 3400);
  assert(frames[1].cells.some((cell) => Math.hypot(...cell.translation) > 1));
  assert(frames[3].target[0] > 100);
  assert(frames[5].target[0] < 0);
  for (const index of [4, 0, 7, 2, 6, 8, 1, 3, 5])
    assert.deepEqual(plain(demo.sample(times[index])), frames[index]);
  assert.equal(frames.at(-1).moving, false);
  assert(
    frames
      .at(-1)
      .cells.every((cell) => cell.rotation === 0 && cell.translation.every((value) => value === 0)),
  );
  assert.deepEqual(plain(demo.sample(-100)), frames[0]);
  assert.deepEqual(plain(demo.sample(1e9)), frames.at(-1));
});

test("fragment demo render cadence cannot change its deterministic native integration clock", () => {
  const times = [120, 240, 648, 840, 1280, 1600, 2000, 3400],
    expected = times.map((at) =>
      plain(api.createFragmentDemo(defaults, { particles: 12 }).sample(at)),
    );
  for (const rate of [30, 60, 144]) {
    const demo = api.createFragmentDemo(defaults, { particles: 12 }),
      schedule = new Set(times);
    for (let at = 0; at <= 3400; at += 1000 / rate) schedule.add(at);
    for (const at of [...schedule].sort((a, b) => a - b)) {
      const sample = demo.sample(at),
        index = times.indexOf(at);
      if (index >= 0) assert.deepEqual(plain(sample), expected[index], rate + " Hz at " + at);
    }
  }
});
