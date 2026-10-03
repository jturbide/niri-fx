// Small real-process checks complement the full Studio rendering suite.
import assert from "node:assert/strict";
import { existsSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { test } from "node:test";
import { launchBrowser } from "../scripts/lib/browser.mjs";

const page = (status) =>
  "data:text/html," +
  encodeURIComponent(`<html data-shader-status="${status}"><p id="error">fixture error</p></html>`);

test("failed Chrome launch cleans its owned profile and reports the cause", async () => {
  const prefix = "niri-fx-missing-" + process.pid + "-";
  await assert.rejects(
    launchBrowser({ command: "/nonexistent/niri-fx-chrome", profilePrefix: prefix }),
    /Chrome did not start.*ENOENT/,
  );
  assert(!readdirSync(tmpdir()).some((name) => name.startsWith(prefix)));
});

test("browser protocol failures are bounded and cleanup rejects in-flight requests", async () => {
  const browser = await launchBrowser();
  try {
    await browser.navigate(page("ready"));
    assert.equal(await browser.evaluate("1 + 2"), 3);
    await assert.rejects(
      browser.evaluate("(()=>{throw new Error('fixture exception')})()"),
      /fixture exception/,
    );
    await assert.rejects(
      browser.rpc(
        "Runtime.evaluate",
        { expression: "new Promise(()=>{})", awaitPromise: true },
        50,
      ),
      /timed out/,
    );
    assert.equal(await browser.evaluate("2 + 3"), 5, "a timeout does not poison later requests");
    await assert.rejects(browser.navigate(page("error")), /Studio render failed: fixture error/);
    await assert.rejects(browser.navigate(page(""), { timeout: 150 }), /did not become ready/);
    const pending = assert.rejects(
      browser.rpc("Runtime.evaluate", { expression: "new Promise(()=>{})", awaitPromise: true }),
      /closed/,
    );
    await browser.close();
    await pending;
    await browser.close();
    assert(!existsSync(browser.profile));
    await assert.rejects(browser.rpc("Runtime.evaluate"), /closed/);
  } finally {
    await browser.close();
  }
});
