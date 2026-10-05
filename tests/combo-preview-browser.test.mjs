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

// Pointer metadata uses the same document/history transactions as shader
// actions, while activation remains an explicit, capability-gated choice.
test("pointer choices survive Library editing, JSON, sharing and stock-safe exports", async () => {
  const html = execFileSync(
    "python3",
    [
      "-c",
      'from niri_fx.preview import preview_document; from niri_fx.presets import PRESETS; print(preview_document(PRESETS["balanced"], hosted=True))',
    ],
    { cwd: projectRoot, encoding: "utf8", maxBuffer: 4 * 1024 * 1024 },
  );
  const scratch = mkdtempSync(join(tmpdir(), "nirifx-pointer-ui-"));
  const page = join(scratch, "studio.html");
  writeFileSync(page, html);
  const browser = await launchBrowser();
  try {
    await browser.navigate(pathToFileURL(page).href + "?breakup=0");
    const evaluate = browser.evaluate;
    await evaluate("window.requestAnimationFrame=()=>1;window.cancelAnimationFrame=()=>{}");
    const choose = (value) =>
      evaluate(
        `byId("combo-pointer").value=${JSON.stringify(value)};byId("combo-pointer").dispatchEvent(new Event("change"))`,
      );
    assert.equal(await evaluate('byId("combo-pointer").value'), "");
    assert.equal(await evaluate('Object.hasOwn(effectDocument(),"pointer")'), false);
    assert.equal(await evaluate('byId("activate-pointer-label").hidden'), true);
    await choose("gentle");
    assert.deepEqual(await evaluate("effectDocument().pointer"), {
      strength: 0.4,
      damping: 85,
      frequency: 10,
    });
    assert.equal(await evaluate("effectDocument().actions.resize"), null);
    assert.equal(await evaluate("effectDocument().actions.movement"), null);
    assert.equal(await evaluate('byId("pointer-kdl").hidden'), false);
    const beforePreview = await evaluate("effectDocument()");
    await evaluate('byId("preview-combo").click()');
    const pointerStage = await evaluate(
      'niriFxComboPreview.currentPlan.stages.find(stage=>stage.action==="pointer")',
    );
    assert(pointerStage);
    await evaluate(`niriFxComboPreview.seek(${pointerStage.startMs + 600})`);
    assert.match(
      await evaluate('byId("combo-preview-status").textContent'),
      /Native spring and shader math; synthetic input, not compositor validation/,
    );
    assert.equal(await evaluate("document.documentElement.dataset.shaderStatus"), "ready");
    assert.equal(await evaluate("document.documentElement.dataset.comboAction"), "pointer");
    await evaluate("niriFxComboPreview.seek(niriFxComboPreview.currentPlan.totalMs)");
    assert.deepEqual(await evaluate("effectDocument()"), beforePreview);
    assert.deepEqual(
      await evaluate(
        'niriFxComboPreview.currentPlan.stages.filter(s=>s.phase==="animation").map(s=>s.action)',
      ),
      ["open", "pointer", "close"],
    );
    await evaluate(
      'byId("combo-close").value="frost-vanish";byId("combo-close").dispatchEvent(new Event("change"))',
    );
    assert.deepEqual(await evaluate("effectDocument().pointer"), beforePreview.pointer);
    await evaluate(
      'byId("combo-mode").value="same";byId("combo-mode").dispatchEvent(new Event("change"));byId("combo-same").value="zipper";byId("combo-same").dispatchEvent(new Event("change"))',
    );
    assert.deepEqual(await evaluate("effectDocument().pointer"), beforePreview.pointer);
    await choose("custom");
    assert.equal(await evaluate('byId("pointer-tuning").open'), true);
    await evaluate(
      'byId("pointer-strength").value="1.15";byId("pointer-strength").dispatchEvent(new Event("change"))',
    );
    const custom = await evaluate("effectDocument()");
    assert.equal(custom.pointer.strength, 1.15);
    assert.equal(await evaluate('byId("combo-pointer").value'), "custom");
    await evaluate('byId("undo").click()');
    assert.equal(await evaluate("effectDocument().pointer.strength"), 0.4);
    await evaluate('byId("redo").click()');
    assert.deepEqual(await evaluate("effectDocument()"), custom);
    await evaluate(
      'byId("pointer-frequency").value="17";byId("pointer-frequency").dispatchEvent(new Event("change"))',
    );
    assert.deepEqual(await evaluate("effectDocument()"), custom);
    assert.equal(await evaluate('byId("pointer-frequency").value'), "10");
    assert.match(await evaluate('byId("error").textContent'), /frequency/);
    await evaluate('byId("show-editor").click();byId("independent").click()');
    assert.deepEqual(await evaluate("effectDocument().pointer"), custom.pointer);
    await evaluate('byId("edit-pointer").click()');
    assert.equal(await evaluate("document.documentElement.dataset.workspace"), "library");
    assert.equal(await evaluate("document.activeElement.id"), "combo-pointer");
    await evaluate(
      'window.pointerDownloads=[];download=(...args)=>pointerDownloads.push(args);byId("export").click();byId("kdl").click();byId("pointer-kdl").click()',
    );
    const downloads = await evaluate("pointerDownloads");
    assert.deepEqual(JSON.parse(downloads[0][1]).pointer, custom.pointer);
    assert.doesNotMatch(downloads[1][1], /pointer-wobble/);
    assert.match(downloads[2][1], /pointer-wobble/);
    assert.equal((downloads[2][1].match(/window-movement/g) || []).length, 1);
    await evaluate(
      'byId("combo-movement").value="fragment-wake";byId("combo-movement").dispatchEvent(new Event("change"));byId("combo-resize").value="spring-wobble";byId("combo-resize").dispatchEvent(new Event("change"));byId("desktop-motion").value="gentle";byId("desktop-motion").dispatchEvent(new Event("change"));byId("pointer-kdl").click()',
    );
    const combinedDocument = await evaluate("effectDocument()");
    const combinedKdl = (await evaluate("pointerDownloads.at(-1)"))[1];
    const expectedKdl = execFileSync(
      "python3",
      [
        "-c",
        "import json,sys;from niri_fx.documents import parse_document;from niri_fx.effects import render_kdl;print(render_kdl(parse_document(json.load(sys.stdin))[2], movement=True, pointer=True), end='')",
      ],
      { cwd: projectRoot, input: JSON.stringify(combinedDocument), encoding: "utf8" },
    );
    assert.equal(
      combinedKdl.slice(combinedKdl.indexOf("\n")),
      expectedKdl.slice(expectedKdl.indexOf("\n")),
    );
    assert.equal((combinedKdl.match(/window-movement/g) || []).length, 1);
    assert.match(combinedKdl, /window-resize/);
    assert.match(combinedKdl, /workspace-switch/);
    await evaluate('byId("share").onclick()');
    const shared = await evaluate(
      'decodeShareDocument(new URLSearchParams(new URL(byId("share-url").value).hash.slice(1)).get("style"))',
    );
    assert.deepEqual(shared.pointer, custom.pointer);
    await evaluate(
      'byId("combo-name").value="Pointer Fusion";byId("combo-name").dispatchEvent(new Event("change"));byId("store-profile").click();byId("profile-confirm").click()',
    );
    await evaluate(
      'new Promise((resolve,reject)=>{const start=Date.now();function check(){if(!byId("profile-dialog").open&&!byId("store-profile").disabled)resolve();else if(Date.now()-start>5000)reject(new Error("Profile save did not settle"));else setTimeout(check,20)}check()})',
    );
    const saved = await evaluate(
      'JSON.parse(localStorage.getItem("nirifx-my-profiles"))["custom-pointer-fusion"]',
    );
    assert.deepEqual(saved.pointer, custom.pointer);
    await choose("disabled");
    assert.equal(await evaluate("effectDocument().pointer.strength"), 0);
    assert.match(await evaluate("kdlDocument({pointer:true})"), /strength 0\.0/);
    await choose("");
    assert.equal(await evaluate('Object.hasOwn(effectDocument(),"pointer")'), false);
    assert.equal(await evaluate('byId("pointer-kdl").hidden'), true);
    await browser.callFunction(
      `async function(text) {
        const files = new DataTransfer();
        files.items.add(new File([text], "pointer.json", {type: "application/json"}));
        byId("import-file").files = files.files;
        await byId("import-file").onchange();
      }`,
      [JSON.stringify(saved)],
    );
    assert.deepEqual(await evaluate("effectDocument()"), saved);
    assert.equal(await evaluate('byId("combo-pointer").value'), "custom");
    assert.equal(await evaluate('byId("error").textContent'), "");
    assert.equal(await evaluate('byId("activate-pointer-label").hidden'), true);
  } finally {
    await browser.close();
    rmSync(scratch, { recursive: true, force: true });
  }
});

