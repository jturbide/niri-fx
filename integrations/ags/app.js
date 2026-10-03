// SPDX-License-Identifier: MIT
// AGS 3 / GTK 4. Supply the directory printed by `niri-fx picker --gtk-dir`.
import app from "ags/gtk4/app";
import GLib from "gi://GLib";

const directory = GLib.getenv("NIRIFX_GTK_DIR");
if (!directory) throw new Error("Set NIRIFX_GTK_DIR to the output of niri-fx picker --gtk-dir");
const { createPickerWindow } = await import(GLib.filename_to_uri(`${directory}/picker.mjs`, null));

// This is a standalone example. Existing shells should keep their own lifecycle.
// createPickerWindow removes its window only after pending commands finish.
app.connect("window-removed", () => {
  if (!app.get_windows().length) app.quit();
});

app.start({
  instanceName: "nirifx-picker",
  main() {
    createPickerWindow(app).window.present();
  },
});
