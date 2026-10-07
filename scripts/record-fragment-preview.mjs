// Record Studio's actual continuous-fragment demo with deterministic synthetic
// input. Native-reference tests cover the math; these are browser showcases,
// not recordings of a desktop compositor or measurements of GPU performance.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { launchBrowser, projectRoot } from "./lib/browser.mjs";
import { recordingProvenance } from "./lib/recording-provenance.mjs";

process.chdir(projectRoot);
const capture = recordingProvenance("scripts/record-fragment-preview.mjs");
let browser;
try {
  mkdirSync("artifacts", { recursive: true });
  const scratch = mkdtempSync(join(projectRoot, "artifacts/fragment-preview-recording-"));
  browser = await launchBrowser();
  const fps = 25;
  for (const id of ["gentle", "tear", "cascade"]) {
    const name = "fragment-preview-" + id,
      source = "examples/profiles/continuous-" + id + ".json",
      document = JSON.parse(readFileSync(source)),
      directory = join(scratch, name),
      page = join(directory, "preview.html");
    mkdirSync(directory);
    capture.generate(page, ["--custom", source]);
    await capture.navigate(browser, { width: 720, height: 616 });
    const { evaluate, rpc } = browser;
    await evaluate(`(()=>{
      const style=document.createElement('style');
      style.textContent='html,body{width:720px;height:616px;max-width:none;margin:0;padding:0;overflow:hidden;background:#10151e}header,body>p,aside,.tabs,.controls,#library-actions,#transfer-options,.selection-summary,.selection-bar,.preview-heading,.workspace-tools,#apply-review,.preview-preferences,#concept-note,#movement-preview-controls,#pointer-preview-tools,#fragment-preview-tools,#caption,#status,main>small,.motion-preference,#error,#combo-preview-status{display:none!important}.layout{display:block;margin:0 14px}html[data-workspace] canvas{width:690px;height:524px!important;max-height:none!important;min-height:0!important;border-radius:12px}canvas[hidden]{display:none}#gif-heading{height:53px;padding:18px 22px 0;box-sizing:border-box;font-size:18px;font-weight:600;color:#dfedf5}#gif-note{padding:10px 22px;font-size:12px;color:#93b5c5;display:block!important}';
      document.head.append(style);
      const heading=document.createElement('div');heading.id='gif-heading';heading.textContent=${JSON.stringify(document.name)};document.body.prepend(heading);
      const note=document.createElement('div');note.id='gif-note';document.body.append(note);
      byId('reduced-motion').checked=false;
      window.recordNow=1000;performance.now=()=>recordNow;
      window.recordFrames=new Map();window.recordFrameId=0;
      window.requestAnimationFrame=callback=>{recordFrames.set(++recordFrameId,callback);return recordFrameId};
      window.cancelAnimationFrame=id=>recordFrames.delete(id);
    })()`);
    const before = await evaluate(
      "({document:effectDocument(),history:editHistory,historyIndex,editingAction,mode,seed,progress})",
    );
    await evaluate("byId('try-fragments').click();byId('fragment-demo').click()");
    assert.equal(
      await evaluate("niriFxFragmentPreview.snapshot().demo"),
      true,
      "Actual drag demo button must start playback",
    );
    assert(
      await evaluate(
        `(()=>{const rect=byId('fragment-stage').getBoundingClientRect();return rect.top>=53&&rect.top<=55&&rect.height>=524&&rect.bottom<590})()`,
      ),
      "Capture must contain the full preview without Studio controls",
    );
    assert.deepEqual(
      await evaluate("effectDocument()"),
      await browser.callFunction("function(doc){return normalizePreset(doc)}", [document]),
    );
    const totalMs = 1600 + document.fragment_motion.release_ms,
      count = Math.ceil((totalMs * fps) / 1000) + 1;
    let final;
    for (let frame = 0; frame < count; frame++) {
      const elapsed = Math.min(totalMs, (frame * 1000) / fps);
      final = await evaluate(`(()=>{
        recordNow=1000+${elapsed};const callbacks=[...recordFrames.values()];recordFrames.clear();callbacks.forEach(callback=>callback(recordNow));
        const state=niriFxFragmentPreview.snapshot();
        byId('gif-note').textContent=${elapsed}<240?'Press and hold · browser preview':${elapsed}<1600?'Drag, pause and reverse · synthetic input':'Release and reconstruct · native response math';
        if(!state.active||byId('error').textContent)throw new Error(byId('error').textContent||'Preview stopped');
        return {active:state.active,scheduled:state.scheduled,demo:state.demo,moving:state.frame.moving};
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
    assert.equal(final.demo, false);
    assert.equal(final.moving, false);
    assert.equal(final.scheduled, false);
    assert.deepEqual(
      await evaluate(
        "({document:effectDocument(),history:editHistory,historyIndex,editingAction,mode,seed,progress})",
      ),
      before,
    );
    const target = "docs/gifs/" + name + ".gif",
      encoded = join(directory, "rendered.gif");
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
      "niri_fx/fragment-preview.js",
      "niri_fx/fragment-controls.js",
      "niri_fx/fragment_motion.py",
      "niri_fx/preview.py",
      "niri_fx/studio.js",
      "niri_fx/preview.html",
      "niri_fx/studio.css",
      "niri_fx/shaders/fragment-motion.glsl",
      "scripts/record-fragment-preview.mjs",
    ];
    const published = await capture.publish({
      sources,
      encoded,
      destination: target,
      manifestPath: "docs/gifs/scenario-manifest.json",
      entry: {
        name,
        file: target,
        mode: "movement",
        source,
        frames: count,
        fps,
        backend: "Studio continuous-fragment preview / synthetic input and texture",
        checks: [
          "actual drag demo button",
          "press anticipation, drag, pause, reversal and release",
          "selected complete fragment response",
          "exact settled reconstruction",
          "document and Undo history unchanged",
        ],
      },
    });
    console.log(`Rendered ${name}: ${count} frames at ${fps} fps, ${published.bytes} bytes`);
  }
  console.log("PASS: continuous-fragment browser recordings. Evidence: " + scratch);
} finally {
  try {
    await browser?.close();
  } finally {
    await capture.close();
  }
}