test("pointer Apply consent is offered only for a verified standalone session", async () => {
  const scratch = mkdtempSync(join(tmpdir(), "nirifx-pointer-consent-"));
  const browser = await launchBrowser();
  try {
    // Exercise UI requests without touching a user's compositor or filesystem.
    await browser.rpc("Page.addScriptToEvaluateOnNewDocument", {
      source: `window.pointerRequests=[];window.fetch=async(path,options)=>{if(options?.body)pointerRequests.push({path,body:JSON.parse(options.body)});return {ok:true,json:async()=>path==="/review"?{plan_sha256:"test-plan",notes:["Reviewed test selection"],changes:[{action:"update",path:"isolated-config.kdl"}]}:{customs:{},managed:{},warnings:[],restore:false,active_name:"Test desktop"}}};`,
    });
    for (const [target, ready, supported] of [
      ["standalone", true, true],
      ["standalone", false, true],
      ["inir", true, false],
    ]) {
      const connection = {
        target,
        token: "test-token",
        pointer: {
          activation_ready: ready,
          target_supported: supported,
          target_detail: "Test capability status",
        },
      };
      const html = execFileSync(
        "python3",
        [
          "-c",
          'import json,sys; from niri_fx.preview import preview_document; from niri_fx.presets import PRESETS; print(preview_document(PRESETS["balanced"],connection=json.loads(sys.argv[1])))',
          JSON.stringify(connection),
        ],
        { cwd: projectRoot, encoding: "utf8", maxBuffer: 4 * 1024 * 1024 },
      );
      const page = join(scratch, `${target}-${ready}.html`);
      writeFileSync(page, html);
      await browser.navigate(pathToFileURL(page).href + "?breakup=0");
      const evaluate = browser.evaluate;
      await evaluate(
        'byId("combo-pointer").value="gentle";byId("combo-pointer").dispatchEvent(new Event("change"))',
      );
      assert.equal(await evaluate('byId("activate-pointer-label").hidden'), !(ready && supported));
      assert.equal(await evaluate('byId("activate-pointer").checked'), false);
      await evaluate('byId("review-selection").onclick()');
      assert.equal(
        await evaluate('pointerRequests.find(item=>item.path==="/review").body.allow_pointer'),
        false,
      );
      await evaluate(
        'byId("activate-pointer").checked=true;byId("activate-pointer").dispatchEvent(new Event("change"));byId("review-selection").onclick()',
      );
      assert.equal(
        await evaluate(
          'pointerRequests.filter(item=>item.path==="/review").at(-1).body.allow_pointer',
        ),
        ready && supported,
      );
      if (ready && supported) {
        await evaluate('byId("apply-selection").onclick()');
        assert.equal(
          await evaluate(
            'pointerRequests.find(item=>item.path==="/apply").body.selection.allow_pointer',
          ),
          true,
        );
        assert.equal(
          await evaluate('pointerRequests.find(item=>item.path==="/apply").body.expected'),
          "test-plan",
        );
      }
      await evaluate(
        'byId("combo-pointer").value="disabled";byId("combo-pointer").dispatchEvent(new Event("change"))',
      );
      assert.equal(await evaluate('byId("activate-pointer").checked'), false);
      assert.equal(await evaluate('byId("apply-review").hidden'), true);
    }
  } finally {
    await browser.close();
    rmSync(scratch, { recursive: true, force: true });
  }
});
