import assert from "node:assert/strict";
import { test } from "node:test";
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { pathToFileURL } from "node:url";
import { launchBrowser, projectRoot } from "../scripts/lib/browser.mjs";

async function studio(work) {
  const root = mkdtempSync(join(tmpdir(), "nirifx-fragment-controls-")),
    page = join(root, "studio.html");
  writeFileSync(
    page,
    execFileSync(
      "python3",
      [
        "-c",
        'from niri_fx.preview import preview_document; from niri_fx.presets import PRESETS; print(preview_document(PRESETS["balanced"], hosted=True))',
      ],
      { cwd: projectRoot, maxBuffer: 4 * 1024 * 1024 },
    ),
  );
  const browser = await launchBrowser();
  try {
    await browser.navigate(pathToFileURL(page).href + "?breakup=0", { width: 1280, height: 1080 });
    await browser.evaluate(`window.fragmentClock=1000;performance.now=()=>fragmentClock;
      window.fragmentFrames=new Map();window.fragmentFrameId=0;
      window.requestAnimationFrame=callback=>{fragmentFrames.set(++fragmentFrameId,callback);return fragmentFrameId};
      window.cancelAnimationFrame=id=>fragmentFrames.delete(id);
      byId('fragment-stage').addEventListener('pointerdown',event=>window.fragmentPointerId=event.pointerId);`);
    await work(browser);
  } finally {
    await browser.close();
    rmSync(root, { recursive: true, force: true });
  }
}
const state = (browser) => browser.evaluate("niriFxFragmentPreview.snapshot()");
const snapshot = (browser) =>
  browser.evaluate(
    "({document:effectDocument(),history:editHistory,index:historyIndex,mode,progress,seed,action:editingAction})",
  );
const advance = (browser, ms) =>
  browser.evaluate(
    `fragmentClock+=${ms};{const queued=[...fragmentFrames.values()];fragmentFrames.clear();queued.forEach(callback=>callback(fragmentClock))}`,
  );
const choose = (browser, name = "tear") =>
  browser.evaluate(
    `byId('native-fragment-preset').value=${JSON.stringify(name)};byId('native-fragment-preset').dispatchEvent(new Event('change'))`,
  );
async function start(browser) {
  await browser.evaluate("niriFxFragmentPreview.stop();byId('try-fragments').click()");
  assert.equal((await state(browser)).active, true);
  assert.equal(await browser.evaluate("byId('error').textContent"), "");
}
async function mouse(browser, type, x, y, pressed = false) {
  const point = await browser.evaluate(
    `(()=>{const c=byId('fragment-stage'),r=c.getBoundingClientRect(),s=Math.min(c.clientWidth/c.width,c.clientHeight/c.height);return {x:r.left+c.clientLeft+(c.clientWidth-c.width*s)/2+${x}*s,y:r.top+c.clientTop+(c.clientHeight-c.height*s)/2+${y}*s}})()`,
  );
  await browser.rpc("Input.dispatchMouseEvent", {
    type,
    ...point,
    button: type === "mouseMoved" && !pressed ? "none" : "left",
    buttons: pressed ? 1 : 0,
    ...(type === "mouseMoved" ? {} : { clickCount: 1 }),
  });
}
async function capture(browser, name) {
  if (!process.env.NIRIFX_FRAGMENT_CAPTURE) return;
  const directory = join(projectRoot, "artifacts/fragment-preview");
  mkdirSync(directory, { recursive: true });
  const image = await browser.rpc("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
  });
  writeFileSync(join(directory, name + ".png"), Buffer.from(image.data, "base64"));
}

