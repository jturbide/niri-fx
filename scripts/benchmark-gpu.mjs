// Shader GPU timings, not compositor frame times. No software fallback claims.
import { spawn, execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, writeFileSync, existsSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import assert from "node:assert/strict";

const options = Object.fromEntries(
  process.argv.slice(2).map((arg) => {
    assert(
      /^--(output|presets|sizes|samples|software)=.+/.test(arg),
      "Use --output=report.json --presets=balanced,iris-bloom --sizes=1920x1080,2560x1440 --samples=60 [--software=true for rejection testing]",
    );
    const split = arg.indexOf("=");
    return [arg.slice(2, split), arg.slice(split + 1)];
  }),
);
assert(options.output, "--output is required");
const output = resolve(options.output);
assert(!existsSync(output), "Use a fresh report filename");
const root = resolve(new URL("..", import.meta.url).pathname);
const scratch = mkdtempSync(join(tmpdir(), "nirifx-gpu-"));
const page = join(scratch, "preview.html");
execFileSync("python3", ["-m", "niri_fx", "preview", "--output", page], { cwd: root });
const browser = spawn(
  process.env.CHROME_BIN || "chromium",
  [
    "--headless=new",
    "--no-sandbox",
    "--remote-debugging-port=0",
    "--user-data-dir=" + scratch,
    ...(options.software === "true"
      ? ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
      : ["--use-gl=angle", "--use-angle=gl", "--enable-webgl"]),
    "about:blank",
  ],
  { stdio: ["ignore", "ignore", "pipe"] },
);
let diagnostics = "",
  failure,
  ws;
browser.stderr.on("data", (chunk) => {
  diagnostics = (diagnostics + chunk).slice(-4096);
});
browser.on("error", (error) => {
  failure = error;
});
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
try {
  const deadline = Date.now() + 30000;
  while (!existsSync(join(scratch, "DevToolsActivePort"))) {
    if (failure || browser.exitCode !== null || Date.now() > deadline)
      throw new Error(failure?.message || diagnostics);
    await delay(100);
  }
  const port = readFileSync(join(scratch, "DevToolsActivePort"), "utf8").split("\n")[0];
  const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  ws = new WebSocket(pages.find((tab) => tab.type === "page").webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
  });
  let id = 0;
  const pending = new Map();
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data),
      item = pending.get(data.id);
    if (!item) return;
    clearTimeout(item.timer);
    pending.delete(data.id);
    data.error ? item.reject(new Error(JSON.stringify(data.error))) : item.resolve(data.result);
  };
  const rpc = (method, params) =>
    new Promise((resolve, reject) => {
      const key = ++id;
      const timer = setTimeout(() => {
        pending.delete(key);
        reject(new Error("Browser request timed out: " + method));
      }, 120000);
      pending.set(key, { resolve, reject, timer });
      ws.send(JSON.stringify({ id: key, method, params }));
    });
  const evaluate = async (expression) => {
    const result = await rpc("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  };
  await rpc("Page.navigate", { url: pathToFileURL(page).href });
  for (
    let i = 0;
    i < 100 && !(await evaluate("document.documentElement?.dataset.shaderStatus"));
    i++
  )
    await delay(100);
  assert.equal(
    await evaluate("document.documentElement?.dataset.shaderStatus"),
    "ready",
    await evaluate("document.getElementById('error').textContent"),
  );
  const presets = (
    options.presets || "balanced,core-detonation,spring-wobble,noise-dissolve,iris-bloom"
  ).split(",");
  const sizes = (options.sizes || "1920x1080,2560x1440,3840x2160").split(",").map((value) => {
    assert(/^\d+x\d+$/.test(value), "Sizes must use WIDTHxHEIGHT");
    return value.split("x").map(Number);
  });
  const results = [];
  for (const preset of presets) {
    assert(
      await evaluate(`Object.hasOwn(catalog.presets, ${JSON.stringify(preset)})`),
      "Unknown preset: " + preset,
    );
    await evaluate(
      `byId('preset').value=${JSON.stringify(preset)};byId('preset').dispatchEvent(new Event('change'))`,
    );
    for (const [width, height] of sizes) {
      const result = await evaluate(
        `window.niriFxBenchmark(${JSON.stringify({ width, height, samples: Number(options.samples || 60) })})`,
      );
      results.push(result);
      console.log(
        `${preset} ${width}x${height}: ${result.status}${result.p95 ? " p95=" + result.p95.toFixed(3) + "ms" : " (" + result.reason + ")"}`,
      );
    }
  }
  writeFileSync(
    output,
    JSON.stringify(
      {
        schema: 1,
        recorded: new Date().toISOString(),
        scope:
          "Single synthetic window, browser WebGL GPU draw time. Excludes compositor, capture, input latency and scanout. Budget exceedances are not measured dropped frames.",
        results,
      },
      null,
      2,
    ) + "\n",
    { flag: "wx" },
  );
  if (results.some((result) => result.status !== "measured")) process.exitCode = 2;
} finally {
  ws?.close();
  if (browser.exitCode === null && !failure) {
    const closed = new Promise((resolve) => browser.once("close", resolve));
    browser.kill();
    await closed;
  }
  rmSync(scratch, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
}
