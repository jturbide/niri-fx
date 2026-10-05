import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { join } from "node:path";
import { test } from "node:test";
import { launchBrowser, projectRoot } from "../scripts/lib/browser.mjs";

async function fixture(
  t,
  { kind = "local", initial = { state: "current", selected_version: null } } = {},
) {
  const html = execFileSync(
    "python3",
    [
      "-c",
      `
import json,sys
from niri_fx.preview import preview_document
from niri_fx.presets import PRESETS
kind,installation=json.loads(sys.argv[1])
connection={'target':'standalone','token':'synthetic-installation-test','installation':installation} if kind=='local' else None
print(preview_document(PRESETS['balanced'],connection=connection,hosted=kind=='hosted'))
`,
      JSON.stringify([kind, initial]),
    ],
    { cwd: projectRoot, encoding: "utf8", maxBuffer: 4 * 1024 * 1024 },
  );
  let reply = { ok: true, installation: initial },
    status = 200,
    hold = false,
    browser;
  const requests = [],
    pending = [];
  let receivedPing;
  const pingReceived = new Promise((resolve) => {
    receivedPing = resolve;
  });
  const server = createServer((request, response) => {
    const path = new URL(request.url, "http://127.0.0.1").pathname;
    requests.push(path);
    if (path === "/ping") {
      receivedPing();
      if (hold) {
        pending.push(response);
        return;
      }
      response.writeHead(status, { "Content-Type": "application/json" });
      response.end(JSON.stringify(reply));
    } else if (path === "/library") {
      response.writeHead(200, { "Content-Type": "application/json" });
      response.end(
        JSON.stringify({
          customs: {},
          managed: {},
          warnings: [],
          restore: false,
          active_name: "Synthetic desktop",
        }),
      );
    } else if (path === "/") {
      response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      response.end(html);
    } else {
      response.writeHead(404).end();
    }
  });
  t.after(async () => {
    try {
      await browser?.close();
    } finally {
      if (server.listening) {
        server.closeAllConnections();
        await new Promise((resolve) => server.close(resolve));
      }
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  browser = await launchBrowser();
  await browser.rpc("Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-reduced-motion", value: "reduce" }],
  });
  await browser.rpc("Page.addScriptToEvaluateOnNewDocument", {
    source: `
    window.installationHeartbeats = [];
    const interval = window.setInterval;
    window.setInterval = (callback, ms, ...args) => {
      if (ms === 45000) { installationHeartbeats.push(callback); return 0; }
      return interval(callback, ms, ...args);
    };
    const timeout = window.setTimeout;
    window.setTimeout = (callback, ms, ...args) => {
      if (ms === 10000) window.expireInstallationRequest = callback;
      return timeout(callback, ms, ...args);
    };
  `,
  });
  await browser.navigate(`http://127.0.0.1:${server.address().port}/?breakup=0`, {
    width: 1320,
    height: 960,
  });
  const wait = (expression) =>
    browser.evaluate(`new Promise((resolve,reject)=>{
    const start=Date.now();function check(){if(${expression})resolve();else if(Date.now()-start>3000)reject(new Error('Installation UI did not settle'));else setTimeout(check,10)}check();
  })`);
  if (kind === "local") await wait("byId('active-look').textContent==='Active: Synthetic desktop'");
  return {
    browser,
    requests,
    async waitForPing() {
      let timer;
      try {
        await Promise.race([
          pingReceived,
          new Promise((_, reject) => {
            timer = setTimeout(
              () => reject(new Error("Held installation request did not arrive")),
              3000,
            );
          }),
        ]);
      } finally {
        clearTimeout(timer);
      }
    },
    respond(value, code = 200) {
      reply = value;
      status = code;
      hold = false;
    },
    hold() {
      hold = true;
    },
    release(value) {
      hold = false;
      for (const response of pending.splice(0)) response.end(JSON.stringify(value));
    },
    wait,
    async check(value, { manual = false, code = 200 } = {}) {
      if (value !== undefined) {
        reply = value;
        status = code;
        hold = false;
      }
      await browser.evaluate(
        manual ? "byId('check-installation').click()" : "void installationHeartbeats[0]()",
      );
      await wait("!byId('check-installation').disabled");
    },
  };
}

