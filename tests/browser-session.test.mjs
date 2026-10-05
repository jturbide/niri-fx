// Small real-process checks complement the full Studio rendering suite.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import { existsSync, readdirSync } from "node:fs";
import { syncBuiltinESMExports } from "node:module";
import { tmpdir } from "node:os";
import { test } from "node:test";
import { launchBrowser, projectRoot } from "../scripts/lib/browser.mjs";

const page = (status) =>
  "data:text/html," +
  encodeURIComponent(`<html data-shader-status="${status}"><p id="error">fixture error</p></html>`);

function portFileReader(t, read) {
  const original = fs.readFileSync;
  t.mock.method(fs, "readFileSync", (path, ...options) =>
    String(path).endsWith("/DevToolsActivePort")
      ? read(() => original(path, ...options))
      : original(path, ...options),
  );
  // The helper deliberately uses named built-in imports. Keep this test seam
  // local to the file reader; real Chrome processes, files and CDP stay in use.
  syncBuiltinESMExports();
  t.after(() => {
    t.mock.restoreAll();
    syncBuiltinESMExports();
  });
}

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
    const fixture = {
      text: "quotes '\" \\ and `template ${tokens}` \u2028",
      nested: [0, false, null],
    };
    assert.deepEqual(
      await browser.callFunction("function(value) { return value; }", [fixture]),
      fixture,
    );
    assert.equal(await browser.callFunction("async function(a,b) { return a+b; }", [2, 3]), 5);
    await assert.rejects(
      browser.callFunction("function() { throw new Error('argument fixture exception'); }"),
      /argument fixture exception/,
    );
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

test("startup hooks capture script errors before page code on every reload", async () => {
  const browser = await launchBrowser();
  try {
    await browser.rpc("Page.addScriptToEvaluateOnNewDocument", {
      source:
        'window.bootErrors=[];addEventListener("error",event=>window.bootErrors.push(event.message));',
    });
    const url =
      "data:text/html," +
      encodeURIComponent(
        '<html><script>throw new Error("fixture startup error")</script><p data-boot-end>Ready</p></html>',
      );
    for (let reload = 0; reload < 2; reload++) {
      await browser.navigate(url, { readySelector: "[data-boot-end]" });
      assert.deepEqual(await browser.evaluate("window.bootErrors"), [
        "Uncaught Error: fixture startup error",
      ]);
    }
  } finally {
    await browser.close();
  }
});

test("browser startup waits for the initial page target after the debugging port", async (t) => {
  const originalFetch = globalThis.fetch;
  let emptyResponses = 0,
    targetRequests = 0;
  t.mock.method(globalThis, "fetch", (url, options) => {
    if (String(url).endsWith("/json/list")) {
      targetRequests++;
      if (emptyResponses++ < 2) return Promise.resolve(new Response("[]"));
    }
    return originalFetch(url, options);
  });
  const browser = await launchBrowser();
  try {
    assert(targetRequests >= 3, "an empty target list is a startup transition");
    await browser.navigate(page("ready"));
    assert.equal(await browser.evaluate("1 + 2"), 3);
  } finally {
    await browser.close();
  }
});

test("browser startup waits for a complete valid debugging port line", async (t) => {
  const incomplete = ["", "12", "0\n/devtools/browser/fixture", "65536\n/devtools/browser/fixture"],
    observed = [];
  portFileReader(t, (actual) => {
    if (!incomplete.length) return actual();
    const value = incomplete.shift();
    observed.push(value);
    return value;
  });
  const browser = await launchBrowser();
  try {
    assert.equal(observed.length, 4, "none of the partial or invalid snapshots starts CDP");
    await browser.navigate(page("ready"));
    assert.equal(await browser.evaluate("3 + 4"), 7);
  } finally {
    await browser.close();
  }
});

test("a permanently invalid debugging port times out and cleans the owned profile", async (t) => {
  const prefix = "niri-fx-invalid-port-" + process.pid + "-",
    launchTimeout = 350,
    started = Date.now();
  let reads = 0;
  portFileReader(t, () => {
    reads++;
    return "65536\n/devtools/browser/fixture";
  });
  await assert.rejects(
    launchBrowser({ launchTimeout, profilePrefix: prefix }),
    /Chrome did not start \(timeout\).*invalid debugging port/s,
  );
  assert(reads >= 2, "malformed contents are retried only within the startup deadline");
  assert(Date.now() - started < launchTimeout + 7000, "startup and cleanup remain bounded");
  assert(!readdirSync(tmpdir()).some((name) => name.startsWith(prefix)));
});

test("an incomplete port does not hide an exiting browser's startup diagnostics", async (t) => {
  const prefix = "niri-fx-exiting-port-" + process.pid + "-";
  portFileReader(t, () => "12");
  await assert.rejects(
    launchBrowser({ command: process.execPath, profilePrefix: prefix }),
    /Chrome did not start \(exit \d+\).*bad option: --headless/s,
  );
  assert(!readdirSync(tmpdir()).some((name) => name.startsWith(prefix)));
});

test("rendering suite selectors reject incomplete coverage before browser startup", () => {
  for (const arguments_ of [
    ["--suite", "unknown"],
    ["--shape-aspect", "1"],
    ["--suite", "studio", "--shape-aspect", "1"],
    ["--suite", "motion", "--shape-aspect", "1"],
    ["--suite", "shapes", "--shape-aspect", "0.5"],
    ["--suite", "motion", "--save-test"],
    ["--suite", "shapes", "--save-test"],
  ]) {
    const result = spawnSync(
      process.execPath,
      ["scripts/browser-smoke.mjs", "http://127.0.0.1/", ...arguments_],
      {
        cwd: projectRoot,
        env: { ...process.env, CHROME_BIN: "/browser-must-not-launch" },
        encoding: "utf8",
        timeout: 5000,
      },
    );
    assert.notEqual(result.status, 0);
    assert.doesNotMatch(result.stderr, /Chrome did not start/);
    assert.match(
      result.stderr,
      /Unknown browser suite|--shape-aspect requires|--save-test requires/,
    );
  }
});
