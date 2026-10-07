import assert from "node:assert/strict";
import { test } from "node:test";
import { execFileSync, spawn } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { launchBrowser, projectRoot } from "../scripts/lib/browser.mjs";

async function sharedStudioFixture(t, { configured = true, saved = true } = {}) {
  let shared = false,
    selected = false,
    stale = false,
    unchanged = false,
    browser;
  const requests = [];
  const html = (shared) =>
    execFileSync(
      "python3",
      [
        "-c",
        `
import json,sys
from niri_fx.preview import preview_document
from niri_fx.presets import PRESETS
shared,configured=json.loads(sys.argv[1])
connection={"target":"native","token":"synthetic-shared-test",
    "installation":{"state":"unmanaged","selected_version":None},"native":{
    "base_bundle":"shared-base" if shared else "launch-base","variant":"fragment",
    "recipe":None,"swap_supported":True,
    "shared":shared,"shared_config_configured":configured,
    "shared_config_path":"/synthetic/normal-niri/config.kdl" if configured else None}}
print(preview_document(PRESETS["balanced"],connection=connection))
`,
        JSON.stringify([shared, configured]),
      ],
      { cwd: projectRoot, encoding: "utf8", maxBuffer: 4 * 1024 * 1024 },
    );
  let page = html(shared);
  const plan = (activation) => ({
    activation,
    plan_sha256: "a".repeat(64),
    changes: unchanged ? [] : [{ action: "update", path: "/synthetic/nirifx-effects.kdl" }],
    notes: ["Synthetic shared-settings fixture; no desktop files are written."],
  });
  const server = createServer(async (request, response) => {
    const path = new URL(request.url, "http://127.0.0.1").pathname;
    if (path === "/") {
      response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" }).end(page);
      return;
    }
    response.setHeader("Content-Type", "application/json");
    if (path === "/library") {
      response.end(
        JSON.stringify({
          customs: {},
          managed: {},
          warnings: [],
          restore: true,
          active_name: "Synthetic settings",
          native: {
            base_bundle: shared ? "shared-base" : "launch-base",
            baseline_bundle: "launch-base",
            shared,
            shared_state: { selected },
            recovery_available: selected,
            selection: { selected: selected ? "shared-base" : "launch-base", previous: null },
            bundles: [],
            recipe: saved
              ? {
                  document: { schema: 3, name: "Saved settings", effect: {} },
                  fragment_preset: null,
                }
              : null,
            reopen: saved,
            running: { status: "matched", bundle_id: "launch-base", detail: "Synthetic identity" },
            live: { ready: false, status: shared ? "shared-config" : "offline" },
          },
        }),
      );
      return;
    }
    let body = "";
    for await (const part of request) body += part;
    requests.push({
      path,
      body: JSON.parse(body || "{}"),
      token: request.headers["x-nirifx-token"],
    });
    if (path === "/shared-review" || path === "/review") {
      response.end(JSON.stringify(plan("config-written")));
    } else if (path === "/recovery-review") {
      response.end(JSON.stringify(plan("next-login")));
    } else if (path === "/shared-apply" || path === "/apply") {
      if (stale) {
        response
          .writeHead(409)
          .end(JSON.stringify({ error: "Shared sources changed. Review again." }));
      } else {
        selected = true;
        response.end(
          JSON.stringify({ activation: "config-written", live: { status: "unverified" } }),
        );
      }
    } else if (path === "/recovery-apply") {
      selected = false;
      response.end(JSON.stringify({ activation: "next-login" }));
    } else {
      response.writeHead(404).end(JSON.stringify({ error: "Unknown synthetic endpoint" }));
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
  await reduceTransactionMotion(browser);
  const url = `http://127.0.0.1:${server.address().port}/?breakup=0`;
  const wait = (expression) =>
    browser.evaluate(`new Promise((resolve,reject)=>{
      const started=Date.now();function check(){if(${expression})resolve();else if(Date.now()-started>3000)reject(new Error('Shared Studio timeout: '+byId('error').textContent));else setTimeout(check,10)}check();
    })`);
  const navigate = async () => {
    await browser.navigate(url, { width: 1440, height: 1080 });
    await wait("byId('native-selected').textContent.length>0");
  };
  await navigate();
  return {
    browser,
    requests,
    async click(id) {
      await browser.callFunction("function(id){byId(id).click()}", [id]);
      await wait("!byId('store-profile').disabled");
    },
    stale(value) {
      stale = value;
    },
    unchanged(value) {
      unchanged = value;
    },
    async reopen() {
      shared = selected;
      page = html(shared);
      await navigate();
    },
  };
}

async function reduceTransactionMotion(browser) {
  // Selecting a Library card automatically replays it. Transaction checks keep
  // real shaders at their endpoints; dedicated preview tests exercise playback.
  await browser.rpc("Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-reduced-motion", value: "reduce" }],
  });
  await browser.rpc("Page.addScriptToEvaluateOnNewDocument", {
    source: `
      window.transactionFrameRequests = 0;
      const requestFrame = window.requestAnimationFrame;
      window.requestAnimationFrame = callback => {
        window.transactionFrameRequests++;
        return requestFrame(callback);
      };
    `,
  });
}

async function assertTransactionMotion(browser) {
  assert.deepEqual(
    await browser.evaluate(`({
      preference: matchMedia("(prefers-reduced-motion: reduce)").matches,
      reduced: byId("reduced-motion").checked,
      frames: window.transactionFrameRequests
    })`),
    { preference: true, reduced: true, frames: 0 },
    "Transaction workflows must honor reduced motion without queuing playback",
  );
}

