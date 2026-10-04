import assert from "node:assert/strict";
import { test } from "node:test";
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { pathToFileURL } from "node:url";
import { launchBrowser, projectRoot } from "../scripts/lib/browser.mjs";

// Drive the real UI through deterministic playback timestamps. The planner's
// clock/cancellation tests cover RAF scheduling; this checks rendered uniforms,
// document isolation, editor transactions and the actual reduced-motion UI.
test("complete combo playback preserves settings and renders selected action loops", async () => {
  const html = execFileSync(
    "python3",
    [
      "-c",
      'from niri_fx.preview import preview_document; from niri_fx.presets import PRESETS; print(preview_document(PRESETS["balanced"], hosted=True))',
    ],
    { cwd: projectRoot, encoding: "utf8", maxBuffer: 4 * 1024 * 1024 },
  );
  const scratch = mkdtempSync(join(tmpdir(), "nirifx-combo-test-"));
  const page = join(scratch, "studio.html");
  writeFileSync(page, html);
  const browser = await launchBrowser();
  try {
    // No uncontrolled intermediate shader work on software GPU. seek() uses
    // the actual production render callback after the actual button starts it.
    await browser.navigate(pathToFileURL(page).href + "?breakup=0");
    const evaluate = browser.evaluate;
    await evaluate(
      `window.comboFrames=new Map();window.comboFrameId=0;window.requestAnimationFrame=callback=>{comboFrames.set(++comboFrameId,callback);return comboFrameId};window.cancelAnimationFrame=id=>comboFrames.delete(id);`,
    );
    assert.deepEqual(
      await evaluate(
        '[...document.querySelectorAll("#library-results [data-style]")].slice(0,5).map(node=>node.dataset.style)',
      ),
      ["fragment-flow", "soft-landing", "ribbon-current", "playful-motion", "geometric-flow"],
    );
    await evaluate('document.querySelector("[data-style=fragment-flow]").click()');
    assert.equal(
      await evaluate('byId("combo-open").selectedOptions[0].textContent'),
      "Fragment Flow · Open",
    );
    await evaluate(
      'byId("combo-mode").value="same";byId("combo-mode").dispatchEvent(new Event("change"))',
    );
    assert.deepEqual(
      await evaluate("effectDocument().actions.open"),
      await evaluate("effectDocument().actions.close"),
    );
    await evaluate('byId("undo").click()');
    const snapshot = await evaluate(
      "({document:effectDocument(),history:historyIndex,action:editingAction,mode,progress,seed,kdl:kdlDocument()})",
    );
    await evaluate('byId("preview-combo").click();niriFxComboPreview.seek(0)');
    const basic = await evaluate(
      '({actions:niriFxComboPreview.currentPlan.stages.filter(s=>s.phase==="animation").map(s=>s.action),total:niriFxComboPreview.currentPlan.totalMs})',
    );
    assert.deepEqual(basic.actions, ["open", "close"]);
    assert.equal(
      basic.total,
      snapshot.document.actions.open.open_ms + 650 + snapshot.document.actions.close.close_ms,
    );
    assert.deepEqual(
      await evaluate(
        "({document:effectDocument(),history:historyIndex,action:editingAction,mode,progress,seed,kdl:kdlDocument()})",
      ),
      snapshot,
    );
    await evaluate("niriFxComboPreview.seek(niriFxComboPreview.currentPlan.totalMs)");
    assert.equal(await evaluate("document.documentElement.dataset.comboState"), "complete");
    assert.equal(await evaluate('byId("progress").value'), "1000");
    assert.equal(
      await evaluate(
        `(()=>{const gl=byId("stage").getContext("webgl"),pixel=new Uint8Array(4);gl.readPixels(600,380,1,1,gl.RGBA,gl.UNSIGNED_BYTE,pixel);return pixel[3]})()`,
      ),
      0,
    );
    assert.deepEqual(await evaluate("effectDocument()"), snapshot.document);
    // Optional actions are explicitly picked; tuned close is different from open.
    await evaluate(
      'byId("combo-close").value="frost-vanish";byId("combo-close").dispatchEvent(new Event("change"));byId("combo-resize").value="spring-wobble";byId("combo-resize").dispatchEvent(new Event("change"));byId("combo-movement").value="fragment-wake";byId("combo-movement").dispatchEvent(new Event("change"))',
    );
    const selected = await evaluate(
      "({document:effectDocument(),history:historyIndex,action:editingAction,mode,seed})",
    );
    await evaluate('byId("preview-combo").click();niriFxComboPreview.seek(0)');
    const plan = await evaluate("niriFxComboPreview.currentPlan");
    const animations = plan.stages.filter((s) => s.phase === "animation");
    assert.deepEqual(
      animations.map((s) => [s.action, s.direction]),
      [
        ["open", null],
        ["resize", "grow"],
        ["resize", "shrink"],
        ["movement", "right"],
        ["movement", "left"],
        ["close", null],
      ],
    );
    assert.equal(animations.at(-1).effect.family, "dissolve");
    for (const stage of animations)
      assert.equal(stage.durationMs, selected.document.actions[stage.action][stage.action + "_ms"]);
    const uniforms = async (time) =>
      evaluate(
        `(()=>{niriFxComboPreview.seek(${time});const gl=byId("stage").getContext("webgl"),program=gl.getParameter(gl.CURRENT_PROGRAM),uniform=name=>{const location=gl.getUniformLocation(program,name);return location ? Array.from(gl.getUniform(program,location)||[]) : []};return {mode:document.documentElement.dataset.comboAction,origin:uniform("fx_move_origin"),from:uniform("fx_resize_from"),to:uniform("fx_resize_to")}})()`,
      );
    const grow = await uniforms(animations[1].startMs + animations[1].durationMs);
    assert.deepEqual(grow.from, [600, 380]);
    assert.deepEqual(grow.to, [800, 440]);
    const shrink = await uniforms(animations[2].startMs);
    assert.deepEqual(shrink.from, [800, 440]);
    assert.deepEqual(shrink.to, [600, 380]);
    const outStart = await uniforms(animations[3].startMs),
      outEnd = await uniforms(animations[3].startMs + animations[3].durationMs),
      backStart = await uniforms(animations[4].startMs),
      backEnd = await uniforms(animations[4].startMs + animations[4].durationMs);
    assert.deepEqual(outEnd.origin, backStart.origin);
    assert.deepEqual(outStart.origin, backEnd.origin);
    assert.equal(outEnd.origin[0] - outStart.origin[0], 160);
    assert.deepEqual(
      await evaluate(
        "({document:effectDocument(),history:historyIndex,action:editingAction,mode,seed})",
      ),
      selected,
    );
    // An edit stops the plan before loading new settings; late RAF is invalid.
    await evaluate(
      'byId("combo-close").value="ghost-wisps";byId("combo-close").dispatchEvent(new Event("change"));for(const callback of comboFrames.values())callback(performance.now()+10000)',
    );
    assert.equal(await evaluate("niriFxComboPreview.active"), false);
    assert.equal(await evaluate('byId("combo-preview-status").hidden'), true);
    assert.equal(await evaluate("effectDocument().actions.close.family"), "wisps");
    await evaluate('byId("undo").click()');
    assert.deepEqual(await evaluate("effectDocument()"), selected.document);
    // Media preference is honored at the actual entry point, without deforming
    // frames. The one readable opening hold remains before transparent close.
    await browser.rpc("Emulation.setEmulatedMedia", {
      features: [{ name: "prefers-reduced-motion", value: "reduce" }],
    });
    await evaluate(
      `new Promise((resolve,reject)=>{const started=Date.now();function check(){if(byId("reduced-motion").checked)resolve();else if(Date.now()-started>5000)reject(new Error("Reduced motion preference did not update"));else setTimeout(check,30)}check()})`,
    );
    assert.equal(await evaluate('byId("reduced-motion").checked'), true);
    await evaluate('byId("preview-combo").click();niriFxComboPreview.seek(0)');
    const reduced = await evaluate("niriFxComboPreview.currentPlan");
    assert.equal(reduced.reducedMotion, true);
    assert.ok(
      reduced.stages.filter((s) => s.phase === "animation").every((s) => s.durationMs === 0),
    );
    await evaluate('byId("preview-combo").click()');
    assert.equal(await evaluate("niriFxComboPreview.active"), false);
    assert.deepEqual(await evaluate("effectDocument()"), selected.document);
    assert.equal(await evaluate("document.documentElement.dataset.shaderStatus"), "ready");
  } finally {
    await browser.close();
    rmSync(scratch, { recursive: true, force: true });
  }
});
