// SPDX-License-Identifier: MIT
import Gtk from "gi://Gtk?version=4.0";
import Gio from "gi://Gio";
import { createPickerWindow } from "./picker.mjs";

const app = new Gtk.Application({
  application_id: "io.github.jturbide.NiriFX.Picker",
  flags: Gio.ApplicationFlags.NON_UNIQUE,
});
app.connect("activate", () => createPickerWindow(app).window.present());
await app.runAsync([]);
