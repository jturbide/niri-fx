import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  chmodSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { Server } from "node:http";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { setTimeout as delay } from "node:timers/promises";
import { launchBrowser, projectRoot } from "../scripts/lib/browser.mjs";
import { recordingProvenance } from "../scripts/lib/recording-provenance.mjs";

const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
const studio = { version: "0.19.0", build: "abcdef012345" };
const html = `<!doctype html><html data-shader-status="ready"><meta charset="utf-8"><p id="sample">Original é</p><script id="effect-catalog" type="application/json">${JSON.stringify({ studio, connection: null })}</script><script>document.getElementById('sample').textContent='Loaded by the original script';</script></html>\n`;

function fixture(t, { duringGeneration = "" } = {}) {
  const root = mkdtempSync(join(tmpdir(), "nirifx-recording-test-"));
  for (const path of ["niri_fx", "examples", "scripts/lib", "docs/gifs", "artifacts"])
    mkdirSync(join(root, path), { recursive: true });
  writeFileSync(join(root, "niri_fx/__init__.py"), "");
  writeFileSync(join(root, "niri_fx/input.py"), "original = True\n");
  writeFileSync(join(root, "niri_fx/preview.html"), html);
  writeFileSync(join(root, "examples/profile.json"), '{"synthetic":true}\n');
  writeFileSync(join(root, "docs/gifs/showcases.json"), '{"clips":[]}\n');
  for (const path of [
    "scripts/recorder.mjs",
    "scripts/lib/recording-provenance.mjs",
    "scripts/lib/browser.mjs",
  ])
    writeFileSync(join(root, path), "// synthetic recording input\n");
  writeFileSync(
    join(root, "niri_fx/__main__.py"),
    `import sys\nfrom pathlib import Path\nPath(sys.argv[-1]).write_text(Path('niri_fx/preview.html').read_text())\n${duringGeneration}\n`,
  );
  const capture = recordingProvenance("scripts/recorder.mjs", { root });
  const page = join(root, "artifacts/preview.html");
  let browser;
  t.after(async () => {
    try {
      if (browser) await browser.close();
    } finally {
      await capture.close();
      rmSync(root, { recursive: true, force: true });
    }
  });
  return {
    root,
    page,
    capture,
    async load() {
      capture.generate(page);
      browser = await launchBrowser();
      await capture.navigate(browser, { width: 600, height: 400 });
      return browser;
    },
  };
}

test("changed inputs are rejected before preview generation", (t) => {
  const { root, page, capture } = fixture(t);
  writeFileSync(join(root, "niri_fx/input.py"), "changed = True\n");
  assert.throws(() => capture.generate(page), /Recording inputs changed/);
  assert.equal(existsSync(page), false);
});

test("input drift during the actual generation subprocess is rejected", (t) => {
  const { page, capture } = fixture(t, {
    duringGeneration: "Path('niri_fx/input.py').write_text('changed = True\\n')",
  });
  assert.throws(() => capture.generate(page), /Recording inputs changed/);
});

test("metadata binds the original HTTP response, not the edited DOM or a later source read", async (t) => {
  const { root, page, capture, load } = fixture(t);
  const input = readFileSync(join(root, "niri_fx/input.py"));
  const browser = await load();
  assert.equal(
    await browser.evaluate("document.getElementById('sample').textContent"),
    "Loaded by the original script",
  );
  await browser.evaluate(
    "document.getElementById('sample').textContent='Recording edits';document.body.style.background='black'",
  );
  // Normal generated files must not trigger source-change rejection.
  mkdirSync(join(root, "niri_fx/__pycache__"), { recursive: true });
  writeFileSync(join(root, "niri_fx/__pycache__/input.pyc"), "bytecode");
  writeFileSync(join(root, "artifacts/frame.png"), "synthetic frame");
  const proof = await capture.finish(["niri_fx/input.py", "scripts/recorder.mjs"]);
  assert.equal(proof.capture.preview_sha256, sha256(readFileSync(page)));
  assert.equal(proof.capture.preview_sha256, sha256(html));
  assert.deepEqual(proof.capture.studio, studio);
  assert.deepEqual(Object.keys(proof.sources), ["niri_fx/input.py", "scripts/recorder.mjs"]);
  for (const path of ["scripts/lib/recording-provenance.mjs", "scripts/lib/browser.mjs"])
    assert.equal(proof.capture.tool_sources[path], sha256(readFileSync(join(root, path))));
  assert.equal(proof.sources["niri_fx/input.py"], sha256(input));
  assert.match(proof.capture.inputs_sha256, /^[0-9a-f]{64}$/);
  assert.equal(JSON.stringify(proof).includes(root), false);
  assert.equal(JSON.stringify(proof).includes("127.0.0.1"), false);
});

