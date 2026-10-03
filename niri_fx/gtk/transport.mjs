// SPDX-License-Identifier: MIT
import Gio from "gi://Gio";
import GLib from "gi://GLib";

export function run(argv) {
  return new Promise((resolve, reject) => {
    // No shell evaluation, cancellation timer or global Gio prototype changes.
    // A configuration writer is allowed to finish even if its view is hidden.
    const process = Gio.Subprocess.new(
      argv,
      Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_PIPE,
    );
    process.communicate_utf8_async(null, null, (source, result) => {
      try {
        const [, stdout, stderr] = source.communicate_utf8_finish(result);
        if (!source.get_successful()) throw new Error(stderr.trim() || "NiriFX command failed.");
        resolve(JSON.parse(stdout));
      } catch (error) {
        reject(error);
      }
    });
  });
}

export function launch(argv) {
  const process = Gio.Subprocess.new(argv, Gio.SubprocessFlags.NONE);
  process.wait_async(null, (source, result) => source.wait_finish(result));
}

export function displayPath(value) {
  let text = String(value);
  for (const key of ["XDG_CONFIG_HOME", "XDG_STATE_HOME", "HOME"]) {
    const prefix = GLib.getenv(key);
    if (prefix) text = text.split(`${prefix}/`).join(key === "HOME" ? "~/" : `$${key}/`);
  }
  return text;
}

export function environmentOptions() {
  return {
    command: JSON.parse(GLib.getenv("NIRIFX_COMMAND") || '["niri-fx"]'),
    configPath: GLib.getenv("NIRIFX_CONFIG") || `${GLib.get_user_config_dir()}/niri/config.kdl`,
    statePath: GLib.getenv("NIRIFX_STATE") || `${GLib.get_user_state_dir()}/niri-fx/gtk`,
    startupFile: GLib.getenv("NIRIFX_CUSTOM") || "",
  };
}
