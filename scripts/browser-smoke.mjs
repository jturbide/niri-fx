// Run against an offline preview or an isolated studio --registry test path.
// Requires Node 22+ and Chromium. Saves review images in the ignored artifacts/.
import { execFileSync } from "node:child_process";
import { appendFileSync, mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { createHash } from "node:crypto";
import assert from "node:assert/strict";
import { parseArgs } from "node:util";
import { setTimeout as sleep } from "node:timers/promises";
import { checkResize } from "./lib/resize-checks.mjs";
import { checkMotion } from "./lib/motion-checks.mjs";
import { checkShapes } from "./lib/shape-checks.mjs";
import { launchBrowser, projectRoot } from "./lib/browser.mjs";

process.chdir(projectRoot);

const { values: options, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    suite: { type: "string", default: "all" },
    "shape-aspect": { type: "string" },
    "save-test": { type: "boolean", default: false },
  },
});
const [url] = positionals;
if (!url || positionals.length !== 1)
  throw new Error(
    "Usage: node scripts/browser-smoke.mjs PREVIEW_URL [--suite all|studio|shapes|motion] [--shape-aspect 0.25|1|4] [--save-test]",
  );
assert(["all", "studio", "shapes", "motion"].includes(options.suite), "Unknown browser suite");
const shapeAspect = options["shape-aspect"];
assert(
  shapeAspect === undefined ||
    (options.suite === "shapes" && ["0.25", "1", "4"].includes(shapeAspect)),
  "--shape-aspect requires --suite shapes and one of 0.25, 1, 4",
);
const hasStudio = ["all", "studio"].includes(options.suite);
assert(!options["save-test"] || hasStudio, "--save-test requires the all or studio suite");
const suiteStarted = performance.now();
let stageStarted = suiteStarted;
let status = "failed";
const timings = [];
const finishStage = (name) => {
  const milliseconds = Math.round(performance.now() - stageStarted);
  timings.push({ name, milliseconds });
  console.log(`TIMING: ${name} ${milliseconds} ms`);
  stageStarted = performance.now();
};
const browser = await launchBrowser();
const { rpc, evaluate, callFunction } = browser;
const sample = () =>
  evaluate(
    `(()=>{const canvas=byId('stage'),gl=canvas.getContext('webgl');const pixels=new Uint8Array(canvas.width*canvas.height*4);gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);let alpha=0,x=0,y=0,occupied=0;for(let i=0;i<pixels.length;i+=4){const a=pixels[i+3];if(a){const px=(i/4)%canvas.width,py=canvas.height-1-Math.floor(i/4/canvas.width);alpha+=a;x+=px*a;y+=py*a;occupied++;}}return {occupied,alpha,cx:alpha?x/alpha:0,cy:alpha?y/alpha:0,error:gl.getError()};})()`,
  );
const setProgress = async (value) => {
  await evaluate(
    `byId('progress').value=${Math.round(value * 1000)};byId('progress').dispatchEvent(new Event('input'))`,
  );
};
try {
  await browser.navigate(url, { width: 1380, height: 1120 });
  finishStage("browser-startup");
  if (["all", "shapes"].includes(options.suite)) {
    await checkShapes(evaluate, shapeAspect === undefined ? undefined : [Number(shapeAspect)]);
    finishStage("shapes");
  }
  if (["all", "motion"].includes(options.suite)) {
    await checkMotion(evaluate, setProgress, sample);
    finishStage("motion");
  }
  if (hasStudio) await checkStudio();
  status = "passed";
} finally {
  await browser.close();
  finishStage(status === "passed" ? "browser-cleanup" : "failed-stage-and-cleanup");
  const milliseconds = Math.round(performance.now() - suiteStarted);
  console.log(`TIMING: total ${milliseconds} ms (${options.suite}, ${status})`);
  if (process.env.GITHUB_STEP_SUMMARY) {
    appendFileSync(
      process.env.GITHUB_STEP_SUMMARY,
      `## Browser ${options.suite}${shapeAspect ? ` (aspect ${shapeAspect})` : ""}: ${status}\n\n` +
        "| Stage | Seconds |\n| --- | ---: |\n" +
        timings
          .map(({ name, milliseconds }) => `| ${name} | ${(milliseconds / 1000).toFixed(3)} |`)
          .join("\n") +
        `\n| Total | ${(milliseconds / 1000).toFixed(3)} |\n`,
    );
  }
  if (process.env.NIRIFX_TIMINGS) {
    writeFileSync(
      process.env.NIRIFX_TIMINGS,
      JSON.stringify(
        { suite: options.suite, shapeAspect, status, milliseconds, stages: timings },
        null,
        2,
      ) + "\n",
    );
  }
}

