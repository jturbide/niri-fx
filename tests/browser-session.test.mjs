// Small real-process checks complement the full Studio rendering suite.
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import {
  chmodSync,
  existsSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { syncBuiltinESMExports } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
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

for (const inheritedStderr of [true, false])
  test(
    inheritedStderr
      ? "startup failure stops owned helpers holding stderr after the leader exits"
      : "startup failure kills owned helpers that close stderr and ignore SIGTERM",
    { skip: process.platform === "win32" },
    async (t) => {
      const directory = mkdtempSync(join(tmpdir(), "niri-fx-browser-helper-"));
      const command = join(directory, "browser.mjs");
      const prefix = "niri-fx-inherited-stderr-" + process.pid + "-";
      t.after(() => {
        const pids = join(directory, "pids.json");
        if (existsSync(pids))
          for (const pid of JSON.parse(readFileSync(pids))) {
            try {
              process.kill(pid, "SIGKILL");
            } catch (error) {
              if (error.code !== "ESRCH") throw error;
            }
          }
        rmSync(directory, { recursive: true, force: true });
        for (const name of readdirSync(tmpdir()).filter((name) => name.startsWith(prefix)))
          rmSync(join(tmpdir(), name), { recursive: true, force: true });
      });
      const helper = `
    const {writeFileSync} = require('node:fs');
    process.on('SIGTERM', () => {
      writeFileSync(${JSON.stringify(join(directory, "helper-signaled"))}, 'SIGTERM');
      ${inheritedStderr ? "process.exit(0);" : "// Stay alive until the harness escalates to SIGKILL."}
    });
    setInterval(() => {}, 1000);
    process.send('ready');
  `;
      writeFileSync(
        command,
        `#!${process.execPath}
import {spawn} from 'node:child_process';
import {writeFileSync} from 'node:fs';
const helper = spawn(process.execPath, ['-e', ${JSON.stringify(helper)}], {
  stdio: ['ignore', 'ignore', ${inheritedStderr ? "process.stderr" : "'ignore'"}, 'ipc']
});
writeFileSync(${JSON.stringify(join(directory, "pids.json"))}, JSON.stringify([process.pid, helper.pid]));
helper.once('message', () => {
  process.stderr.write('synthetic startup failure with an inherited stderr handle\\n');
  process.exit(7);
});
`,
      );
      chmodSync(command, 0o700);
      const started = Date.now();
      await assert.rejects(
        launchBrowser({ command, launchTimeout: 3000, profilePrefix: prefix }),
        /Chrome did not start \(exit 7\).*synthetic startup failure/s,
      );
      assert.equal(readFileSync(join(directory, "helper-signaled"), "utf8"), "SIGTERM");
      const [group] = JSON.parse(readFileSync(join(directory, "pids.json")));
      assert.throws(() => process.kill(-group, 0), { code: "ESRCH" });
      assert(Date.now() - started < 10000, "startup and inherited-pipe cleanup remain bounded");
      assert(!readdirSync(tmpdir()).some((name) => name.startsWith(prefix)));
    },
  );

test("cleanup errors retain the original browser startup failure", async (t) => {
  const prefix = "niri-fx-cleanup-error-" + process.pid + "-";
  const original = fs.rmSync;
  t.after(() => {
    t.mock.restoreAll();
    syncBuiltinESMExports();
    for (const name of readdirSync(tmpdir()).filter((name) => name.startsWith(prefix)))
      original(join(tmpdir(), name), { recursive: true, force: true });
  });
  t.mock.method(fs, "rmSync", (path, ...options) => {
    if (String(path).includes(prefix)) throw new Error("synthetic cleanup failure");
    return original(path, ...options);
  });
  syncBuiltinESMExports();
  await assert.rejects(
    launchBrowser({ command: "/nonexistent/niri-fx-chrome", profilePrefix: prefix }),
    (error) => {
      assert(error instanceof AggregateError);
      assert.match(error.message, /Chrome did not start.*ENOENT.*cleanup also failed/s);
      assert.match(error.errors[0].message, /ENOENT/);
      assert.equal(error.cause, error.errors[0]);
      assert.equal(error.errors[1].message, "synthetic cleanup failure");
      return true;
    },
  );
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
