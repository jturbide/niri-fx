// Record real action controls and portable downloads with synthetic content.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { launchBrowser, projectRoot } from "./lib/browser.mjs";

process.chdir(projectRoot);
mkdirSync("artifacts", { recursive: true });
const root = mkdtempSync(join(projectRoot, "artifacts/action-choices-"));
const page = join(root, "preview.html");
execFileSync("python3", ["-m", "niri_fx", "preview", "--output", page]);
const browser = await launchBrowser();
const fps = 20;
let count = 0;
try {
  const { evaluate, rpc, callFunction } = browser;
  await browser.navigate(pathToFileURL(page).href, { width: 1440, height: 1160 });
  await rpc("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: root });
  await evaluate(`(() => {
    seed=.43;
    const style=document.createElement('style');
    style.textContent='canvas{max-height:380px;min-height:0}aside{max-height:calc(100vh - 470px)}';document.head.append(style);
    const banner=document.createElement('div');banner.id='recording-step';
    banner.style.cssText='position:fixed;bottom:0;left:0;right:0;padding:14px 24px;background:#212331;color:#f0edf7;font:600 19px system-ui;z-index:100';document.body.append(banner);
    document.querySelector('[data-library-action=combo]').click();document.querySelector('[data-style=fragment-flow]').click();
    byId('combo-options').open=true;
    byId('library-panel').scrollTop=byId('combo-actions').offsetTop-byId('library-panel').offsetTop-120;
  })()`);
  async function select(id, value) {
    await callFunction(
      "function(id,value) { const select=byId(id); select.value=value; select.dispatchEvent(new Event('change')); }",
      [id, value],
    );
  }
  async function hold(label, seconds = 1.5) {
    await callFunction("function(label) { byId('recording-step').textContent=label; }", [label]);
    const shot = await rpc("Page.captureScreenshot", { format: "png" });
    const pixels = Buffer.from(shot.data, "base64");
    for (let index = 0; index < seconds * fps; index++)
      writeFileSync(join(root, String(count++).padStart(4, "0") + ".png"), pixels);
  }
  await hold("Choose a mode for each action: Preserve / NiriFX Style / Off", 2);
  await select("combo-open-mode", "preserve");
  await hold("Preserve opening / Keep the Niri or shell settings underneath NiriFX", 2);
  await select("combo-close", "frost-vanish");
  await hold("NiriFX Style for closing / Choose Frost Vanish", 1.5);
  await select("combo-resize-mode", "off");
  await hold("Off for resize / Disable this action without changing the others", 2);
  let document = await evaluate("effectDocument()");
  assert.equal(document.actions.open, null);
  assert.equal(document.actions.close.family, "dissolve");
  assert.equal(document.actions.resize, "off");
  await select("combo-movement", "fragment-wake");
  await select("combo-swap", "pixel-relay");
  const movement = await evaluate("effectDocument().actions.movement");
  assert.equal(await evaluate("effectDocument().actions.swap.family"), "pixels");
  await evaluate(
    "byId('library-panel').scrollTop+=byId('combo-swap-mode').getBoundingClientRect().top-byId('library-panel').getBoundingClientRect().top-190",
  );
  await hold("Move with Fragment Wake / Swap with Pixel Relay", 2);
  await select("combo-swap-mode", "off");
  assert.deepEqual(await evaluate("effectDocument().actions.movement"), movement);
  await hold("Turn Swap off / Your Move style stays the same", 1.5);
  await select("combo-swap-mode", "preserve");
  await select("combo-movement-mode", "preserve");
  await evaluate(
    "byId('library-panel').scrollTop=byId('combo-actions').offsetTop-byId('library-panel').offsetTop-120",
  );
  await select("combo-mode", "same");
  assert.equal(await evaluate("effectDocument().actions.open"), null);
  assert.equal(await evaluate("effectDocument().actions.resize"), "off");
  await hold("Shared style only changes NiriFX Style actions / Preserve and Off stay selected", 2);
  await select("combo-mode", "mixed");
  await select("combo-open-mode", "off");
  await select("combo-close-mode", "off");
  await hold("All three stock actions Off / Each choice remains independent", 2);
  document = await evaluate("effectDocument()");
  assert.equal(document.actions.open, "off");
  assert.equal(document.actions.close, "off");
  assert.equal(document.actions.resize, "off");
  await select("combo-open-mode", "preserve");
  await select("combo-close-mode", "style");
  await select("combo-close", "frost-vanish");
  await select("combo-name", "Quiet Exit");
  await evaluate("byId('transfer-options').open=true;byId('export').click();byId('kdl').click()");
  await hold("Export editable JSON and Niri config / Previewing leaves your desktop unchanged", 2);
  const saved = JSON.parse(readFileSync(join(root, "nirifx-preset.json")));
  assert.equal(saved.actions.open, null);
  assert.equal(saved.actions.resize, "off");
  const kdl = readFileSync(join(root, "nirifx.kdl"), "utf8");
  assert.doesNotMatch(kdl, /window-open/);
  assert.match(kdl, /window-resize\s*\{\s*off\s*\}/);
  execFileSync("niri", ["validate", "-c", join(root, "nirifx.kdl")]);
  const destination = "docs/gifs/workflow-action-choices.gif";
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
    destination,
  ]);
  const path = "docs/gifs/scenario-manifest.json";
  const manifest = JSON.parse(readFileSync(path));
  manifest.clips = manifest.clips.filter((clip) => clip.name !== "workflow-action-choices");
  manifest.clips.push({
    name: "workflow-action-choices",
    file: destination,
    bytes: statSync(destination).size,
    backend: "actual offline Library UI / synthetic texture",
    fps,
    frames: count,
    sources: Object.fromEntries(
      [
        "niri_fx/library.js",
        "niri_fx/effect-core.js",
        "niri_fx/preview.py",
        "niri_fx/studio.js",
        "niri_fx/preview.html",
        "niri_fx/studio.css",
        "scripts/record-action-choices.mjs",
      ].map((path) => [path, createHash("sha256").update(readFileSync(path)).digest("hex")]),
    ),
    checks: [
      "independent Preserve / NiriFX Style / Off",
      "Preserve retains underlying configuration",
      "independent Move and Swap styles",
      "Swap Off leaves Move unchanged",
      "shared style preserves other modes",
      "all stock actions Off",
      "actual JSON/KDL downloads",
      "stock Niri validation",
    ],
  });
  writeFileSync(path, JSON.stringify(manifest, null, 2) + "\n");
  console.log(`PASS: action choices and actual downloads; ${count} frames. Evidence: ${root}`);
} finally {
  await browser.close();
}
