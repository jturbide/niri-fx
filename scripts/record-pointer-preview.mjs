// Capture the same native-math drag trace that Studio plays in a combo.
// The window and input are synthetic; this is not a compositor recording.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { launchBrowser, projectRoot } from "./lib/browser.mjs";
import { recordingProvenance } from "./lib/recording-provenance.mjs";

process.chdir(projectRoot);
const capture = recordingProvenance("scripts/record-pointer-preview.mjs");
let browser;
try {
  mkdirSync("artifacts", { recursive: true });
  const scratch = mkdtempSync(join(projectRoot, "artifacts/pointer-preview-"));
  browser = await launchBrowser();
  const fps = 25;

  for (const id of ["gentle", "rubber-sheet", "release-settle"]) {
    const name = "pointer-preview-" + id,
      source = "examples/profiles/" + name + ".json",
      document = JSON.parse(readFileSync(source)),
      directory = join(scratch, name),
      page = join(directory, "preview.html");
    mkdirSync(directory);
    capture.generate(page, ["--custom", source]);
    await capture.navigate(browser, { width: 720, height: 616 });
    const { evaluate, rpc } = browser;
    await evaluate(`(() => {
      const style=document.createElement('style');
      style.textContent='html,body{width:720px;height:616px;max-width:none;margin:0;padding:0;overflow:hidden;background:#10151e}header,body>p,aside,.tabs,.controls,#library-actions,#transfer-options,.selection-summary,.selection-bar,.preview-heading,.workspace-tools,#apply-review,.preview-preferences,#concept-note,#movement-preview-controls,#pointer-preview-tools,#caption,#status,main>small,.motion-preference,#error,#combo-preview-status{display:none!important}.layout{display:block;margin:0 14px}html[data-workspace] canvas{width:690px;height:524px!important;max-height:none!important;min-height:0!important;border-radius:12px}canvas[hidden]{display:none}#gif-heading{height:53px;padding:18px 22px 0;box-sizing:border-box;font-size:18px;font-weight:600;color:#dfedf5}#gif-note{padding:10px 22px;font-size:12px;color:#93b5c5;display:block!important}';
      document.head.append(style);
      const heading=document.createElement('div');heading.id='gif-heading';heading.textContent=${JSON.stringify(document.name)};document.body.prepend(heading);
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
      const screenshot = await rpc("Page.captureScreenshot", {
        format: "png",
        captureBeyondViewport: false,
      });
      writeFileSync(
        join(directory, String(frame).padStart(4, "0") + ".png"),
        Buffer.from(screenshot.data, "base64"),
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
    const encoded = join(directory, "rendered.gif");
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
      encoded,
    ]);
    const sources = [
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
    ];
    const entry = {
      name,
      file: target,
      mode: "pointer",
      source,
      frames: count,
      fps,
      backend: "Studio native-math pointer preview / synthetic input and texture",
      checks: [
        "actual Preview combo button",
        "deterministic drag, reverse and release",
        "selected pointer controls",
        "complete open and close cycle",
        "document and Undo history unchanged",
      ],
    };
    const published = await capture.publish({
      sources,
      encoded,
      destination: target,
      manifestPath: "docs/gifs/scenario-manifest.json",
      entry,
    });
    console.log(`Rendered ${name}: ${count} frames at ${fps} fps, ${published.bytes} bytes`);
  }
  console.log("PASS: pointer combo recordings. Evidence: " + scratch);
} finally {
  try {
    await browser?.close();
  } finally {
    await capture.close();
  }
}
