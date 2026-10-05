// Record real Studio controls with a synthetic profile; no desktop or HTTP save.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { setTimeout as delay } from "node:timers/promises";
import { launchBrowser, projectRoot } from "./lib/browser.mjs";

process.chdir(projectRoot);
mkdirSync("artifacts", { recursive: true });
const root = mkdtempSync(join(projectRoot, "artifacts/studio-workflow-"));
const page = join(root, "preview.html");
execFileSync("python3", ["-m", "niri_fx", "preview", "--output", page]);
const browser = await launchBrowser();
try {
  const { rpc, evaluate } = browser;
  await browser.navigate(pathToFileURL(page).href, { width: 1280, height: 1080 });
  await evaluate("byId('show-editor').click();byId('transfer-options').open=true");
  await rpc("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: root });
  await evaluate(`
    seed=0.43;
    const captureStyle=document.createElement('style');
    captureStyle.textContent='canvas{max-height:400px;min-height:0}aside{max-height:calc(100vh - 270px)}';
    document.head.append(captureStyle);
    const banner=document.createElement('div');banner.id='recording-step';
    banner.style.cssText='position:fixed;bottom:0;left:0;right:0;padding:16px 24px;background:#172434;color:#e4efff;font:600 20px system-ui;z-index:100;box-shadow:0 -2px 12px #0005';
    document.body.append(banner);
  `);
  let count = 0;
  async function frames(label, seconds = 1.5, animate = false) {
    await evaluate(
      `document.getElementById('recording-step').textContent=${JSON.stringify(label)}`,
    );
    for (let i = 0; i < seconds * 10; i++) {
      if (animate)
        await evaluate(
          `byId('progress').value=${Math.round((i / (seconds * 10 - 1)) * 1000)};byId('progress').dispatchEvent(new Event('input'))`,
        );
      const shot = await rpc("Page.captureScreenshot", { format: "png" });
      writeFileSync(
        join(root, String(count++).padStart(4, "0") + ".png"),
        Buffer.from(shot.data, "base64"),
      );
    }
  }
  await frames("1 / Import a profile / Opening and closing have separate styles");
  const document = await rpc("DOM.getDocument");
  const input = await rpc("DOM.querySelector", {
    nodeId: document.root.nodeId,
    selector: "#import-file",
  });
  await rpc("DOM.setFileInputFiles", {
    nodeId: input.nodeId,
    files: [join(projectRoot, "examples/profiles/burst-and-drift.json")],
  });
  for (let attempt = 0; attempt < 50; attempt++) {
    if (await evaluate("byId('status').textContent.startsWith('Imported Burst and Drift')")) break;
    await delay(100);
  }
  assert.equal(await evaluate("effectDocument().kind"), "profile");
  await frames("Imported Burst and Drift / Explosion opens · Dust Drift closes");
  await evaluate(
    "byId('action').value='close';byId('action').dispatchEvent(new Event('change'));byId('pin').click();byId('advanced').click()",
  );
  await frames("2 / Edit Close, pin A and show advanced controls");
  await evaluate(
    "byId('pixel_wind').value='right';byId('pixel_wind').dispatchEvent(new Event('input'));byId('pixel_wind').scrollIntoView({block:'center'})",
  );
  assert.equal(await evaluate("byId('pixel_wind').getBoundingClientRect().height>0"), true);
  await frames("3 / Set Dust wind to Right / Only closing changes", 2, true);
  await evaluate(
    "byId('progress').value=500;byId('progress').dispatchEvent(new Event('input'));byId('compare').click()",
  );
  await frames("4 / Show A / Compare original wind at the same progress");
  await evaluate("byId('compare').click()");
  await frames("Show B / return to the edited closing effect");
  await evaluate("byId('undo').click()");
  assert.equal(await evaluate("effectDocument().actions.close.pixel_wind"), "up");
  await frames("5 / Undo restores Up / Redo recovers Right", 1);
  await evaluate(
    "byId('redo').click();byId('editor-panel').scrollTop=0;byId('name').value='Sideways Drift';byId('name').dispatchEvent(new Event('change'))",
  );
  await frames("6 / Export JSON and Niri config / Resize preserves desktop settings");
  const expected = await evaluate("effectDocument()");
  assert.equal(expected.actions.close.pixel_wind, "right");
  assert.equal(expected.actions.open.family, "fragments");
  assert.equal(expected.actions.resize, null);
  await evaluate("byId('export').click();byId('kdl').click()");
  await delay(300);
  const { readdirSync } = await import("node:fs");
  const exported = readdirSync(root).find((name) => name.endsWith(".json"));
  const kdl = readdirSync(root).find((name) => name.endsWith(".kdl"));
  assert(exported && kdl, "both actual download buttons produced files");
  assert.deepEqual(JSON.parse(readFileSync(join(root, exported))), expected);
  assert.doesNotMatch(readFileSync(join(root, kdl), "utf8"), /window-resize/);
  execFileSync("niri", ["validate", "-c", join(root, kdl)]);
  await frames("Saved files are ready to review / Preview and export do not activate effects", 2);
  const destination = "docs/gifs/workflow-studio-profile.gif";
  execFileSync("ffmpeg", [
    "-v",
    "error",
    "-y",
    "-framerate",
    "10",
    "-i",
    join(root, "%04d.png"),
    "-filter_complex",
    "scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=none",
    "-loop",
    "0",
    destination,
  ]);
  const path = "docs/gifs/scenario-manifest.json";
  const { existsSync, statSync } = await import("node:fs");
  const manifest = existsSync(path) ? JSON.parse(readFileSync(path)) : { clips: [] };
  manifest.clips = manifest.clips.filter((clip) => clip.name !== "workflow-studio-profile");
  manifest.clips.push({
    name: "workflow-studio-profile",
    file: destination,
    bytes: statSync(destination).size,
    backend: "actual offline Studio UI / synthetic WebGL texture",
    sources: Object.fromEntries(
      [
        "examples/profiles/burst-and-drift.json",
        "niri_fx/effect-core.js",
        "niri_fx/pointer-preview.js",
        "niri_fx/preview.py",
        "niri_fx/combo-preview.js",
        "niri_fx/library.js",
        "niri_fx/studio.js",
        "niri_fx/preview.html",
        "niri_fx/studio.css",
        "scripts/record-studio-workflow.mjs",
      ].map((path) => [path, createHash("sha256").update(readFileSync(path)).digest("hex")]),
    ),
    fps: 10,
    frames: count,
    checks: [
      "file import",
      "independent close edit",
      "visible advanced wind control",
      "A/B",
      "undo/redo",
      "actual JSON and KDL downloads",
      "stock Niri validation",
      "resize absent",
    ],
  });
  writeFileSync(path, JSON.stringify(manifest, null, 2) + "\n");
  console.log(`PASS: Studio workflow and downloads; ${count} frames. Evidence: ${root}`);
} finally {
  await browser.close();
}
