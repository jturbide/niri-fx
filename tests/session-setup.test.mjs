import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { join } from "node:path";
import { test } from "node:test";
import { launchBrowser, projectRoot } from "../scripts/lib/browser.mjs";

const token = "synthetic-session-setup";
const fingerprint = "a".repeat(64);
const ready = {
  state: "update",
  can_review: true,
  action: "update",
  installed: { version: "0.23.0", build_id: "new-build" },
  next_login: { tools_version: "0.22.1", build_id: "old-build", shared: true },
  running: { status: "matched", detail: "NiriFX compositor · current desktop" },
  config: { mode: "preserve" },
  detail: "An installed package update is ready to review.",
};
const plan = {
  plan_sha256: fingerprint,
  intent: "update",
  changes: [{ action: "create", path: "/example/selected-session.json" }],
  notes: ["Your saved recipe and previous session remain available."],
};

async function fixture(t, { session = ready, hosted = false } = {}) {
  const html = execFileSync(
    "python3",
    [
      "-c",
      `
import json,sys
from niri_fx.preview import preview_document
from niri_fx.presets import PRESETS
session,hosted=json.loads(sys.argv[1])
connection=None if hosted else {'target':'standalone','token':'synthetic-session-setup','session':session,'installation':{'state':'current','selected_version':'0.22.1'}}
print(preview_document(PRESETS['balanced'], connection=connection, hosted=hosted))
`,
      JSON.stringify([session, hosted]),
    ],
    { cwd: projectRoot, encoding: "utf8", maxBuffer: 5 * 1024 * 1024 },
  );
  let browser,
    rejectApply = false,
    pending = false;
  const requests = [];
  const server = createServer(async (request, response) => {
    const path = new URL(request.url, "http://127.0.0.1").pathname;
    if (path === "/") return response.end(html);
    if (path === "/library")
      return response.end(
        JSON.stringify({
          customs: {},
          managed: {},
          warnings: [],
          restore: false,
          active_name: "Synthetic desktop",
        }),
      );
    if (!path.startsWith("/session-")) return response.writeHead(404).end();
    assert.equal(request.headers["x-nirifx-token"], token);
    const chunks = [];
    for await (const chunk of request) chunks.push(chunk);
    const body = JSON.parse(Buffer.concat(chunks));
    requests.push({ path, body });
    response.setHeader("Content-Type", "application/json");
    if (path === "/session-status") return response.end(JSON.stringify(session));
    if (path === "/session-review") {
      pending = true;
      return response.end(JSON.stringify(plan));
    }
    if (path === "/session-cancel") {
      assert.equal(body.expected, fingerprint);
      pending = false;
      return response.end(JSON.stringify({ cancelled: true }));
    }
    if (path === "/session-apply") {
      assert.equal(body.expected, fingerprint);
      assert(pending, "Apply requires a fresh review");
      pending = false;
      if (rejectApply === true)
        return response
          .writeHead(409)
          .end(JSON.stringify({ error: "Session changed. Review again." }));
      session = {
        ...ready,
        state: "current",
        can_review: false,
        action: null,
        next_login: { ...ready.next_login, tools_version: "0.23.0", build_id: "new-build" },
      };
      if (rejectApply === "uncertain") {
        session = { ...session, reopen_required: true, apply_uncertain: true };
        return response.writeHead(400).end(
          JSON.stringify({
            error: "The package response could not be read.",
            reopen_required: true,
            apply_uncertain: true,
          }),
        );
      }
      if (rejectApply === "malformed") return response.end(JSON.stringify({}));
      return response.end(
        JSON.stringify({ activation: "next-login", reopen_required: true, session }),
      );
    }
    response.writeHead(404).end();
  });
  t.after(async () => {
    try {
      await browser?.close();
    } finally {
      server.closeAllConnections();
      await new Promise((resolve) => server.close(resolve));
    }
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  browser = await launchBrowser();
  await browser.rpc("Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-reduced-motion", value: "reduce" }],
  });
  await browser.navigate(`http://127.0.0.1:${server.address().port}/?breakup=0`, {
    width: 1280,
    height: 960,
  });
  const wait = (condition) =>
    browser.evaluate(
      `new Promise((resolve,reject)=>{const start=Date.now();function check(){if(${condition})resolve();else if(Date.now()-start>5000)reject(new Error('Session UI did not settle'));else setTimeout(check,20)}check()})`,
    );
  await wait("document.documentElement.dataset.shaderStatus==='ready'");
  const click = async (id) => {
    await browser.evaluate(`byId(${JSON.stringify(id)}).click()`);
    await wait("!window.niriFxSessionSetup.snapshot().busy");
  };
  return {
    browser,
    requests,
    click,
    failApply(mode = true) {
      rejectApply = mode;
    },
  };
}

const draft = (browser) =>
  browser.evaluate(
    "JSON.stringify({document:effectDocument(),history:editHistory,index:historyIndex,mode,progress,seed})",
  );