test("shared settings review preserves drafts and separates file updates from running confirmation", async (t) => {
  const view = await sharedStudioFixture(t);
  const { browser, click, requests } = view;
  const { evaluate } = browser;
  const snapshot = () => evaluate("({document:effectDocument(),history:editHistory,historyIndex})");
  assert.equal(await evaluate("byId('native-share').disabled"), false);
  assert.equal(await evaluate("byId('native-shared-settings').hidden"), false);
  assert.equal(await evaluate("byId('native-share').closest('details') === null"), true);
  assert.match(await evaluate("byId('native-config-mode').textContent"), /Using a saved copy/);
  assert.equal(
    await evaluate("byId('native-shared-source').textContent"),
    "Normal Niri configuration: /synthetic/normal-niri/config.kdl",
  );
  assert.match(
    await evaluate("byId('native-shared-help').textContent"),
    /Changes made through your shell.*do not reach this saved copy/,
  );
  assert.equal(requests.length, 0, "Displaying the sharing choice must not review or apply it");
  await evaluate(`
    byId('combo-name').value='Unsaved shared draft';
    byId('combo-name').dispatchEvent(new Event('change'));
    byId('native-fragment-preset').value='cascade';
    byId('native-fragment-preset').dispatchEvent(new Event('change'));
  `);
  const draft = await snapshot();
  await click("native-share");
  assert.match(await evaluate("byId('review-summary').textContent"), /Share saved settings/);
  assert.match(
    await evaluate("byId('review-summary').textContent"),
    /draft is not used or changed/,
  );
  assert.match(
    await evaluate("byId('review-summary').textContent"),
    /cannot independently confirm/,
  );
  assert.equal(await evaluate("byId('apply-selection').textContent"), "Apply shared settings");
  assert.equal(await evaluate("byId('review-files').children.length"), 1);
  if (process.env.NIRIFX_SHARED_STUDIO_SCREENSHOT) {
    await evaluate("window.scrollTo(0,0)");
    const shot = await browser.rpc("Page.captureScreenshot", { format: "png" });
    writeFileSync(process.env.NIRIFX_SHARED_STUDIO_SCREENSHOT, Buffer.from(shot.data, "base64"));
  }
  await click("cancel-review");
  assert.equal(
    requests.some((request) => request.path === "/shared-apply"),
    false,
  );
  assert.deepEqual(await snapshot(), draft);

  view.stale(true);
  await click("native-share");
  await click("apply-selection");
  assert.match(await evaluate("byId('error').textContent"), /Shared sources changed/);
  assert.equal(await evaluate("byId('native-share').disabled"), false);
  assert.equal(await evaluate("byId('apply-review').hidden"), true);
  assert.deepEqual(await snapshot(), draft);
  view.stale(false);
  await click("native-share");
  await click("apply-selection");
  assert.deepEqual(await snapshot(), draft);
  assert.match(await evaluate("byId('status').textContent"), /draft is unchanged/);
  assert.match(
    await evaluate("byId('status').textContent"),
    /has not been independently confirmed/,
  );
  assert.equal(await evaluate("byId('native-share').hidden"), true);
  assert.equal(await evaluate("byId('review-selection').disabled"), true);
  assert.equal(await evaluate("byId('restore-selection').disabled"), true);
  assert.equal(await evaluate("byId('store-profile').disabled"), false);
  assert.equal(await evaluate("byId('export').disabled"), false);
  assert.match(
    await evaluate("byId('native-session-help').textContent"),
    /close and reopen Studio/,
  );
  for (const request of requests.filter((item) => item.path.startsWith("/shared-"))) {
    assert.equal(request.token, "synthetic-shared-test");
    assert.deepEqual(
      request.body,
      request.path === "/shared-review" ? {} : { expected: "a".repeat(64) },
      "Sharing submits neither the unsaved document nor a browser-selected path",
    );
  }

  // Opening a new document simulates relaunch against the selected shared base.
  // A selector change alone must never switch the source of the existing editor.
  await view.reopen();
  assert.equal(
    await evaluate("byId('native-config-mode').textContent"),
    "Normal Niri settings are shared",
  );
  assert.equal(await evaluate("byId('review-selection').disabled"), false);
  assert.equal(await evaluate("byId('review-selection').textContent"), "Review & apply");
  assert.match(
    await evaluate("byId('native-session-help').textContent"),
    /Normal Niri settings are shared/,
  );
  assert.match(await evaluate("byId('native-running').textContent"), /not independently confirmed/);
  assert.match(
    await evaluate("byId('native-base').textContent"),
    /Preserve follows your normal Niri/,
  );
  assert.match(
    await evaluate("byId('pointer-description').textContent"),
    /shared Niri configuration/,
  );
  await click("review-selection");
  assert.equal(await evaluate("byId('apply-selection').textContent"), "Apply shared settings");
  assert.doesNotMatch(
    await evaluate("byId('review-summary').textContent"),
    /desktop stays unchanged/,
  );
  assert.match(
    await evaluate("byId('review-summary').textContent"),
    /already using these files reload automatically/,
  );
  await click("apply-selection");
  assert.match(await evaluate("byId('status').textContent"), /^Updated shared configuration files/);
  assert.match(
    await evaluate("byId('status').textContent"),
    /already using these files reload automatically/,
  );
  assert.doesNotMatch(
    await evaluate("byId('status').textContent"),
    /Applied to this desktop|current session stays unchanged/,
  );
  view.unchanged(true);
  await click("review-selection");
  assert.match(
    await evaluate("byId('review-summary').textContent"),
    /files already match.*not been independently confirmed/s,
  );
  await click("cancel-review");
  view.unchanged(false);
  assert.equal(await evaluate("byId('native-recovery').disabled"), false);
  await click("native-recovery");
  assert.equal(await evaluate("byId('apply-selection').textContent"), "Select for next login");
  assert.match(
    await evaluate("byId('review-summary').textContent"),
    /normal Niri settings.*stay unchanged/,
  );
  await click("cancel-review");
  assert.equal(
    requests.some((request) => request.path === "/recovery-apply"),
    false,
  );
  const recoveryDraft = await snapshot();
  await click("native-recovery");
  await click("apply-selection");
  assert.deepEqual(await snapshot(), recoveryDraft);
  assert.match(
    await evaluate("byId('status').textContent"),
    /next NiriFX login.*Normal Niri settings were not changed/,
  );
  assert.equal(await evaluate("byId('review-selection').disabled"), true);
  assert.equal(await evaluate("byId('native-recovery').hidden"), true);
  assert.equal(await evaluate("byId('store-profile').disabled"), false);
  assert.deepEqual(requests.find((request) => request.path === "/recovery-apply").body, {
    expected: "a".repeat(64),
  });
  await assertTransactionMotion(browser);
});

test("shared setup needs a launch-scoped source and an applied recipe", async (t) => {
  for (const options of [{ configured: false }, { saved: false }])
    await t.test(JSON.stringify(options), async (t) => {
      const view = await sharedStudioFixture(t, options);
      const { evaluate } = view.browser;
      assert.equal(await evaluate("byId('native-share').disabled"), true);
      if (options.configured === false) {
        assert.equal(await evaluate("byId('native-share').hidden"), true);
        assert.equal(await evaluate("byId('native-shared-settings').hidden"), false);
        assert.match(
          await evaluate("byId('native-shared-source').textContent"),
          /No normal Niri configuration was connected/,
        );
      } else {
        assert.equal(await evaluate("byId('native-share').hidden"), false);
        assert.match(await evaluate("byId('native-shared-help').textContent"), /apply them first/);
      }
      await view.click("native-share");
      assert.equal(
        view.requests.some((request) => request.path.startsWith("/shared-")),
        false,
      );
    });
});

