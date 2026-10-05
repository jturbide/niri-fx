// Capture the same native-math drag trace that Studio plays in a combo.
// The window and input are synthetic; this is not a compositor recording.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { launchBrowser, projectRoot } from "./lib/browser.mjs";

process.chdir(projectRoot);
mkdirSync("artifacts", { recursive: true });
const scratch = mkdtempSync(join(projectRoot, "artifacts/pointer-preview-"));
const browser = await launchBrowser();
const fps = 25;
try {
  for (const id of ["gentle", "rubber-sheet", "release-settle"]) {
    const name = "pointer-preview-" + id,
      source = "examples/profiles/" + name + ".json",
      document = JSON.parse(readFileSync(source)),
      directory = join(scratch, name),
      page = join(directory, "preview.html");
    mkdirSync(directory);
    execFileSync("python3", ["-m", "niri_fx", "preview", "--custom", source, "--output", page]);
    await browser.navigate(pathToFileURL(page).href, { width: 720, height: 616 });
    const { evaluate, rpc } = browser;
    await evaluate(`(() => {
      const style=document.createElement('style');
      style.textContent='html,body{width:720px;height:616px;max-width:none;margin:0;padding:0;overflow:hidden;background:#10151e}header,body>p,aside,.tabs,.controls,#library-actions,#transfer-options,.selection-summary,#concept-note,#movement-preview-controls,#pointer-preview-tools,#caption,#status,main>small,.motion-preference,#error,#combo-preview-status{display:none!important}.layout{display:block;margin:0 14px}html[data-workspace] canvas{width:690px;height:524px;max-height:none;min-height:0;border-radius:12px}canvas[hidden]{display:none}#gif-heading{height:53px;padding:18px 22px 0;box-sizing:border-box;font-size:18px;font-weight:600;color:#dfedf5}#gif-note{padding:10px 22px;font-size:12px;color:#93b5c5;display:block!important}';
      document.head.append(style);
      const heading=document.createElement('div');heading.id='gif-heading';heading.textContent=${JSON.stringify(document.name)};document.body.prepend(heading);
      const note=document.createElement('div');note.id='gif-note';document.body.append(note);
      byId('reduced-motion').checked=false;seed=0.43;
    })()`);
    const before = await evaluate(
      "({document:effectDocument(),history:editHistory,historyIndex,editingAction,mode,seed})",
    );
    const plan = await evaluate(`(() => {
      byId('preview-combo').click();
      if(!window.niriFxComboPreview?.active)throw new Error('Combo button did not start playback');
      window.niriFxComboPreview.seek(0);
      return window.niriFxComboPreview.currentPlan;
    })()`);
    assert.deepEqual(
      plan.document,
      await browser.callFunction("function(doc) { return normalizePreset(doc); }", [document]),
    );
    assert.equal(plan.stages.filter((stage) => stage.action === "pointer").length, 1);
    const count = Math.ceil((plan.totalMs * fps) / 1000) + 1;
    let final;
    for (let frame = 0; frame < count; frame++) {
      final = await evaluate(`(() => {
        const state=window.niriFxComboPreview.seek(${Math.min(plan.totalMs, (frame * 1000) / fps)});
        byId('gif-note').textContent=state.action==='pointer'
          ? (state.phase==='drag'?'Dragging':'Settling')+' · native math, synthetic input'
          : state.label+' · synthetic window';
        if(document.documentElement.dataset.shaderStatus!=='ready')throw new Error(byId('error').textContent||'Shader not ready');
        return state;
      })()`);
      const capture = await rpc("Page.captureScreenshot", {
        format: "png",
        captureBeyondViewport: false,
      });
      writeFileSync(
        join(directory, String(frame).padStart(4, "0") + ".png"),
        Buffer.from(capture.data, "base64"),
      );
    }
    assert.equal(final.action, "close");
    assert.equal(final.progress, 1);
    assert(final.complete);
    assert.deepEqual(
      await evaluate(
        "({document:effectDocument(),history:editHistory,historyIndex,editingAction,mode,seed})",
      ),
      before,
    );
    writeFileSync(join(directory, "timeline.json"), JSON.stringify(plan, null, 2) + "\n");
    const target = "docs/gifs/" + name + ".gif";
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
    const manifestPath = "docs/gifs/scenario-manifest.json",
      manifest = JSON.parse(readFileSync(manifestPath));
    const entry = {
      name,
      file: target,
      mode: "pointer",
      source,
      frames: count,
      fps,
      bytes: statSync(target).size,
      backend: "Studio native-math pointer preview / synthetic input and texture",
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
          "niri_fx/shaders/gravity.glsl",
          "niri_fx/shaders/gravity-entry.glsl",
          "scripts/record-pointer-preview.mjs",
        ].map((path) => [path, createHash("sha256").update(readFileSync(path)).digest("hex")]),
      ),
      checks: [
        "actual Preview combo button",
        "deterministic drag, reverse and release",
        "selected pointer controls",
        "complete open and close cycle",
        "document and Undo history unchanged",
      ],
    };
    const index = manifest.clips.findIndex((clip) => clip.name === name);
    if (index < 0) manifest.clips.push(entry);
    else manifest.clips[index] = entry;
    writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
    console.log(`Rendered ${name}: ${count} frames at ${fps} fps, ${entry.bytes} bytes`);
  }
  console.log("PASS: pointer combo recordings. Evidence: " + scratch);
} finally {
  await browser.close();
}
