import assert from "node:assert/strict";
import { test } from "node:test";
import { execFileSync, spawn } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { launchBrowser, projectRoot } from "../scripts/lib/browser.mjs";

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
    await browser.rpc("Page.addScriptToEvaluateOnNewDocument", {
      source: `window.libraryBootErrors=[];addEventListener('error',event=>window.libraryBootErrors.push(String(event.message).replace(/https?:\\/\\/\\S+/g,'[url]')));`,
    });
    async function reload() {
      try {
        await browser.navigate(url);
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
          performance: performance.getEntriesByType("navigation").map(entry=>({type:entry.type,load:entry.loadEventEnd,dom:entry.domContentLoadedEventEnd})),
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
    await evaluate('document.querySelector("[data-style=fragments-motion]").click()');
    assert.equal(await evaluate("effectDocument().actions.resize"), null);
    await evaluate(
      'byId("combo-close").value="frost-vanish";byId("combo-close").dispatchEvent(new Event("change"))',
    );
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
    assert.equal(unsupported.actions.resize, null);
    assert.equal(unsupported.actions.movement, null);
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
