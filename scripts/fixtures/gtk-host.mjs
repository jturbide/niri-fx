// Test-only file IPC. No mutation endpoint is shipped in the production picker.
import Gtk from "gi://Gtk?version=4.0";
import Gio from "gi://Gio";
import GLib from "gi://GLib";
import { createPickerWindow } from "../../niri_fx/gtk/picker.mjs";
const directory = GLib.getenv("NIRIFX_TEST_CHANNEL");
const decoder = new TextDecoder();
const app = new Gtk.Application({
  application_id: "io.github.jturbide.NiriFX.Test",
  flags: Gio.ApplicationFlags.NON_UNIQUE,
});
app.connect("activate", () => {
  const picker = createPickerWindow(app);
  const c = picker.controller;
  c.subscribe(() =>
    GLib.file_set_contents(
      `${directory}/state.json`,
      JSON.stringify({
        count: Object.keys(c.presets).length,
        selected: c.selectedId,
        busy: c.busy,
        canApply: c.canApply,
        error: c.error,
        status: c.status,
        undo: c.undoTransaction,
        document: c.document,
        allowResize: c.allowResize,
      }),
    ),
  );
  GLib.timeout_add(GLib.PRIORITY_DEFAULT, 40, () => {
    const file = `${directory}/command.json`;
    if (GLib.file_test(file, GLib.FileTest.EXISTS)) {
      const { method, args } = JSON.parse(decoder.decode(GLib.file_get_contents(file)[1]));
      GLib.unlink(file);
      if (!["select", "review", "apply", "undo", "loadFile", "consentResize"].includes(method))
        throw new Error("Unknown test method");
      void c[method](...args);
    }
    return GLib.SOURCE_CONTINUE;
  });
  picker.window.present();
});
await app.runAsync([]);
