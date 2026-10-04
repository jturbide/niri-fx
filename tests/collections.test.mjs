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
    await browser.evaluate(
      "byId('preset-collection').value='desktop';byId('preset-collection').dispatchEvent(new Event('change'));byId('profile').value='gentle-motion';byId('profile').dispatchEvent(new Event('change'))",
    );
    assert.equal(await browser.evaluate("byId('desktop-motion').value"), "gentle");
    assert.equal(await browser.evaluate("effectDocument().motion.camera.stiffness"), 450);
    assert.equal(await browser.evaluate("effectDocument().actions.resize"), null);
    await browser.evaluate(
      "byId('desktop-motion').value='playful';byId('desktop-motion').dispatchEvent(new Event('change'))",
    );
    assert.equal(await browser.evaluate("effectDocument().motion.camera.damping_ratio"), 0.85);
    await browser.evaluate("byId('undo').click()");
    assert.equal(await browser.evaluate("byId('desktop-motion').value"), "gentle");
    await browser.evaluate(
      "byId('desktop-motion').value='';byId('desktop-motion').dispatchEvent(new Event('change'))",
    );
    assert.equal(await browser.evaluate("Object.hasOwn(effectDocument(),'motion')"), false);
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

test("action companions require explicit opt-in and survive import and Undo", async () => {
  const directory = mkdtempSync(join(projectRoot, "artifacts/action-set-test-"));
  const preview = join(directory, "studio.html");
  execFileSync("python3", ["-m", "niri_fx", "preview", "--output", preview], { cwd: projectRoot });
  const browser = await launchBrowser();
  try {
    await browser.navigate(pathToFileURL(preview).href);
    await browser.evaluate(
      "byId('progress').value=0;byId('progress').dispatchEvent(new Event('input'))",
    );
    const companions = await browser.evaluate("catalog.action_companions");
    for (const [name, suggestions] of Object.entries(companions)) {
      await browser.evaluate(
        `byId('profile').value=${JSON.stringify(name)};byId('profile').dispatchEvent(new Event('change'))`,
      );
      const before = await browser.evaluate("effectDocument()");
      assert.equal(before.actions.resize, null);
      assert.equal(before.actions.movement, null);
      for (const action of ["resize", "movement"]) {
        await browser.evaluate(
          `byId('action').value='${action}';byId('action').dispatchEvent(new Event('change'))`,
        );
        assert.deepEqual(
          await browser.evaluate("effectDocument()"),
          before,
          "viewing never opts in",
        );
        assert.deepEqual(await browser.evaluate("parameters"), suggestions[action]);
        assert.equal(await browser.evaluate("byId('action-companion-note').hidden"), false);
        await browser.evaluate(
          "byId('action-enabled').checked=true;byId('action-enabled').dispatchEvent(new Event('change'))",
        );
        assert.deepEqual(
          await browser.evaluate(`effectDocument().actions.${action}`),
          suggestions[action],
        );
        assert.equal(await browser.evaluate("byId('action-companion-note').hidden"), true);
        assert.equal(await browser.evaluate("kdlDocument().includes('window-movement')"), false);
        await browser.evaluate("byId('undo').click()");
        assert.equal(await browser.evaluate(`effectDocument().actions.${action}`), null);
        await browser.evaluate("byId('redo').click()");
        assert.deepEqual(
          await browser.evaluate(`effectDocument().actions.${action}`),
          suggestions[action],
        );
        await browser.evaluate(
          "byId('action-enabled').checked=false;byId('action-enabled').dispatchEvent(new Event('change'))",
        );
        assert.deepEqual(await browser.evaluate("effectDocument()"), before);
      }
      await browser.evaluate(
        `loadDocument(normalizePreset({...catalog.profiles[${JSON.stringify(name)}],name:'Renamed import'}));populate();refresh();byId('action').value='resize';byId('action').dispatchEvent(new Event('change'))`,
      );
      assert.deepEqual(
        await browser.evaluate("parameters"),
        suggestions.resize,
        "suggestions match normalized effects, not names",
      );
      await browser.evaluate(
        "actions.open.open_ms+=1;byId('action').value='open';byId('action').dispatchEvent(new Event('change'));byId('action').value='resize';byId('action').dispatchEvent(new Event('change'))",
      );
      assert.equal(await browser.evaluate("byId('action-companion-note').hidden"), true);
      assert.deepEqual(
        await browser.evaluate("parameters"),
        await browser.evaluate("catalog.presets.balanced"),
        "edited window effects do not silently select a companion",
      );
    }
  } finally {
    await browser.close();
  }
});