const snapshot = (browser) =>
  browser.evaluate(`({
  document:effectDocument(),parameters,editHistory,historyIndex,editingAction,mode,progress,seed,sessionSettings,
  href:location.href,status:byId('status').textContent,error:byId('error').textContent,
  undo:byId('undo').disabled,redo:byId('redo').disabled,
  selection:byId('selection-actions').textContent
})`);
const status = (state, selected_version = null) => ({
  ok: true,
  installation: { state, selected_version },
});

test("local heartbeat reports same-version runtime changes without touching unsaved editing", async (t) => {
  const view = await fixture(t);
  const { browser } = view;
  assert.equal(await browser.evaluate("installationHeartbeats.length"), 1);
  assert.equal(view.requests.includes("/ping"), false);
  assert.equal(await browser.evaluate("byId('installation-notice').hidden"), true);
  await browser.evaluate(
    "byId('show-editor').click();byId('spin').value=175;byId('spin').dispatchEvent(new Event('input'))",
  );
  const draft = await snapshot(browser);
  assert(draft.historyIndex > 0);
  const version = await browser.evaluate("catalog.studio.version");
  await view.check(status("changed", version));
  assert.equal(await browser.evaluate("byId('installation-notice').hidden"), false);
  assert.equal(await browser.evaluate("byId('studio-about').open"), false);
  assert.match(
    await browser.evaluate("byId('installation-notice').textContent"),
    /different Studio installation.*Save or export.*NiriFX launcher.*Reloading/s,
  );
  assert.doesNotMatch(
    await browser.evaluate("byId('installation-notice').textContent"),
    /newer|update available/i,
  );
  assert.deepEqual(await snapshot(browser), draft);
  assert.equal(
    await browser.evaluate("byId('installation-announcement').getAttribute('role')"),
    "status",
  );
  await browser.evaluate(
    `window.noticeMutations=0;new MutationObserver(events=>noticeMutations+=events.length).observe(byId('installation-announcement'),{subtree:true,childList:true,attributes:true,characterData:true})`,
  );
  await view.check(status("changed", version));
  assert.equal(
    await browser.evaluate("noticeMutations"),
    0,
    "Unchanged heartbeats must not repeat notices",
  );
  if (process.env.NIRIFX_INSTALLATION_SCREENSHOTS) {
    const root = process.env.NIRIFX_INSTALLATION_SCREENSHOTS;
    mkdirSync(root, { recursive: true });
    await browser.evaluate("byId('show-library').click();window.scrollTo(0,0)");
    for (const [name, width, height] of [
      ["desktop", 1320, 960],
      ["narrow", 390, 900],
    ]) {
      await browser.rpc("Emulation.setDeviceMetricsOverride", {
        width,
        height,
        deviceScaleFactor: 1,
        mobile: false,
      });
      assert.equal(
        await browser.evaluate("document.documentElement.scrollWidth<=innerWidth"),
        true,
      );
      const shot = await browser.rpc("Page.captureScreenshot", { format: "png" });
      writeFileSync(join(root, name + ".png"), Buffer.from(shot.data, "base64"));
    }
  }
  await view.check(status("current", version));
  assert.equal(await browser.evaluate("byId('installation-notice').hidden"), true);
  assert.match(
    await browser.evaluate("byId('installation-detail').textContent"),
    /using the selected/,
  );
});

