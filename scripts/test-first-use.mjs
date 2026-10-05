#!/usr/bin/env node
// Real Library buttons, an empty account and owned Niri files. No desktop session.
import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { launchBrowser, projectRoot } from "./lib/browser.mjs";

const args = process.argv.slice(2);
let wheel = null,
  inirRoot = null;
while (args.length) {
  const option = args.shift();
  const value = args.shift();
  if (!value || !["--wheel", "--inir-root"].includes(option))
    throw new Error(
      "Usage: node scripts/test-first-use.mjs [--wheel candidate.whl] [--inir-root installed-shell]",
    );
  if (option === "--wheel") wheel = resolve(value);
  else inirRoot = resolve(value);
}
const target = inirRoot ? "inir" : "standalone";
const root = mkdtempSync(join(tmpdir(), "nirifx-first-use-"));
const environment = {
  ...process.env,
  PYTHONNOUSERSITE: "1",
  PYTHONDONTWRITEBYTECODE: "1",
  PIP_DISABLE_PIP_VERSION_CHECK: "1",
};
for (const key of [
  "NIRI_SOCKET",
  "WAYLAND_DISPLAY",
  "DISPLAY",
  "DBUS_SESSION_BUS_ADDRESS",
  "XDG_RUNTIME_DIR",
  "PYTHONPATH",
  "PYTHONHOME",
  "VIRTUAL_ENV",
])
  delete environment[key];
