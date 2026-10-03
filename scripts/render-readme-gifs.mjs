// Deterministic recordings of Studio's real shaders and its labelled concepts.
// Node 22+, Chromium and FFmpeg. No desktop capture or live preset changes.
import { spawn, execFileSync } from "node:child_process";
import {
  mkdtempSync,
  readFileSync,
  existsSync,
  mkdirSync,
  writeFileSync,
  rmSync,
  statSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";
import assert from "node:assert/strict";

const root = resolve(fileURLToPath(new URL("..", import.meta.url)));
process.chdir(root);
const args = process.argv.slice(2);
assert(
  args.every((arg) => ["--showcase-only", "--slices-only", "--new-only"].includes(arg)),
  "Supported options: --showcase-only, --slices-only or --new-only",
);
mkdirSync(join(root, "artifacts"), { recursive: true });
const scratch = mkdtempSync(join(root, "artifacts/readme-gifs-"));
const preview = join(scratch, "preview.html");
execFileSync("python3", ["-m", "niri_fx", "preview", "--output", preview]);
const profile = mkdtempSync(join(tmpdir(), "fragments-gifs-"));
const browser = spawn(
  "chromium",
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
  { stdio: "ignore" },
);
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
let ws;
try {
  for (let i = 0; i < 100 && !existsSync(join(profile, "DevToolsActivePort")); i++)
    await sleep(100);
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
    const message = JSON.parse(event.data),
      p = pending.get(message.id);
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
    width: 720,
    height: 616,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await rpc("Page.navigate", { url: pathToFileURL(preview).href });
  for (let i = 0; i < 100; i++) {
    if (await evaluate("document.documentElement.dataset.shaderStatus")) break;
    await sleep(100);
  }
  assert.equal(await evaluate("document.documentElement.dataset.shaderStatus"), "ready");
  // Capture-only layout: keep the actual canvas and synthetic window textures.
  await evaluate(`(()=>{
  const style=document.createElement('style');style.textContent=
   'html,body{width:720px;height:616px;margin:0;padding:0;overflow:hidden;background:#10151e}header,body>p,aside,.tabs,.controls,#concept-note,#caption,#status,main>small,#error{display:none!important}.layout{display:block;margin:0 14px}canvas{width:690px;height:524px;max-height:none;min-height:0;border-radius:12px}canvas[hidden]{display:none}#gif-heading{height:53px;padding:18px 22px 0;box-sizing:border-box;font-size:18px;font-weight:600;color:#dfedf5}#gif-note{padding:10px 22px;font-size:12px;color:#93b5c5;display:block!important}';
  document.head.append(style);
  const heading=document.createElement('div');heading.id='gif-heading';document.body.prepend(heading);
  const note=document.createElement('div');note.id='gif-note';document.body.append(note);
 })()`);
  const presets = JSON.parse(
    execFileSync(
      "python3",
      [
        "-c",
        "import json;from niri_fx.effects import describe_presets;print(json.dumps(describe_presets()))",
      ],
      { encoding: "utf8" },
    ),
  );
  const out = join(root, "docs/gifs");
  mkdirSync(out, { recursive: true });
  const originalSpecs = [
    {
      name: "opening",
      preset: "explosion",
      mode: "effect",
      title: "OPEN · Reconstruction",
      direction: "open",
    },
    {
      name: "closing",
      preset: "explosion",
      mode: "effect",
      title: "CLOSE · Explosion",
      direction: "close",
    },
    {
      name: "resize",
      preset: "balanced",
      mode: "resize",
      title: "RESIZE · Opt-in fragments",
      direction: "round",
    },
    {
      name: "move-concept",
      preset: "balanced",
      mode: "move",
      title: "MOVE · Studio design concept",
      direction: "round",
    },
    {
      name: "swap-concept",
      preset: "balanced",
      mode: "swap",
      title: "SWAP · Studio design concept",
      direction: "round",
    },
    ...Object.keys(presets).map((preset) => ({
      name: "preset-" + preset,
      preset,
      mode: "effect",
      title: preset.replaceAll("-", " ").toUpperCase(),
      direction: "round",
      small: true,
    })),
  ];
  const showcases = JSON.parse(readFileSync(join(out, "showcases.json"), "utf8")).clips;
  const additions = new Set([
    "slide-apart",
    "split-curtain",
    "ribbon-wave",
    "shuffled-slats",
    "venetian-sweep",
    "tidal-fragments",
    "mosaic-burst",
    "chaotic-confetti",
    "crosswind",
    "orbital-ribbons",
    "spring-wobble",
    "rubber-band",
    "jelly",
  ]);
  const specs = args.includes("--new-only")
    ? [
        ...originalSpecs.filter((spec) => additions.has(spec.preset)),
        ...showcases.filter((spec) => spec.name === "compare-slice-count" || spec.new),
      ]
    : args.includes("--slices-only")
      ? [
          ...originalSpecs.filter((spec) => presets[spec.preset]?.family === "slices"),
          ...showcases.filter((spec) => spec.name.startsWith("compare-slice")),
        ]
      : args.includes("--showcase-only")
        ? showcases
        : [...originalSpecs, ...showcases];
  const previous = existsSync(join(out, "manifest.json"))
    ? JSON.parse(readFileSync(join(out, "manifest.json"), "utf8")).clips
    : [];
  let manifest = previous;
  for (const spec of specs) {
    const panels = spec.panels || [{ label: spec.title, preset: spec.preset }];
    const comparison = panels.length > 1,
      recorded = [];
    let count;
    for (const [index, panel] of panels.entries()) {
      const directory = join(scratch, spec.name + "-" + index);
      mkdirSync(directory);
      let effect = panel.source
        ? JSON.parse(readFileSync(join(root, panel.source), "utf8")).effect
        : { ...presets[panel.preset], ...panel.overrides };
      // Python validation and shader parity keep the examples faithful to CLI exports.
      const generated = JSON.parse(
        execFileSync(
          "python3",
          [
            "-c",
            'import json,sys;from dataclasses import asdict;from niri_fx.effects import Effect,shader;p=Effect(**json.load(sys.stdin));print(json.dumps({"effect":asdict(p),"sources":[shader(p,True),shader(p,False)]}))',
          ],
          { input: JSON.stringify(effect), encoding: "utf8" },
        ),
      );
      effect = generated.effect;
      const sources = generated.sources;
      const concept = ["move", "swap"].includes(spec.mode);
      // Show actual preset durations, sampled at 20 fps; a hold separates endpoints.
      const forward = spec.mode === "resize" ? effect.resize_ms : concept ? 1100 : effect.close_ms;
      const backward = spec.mode === "resize" ? effect.resize_ms : concept ? 1100 : effect.open_ms;
      const pause = 450,
        fps = 20;
      const duration =
        spec.direction === "round"
          ? pause * 3 + forward + backward
          : pause * 2 + (spec.direction === "open" ? backward : forward);
      const note = concept
        ? "Synthetic windows · design preview, not installed movement"
        : spec.mode === "resize"
          ? "Real resize shader · disabled by default"
          : comparison
            ? "Real shader · same timing, texture and seed"
            : panel.source
              ? "Custom settings · real shader · resize off"
              : "Real open/close shader · " + panel.preset + " preset · synthetic window";
      await evaluate(`byId('preset').value=${JSON.stringify(panel.preset || "balanced")};byId('preset').dispatchEvent(new Event('change'));
    parameters=normalizePreset({schema:3,name:'Recording',effect:${JSON.stringify(effect)}}).effect;populate();document.querySelector('[data-mode=${spec.mode}]').click();refresh();
    byId('gif-heading').textContent=${JSON.stringify(panel.label)};byId('gif-note').textContent=${JSON.stringify(note)};
    byId('gif-heading').style.fontSize=${JSON.stringify(comparison ? "28px" : spec.panels ? "24px" : "18px")};byId('gif-note').style.fontSize=${JSON.stringify(spec.panels ? "18px" : "12px")};`);
      assert.equal(await evaluate("document.documentElement.dataset.shaderStatus"), "ready");
      assert.deepEqual(await evaluate("parameters"), effect);
      assert.deepEqual(
        await evaluate("[shaderFor(parameters,true),shaderFor(parameters,false)]"),
        sources,
      );
      const panelFrames = Math.ceil((duration * fps) / 1000);
      if (index) assert.equal(panelFrames, count, "Comparison panels must have matching timing");
      count = panelFrames;
      for (let frame = 0; frame < count; frame++) {
        const t = (frame * 1000) / fps;
        let p;
        if (spec.direction === "open") p = 1 - Math.max(0, Math.min(1, (t - pause) / backward));
        else if (spec.direction === "close") p = Math.max(0, Math.min(1, (t - pause) / forward));
        else if (t < pause + forward) p = Math.max(0, Math.min(1, (t - pause) / forward));
        else p = 1 - Math.max(0, Math.min(1, (t - 2 * pause - forward) / backward));
        await evaluate(
          `byId('progress').value=${Math.round(p * 1000)};byId('progress').dispatchEvent(new Event('input'));`,
        );
        const capture = await rpc("Page.captureScreenshot", {
          format: "png",
          captureBeyondViewport: false,
        });
        writeFileSync(
          join(directory, String(frame).padStart(4, "0") + ".png"),
          Buffer.from(capture.data, "base64"),
        );
      }
      recorded.push({
        directory,
        effect,
        ...(panel.source ? { source: panel.source } : { preset: panel.preset }),
        label: panel.label,
      });
    }
    const fps = 20,
      target = join(out, spec.name + ".gif"),
      width = comparison || spec.small ? 360 : spec.panels ? 480 : 640;
    const inputs = recorded.flatMap((panel) => [
      "-framerate",
      String(fps),
      "-i",
      join(panel.directory, "%04d.png"),
    ]);
    const scale = recorded
      .map((_, i) => `[${i}:v]scale=${width}:-1:flags=lanczos[v${i}]`)
      .join(";");
    const stack = comparison
      ? recorded.map((_, i) => `[v${i}]`).join("") + `hstack=inputs=${panels.length}[stack];[stack]`
      : "[v0]";
    execFileSync("ffmpeg", [
      "-v",
      "error",
      "-y",
      ...inputs,
      "-filter_complex",
      `${scale};${stack}split[a][b];[a]palettegen=max_colors=192:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle`,
      "-loop",
      "0",
      target,
    ]);
    assert(statSync(target).size > 1000);
    manifest = manifest.filter((clip) => clip.file !== "docs/gifs/" + spec.name + ".gif");
    manifest.push({
      file: "docs/gifs/" + spec.name + ".gif",
      ...(spec.preset ? { preset: spec.preset, effect: recorded[0].effect } : {}),
      mode: spec.mode,
      frames: count,
      fps,
      bytes: statSync(target).size,
      ...(spec.panels
        ? {
            panels: recorded.map((panel) =>
              Object.fromEntries(Object.entries(panel).filter(([key]) => key !== "directory")),
            ),
          }
        : {}),
    });
    writeFileSync(
      join(out, "manifest.json"),
      JSON.stringify(
        {
          renderer: "Studio WebGL shaders / labelled Canvas movement concepts",
          fps: 20,
          clips: manifest,
        },
        null,
        2,
      ) + "\n",
    );
    console.log(
      `Rendered ${spec.name}: ${count} frames, ${Math.round(statSync(target).size / 1024)} KiB`,
    );
  }
  console.log("Frame sources: " + scratch);
} finally {
  ws?.close();
  if (browser.exitCode === null) {
    const exited = new Promise((resolve) => browser.once("exit", resolve));
    browser.kill("SIGTERM");
    await exited;
  }
  // Chrome helpers may flush their profile briefly after the browser exits.
  rmSync(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
}
