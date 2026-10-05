#!/usr/bin/env node
// Hardware-only microbenchmark of the experimental native forward mesh.
// Browser code rasterizes Rust-emitted vertices; it never simulates particles.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { launchBrowser, projectRoot } from "./lib/browser.mjs";
import { benchmarkFragmentMesh } from "./lib/fragment-gpu.mjs";

const { values } = parseArgs({
  options: {
    fixture: { type: "string" },
    "native-source": { type: "string" },
    output: { type: "string" },
    samples: { type: "string", default: "60" },
    repeats: { type: "string", default: "2" },
    sizes: { type: "string", default: "1920x1080,3840x2160" },
    windows: { type: "string", default: "1,2,4" },
    cells: { type: "string", default: "600,800,1200,4096" },
    software: { type: "boolean", default: false },
    check: { type: "boolean", default: false },
    help: { type: "boolean", default: false },
  },
  strict: true,
});
if (values.help) {
  console.log(
    "Usage: node scripts/benchmark-fragment-gpu.mjs --fixture native-meshes.json --native-source /path/to/niri --output fresh-report.json [--samples 60 --repeats 2 --sizes 1920x1080,3840x2160 --windows 1,2,4 --cells 600,800,1200,4096]\nEach GPU query times 32 fixed warm compositions; reported percentiles describe batch averages, not individual frames.\n--check validates fixture/source without launching a browser; --software only exercises hardware rejection.",
  );
  process.exit(0);
}
assert(values.fixture && values["native-source"], "--fixture and --native-source are required");
assert(values.check || values.output, "--output is required; choose a fresh report filename");
const output = values.output ? resolve(values.output) : null;
assert(!output || !existsSync(output), "Use a fresh report filename");
function integer(value, min, max) {
  assert(/^\d+$/.test(value), "Expected an integer option");
  const number = Number(value);
  assert(Number.isSafeInteger(number) && number >= min && number <= max, `Expected ${min}..${max}`);
  return number;
}
const samples = integer(values.samples, 10, 120),
  repeats = integer(values.repeats, 1, 3);