test("simple Studio previews one action while preserving the rest of the combo", async () => {
  const html = execFileSync(
    "python3",
    [
      "-c",
      'from niri_fx.preview import preview_document; from niri_fx.presets import PRESETS; print(preview_document(PRESETS["balanced"], hosted=True))',
    ],
    { cwd: projectRoot, encoding: "utf8", maxBuffer: 4 * 1024 * 1024 },
  );
  const server = createServer((_request, response) => {
    response.writeHead(200, { "Content-Type": "text/html" });
    response.end(html);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await launchBrowser();
  try {
    await browser.navigate(`http://127.0.0.1:${server.address().port}/?breakup=0`, {
      width: 1320,
      height: 960,
    });
    const { evaluate } = browser;
    await evaluate(`
      window.simpleFrames = new Map(); window.simpleFrameId = 0;
      window.requestAnimationFrame = callback => {
        simpleFrames.set(++simpleFrameId, callback); return simpleFrameId;
      };
      window.cancelAnimationFrame = id => simpleFrames.delete(id);
    `);
    const action = (name) =>
      evaluate(`document.querySelector('[data-library-action="${name}"]').click()`);
    const choose = (name) => evaluate(`document.querySelector('[data-style="${name}"]').click()`);
    const keyboardActivate = async () => {
      for (const type of ["keyDown", "keyUp"])
        await browser.rpc("Input.dispatchKeyEvent", {
          type,
          key: "Enter",
          code: "Enter",
          windowsVirtualKeyCode: 13,
          text: "\r",
          unmodifiedText: "\r",
        });
    };
    assert.equal(await evaluate('byId("combo-options").open'), false);
    assert.equal(await evaluate('byId("transfer-options").open'), false);
    assert.equal(await evaluate('byId("export").checkVisibility()'), true);
    assert.equal(
      await evaluate('document.querySelector("label[for=combo-pointer-mode]").textContent'),
      "Pointer wobble",
    );
    assert.equal(await evaluate('byId("pointer-movement-note").hidden'), true);
    assert.equal(await evaluate('byId("pointer-movement-note").textContent'), "");
    assert.equal(
      await evaluate(
        'document.querySelector("[data-library-action=open]").getAttribute("aria-pressed")',
      ),
      "true",
    );
    assert.equal(await evaluate('document.querySelector("[data-style=fragment-flow]")'), null);
    await choose("explosion");
    assert.equal(await evaluate("editingAction"), "open");
    assert.equal(await evaluate("simpleFrames.size"), 1, "Selecting a card starts playback");
    assert.deepEqual(
      await evaluate("effectDocument().actions.open"),
      await evaluate("({...catalog.presets.explosion,resize:false})"),
    );
    const opening = await evaluate("effectDocument().actions.open");
    await action("close");
    await choose("frost-vanish");
    assert.equal(await evaluate("editingAction"), "close");
    assert.deepEqual(await evaluate("effectDocument().actions.open"), opening);
    const closing = await evaluate("effectDocument().actions.close");
    await action("resize");
    assert.equal(await evaluate('document.querySelector("[data-style=frost-vanish]")'), null);
    await choose("spring-wobble");
    assert.equal(await evaluate("mode"), "resize");
    assert.equal(await evaluate("effectDocument().actions.resize.family"), "elastic");
    await action("movement");
    await choose("fragment-wake");
    assert.equal(await evaluate("mode"), "movement");
    assert.equal(await evaluate("effectDocument().actions.movement.family"), "fragments");
    const movement = await evaluate("effectDocument().actions.movement");
    await action("swap");
    await evaluate('document.querySelector("[data-style=pixel-relay]").focus()');
    const scroll = await evaluate('byId("library-results").scrollTop');
    await keyboardActivate();
    assert.equal(await evaluate("editingAction"), "swap");
    assert.equal(await evaluate("mode"), "movement");
    assert.deepEqual(
      await evaluate("effectDocument().actions.swap"),
      await evaluate('({...catalog.presets["pixel-relay"], resize:false})'),
    );
    assert.deepEqual(await evaluate("effectDocument().actions.movement"), movement);
    assert.equal(await evaluate("document.activeElement.dataset.style"), "pixel-relay");
    assert.equal(await evaluate('byId("library-results").scrollTop'), scroll);
    for (const direction of ["left", "right", "up", "down"])
      for (const progress of [0, 1000]) {
        const bounds = await evaluate(`(() => {
          byId("pause").click();
          byId("movement-direction").value=${JSON.stringify(direction)};
          byId("movement-direction").dispatchEvent(new Event("change"));
          byId("progress").value=${progress};
          byId("progress").dispatchEvent(new Event("input"));
          const canvas=byId("stage"),gl=canvas.getContext("webgl");
          const pixels=new Uint8Array(canvas.width*canvas.height*4);
          gl.readPixels(0,0,canvas.width,canvas.height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
          let left=canvas.width,right=-1,bottom=canvas.height,top=-1;
          for(let y=0;y<canvas.height;y++)for(let x=0;x<canvas.width;x++)
            if(pixels[(y*canvas.width+x)*4+3]>4){
              left=Math.min(left,x);right=Math.max(right,x);
              bottom=Math.min(bottom,y);top=Math.max(top,y);
            }
          return {left,right,bottom,top,width:canvas.width,height:canvas.height};
        })()`);
        assert(bounds.right > bounds.left, "Swap endpoints must contain visible windows");
        assert(
          bounds.left > 0 &&
            bounds.right < bounds.width - 1 &&
            bounds.bottom > 0 &&
            bounds.top < bounds.height - 1,
          `${direction} swap endpoint ${progress} must leave a visible margin on every canvas edge`,
        );
      }
    await evaluate('byId("movement-direction").value="right"');
    if (process.env.NIRIFX_SIMPLE_STUDIO_SCREENSHOT) {
      await evaluate(`
        byId("pause").click();seed=.43;
        byId("progress").value=450;byId("progress").dispatchEvent(new Event("input"));
        window.scrollTo(0, 0);
      `);
      const shot = await browser.rpc("Page.captureScreenshot", { format: "png" });
      writeFileSync(
        process.env.NIRIFX_SIMPLE_STUDIO_SCREENSHOT.replace(/\.png$/, "-swap.png"),
        Buffer.from(shot.data, "base64"),
      );
    }
    await evaluate('document.querySelector("[data-favorite=pixel-relay]").focus()');
    await keyboardActivate();
    assert.equal(await evaluate("document.activeElement.dataset.favorite"), "pixel-relay");
    assert.match(await evaluate('document.activeElement.getAttribute("aria-label")'), /^Remove/);
    await action("movement");
    await evaluate('byId("library-preserve").click()');
    assert.equal(await evaluate('byId("pointer-kdl").hidden'), false);
    const nativeExport = await evaluate(`(() => {
      const originalDownload = download;
      let exported;
      try {
        download = (name, text) => { exported = { name, text }; };
        byId("pointer-kdl").click();
      } finally { download = originalDownload; }
      return exported;
    })()`);
    assert.equal(nativeExport.name, "nirifx-session.kdl");
    assert.match(nativeExport.text, /window-swap\s*\{/);
    assert.doesNotMatch(nativeExport.text, /window-movement\s*\{|pointer-wobble/);
    await choose("fragment-wake");
    await action("swap");
    await evaluate('byId("library-off").click()');
    assert.equal(await evaluate("effectDocument().actions.swap"), "off");
    await evaluate('byId("library-preserve").click()');
    assert.equal(await evaluate("effectDocument().actions.swap ?? null"), null);
    await evaluate('byId("undo").click()');
    assert.equal(await evaluate("effectDocument().actions.swap"), "off");
    assert.deepEqual(await evaluate("effectDocument().actions.movement"), movement);
    assert.deepEqual(await evaluate("effectDocument().actions.open"), opening);
    assert.deepEqual(await evaluate("effectDocument().actions.close"), closing);
    await action("movement");
    await evaluate('byId("library-off").click()');
    assert.equal(await evaluate("effectDocument().actions.movement"), "off");
    await evaluate('byId("library-preserve").click()');
    assert.equal(await evaluate("effectDocument().actions.movement"), null);
    await evaluate('byId("undo").click()');
    assert.equal(await evaluate("effectDocument().actions.movement"), "off");
    const before = await evaluate("effectDocument()");
    await action("close");
    await evaluate(`
      byId("reduced-motion").checked = true;
      byId("reduced-motion").dispatchEvent(new Event("change"));
      byId("library-replay").click();
    `);
    assert.equal(await evaluate("simpleFrames.size"), 0);
    assert.equal(await evaluate("progress"), 1);
    assert.deepEqual(await evaluate("effectDocument()"), before);
    if (process.env.NIRIFX_SIMPLE_STUDIO_SCREENSHOT) {
      await action("open");
      await evaluate("window.scrollTo(0, 0)");
      const shot = await browser.rpc("Page.captureScreenshot", { format: "png" });
      writeFileSync(process.env.NIRIFX_SIMPLE_STUDIO_SCREENSHOT, Buffer.from(shot.data, "base64"));
    }
    await browser.rpc("Emulation.setDeviceMetricsOverride", {
      width: 520,
      height: 960,
      deviceScaleFactor: 1,
      mobile: false,
    });
    assert.equal(await evaluate("document.documentElement.scrollWidth <= innerWidth"), true);
    assert.equal(await evaluate('byId("export").checkVisibility()'), true);
    if (process.env.NIRIFX_SIMPLE_STUDIO_SCREENSHOT) {
      const narrow = await browser.rpc("Page.captureScreenshot", { format: "png" });
      writeFileSync(
        process.env.NIRIFX_SIMPLE_STUDIO_SCREENSHOT.replace(/\.png$/, "-narrow.png"),
        Buffer.from(narrow.data, "base64"),
      );
    }
    await evaluate('byId("studio-about").open=true');
    assert.equal(await evaluate("document.documentElement.scrollWidth <= innerWidth"), true);
    if (process.env.NIRIFX_SIMPLE_STUDIO_SCREENSHOT) {
      await evaluate('byId("studio-identity").scrollIntoView({block:"center"})');
      const footer = await browser.rpc("Page.captureScreenshot", { format: "png" });
      writeFileSync(
        process.env.NIRIFX_SIMPLE_STUDIO_SCREENSHOT.replace(/\.png$/, "-about.png"),
        Buffer.from(footer.data, "base64"),
      );
    }
    await evaluate('byId("studio-about").open=false');
    await action("combo");
    await choose("fragment-flow");
    assert.equal(await evaluate("effectDocument().name"), "Fragment Flow");
    assert.equal(await evaluate('byId("error").textContent'), "");
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
});

test("library combines supported actions, preserves edits and saves offline without activation", async () => {
  const html = execFileSync(
    "python3",
    [
      "-c",
      'from niri_fx.preview import preview_document; from niri_fx.presets import PRESETS; print(preview_document(PRESETS["balanced"], hosted=True))',
    ],
    { cwd: projectRoot, encoding: "utf8", maxBuffer: 4 * 1024 * 1024 },
  );
  const requests = [];
  const server = createServer((request, response) => {
    requests.push(request.url);
    response.writeHead(200, { "Content-Type": "text/html" });
    response.end(html);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  // These assertions exercise Library transactions, not intermediate pixels.
  // Keep the real shader at its intact endpoint; the rendering suite separately
  // checks intermediate frames without accumulating software GPU work here.
  const url = `http://127.0.0.1:${server.address().port}/studio/?breakup=0`;
  const browser = await launchBrowser();
  try {
    await reduceTransactionMotion(browser);
    await browser.rpc("Page.addScriptToEvaluateOnNewDocument", {
      source: `window.libraryBootErrors=[];addEventListener('error',event=>window.libraryBootErrors.push(String(event.message).replace(/https?:\\/\\/\\S+/g,'[url]')));`,
    });
    let loaded = false;
    async function reload() {
      try {
        if (loaded) await assertTransactionMotion(browser);
        await browser.navigate(url);
        loaded = true;
        await assertTransactionMotion(browser);
      } catch (error) {
        console.error(
          "Library reload diagnostics",
          await browser.evaluate(`({
          readyState: document.readyState,
          title: document.title,
          scripts: Array.from(document.scripts, script=>({type:script.type,length:script.textContent.length})),
          errors: window.libraryBootErrors,
          bodyLength: document.body?.textContent.length,
          globals: (()=>{
            const result={};
            for(const expression of ["createEffectCore","createFxLibrary","byId","catalog","parameters","workspace"]){
              try{result[expression]=typeof eval(expression)}
              catch(error){result[expression]=String(error.message)}
            }
            return result;
          })(),
          attributes: {...document.documentElement.dataset},
          storageKeys: Object.keys(localStorage),
          performance: performance.getEntriesByType("navigation").map(entry=>({
            type:entry.type,fetch:entry.fetchStart,responseStart:entry.responseStart,
            responseEnd:entry.responseEnd,interactive:entry.domInteractive,
            dom:entry.domContentLoadedEventEnd,load:entry.loadEventEnd
          })),
          visibility: document.visibilityState
        })`),
        );
        throw error;
      }
    }
    await reload();
    const evaluate = browser.evaluate;
    const settle = (dialogOpen = false) =>
      evaluate(`new Promise((resolve,reject)=>{
        const started=Date.now();
        function check(){
          if(!byId("store-profile").disabled&&!byId("profile-confirm").disabled&&byId("profile-dialog").open===${dialogOpen})resolve();
          else if(Date.now()-started>5000)reject(new Error("Profile operation did not settle"));
          else setTimeout(check,30);
        }
        // Dialog close events are queued; let them run before another operation.
        setTimeout(check,0);
      })`);
    assert.equal(await evaluate("document.documentElement.dataset.workspace"), "library");
    assert.equal(await evaluate('byId("activation-controls").hidden'), true);
    assert.equal(await evaluate('getComputedStyle(byId("save-target")).display'), "none");
    assert.equal(await evaluate("effectDocument().effect.resize"), false);
    await evaluate(
      'document.querySelector("[data-library-action=combo]").click();document.querySelector("[data-style=fragments-motion]").click()',
    );
    assert.equal(await evaluate("effectDocument().actions.resize"), null);
    await evaluate(
      'byId("combo-close").value="frost-vanish";byId("combo-close").dispatchEvent(new Event("change"))',
    );
    assert.equal(await evaluate("progress"), 1, "Reduced-motion Close renders its endpoint");
    await assertTransactionMotion(browser);
    assert.equal(await evaluate("effectDocument().actions.open.fragment_mix"), 0.5);
    assert.equal(await evaluate("effectDocument().actions.close.family"), "dissolve");
    assert.equal(await evaluate('byId("combo-mode").value'), "mixed");
    await evaluate(
      'byId("combo-resize").value="spring-wobble";byId("combo-resize").dispatchEvent(new Event("change"));byId("combo-movement").value="fragment-wake";byId("combo-movement").dispatchEvent(new Event("change"))',
    );
    const combo = await evaluate("effectDocument()");
    assert.equal(combo.actions.resize.family, "elastic");
    assert.equal(combo.actions.movement.family, "fragments");
    assert.equal(await evaluate('kdlDocument().includes("window-movement")'), false);
    assert.equal(await evaluate('kdlDocument().includes("window-resize")'), true);
    assert.equal(
      await evaluate('Array.from(byId("combo-resize").options).some(o=>o.value==="frost-vanish")'),
      false,
    );
    await evaluate(
      'byId("combo-mode").value="same";byId("combo-mode").dispatchEvent(new Event("change"))',
    );
    const same = await evaluate("effectDocument()");
    for (const action of ["close", "resize", "movement"])
      assert.deepEqual(same.actions[action], same.actions.open);
    await evaluate('byId("undo").click()');
    assert.deepEqual(await evaluate("effectDocument()"), combo);
    await evaluate(
      'byId("show-editor").click();byId("spin").value=210;byId("spin").dispatchEvent(new Event("input"));byId("show-library").click()',
    );
    assert.equal(await evaluate('byId("combo-movement").value'), "custom");
    assert.equal(await evaluate("effectDocument().actions.movement.spin"), 210);
    await evaluate(
      'byId("combo-name").value="Night Motion";byId("combo-name").dispatchEvent(new Event("change"));byId("store-profile").click()',
    );
    assert.equal(await evaluate('byId("profile-dialog").open'), true);
    await evaluate('byId("profile-confirm").click()');
    await settle();
    await reload();
    await evaluate(
      'byId("library-collection").value="customs";byId("library-collection").dispatchEvent(new Event("change"))',
    );
    assert.equal(
      await evaluate(
        'document.querySelector("[data-style=custom-night-motion]").textContent.includes("Night Motion")',
      ),
      true,
    );
    await evaluate('document.querySelector("[data-style=custom-night-motion]").click()');
    assert.equal(await evaluate("effectDocument().actions.movement.spin"), 210);
    await evaluate(
      'byId("combo-mode").value="same";byId("combo-mode").dispatchEvent(new Event("change"));byId("combo-same").value="frost-vanish";byId("combo-same").dispatchEvent(new Event("change"))',
    );
    const unsupported = await evaluate("effectDocument()");
    assert.equal(unsupported.actions.resize.family, "fragments");
    assert.equal(unsupported.actions.movement.family, "fragments");
    assert.deepEqual(unsupported.actions.open, unsupported.actions.close);
    await evaluate(
      'byId("combo-name").value="";byId("combo-name").dispatchEvent(new Event("change"))',
    );
    assert.equal(await evaluate("effectDocument().name"), "Night Motion");
    assert.match(await evaluate('byId("error").textContent'), /Name must/);
    // Manage the saved document rather than the unsaved edits above.
    await evaluate('document.querySelector("[data-style=custom-night-motion]").click()');
    assert.equal(await evaluate('byId("rename-profile").hidden'), false);
    await evaluate('byId("copy-profile").click()');
    assert.equal(await evaluate('byId("profile-save-name").value'), "Night Motion copy");
    await evaluate('byId("profile-confirm").click()');
    await settle();
    assert.equal(await evaluate("effectDocument().name"), "Night Motion copy");
    await evaluate(
      `document.querySelector('button[aria-label="Favorite Night Motion copy"]').click()`,
    );
    // A dialog close event can arrive after another dialog has already opened.
    // Exercise that ordering directly instead of relying on browser frame timing.
    await evaluate(`new Promise(resolve=>{
      byId("profile-dialog").addEventListener("close",()=>resolve(),{once:true});
      byId("rename-profile").click();
      byId("profile-cancel").click();
      byId("rename-profile").click();
    })`);
    await evaluate(
      'byId("profile-save-name").value="Night_Motion";byId("profile-confirm").click()',
    );
    await settle(true);
    assert.match(await evaluate('byId("profile-dialog-error").textContent'), /already belongs/);
    assert.equal(await evaluate('byId("profile-dialog").open'), true);
    await evaluate(
      'byId("profile-save-name").value="Evening Motion";byId("profile-confirm").click()',
    );
    await settle();
    assert.equal(await evaluate("effectDocument().name"), "Evening Motion");
    assert(
      (await evaluate('JSON.parse(localStorage.getItem("nirifx-favorites"))')).includes(
        "custom-evening-motion",
      ),
    );
    assert(
      !(await evaluate('JSON.parse(localStorage.getItem("nirifx-favorites"))')).includes(
        "custom-night-motion-copy",
      ),
    );
    const shelf = await evaluate('JSON.parse(localStorage.getItem("nirifx-my-profiles"))');
    assert(shelf["custom-night-motion"]);
    assert(shelf["custom-evening-motion"]);
    assert(!shelf["custom-night-motion-copy"]);
    await evaluate('byId("remove-profile").click();byId("profile-cancel").click()');
    await settle();
    assert.deepEqual(
      await evaluate('JSON.parse(localStorage.getItem("nirifx-my-profiles"))'),
      shelf,
    );
    await evaluate('byId("remove-profile").click();byId("profile-confirm").click()');
    await settle();
    assert.equal(await evaluate('byId("remove-profile").hidden'), true);
    assert(
      !(await evaluate('JSON.parse(localStorage.getItem("nirifx-favorites"))')).includes(
        "custom-evening-motion",
      ),
    );
    assert.equal(await evaluate("effectDocument().name"), "Evening Motion");
    assert.equal(
      await evaluate('Object.keys(JSON.parse(localStorage.getItem("nirifx-my-profiles"))).length'),
      1,
    );
    // A damaged entry does not hide other profiles or get discarded on save.
    await evaluate(
      'localStorage.setItem("nirifx-my-profiles",JSON.stringify({...JSON.parse(localStorage.getItem("nirifx-my-profiles")),"custom-damaged":{schema:99}}))',
    );
    await reload();
    await evaluate(
      'byId("library-collection").value="customs";byId("library-collection").dispatchEvent(new Event("change"));document.querySelector("[data-style=custom-night-motion]").click();byId("store-profile").click()',
    );
    assert.equal(await evaluate('byId("profile-confirm").textContent'), "Replace saved profile");
    assert.match(await evaluate('byId("library-warning").textContent'), /could not be read/);
    const changed = await evaluate(
      'let shelf=JSON.parse(localStorage.getItem("nirifx-my-profiles"));shelf["custom-night-motion"].actions.close=shelf["custom-night-motion"].actions.open;localStorage.setItem("nirifx-my-profiles",JSON.stringify(shelf));shelf',
    );
    await evaluate('byId("profile-confirm").click()');
    await settle(true);
    assert.match(await evaluate('byId("profile-dialog-error").textContent'), /another tab/);
    assert.deepEqual(
      await evaluate('JSON.parse(localStorage.getItem("nirifx-my-profiles"))'),
      changed,
    );
    await evaluate('byId("profile-cancel").click()');
    assert(requests.every((path) => path === "/studio/?breakup=0" || path === "/favicon.ico"));
    assert.equal(await evaluate('byId("error").textContent'), "");
    await assertTransactionMotion(browser);
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
});

test("installed Library UI manages its JSON shelf through the authenticated server", async () => {
  const root = mkdtempSync(join(tmpdir(), "nirifx-library-"));
  const config = join(root, "config.kdl");
  writeFileSync(config, "animations {}\n");
  const process = spawn(
    "python3",
    [
      "-m",
      "niri_fx",
      "studio",
      "--target",
      "standalone",
      "--config",
      config,
      "--state",
      join(root, "state"),
      "--no-browser",
    ],
    { cwd: projectRoot, stdio: ["ignore", "pipe", "pipe"] },
  );
  let browser;
  try {
    const url = await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error("Studio did not start")), 20000);
      let output = "";
      process.stdout.on("data", (chunk) => {
        output += chunk;
        const match = output.match(/NiriFX Studio: (http:\/\/127\.0\.0\.1:[^\s]+)/);
        if (match) {
          clearTimeout(timeout);
          resolve(match[1]);
        }
      });
      process.once("error", (error) => {
        clearTimeout(timeout);
        reject(error);
      });
      process.once("exit", () => {
        clearTimeout(timeout);
        reject(new Error("Studio exited before its session was ready"));
      });
    });
    browser = await launchBrowser();
    await browser.navigate(url);
    const { evaluate } = browser;
    const settle = () =>
      evaluate(
        "new Promise((resolve,reject)=>{const started=Date.now();function check(){if(!byId('profile-dialog').open&&!byId('store-profile').disabled)resolve();else if(byId('profile-dialog-error').textContent)reject(new Error(byId('profile-dialog-error').textContent));else if(Date.now()-started>5000)reject(new Error('Profile operation timed out'));else setTimeout(check,30)}check()})",
      );
    await evaluate(
      'byId("store-profile").click();byId("profile-save-name").value="Local Night";byId("profile-confirm").click()',
    );
    await settle();
    const folder = join(root, "state/profiles");
    const saved = JSON.parse(readFileSync(join(folder, "local-night.json")));
    assert.equal(saved.name, "Local Night");
    // Reload reads server fingerprints and exposes only owned shelf entries.
    await browser.navigate(url);
    await evaluate(
      'new Promise(resolve=>{function check(){if(!byId("copy-profile").hidden)resolve();else setTimeout(check,30)}byId("library-collection").value="customs";byId("library-collection").dispatchEvent(new Event("change"));function select(){const card=document.querySelector("[data-style=custom-local-night]");if(card){card.click();check()}else setTimeout(select,30)}select()})',
    );
    await evaluate('byId("copy-profile").click();byId("profile-confirm").click()');
    await settle();
    await evaluate(
      'byId("rename-profile").click();byId("profile-save-name").value="Local Dawn";byId("profile-confirm").click()',
    );
    await settle();
    assert(readdirSync(folder).includes("local-dawn.json"));
    assert(!readdirSync(folder).includes("local-night-copy.json"));
    await evaluate('byId("remove-profile").click();byId("profile-confirm").click()');
    await settle();
    assert.deepEqual(
      readdirSync(folder).filter((name) => name.endsWith(".json")),
      ["local-night.json"],
    );
    assert.equal(readFileSync(config, "utf8"), "animations {}\n");
    assert.equal(await evaluate('byId("error").textContent'), "");
  } finally {
    if (browser) await browser.close();
    const stopped = new Promise((resolve) => process.once("exit", resolve));
    if (process.exitCode === null) {
      process.kill("SIGTERM");
      await stopped;
    }
    rmSync(root, { recursive: true, force: true });
  }
});

test("all action modes survive editing, shared styles, preview, Undo and saved JSON", async () => {
  const html = execFileSync(
    "python3",
    [
      "-c",
      'from niri_fx.preview import preview_document; from niri_fx.presets import PRESETS; print(preview_document(PRESETS["balanced"], hosted=True))',
    ],
    { cwd: projectRoot, encoding: "utf8", maxBuffer: 4 * 1024 * 1024 },
  );
  const server = createServer((_request, response) => {
    response.writeHead(200, { "Content-Type": "text/html" });
    response.end(html);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const browser = await launchBrowser();
  const url = `http://127.0.0.1:${server.address().port}/?breakup=0`;
  try {
    await browser.navigate(url);
    const evaluate = browser.evaluate;
    const setMode = (action, mode) =>
      evaluate(
        `byId('combo-${action}-mode').value='${mode}';byId('combo-${action}-mode').dispatchEvent(new Event('change'))`,
      );
    for (const [action, mode] of Object.entries({
      open: "off",
      close: "preserve",
      resize: "off",
      movement: "preserve",
      pointer: "off",
    }))
      await setMode(action, mode);
    const original = await evaluate("effectDocument()");
    assert.equal(original.schema, 2);
    assert.deepEqual(original.actions, { open: "off", close: null, resize: "off", movement: null });
    assert.equal(original.pointer.strength, 0);
    assert.equal(await evaluate('byId("combo-open").disabled'), true);
    assert.equal(await evaluate('byId("combo-open-tune").disabled'), true);
    assert.deepEqual(
      await evaluate("decodeShareDocument(encodeShareDocument(effectDocument()))"),
      original,
    );
    await setMode("close", "style");
    await evaluate(
      'byId("combo-mode").value="same";byId("combo-mode").dispatchEvent(new Event("change"));byId("combo-same").value="spring-wobble";byId("combo-same").dispatchEvent(new Event("change"))',
    );
    const shared = await evaluate("effectDocument()");
    assert.equal(shared.actions.open, "off");
    assert.equal(shared.actions.close.family, "elastic");
    assert.equal(shared.actions.resize, "off");
    assert.equal(shared.actions.movement, null);
    await evaluate(
      'byId("show-editor").click();byId("action").value="close";byId("action").dispatchEvent(new Event("change"));byId("action-mode").value="preserve";byId("action-mode").dispatchEvent(new Event("change"))',
    );
    assert.equal(await evaluate("effectDocument().actions.close"), null);
    assert.match(await evaluate('byId("caption").textContent'), /underlying desktop or shell/);
    assert.equal(await evaluate('byId("family").disabled'), true);
    await evaluate(
      'byId("action-mode").value="style";byId("action-mode").dispatchEvent(new Event("change"))',
    );
    assert.deepEqual(await evaluate("effectDocument().actions.close"), shared.actions.close);
    await evaluate('byId("undo").click()');
    assert.equal(await evaluate('byId("action-mode").value'), "preserve");
    await evaluate('byId("redo").click()');
    assert.equal(await evaluate('byId("action-mode").value'), "style");
    for (const mode of ["preserve", "off"]) {
      for (const action of ["open", "close", "resize", "movement"]) await setMode(action, mode);
      await evaluate(
        'byId("preview-combo").click();niriFxComboPreview.seek(niriFxComboPreview.currentPlan.totalMs)',
      );
      assert.equal(await evaluate("document.documentElement.dataset.shaderStatus"), "ready");
      assert.equal(await evaluate("comboPreviewFrame.visible"), mode === "preserve");
      assert.equal(
        await evaluate(
          '(()=>{const gl=byId("stage").getContext("webgl"),p=new Uint8Array(4);gl.readPixels(600,380,1,1,gl.RGBA,gl.UNSIGNED_BYTE,p);return p[3]})()',
        ),
        mode === "preserve" ? 255 : 0,
      );
    }
    await setMode("open", "preserve");
    await evaluate(
      'byId("combo-name").value="Mode choices";byId("combo-name").dispatchEvent(new Event("change"));byId("store-profile").click();byId("profile-confirm").click()',
    );
    await evaluate(
      'new Promise((resolve,reject)=>{const start=Date.now();function check(){if(!byId("profile-dialog").open)resolve();else if(Date.now()-start>5000)reject(new Error(byId("profile-dialog-error").textContent||"Save timeout"));else setTimeout(check,30)}check()})',
    );
    const saved = await evaluate("effectDocument()");
    await browser.navigate(url);
    await evaluate(
      'byId("library-collection").value="customs";byId("library-collection").dispatchEvent(new Event("change"));document.querySelector("[data-style=custom-mode-choices]").click()',
    );
    assert.deepEqual(await evaluate("effectDocument()"), saved);
    assert.equal(await evaluate('byId("combo-open-mode").value'), "preserve");
    assert.equal(await evaluate('byId("combo-close-mode").value'), "off");
    assert.equal(await evaluate('byId("combo-pointer-mode").value'), "off");
    assert.equal(await evaluate('byId("error").textContent'), "");
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
});

test("managed Studio reviews immutable recipes, cancellation, stale selection and rollback", async () => {
  const environment = { ...process.env, PYTHONDONTWRITEBYTECODE: "1" };
  for (const key of ["NIRI_SOCKET", "WAYLAND_DISPLAY", "DISPLAY", "DBUS_SESSION_BUS_ADDRESS"])
    delete environment[key];
  const child = spawn(
    "python3",
    [
      "-c",
      `
import json, signal, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "tests"))
from test_native_library import NativeLibraryFixture
from niri_fx.cli import main
fixture = NativeLibraryFixture()
fixture.setUp()
signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
print("Fixture: " + json.dumps({"root": str(fixture.root), "native": str(fixture.native), "base": fixture.base}), flush=True)
try:
    main(["studio", "--target", "native", "--native-root", str(fixture.native),
        "--state", str(fixture.args.state), "--no-browser", "--preset", "balanced", "--spin", "50"])
finally:
    fixture.doCleanups()
`,
    ],
    { cwd: projectRoot, env: environment, stdio: ["ignore", "pipe", "pipe"] },
  );
  let browser;
  try {
    const { url, fixture } = await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("Managed Studio startup timed out")), 20000);
      let output = "";
      child.stdout.on("data", (chunk) => {
        output += chunk;
        const url = output.match(/NiriFX Studio: (http:\/\/127\.0\.0\.1:[^\s]+)/)?.[1];
        const fixture = output.match(/Fixture: (.+)/)?.[1];
        if (url && fixture) {
          clearTimeout(timer);
          resolve({ url, fixture: JSON.parse(fixture) });
        }
      });
      child.once("error", (error) => {
        clearTimeout(timer);
        reject(error);
      });
      child.once("exit", () => {
        clearTimeout(timer);
        reject(new Error("Managed Studio stopped before readiness"));
      });
    });
    const files = (folder) =>
      Object.fromEntries(
        readdirSync(folder, { recursive: true, withFileTypes: true })
          .filter((entry) => entry.isFile())
          .map((entry) => {
            const path = join(entry.parentPath, entry.name);
            return [path.slice(folder.length), readFileSync(path).toString("base64")];
          }),
      );
    const selector = join(fixture.native, "selection.json");
    const selection = () => JSON.parse(readFileSync(selector));
    const originalBundles = files(join(fixture.native, "bundles"));
    browser = await launchBrowser({ requestTimeout: 20000 });
    await reduceTransactionMotion(browser);
    await browser.navigate(url + "&breakup=0", { width: 1440, height: 1080 });
    await assertTransactionMotion(browser);
    const { evaluate } = browser;
    const wait = (expression) =>
      evaluate(`new Promise((resolve,reject)=>{
      const started=Date.now();function check(){if(${expression})resolve();else if(Date.now()-started>7000)reject(new Error('Managed operation timeout: '+byId('error').textContent));else setTimeout(check,30)}check();
    })`);
    const settle = () => wait("!byId('review-selection').disabled");
    const diagnose = async (action, operation) => {
      try {
        return await operation();
      } catch (error) {
        throw new Error(`Managed Studio ${action}: ${error.message}`, { cause: error });
      }
    };
    const click = (id) =>
      diagnose(`click ${id}`, () => browser.callFunction("function(id){byId(id).click()}", [id]));
    const choose = (id, value) =>
      diagnose(`change ${id}`, () =>
        browser.callFunction(
          "function(id,value){byId(id).value=value;byId(id).dispatchEvent(new Event('change'))}",
          [id, value],
        ),
      );
    await wait("byId('active-look').textContent.startsWith('Next login: ')");
    assert.equal(
      await evaluate('byId("studio-build").textContent'),
      await evaluate("catalog.studio.build"),
    );
    assert.match(
      await evaluate('byId("studio-mode-help").textContent'),
      /Local Studio.*Close and reopen Studio/s,
    );
    assert.equal(await evaluate("byId('native-session').hidden"), false);
    assert.equal(await evaluate("byId('save-target').hidden"), true);
    assert.equal(await evaluate("effectDocument().effect.spin"), 50);
    assert.equal(await evaluate("byId('preset').value"), "");
    assert.equal(await evaluate("catalog.connection.pointer"), undefined);
    await evaluate('document.querySelector("[data-library-action=movement]").click()');
    assert.equal(await evaluate('document.querySelectorAll("[data-fragment]").length'), 3);
    await evaluate('document.querySelector("[data-fragment=gentle]").click()');
    assert.equal(await evaluate("byId('native-fragment-preset').value"), "gentle");
    assert.equal(await evaluate("effectDocument().actions.movement.family"), "fragments");
    await evaluate(
      'document.querySelector("[data-library-action=combo]").click();document.querySelector("[data-style=fragments-motion]").click()',
    );
    await choose("combo-open-mode", "preserve");
    await choose("combo-close", "frost-vanish");
    await choose("combo-resize-mode", "off");
    await choose("native-fragment-preset", "gentle");
    await choose("native-fragment-preset", "tear");
    await click("undo");
    assert.equal(await evaluate("byId('native-fragment-preset').value"), "gentle");
    assert.deepEqual(
      await evaluate("effectDocument().actions.movement"),
      await evaluate("catalog.fragment_presets.gentle.effect"),
    );
    await click("redo");
    assert.equal(await evaluate("byId('native-fragment-preset').value"), "tear");
    await choose("native-fragment-preset", "");
    assert.equal(await evaluate("byId('native-fragment-preset').value"), "");
    await click("undo");
    assert.equal(await evaluate("byId('native-fragment-preset').value"), "tear");
    await click("redo");
    assert.equal(await evaluate("byId('native-fragment-preset').value"), "");
    await choose("native-fragment-preset", "cascade");
    assert.deepEqual(
      await evaluate("effectDocument().actions.movement"),
      await evaluate("catalog.fragment_presets.cascade.effect"),
    );
    await choose("combo-pointer-mode", "style");
    await choose("combo-pointer", "rubber-sheet");
    assert.equal(await evaluate("byId('pointer-movement-note').hidden"), false);
    assert.match(
      await evaluate("byId('pointer-movement-note').textContent"),
      /continuous fragments take priority over whole-window wobble/,
    );
    await choose("combo-pointer-mode", "off");
    assert.equal(await evaluate("effectDocument().pointer.strength"), 0);
    assert.equal(await evaluate("byId('native-fragment-preset').value"), "cascade");
    assert.deepEqual(
      await evaluate("effectDocument().actions.movement"),
      await evaluate("catalog.fragment_presets.cascade.effect"),
    );
    assert.match(
      await evaluate("byId('pointer-description').textContent"),
      /^Disable whole-window wobble/,
    );
    assert.match(
      await evaluate("byId('pointer-movement-note').textContent"),
      /Pointer wobble Off does not stop continuous fragments.*Set Move to Off/s,
    );
    assert.match(
      await evaluate("byId('combo-pointer-mode').getAttribute('aria-describedby')"),
      /pointer-movement-note/,
    );
    await choose("combo-movement-mode", "off");
    assert.equal(await evaluate("byId('native-fragment-preset').value"), "cascade");
    assert.deepEqual(
      await evaluate("effectDocument().fragment_motion"),
      await evaluate("catalog.fragment_presets.cascade.settings"),
    );
    assert.match(
      await evaluate("byId('pointer-movement-note').textContent"),
      /^Move is Off: fragment dragging and timed Move effects are disabled/,
    );
    await click("undo");
    assert.equal(await evaluate("byId('native-fragment-preset').value"), "cascade");
    assert.equal(await evaluate("effectDocument().pointer.strength"), 0);
    assert.match(
      await evaluate("byId('pointer-movement-note').textContent"),
      /continuous fragments take priority/,
    );
    await click("redo");
    assert.equal(await evaluate("effectDocument().actions.movement"), "off");
    assert.match(await evaluate("byId('pointer-movement-note').textContent"), /^Move is Off:/);
    await choose("combo-pointer-mode", "preserve");
    await choose("native-fragment-preset", "tear");
    await choose("fragment-response-max_lag", "555");
    await choose("combo-name", "Studio Trial");
    const document = await evaluate("effectDocument()");
    assert.equal(document.fragment_motion.max_lag, 555);
    await click("store-profile");
    assert.match(
      await evaluate("byId('profile-dialog-help').textContent"),
      /keep the complete recipe, including continuous fragment response/,
    );
    await click("profile-confirm");
    await wait("!byId('profile-dialog').open&&!byId('store-profile').disabled");
    assert.equal(selection().selected, fixture.base);
    const beforeReview = files(fixture.root);
    await click("review-selection");
    await settle();
    assert.equal(await evaluate("byId('apply-review').hidden"), false);
    assert.equal(await evaluate("byId('apply-selection').textContent"), "Select for next login");
    assert.deepEqual(files(fixture.root), beforeReview);
    if (process.env.NIRIFX_NATIVE_STUDIO_SCREENSHOT) {
      const layout = await browser.rpc("Page.getLayoutMetrics");
      const shot = await browser.rpc("Page.captureScreenshot", {
        format: "png",
        captureBeyondViewport: true,
        clip: {
          x: 0,
          y: 0,
          width: 1440,
          height: Math.ceil(layout.cssContentSize.height),
          scale: 1,
        },
      });
      writeFileSync(process.env.NIRIFX_NATIVE_STUDIO_SCREENSHOT, Buffer.from(shot.data, "base64"));
    }
    await click("cancel-review");
    assert.equal(await evaluate("byId('apply-review').hidden"), true);
    assert.deepEqual(files(fixture.root), beforeReview);
    await click("review-selection");
    await settle();
    await click("apply-selection");
    await settle();
    assert.equal(await evaluate("byId('error').textContent"), "");
    const applied = selection().selected;
    assert.notEqual(applied, fixture.base);
    assert.equal(selection().previous, fixture.base);
    const retained = files(join(fixture.native, "bundles"));
    for (const [path, bytes] of Object.entries(originalBundles))
      assert.equal(retained[path], bytes);
    await choose("combo-close-mode", "off");
    await click("native-reopen");
    assert.deepEqual(await evaluate("effectDocument()"), document);
    assert.equal(await evaluate("byId('native-fragment-preset').value"), "custom");
    assert.match(
      await evaluate("byId('pointer-movement-note').textContent"),
      /continuous fragments take priority/,
    );
    const beforeRollback = files(fixture.root);
    await click("restore-selection");
    await settle();
    assert.equal(await evaluate("byId('apply-review').hidden"), false);
    assert.deepEqual(files(fixture.root), beforeRollback);
    await click("cancel-review");
    assert.deepEqual(files(fixture.root), beforeRollback);
    await click("restore-selection");
    await settle();
    await click("apply-selection");
    await settle();
    assert.equal(selection().selected, fixture.base);
    assert.equal(selection().previous, applied);
    assert.deepEqual(files(join(fixture.native, "bundles")), retained);
    await click("review-selection");
    await settle();
    writeFileSync(
      selector,
      JSON.stringify({ schema: 1, selected: null, previous: fixture.base }) + "\n",
    );
    const stale = files(fixture.root);
    await click("apply-selection");
    await settle();
    assert.match(await evaluate("byId('error').textContent"), /plan changed/i);
    assert.equal(await evaluate("byId('apply-review').hidden"), true);
    assert.deepEqual(files(fixture.root), stale);
    // Reviewed rollback can explicitly return to stock/no-selection.
    writeFileSync(
      selector,
      JSON.stringify({ schema: 1, selected: fixture.base, previous: null }) + "\n",
    );
    await click("restore-selection");
    await settle();
    await click("apply-selection");
    await settle();
    assert.equal(selection().selected, null);
    assert.match(await evaluate("byId('status').textContent"), /Choose stock Niri/);
    assert.equal(await evaluate("byId('error').textContent"), "");
    // The backend owns live identity checks. Exercise presentation with explicit
    // protocol responses; these requests never activate a real compositor.
    await evaluate(`
      window.realLibraryFetch = fetch;
      window.liveResult = "applied";
      window.fetch = async (path, options) => {
        if (path === "/review") return new Response(JSON.stringify({
          activation: "live-and-next-login", changes: [], notes: [], plan_sha256: "reviewed"
        }));
        if (path === "/apply") return new Response(JSON.stringify({
          selection: {selected: "synthetic"}, activation: "live-and-next-login",
          live: {status: window.liveResult, detail: "Synthetic desktop result."}
        }));
        const response = await realLibraryFetch(path, options);
        if (String(path).startsWith("/library?")) {
          const data = await response.json();
          data.native.running.status = "matched";
          data.native.live = {ready: window.liveResult === "applied", detail: "Synthetic verified session."};
          return new Response(JSON.stringify(data));
        }
        return response;
      };
    `);
    for (const status of ["applied", "failed", "unconfirmed"]) {
      await browser.callFunction("function(status){window.liveResult=status}", [status]);
      await click("review-selection");
      await settle();
      assert.equal(await evaluate("byId('apply-selection').textContent"), "Apply to desktop");
      assert.equal(
        await evaluate("byId('review-selection').textContent"),
        status === "applied" ? "Review & apply" : "Review next login",
      );
      await click("apply-selection");
      await settle();
      const message = await evaluate("byId('status').textContent");
      assert.match(message, status === "applied" ? /Applied to this desktop/ : /not confirmed/);
      if (status !== "applied") assert.doesNotMatch(message, /Applied to this desktop/);
      if (status !== "applied")
        assert.match(await evaluate("byId('native-running').textContent"), /effects not confirmed/);
    }
    await assertTransactionMotion(browser);
  } finally {
    if (browser) await browser.close();
    if (child.exitCode === null) {
      const stopped = new Promise((resolve) => child.once("exit", resolve));
      child.kill("SIGTERM");
      await stopped;
    }
  }
});