test("Studio continuously drags fragments through press, pause, reversal, regrab and release without changing a recipe", async () => {
  await studio(async (browser) => {
    await choose(browser);
    assert.equal(
      await browser.evaluate(
        "document.querySelector('[data-library-action=movement]').getAttribute('aria-pressed')",
      ),
      "true",
    );
    assert.equal(
      await browser.evaluate("byId('library-heading').textContent"),
      "Choose a move style",
    );
    assert.equal(
      (await state(browser)).active,
      true,
      "choosing a response opens its real gesture demo",
    );
    assert.equal((await state(browser)).demo, true);
    await start(browser);
    const before = await snapshot(browser),
      intact = await state(browser);
    await mouse(browser, "mouseMoved", 330, 270);
    await mouse(browser, "mousePressed", 330, 270, true);
    const initialGrab = await state(browser);
    const grabbedCell = initialGrab.frame.cells.find(
      (cell) =>
        Math.abs(cell.center[0] - 130) <= cell.half_extent[0] &&
        Math.abs(cell.center[1] - 80) <= cell.half_extent[1],
    );
    assert(grabbedCell, "the cursor is covered by a source cell");
    assert.equal(grabbedCell.pin_weight, 1, "the initial grabbed cell is pinned immediately");
    await advance(browser, 200);
    const held = await state(browser);
    assert.equal(held.captured, true);
    assert(held.frame.cells.some((cell) => Math.hypot(...cell.translation) > 2));
    await capture(browser, "press");
    await mouse(browser, "mouseMoved", 450, 300, true);
    const moved = await state(browser);
    assert(Math.abs(moved.offset[0] - 120) < 2);
    assert(Math.abs(moved.offset[1] - 30) < 2);
    const far = held.frame.cells.findIndex(
      (cell) => cell.pin_weight === 0 && cell.center[0] > 550 && cell.center[1] > 320,
    );
    for (let axis = 0; axis < 2; axis++)
      assert(
        Math.abs(
          moved.frame.cells[far].translation[axis] +
            moved.offset[axis] -
            held.frame.cells[far].translation[axis],
        ) < 0.01,
        "far cell stays at its world position on a new target",
      );
    await advance(browser, 120);
    const following = await state(browser);
    assert.notDeepEqual(following.frame.cells, moved.frame.cells);
    await mouse(browser, "mouseMoved", 270, 240, true);
    await advance(browser, 32);
    const reverse = await state(browser);
    assert(reverse.offset[0] < 0);
    assert(reverse.frame.cells.some((cell) => Math.abs(cell.rotation) > 0.001));
    await capture(browser, "reversal");
    await mouse(browser, "mouseReleased", 270, 240);
    const released = await state(browser);
    assert.equal(released.captured, false);
    assert.equal(released.scheduled, true);
    await mouse(browser, "mouseMoved", 430, 390);
    await mouse(browser, "mousePressed", 430, 390, true);
    const regrabbed = await state(browser);
    assert.equal(regrabbed.captured, true);
    for (let index = 0; index < released.frame.cells.length; index++)
      for (const key of ["translation", "rotation", "tilt"])
        assert.deepEqual(
          regrabbed.frame.cells[index][key],
          released.frame.cells[index][key],
          "regrab preserves the current pose",
        );
    await mouse(browser, "mouseReleased", 430, 390);
    await advance(browser, 2000);
    const settled = await state(browser);
    assert.equal(settled.scheduled, false);
    assert.equal(settled.frame.moving, false);
    assert.deepEqual(
      settled.frame.cells.map((cell) => cell.translation),
      intact.frame.cells.map((cell) => cell.translation),
    );
    await capture(browser, "settled");
    assert.deepEqual(await snapshot(browser), before);
    await browser.evaluate("byId('fragment-stop').click()");
    assert.equal((await state(browser)).active, false);
    assert.equal(await browser.evaluate("fragmentFrames.size"), 0);
    assert.deepEqual(await snapshot(browser), before);
  });
});

