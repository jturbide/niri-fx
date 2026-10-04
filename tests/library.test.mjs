import assert from "node:assert/strict";
import { test } from "node:test";
import { execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { launchBrowser, projectRoot } from "../scripts/lib/browser.mjs";

test("library combines supported actions, preserves edits and saves offline without activation", async () => {
  const html = execFileSync(
    "python3",
    [
      "-c",
      'from niri_fx.preview import preview_document; from niri_fx.presets import PRESETS; print(preview_document(PRESETS["balanced"], hosted=True))',
    ],
    { cwd: projectRoot, encoding: "utf8", maxBuffer: 4 * 1024 * 1024 },
  );
  const requests = [];
  const server = createServer((request, response) => {
    requests.push(request.url);
    response.writeHead(200, { "Content-Type": "text/html" });
    response.end(html);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const url = `http://127.0.0.1:${server.address().port}/studio/`;
  const browser = await launchBrowser();
  try {
    await browser.navigate(url);
    const evaluate = browser.evaluate;
    assert.equal(await evaluate("document.documentElement.dataset.workspace"), "library");
    assert.equal(await evaluate('byId("activation-controls").hidden'), true);
    assert.equal(await evaluate('getComputedStyle(byId("save-target")).display'), "none");
    assert.equal(await evaluate("effectDocument().effect.resize"), false);
    await evaluate('document.querySelector("[data-style=fragments-motion]").click()');
    assert.equal(await evaluate("effectDocument().actions.resize"), null);
    await evaluate(
      'byId("combo-close").value="frost-vanish";byId("combo-close").dispatchEvent(new Event("change"))',
    );
    assert.equal(await evaluate("effectDocument().actions.open.fragment_mix"), 0.5);
    assert.equal(await evaluate("effectDocument().actions.close.family"), "dissolve");
    assert.equal(await evaluate('byId("combo-mode").value'), "mixed");
    await evaluate(
      'byId("combo-resize").value="spring-wobble";byId("combo-resize").dispatchEvent(new Event("change"));byId("combo-movement").value="fragment-wake";byId("combo-movement").dispatchEvent(new Event("change"))',
    );
    const combo = await evaluate("effectDocument()");
    assert.equal(combo.actions.resize.family, "elastic");
    assert.equal(combo.actions.movement.family, "fragments");
    assert.equal(await evaluate('kdlDocument().includes("window-movement")'), false);
    assert.equal(await evaluate('kdlDocument().includes("window-resize")'), true);
    assert.equal(
      await evaluate('Array.from(byId("combo-resize").options).some(o=>o.value==="frost-vanish")'),
      false,
    );
    await evaluate(
      'byId("combo-mode").value="same";byId("combo-mode").dispatchEvent(new Event("change"))',
    );
    const same = await evaluate("effectDocument()");
    for (const action of ["close", "resize", "movement"])
      assert.deepEqual(same.actions[action], same.actions.open);
    await evaluate('byId("undo").click()');
    assert.deepEqual(await evaluate("effectDocument()"), combo);
    await evaluate(
      'byId("show-editor").click();byId("spin").value=210;byId("spin").dispatchEvent(new Event("input"));byId("show-library").click()',
    );
    assert.equal(await evaluate('byId("combo-movement").value'), "custom");
    assert.equal(await evaluate("effectDocument().actions.movement.spin"), 210);
    await evaluate(
      'byId("combo-name").value="Night Motion";byId("combo-name").dispatchEvent(new Event("change"));byId("store-profile").click()',
    );
    await evaluate("new Promise(resolve=>setTimeout(resolve,100))");
    await browser.navigate(url);
    await evaluate(
      'byId("library-collection").value="customs";byId("library-collection").dispatchEvent(new Event("change"))',
    );
    assert.equal(
      await evaluate(
        'document.querySelector("[data-style=custom-night-motion]").textContent.includes("Night Motion")',
      ),
      true,
    );
    await evaluate('document.querySelector("[data-style=custom-night-motion]").click()');
    assert.equal(await evaluate("effectDocument().actions.movement.spin"), 210);
    await evaluate(
      'byId("combo-mode").value="same";byId("combo-mode").dispatchEvent(new Event("change"));byId("combo-same").value="frost-vanish";byId("combo-same").dispatchEvent(new Event("change"))',
    );
    const unsupported = await evaluate("effectDocument()");
    assert.equal(unsupported.actions.resize, null);
    assert.equal(unsupported.actions.movement, null);
    assert.deepEqual(unsupported.actions.open, unsupported.actions.close);
    assert(requests.every((path) => path === "/studio/" || path === "/favicon.ico"));
    assert.equal(await evaluate('byId("error").textContent'), "");
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
});