test("manual retry preserves meaningful prior guidance and rejects malformed replies", async (t) => {
  const view = await fixture(t, { initial: { state: "changed", selected_version: "0.19.0" } });
  const { browser } = view;
  await browser.evaluate("byId('studio-about').open=true");
  const draft = await snapshot(browser);
  for (const reply of [
    null,
    { ok: true },
    status("unknown"),
    { ok: false, installation: { state: "current", selected_version: null } },
    status("unavailable"),
  ]) {
    await view.check(reply, { manual: true });
    assert.match(
      await browser.evaluate("byId('installation-notice').textContent"),
      /different Studio installation.*last known result/s,
    );
    assert.equal(await browser.evaluate("byId('check-installation').disabled"), false);
  }
  await view.check(status("current"), { manual: true, code: 503 });
  assert.match(
    await browser.evaluate("byId('installation-detail').textContent"),
    /last known result/,
  );
  await view.check(status("prepared"), { manual: true });
  assert.match(
    await browser.evaluate("byId('installation-notice').textContent"),
    /not active yet.*registration and activation/s,
  );
  assert.equal(await browser.evaluate("byId('installation-notice-guide').hidden"), false);
  assert.match(
    await browser.evaluate("byId('installation-notice-guide').href"),
    /docs\/tool-updates\.md$/,
  );
  await view.check(status("unmanaged"), { manual: true });
  assert.equal(await browser.evaluate("byId('installation-notice').hidden"), true);
  assert.match(
    await browser.evaluate("byId('installation-detail').textContent"),
    /outside the shared/,
  );
  assert.deepEqual(await snapshot(browser), draft);
});

test("manual and heartbeat checks share one request and timeout permits a retry", async (t) => {
  const view = await fixture(t);
  const { browser } = view;
  view.hold();
  await browser.evaluate("byId('check-installation').click()");
  await view.wait("byId('check-installation').disabled");
  await browser.evaluate("void installationHeartbeats[0]();byId('check-installation').click()");
  await view.waitForPing();
  await browser.evaluate("expireInstallationRequest()");
  await view.wait("!byId('check-installation').disabled");
  assert.equal(view.requests.filter((path) => path === "/ping").length, 1);
  assert.match(
    await browser.evaluate("byId('installation-notice').textContent"),
    /could not be verified/,
  );
  view.release(status("changed"));
  view.respond(status("current"));
  await browser.evaluate("byId('retry-installation').focus();byId('retry-installation').click()");
  await view.wait("!byId('retry-installation').disabled");
  assert.equal(await browser.evaluate("document.activeElement.id"), "show-library");
  assert.equal(await browser.evaluate("byId('installation-notice').hidden"), true);
  assert.equal(
    await browser.evaluate("byId('check-installation').textContent"),
    "Check installation",
  );
  assert.equal(
    await browser.evaluate("byId('installation-check-result').textContent"),
    "Installation checked.",
  );
});

test("missing initial verification is unavailable and version strings are displayed as text", async (t) => {
  const view = await fixture(t, { initial: null });
  const { browser } = view;
  assert.match(
    await browser.evaluate("byId('installation-notice-title').textContent"),
    /unavailable/,
  );
  await view.check(status("changed", "<img src=x onerror=alert(1)>"));
  assert.equal(
    await browser.evaluate("byId('installation-notice').querySelectorAll('img').length"),
    0,
  );
  assert.match(await browser.evaluate("byId('installation-detail').textContent"), /<img src=x/);
});

for (const kind of ["hosted", "offline"])
  test(`${kind} Studio has no installation checks or local status requests`, async (t) => {
    const view = await fixture(t, { kind });
    const { browser } = view;
    assert.equal(await browser.evaluate("catalog.connection"), null);
    assert.equal(await browser.evaluate("installationHeartbeats.length"), 0);
    assert.equal(await browser.evaluate("byId('studio-installation').hidden"), true);
    assert.equal(await browser.evaluate("byId('installation-notice').hidden"), true);
    await browser.evaluate("byId('studio-about').open=true;byId('check-installation').click()");
    assert.equal(view.requests.includes("/ping"), false);
  });