function account(name) {
  const env = { ...environment };
  for (const key of [
    "HOME",
    "XDG_CONFIG_HOME",
    "XDG_STATE_HOME",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
    "XDG_RUNTIME_DIR",
  ]) {
    env[key] = join(root, name, key.toLowerCase());
    mkdirSync(env[key], { recursive: true, mode: 0o700 });
  }
  return env;
}
const appEnv = account("app");
// Chromium crash reports and preferences must not enter the app's account.
process.env = account("browser");
function run(command, cwd = root) {
  const result = spawnSync(command[0], command.slice(1), {
    cwd,
    env: appEnv,
    encoding: "utf8",
    timeout: 120000,
  });
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  return result.stdout.trim();
}
function files(folder) {
  if (!existsSync(folder)) return {};
  return Object.fromEntries(
    readdirSync(folder, { recursive: true, withFileTypes: true })
      .filter((entry) => entry.isFile())
      .map((entry) => {
        const path = join(entry.parentPath, entry.name);
        return [path, readFileSync(path, "utf8")];
      }),
  );
}
let server, browser;
async function stopServer() {
  if (!server || server.exitCode !== null) return;
  await new Promise((done) => {
    const timer = setTimeout(() => server.kill("SIGKILL"), 5000);
    server.once("exit", () => {
      clearTimeout(timer);
      done();
    });
    server.kill("SIGTERM");
  });
}
async function startServer(command, cwd, options = []) {
  server = spawn(command[0], [...command.slice(1), "studio", "--no-browser", ...options], {
    cwd,
    env: appEnv,
    stdio: ["ignore", "pipe", "ignore"],
  });
  // The session URL is a capability. Keep it out of logs and assertion messages.
  return await new Promise((accept, reject) => {
    const timer = setTimeout(() => reject(new Error("Studio startup timed out")), 20000);
    let output = "";
    server.stdout.on("data", (chunk) => {
      output += chunk;
      const match = output.match(/NiriFX Studio: (http:\/\/127\.0\.0\.1:[^\s]+)/);
      if (match) {
        clearTimeout(timer);
        accept(match[1]);
      }
    });
    server.once("error", () => {
      clearTimeout(timer);
      reject(new Error("Studio could not start"));
    });
    server.once("exit", () => {
      clearTimeout(timer);
      reject(new Error("Studio stopped before readiness"));
    });
  });
}
async function waitFor(expression) {
  const deadline = Date.now() + 15000;
  do {
    if (await browser.evaluate(expression)) return;
    const error = await browser.evaluate("byId('error').textContent");
    assert.equal(error, "");
    await delay(50);
  } while (Date.now() < deadline);
  throw new Error("Library operation did not settle");
}
async function click(id) {
  await browser.callFunction(
    `function(id) {
      const control = byId(id);
      if (control.disabled || control.hidden) throw new Error('Unavailable control: ' + id);
      control.click();
    }`,
    [id],
  );
}
async function choose(id, value) {
  await browser.callFunction(
    `function(id, value) {
      const control = byId(id);
      if (control.disabled) throw new Error('Disabled control: ' + id);
      control.value = value;
      if (control.value !== value) throw new Error('Missing choice: ' + id);
      control.dispatchEvent(new Event('change'));
    }`,
    [id, value],
  );
}
async function ready(expectedTarget = target) {
  await waitFor("byId('active-look').textContent.startsWith('Active: ')");
  assert.equal(await browser.evaluate("document.documentElement.dataset.workspace"), "library");
  assert.equal(await browser.evaluate("catalog.connection.target"), expectedTarget);
}
try {
  const config = join(appEnv.XDG_CONFIG_HOME, "niri/config.kdl");
  const include = join(appEnv.XDG_CONFIG_HOME, "niri/nirifx/animations.kdl");
  const animation = join(appEnv.XDG_CONFIG_HOME, "niri/config.d/60-animations.kdl");
  const registry = join(appEnv.XDG_CONFIG_HOME, "inir/niri-animation-presets.json");
  let original = `// Existing desktop choices survive the first NiriFX session.
hotkey-overlay { skip-at-startup; }
animations {
    window-open { duration-ms 210; curve "ease-out-cubic"; }
    window-close { duration-ms 190; curve "ease-out-cubic"; }
    window-resize { duration-ms 170; curve "ease-out-cubic"; }
}
`;
  mkdirSync(join(appEnv.XDG_CONFIG_HOME, "niri"));
  writeFileSync(config, original);
  let shellBaseline;
  if (inirRoot) {
    // Read the installed helper/defaults in place; all helper writes are routed
    // through the child's isolated XDG_CONFIG_HOME, with no desktop socket.
    symlinkSync(inirRoot, join(appEnv.XDG_DATA_HOME, "inir"), "dir");
    mkdirSync(join(appEnv.XDG_CONFIG_HOME, "niri/config.d"));
    writeFileSync(
      config,
      'hotkey-overlay { skip-at-startup; }\ninclude "config.d/60-animations.kdl"\n',
    );
    writeFileSync(animation, "// Synthetic shell settings\nanimations {\n slowdown 1.25\n}\n");
    const applied = JSON.parse(
      run([
        "python3",
        join(inirRoot, "scripts/niri-config.py"),
        "apply-animation-preset",
        "snappy",
      ]),
    );
    assert.equal(applied.success, true);
    shellBaseline = JSON.parse(
      run(["python3", join(inirRoot, "scripts/niri-config.py"), "get-animation-presets"]),
    );
    assert.equal(shellBaseline.active, "snappy");
    original = readFileSync(config, "utf8");
  }
  const baseline = files(appEnv.XDG_CONFIG_HOME);
  let command = ["python3", "-m", "niri_fx"],
    cwd = projectRoot;
  if (wheel) {
    run(["python3", "-m", "venv", join(root, "venv")]);
    run([join(root, "venv/bin/python"), "-m", "pip", "install", "--no-index", "--no-deps", wheel]);
    command = [join(root, "venv/bin/niri-fx")];
    cwd = root;
  }
  const version = run([...command, "--version"], cwd);
  assert.deepEqual(files(appEnv.XDG_CONFIG_HOME), baseline, "Installation modified the config");
  assert.deepEqual(files(appEnv.XDG_STATE_HOME), {});
  run(["niri", "validate", "-c", config]);
  let url = await startServer(command, cwd);
  browser = await launchBrowser();
  await browser.navigate(url);
  await ready();
  assert.equal(await browser.evaluate("byId('restore-selection').disabled"), true);
  assert.equal(
    await browser.evaluate("byId('active-look').textContent"),
    inirRoot
      ? `Active: ${shellBaseline.presets.find((preset) => preset.id === "snappy").name}`
      : "Active: Current Niri settings",
  );
  await browser.evaluate(
    "document.querySelector('[data-library-action=combo]').click();document.querySelector('[data-style=fragment-flow]').click()",
  );
  const combo = await browser.evaluate("effectDocument()");
  assert.equal(combo.name, "Fragment Flow");
  assert.equal(combo.schema, 2);
  assert.equal(combo.actions.resize, null);
  assert.equal(combo.actions.movement, null);
  assert.equal(combo.pointer ?? null, null);
  await click("preview-combo");
  await browser.evaluate("niriFxComboPreview.seek(niriFxComboPreview.currentPlan.totalMs)");

  // Modes are independent, and returning to Style recovers the chosen effect.
  for (const action of ["open", "close", "resize", "movement", "pointer"]) {
    await choose(`combo-${action}-mode`, "style");
    const styled = await browser.evaluate("effectDocument()");
    await choose(`combo-${action}-mode`, "off");
    const off = await browser.evaluate("effectDocument()");
    assert.equal(
      action === "pointer" ? off.pointer.strength : off.actions[action],
      action === "pointer" ? 0 : "off",
    );
    await choose(`combo-${action}-mode`, "preserve");
    const preserved = await browser.evaluate("effectDocument()");
    assert.equal(
      action === "pointer" ? (preserved.pointer ?? null) : preserved.actions[action],
      null,
    );
    await choose(`combo-${action}-mode`, "style");
    const recovered = await browser.evaluate("effectDocument()");
    assert.deepEqual(
      action === "pointer" ? recovered.pointer : recovered.actions[action],
      action === "pointer" ? styled.pointer : styled.actions[action],
    );
  }
  // A first stock combo: the user's opening remains, closing has its own style,
  // resizing is explicitly off; native choices stay Preserve.
  await choose("combo-open-mode", "preserve");
  await choose("combo-close", "frost-vanish");
  await choose("combo-resize-mode", "off");
  await choose("combo-movement-mode", "preserve");
  await choose("combo-pointer-mode", "preserve");
  await click("store-profile");
  await browser.callFunction("function() { byId('profile-save-name').value = 'First Combo'; }");
  await click("profile-confirm");
  await waitFor("!byId('profile-dialog').open && !byId('store-profile').disabled");
  const profile = join(appEnv.XDG_STATE_HOME, "niri-fx/profiles/first-combo.json");
  const saved = readFileSync(profile, "utf8");
  const document = JSON.parse(saved);
  assert.equal(document.actions.open, null);
  assert.equal(document.actions.resize, "off");
  assert.equal(document.actions.close.family, "dissolve");
  assert.deepEqual(files(appEnv.XDG_CONFIG_HOME), baseline, "Preview or Save modified the config");
  await click("review-selection");
  await waitFor("!byId('apply-review').hidden && !byId('apply-selection').disabled");
  assert.deepEqual(files(appEnv.XDG_CONFIG_HOME), baseline, "Review modified the config");
  assert.equal(await browser.evaluate("byId('review-files').children.length"), 2);
  assert.match(await browser.evaluate("byId('review-summary').textContent"), /First Combo/);
  await click("cancel-review");
  assert.equal(await browser.evaluate("byId('apply-review').hidden"), true);
  assert.deepEqual(files(appEnv.XDG_CONFIG_HOME), baseline);
  await click("review-selection");
  await waitFor("!byId('apply-review').hidden && !byId('apply-selection').disabled");
  await click("apply-selection");
  await waitFor(
    "!byId('restore-selection').disabled && byId('status').textContent.startsWith('Applied.')",
  );
  assert(readFileSync(config, "utf8").startsWith(original));
  if (inirRoot) {
    const active = JSON.parse(
      run(["python3", join(inirRoot, "scripts/niri-config.py"), "get-animation-presets"]),
    );
    assert.equal(active.active, "niri-fx-custom-first-combo");
    const applied = active.presets.find((preset) => preset.id === active.active);
    const base = shellBaseline.presets.find((preset) => preset.id === "snappy");
    assert.deepEqual(applied.profile, document);
    assert.deepEqual(applied.types["window-resize"], { "duration-ms": 0, curve: "linear" });
    assert.deepEqual(applied.types["window-open"], base.types["window-open"]);
    assert.deepEqual(applied.types["window-movement"], base.types["window-movement"]);
    assert.match(readFileSync(animation, "utf8"), /slowdown 1\.25/);
    assert.equal(existsSync(include), false);
    assert.equal(existsSync(registry), true);
  } else {
    const override = readFileSync(include, "utf8");
    assert.match(override, /window-close/);
    assert.match(override, /window-resize\s*\{\s*off/);
    assert.doesNotMatch(override, /window-open|window-movement|pointer-wobble/);
  }
  run(["niri", "validate", "-c", config]);
  const activeLabel = inirRoot ? "Active: NiriFX · First Combo" : "Active: First Combo";
  assert.equal(await browser.evaluate("byId('active-look').textContent"), activeLabel);

  // A new process sees the saved profile and owns the same Restore history.
  await stopServer();
  url = await startServer(command, cwd);
  await browser.navigate(url);
  await ready();
  assert.equal(await browser.evaluate("byId('active-look').textContent"), activeLabel);
  await choose("library-collection", "customs");
  await browser.evaluate("document.querySelector('[data-style=custom-first-combo]').click()");
  assert.deepEqual(await browser.evaluate("effectDocument()"), document);
  await click("restore-selection");
  await waitFor(
    "byId('restore-selection').disabled && byId('status').textContent === 'Restored previous settings.'",
  );
  assert.deepEqual(
    files(appEnv.XDG_CONFIG_HOME),
    baseline,
    "Restore did not recover the exact config",
  );
  assert.equal(existsSync(include), false);
  assert.equal(readFileSync(profile, "utf8"), saved, "Restore changed the saved Library copy");
  run(["niri", "validate", "-c", config]);
  assert.equal(await browser.evaluate("byId('error').textContent"), "");

  // Auto-detection is based on the helper's presence, not the login session.
  // A synthetic read-only helper proves the launch route without shell mutation.
  await stopServer();
  if (!inirRoot) {
    const helperFolder = join(appEnv.XDG_DATA_HOME, "inir/scripts");
    mkdirSync(helperFolder, { recursive: true });
    writeFileSync(
      join(helperFolder, "niri-config.py"),
      'import json\nprint(json.dumps({"active": "base", "presets": [{"id": "base", "name": "Existing shell style", "types": {}}]}))\n',
    );
  }
  url = await startServer(command, cwd);
  await browser.navigate(url);
  await ready("inir");
  assert.equal(await browser.evaluate("byId('error').textContent"), "");
  assert.deepEqual(files(appEnv.XDG_CONFIG_HOME), baseline);
  await stopServer();
  url = await startServer(command, cwd, ["--target", "standalone"]);
  await browser.navigate(url);
  await ready("standalone");
  assert.equal(await browser.evaluate("byId('error').textContent"), "");
  assert.deepEqual(files(appEnv.XDG_CONFIG_HOME), baseline);
  console.log(
    `PASS clean-account ${wheel ? "installed wheel" : "source"} ${version} ${target}: recommended combo, all five independent mode controls, saved profile, cancel/review/apply, restart and exact Restore, auto iNiR routing and explicit standalone; stock Niri validates. ${inirRoot ? "Real installed iNiR serializer and active recognition verified. " : ""}No desktop session connected.`,
  );
} finally {
  if (browser) await browser.close();
  await stopServer();
  rmSync(root, { recursive: true, force: true });
}