test("Studio fragment preview respects reduced motion, keyboard control and cancellation", async () => {
  await studio(async (browser) => {
    await choose(browser, "gentle");
    await start(browser);
    const before = await snapshot(browser);
    await browser.evaluate(
      "byId('reduced-motion').checked=true;byId('reduced-motion').dispatchEvent(new Event('change'))",
    );
    await mouse(browser, "mouseMoved", 420, 290);
    await mouse(browser, "mousePressed", 420, 290, true);
    await mouse(browser, "mouseMoved", 470, 310, true);
    await advance(browser, 200);
    let current = await state(browser);
    assert.equal(current.captured, true);
    assert.equal(current.scheduled, false);
    assert(current.frame.cells.every((cell) => cell.translation.every((value) => value === 0)));
    assert(Math.abs(current.offset[0] - 50) < 2);
    await mouse(browser, "mouseReleased", 470, 310);
    await browser.evaluate("byId('fragment-demo').click()");
    assert.equal((await state(browser)).demo, false);
    await browser.evaluate(
      "byId('reduced-motion').checked=false;byId('reduced-motion').dispatchEvent(new Event('change'));byId('fragment-stage').focus()",
    );
    await browser.rpc("Input.dispatchKeyEvent", {
      type: "keyDown",
      key: "Enter",
      code: "Enter",
      windowsVirtualKeyCode: 13,
      text: "\r",
    });
    await browser.rpc("Input.dispatchKeyEvent", {
      type: "keyUp",
      key: "Enter",
      code: "Enter",
      windowsVirtualKeyCode: 13,
    });
    assert.equal((await state(browser)).demo, true);
    await advance(browser, 700);
    assert((await state(browser)).frame.cells.some((cell) => Math.abs(cell.rotation) > 0));
    await browser.rpc("Input.dispatchKeyEvent", {
      type: "keyDown",
      key: "Escape",
      code: "Escape",
      windowsVirtualKeyCode: 27,
    });
    await browser.rpc("Input.dispatchKeyEvent", {
      type: "keyUp",
      key: "Escape",
      code: "Escape",
      windowsVirtualKeyCode: 27,
    });
    assert.equal((await state(browser)).active, false);
    assert.equal(await browser.evaluate("fragmentFrames.size"), 0);
    await start(browser);
    await mouse(browser, "mouseMoved", 420, 290);
    await mouse(browser, "mousePressed", 420, 290, true);
    await browser.evaluate(
      "byId('fragment-stage').dispatchEvent(new PointerEvent('pointercancel',{pointerId:fragmentPointerId}))",
    );
    current = await state(browser);
    assert.equal(current.active, false);
    assert.equal(current.captured, false);
    await mouse(browser, "mouseReleased", 420, 290);
    for (const event of ["blur", "resize"]) {
      await start(browser);
      await browser.evaluate(`window.dispatchEvent(new Event(${JSON.stringify(event)}))`);
      assert.equal((await state(browser)).active, false);
    }
    await start(browser);
    await browser.evaluate("byId('fragment-demo').click();byId('show-editor').click()");
    assert.equal((await state(browser)).active, false);
    assert.equal(await browser.evaluate("fragmentFrames.size"), 0);
    assert.deepEqual(await snapshot(browser), before);
    await start(browser);
    await browser.evaluate("byId('fragment-demo').click()");
    assert.equal((await state(browser)).demo, true);
    await browser.evaluate("niriFxBenchmark({width:0}).catch(()=>{})");
    assert.equal((await state(browser)).active, false);
    assert.equal(await browser.evaluate("fragmentFrames.size"), 0);
    await start(browser);
    await browser.evaluate(
      "Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))",
    );
    assert.equal((await state(browser)).active, false);
  });
});

test("fragment anchors follow letterboxed pixels, lost capture cleans up, and response changes replace playback", async () => {
  await studio(async (browser) => {
    await choose(browser);
    await start(browser);
    await browser.evaluate(
      "byId('fragment-stage').style.cssText='width:800px;height:380px;max-height:none;min-height:0'",
    );
    await mouse(browser, "mouseMoved", 770, 532);
    await mouse(browser, "mousePressed", 770, 532, true);
    let current = await state(browser);
    assert(Math.abs(current.frame.anchor[0] - 0.95) < 0.002);
    assert(Math.abs(current.frame.anchor[1] - 0.9) < 0.002);
    await advance(browser, 32);
    await mouse(browser, "mouseMoved", 730, 512, true);
    current = await state(browser);
    assert(Math.abs(current.offset[0] + 40) < 2);
    assert(Math.abs(current.offset[1] + 20) < 2);
    await browser.evaluate("byId('fragment-stage').releasePointerCapture(fragmentPointerId)");
    await mouse(browser, "mouseMoved", 728, 510, true);
    assert.equal((await state(browser)).active, false);
    assert.equal(await browser.evaluate("fragmentFrames.size"), 0);
    await mouse(browser, "mouseReleased", 728, 510);
    await start(browser);
    await choose(browser, "cascade");
    current = await state(browser);
    assert.equal(current.demo, true);
    assert(current.frame.cells.length > 1200);
    assert.equal(current.offset[0], 0);
    await advance(browser, 4000);
    assert.equal((await state(browser)).demo, false);
    assert.equal((await state(browser)).scheduled, false);
    await browser.evaluate("niriFxFragmentPreview.stop()");
    assert.equal(await browser.evaluate("fragmentFrames.size"), 0);
  });
});
