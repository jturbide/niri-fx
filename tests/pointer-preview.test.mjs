// Native-derived spring parity without a browser, compositor or active session.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";

const source = readFileSync(new URL("../niri_fx/pointer-preview.js", import.meta.url), "utf8"),
  { createPointerSpring, createPointerDemo, POINTER_PREVIEW_SHADER } = runInNewContext(
    source + "\n({ createPointerSpring, createPointerDemo, POINTER_PREVIEW_SHADER })",
  ),
  patch = readFileSync(
    new URL("../experimental/niri-pointer-wobble.patch", import.meta.url),
    "utf8",
  ),
  reference = JSON.parse(
    readFileSync(new URL("./fixtures/pointer-native-reference.json", import.meta.url), "utf8"),
  ),
  defaults = { strength: 0.7, damping: 65, frequency: 8 },
  plain = (value) => JSON.parse(JSON.stringify(value));

function nativeSource(path) {
  const section = patch.split(`diff --git a/${path} b/${path}\n`)[1].split("\ndiff --git ")[0];
  assert(section.includes("--- /dev/null\n"), "reference requires a complete new-file hunk");
  const lines = section
    .slice(section.indexOf("\n", section.indexOf("\n@@ ") + 1) + 1)
    .trimEnd()
    .split("\n");
  assert(
    lines.every((line) => line.startsWith("+")),
    "unexpected native source hunk",
  );
  return lines.map((line) => line.slice(1)).join("\n") + "\n";
}
function near(actual, expected, label) {
  assert(Number.isFinite(actual), label + " must be finite");
  assert(
    Math.abs(actual - expected) <= 1e-8,
    `${label}: ${actual} differs from native ${expected}`,
  );
}

test("reference vectors remain tied to the exact native Rust and GLSL sources", () => {
  assert.equal(reference.schema, 1);
  for (const [path, digest] of Object.entries(reference.source_sha256))
    assert.equal(
      createHash("sha256").update(nativeSource(path)).digest("hex"),
      digest,
      "Run python3 scripts/pointer-preview-reference.py after reviewing native changes",
    );
});

test("browser samples match native Rust across damping, release, regrab and adversarial input", () => {
  let samples = 0;
  for (const trace of reference.cases) {
    const spring = createPointerSpring(trace.config, trace.anchor);
    for (const item of trace.events) {
      if (item.op === "sample") {
        const actual = spring.sample(item.at),
          expected = item.expected;
        for (const field of ["deformation", "anchor"])
          for (let axis = 0; axis < 2; axis++)
            near(
              actual[field][axis],
              expected[field][axis],
              `${trace.name} at ${item.at}: ${field}[${axis}]`,
            );
        for (const field of ["released", "moving"])
          assert.equal(actual[field], expected[field], `${trace.name} at ${item.at}: ${field}`);
        assert(Math.hypot(...actual.deformation) <= 64 + 1e-8);
        samples++;
      } else if (item.op === "release") spring.release(item.at);
      else spring[item.op](item.value, item.at);
    }
  }
  assert(samples > 120, "exercise the complete reference, including saturation bursts");
});