test("a different original resource is rejected even with the same Studio build", async (t) => {
  const { page, capture } = fixture(t);
  capture.generate(page);
  const browser = await launchBrowser();
  t.after(() => browser.close());
  const different = {
    ...browser,
    rpc: (method, params) =>
      method === "Page.getResourceContent"
        ? Promise.resolve({
            content: html + "<!-- different input, same UI build -->",
            base64Encoded: false,
          })
        : browser.rpc(method, params),
  };
  await assert.rejects(capture.navigate(different), /Loaded recording document differs/);
});

test("source edits during capture are rejected even after restoring their original bytes", async (t) => {
  const { root, capture, load } = fixture(t);
  const source = join(root, "niri_fx/input.py");
  const original = readFileSync(source);
  const browser = await load();
  const screenshot = await browser.rpc("Page.captureScreenshot", { format: "png" });
  assert(Buffer.from(screenshot.data, "base64").length > 100);
  writeFileSync(source, "changed = True\n");
  writeFileSync(source, original);
  await delay(20);
  await assert.rejects(capture.finish(["niri_fx/input.py"]), /Recording inputs changed/);
});

test("a modified generated file cannot be relabelled as the already loaded preview", async (t) => {
  const { page, capture, load } = fixture(t);
  const browser = await load();
  writeFileSync(page, html.replace("Original é", "New file"));
  // The server serves the original in-memory snapshot even after disk changes.
  const response = await fetch(await browser.evaluate("location.href"));
  assert.equal(await response.text(), html);
  await assert.rejects(capture.finish([]), /Generated recording preview changed/);
});

test("new recording inputs and reloads invalidate a pending capture", async (t) => {
  const first = fixture(t);
  await first.load();
  writeFileSync(join(first.root, "examples/new-profile.json"), "{}");
  await assert.rejects(first.capture.finish([]), /Recording inputs changed/);

  const second = fixture(t);
  const browser = await second.load();
  await browser.navigate(await browser.evaluate("location.href"));
  await assert.rejects(second.capture.finish([]), /Recording preview was reloaded/);
});

test("metadata cannot add a source that was not in the original input snapshot", async (t) => {
  const { capture, load } = fixture(t);
  await load();
  await assert.rejects(capture.finish(["unrecorded-file"]), /source was not snapshotted/);
});

function outputs(root) {
  const destination = join(root, "docs/gifs/recording.gif");
  const encoded = join(root, "artifacts/rendered.gif");
  // Publication requires encoded GIF bytes; pixel correctness belongs to the renderer tests.
  const gif = Buffer.concat([Buffer.from("GIF89a"), Buffer.alloc(1100, 97)]);
  const oldGif = Buffer.from("previous synthetic GIF");
  const manifestPath = join(root, "docs/gifs/manifest.json");
  const manifest = JSON.stringify({ clips: [{ file: destination, bytes: oldGif.length }] }) + "\n";
  writeFileSync(destination, oldGif);
  writeFileSync(encoded, gif);
  writeFileSync(manifestPath, manifest);
  return {
    destination,
    encoded,
    gif,
    oldGif,
    manifestPath,
    manifest,
    request: {
      destination,
      encoded,
      manifestPath,
      sources: ["niri_fx/input.py"],
      entry: { name: "synthetic" },
    },
  };
}

test("a malformed manifest refuses publication without replacing the existing GIF", async (t) => {
  const { root, capture, load } = fixture(t);
  await load();
  const output = outputs(root);
  writeFileSync(output.manifestPath, "not JSON");
  await assert.rejects(capture.publish(output.request), SyntaxError);
  assert.deepEqual(readFileSync(output.destination), output.oldGif);
  assert.deepEqual(readFileSync(output.encoded), output.gif);
  assert.equal(readFileSync(output.manifestPath, "utf8"), "not JSON");
});

