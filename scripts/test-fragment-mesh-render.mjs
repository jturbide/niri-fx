#!/usr/bin/env node
// Explicit native acceptance companion. No missing fixture or native source may
// turn into a pass: both are required, separately from portable browser CI.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { launchBrowser, projectRoot } from "./lib/browser.mjs";
import { renderFragmentMeshes } from "./lib/fragment-mesh-render.mjs";
const { values } = parseArgs({
  options: {
    fixture: { type: "string" },
    "native-source": { type: "string" },
    proof: { type: "string" },
  },
  strict: true,
});
assert.ok(
  values.fixture && values["native-source"],
  "Required: --fixture <Rust-emitted JSON> --native-source <experimental Niri checkout>",
);
const fixture = JSON.parse(readFileSync(resolve(values.fixture), "utf8"));
assert.equal(fixture.contract, 3);
assert.equal(fixture.producer, "FragmentMotion::sample + fragment_mesh_vertices");
const frames = Object.fromEntries(fixture.frames.map((frame) => [frame.name, frame]));
for (const name of [
  "rest",
  "press",
  "held",
  "onset",
  "step-440",
  "step-480",
  "step-540",
  "step-620",
  "step-760",
  "step-1000",
  "reverse-before",
  "reverse-after",
  "release-before",
  "release-after",
  "regrab-before",
  "regrab-after",
  "settled",
])
  assert.ok(frames[name], "Missing native fixture state: " + name);
for (const frame of fixture.frames) {
  if (["rest", "settled"].includes(frame.name)) {
    assert.equal(frame.vertices.length, 6, "identity state must use the protected texture quad");
  } else {
    assert.ok(frame.vertices.length >= 800 * 6 && frame.vertices.length <= 4096 * 6);
  }
  assert.ok(frame.cells.length >= 800 && frame.cells.length <= 4096);
  for (const v of frame.vertices) {
    assert.equal(v.length, 9);
    assert.ok(v.every(Number.isFinite));
    assert.ok(v[0] >= 0 && v[0] <= 1 && v[1] >= 0 && v[1] <= 1);
  }
}
const key = (cell) => cell.center.join(",");
function cells(frame) {
  return new Map(frame.cells.map((cell) => [key(cell), cell]));
}
function near(a, b, message, tolerance = 0.0001) {
  assert.ok(Math.abs(a - b) <= tolerance, `${message}: ${a} vs ${b}`);
}
function continuity(before, after, { pinnedFollows = false } = {}) {
  const previous = cells(before);
  for (const next of after.cells) {
    const old = previous.get(key(next));
    assert.ok(old, "source identity changed");
    for (let axis = 0; axis < 2; axis++) {
      const travel = pinnedFollows ? old.pin * (after.target[axis] - before.target[axis]) : 0;
      near(
        next.translation[axis] + after.target[axis],
        old.translation[axis] + before.target[axis] + travel,
        "world position changed at input",
      );
      near(next.tilt[axis], old.tilt[axis], "tilt changed at input");
    }
    near(next.rotation, old.rotation, "rotation changed at input");
  }
}
continuity(frames.held, frames.onset, { pinnedFollows: true });
continuity(frames["reverse-before"], frames["reverse-after"], { pinnedFollows: true });
continuity(frames["release-before"], frames["release-after"]);
continuity(frames["regrab-before"], frames["regrab-after"]);
const baseline = cells(frames.held),
  delayed = cells(frames["step-480"]);
let farHeld = 0;
for (const cell of frames.onset.cells) {
  if (cell.center[1] > 400 && cell.pin === 0) {
    const old = baseline.get(key(cell)),
      later = delayed.get(key(cell));
    if (Math.abs(later.translation[0] + 40 - old.translation[0]) < 0.1) farHeld++;
  }
}
assert.ok(farHeld >= 20, `far pieces did not wait in screen space: ${farHeld}`);
const traces = new Set();
for (const cell of frames.onset.cells.filter((cell) => cell.pin === 0)) {
  traces.add(
    ["step-440", "step-480", "step-540", "step-620", "step-760"]
      .map((name) => Math.round(cells(frames[name]).get(key(cell)).translation[0] * 2))
      .join(","),
  );
}
assert.ok(traces.size > 30, `not enough independent delayed trajectories: ${traces.size}`);
const source = execFileSync(
  "python3",
  [
    "-c",
    "from dataclasses import replace;from niri_fx.effects import PRESETS,movement_shader;print(movement_shader(replace(PRESETS['balanced'],particles=800)))",
  ],
  { cwd: projectRoot, encoding: "utf8" },
);
const native = resolve(values["native-source"], "src/render_helpers/shaders");
const vertex = readFileSync(resolve(native, "fragment_mesh.vert"), "utf8");
const epilogue = readFileSync(resolve(native, "fragment_mesh_epilogue.frag"), "utf8");
const browser = await launchBrowser({ profilePrefix: "niri-fx-native-mesh-proof-" });
try {
  const render = {};
  for (const filter of ["nearest", "linear"]) {
    const result = await browser.callFunction(renderFragmentMeshes.toString(), [
      {
        source,
        vertex,
        epilogue,
        fixture,
        filter,
        proof: filter === "linear" && Boolean(values.proof),
      },
    ]);
    assert.equal(
      result.rest.max,
      0,
      `${filter}: native resting mesh must equal protected source pixels`,
    );
    assert.equal(
      result.settled.max,
      0,
      `${filter}: native settled mesh must rejoin protected source pixels`,
    );
    assert.ok(result.press.changed > 1000, `${filter}: press spread was not rendered`);
    assert.ok(result.moving.changed > 1000, `${filter}: delayed cell deformation was not rendered`);
    assert.ok(
      result.premultiplied && result.sourceClip,
      `${filter}: protected source alpha/UV clipping failed`,
    );
    if (result.proof) {
      writeFileSync(resolve(values.proof), Buffer.from(result.proof.split(",")[1], "base64"));
      delete result.proof;
    }
    render[filter] = result;
  }
  console.log(
    JSON.stringify(
      {
        fixture: resolve(values.fixture),
        frames: fixture.frames.length,
        delayedTrajectories: traces.size,
        farCellsHeld: farHeld,
        render,
      },
      null,
      2,
    ),
  );
} finally {
  await browser.close();
}