test("pointer shader matches native math with only explicit geometry and alpha adapters", () => {
  const native = nativeSource("src/render_helpers/shaders/pointer_wobble.frag");
  const adapted = native
    .slice(native.indexOf("vec2 displacement"))
    .replace("void main()", "vec4 pointer_color(vec2 coords, vec2 size)")
    .replace(
      "vec2 dest = (niri_input_to_geo * vec3(niri_v_coords, 1.0)).xy;",
      "vec2 dest = coords;",
    )
    .replaceAll("niri_geo_size", "size")
    .replace("vec2 uv = (niri_geo_to_tex * vec3(source, 1.0)).xy;", "vec2 uv = source;")
    .replace("color *= niri_alpha;", "")
    .replace(/#if defined\(DEBUG_FLAGS\)[\s\S]*?#endif/g, "")
    .replace("gl_FragColor = color;", "return color;");
  const tokens = (value) => value.replace(/\/\/[^\n]*/g, "").replace(/\s+/g, "");
  assert.equal(
    tokens(POINTER_PREVIEW_SHADER.slice(POINTER_PREVIEW_SHADER.indexOf("vec2 displacement"))),
    tokens(adapted),
  );
  for (const uniform of [
    "sampler2D niri_tex",
    "vec2 niri_pointer_anchor",
    "vec2 niri_pointer_deformation",
  ])
    assert(POINTER_PREVIEW_SHADER.includes("uniform " + uniform + ";"));
});

test("direct spring sampling is frame-independent before the native rest threshold", () => {
  for (const damping of [10, 65, 100]) {
    const config = { ...defaults, damping, frequency: 2 },
      once = createPointerSpring(config);
    once.push([60, 40], 0);
    const expected = once.sample(120);
    for (const rate of [30, 60, 144]) {
      const spring = createPointerSpring(config);
      spring.push([60, 40], 0);
      for (let time = 1000 / rate; time < 120; time += 1000 / rate) {
        spring.sample(time);
        spring.sample(time);
      }
      const actual = spring.sample(120);
      actual.deformation.forEach((value, axis) =>
        near(value, expected.deformation[axis], `${rate} Hz`),
      );
    }
  }
});

test("fixed demo events are immutable and support backward seeks and every render cadence", () => {
  const config = { ...defaults },
    demo = createPointerDemo(config);
  assert(Object.isFrozen(demo));
  assert.equal(demo.dragMs, 1200);
  assert.equal(demo.durationMs, 3200);
  const times = [0, 100, 399, 400, 615, 800, 1199, 1200, 1220, 1700, 3199, 3200],
    expected = times.map((time) => plain(demo.sample(time)));
  config.strength = 0;
  for (const rate of [30, 60, 144]) {
    for (let time = 0; time < 3200; time += 1000 / rate) demo.sample(time);
    for (const index of [11, 7, 0, 6, 2, 9, 1, 8, 3, 10, 5, 4])
      assert.deepEqual(plain(demo.sample(times[index])), expected[index]);
  }
  const returned = demo.sample(400);
  returned.deformation[0] = returned.anchor[0] = returned.offset[0] = 10000;
  assert.deepEqual(plain(demo.sample(400)), expected[times.indexOf(400)]);
  assert.deepEqual(plain(demo.sample(-1)), expected[0]);
  assert.deepEqual(plain(demo.sample(1e9)), expected.at(-1));
  assert.equal(expected[0].phase, "drag");
  assert.equal(expected[7].phase, "settle");
  assert.deepEqual(expected.at(-1).offset, [0, 0]);
  assert.deepEqual(expected.at(-1).deformation, [0, 0]);
  assert.equal(expected.at(-1).moving, false);
  assert.equal(expected.at(-1).released, true);
  for (let time = 0; time <= 3200; time += 7) {
    const state = demo.sample(time);
    assert(Math.abs(state.offset[0]) <= 120 && Math.abs(state.offset[1]) <= 120);
    assert(Math.hypot(...state.deformation) <= 64 + 1e-8);
  }
});

test("release and repeated grab preserve displayed displacement and zero strength stays still", () => {
  const spring = createPointerSpring({ ...defaults, damping: 10, frequency: 2 });
  spring.push([200, 50], 0);
  const before = plain(spring.sample(16));
  spring.release(16);
  assert.deepEqual(plain(spring.sample(16).deformation), before.deformation);
  const tail = plain(spring.sample(1800));
  spring.grab([0.8, 0.9], 1800);
  const grabbed = plain(spring.sample(1800));
  assert.deepEqual(grabbed.deformation, tail.deformation);
  assert.deepEqual(grabbed.anchor, tail.anchor);
  assert.equal(grabbed.released, false);
  assert.deepEqual(plain(spring.sample(1880).anchor), [0.8, 0.9]);
  const off = createPointerSpring({ ...defaults, strength: 0 });
  off.push([1e308, -1e308], 0);
  assert.deepEqual(plain(off.sample(16).deformation), [0, 0]);
  assert.equal(off.sample(16).moving, false);
});

test("invalid controls and times fail clearly, and invalid pointer deltas leave native state alone", () => {
  for (const config of [
    null,
    {},
    { ...defaults, strength: NaN },
    { ...defaults, strength: 3 },
    { ...defaults, damping: 65.5 },
    { ...defaults, damping: 9 },
    { ...defaults, frequency: 1 },
    { ...defaults, frequency: 17 },
  ])
    assert.throws(() => createPointerSpring(config), /valid strength/);
  for (const time of [NaN, Infinity, -1])
    assert.throws(() => createPointerSpring(defaults, undefined, time), /time must be/);
  assert.throws(() => createPointerSpring(defaults, [0, Infinity]), /finite coordinates/);
  const spring = createPointerSpring(defaults),
    other = createPointerSpring(defaults);
  spring.push([80, 15], 0);
  other.push([80, 15], 0);
  for (const delta of [[NaN, 1], [Infinity, 1], [1], null]) spring.push(delta, 100);
  assert.deepEqual(plain(spring.sample(16)), plain(other.sample(16)));
  assert.throws(() => spring.sample(NaN), /time must be/);
  assert.throws(() => createPointerDemo(defaults).sample(NaN), /time must be/);
});