test("session review, cancel and apply preserve the draft and require reopening before effect activation", async (t) => {
  const view = await fixture(t);
  const { browser } = view;
  await browser.evaluate(
    "byId('show-editor').click();byId('spin').value=170;byId('spin').dispatchEvent(new Event('input'))",
  );
  const before = await draft(browser);
  assert.equal(view.requests.length, 0, "Opening Studio must not review or adopt automatically");
  assert.equal(await browser.evaluate("byId('session-review').textContent"), "Review update");
  await view.click("session-review");
  assert.equal(await browser.evaluate("byId('session-plan').hidden"), false);
  assert.equal(
    await browser.evaluate("byId('session-plan-title').textContent"),
    "Select this package update for your next login?",
  );
  await view.click("session-cancel");
  assert.equal(await draft(browser), before);
  assert.equal(await browser.evaluate("byId('session-plan').hidden"), true);
  assert.equal(view.requests.filter((r) => r.path === "/session-apply").length, 0);
  await view.click("session-review");
  await view.click("session-apply");
  assert.equal(await draft(browser), before);
  assert.equal(await browser.evaluate("byId('review-selection').disabled"), true);
  assert.match(
    await browser.evaluate("byId('session-setup-detail').textContent"),
    /Save or export.*reopen.*Log in/s,
  );
  assert.equal(await browser.evaluate("byId('session-review').hidden"), true);
  await view.click("session-refresh");
  assert.equal(await browser.evaluate("byId('review-selection').disabled"), true);
  if (process.env.NIRIFX_SESSION_SCREENSHOTS) {
    mkdirSync(process.env.NIRIFX_SESSION_SCREENSHOTS, { recursive: true });
    await browser.evaluate("byId('show-library').click();scrollTo(0,0)");
    const shot = await browser.rpc("Page.captureScreenshot", { format: "png" });
    writeFileSync(
      join(process.env.NIRIFX_SESSION_SCREENSHOTS, "session-updated.png"),
      Buffer.from(shot.data, "base64"),
    );
  }
});

test("a stale session review cannot be applied again without another review", async (t) => {
  const view = await fixture(t);
  const before = await draft(view.browser);
  view.failApply();
  await view.click("session-review");
  await view.click("session-apply");
  assert.equal(await view.browser.evaluate("byId('session-plan').hidden"), true);
  assert.match(await view.browser.evaluate("byId('session-error').textContent"), /Review again/);
  assert.equal(await draft(view.browser), before);
  assert.equal(view.requests.filter((r) => r.path === "/session-apply").length, 1);
  assert.equal(await view.browser.evaluate("niriFxSessionSetup.snapshot().applied"), false);
});

test("an ambiguous Apply reply locks desktop activation without claiming success", async (t) => {
  const view = await fixture(t);
  const before = await draft(view.browser);
  view.failApply("uncertain");
  await view.click("session-review");
  await view.click("session-apply");
  assert.equal(await view.browser.evaluate("niriFxSessionSetup.snapshot().uncertain"), true);
  assert.equal(await view.browser.evaluate("byId('review-selection').disabled"), true);
  assert.equal(
    await view.browser.evaluate("byId('session-setup-title').textContent"),
    "Session setup needs checking",
  );
  assert.match(
    await view.browser.evaluate("byId('session-setup-detail').textContent"),
    /could not be confirmed.*reopen.*check/s,
  );
  assert.doesNotMatch(
    await view.browser.evaluate("byId('session-result').textContent"),
    /selected|ready/i,
  );
  assert.equal(await draft(view.browser), before);
  await view.click("session-refresh");
  assert.equal(await view.browser.evaluate("niriFxSessionSetup.snapshot().uncertain"), true);
  assert.equal(await view.browser.evaluate("byId('review-selection').disabled"), true);
});

test("an unreadable successful response also requires checking the outcome", async (t) => {
  const view = await fixture(t);
  view.failApply("malformed");
  await view.click("session-review");
  await view.click("session-apply");
  assert.equal(await view.browser.evaluate("niriFxSessionSetup.snapshot().uncertain"), true);
  assert.equal(await view.browser.evaluate("byId('review-selection').disabled"), true);
  assert.match(
    await view.browser.evaluate("byId('session-error').textContent"),
    /could not be confirmed/,
  );
});

test("reopening the same page keeps uncertain setup fenced and first setup names its config", async (t) => {
  const prior = await fixture(t, {
    session: { ...ready, reopen_required: true, apply_uncertain: true },
  });
  assert.equal(await prior.browser.evaluate("byId('review-selection').disabled"), true);
  assert.equal(
    await prior.browser.evaluate("byId('session-setup-title').textContent"),
    "Session setup needs checking",
  );
  const fresh = await fixture(t, {
    session: {
      ...ready,
      state: "ready",
      action: "setup",
      next_login: null,
      config: {
        mode: "copy",
        path: "/example/niri/config.kdl",
        detail: "Later source edits are not shared automatically.",
      },
    },
  });
  assert.equal(await fresh.browser.evaluate("byId('session-review').textContent"), "Review setup");
  assert.match(
    await fresh.browser.evaluate("byId('session-config').textContent"),
    /not shared automatically.*\/example\/niri\/config.kdl.*draft is not applied/,
  );
});

test("missing packages show installation guidance while hosted Studio has no session controls", async (t) => {
  const missing = await fixture(t, {
    session: {
      state: "missing",
      can_review: false,
      detail: "Install the complete package to set up a session.",
    },
  });
  assert.equal(await missing.browser.evaluate("byId('session-install-guide').hidden"), false);
  assert.equal(await missing.browser.evaluate("byId('session-review').hidden"), true);
  const hosted = await fixture(t, { hosted: true });
  assert.equal(await hosted.browser.evaluate("byId('session-setup').hidden"), true);
  assert.equal(hosted.requests.length, 0);
});
