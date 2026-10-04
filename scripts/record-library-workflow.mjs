// Record the actual library/combo controls and downloads on synthetic content.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync, statSync, renameSync } from "node:fs";
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
    `const style=document.createElement('style');style.textContent='canvas{max-height:470px;min-height:0}';document.head.append(style);const banner=document.createElement('div');banner.id='recording-step';banner.style.cssText='position:fixed;bottom:0;left:0;right:0;padding:14px 24px;background:#172434;color:#e4efff;font:600 19px system-ui;z-index:100';document.body.append(banner);seed=.43;`,
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
  async function comboFrames(label) {
    await evaluate(`byId('recording-step').textContent=${JSON.stringify(label)}`);
    const before = await evaluate(
      "({document:effectDocument(),history:editHistory,historyIndex,seed})",
    );
    const plan = await evaluate(`(() => {
      byId('preview-combo').click();
      if(!window.niriFxComboPreview?.active)throw new Error('Combo button did not start playback');
      window.niriFxComboPreview.seek(0);
      return window.niriFxComboPreview.currentPlan;
    })()`);
    const total = Math.ceil((plan.totalMs * 20) / 1000) + 1;
    for (let index = 0; index < total; index++) {
      const elapsed = Math.min(plan.totalMs, (index * 1000) / 20);
      await evaluate(`window.niriFxComboPreview.seek(${elapsed})`);
      const shot = await rpc("Page.captureScreenshot", { format: "png" });
      writeFileSync(
        join(root, String(count++).padStart(4, "0") + ".png"),
        Buffer.from(shot.data, "base64"),
      );
    }
    assert.equal(await evaluate("window.niriFxComboPreview.active"), false);
    assert.deepEqual(
      await evaluate("({document:effectDocument(),history:editHistory,historyIndex,seed})"),
      before,
    );
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
  await comboFrames("4 / Preview your opening, resize and closing styles together");
  await frames("Preview complete / Your combo and active desktop settings stay the same", 1);
  await evaluate(
    `byId('combo-pointer').value='gentle';byId('combo-pointer').dispatchEvent(new Event('change'));byId('progress').value=0;byId('progress').dispatchEvent(new Event('input'));byId('library-panel').scrollTop+=byId('pointer-settings').getBoundingClientRect().top-byId('library-panel').getBoundingClientRect().top-80`,
  );
  await frames("5 / Choose pointer drag / Live use requires the native extension", 1.25);
  await evaluate(
    `byId('pointer-tuning').open=true;byId('pointer-strength').value=.75;byId('pointer-strength').dispatchEvent(new Event('change'));byId('library-panel').scrollTop+=byId('pointer-settings').getBoundingClientRect().top-byId('library-panel').getBoundingClientRect().top-80`,
  );
  const pointerDocument = await evaluate("effectDocument()");
  assert.deepEqual(pointerDocument.pointer, { strength: 0.75, damping: 85, frequency: 10 });
  await frames("Customize the spring / Try pointer drag to preview the response", 1.25);
  await comboFrames("Preview pointer drag and release together with your combo");
  await evaluate(`byId('export').click();byId('kdl').click();byId('pointer-kdl').click()`);
  await frames("JSON keeps pointer settings / Stock config leaves them out", 1.25);
  assert.deepEqual(
    JSON.parse(readFileSync(join(root, "nirifx-preset.json"))).pointer,
    pointerDocument.pointer,
  );
  assert.doesNotMatch(readFileSync(join(root, "nirifx.kdl"), "utf8"), /pointer-wobble/);
  assert.match(readFileSync(join(root, "nirifx-experimental.kdl"), "utf8"), /pointer-wobble/);
  execFileSync("niri", ["validate", "-c", join(root, "nirifx.kdl")]);
  // Retain the actual first downloads as evidence without affecting the later
  // save/copy/rename sequence or Chrome's duplicate-filename behavior.
  renameSync(join(root, "nirifx-preset.json"), join(root, "pointer-profile.json"));
  renameSync(join(root, "nirifx.kdl"), join(root, "pointer-stock.kdl"));
  await evaluate(
    `byId('combo-mode').value='same';byId('combo-mode').dispatchEvent(new Event('change'))`,
  );
  assert.deepEqual(await evaluate("effectDocument().pointer"), pointerDocument.pointer);
  await frames("6 / Share one window style / Pointer settings stay with the combo", 2, true);
  await evaluate(
    `byId('combo-pointer').value='';byId('combo-pointer').dispatchEvent(new Event('change'));byId('pointer-tuning').open=false;byId('library-panel').scrollTop=byId('combo-actions').offsetTop-byId('library-panel').offsetTop-130`,
  );
  assert.equal(await evaluate('Object.hasOwn(effectDocument(), "pointer")'), false);
  await frames("Use desktop settings / Leave pointer behavior unchanged", 0.75);
  await evaluate(
    `byId('combo-close').value='frost-vanish';byId('combo-close').dispatchEvent(new Event('change'));byId('combo-resize').value='';byId('combo-resize').dispatchEvent(new Event('change'));byId('combo-name').value='Night Motion';byId('combo-name').dispatchEvent(new Event('change'));byId('store-profile').click()`,
  );
  await frames("7 / Name your combo before saving", 1);
  await evaluate(`byId('profile-confirm').click()`);
  await evaluate("byId('progress').value=0;byId('progress').dispatchEvent(new Event('input'))");
  await evaluate("byId('store-profile').scrollIntoView({block:'center'})");
  await frames("Saved to My profiles / Your active effects stay the same", 1.5);
  const expected = await evaluate("effectDocument()");
  assert.equal(expected.actions.open.family, "fragments");
  assert.equal(expected.actions.close.family, "dissolve");
  assert.equal(expected.actions.resize, null);
  await evaluate(
    `byId('library-panel').scrollTop=0;byId('library-collection').value='customs';byId('library-collection').dispatchEvent(new Event('change'));byId('copy-profile').click()`,
  );
  await frames("8 / Save a copy to try another variation", 1.5);
  await evaluate(`byId('profile-confirm').click()`);
  await frames("The original stays in My profiles", 1);
  await evaluate(
    `byId('rename-profile').click();byId('profile-save-name').value='Night Motion alternate';byId('profile-save-name').dispatchEvent(new Event('input'))`,
  );
  await frames("9 / Give the copy a clearer name", 1.5);
  await evaluate(`byId('profile-confirm').click()`);
  await frames("Renamed / Active effects keep their original name", 1);
  await evaluate(`byId('remove-profile').click()`);
  await frames("10 / Remove the Library copy when it is no longer needed", 1.5);
  await evaluate(`byId('profile-confirm').click()`);
  await frames("Removed from My profiles / The original remains", 1);
  await evaluate(`document.querySelector('[data-style=custom-night-motion]').click()`);
  await evaluate(`byId('export').click();byId('kdl').click()`);
  await frames("11 / Export editable JSON and stock Niri config", 1.5);
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
      [
        "niri_fx/library.js",
        "niri_fx/pointer.py",
        "niri_fx/pointer-preview.js",
        "niri_fx/preview.py",
        "niri_fx/effect-core.js",
        "niri_fx/combo-preview.js",
        "niri_fx/studio.js",
        "niri_fx/preview.html",
        "niri_fx/studio.css",
        "scripts/record-library-workflow.mjs",
      ].map((path) => [path, createHash("sha256").update(readFileSync(path)).digest("hex")]),
    ),
    checks: [
      "recommended selection",
      "independent open/close",
      "resize selection",
      "actual Preview combo button",
      "complete action-specific open/resize/close cycle",
      "stable seed and unchanged document/history",
      "shared style",
      "explicit pointer preset and bounded custom controls",
      "pointer metadata survives shared window styles and JSON export",
      "stock KDL omits pointer while experimental export includes it",
      "pointer restored to inherited desktop settings",
      "saved profile",
      "explicit save confirmation",
      "copy and rename",
      "remove Library copy only",
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
