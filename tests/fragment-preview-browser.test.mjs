import assert from "node:assert/strict";
import test from "node:test";
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { pathToFileURL } from "node:url";
import { launchBrowser } from "../scripts/lib/browser.mjs";

const source = readFileSync(new URL("../niri_fx/fragment-preview.js", import.meta.url), "utf8"),
  reference = JSON.parse(
    readFileSync(new URL("./fixtures/fragment-native-reference.json", import.meta.url), "utf8"),
  );
async function renderer(work) {
  const directory = mkdtempSync(join(tmpdir(), "nirifx-fragment-render-")),
    page = join(directory, "preview.html");
  writeFileSync(
    page,
    `<!doctype html><html><body><canvas id="stage" width="1000" height="760"></canvas><script>${source}</script><script>
    const texture=document.createElement('canvas');texture.width=600;texture.height=380;
    const ctx=texture.getContext('2d');ctx.fillStyle='#214256';ctx.fillRect(0,0,600,380);
    ctx.clearRect(0,0,18,18);ctx.fillStyle='#7fddb6';ctx.fillRect(18,18,260,130);
    ctx.fillStyle='rgba(230,177,241,0.6)';ctx.fillRect(300,185,260,170);
    window.stage=document.getElementById('stage');window.renderer=createFragmentRenderer(stage,texture);
    window.pixels=()=>{const gl=stage.getContext('webgl'),pixels=new Uint8Array(stage.width*stage.height*4);gl.readPixels(0,0,stage.width,stage.height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);let hash=2166136261,opaque=0;for(let i=0;i<pixels.length;i++){hash=Math.imul(hash^pixels[i],16777619);if(i%4===3&&pixels[i])opaque++;}return {hash,opaque,error:gl.getError()};};
    </script></body></html>`,
  );
  const browser = await launchBrowser();
  try {
    await browser.navigate(pathToFileURL(page).href, {
      width: 1100,
      height: 900,
      readySelector: "#stage",
    });
    await work(browser);
  } finally {
    await browser.close();
    rmSync(directory, { recursive: true, force: true });
  }
}

test("native fragment mesh renders press, delayed world pieces, reversal and exact reconstruction", async () => {
  await renderer(async (browser) => {
    for (const name of ["gentle", "tear", "cascade"]) {
      const trace = reference.cases.find((item) => item.name.startsWith(name + "-"));
      await browser.evaluate(
        `window.motion=createFragmentMotion(${JSON.stringify(trace.config)},{particles:${trace.particles}});renderer.draw(motion.sample(0));`,
      );
      const intact = await browser.evaluate("pixels()");
      assert(intact.opaque > 220000);
      assert.equal(intact.error, 0);
      await browser.evaluate("motion.grab([0.2,0.2],0);renderer.draw(motion.sample(200));");
      const pressed = await browser.evaluate("pixels()");
      assert.notEqual(pressed.hash, intact.hash);
      const lag = await browser.evaluate(
        `motion.push([130,30],200);{const sample=motion.sample(216);renderer.draw(sample);sample.cells.filter(cell=>cell.pin_weight===0).map(cell=>cell.translation[0]);}`,
      );
      assert(
        lag.some((value) => value < -80),
        "distant pieces retain their world positions",
      );
      const moved = await browser.evaluate("pixels()");
      assert.notEqual(moved.hash, pressed.hash);
      assert.equal(moved.error, 0);
      await browser.evaluate(
        "motion.push([-210,-30],232);renderer.draw(motion.sample(248));motion.release(248)",
      );
      const reversed = await browser.evaluate("pixels()");
      assert.notEqual(reversed.hash, moved.hash);
      await browser.evaluate(
        `renderer.draw(motion.sample(${248 + trace.config.release_ms}),{offset:[0,0]})`,
      );
      assert.deepEqual(
        await browser.evaluate("pixels()"),
        intact,
        "release recovers exact source pixels without cell seams",
      );
    }
    await browser.evaluate("renderer.destroy();renderer.destroy()");
    assert.equal(
      await browser.evaluate(
        "(()=>{try{renderer.draw(motion.sample(9000));return false;}catch(error){return error.message.includes('unavailable')}})()",
      ),
      true,
    );
  });
});

test("custom fragment responses render their rotation and tilt without unsupported shape approximation", async () => {
  await renderer(async (browser) => {
    for (const trace of reference.cases.filter((item) => item.name.endsWith("custom-extremes"))) {
      await browser.evaluate(
        `window.motion=createFragmentMotion(${JSON.stringify(trace.config)},{particles:${trace.particles}});motion.grab([0.7,0.7],0);motion.push([140,-80],100);renderer.draw(motion.sample(300));`,
      );
      const pixels = await browser.evaluate("pixels()");
      assert(pixels.opaque > 10000);
      assert.equal(pixels.error, 0);
    }
  });
});
