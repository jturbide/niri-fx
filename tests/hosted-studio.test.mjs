import assert from "node:assert/strict";
import { test } from "node:test";
import { execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { resolve, sep } from "node:path";
import { launchBrowser, projectRoot } from "../scripts/lib/browser.mjs";

test("hosted gallery settings load, edit, share and download without local endpoints", async () => {
  const html = execFileSync(
    "python3",
    [
      "-c",
      'from niri_fx.preview import preview_document; from niri_fx.effects import PRESETS; print(preview_document(PRESETS["balanced"],hosted=True))',
    ],
    { cwd: projectRoot, encoding: "utf8", maxBuffer: 4 * 1024 * 1024 },
  );
  const requests = [];
  const server = createServer((request, response) => {
    const pathname = new URL(request.url, "http://127.0.0.1").pathname;
    requests.push(pathname);
    if (pathname === "/studio/") {
      response.writeHead(200, { "Content-Type": "text/html" });
      response.end(html);
      return;
    }
    const root = resolve(projectRoot, "docs"),
      file = resolve(
        root,
        "." + decodeURIComponent(pathname) + (pathname.endsWith("/") ? "index.html" : ""),
      );
    if (!file.startsWith(root + sep)) {
      response.writeHead(404).end();
      return;
    }
    try {
      const content = readFileSync(file);
      const types = {
        html: "text/html",
        js: "text/javascript",
        css: "text/css",
        json: "application/json",
        webp: "image/webp",
      };
      response.writeHead(200, {
        "Content-Type": types[file.split(".").at(-1)] || "application/octet-stream",
      });
      response.end(content);
    } catch {
      response.writeHead(404).end();
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  let browser;
  try {
    browser = await launchBrowser();
    await browser.navigate(base + "/gallery/?family=hexagons&token=unrelated-query", {
      readySelector: "[data-gallery-ready]",
    });
    assert.equal(
      await browser.evaluate('document.querySelectorAll("article:not([hidden])").length'),
      2,
    );
    await browser.evaluate('document.getElementById("share-view").click()');
    assert.equal(
      await browser.evaluate('document.getElementById("copy-text").value'),
      "https://jturbide.github.io/niri-fx/gallery/?family=hexagons&collection=all",
    );
    const settings = await browser.evaluate(
      `(()=>{const card=document.querySelector('article:not([hidden])');return {url:card.querySelector('[data-studio]').href,json:card.querySelector('[download]').getAttribute('href'),command:card.querySelector('[data-command]').dataset.command};})()`,
    );
    const doc = await (await fetch(base + "/gallery/" + settings.json)).json();
    assert.equal(doc.effect.family, "hexagons");
    assert(settings.command.includes("--custom ./nirifx-preset-hexagon-burst.json"));
    await browser.navigate(base + "/studio/" + new URL(settings.url).hash);
    assert.equal(await browser.evaluate("catalog.connection"), null);
    assert.equal(await browser.evaluate('byId("studio-kind").textContent'), "WEB STUDIO");
    assert.deepEqual(await browser.evaluate("effectDocument()"), doc);
    await browser.evaluate(
      'byId("hex_spin").value=230;byId("hex_spin").dispatchEvent(new Event("input"));seed=.72;draw(.32)',
    );
    const edited = await browser.evaluate("effectDocument()");
    // Deliberately add a session-looking query: sharing must never forward it.
    await browser.evaluate(
      'history.replaceState(null,"","?token=local-fixture-secret");byId("share").click()',
    );
    const shared = await browser.evaluate('byId("share-url").value');
    assert(shared.startsWith("https://jturbide.github.io/niri-fx/studio/#style="));
    assert(!shared.includes("local-fixture-secret"));
    await browser.navigate(base + "/studio/" + new URL(shared).hash);
    assert.deepEqual(await browser.evaluate("effectDocument()"), edited);
    assert.deepEqual(await browser.evaluate("({seed,progress})"), { seed: 0.72, progress: 0.32 });
    // Preserve an explicit resize profile, including which action is being edited.
    await browser.evaluate(
      'byId("independent").click();byId("action").value="resize";byId("action").dispatchEvent(new Event("change"));byId("action-mode").value="style";byId("action-mode").dispatchEvent(new Event("change"));byId("resize-direction").value="shrink";byId("share").click()',
    );
    const profile = await browser.evaluate("effectDocument()"),
      profileLink = await browser.evaluate('byId("share-url").value');
    await browser.navigate(base + "/studio/" + new URL(profileLink).hash);
    assert.deepEqual(await browser.evaluate("effectDocument()"), profile);
    assert.equal(await browser.evaluate("editingAction"), "resize");
    assert.equal(await browser.evaluate("mode"), "resize");
    assert.equal(await browser.evaluate('byId("resize-direction").value'), "shrink");
    await browser.evaluate(
      'byId("action").value="movement";byId("action").dispatchEvent(new Event("change"));byId("action-mode").value="style";byId("action-mode").dispatchEvent(new Event("change"));byId("preset").value="fragment-wake";byId("preset").dispatchEvent(new Event("change"));byId("movement-direction").value="up";byId("share").click()',
    );
    const moving = await browser.evaluate("effectDocument()"),
      movingLink = await browser.evaluate('byId("share-url").value');
    await browser.navigate(base + "/studio/" + new URL(movingLink).hash);
    assert.deepEqual(await browser.evaluate("effectDocument()"), moving);
    assert.equal(await browser.evaluate("editingAction"), "movement");
    assert.equal(await browser.evaluate("mode"), "movement");
    assert.equal(await browser.evaluate('byId("movement-direction").value'), "up");
    assert(!(await browser.evaluate("kdlDocument().includes('window-movement')")));
    for (const fragment of [
      "#style=!bad",
      "#style=" +
        Buffer.from(
          JSON.stringify({ schema: 3, name: "Bad", effect: { family: "pixels", resize: true } }),
        ).toString("base64url"),
    ]) {
      await browser.navigate(base + "/studio/" + fragment);
      assert.match(
        await browser.evaluate('byId("error").textContent'),
        /Cannot open shared settings/,
      );
      assert.equal(await browser.evaluate("parameters.resize"), false);
    }
    await browser.navigate(base + "/studio/?preset=__proto__");
    assert.equal(await browser.evaluate("parameters.family"), "fragments");
    assert.equal(await browser.evaluate('byId("preset").value'), "balanced");
    const beforePairing = await browser.evaluate("effectDocument()");
    await browser.evaluate("document.querySelector('[data-mode=\"resize\"]').click()");
    await browser.evaluate(
      'byId("profile").value="burst-and-drift";byId("profile").dispatchEvent(new Event("change"))',
    );
    const pairing = await browser.evaluate("effectDocument()");
    assert.equal(pairing.kind, "profile");
    assert.equal(pairing.actions.open.family, "fragments");
    assert.equal(pairing.actions.close.family, "pixels");
    assert.equal(pairing.actions.resize, null);
    assert.equal(await browser.evaluate("mode"), "effect");
    assert.equal(await browser.evaluate("editingAction"), "open");
    await browser.evaluate('byId("undo").click()');
    assert.deepEqual(await browser.evaluate("effectDocument()"), beforePairing);
    await browser.evaluate('byId("redo").click();byId("share").click()');
    const pairingLink = await browser.evaluate('byId("share-url").value');
    await browser.navigate(base + "/studio/" + new URL(pairingLink).hash);
    assert.deepEqual(await browser.evaluate("effectDocument()"), pairing);
    // Browser tests use software rendering: a load batch must still refuse to
    // report it as hardware performance, and malformed counts fail explicitly.
    const timing = await browser.evaluate("window.niriFxBenchmark({draws: 4, samples: 10})");
    assert.equal(timing.draws, 4);
    assert.equal(timing.status, "unsupported");
    for (const draws of [0, 9, 1.5])
      await assert.rejects(
        browser.evaluate(`window.niriFxBenchmark({draws: ${draws}})`),
        /Invalid benchmark/,
      );
    assert(!requests.some((path) => ["/save", "/ping", "/preferences"].includes(path)));
  } finally {
    await browser?.close();
    await new Promise((resolve) => server.close(resolve));
  }
});
