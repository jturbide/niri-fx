// Deterministic recordings of Studio's real shaders and its labelled concepts.
// Node 22+, Chromium and FFmpeg. No desktop capture or live preset changes.
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, existsSync, mkdirSync, writeFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import assert from "node:assert/strict";
import { launchBrowser, projectRoot } from "./lib/browser.mjs";

const root = projectRoot;
process.chdir(root);
const args = process.argv.slice(2);
assert(
  args.length <= 1 &&
    args.every(
      (arg) =>
        ["--showcase-only", "--slices-only", "--new-only"].includes(arg) ||
        arg.startsWith("--only="),
    ),
  "Use one of: --showcase-only, --slices-only, --new-only, --only=clip-name,clip-name",
);
mkdirSync(join(root, "artifacts"), { recursive: true });
const scratch = mkdtempSync(join(root, "artifacts/readme-gifs-"));
const preview = join(scratch, "preview.html");
execFileSync("python3", ["-m", "niri_fx", "preview", "--output", preview]);
const browser = await launchBrowser();
try {
  const { rpc, evaluate } = browser;
  await browser.navigate(pathToFileURL(preview).href, { width: 720, height: 616 });
  // Capture-only layout: keep the actual canvas and synthetic window textures.
  await evaluate(`(()=>{
  const style=document.createElement('style');style.textContent=
   'html,body{width:720px;height:616px;margin:0;padding:0;overflow:hidden;background:#10151e}header,body>p,aside,.tabs,.controls,#concept-note,#movement-preview-controls,#caption,#status,main>small,.motion-preference,#error{display:none!important}.layout{display:block;margin:0 14px}canvas{width:690px;height:524px;max-height:none;min-height:0;border-radius:12px}canvas[hidden]{display:none}#gif-heading{height:53px;padding:18px 22px 0;box-sizing:border-box;font-size:18px;font-weight:600;color:#dfedf5}#gif-note{padding:10px 22px;font-size:12px;color:#93b5c5;display:block!important}';
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
  let specs = args.includes("--new-only")
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
  if (args[0]?.startsWith("--only=")) {
    const names = new Set(args[0].slice("--only=".length).split(","));
    const all = [...originalSpecs, ...showcases];
    assert(
      [...names].every((name) => all.some((spec) => spec.name === name)),
      "Unknown clip in --only selection",
    );
    specs = all.filter((spec) => names.has(spec.name));
  }
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
      const sourceDoc = panel.source
        ? JSON.parse(readFileSync(join(root, panel.source), "utf8"))
        : null;
      let openingEffect =
        sourceDoc?.kind === "profile" && spec.mode === "effect" ? sourceDoc.actions.open : null;
      let effect = sourceDoc
        ? sourceDoc.effect ||
          sourceDoc.actions[["resize", "movement"].includes(spec.mode) ? spec.mode : "close"]
        : { ...presets[panel.preset], ...panel.overrides };
      // Python validation and shader parity keep the examples faithful to CLI exports.
      const generated = JSON.parse(
        execFileSync(
          "python3",
          [
            "-c",
            'import json,sys;from dataclasses import asdict;from niri_fx.effects import Effect,shader,resize_shader,movement_shader,FAMILIES;p=Effect(**json.load(sys.stdin));print(json.dumps({"effect":asdict(p),"sources":[shader(p,True),shader(p,False)],"resize":resize_shader(p) if FAMILIES[p.family]["resize"] else None,"movement":movement_shader(p) if FAMILIES[p.family]["movement"] else None}))',
          ],
          { input: JSON.stringify(effect), encoding: "utf8" },
        ),
      );
      effect = generated.effect;
      const sources = generated.sources;
      if (openingEffect) {
        // Older example documents can omit settings added since they were
        // written. Normalize opening just like closing before shader expansion.
        openingEffect = await evaluate(
          `normalizePreset({schema:3,name:"Recording",effect:${JSON.stringify(openingEffect)}}).effect`,
        );
        const openingShader = execFileSync(
          "python3",
          [
            "-c",
            "import json,sys;from niri_fx.effects import Effect,shader;print(shader(Effect(**json.load(sys.stdin)),True),end='')",
          ],
          { input: JSON.stringify(openingEffect), encoding: "utf8" },
        );
        assert.equal(
          await evaluate(`shaderFor(${JSON.stringify(openingEffect)}, true)`),
          openingShader,
        );
      }
      const concept = ["move", "swap"].includes(spec.mode);
      // Show actual preset durations, sampled at 20 fps; a hold separates endpoints.
      const forward =
        spec.mode === "resize"
          ? effect.resize_ms
          : spec.mode === "movement"
            ? effect.movement_ms
            : concept
              ? 1100
              : effect.close_ms;
      const backward =
        spec.mode === "resize"
          ? effect.resize_ms
          : spec.mode === "movement"
            ? effect.movement_ms
            : concept
              ? 1100
              : (openingEffect || effect).open_ms;
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
          : spec.mode === "movement"
            ? "Experimental movement shader · synthetic directional path"
            : comparison
              ? "Real shader · same timing, texture and seed"
              : panel.source
                ? "Custom settings · real shader · resize off"
                : "Real open/close shader · " + panel.preset + " preset · synthetic window";
      await evaluate(`byId('preset').value=${JSON.stringify(panel.preset || "balanced")};byId('preset').dispatchEvent(new Event('change'));
    byId('resize-direction').value='grow';byId('movement-direction').value='right';parameters=normalizePreset({schema:3,name:'Recording',effect:${JSON.stringify(effect)}}).effect;populate();document.querySelector('[data-mode=${spec.mode}]').click();refresh();
    byId('gif-heading').textContent=${JSON.stringify(panel.label)};byId('gif-note').textContent=${JSON.stringify(note)};
    byId('gif-heading').style.fontSize=${JSON.stringify(comparison ? "28px" : spec.panels ? "24px" : "18px")};byId('gif-note').style.fontSize=${JSON.stringify(spec.panels ? "18px" : "12px")};`);
      assert.equal(await evaluate("document.documentElement?.dataset.shaderStatus"), "ready");
      assert.deepEqual(await evaluate("parameters"), effect);
      assert.deepEqual(
        await evaluate("[shaderFor(parameters,true),shaderFor(parameters,false)]"),
        sources,
      );
      if (spec.mode === "resize")
        assert.equal(await evaluate("shaderFor(parameters,false,true)"), generated.resize);
      if (spec.mode === "movement")
        assert.equal(await evaluate("shaderFor(parameters,false,false,true)"), generated.movement);
      const panelFrames = Math.ceil((duration * fps) / 1000);
      if (index) assert.equal(panelFrames, count, "Comparison panels must have matching timing");
      count = panelFrames;
      let showingOpening = false;
      for (let frame = 0; frame < count; frame++) {
        const t = (frame * 1000) / fps;
        if (openingEffect && !showingOpening && t >= 2 * pause + forward) {
          showingOpening = true;
          await evaluate(`parameters=${JSON.stringify(openingEffect)};populate();refresh();`);
        }
        let p;
        if (spec.direction === "open") p = 1 - Math.max(0, Math.min(1, (t - pause) / backward));
        else if (spec.direction === "close") p = Math.max(0, Math.min(1, (t - pause) / forward));
        else if (t < pause + forward) p = Math.max(0, Math.min(1, (t - pause) / forward));
        else p = 1 - Math.max(0, Math.min(1, (t - 2 * pause - forward) / backward));
        if (spec.mode === "resize" && spec.direction === "round" && t >= 2 * pause + forward) {
          // A new resize has exchanged textures and matrices, and time starts at zero.
          p = Math.max(0, Math.min(1, (t - 2 * pause - forward) / backward));
          await evaluate("byId('resize-direction').value='shrink'");
        }
        if (spec.mode === "movement" && spec.direction === "round" && t >= 2 * pause + forward) {
          p = Math.max(0, Math.min(1, (t - 2 * pause - forward) / backward));
          await evaluate("byId('movement-direction').value='left'");
        }
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
        ...(openingEffect ? { opening_effect: openingEffect } : {}),
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
    const entry = {
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
    };
    // Re-recording an existing clip should not reorder unrelated manifest rows.
    const existing = manifest.findIndex((clip) => clip.file === entry.file);
    if (existing < 0) manifest.push(entry);
    else manifest[existing] = entry;
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
  await browser.close();
}
