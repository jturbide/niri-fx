// Record complete combos through Studio's real button and deterministic clock.
// Only synthetic textures are captured; no desktop or installed effects change.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { launchBrowser, projectRoot } from "./lib/browser.mjs";

process.chdir(projectRoot);
const defaults = [
  "fragment-flow",
  "soft-landing",
  "ribbon-current",
  "playful-motion",
  "geometric-flow",
];
const args = process.argv.slice(2);
assert(
  args.length <= 1 && (!args[0] || args[0].startsWith("--only=")),
  "Use --only=profile-id,profile-id",
);
const selected = args[0] ? args[0].slice("--only=".length).split(",") : defaults;
assert(selected.length && new Set(selected).size === selected.length, "Select distinct profiles");
const specifications = JSON.parse(readFileSync("docs/gifs/showcases.json", "utf8")).clips;
const clips = selected.map((id) => {
  const spec = specifications.find((spec) => spec.name === "profile-" + id);
  assert(spec?.panels?.length === 1 && spec.panels[0].source, "Unknown one-panel profile: " + id);
  return { id, spec, source: spec.panels[0].source };
});
mkdirSync("artifacts", { recursive: true });
const scratch = mkdtempSync(join(projectRoot, "artifacts/combo-showcases-"));
const page = join(scratch, "preview.html");
execFileSync("python3", ["-m", "niri_fx", "preview", "--output", page]);
const browser = await launchBrowser();
const fps = 20;
try {
  const { evaluate, rpc } = browser;
  await browser.navigate(pathToFileURL(page).href, { width: 720, height: 616 });
  await evaluate(`(() => {
    const style=document.createElement('style');
    style.textContent='html,body{width:720px;height:616px;max-width:none;margin:0;padding:0;overflow:hidden;background:#10151e}header,body>p,aside,.tabs,.controls,#library-actions,#transfer-options,.selection-summary,.selection-bar,.preview-heading,.workspace-tools,#apply-review,.preview-preferences,#concept-note,#movement-preview-controls,#caption,#status,main>small,.motion-preference,#error,#combo-preview-status{display:none!important}.layout{display:block;margin:0 14px}html[data-workspace] canvas{width:690px;height:524px!important;max-height:none!important;min-height:0!important;border-radius:12px}canvas[hidden]{display:none}#gif-heading{height:53px;padding:18px 22px 0;box-sizing:border-box;font-size:18px;font-weight:600;color:#dfedf5}#gif-note{padding:10px 22px;font-size:12px;color:#93b5c5;display:block!important}';
    document.head.append(style);
    const heading=document.createElement('div');heading.id='gif-heading';document.body.prepend(heading);
    const note=document.createElement('div');note.id='gif-note';document.body.append(note);
    byId('reduced-motion').checked=false;seed=0.43;
  })()`);
  assert(
    await evaluate(`(() => {
      const canvas=byId('stage').getBoundingClientRect();
      return canvas.top >= 53 && canvas.top <= 55 && canvas.height >= 524 && canvas.bottom < 590;
    })()`),
    "Capture layout must show the complete preview canvas without Studio controls",
  );
  for (const { id, spec, source } of clips) {
    const directory = join(scratch, spec.name);
    mkdirSync(directory);
    const input = JSON.parse(readFileSync(source, "utf8"));
    const expected = JSON.parse(
      execFileSync(
        "python3",
        [
          "-c",
          `
import json,sys
from pathlib import Path
from niri_fx.documents import effect_document,parse_document
from niri_fx.effects import shader,resize_shader,movement_shader,renderer_name,TEMPLATE_FILES,RESIZE_TEMPLATES
name,_,profile=parse_document(json.load(sys.stdin))
sources=set()
shaders={}
for action in ('open','close','resize','movement'):
    effect=getattr(profile,action)
    if effect is None:
        continue
    renderer=renderer_name(effect)
    if action=='resize':
        renderer='resize-shaped' if effect.family=='fragments' and effect.shaped_resize else RESIZE_TEMPLATES[effect.family]
    filename=TEMPLATE_FILES[renderer]
    path=Path('niri_fx/shaders') / (filename+'.glsl')
    sources.add(str(path))
    text=path.read_text()
    if '@ACTION_ENTRY@' in text:
        entry=('movement-elastic-entry' if effect.family=='elastic' else 'movement-entry') if action=='movement' else filename+'-entry'
        path=path.with_name(entry+'.glsl')
        sources.add(str(path))
        text=text.replace('@ACTION_ENTRY@',path.read_text())
    for token,snippet in {'NOISE':'noise','EDGE_COLOR':'edge-color','RESIZE_COMMON':'resize-common','FRAGMENT_SHAPES':'fragment-shapes'}.items():
        if '@'+token+'@' in text:
            path=Path('niri_fx/shaders') / (snippet+'.glsl')
            sources.add(str(path))
            text=text.replace('@'+token+'@',path.read_text())
    shaders[action]=resize_shader(effect) if action=='resize' else movement_shader(effect) if action=='movement' else shader(effect,action=='open')
print(json.dumps({'document':effect_document(name,profile),'shaders':shaders,'sources':sorted(sources)}))
`,
        ],
        { input: JSON.stringify(input), encoding: "utf8", maxBuffer: 4 * 1024 * 1024 },
      ),
    );
    await evaluate(
      `document.querySelector('[data-library-action=combo]').click();document.querySelector('[data-style=${id}]').click();byId('gif-heading').textContent=${JSON.stringify(input.name)};seed=0.43;`,
    );
    assert.deepEqual(await evaluate("effectDocument()"), expected.document);
    for (const [action, shader] of Object.entries(expected.shaders))
      assert.equal(
        await evaluate(
          `shaderFor(effectDocument().actions[${JSON.stringify(action)}],${action === "open"},${action === "resize"},${action === "movement"})`,
        ),
        shader,
        id + " " + action + " shader parity",
      );
    const before = await evaluate(
      "({document:effectDocument(),history:editHistory,historyIndex,parameters,editingAction,mode,seed})",
    );
    const plan = await evaluate(`(() => {
      byId('preview-combo').click();
      if(!window.niriFxComboPreview?.active)throw new Error('Combo button did not start playback');
      window.niriFxComboPreview.seek(0);
      return window.niriFxComboPreview.currentPlan;
    })()`);
    assert.deepEqual(plan.document, expected.document);
    assert.equal(plan.seed, 0.43);
    assert.equal(plan.reducedMotion, false);
    const count = Math.ceil((plan.totalMs * fps) / 1000) + 1 + fps / 2;
    let final;
    for (let frame = 0; frame < count; frame++) {
      const elapsedMs = Math.min(plan.totalMs, (frame * 1000) / fps);
      if (!final) {
        final = await evaluate(`(() => {
          const state=window.niriFxComboPreview.seek(${elapsedMs});
          byId('gif-note').textContent=state.label+' · synthetic window';
          if(document.documentElement.dataset.shaderStatus!=='ready')throw new Error(byId('error').textContent||'Shader not ready');
          return state.complete?state:null;
        })()`);
      }
      const capture = await rpc("Page.captureScreenshot", {
        format: "png",
        captureBeyondViewport: false,
      });
      writeFileSync(
        join(directory, String(frame).padStart(4, "0") + ".png"),
        Buffer.from(capture.data, "base64"),
      );
    }
    assert.equal(final?.action, "close");
    assert.equal(final?.progress, 1);
    assert.equal(await evaluate("window.niriFxComboPreview.active"), false);
    assert.equal(
      await evaluate(`(() => {
        const canvas=byId('stage'),gl=canvas.getContext('webgl');
        const pixels=new Uint8Array(canvas.width*canvas.height*4);
        gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
        for(let index=3;index<pixels.length;index+=4)if(pixels[index]!==0)return false;
        return true;
      })()`),
      true,
      id + " complete close leaves a transparent WebGL endpoint",
    );
    assert.deepEqual(
      await evaluate(
        "({document:effectDocument(),history:editHistory,historyIndex,parameters,editingAction,mode,seed})",
      ),
      before,
    );
    // Keep an uncompressed endpoint and opening hold for independent review.
    writeFileSync(join(directory, "timeline.json"), JSON.stringify(plan, null, 2) + "\n");
    const target = "docs/gifs/" + spec.name + ".gif";
    execFileSync("ffmpeg", [
      "-v",
      "error",
      "-y",
      "-framerate",
      String(fps),
      "-i",
      join(directory, "%04d.png"),
      "-filter_complex",
      "scale=480:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=192:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
      "-loop",
      "0",
      target,
    ]);
    assert(statSync(target).size > 1000);
    const manifestPath = "docs/gifs/manifest.json",
      manifest = JSON.parse(readFileSync(manifestPath));
    const entry = {
      file: target,
      mode: "effect",
      frames: count,
      fps,
      bytes: statSync(target).size,
      backend: "actual Studio combo playback / synthetic WebGL texture",
      panels: [
        {
          effect: expected.document.actions.close,
          opening_effect: expected.document.actions.open,
          source,
          label: spec.panels[0].label,
        },
      ],
      sources: Object.fromEntries(
        [
          source,
          "niri_fx/library.js",
          "niri_fx/effect-core.js",
          "niri_fx/pointer-preview.js",
          "niri_fx/preview.py",
          "niri_fx/combo-preview.js",
          "niri_fx/studio.js",
          "niri_fx/preview.html",
          "niri_fx/studio.css",
          "scripts/record-combo-showcases.mjs",
          ...expected.sources,
        ].map((path) => [path, createHash("sha256").update(readFileSync(path)).digest("hex")]),
      ),
      combo: {
        document: expected.document,
        seed: plan.seed,
        duration_ms: plan.totalMs,
        stages: plan.stages.map(({ action, phase, direction, startMs, durationMs }) => ({
          action,
          phase,
          direction,
          start_ms: startMs,
          duration_ms: durationMs,
        })),
      },
      checks: [
        "actual Preview combo button",
        "complete opening and closing cycle",
        "action-specific shader parity and timing",
        "stable seed",
        "only explicitly enabled optional actions",
        "transparent final endpoint",
        "document and Undo history unchanged",
      ],
    };
    const index = manifest.clips.findIndex((clip) => clip.file === target);
    assert(index >= 0, "Existing profile manifest row required");
    manifest.clips[index] = entry;
    writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
    console.log(
      `Rendered ${spec.name}: ${count} frames at ${fps} fps, ${statSync(target).size} bytes`,
    );
  }
  console.log("PASS: complete combo cycles. Evidence: " + scratch);
} finally {
  await browser.close();
}
