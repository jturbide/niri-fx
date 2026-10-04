import assert from "node:assert/strict";
import { test } from "node:test";
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { pathToFileURL } from "node:url";
import { launchBrowser, projectRoot } from "../scripts/lib/browser.mjs";

async function studio(work) {
  const root = mkdtempSync(join(tmpdir(), "nirifx-pointer-preview-"));
  const page = join(root, "studio.html");
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
    await browser.evaluate(`window.pointerClock=1000;performance.now=()=>pointerClock;
      window.pointerFrames=new Map();window.pointerFrameId=0;
      window.requestAnimationFrame=callback=>{pointerFrames.set(++pointerFrameId,callback);return pointerFrameId};
      window.cancelAnimationFrame=id=>pointerFrames.delete(id);
      window.pointerPixels=()=>{const c=byId('stage'),g=c.getContext('webgl'),p=new Uint8Array(c.width*c.height*4);g.readPixels(0,0,c.width,c.height,g.RGBA,g.UNSIGNED_BYTE,p);let h=2166136261,opaque=0;for(let i=0;i<p.length;i++){h=Math.imul(h^p[i],16777619);if(i%4===3&&p[i])opaque++;}return {hash:h,opaque}};
      byId('stage').addEventListener('pointerdown',event=>window.testPointerId=event.pointerId);`);
    await work(browser);
  } finally {
    await browser.close();
    rmSync(root, { recursive: true, force: true });
  }
}
const snapshot = (browser) =>
  browser.evaluate(
    "({document:effectDocument(),history:editHistory,index:historyIndex,mode,progress,seed,action:editingAction})",
  );
const state = (browser) => browser.evaluate("niriFxPointerPreview.snapshot()");
const advance = (browser, ms) =>
  browser.evaluate(
    `pointerClock+=${ms};{const queued=[...pointerFrames.values()];pointerFrames.clear();queued.forEach(callback=>callback(pointerClock))}`,
  );
const choose = (browser, id = "rubber-sheet") =>
  browser.evaluate(
    `byId('combo-pointer').value=${JSON.stringify(id)};byId('combo-pointer').dispatchEvent(new Event('change'))`,
  );
async function mouse(browser, type, x, y, pressed = false) {
  const point = await browser.evaluate(
    `(()=>{const c=byId('stage'),r=c.getBoundingClientRect(),s=Math.min(c.clientWidth/c.width,c.clientHeight/c.height);return {x:r.left+c.clientLeft+(c.clientWidth-c.width*s)/2+${x}*s,y:r.top+c.clientTop+(c.clientHeight-c.height*s)/2+${y}*s}})()`,
  );
  await browser.rpc("Input.dispatchMouseEvent", {
    type,
    ...point,
    button: type === "mouseMoved" && !pressed ? "none" : "left",
    buttons: pressed ? 1 : 0,
    ...(type === "mouseMoved" ? {} : { clickCount: 1 }),
  });
}
async function start(browser) {
  await browser.evaluate("byId('try-pointer').click()");
  assert.equal((await state(browser)).active, true);
  assert.equal(await browser.evaluate("document.documentElement.dataset.shaderStatus"), "ready");
}

test("pointer drag renders deformation, settles without moving geometry and preserves the document", async () => {
  await studio(async (browser) => {
    assert.equal(await browser.evaluate("byId('try-pointer').disabled"), true);
    await choose(browser, "disabled");
    assert.equal(await browser.evaluate("byId('try-pointer').disabled"), true);
    await choose(browser);
    const before = await snapshot(browser);
    await start(browser);
    const intact = await browser.evaluate("pointerPixels()");
    assert(intact.opaque > 200000);
    await mouse(browser, "mouseMoved", 500, 225);
    await mouse(browser, "mousePressed", 500, 225, true);
    await advance(browser, 16);
    await mouse(browser, "mouseMoved", 590, 265, true);
    await advance(browser, 16);
    const dragged = await state(browser);
    assert.equal(dragged.captured, true);
    assert(Math.abs(dragged.offset[0] - 90) < 2);
    assert(Math.abs(dragged.offset[1] - 40) < 2);
    assert(Math.hypot(...dragged.frame.pointer.deformation) > 0);
    assert.notEqual((await browser.evaluate("pointerPixels()")).hash, intact.hash);
    await advance(browser, 16);
    await mouse(browser, "mouseMoved", 550, 235, true);
    await mouse(browser, "mouseReleased", 550, 235);
    const released = await state(browser);
    const releasedPixels = await browser.evaluate("pointerPixels()");
    assert.equal(released.captured, false);
    assert.equal(released.scheduled, true);
    await advance(browser, 2050);
    const settled = await state(browser);
    assert.deepEqual(settled.offset, released.offset);
    assert.deepEqual(settled.frame.pointer.deformation, [0, 0]);
    assert.equal(settled.scheduled, false);
    assert.notEqual((await browser.evaluate("pointerPixels()")).hash, releasedPixels.hash);
    assert.deepEqual(await snapshot(browser), before);
    await browser.evaluate("byId('pointer-stop').click()");
    assert.equal((await state(browser)).active, false);
    assert.equal(await browser.evaluate("pointerFrames.size"), 0);
    assert.deepEqual(await snapshot(browser), before);
  });
});

