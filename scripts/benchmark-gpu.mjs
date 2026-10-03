// Shader GPU timings, not compositor frame times. No software fallback claims.
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync, existsSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import assert from "node:assert/strict";
import { launchBrowser, projectRoot } from "./lib/browser.mjs";

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
const root = projectRoot;
const scratch = mkdtempSync(join(tmpdir(), "nirifx-gpu-"));
const page = join(scratch, "preview.html");
let browser;
try {
  execFileSync("python3", ["-m", "niri_fx", "preview", "--output", page], { cwd: root });
  browser = await launchBrowser({ software: options.software === "true" });
  const { evaluate } = browser;
  await browser.navigate(pathToFileURL(page).href);
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
  await browser?.close();
  rmSync(scratch, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
}