const windows = values.windows.split(",").map((v) => integer(v, 1, 4));
assert(
  windows.every((v) => [1, 2, 4].includes(v)) && new Set(windows).size === windows.length,
  "Choose unique window counts from 1,2,4",
);
const counts = values.cells.split(",").map((v) => integer(v, 1, 4096));
assert(
  counts.every((v) => [600, 800, 1200, 4096].includes(v)) && new Set(counts).size === counts.length,
  "Choose unique cell counts from 600,800,1200,4096",
);
const sizes = values.sizes.split(",").map((size) => {
  assert(/^[0-9]+x[0-9]+$/.test(size), "Sizes must use WIDTHxHEIGHT");
  const [width, height] = size.split("x").map(Number);
  assert(
    [
      [1920, 1080],
      [3840, 2160],
    ].some(([w, h]) => width === w && height === h),
    "Choose 1920x1080 and/or 3840x2160",
  );
  return [width, height];
});
assert(new Set(values.sizes.split(",")).size === sizes.length, "Choose unique sizes");
const fixtureBytes = readFileSync(resolve(values.fixture));
assert(fixtureBytes.length <= 64 * 1024 * 1024, "Fixture exceeds 64 MiB");
const fixture = JSON.parse(fixtureBytes);
assert.equal(fixture.contract, 3);
assert.equal(fixture.producer, "FragmentMotion::sample + fragment_mesh_vertices");
assert(
  Array.isArray(fixture.cases) && fixture.cases.length === 4,
  "Expected four native density cases",
);
assert.deepEqual(
  fixture.cases.map((item) => item.actual_cells).sort((a, b) => a - b),
  [600, 800, 1200, 4096],
);
for (const item of fixture.cases) {
  assert.deepEqual(item.grid, { particles: 0, tile: 28 });
  assert.deepEqual(item.native_config, { defaults: true });
  assert.equal(item.requested_cells, item.actual_cells);
  assert(Array.isArray(item.texture_rect) && item.texture_rect.length === 4);
  assert(item.texture_rect.every(Number.isFinite));
  assert(item.texture_rect.slice(2).every((n) => Number.isInteger(n) && n > 0 && n <= 4096));
  assert(Array.isArray(item.states) && item.states.length <= 8);
  const states = Object.fromEntries(item.states.map((state) => [state.name, state]));
  assert.equal(Object.keys(states).length, item.states.length, "Duplicate mesh state");
  for (const name of ["rest", "moving", "settled"])
    assert(states[name], "Missing native state: " + name);
  for (const state of item.states) {
    assert.equal(state.actual_cells, item.actual_cells);
    assert(Number.isFinite(state.ms) && state.ms >= 0);
    assert(
      Array.isArray(state.area) && state.area.length === 4 && state.area.every(Number.isFinite),
    );
    assert(state.area[2] > 0 && state.area[3] > 0);
    assert(Array.isArray(state.vertices));
    assert.equal(
      state.vertices.length,
      ["rest", "settled"].includes(state.name) ? 6 : item.actual_cells * 6,
    );
    for (const vertex of state.vertices) {
      assert(Array.isArray(vertex) && vertex.length === 9 && vertex.every(Number.isFinite));
      assert(
        vertex[0] >= 0 && vertex[0] <= 1 && vertex[1] >= 0 && vertex[1] <= 1,
        "Mesh destination is outside its declared area",
      );
      assert(vertex[6] > 0 && vertex[7] > 0 && vertex[8] >= 0 && vertex[8] <= 1);
    }
  }
}
const source = execFileSync(
  "python3",
  [
    "-c",
    "from dataclasses import replace;from niri_fx.effects import movement_shader;from niri_fx.fragment_motion import PRESETS;print(movement_shader(replace(PRESETS['tear'].effect,particles=0,tile_size=28)))",
  ],
  { cwd: projectRoot, encoding: "utf8", timeout: 10000 },
);
assert(
  source.includes("// nirifx-fragment-motion: 3\n") &&
    /^\/\/ nirifx-fragment-grid: (\S+) (\S+)$/m.exec(source)?.slice(1).map(Number).join(",") ===
      "0,28",
  "Generated shader does not match the native fixture grid",
);
const native = resolve(values["native-source"]);
const vertex = readFileSync(
  resolve(native, "src/render_helpers/shaders/fragment_mesh.vert"),
  "utf8",
);
const epilogue = readFileSync(
  resolve(native, "src/render_helpers/shaders/fragment_mesh_epilogue.frag"),
  "utf8",
);
const hash = (data) => createHash("sha256").update(data).digest("hex");
const provenance = {
  fixture: hash(fixtureBytes),
  generatedShader: hash(source),
  nativeVertex: hash(vertex),
  nativeEpilogue: hash(epilogue),
  nativeMovement: hash(readFileSync(resolve(native, "src/render_helpers/movement.rs"))),
  nativeDynamics: hash(readFileSync(resolve(native, "src/animation/fragment_motion.rs"))),
  runner: hash(readFileSync(new URL(import.meta.url))),
  browserHarness: hash(readFileSync(new URL("./lib/fragment-gpu.mjs", import.meta.url))),
  browserLauncher: hash(readFileSync(new URL("./lib/browser.mjs", import.meta.url))),
};
if (values.check) {
  console.log(
    JSON.stringify(
      { status: "validated", counts: fixture.cases.map((item) => item.actual_cells), provenance },
      null,
      2,
    ),
  );
  process.exit(0);
}
const report = {
  schema: 1,
  kind: "native-fragment-mesh-webgl-gpu",
  started: new Date().toISOString(),
  scope:
    "Each GPU query times 32 fixed compositions, each with one clear and 1/2/4 overlapping synthetic windows using actual Rust-emitted continuous fragment meshes. Raw batch nanoseconds and per-composition batch averages are retained. Percentiles summarize batch averages, not individual frames. Vertex buffers/textures are preuploaded; the pose, textures and caches remain warm. Excludes CPU simulation, uploads, shader compilation, validation readbacks, compositor capture/input, physical presentation and scanout. Source texture dimensions and aspect vary with cell count, so this is not isolated per-cell cost. One fixed pose on one hardware system does not establish desktop frame rates.",
  provenance,
  fixture: {
    contract: fixture.contract,
    producer: fixture.producer,
    grid: fixture.cases[0].grid,
    nativeConfig: fixture.cases[0].native_config,
  },
  requested: { samples, repeats, sizes, windows, counts, softwareRejection: values.software },
  results: [],
  status: "running",
};
let browser;
const deadline = Date.now() + 12 * 60 * 1000;
try {
  for (let repeat = 1; repeat <= repeats; repeat++) {
    browser = await launchBrowser({
      software: values.software,
      requestTimeout: 60000,
      profilePrefix: "nirifx-fragment-gpu-",
    });
    const browserVersion = await browser.rpc("Browser.getVersion");
    for (const item of fixture.cases.filter((item) => counts.includes(item.actual_cells))) {
      for (const [width, height] of sizes) {
        for (const count of windows) {
          assert(Date.now() < deadline, "Benchmark exceeded its 12-minute total deadline");
          const result = await browser.callFunction(benchmarkFragmentMesh.toString(), [
            { source, vertex, epilogue, fixture: item, width, height, windows: count, samples },
          ]);
          report.results.push({ repeat, browserVersion, ...result });
          if (result.status !== "measured")
            throw new Error(result.reason || "Hardware measurement failed");
          assert.equal(result.samples, samples);
          console.log(
            `${repeat}/${repeats} ${item.actual_cells} cells ${width}x${height} ${count} window(s): batch-average p50=${result.batchAverageMs.p50.toFixed(3)}ms p95=${result.batchAverageMs.p95.toFixed(3)}ms`,
          );
        }
      }
    }
    await browser.close();
    browser = null;
  }
  report.status = "measured";
} catch (error) {
  report.status = "failed";
  report.failure = error.message;
  process.exitCode = 1;
  console.error(error.message);
} finally {
  try {
    await browser?.close();
  } catch (error) {
    report.status = "failed";
    report.cleanupFailure = error.message;
    process.exitCode = 1;
  }
  report.finished = new Date().toISOString();
  writeFileSync(output, JSON.stringify(report, null, 2) + "\n", { flag: "wx" });
}