test("pointer capture, reduced motion, keyboard demo and cancellation leave no stale playback", async () => {
  await studio(async (browser) => {
    await choose(browser);
    const before = await snapshot(browser);
    await start(browser);
    await mouse(browser, "mouseMoved", 500, 225);
    await mouse(browser, "mousePressed", 500, 225, true);
    await advance(browser, 16);
    await mouse(browser, "mouseMoved", 990, 740, true);
    const bounded = await state(browser);
    assert(Math.abs(bounded.offset[0]) <= 134 && Math.abs(bounded.offset[1]) <= 124);
    await browser.evaluate("byId('stage').releasePointerCapture(testPointerId)");
    await mouse(browser, "mouseMoved", 988, 738, true);
    assert.equal((await state(browser)).active, false);
    assert.equal(await browser.evaluate("pointerFrames.size"), 0);
    await mouse(browser, "mouseReleased", 990, 740);
    await start(browser);
    await browser.evaluate(
      "byId('reduced-motion').checked=true;byId('reduced-motion').dispatchEvent(new Event('change'))",
    );
    await mouse(browser, "mouseMoved", 500, 225);
    await mouse(browser, "mousePressed", 500, 225, true);
    await advance(browser, 16);
    await mouse(browser, "mouseMoved", 560, 245, true);
    const reduced = await state(browser);
    assert.equal(reduced.captured, true);
    assert.deepEqual(reduced.frame.pointer.deformation, [0, 0]);
    assert.equal(reduced.scheduled, false);
    await mouse(browser, "mouseReleased", 560, 245);
    await browser.evaluate("byId('pointer-demo').click()");
    assert.equal((await state(browser)).demo, false);
    assert.equal(await browser.evaluate("pointerFrames.size"), 0);
    await browser.evaluate(
      "byId('reduced-motion').checked=false;byId('reduced-motion').dispatchEvent(new Event('change'));byId('pointer-demo').focus()",
    );
    await browser.rpc("Input.dispatchKeyEvent", {
      type: "keyDown",
      key: "Enter",
      code: "Enter",
      windowsVirtualKeyCode: 13,
      text: "\r",
      unmodifiedText: "\r",
    });
    await browser.rpc("Input.dispatchKeyEvent", {
      type: "keyUp",
      key: "Enter",
      code: "Enter",
      windowsVirtualKeyCode: 13,
      text: "\r",
      unmodifiedText: "\r",
    });
    assert.equal((await state(browser)).demo, true);
    await advance(browser, 600);
    assert(Math.hypot(...(await state(browser)).frame.pointer.deformation) > 0);
    assert.equal(await browser.evaluate("document.activeElement.id"), "pointer-demo");
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
    assert.equal(await browser.evaluate("pointerFrames.size"), 0);
    await start(browser);
    await browser.evaluate("byId('pointer-demo').click();byId('show-editor').click()");
    assert.equal((await state(browser)).active, false);
    assert.equal(await browser.evaluate("pointerFrames.size"), 0);
    await advance(browser, 4000);
    assert.deepEqual(await snapshot(browser), before);
    await start(browser);
    await mouse(browser, "mouseMoved", 500, 225);
    await mouse(browser, "mousePressed", 500, 225, true);
    await browser.evaluate(
      "byId('stage').dispatchEvent(new PointerEvent('pointercancel',{pointerId:testPointerId}))",
    );
    assert.equal((await state(browser)).captured, false);
    assert.equal((await state(browser)).active, false);
    await mouse(browser, "mouseReleased", 500, 225);
    await start(browser);
    await browser.evaluate(
      "Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'))",
    );
    assert.equal((await state(browser)).active, false);
    assert.equal(await browser.evaluate("pointerFrames.size"), 0);
  });
});

