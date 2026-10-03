import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import { launchBrowser, projectRoot } from "../scripts/lib/browser.mjs";

test("Studio collections browse across families without changing the current effect", async () => {
  mkdirSync(join(projectRoot, "artifacts"), { recursive: true });
  const directory = mkdtempSync(join(projectRoot, "artifacts/collections-test-"));
  const preview = join(directory, "studio.html");
  execFileSync("python3", ["-m", "niri_fx", "preview", "--output", preview], { cwd: projectRoot });
  const browser = await launchBrowser();
  try {
    await browser.navigate(pathToFileURL(preview).href);
    const before = await browser.evaluate("JSON.stringify(effectDocument())");
    const groups = await browser.evaluate("catalog.collections");
    for (const [id, collection] of Object.entries(groups)) {
      await browser.evaluate(
        `byId('preset-collection').value=${JSON.stringify(id)};byId('preset-collection').dispatchEvent(new Event('change'))`,
      );
      assert.equal(await browser.evaluate("JSON.stringify(effectDocument())"), before);
      const styles = await browser.evaluate(
        "[...byId('preset').options].filter(option=>option.value&&!option.hidden).map(option=>option.value)",
      );
      const profiles = await browser.evaluate(
        "[...byId('profile').options].filter(option=>option.value&&!option.hidden).map(option=>option.value)",
      );
      assert.deepEqual([...styles, ...profiles].sort(), [...collection.styles].sort());
    }
    await browser.evaluate(
      "byId('preset-collection').value='shapes';byId('preset-collection').dispatchEvent(new Event('change'));byId('profile').value='geometric-flow';byId('profile').dispatchEvent(new Event('change'))",
    );
    assert.deepEqual(
      await browser.evaluate(
        "[actions.open.fragment_shape,actions.close.fragment_shape,actions.resize,actions.movement]",
      ),
      ["triangle", "hexagon", null, null],
    );
    // Choosing a family returns to its full preset list instead of leaving
    // stale collection restrictions that can make every option disappear.
    await browser.evaluate(
      "byId('family').value='pixels';byId('family').dispatchEvent(new Event('change'))",
    );
    assert.equal(await browser.evaluate("byId('preset-collection').value"), "");
    assert(
      await browser.evaluate(
        "[...byId('preset').options].some(option=>option.value==='pixel-wipe'&&!option.hidden)",
      ),
    );
  } finally {
    await browser.close();
  }
});
