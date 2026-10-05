// Shared Chromium lifecycle for render checks, GIF recording and GPU measurement.
// Every invocation owns its profile and child process; personal browser state is
// never reused. Software rendering is explicit so benchmark results cannot silently
// switch to a CPU renderer and masquerade as hardware GPU timings.
import { spawn, spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";

export const projectRoot = fileURLToPath(new URL("../../", import.meta.url));

function executable() {
  const selected =
    process.env.CHROME_BIN ||
    ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable"].find(
      (name) => spawnSync(name, ["--version"], { stdio: "ignore" }).status === 0,
    );
  if (!selected) throw new Error("Install Chromium/Chrome or set CHROME_BIN");
  return selected;
}

async function withTimeout(promise, milliseconds, message) {
  let timer;
  try {
    return await Promise.race([
      promise,
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error(message)), milliseconds);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

export async function launchBrowser({
  command = executable(),
  software = true,
  launchTimeout = 30000,
  requestTimeout = 120000,
  profilePrefix = "niri-fx-browser-",
} = {}) {
  const profile = mkdtempSync(join(tmpdir(), profilePrefix));
  const browserProcess = spawn(
    command,
    [
      "--headless=new",
      "--no-sandbox",
      "--disable-dev-shm-usage",
      ...(software
        ? ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
        : ["--use-gl=angle", "--use-angle=gl", "--enable-webgl"]),
      "--remote-debugging-port=0",
      "--user-data-dir=" + profile,
      "about:blank",
    ],
    { stdio: ["ignore", "ignore", "pipe"] },
  );
  let diagnostics = "",
    launchError,
    closed = false,
    socket,
    sequence = 0,
    closing;
  const pending = new Map();
  browserProcess.stderr.on("data", (chunk) => {
    diagnostics = (diagnostics + chunk).slice(-8192);
  });
  browserProcess.on("error", (error) => {
    launchError = error;
  });
  const exited = new Promise((resolve) =>
    browserProcess.once("close", () => {
      closed = true;
      resolve();
    }),
  );

  function rejectPending(error) {
    for (const item of pending.values()) {
      clearTimeout(item.timer);
      item.reject(error);
    }
    pending.clear();
  }

  function close() {
    // Idempotent cleanup also serves the startup-error path. Closing a session
    // rejects outstanding RPCs immediately instead of leaving callers hanging.
    return (closing ??= (async () => {
      rejectPending(new Error("Browser session closed"));
      socket?.close();
      if (!closed) {
        browserProcess.kill("SIGTERM");
        try {
          await withTimeout(exited, 3000, "Chrome did not stop");
        } catch {
          browserProcess.kill("SIGKILL");
          await withTimeout(exited, 3000, "Chrome did not exit after SIGKILL");
        }
      }
      // Chrome helpers can finish flushing briefly after the main process exits.
      rmSync(profile, { recursive: true, force: true, maxRetries: 10, retryDelay: 100 });
    })());
  }

  function rpc(method, params = {}, timeout = requestTimeout) {
    if (closing || socket?.readyState !== WebSocket.OPEN)
      return Promise.reject(new Error("Browser connection is closed"));
    return new Promise((resolve, reject) => {
      const id = ++sequence;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error("Browser request timed out: " + method));
      }, timeout);
      pending.set(id, { resolve, reject, timer });
      try {
        socket.send(JSON.stringify({ id, method, params }));
      } catch (error) {
        clearTimeout(timer);
        pending.delete(id);
        reject(error);
      }
    });
  }

  async function evaluate(expression) {
    const result = await rpc("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
    return result.result.value;
  }

  async function callFunction(functionDeclaration, args = []) {
    // Send fixture/import data through CDP values, separate from executable
    // source. A fresh global handle also survives navigation between calls.
    const global = await rpc("Runtime.evaluate", { expression: "globalThis" });
    const objectId = global.result.objectId;
    if (!objectId) throw new Error("Browser global object is unavailable");
    try {
      const result = await rpc("Runtime.callFunctionOn", {
        objectId,
        functionDeclaration,
        arguments: args.map((value) => ({ value })),
        returnByValue: true,
        awaitPromise: true,
      });
      if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
      return result.result.value;
    } finally {
      await rpc("Runtime.releaseObject", { objectId });
    }
  }

  async function navigate(url, { width, height, timeout = 30000, readySelector = null } = {}) {
    if (width && height)
      await rpc("Emulation.setDeviceMetricsOverride", {
        width,
        height,
        deviceScaleFactor: 1,
        mobile: false,
      });
    const navigation = await rpc("Page.navigate", { url });
    if (navigation.errorText) throw new Error("Browser navigation failed: " + navigation.errorText);
    const deadline = Date.now() + timeout;
    let state;
    while (Date.now() < deadline) {
      try {
        state = await evaluate(
          `({url:location.href,status:${readySelector ? `(document.querySelector(${JSON.stringify(readySelector)}) ? "ready" : "loading")` : "document.documentElement?.dataset.shaderStatus"},error:document.getElementById('error')?.textContent})`,
        );
      } catch (error) {
        // Navigation can replace the execution context between two CDP requests.
        if (!/Execution context was destroyed|Cannot find context/.test(error.message)) throw error;
      }
      if (state?.url === url) {
        if (state.status === "ready") return;
        if (state.status === "error") throw new Error("Studio render failed: " + state.error);
      }
      await delay(100);
    }
    // Report readiness without logging session URLs or capability tokens.
    throw new Error(
      `Studio did not become ready before the browser timeout (status: ${state?.status ?? "loading"}; expected location: ${state?.url === url}; error: ${state?.error || "none"})`,
    );
  }

  try {
    const deadline = Date.now() + launchTimeout;
    const portFile = join(profile, "DevToolsActivePort");
    let port, portProblem;
    while (port === undefined) {
      if (launchError || closed || Date.now() >= deadline)
        throw new Error(
          `Chrome did not start (${launchError?.message ?? (closed ? "exit " + browserProcess.exitCode : "timeout")}).\n${portProblem ? portProblem + "\n" : ""}${diagnostics}`,
          { cause: launchError },
        );
      try {
        // Chrome creates this file before finishing its write. A digit-only
        // prefix can itself be a valid port, so require the first line's newline
        // before using it. The browser endpoint on line two need not end in one.
        const contents = readFileSync(portFile, "utf8"),
          lineEnd = contents.indexOf("\n"),
          firstLine = contents.slice(0, lineEnd),
          candidate = Number(firstLine);
        if (
          lineEnd >= 0 &&
          /^\d+$/.test(firstLine) &&
          Number.isInteger(candidate) &&
          candidate >= 1 &&
          candidate <= 65535
        )
          port = candidate;
        else portProblem = "Chrome returned an incomplete or invalid debugging port";
      } catch (error) {
        if (error.code !== "ENOENT")
          throw new Error("Chrome debugging port file could not be read.\n" + diagnostics, {
            cause: error,
          });
      }
      if (port === undefined) await delay(Math.max(0, Math.min(100, deadline - Date.now())));
    }
    // The debugging port can be published before the initial page target.
    // Retry only an empty target list, within the same bounded startup window.
    let page;
    while (!page) {
      if (launchError || closed || Date.now() >= deadline)
        throw new Error("Chrome did not create a page target before startup ended");
      const response = await fetch(`http://127.0.0.1:${port}/json/list`, {
        signal: AbortSignal.timeout(Math.max(1, deadline - Date.now())),
      });
      if (!response.ok) throw new Error("Chrome debugging endpoint failed: " + response.status);
      page = (await response.json()).find((tab) => tab.type === "page");
      if (!page) await delay(50);
    }
    socket = new WebSocket(page.webSocketDebuggerUrl);
    socket.onmessage = (event) => {
      const message = JSON.parse(event.data),
        item = pending.get(message.id);
      if (!item) return; // CDP events and late replies to timed-out requests.
      clearTimeout(item.timer);
      pending.delete(message.id);
      message.error
        ? item.reject(new Error(JSON.stringify(message.error)))
        : item.resolve(message.result);
    };
    socket.onclose = () => rejectPending(new Error("Browser connection closed"));
    await withTimeout(
      new Promise((resolve, reject) => {
        socket.onopen = resolve;
        socket.onerror = () => {
          const error = new Error("Browser WebSocket failed");
          rejectPending(error);
          reject(error);
        };
      }),
      launchTimeout,
      "Chrome debugging connection timed out",
    );
    // Startup hooks are accepted while Page is disabled but never execute.
    // Enable the lifecycle domains before callers register or navigate pages.
    await rpc("Page.enable");
    await rpc("Runtime.enable");
    return { rpc, evaluate, callFunction, navigate, close, profile };
  } catch (error) {
    await close();
    throw error;
  }
}
