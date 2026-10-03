import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import assert from "node:assert/strict";
import { test } from "node:test";
import { pathToFileURL } from "node:url";
import { join } from "node:path";
import { launchBrowser, projectRoot } from "../scripts/lib/browser.mjs";

test("gallery starts paused, filters examples and plays only one animation", async () => {
  const recommended = JSON.parse(
    execFileSync(
      "python3",
      [
        "-c",
        "import json;from niri_fx.catalog import RECOMMENDED;print(json.dumps(list(RECOMMENDED)))",
      ],
      { cwd: projectRoot, encoding: "utf8" },
    ),
  );
  const url = pathToFileURL(join(projectRoot, "docs/gallery/index.html")).href;
  const browser = await launchBrowser();
  try {
    await browser.rpc("Emulation.setEmulatedMedia", {
      features: [{ name: "prefers-reduced-motion", value: "reduce" }],
    });
    await browser.navigate(url, {
      width: 1280,
      height: 900,
      readySelector: "[data-gallery-ready]",
    });
    assert.equal(
      await browser.evaluate("document.querySelectorAll('img[src*=\".gif?\"]').length"),
      0,
    );
    assert.equal(
      await browser.evaluate("document.querySelector('article').dataset.families"),
      "fragments",
    );
    assert.deepEqual(
      await browser.evaluate(
        "[...document.querySelectorAll('article:not([hidden]) img')].map(image=>image.id.replace('preset-',''))",
      ),
      recommended,
    );
    assert.equal(
      await browser.evaluate(
        "document.querySelector('.collections [aria-pressed=true]').dataset.collection",
      ),
      "starter",
    );
    assert(
      await browser.evaluate(
        "[...document.querySelectorAll('article:not([hidden]) .starter-note')].every(note=>note.textContent.length>10)",
      ),
    );
    await browser.evaluate(
      "document.querySelector('.collections [data-collection=profiles]').click()",
    );
    assert.equal(
      await browser.evaluate("document.querySelectorAll('article:not([hidden])').length"),
      7,
    );
    assert(
      await browser.evaluate(
        "[...document.querySelectorAll('article:not([hidden])')].every(card=>card.dataset.collection==='profiles' && card.dataset.action==='effect')",
      ),
    );
    await browser.evaluate(
      "document.getElementById('search').value='ribbon';document.getElementById('search').dispatchEvent(new Event('input'))",
    );
    assert.equal(
      await browser.evaluate("document.querySelectorAll('article:not([hidden])').length"),
      1,
    );
    await browser.evaluate(
      "document.querySelector('.collections [data-collection=starter]').click()",
    );
    await browser.evaluate(
      "document.getElementById('search').value='ink';document.getElementById('search').dispatchEvent(new Event('input'))",
    );
    assert.equal(await browser.evaluate("document.getElementById('collection').value"), "all");
    assert(
      await browser.evaluate(
        "[...document.querySelectorAll('article:not([hidden])')].every(c=>c.dataset.search.includes('ink'))",
      ),
    );
    await browser.evaluate("document.querySelector('article:not([hidden]) [data-play]').click()");
    assert.equal(
      await browser.evaluate("document.querySelectorAll('img[src*=\".gif?\"]').length"),
      1,
    );
    await browser.evaluate(
      "document.querySelectorAll('article:not([hidden]) [data-play]')[1].click()",
    );
    assert.equal(
      await browser.evaluate("document.querySelectorAll('img[src*=\".gif?\"]').length"),
      1,
    );
    await browser.evaluate("document.querySelector('.filters summary').click()");
    assert.equal(await browser.evaluate("document.querySelector('.filters').open"), true);
    await browser.evaluate(
      "document.getElementById('family').value='hexagons';document.getElementById('family').dispatchEvent(new Event('input'))",
    );
    assert.equal(
      await browser.evaluate("document.querySelectorAll('img[src*=\".gif?\"]').length"),
      0,
    );
    assert.equal(await browser.evaluate("document.getElementById('empty').hidden"), false);
    await browser.evaluate(
      "document.getElementById('search').value='';document.getElementById('search').dispatchEvent(new Event('input'))",
    );
    assert.equal(
      await browser.evaluate("document.querySelectorAll('article:not([hidden])').length"),
      2,
    );
    await browser.evaluate(
      "document.querySelector('article:not([hidden]) [data-play]').click();document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}))",
    );
    assert.equal(
      await browser.evaluate("document.querySelectorAll('img[src*=\".gif?\"]').length"),
      0,
    );
    // Old scenario links and direct anchors must not disappear behind Start here.
    await browser.navigate(url + "?action=resize", { readySelector: "[data-gallery-ready]" });
    assert.equal(await browser.evaluate("document.getElementById('collection').value"), "all");
    assert(
      await browser.evaluate(
        "[...document.querySelectorAll('article:not([hidden])')].every(card=>card.dataset.action==='resize')",
      ),
    );
    assert(
      (await browser.evaluate("document.querySelectorAll('article:not([hidden])').length")) > 0,
    );
    await browser.navigate(url + "#preset-vortex-fold", { readySelector: "[data-gallery-ready]" });
    assert.equal(
      await browser.evaluate(
        "document.getElementById('preset-vortex-fold').closest('article').hidden",
      ),
      false,
    );
    await browser.navigate(url + "?collection=profiles", { readySelector: "[data-gallery-ready]" });
    assert.equal(
      await browser.evaluate("document.querySelectorAll('article:not([hidden])').length"),
      7,
    );
    await browser.evaluate("location.hash='preset-pixelate'");
    assert.equal(
      await browser.evaluate(
        "document.getElementById('preset-pixelate').closest('article').hidden",
      ),
      false,
    );
    assert.equal(
      await browser.evaluate("document.querySelectorAll('img[src*=\".gif?\"]').length"),
      0,
    );
    // Back/forward restores the collection instead of applying a default again.
    await browser.evaluate(
      "history.pushState(null,'','?collection=profiles');dispatchEvent(new PopStateEvent('popstate'))",
    );
    assert.equal(
      await browser.evaluate("document.querySelectorAll('article:not([hidden])').length"),
      7,
    );
    await browser.evaluate(
      "history.pushState(null,'','?collection=invalid&family=hexagons');dispatchEvent(new PopStateEvent('popstate'))",
    );
    assert.equal(
      await browser.evaluate("document.querySelectorAll('article:not([hidden])').length"),
      2,
    );
    mkdirSync(join(projectRoot, "artifacts/adoption-path"), { recursive: true });
    for (const width of [1280, 390]) {
      await browser.navigate(url, { width, height: 940, readySelector: "[data-gallery-ready]" });
      assert(
        await browser.evaluate("document.documentElement.scrollWidth <= innerWidth"),
        "gallery fits viewport",
      );
      const shot = await browser.rpc("Page.captureScreenshot", { format: "png" });
      writeFileSync(
        join(projectRoot, `artifacts/adoption-path/gallery-${width}.png`),
        Buffer.from(shot.data, "base64"),
      );
    }
  } finally {
    await browser.close();
  }
});
