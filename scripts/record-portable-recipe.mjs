// Record Web Studio recipe editing on synthetic content, without local endpoints.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { launchBrowser, projectRoot } from "./lib/browser.mjs";
import { recordingProvenance } from "./lib/recording-provenance.mjs";

process.chdir(projectRoot);
const capture = recordingProvenance("scripts/record-portable-recipe.mjs");
let browser;
try {
  mkdirSync("artifacts", { recursive: true });
  const root = mkdtempSync(join(projectRoot, "artifacts/portable-recipe-"));
  capture.generate(join(root, "preview.html"), [], { hosted: true });
  browser = await launchBrowser();
  await capture.navigate(browser, { width: 1440, height: 1160 });
  const { evaluate, callFunction, rpc } = browser;
  await rpc("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: root });
  await evaluate(`(() => {
    window.requestAnimationFrame=()=>1;window.cancelAnimationFrame=()=>{};seed=.43;
    const style=document.createElement('style');
    style.textContent='canvas{max-height:380px;min-height:0}aside{max-height:calc(100vh - 470px)}';
    document.head.append(style);
    const banner=document.createElement('div');banner.id='recording-step';
    banner.style.cssText='position:fixed;bottom:0;left:0;right:0;padding:14px 24px;background:#172434;color:#e4efff;font:600 19px system-ui;z-index:100';
    document.body.append(banner);
    document.querySelector('[data-library-action=movement]').click();
  })()`);
  assert.equal(await evaluate("catalog.hosted"), true);
  assert.equal(await evaluate("catalog.connection"), null);
  assert.equal(await evaluate("byId('activation-controls').hidden"), true);
  const fps = 20;
  let count = 0;
  async function hold(label, seconds = 2) {
    await callFunction("function(label){byId('recording-step').textContent=label}", [label]);
    const shot = await rpc("Page.captureScreenshot", { format: "png" }),
      pixels = Buffer.from(shot.data, "base64");
    for (let frame = 0; frame < seconds * fps; frame++)
      writeFileSync(join(root, String(count++).padStart(4, "0") + ".png"), pixels);
  }
  async function choose(id, value) {
    await callFunction(
      "function(id,value){byId(id).value=value;byId(id).dispatchEvent(new Event('change'))}",
      [id, value],
    );
  }
  async function focus(id, offset = 40) {
    await callFunction(
      "function(id,offset){byId('library-panel').scrollTop+=byId(id).getBoundingClientRect().top-byId('library-panel').getBoundingClientRect().top-offset}",
      [id, offset],
    );
  }
  const waitForSave = () =>
    evaluate(`new Promise((resolve,reject)=>{
    const started=Date.now();function check(){if(!byId('profile-dialog').open&&!byId('store-profile').disabled)resolve();else if(Date.now()-started>5000)reject(new Error(byId('profile-dialog-error').textContent||'Save timeout'));else setTimeout(check,20)}check();
  })`);
  assert.deepEqual(
    await evaluate(
      "[...document.querySelectorAll('[data-fragment]')].map(item=>item.dataset.fragment)",
    ),
    ["gentle", "tear", "cascade"],
  );
  await hold("1 / Start with Gentle, Tear or Cascade in Web Studio");
  await evaluate("document.querySelector('[data-fragment=tear]').click()");
  assert.deepEqual(
    await evaluate("effectDocument().fragment_motion"),
    await evaluate("catalog.fragment_presets.tear.settings"),
  );
  await hold("2 / Tear includes material and response / The canvas previews material only");
  await evaluate("byId('combo-options').open=true;byId('fragment-tuning').open=true");
  await focus("native-fragments");
  await hold("3 / Open response controls when you want more detail", 1.5);
  await choose("fragment-response-max_lag", "555");
  const response = await evaluate("effectDocument().fragment_motion");
  assert.equal(response.max_lag, 555);
  assert.equal(await evaluate("byId('native-fragment-preset').value"), "custom");
  await focus("fragment-response-max_lag", 280);
  await hold("4 / Customize maximum separation / Every response value stays in the recipe");
  await evaluate("byId('fragment-tuning').open=false");
  await choose("combo-movement-mode", "off");
  await focus("native-fragments", 120);
  assert.deepEqual(await evaluate("effectDocument().fragment_motion"), response);
  assert.match(
    await evaluate("byId('native-fragment-description').textContent"),
    /Move is Off.*response stays saved/,
  );
  await hold("5 / Move Off keeps your response saved and inactive");
  await choose("combo-movement-mode", "style");
  assert.deepEqual(await evaluate("effectDocument().fragment_motion"), response);
  await hold("6 / Return to a compatible Move style / Your custom response returns");
  await choose("combo-name", "Portable Tear");
  const recipe = await evaluate("effectDocument()");
  assert.equal(recipe.schema, 4);
  assert.equal(recipe.actions.swap, null);
  await evaluate("byId('store-profile').click()");
  await hold("7 / Save the complete recipe to My profiles", 1.5);
  await evaluate("byId('profile-confirm').click()");
  await waitForSave();
  assert.deepEqual(
    await evaluate(
      "JSON.parse(localStorage.getItem('nirifx-my-profiles'))['custom-portable-tear']",
    ),
    recipe,
  );
  await choose("native-fragment-preset", "gentle");
  await choose("library-collection", "customs");
  await evaluate(
    "byId('combo-options').open=false;byId('library-panel').scrollTop=0;document.querySelector('[data-style=custom-portable-tear]').click()",
  );
  assert.deepEqual(await evaluate("effectDocument()"), recipe);
  await hold("8 / Reopen My profiles / Material and all 18 response controls return");
  await evaluate("byId('transfer-options').open=true;byId('export').click()");
  await hold("9 / Export editable JSON / The same recipe opens in local Studio");
  assert.deepEqual(JSON.parse(readFileSync(join(root, "nirifx-preset.json"))), recipe);
  const documentSources = ["gentle", "tear", "cascade", "long-trail"].map(
    (name) => "examples/profiles/continuous-" + name + ".json",
  );
  // Each source is really imported and shown. These declarations are separate
  // from runtime hashes so documentation coverage means observed documents.
  for (const source of documentSources) {
    const input = JSON.parse(readFileSync(source, "utf8"));
    await callFunction(
      `async function(document,name){
      const files=new DataTransfer();
      files.items.add(new File([JSON.stringify(document)],name,{type:'application/json'}));
      byId('import-file').files=files.files;await byId('import-file').onchange();
    }`,
      [input, source.split("/").at(-1)],
    );
    assert.deepEqual(await evaluate("effectDocument()"), input);
    await evaluate(
      "document.querySelector('[data-library-action=movement]').click();byId('combo-options').open=true;byId('fragment-tuning').open=false",
    );
    await focus("native-fragments", 100);
    await hold("JSON example / " + input.name + " / Material preview only", 1.5);
  }
  assert.equal(await evaluate("byId('error').textContent"), "");
  const destination = "docs/gifs/workflow-portable-recipe.gif",
    encoded = join(root, "rendered.gif");
  execFileSync("ffmpeg", [
    "-y",
    "-loglevel",
    "error",
    "-framerate",
    String(fps),
    "-i",
    join(root, "%04d.png"),
    "-filter_complex",
    "scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=none",
    "-loop",
    "0",
    encoded,
  ]);
  await capture.publish({
    sources: [
      "scripts/record-portable-recipe.mjs",
      "niri_fx/fragment_motion.py",
      "niri_fx/profiles.py",
      "niri_fx/documents.py",
      "niri_fx/preview.py",
      "niri_fx/effect-core.js",
      "niri_fx/library.js",
      "niri_fx/studio.js",
      "niri_fx/preview.html",
      "niri_fx/studio.css",
      ...documentSources,
    ],
    encoded,
    destination,
    manifestPath: "docs/gifs/scenario-manifest.json",
    entry: {
      name: "workflow-portable-recipe",
      backend: "actual hosted Studio UI / synthetic material preview only",
      document_sources: documentSources,
      fps,
      frames: count,
      checks: [
        "public hosted catalog without local connection",
        "Gentle Tear Cascade first",
        "complete preset response",
        "custom maximum separation",
        "Move Off retains dormant response",
        "compatible style restores custom response",
        "browser Library save and reopen",
        "all 18 response values preserved",
        "actual complete JSON download",
        "actual import and complete equality for every document_sources example",
        "no compositor response claim",
      ],
    },
  });
  console.log(`PASS: portable hosted recipe; ${count} frames. Evidence: ${root}`);
} finally {
  try {
    await browser?.close();
  } finally {
    await capture.close();
  }
}
