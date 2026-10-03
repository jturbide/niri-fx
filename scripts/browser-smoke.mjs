// Run against an offline preview or an isolated studio --registry test path.
// Requires Node 22+ and Chromium. Saves review images in the ignored artifacts/.
import { spawn, execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, existsSync, mkdirSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { createHash } from "node:crypto";
import assert from "node:assert/strict";

const url = process.argv[2];
if (!url) throw new Error("Usage: node scripts/browser-smoke.mjs PREVIEW_URL [--save-test]");
const executable =
  process.env.CHROME_BIN ||
  ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable"].find(
    (name) => spawnSync(name, ["--version"], { stdio: "ignore" }).status === 0,
  );
if (!executable) throw new Error("Install Chromium/Chrome or set CHROME_BIN");
const profile = mkdtempSync(join(tmpdir(), "niri-fx-browser-"));
const browser = spawn(
  executable,
  [
    "--headless=new",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
    "--remote-debugging-port=0",
    "--user-data-dir=" + profile,
    "about:blank",
  ],
  { stdio: ["ignore", "ignore", "pipe"] },
);
let diagnostics = "",
  launchError,
  closed = false;
browser.stderr.on("data", (chunk) => {
  diagnostics = (diagnostics + chunk.toString()).slice(-8192);
});
browser.on("error", (error) => {
  launchError = error;
});
const browserClosed = new Promise((resolve) =>
  browser.once("close", () => {
    closed = true;
    resolve();
  }),
);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let ws;
try {
  const deadline = Date.now() + 30000;
  while (!existsSync(join(profile, "DevToolsActivePort"))) {
    if (launchError || closed || Date.now() >= deadline)
      throw new Error(
        `Chrome did not start (${launchError?.message ?? (closed ? "exit " + browser.exitCode : "30s timeout")}).\n${diagnostics}`,
      );
    await sleep(100);
  }
  const port = readFileSync(join(profile, "DevToolsActivePort"), "utf8").split("\n")[0];
  const tabs = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  ws = new WebSocket(tabs.find((tab) => tab.type === "page").webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
  });
  let sequence = 0;
  const pending = new Map();
  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    const p = pending.get(message.id);
    if (p) {
      pending.delete(message.id);
      message.error
        ? p.reject(new Error(JSON.stringify(message.error)))
        : p.resolve(message.result);
    }
  };
  const rpc = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = ++sequence;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
  const evaluate = async (expression) => {
    const r = await rpc("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails));
    return r.result.value;
  };
  await rpc("Emulation.setDeviceMetricsOverride", {
    width: 1380,
    height: 1120,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await rpc("Page.navigate", { url });
  for (let i = 0; i < 100; i++) {
    if (await evaluate("document.documentElement.dataset.shaderStatus")) break;
    await sleep(100);
  }
  assert.equal(
    await evaluate("document.documentElement.dataset.shaderStatus"),
    "ready",
    await evaluate("byId('error').textContent"),
  );
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
  const sample = () =>
    evaluate(
      `(()=>{const canvas=byId('stage'),gl=canvas.getContext('webgl');const pixels=new Uint8Array(canvas.width*canvas.height*4);gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);let alpha=0,x=0,y=0,occupied=0;for(let i=0;i<pixels.length;i+=4){const a=pixels[i+3];if(a){const px=(i/4)%canvas.width,py=canvas.height-1-Math.floor(i/4/canvas.width);alpha+=a;x+=px*a;y+=py*a;occupied++;}}return {occupied,alpha,cx:alpha?x/alpha:0,cy:alpha?y/alpha:0,error:gl.getError()};})()`,
    );
  const setProgress = async (value) => {
    await evaluate(
      `byId('progress').value=${Math.round(value * 1000)};byId('progress').dispatchEvent(new Event('input'))`,
    );
  };
  const results = {};
  mkdirSync("artifacts", { recursive: true });
  for (const name of Object.keys(expected)) {
    await evaluate(
      `byId('preset').value=${JSON.stringify(name)};byId('preset').dispatchEvent(new Event('change'))`,
    );
    assert.equal(await evaluate("document.documentElement.dataset.shaderStatus"), "ready", name);
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
  assert.equal(await evaluate("document.documentElement.dataset.shaderStatus"), "ready");
  // Exercise the real resize shader, two texture inputs and stable endpoints.
  const resizeExpected = JSON.parse(
    execFileSync(
      "python3",
      [
        "-c",
        'import hashlib,json;from niri_fx.effects import PRESETS,resize_shader;print(json.dumps({k:hashlib.sha256(resize_shader(v).encode()).hexdigest() for k,v in PRESETS.items() if v.family=="fragments"}))',
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
    assert(middle.occupied > 0 && middle.occupied < 700 * 410, name + " resize breaks into pieces");
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
  // Import through the real file input; failed imports leave the editor untouched.
  const importFile = async (text) =>
    evaluate(
      `(async()=>{const transfer=new DataTransfer();transfer.items.add(new File([${JSON.stringify(text)}],'preset.json',{type:'application/json'}));byId('import-file').files=transfer.files;await byId('import-file').onchange();return {effect:effectDocument(),error:byId('error').textContent,status:byId('status').textContent};})()`,
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
  assert.equal(await evaluate("mode"), "effect", "import exits an unsupported resize preview");
  assert.equal(await evaluate("byId('fragment-controls').hidden"), true);
  assert.equal(await evaluate("byId('slice-controls').hidden"), false);
  assert(
    await evaluate(
      "[...document.querySelectorAll('[data-mode]')].filter(b=>b.dataset.mode!=='effect').every(b=>b.disabled)",
    ),
    "unsupported modes disabled",
  );
  const sliceSaved = await evaluate("effectDocument()");
  for (const effect of [
    { family: "slices", resize: true },
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
        "import json,sys;from niri_fx.integration import custom_document;from niri_fx.effects import effect_document;doc=json.load(sys.stdin);name,_,effect=custom_document(doc);print(json.dumps(effect_document(name,effect)))",
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
      { elastic_twist: 80, elastic_stretch: 1, elastic_ripple: 4, elastic_anchor: "bottom-right" },
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
        "import json,sys;from niri_fx.integration import custom_document;from niri_fx.effects import animation_types;print(json.dumps(animation_types(custom_document(json.load(sys.stdin))[2])))",
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
    "byId('action-enabled').checked=true;byId('action-enabled').dispatchEvent(new Event('change'))",
  );
  assert(await evaluate("kdlDocument().includes('window-resize')"));
  assert.equal(await evaluate("effectDocument().actions.open.family"), "elastic");
  const resizeProfile = await evaluate("effectDocument()");
  const resizeImport = await importFile(JSON.stringify(resizeProfile));
  assert.equal(resizeImport.error, "");
  assert.match(resizeImport.status, /Resize is enabled in this document/);
  assert.deepEqual(resizeImport.effect, resizeProfile);
  await evaluate("byId('action').value='resize';byId('action').dispatchEvent(new Event('change'))");
  await evaluate(
    "byId('action-enabled').checked=false;byId('action-enabled').dispatchEvent(new Event('change'))",
  );
  assert(!(await evaluate("kdlDocument().includes('window-resize')")));
  if (process.argv.includes("--save-test")) {
    await evaluate("byId('name').value='Browser Profile';byId('save').click()");
    for (let i = 0; i < 100 && (await evaluate("byId('save').disabled")); i++) await sleep(100);
    assert.equal(await evaluate("byId('error').textContent"), "");
    assert.match(await evaluate("byId('status').textContent"), /^Saved NiriFX/);
  }
  await importFile(JSON.stringify({ schema: 3, name: "Reveal Test", effect: { family: "iris" } }));
  for (const [preset, changes] of Object.entries({
    "ember-erosion": {
      dissolve_scale: 12,
      dissolve_softness: 0.2,
      dissolve_direction: "left",
      dissolve_bias: 0.1,
      edge_width: 0.3,
      edge_hue: 220,
    },
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
      const before = await pixelHash();
      await evaluate(
        `byId(${JSON.stringify(key)}).value=${JSON.stringify(value)};byId(${JSON.stringify(key)}).dispatchEvent(new Event('input'))`,
      );
      assert.notEqual(await pixelHash(), before, key + " independently changes pixels");
      assert.equal((await sample()).error, 0);
    }
  }
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
    "byId('preset').value='iris-bloom';byId('preset').dispatchEvent(new Event('change'));byId('favorite').click();byId('search').value='bloom';byId('search').dispatchEvent(new Event('input'))",
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
      "import sys,json;from niri_fx.integration import custom_document;from niri_fx.effects import shader;print(shader(custom_document(json.load(sys.stdin))[2],False),end='')",
    ],
    { input: JSON.stringify(roundingDoc), encoding: "utf8" },
  );
  assert.equal(await evaluate("shaderFor(parameters,false)"), rounded);
  const unsupported = await evaluate("window.niriFxBenchmark({samples:10})");
  assert.equal(unsupported.status, "unsupported", "software WebGL must not claim GPU performance");
  if (process.argv.includes("--save-test")) {
    for (const [family, preset] of Object.entries({
      fragments: "bubble-burst",
      slices: "hinged-fan",
      elastic: "corner-spring",
      dissolve: "ember-erosion",
      iris: "diamond-turn",
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
  writeFileSync("artifacts/browser-checks.json", JSON.stringify(results, null, 2) + "\n");
  console.log(
    `PASS: ${Object.keys(expected).length} WebGL-rendered presets, exact endpoints, motion, shader parity, extreme controls, three resize styles, texture transitions, intact move/swap endpoints, valid/invalid JSON imports exact imported values, piece shapes, hinges, elastic transforms, spatial releases, visible/reproducible variation, capabilities and current schema validation` +
      (process.argv.includes("--save-test") ? ", and save to isolated registry." : "."),
  );
} finally {
  ws?.close();
  if (!closed) {
    browser.kill("SIGTERM");
    await browserClosed;
  }
  // Chrome helpers may flush their profile briefly after the browser exits.
  rmSync(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
}
