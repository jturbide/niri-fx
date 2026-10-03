import assert from "node:assert/strict";
import { test } from "node:test";
import { pathToFileURL } from "node:url";
import { join } from "node:path";
import { launchBrowser, projectRoot } from "../scripts/lib/browser.mjs";

test("gallery starts paused, filters examples and plays only one animation", async () => {
  const browser = await launchBrowser();
  try {
    await browser.rpc("Emulation.setEmulatedMedia", {
      features: [{ name: "prefers-reduced-motion", value: "reduce" }],
    });
    await browser.navigate(pathToFileURL(join(projectRoot, "docs/gallery/index.html")).href, {
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
    await browser.evaluate(
      "document.getElementById('search').value='ink';document.getElementById('search').dispatchEvent(new Event('input'))",
    );
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
  } finally {
    await browser.close();
  }
});
