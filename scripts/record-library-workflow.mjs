// Record the actual library/combo controls and downloads on synthetic content.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { launchBrowser, projectRoot } from "./lib/browser.mjs";

process.chdir(projectRoot);
mkdirSync("artifacts", { recursive: true });
const root = mkdtempSync(join(projectRoot, "artifacts/library-workflow-"));
const page = join(root, "preview.html");
execFileSync("python3", ["-m", "niri_fx", "preview", "--output", page]);
const browser = await launchBrowser();
try {
  await browser.navigate(pathToFileURL(page).href, { width: 1440, height: 1160 });
  const { evaluate, rpc } = browser;
  await rpc("Browser.setDownloadBehavior", { behavior: "allow", downloadPath: root });
  await evaluate(
    `const banner=document.createElement('div');banner.id='recording-step';banner.style.cssText='position:fixed;bottom:0;left:0;right:0;padding:14px 24px;background:#172434;color:#e4efff;font:600 19px system-ui;z-index:100';document.body.append(banner);seed=.43;`,
  );
  let count = 0;
  async function frames(label, seconds = 1.5, animate = false) {
    await evaluate(`byId('recording-step').textContent=${JSON.stringify(label)}`);
    for (let i = 0; i < seconds * 20; i++) {
      if (animate)
        await evaluate(
          `byId('progress').value=${Math.round((i / (seconds * 20 - 1)) * 1000)};byId('progress').dispatchEvent(new Event('input'))`,
        );
      const shot = await rpc("Page.captureScreenshot", { format: "png" });
      writeFileSync(
        join(root, String(count++).padStart(4, "0") + ".png"),
        Buffer.from(shot.data, "base64"),
      );
    }
  }
  await frames("1 / Start with a recommended look");
  await evaluate(`document.querySelector('[data-style=fragments-motion]').click()`);
  await frames("Fragments Motion / Resize and movement start off", 2, true);
  await evaluate(
    `byId('library-panel').scrollTop=byId('combo-actions').offsetTop-byId('library-panel').offsetTop-130;byId('combo-close').value='frost-vanish';byId('combo-close').dispatchEvent(new Event('change'))`,
  );
  await frames("2 / Keep fragments for opening, choose Frost Vanish for closing", 2, true);
  await evaluate(
    `byId('combo-resize').value='spring-wobble';byId('combo-resize').dispatchEvent(new Event('change'))`,
  );
  await frames("3 / Add resize only when you want it", 2, true);
  await evaluate(
    `byId('combo-mode').value='same';byId('combo-mode').dispatchEvent(new Event('change'))`,
  );
  await frames("4 / Use the same style for every enabled action", 2, true);
  await evaluate(
    `byId('combo-close').value='frost-vanish';byId('combo-close').dispatchEvent(new Event('change'));byId('combo-resize').value='';byId('combo-resize').dispatchEvent(new Event('change'));byId('combo-name').value='Night Motion';byId('combo-name').dispatchEvent(new Event('change'));byId('store-profile').click()`,
  );
  await evaluate("byId('progress').value=0;byId('progress').dispatchEvent(new Event('input'))");
  await evaluate("byId('store-profile').scrollIntoView({block:'center'})");
  await frames("5 / Save your combo to My profiles", 1.5);
  const expected = await evaluate("effectDocument()");
  assert.equal(expected.actions.open.family, "fragments");
  assert.equal(expected.actions.close.family, "dissolve");
  assert.equal(expected.actions.resize, null);
  await evaluate(`byId('export').click();byId('kdl').click()`);
  await frames("6 / Export editable JSON and stock Niri config", 1.5);
  assert.deepEqual(JSON.parse(readFileSync(join(root, "nirifx-preset.json"))), expected);
  execFileSync("niri", ["validate", "-c", join(root, "nirifx.kdl")]);
  const destination = "docs/gifs/workflow-library.gif";
  execFileSync("ffmpeg", [
    "-y",
    "-loglevel",
    "error",
    "-framerate",
    "20",
    "-i",
    join(root, "%04d.png"),
    "-filter_complex",
    "scale=960:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=none",
    "-loop",
    "0",
    destination,
  ]);
  const path = "docs/gifs/scenario-manifest.json",
    manifest = JSON.parse(readFileSync(path));
  manifest.clips = manifest.clips.filter((clip) => clip.name !== "workflow-library");
  manifest.clips.push({
    name: "workflow-library",
    file: destination,
    bytes: statSync(destination).size,
    backend: "actual offline library UI / synthetic WebGL texture",
    fps: 20,
    frames: count,
    sources: Object.fromEntries(
      ["niri_fx/library.js", "niri_fx/preview.html"].map((path) => [
        path,
        createHash("sha256").update(readFileSync(path)).digest("hex"),
      ]),
    ),
    checks: [
      "recommended selection",
      "independent open/close",
      "resize opt-in",
      "shared style",
      "saved profile",
      "actual JSON and KDL downloads",
      "stock Niri validation",
    ],
  });
  writeFileSync(path, JSON.stringify(manifest, null, 2) + "\n");
  const shot = await rpc("Page.captureScreenshot", { format: "png" });
  writeFileSync(join(root, "review.png"), Buffer.from(shot.data, "base64"));
  console.log(`PASS: library workflow and downloads; ${count} frames. Evidence: ${root}`);
} finally {
  await browser.close();
}