async function checkStudio() {
  const initialDocument = await evaluate("effectDocument()");
  assert.equal(
    await evaluate("getComputedStyle(byId('spin').closest('.parameter')).display"),
    "none",
  );
  await evaluate(
    "byId('advanced').checked=true;byId('advanced').dispatchEvent(new Event('change'))",
  );
  assert.notEqual(
    await evaluate("getComputedStyle(byId('spin').closest('.parameter')).display"),
    "none",
  );
  assert.deepEqual(
    await evaluate("effectDocument()"),
    initialDocument,
    "view changes preserve all settings",
  );
  await evaluate("byId('reduced-motion').checked=true;byId('close').click()");
  assert.equal(await evaluate("progress"), 1, "reduced motion shows the endpoint without playback");
  await evaluate("byId('open').click()");
  assert.equal(await evaluate("progress"), 0);
  assert.deepEqual(
    await evaluate("effectDocument()"),
    initialDocument,
    "preview motion preference does not alter exports",
  );
  await evaluate(
    "byId('reduced-motion').checked=false;byId('advanced').checked=false;byId('advanced').dispatchEvent(new Event('change'))",
  );
  finishStage("editor-preferences");
  const expected = JSON.parse(
    execFileSync(
      "python3",
      [
        "-c",
        "import hashlib,json;from niri_fx.effects import PRESETS,shader;print(json.dumps({k:hashlib.sha256(shader(v,False).encode()).hexdigest() for k,v in PRESETS.items()}))",
      ],
      { encoding: "utf8" },
    ),
  );
  const results = {};
  mkdirSync("artifacts", { recursive: true });
  for (const name of Object.keys(expected)) {
    await evaluate(
      `byId('preset').value=${JSON.stringify(name)};byId('preset').dispatchEvent(new Event('change'))`,
    );
    assert.equal(await evaluate("document.documentElement?.dataset.shaderStatus"), "ready", name);
    assert.equal(
      createHash("sha256")
        .update(await evaluate("shaderFor(parameters,false)"))
        .digest("hex"),
      expected[name],
      name + " export matches Python",
    );
    await setProgress(0);
    const start = await sample();
    assert.equal(start.occupied, 600 * 380, name + " reconstructs all pixels");
    await setProgress(0.45);
    const middle = await sample();
    assert(middle.alpha > 0 && middle.alpha < start.alpha, name + " visible partial transition");
    assert.equal(middle.error, 0);
    if (
      [
        "balanced",
        "explosion",
        "implosion",
        "earth",
        "black-hole",
        "vortex",
        "space",
        "slide-apart",
        "alternating-blinds",
        "diagonal-shear",
        "shuffled-slats",
        "tidal-fragments",
        "mosaic-burst",
        "spring-wobble",
        "ember-erosion",
        "frost-vanish",
        "pixel-wipe",
        "pixelate",
        "dust-drift",
        "ghost-wisps",
        "ink-current",
        "shockwave",
        "ripple-collapse",
        "wave-fold",
      ].includes(name)
    ) {
      const capture = await rpc("Page.captureScreenshot", { format: "png" });
      writeFileSync(resolve("artifacts", name + ".png"), Buffer.from(capture.data, "base64"));
    }
    await setProgress(1);
    const end = await sample();
    assert.equal(end.occupied, 0, name + " disappears completely");
    results[name] = { start, middle, end };
  }
  assert(results.earth.middle.cy > results.balanced.middle.cy + 25, "Earth moves downward");
  assert(results.updraft.middle.cy < results.balanced.middle.cy - 20, "Updraft moves upward");
  assert(
    results["black-hole"].middle.occupied < results.balanced.middle.occupied / 2,
    "Black hole contracts",
  );
  // Check extreme controls through the real UI, then save only if explicitly requested.
  await evaluate("byId('preset').value='vortex';byId('preset').dispatchEvent(new Event('change'))");
  for (const [id, value] of Object.entries({
    particles: 4096,
    gravity_strength: 3,
    spin: 720,
    swirl: 360,
    dispersion: 1,
    stagger: 0.4,
  }))
    await evaluate(
      `byId(${JSON.stringify(id)}).value=${JSON.stringify(value)};byId(${JSON.stringify(id)}).dispatchEvent(new Event('input'))`,
    );
  await setProgress(0.5);
  assert.equal((await sample()).error, 0);
  assert.equal(await evaluate("document.documentElement?.dataset.shaderStatus"), "ready");
  finishStage("preset-parity-and-extremes");
  // Exercise the real resize shader, two texture inputs and stable endpoints.
  const resizeExpected = JSON.parse(
    execFileSync(
      "python3",
      [
        "-c",
        'import hashlib,json;from niri_fx.effects import PRESETS,FAMILIES,resize_shader;print(json.dumps({k:hashlib.sha256(resize_shader(v).encode()).hexdigest() for k,v in PRESETS.items() if FAMILIES[v.family]["resize"]}))',
      ],
      { encoding: "utf8" },
    ),
  );
  await evaluate(
    "byId('preset').value='balanced';byId('preset').dispatchEvent(new Event('change'));document.querySelector('[data-mode=resize]').click()",
  );
  for (const name of Object.keys(resizeExpected)) {
    await evaluate(
      `byId('preset').value=${JSON.stringify(name)};byId('preset').dispatchEvent(new Event('change'))`,
    );
    assert.equal(
      createHash("sha256")
        .update(await evaluate("shaderFor(parameters,false,true)"))
        .digest("hex"),
      resizeExpected[name],
      name + " resize export parity",
    );
    await setProgress(0);
    assert.equal((await sample()).occupied, 600 * 380, name + " resize starts intact");
    await setProgress(0.5);
    const middle = await sample();
    assert(
      middle.occupied > 0 && middle.occupied <= 700 * 410,
      name + " resize retains visible content",
    );
    assert.equal(middle.error, 0);
    await setProgress(1);
    assert.equal((await sample()).occupied, 800 * 440, name + " resize ends intact");
  }
  const pixel = () =>
    evaluate(
      `(()=>{const gl=byId('stage').getContext('webgl'),p=new Uint8Array(4);gl.readPixels(500,200,1,1,gl.RGBA,gl.UNSIGNED_BYTE,p);return Array.from(p);})()`,
    );
  await setProgress(0);
  const oldPixel = await pixel();
  await setProgress(1);
  assert.notDeepEqual(await pixel(), oldPixel, "resize switches to the new texture contents");
  await setProgress(0.5);
  const resizeCapture = await rpc("Page.captureScreenshot", { format: "png" });
  writeFileSync("artifacts/resize.png", Buffer.from(resizeCapture.data, "base64"));
  // Opt-in resize styles retain endpoints and preserve more content than full breakup.
  await evaluate(
    "byId('preset').value='balanced';byId('preset').dispatchEvent(new Event('change'))",
  );
  const resizeModes = {};
  for (const name of ["full", "edge", "soft"]) {
    await evaluate(
      `byId('resize_mode').value=${JSON.stringify(name)};byId('resize_mode').dispatchEvent(new Event('input'))`,
    );
    assert.equal(
      await evaluate("parameters.resize"),
      false,
      "choosing a resize style is not opt-in",
    );
    await setProgress(0);
    assert.equal((await sample()).occupied, 600 * 380);
    await setProgress(0.5);
    resizeModes[name] = await sample();
    assert.equal(resizeModes[name].error, 0);
    if (name === "edge")
      assert(
        await evaluate(
          `(()=>{const gl=byId('stage').getContext('webgl'),data=new Uint8Array(40*40*4);gl.readPixels(480,360,40,40,gl.RGBA,gl.UNSIGNED_BYTE,data);for(let i=3;i<data.length;i+=4)if(data[i]!==255)return false;return true;})()`,
        ),
        "edge mode keeps central content intact",
      );
    await setProgress(1);
    assert.equal((await sample()).occupied, 800 * 440);
  }
  assert(resizeModes.edge.alpha > resizeModes.full.alpha, "edge mode retains more content");
  assert(resizeModes.soft.alpha > resizeModes.full.alpha, "soft mode retains more content");
  await checkResize(evaluate, setProgress, sample, callFunction);
  finishStage("resize");
  // Both textured windows must exchange positions intact, with a visible
  // intermediate stream. The movement prototype must remain labelled as such.
  await evaluate(
    "byId('preset').value='balanced';byId('preset').dispatchEvent(new Event('change'));document.querySelector('[data-mode=swap]').click()",
  );
  assert.equal(await evaluate("byId('concept-note').hidden"), false);
  const sameImage = (a, b, message) => {
    let delta = 0;
    for (let i = 0; i < a.length; i++) delta = Math.max(delta, Math.abs(a[i] - b[i]));
    assert(delta <= 2, message + " (Canvas resampling tolerance 2/255, got " + delta + ")");
  };
  const columns = () =>
    evaluate(
      `(()=>{const c=byId('motion-stage').getContext('2d');return [65,555].map(x=>Array.from(c.getImageData(x,250,380,240).data));})()`,
    );
  await setProgress(0);
  const before = await columns();
  await setProgress(0.5);
  const during = await columns();
  assert.notDeepEqual(during, before, "swap has intermediate fragments");
  const swapCapture = await rpc("Page.captureScreenshot", { format: "png" });
  writeFileSync("artifacts/swap.png", Buffer.from(swapCapture.data, "base64"));
  await setProgress(1);
  const after = await columns();
  sameImage(after[0], before[1], "second window arrives intact");
  sameImage(after[1], before[0], "first window arrives intact");
  await evaluate("document.querySelector('[data-mode=move]').click()");
  await setProgress(0);
  const moveBefore = await columns();
  await setProgress(1);
  const moveAfter = await columns();
  sameImage(moveAfter[1], moveBefore[0], "move arrives intact");
  assert(
    await evaluate(`(()=>{
    const canvas=document.createElement('canvas');canvas.width=1000;canvas.height=760;
    const preview=new MotionPreview(canvas,canvas);
    const p={...catalog.defaults,particles:4096,size_variation:1,fragment_roundness:1,fragment_shrink:1,release:'checkerboard'};
    for(const seed of [0,0.37,0.99]) {
      const parts=preview.particles(0.5,'swap',p,seed);
      if(!parts.length || parts.some(part=>part.sw<=0 || part.sh<=0 || part.scale<=0)) return false;
      preview.draw(0.5,'swap',p,seed);
    }
    return true;
  })()`),
    "unequal rounded concept pieces remain drawable at texture boundaries",
  );
  await evaluate("document.querySelector('[data-mode=effect]').click()");
  finishStage("move-swap-concepts");
  // Import through the real file input; failed imports leave the editor untouched.
  const importFile = async (text) =>
    callFunction(
      `async function(text) { const transfer=new DataTransfer();transfer.items.add(new File([text],'preset.json',{type:'application/json'}));byId('import-file').files=transfer.files;await byId('import-file').onchange();return {effect:effectDocument(),error:byId('error').textContent,status:byId('status').textContent}; }`,
      [text],
    );
  const importedDoc = {
    schema: 3,
    name: "Imported Exact",
    effect: {
      gravity: "up",
      gravity_strength: 0.833,
      open_ms: 723,
      release: "right",
      origin_x: 0.123,
      resize_mode: "edge",
    },
  };
  let imported = await importFile(JSON.stringify(importedDoc));
  assert.equal(imported.error, "");
  assert.equal(imported.effect.name, importedDoc.name);
  assert.equal(imported.effect.effect.gravity_strength, 0.833);
  assert.equal(imported.effect.effect.resize, false);
  await evaluate("byId('spin').dispatchEvent(new Event('input'))");
  assert.equal(
    await evaluate("parameters.gravity_strength"),
    0.833,
    "unrelated edits preserve imported precision",
  );
  assert.equal(await evaluate("parameters.open_ms"), 723);
  const saved = await evaluate("effectDocument()");
  for (const invalid of [
    "{broken",
    JSON.stringify({ schema: true, name: "Bad", effect: {} }),
    JSON.stringify({ schema: 3, name: "Bad", effect: { gravity: "typo" } }),
    JSON.stringify({ schema: 3, name: "Bad", effect: { shader: "injection" } }),
    JSON.stringify({ schema: 3, name: "Bad", effect: { resize: 1 } }),
    " ".repeat(16385),
  ]) {
    const result = await importFile(invalid);
    assert.match(result.error, /Import failed/);
    assert.deepEqual(result.effect, saved);
  }
  imported = await importFile(
    JSON.stringify({
      schema: 3,
      name: "Resize import",
      effect: { resize: true, resize_mode: "soft" },
    }),
  );
  assert.equal(imported.error, "");
  assert.equal(imported.effect.effect.resize, true);
  await importFile(JSON.stringify({ schema: 3, name: "Default import", effect: {} }));
  assert.equal(await evaluate("parameters.resize"), false);
  // Family-specific UI, versioned slice imports and bounded extreme controls.
  assert.equal(await evaluate("parameters.family"), "fragments", "default family is fragments");
  assert.equal(await evaluate("effectDocument().schema"), 3, "all exports use the current schema");
  await evaluate("document.querySelector('[data-mode=resize]').click()");
  imported = await importFile(
    JSON.stringify({
      schema: 3,
      name: "Sliced Test",
      effect: { family: "slices", slice_count: 13, slice_angle: -33.25, slice_rotation: 12.5 },
    }),
  );
  assert.equal(imported.error, "");
  assert.equal(imported.effect.schema, 3);
  assert.equal(imported.effect.effect.family, "slices");
  assert.equal(await evaluate("mode"), "resize", "slice import retains supported resize preview");
  assert.equal(await evaluate("byId('fragment-controls').hidden"), true);
  assert.equal(await evaluate("byId('slice-controls').hidden"), false);
  assert(
    await evaluate(
      "[...document.querySelectorAll('[data-mode]')].filter(b=>['move','swap'].includes(b.dataset.mode)).every(b=>b.disabled)",
    ),
    "unsupported modes disabled",
  );
  await evaluate("document.querySelector('[data-mode=effect]').click()");
  const sliceSaved = await evaluate("effectDocument()");
  for (const effect of [
    { family: "wisps", resize: true },
    { family: "slices", slice_count: 1 },
    { family: "unknown" },
    { family: "slices", slice_direction: "typo" },
  ]) {
    const rejected = await importFile(JSON.stringify({ schema: 3, name: "Invalid Slice", effect }));
    assert.match(rejected.error, /Import failed/);
    assert.deepEqual(rejected.effect, sliceSaved);
  }
  for (const schema of [1, 2, 4]) {
    const unsupported = await importFile(
      JSON.stringify({ schema, name: "Unsupported format", effect: {} }),
    );
    assert.match(unsupported.error, /schema: 3/);
    assert.deepEqual(unsupported.effect, sliceSaved);
  }
  for (const [id, value] of Object.entries({
    slice_count: 48,
    slice_angle: -90,
    slice_distance: 600,
    slice_stagger: 0.75,
    slice_rotation: 60,
    slice_direction: "negative",
  }))
    await evaluate(
      `byId(${JSON.stringify(id)}).value=${JSON.stringify(value)};byId(${JSON.stringify(id)}).dispatchEvent(new Event('input'))`,
    );
  assert.equal(
    await evaluate("parameters.slice_direction"),
    "negative",
    "slice direction responds immediately",
  );
  await setProgress(0);
  assert.equal((await sample()).occupied, 600 * 380);
  await setProgress(0.5);
  assert.equal((await sample()).error, 0);
  await setProgress(1);
  assert.equal((await sample()).occupied, 0);
  const exportedSlice = await evaluate("effectDocument()");
  const normalizedSlice = JSON.parse(
    execFileSync(
      "python3",
      [
        "-c",
        "import json,sys;from niri_fx.documents import parse_document,effect_document;doc=json.load(sys.stdin);name,_,effect=parse_document(doc);print(json.dumps(effect_document(name,effect)))",
      ],
      { input: JSON.stringify(exportedSlice), encoding: "utf8" },
    ),
  );
  assert.deepEqual(exportedSlice, normalizedSlice);
  await evaluate(
    "byId('family').value='fragments';byId('family').dispatchEvent(new Event('change'))",
  );
  assert.equal(await evaluate("parameters.resize"), false);
  assert.equal(await evaluate("byId('slice-controls').hidden"), true);
  finishStage("imports");
  // New controls must visibly affect pixels, round-trip exactly and remain deterministic.
  const pixelHash = () =>
    evaluate(
      `(()=>{const g=byId('stage').getContext('webgl'),a=new Uint8Array(1000*760*4);g.readPixels(0,0,1000,760,g.RGBA,g.UNSIGNED_BYTE,a);let h=2166136261;for(const b of a)h=Math.imul(h^b,16777619);return h>>>0;})()`,
    );
  for (const preset of ["slide-apart", "balanced"]) {
    await evaluate(
      `byId('preset').value=${JSON.stringify(preset)};byId('preset').dispatchEvent(new Event('change'))`,
    );
    await setProgress(0.35);
    const baseline = await pixelHash();
    for (const field of ["size_variation", "direction_variation", "wave_strength"]) {
      await evaluate(
        `byId(${JSON.stringify(field)}).value=1;byId(${JSON.stringify(field)}).dispatchEvent(new Event('input'))`,
      );
      assert.notEqual(
        await pixelHash(),
        baseline,
        preset + " " + field + " changes the rendered image",
      );
      assert.equal(await evaluate("effectDocument().schema"), 3);
      const snapshot = await pixelHash();
      await setProgress(0.35);
      assert.equal(await pixelHash(), snapshot, "redrawing does not reroll randomness");
      await evaluate(
        `byId(${JSON.stringify(field)}).value=0;byId(${JSON.stringify(field)}).dispatchEvent(new Event('input'))`,
      );
    }
  }
  // Each new control must independently change real pixels, survive an export/
  // import round trip, and retain intact/transparent endpoints.
  for (const [preset, changes] of [
    ["balanced", { fragment_shrink: 0.9, fragment_roundness: 1 }],
    ["hinged-fan", { slice_pivot: 1, slice_collapse: 1 }],
    [
      "spring-wobble",
      {
        elastic_twist: 80,
        elastic_stretch: 1,
        elastic_ripple: 4,
        elastic_anchor: "bottom-right",
      },
    ],
  ]) {
    for (const [field, value] of Object.entries(changes)) {
      await evaluate(
        `byId('preset').value=${JSON.stringify(preset)};byId('preset').dispatchEvent(new Event('change'))`,
      );
      await setProgress(0.37);
      const before = await pixelHash(),
        area = (await sample()).occupied;
      await evaluate(
        `byId(${JSON.stringify(field)}).value=${JSON.stringify(value)};byId(${JSON.stringify(field)}).dispatchEvent(new Event('input'))`,
      );
      assert.notEqual(await pixelHash(), before, field + " visibly changes the shader");
      if (["fragment_shrink", "fragment_roundness", "slice_collapse"].includes(field))
        assert((await sample()).occupied < area, field + " reduces visible piece area");
      const doc = await evaluate("effectDocument()");
      assert.equal((await importFile(JSON.stringify(doc))).error, "");
      assert.deepEqual(await evaluate("effectDocument()"), doc);
      for (const p of [0.001, 0.99]) {
        await setProgress(p);
        assert.equal((await sample()).error, 0);
      }
      await setProgress(0);
      assert.equal((await sample()).occupied, 600 * 380);
      await setProgress(1);
      assert.equal((await sample()).occupied, 0);
    }
  }
  const releaseImages = new Set();
  for (const release of ["center", "edges", "diagonal", "checkerboard"]) {
    assert.equal(
      (
        await importFile(
          JSON.stringify({
            schema: 3,
            name: "Spatial release",
            effect: { release, scatter: 100, stagger: 0 },
          }),
        )
      ).error,
      "",
    );
    await setProgress(0.23);
    releaseImages.add(await pixelHash());
    assert.equal((await sample()).error, 0);
  }
  assert.equal(releaseImages.size, 4, "each spatial release has a distinct pattern");
  for (const family of ["fragments", "slices"]) {
    const doc = {
      schema: 3,
      name: "Extreme variation",
      effect: {
        family,
        size_variation: 1,
        direction_variation: 1,
        wave_strength: 1,
        wave_frequency: 0.25,
        wave_speed: 4,
        ...(family === "slices"
          ? {
              slice_count: 48,
              slice_order: "random",
              slice_direction: "random",
              slice_travel_variation: 1,
              slice_rotation_variation: 1,
              slice_rotation: 60,
              slice_pivot: -1,
              slice_collapse: 1,
            }
          : {
              gravity: "center",
              gravity_strength: 3,
              particles: 4096,
              release: "edges",
              fragment_roundness: 1,
              fragment_shrink: 1,
              wave_span: 0.7,
            }),
      },
    };
    assert.equal((await importFile(JSON.stringify(doc))).error, "");
    for (const p of [0, 0.01, 0.45, 0.99, 1]) {
      await setProgress(p);
      assert.equal((await sample()).error, 0);
    }
    const saved = await evaluate("effectDocument()");
    assert.equal((await importFile(JSON.stringify(saved))).error, "");
    assert.deepEqual(await evaluate("effectDocument()"), saved);
    assert.match((await importFile(JSON.stringify({ ...doc, schema: 2 }))).error, /schema: 3/);
  }
  await evaluate(
    "byId('preset').value='spring-wobble';byId('preset').dispatchEvent(new Event('change'))",
  );
  await setProgress(0.27);
  assert.equal(await evaluate("byId('elastic-controls').hidden"), false);
  assert.equal(await evaluate("byId('slice-controls').hidden"), true);
  assert.equal(await evaluate("byId('fragment-controls').hidden"), true);
  const elasticBase = await pixelHash();
  for (const [id, value] of Object.entries({
    elastic_strength: 1,
    elastic_frequency: 5,
    elastic_damping: 0,
    elastic_axis: "vertical",
    elastic_twist: -90,
    elastic_stretch: 1,
    elastic_ripple: 4,
    elastic_anchor: "top-left",
  }))
    await evaluate(
      `byId(${JSON.stringify(id)}).value=${JSON.stringify(value)};byId(${JSON.stringify(id)}).dispatchEvent(new Event('input'))`,
    );
  assert.notEqual(await pixelHash(), elasticBase);
  assert.equal((await sample()).error, 0);
  await setProgress(0);
  assert.equal((await sample()).occupied, 600 * 380);
  await setProgress(1);
  assert.equal((await sample()).occupied, 0);
  await evaluate(
    "byId('preset').value='balanced';byId('preset').dispatchEvent(new Event('change'))",
  );
  finishStage("variation-controls");
  // Independent actions must survive selection, editing, undo and export.
  await evaluate(
    `byId('preset').value='spring-wobble';byId('preset').dispatchEvent(new Event('change'));byId('independent').checked=true;byId('independent').dispatchEvent(new Event('change'));byId('action').value='close';byId('action').dispatchEvent(new Event('change'));byId('preset').value='ember-erosion';byId('preset').dispatchEvent(new Event('change'));byId('name').value='Browser Profile';`,
  );
  const profileDocument = await evaluate("effectDocument()");
  assert.equal(profileDocument.actions.open.family, "elastic");
  assert.equal(profileDocument.actions.close.family, "dissolve");
  assert.equal(profileDocument.actions.resize, null);
  const profileExpected = JSON.parse(
    execFileSync(
      "python3",
      [
        "-c",
        "import json,sys;from niri_fx.documents import parse_document;from niri_fx.effects import animation_types;print(json.dumps(animation_types(parse_document(json.load(sys.stdin))[2])))",
      ],
      { input: JSON.stringify(profileDocument), encoding: "utf8" },
    ),
  );
  for (const action of ["open", "close"])
    assert.equal(
      await evaluate(`shaderFor(effectDocument().actions.${action}, ${action === "open"})`),
      profileExpected["window-" + action]["custom-shader"],
    );
  assert(!(await evaluate("kdlDocument().includes('window-resize')")));
  await evaluate(
    "byId('action').value='open';byId('action').dispatchEvent(new Event('change'));byId('elastic_twist').value=33;byId('elastic_twist').dispatchEvent(new Event('input'))",
  );
  assert.equal(await evaluate("effectDocument().actions.open.elastic_twist"), 33);
  assert.equal(await evaluate("effectDocument().actions.close.family"), "dissolve");
  await evaluate("byId('undo').click()");
  assert.equal(await evaluate("effectDocument().actions.open.elastic_twist"), 0);
  await evaluate("byId('redo').click()");
  assert.equal(await evaluate("effectDocument().actions.open.elastic_twist"), 33);
  await evaluate("document.querySelector('[data-reset=elastic_twist]').click()");
  assert.equal(await evaluate("effectDocument().actions.open.elastic_twist"), 0);
  const profileSaved = await evaluate("effectDocument()");
  await evaluate(`window.downloadFixture={click:HTMLAnchorElement.prototype.click,url:URL.createObjectURL};
  HTMLAnchorElement.prototype.click=function(){downloadFixture.name=this.download};
  URL.createObjectURL=function(blob){downloadFixture.blob=blob;return downloadFixture.url.call(URL,blob)};`);
  for (const target of ["standalone", "noctalia"]) {
    await evaluate(
      `byId('save-target').value=${JSON.stringify(target)};byId('save-target').dispatchEvent(new Event('change'));byId('save').click()`,
    );
    assert.equal(await evaluate("byId('save').disabled"), false);
    assert.match(await evaluate("downloadFixture.name"), /^nirifx-.+\.kdl$/);
    assert.equal(await evaluate("downloadFixture.blob.text()"), await evaluate("kdlDocument()"));
    assert(!(await evaluate("byId('save-help').textContent.includes('iRiS Settings')")));
  }
  await evaluate(
    "HTMLAnchorElement.prototype.click=downloadFixture.click;URL.createObjectURL=downloadFixture.url;delete window.downloadFixture;byId('save-target').value=catalog.save_target;byId('save-target').dispatchEvent(new Event('change'))",
  );
  await evaluate("byId('action').value='resize';byId('action').dispatchEvent(new Event('change'))");
  assert.equal((await importFile(JSON.stringify(profileSaved))).error, "");
  assert.equal(await evaluate("byId('action').value"), "open", "import selects the shown action");
  assert.deepEqual(await evaluate("effectDocument()"), profileSaved);
  await evaluate("byId('action').value='resize';byId('action').dispatchEvent(new Event('change'))");
  assert.equal(
    await evaluate("effectDocument().actions.resize"),
    null,
    "viewing resize never enables it",
  );
  await evaluate(
    "byId('action-mode').value='style';byId('action-mode').dispatchEvent(new Event('change'))",
  );
  assert(await evaluate("kdlDocument().includes('window-resize')"));
  assert.equal(await evaluate("effectDocument().actions.open.family"), "elastic");
  const resizeProfile = await evaluate("effectDocument()");
  const resizeImport = await importFile(JSON.stringify(resizeProfile));
  assert.equal(resizeImport.error, "");
  assert.match(resizeImport.status, /Resize override: included/);
  assert.deepEqual(resizeImport.effect, resizeProfile);
  await evaluate("byId('action').value='resize';byId('action').dispatchEvent(new Event('change'))");
  await evaluate(
    "byId('action-mode').value='preserve';byId('action-mode').dispatchEvent(new Event('change'))",
  );
  assert(!(await evaluate("kdlDocument().includes('window-resize')")));
  if (options["save-test"]) {
    await evaluate("byId('name').value='Browser Profile';byId('save').click()");
    for (let i = 0; i < 100 && (await evaluate("byId('save').disabled")); i++) await sleep(100);
    assert.equal(await evaluate("byId('error').textContent"), "");
    assert.match(await evaluate("byId('status').textContent"), /^Saved NiriFX/);
  }
  finishStage("independent-actions");
  await importFile(JSON.stringify({ schema: 3, name: "Reveal Test", effect: { family: "iris" } }));
  for (const [preset, changes] of Object.entries({
    "ember-erosion": {
      dissolve_scale: 12,
      dissolve_softness: 0.2,
      dissolve_direction: "left",
      dissolve_bias: 0.1,
      edge_width: 0.3,
      edge_hue: 220,
      dissolve_detail: 0,
      dissolve_flow: 1.5,
      edge_saturation: 1,
      edge_brightness: 0,
      edge_char: 0,
    },
    "pixel-wipe": {
      pixel_size: 32,
      pixel_direction: "down",
      pixel_randomness: 0.85,
      pixel_softness: 0.38,
      pixel_x: 0.1,
      pixel_y: 0.1,
    },
    "dust-drift": { pixel_travel: 1, pixel_wind: "right" },
    "ghost-wisps": {
      wisp_scale: 90,
      wisp_strands: 8,
      wisp_curl: 1.6,
      wisp_drift: 220,
      wisp_angle: 35,
      wisp_speed: 3,
      wisp_glow: 0,
      wisp_softness: 0.28,
    },
    shockwave: {
      distortion_mode: "ripple",
      distortion_strength: 65,
      distortion_wavelength: 160,
      distortion_width: 220,
      distortion_cycles: 3.5,
      distortion_falloff: 3.8,
      distortion_x: 0.1,
      distortion_y: 0.1,
    },
    "wave-fold": { distortion_angle: -45, distortion_fade: 0.8 },
    "vortex-fold": {
      distortion_twist: -270,
      distortion_contract: 0,
      distortion_falloff: 0,
      distortion_x: 0.15,
      distortion_y: 0.85,
    },
    "hexagon-burst": {
      hex_size: 42,
      hex_spread: 0.2,
      hex_spin: 330,
      hex_direction: "inward",
      hex_stagger: 0.65,
    },
    "ink-spread": {
      dissolve_mode: "noise",
      dissolve_turbulence: 0.1,
      dissolve_x: 0.1,
      dissolve_y: 0.1,
    },
    "signal-glitch": { glitch_bands: 8, glitch_chroma: 1 },
    "diamond-turn": {
      iris_shape: "square",
      iris_direction: "outward",
      iris_softness: 0.2,
      iris_twist: -140,
      iris_x: 0.1,
      iris_y: 0.85,
    },
  })) {
    for (const [key, value] of Object.entries(changes)) {
      await evaluate(
        `byId('preset').value=${JSON.stringify(preset)};byId('preset').dispatchEvent(new Event('change'))`,
      );
      await setProgress(0.45);
      if (key === "edge_hue")
        await evaluate(
          "byId('edge_saturation').value=1;byId('edge_saturation').dispatchEvent(new Event('input'))",
        );
      const before = await pixelHash();
      await evaluate(
        `byId(${JSON.stringify(key)}).value=${JSON.stringify(value)};byId(${JSON.stringify(key)}).dispatchEvent(new Event('input'))`,
      );
      assert.notEqual(await pixelHash(), before, key + " independently changes pixels");
      assert.equal((await sample()).error, 0);
    }
  }
  finishStage("family-controls");
  await evaluate("byId('pin').click()");
  const pinnedHash = await pixelHash();
  await evaluate("byId('iris_x').value=0.9;byId('iris_x').dispatchEvent(new Event('input'))");
  const editedHash = await pixelHash(),
    editedDocument = await evaluate("effectDocument()");
  assert.notEqual(editedHash, pinnedHash);
  await evaluate("byId('compare').click()");
  assert.equal(await pixelHash(), pinnedHash);
  assert.deepEqual(await evaluate("effectDocument()"), editedDocument, "A/B is non-destructive");
  await evaluate("byId('compare').click()");
  assert.equal(await pixelHash(), editedHash);
  await evaluate(
    "byId('preset').value='iris-bloom';byId('preset').dispatchEvent(new Event('change'));byId('favorite').click();byId('search').value='iris bloom';byId('search').dispatchEvent(new Event('input'))",
  );
  assert.deepEqual(
    await evaluate(
      "Array.from(byId('preset').options).filter(option => option.value && !option.hidden).map(option => option.value)",
    ),
    ["iris-bloom"],
  );
  await evaluate("byId('search').value='';byId('search').dispatchEvent(new Event('input'))");
  const roundingDoc = {
    schema: 3,
    name: "Rounding",
    effect: { family: "slices", wave_strength: 0.0078125, slice_rotation: -0.0078125 },
  };
  await importFile(JSON.stringify(roundingDoc));
  const rounded = execFileSync(
    "python3",
    [
      "-c",
      "import sys,json;from niri_fx.documents import parse_document;from niri_fx.effects import shader;print(shader(parse_document(json.load(sys.stdin))[2],False),end='')",
    ],
    { input: JSON.stringify(roundingDoc), encoding: "utf8" },
  );
  assert.equal(await evaluate("shaderFor(parameters,false)"), rounded);
  const unsupported = await evaluate("window.niriFxBenchmark({samples:10})");
  assert.equal(unsupported.status, "unsupported", "software WebGL must not claim GPU performance");
  // Vortex controls are inactive for waves and the independent ripple resize.
  // Changing views preserves them and never opts into resize.
  await evaluate(
    "byId('preset').value='vortex-fold';byId('preset').dispatchEvent(new Event('change'))",
  );
  const vortexDocument = await evaluate("effectDocument()");
  assert.equal(await evaluate("byId('distortion_twist').disabled"), false);
  assert.equal(await evaluate("byId('distortion_strength').disabled"), true);
  await evaluate("document.querySelector('[data-mode=resize]').click()");
  assert.equal(await evaluate("byId('distortion_twist').disabled"), true);
  assert.equal(await evaluate("byId('distortion_strength').disabled"), false);
  assert.deepEqual(await evaluate("effectDocument()"), vortexDocument);
  await evaluate("document.querySelector('[data-mode=effect]').click()");
  // Exercise signed twists, the smallest legal scale, corner origins and
  // non-square geometry through the real shader, including exact endpoints.
  for (const [twist, contraction, origin, geometry] of [
    [-720, 0.95, 0, [900, 280]],
    [720, 0.95, 1, [280, 660]],
    [0, 0, 0.5, [600, 380]],
    [720, 0.95, 0.5, [5, 3]],
  ]) {
    await importFile(
      JSON.stringify({
        schema: 3,
        name: "Vortex extrema",
        effect: {
          family: "distortion",
          distortion_mode: "vortex",
          distortion_twist: twist,
          distortion_contract: contraction,
          distortion_x: origin,
          distortion_y: origin,
        },
      }),
    );
    for (const position of [0, 0.001, 0.5, 0.999, 1]) {
      await setProgress(position);
      await evaluate(`(() => { const gl=byId('stage').getContext('webgl');
      gl.uniform2f(gl.getUniformLocation(gl.getParameter(gl.CURRENT_PROGRAM),'fx_window'),${geometry.join(",")});
      gl.drawArrays(gl.TRIANGLES,0,6);gl.finish(); })()`);
      const pixels = await sample();
      assert.equal(pixels.error, 0, "vortex extreme renders without GL errors");
      if (position === 0) assert(pixels.occupied > 0, "vortex starts intact");
      if (position === 1) assert.equal(pixels.occupied, 0, "vortex ends transparent");
    }
  }
  finishStage("editor-capabilities-and-vortex");
  // Generated edge highlights must never make a fully transparent source opaque.
  await evaluate(`(()=>{
  const context=byId('stage').getContext('webgl');context.activeTexture(context.TEXTURE0);
  window.alphaFixture={context,original:context.getParameter(context.TEXTURE_BINDING_2D),texture:context.createTexture()};
  context.bindTexture(context.TEXTURE_2D,alphaFixture.texture);
  context.texImage2D(context.TEXTURE_2D,0,context.RGBA,600,380,0,context.RGBA,context.UNSIGNED_BYTE,new Uint8Array(600*380*4));
  for(const key of [context.TEXTURE_MIN_FILTER,context.TEXTURE_MAG_FILTER])context.texParameteri(context.TEXTURE_2D,key,context.LINEAR);
  for(const key of [context.TEXTURE_WRAP_S,context.TEXTURE_WRAP_T])context.texParameteri(context.TEXTURE_2D,key,context.CLAMP_TO_EDGE);
})()`);
  for (const preset of [
    "ember-erosion",
    "frost-vanish",
    "pixel-wipe",
    "pixelate",
    "dust-drift",
    "ghost-wisps",
    "ink-current",
    "shockwave",
    "ripple-collapse",
    "wave-fold",
    "vortex-fold",
    "soft-swirl",
    "hexagon-burst",
    "hive-collapse",
    "signal-glitch",
    "chromatic-glitch",
    "ink-spread",
    "ink-bloom",
  ]) {
    await evaluate(
      `byId('preset').value=${JSON.stringify(preset)};byId('preset').dispatchEvent(new Event('change'))`,
    );
    await setProgress(0.45);
    assert.equal((await sample()).occupied, 0, preset + " preserves transparent source pixels");
  }
  await evaluate(
    "alphaFixture.context.bindTexture(alphaFixture.context.TEXTURE_2D,alphaFixture.original);alphaFixture.context.deleteTexture(alphaFixture.texture);delete window.alphaFixture",
  );
  if (options["save-test"]) {
    for (const [family, preset] of Object.entries({
      fragments: "bubble-burst",
      slices: "hinged-fan",
      elastic: "corner-spring",
      dissolve: "ember-erosion",
      iris: "diamond-turn",
      pixels: "dust-drift",
      wisps: "ghost-wisps",
      distortion: "shockwave",
      hexagons: "hexagon-burst",
    })) {
      await evaluate(
        `byId('preset').value=${JSON.stringify(preset)};byId('preset').dispatchEvent(new Event('change'));byId('name').value=${JSON.stringify("Browser " + family)};byId('save').click()`,
      );
      for (let i = 0; i < 100; i++) {
        if (await evaluate("!byId('save').disabled")) break;
        await sleep(100);
      }
      assert.equal(await evaluate("byId('save').disabled"), false, "save completed");
      assert.equal(await evaluate("byId('error').textContent"), "");
      assert.match(await evaluate("byId('status').textContent"), /^Saved NiriFX/);
    }
  }
  finishStage("transparency-and-family-saves");
  writeFileSync("artifacts/browser-checks.json", JSON.stringify(results, null, 2) + "\n");
  console.log(
    `PASS: ${Object.keys(expected).length} WebGL-rendered presets, exact endpoints, motion, shader parity, extreme controls, three resize styles, texture transitions, intact move/swap endpoints, valid/invalid JSON imports exact imported values, piece shapes, hinges, elastic transforms, spatial releases, visible/reproducible variation, capabilities and current schema validation` +
      (options["save-test"] ? ", and save to isolated registry." : "."),
  );
}