test("source drift refuses publication and preserves both previous outputs and staged evidence", async (t) => {
  const { root, capture, load } = fixture(t);
  await load();
  const output = outputs(root);
  writeFileSync(join(root, "niri_fx/input.py"), "changed = True\n");
  await assert.rejects(capture.publish(output.request), /Recording inputs changed/);
  assert.deepEqual(readFileSync(output.destination), output.oldGif);
  assert.deepEqual(readFileSync(output.encoded), output.gif);
  assert.equal(readFileSync(output.manifestPath, "utf8"), output.manifest);
});

test("successful publication pairs the staged GIF with its bound preview metadata", async (t) => {
  const { root, capture, load } = fixture(t);
  await load();
  const output = outputs(root);
  const entry = await capture.publish(output.request);
  assert.deepEqual(readFileSync(output.destination), output.gif);
  assert.equal(existsSync(output.encoded), false);
  assert.equal(existsSync(output.encoded + ".previous.gif"), false);
  assert.deepEqual(JSON.parse(readFileSync(output.manifestPath)), { clips: [entry] });
  assert.equal(entry.bytes, output.gif.length);
  assert.equal(entry.capture.preview_sha256, sha256(html));
});

test("failed metadata replacement restores the prior GIF and retains the staged recording", async (t) => {
  const { root, capture, load } = fixture(t);
  await load();
  const output = outputs(root);
  const manifestDirectory = join(root, "readonly-manifest");
  mkdirSync(manifestDirectory);
  output.request.manifestPath = join(manifestDirectory, "manifest.json");
  writeFileSync(output.request.manifestPath, output.manifest);
  chmodSync(manifestDirectory, 0o500);
  try {
    await assert.rejects(capture.publish(output.request), { code: "EACCES" });
    assert.deepEqual(readFileSync(output.destination), output.oldGif);
    assert.deepEqual(readFileSync(output.encoded), output.gif);
    assert.equal(readFileSync(output.request.manifestPath, "utf8"), output.manifest);
    assert(existsSync(output.encoded + ".manifest.json"));
  } finally {
    chmodSync(manifestDirectory, 0o700);
  }
});

test("cleanup preserves a failed loopback bind without an extra server-close error", async (t) => {
  const { page, capture } = fixture(t);
  capture.generate(page);
  const failure = Object.assign(new Error("Synthetic loopback bind failure"), {
    code: "EADDRNOTAVAIL",
  });
  t.mock.method(Server.prototype, "listen", function () {
    queueMicrotask(() => this.emit("error", failure));
    return this;
  });
  await assert.rejects(capture.navigate({}), (error) => error === failure);
  await assert.doesNotReject(capture.close());
});

test("shared helpers stay in capture history but still reject in-flight edits", async (t) => {
  const { root, capture, load } = fixture(t);
  await load();
  const proof = {
    file: "docs/gifs/synthetic.gif",
    ...(await capture.finish(["niri_fx/input.py", "scripts/recorder.mjs"])),
  };
  writeFileSync(join(root, "scripts/lib/browser.mjs"), "// later helper revision\n");
  await assert.rejects(capture.finish([]), /Recording inputs changed/);
  const check = () =>
    JSON.parse(
      execFileSync(
        "python3",
        [
          "-c",
          `
import importlib.util,json,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('docs_check',sys.argv[1])
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.ROOT=Path(sys.argv[2])
errors=[]
module.recording_sources(json.loads(sys.argv[3]),errors)
print(json.dumps(errors))
`,
          join(projectRoot, "scripts/check-docs.py"),
          root,
          JSON.stringify(proof),
        ],
        { cwd: projectRoot, encoding: "utf8" },
      ),
    );
  assert.deepEqual(check(), [], "Historical helper revisions do not stale a finished recording");
  writeFileSync(join(root, "scripts/recorder.mjs"), "// changed frame timing\n");
  assert.match(check()[0], /Recording source changed.*scripts\/recorder\.mjs/);
});