test("pointer anchors match letterboxed pixels and active regrabs retain the native spring", async () => {
  await studio(async (browser) => {
    await choose(browser);
    await browser.evaluate(
      "byId('stage').style.cssText='width:800px;height:380px;max-height:none;min-height:0'",
    );
    await start(browser);
    // Independently specified geometry: a 1000x760 bitmap fits this 800x380 CSS
    // content box at 1/2 scale, leaving 150 CSS pixels on each horizontal side.
    const box = await browser.evaluate(
      "(()=>{const c=byId('stage'),r=c.getBoundingClientRect();return {left:r.left+c.clientLeft,top:r.top+c.clientTop,width:c.clientWidth,height:c.clientHeight}})()",
    );
    assert.equal(box.width, 800);
    assert.equal(box.height, 380);
    const point = (anchor, offset = [0, 0]) => ({
      x: box.left + 150 + (200 + anchor[0] * 600 + offset[0]) / 2,
      y: box.top + (190 + anchor[1] * 380 + offset[1]) / 2,
    });
    const send = (type, p, pressed = false) =>
      browser.rpc("Input.dispatchMouseEvent", {
        type,
        ...p,
        button: type === "mouseMoved" && !pressed ? "none" : "left",
        buttons: pressed ? 1 : 0,
        ...(type === "mouseMoved" ? {} : { clickCount: 1 }),
      });
    const bottom = point([0.95, 0.9]);
    await send("mouseMoved", bottom);
    await send("mousePressed", bottom, true);
    let current = await state(browser);
    assert(Math.abs(current.frame.pointer.anchor[0] - 0.95) < 0.002);
    assert(Math.abs(current.frame.pointer.anchor[1] - 0.9) < 0.002);
    await advance(browser, 16);
    const moved = { x: bottom.x + 25, y: bottom.y - 10 };
    await send("mouseMoved", moved, true);
    await advance(browser, 16);
    current = await state(browser);
    assert(Math.abs(current.offset[0] - 50) < 1);
    assert(Math.abs(current.offset[1] + 20) < 1);
    await send("mouseReleased", moved);
    const released = await state(browser);
    assert(Math.hypot(...released.frame.pointer.deformation) > 0);
    const corner = point([0.1, 0.2], released.offset);
    await send("mouseMoved", corner);
    await send("mousePressed", corner, true);
    const regrabbed = await state(browser);
    assert.deepEqual(regrabbed.offset, released.offset);
    assert.deepEqual(regrabbed.frame.pointer.deformation, released.frame.pointer.deformation);
    assert.deepEqual(regrabbed.frame.pointer.anchor, released.frame.pointer.anchor);
    assert.equal(regrabbed.frame.pointer.released, false);
    await send("mouseReleased", corner);
    await advance(browser, 2050);
    await send("mousePressed", corner, true);
    current = await state(browser);
    assert(Math.abs(current.frame.pointer.anchor[0] - 0.1) < 0.002);
    assert(Math.abs(current.frame.pointer.anchor[1] - 0.2) < 0.002);
    await send("mouseReleased", corner);
    for (const event of ["blur", "resize"]) {
      await browser.evaluate(`window.dispatchEvent(new Event(${JSON.stringify(event)}))`);
      assert.equal((await state(browser)).active, false);
      assert.equal(await browser.evaluate("pointerFrames.size"), 0);
      await start(browser);
    }
    await browser.evaluate("niriFxBenchmark({width:0}).catch(()=>{})");
    assert.equal((await state(browser)).active, false);
    await browser.evaluate(
      "byId('preview-combo').click();niriFxBenchmark({width:0}).catch(()=>{})",
    );
    assert.equal(await browser.evaluate("niriFxComboPreview.active"), false);
    assert.equal(await browser.evaluate("pointerFrames.size"), 0);
    await start(browser);
    await choose(browser, "gentle");
    assert.equal((await state(browser)).active, false);
    assert.equal(await browser.evaluate("pointerFrames.size"), 0);
  });
});
