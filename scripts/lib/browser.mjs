// Shared Chromium lifecycle for render checks, GIF recording and GPU measurement.
// Every invocation owns its profile and child process; personal browser state is
// never reused. Software rendering is explicit so benchmark results cannot silently
// switch to a CPU renderer and masquerade as hardware GPU timings.
import { spawn, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
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
    while (!existsSync(portFile)) {
      if (launchError || closed || Date.now() >= deadline)
        throw new Error(
          `Chrome did not start (${launchError?.message ?? (closed ? "exit " + browserProcess.exitCode : "timeout")}).\n${diagnostics}`,
        );
      await delay(100);
    }
    const port = readFileSync(portFile, "utf8").split("\n")[0];
    if (!/^\d+$/.test(port)) throw new Error("Chrome returned an invalid debugging port");
    const response = await fetch(`http://127.0.0.1:${port}/json/list`, {
      signal: AbortSignal.timeout(launchTimeout),
    });
    if (!response.ok) throw new Error("Chrome debugging endpoint failed: " + response.status);
    const page = (await response.json()).find((tab) => tab.type === "page");
    if (!page) throw new Error("Chrome did not create a page target");
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
    return { rpc, evaluate, navigate, close, profile };
  } catch (error) {
    await close();
    throw error;
  }
}
