// Real GJS -> Gio.Subprocess -> Python -> temporary Niri config acceptance.
import GLib from "gi://GLib";
import { PickerController } from "../../niri_fx/gtk/controller.mjs";
import { environmentOptions, run, displayPath } from "../../niri_fx/gtk/transport.mjs";

function check(value, message) {
  if (!value) throw new Error(message);
}
const decode = new TextDecoder();
const read = (path) => decode.decode(GLib.file_get_contents(path)[1]);
const write = (path, data) => GLib.file_set_contents(path, data);
const exists = (path) => GLib.file_test(path, GLib.FileTest.EXISTS);
const options = environmentOptions();
const launched = [];
const c = new PickerController({
  ...options,
  run,
  displayPath,
  launch: (args) => launched.push(args),
});
const original = read(options.configPath);
const include = `${GLib.path_get_dirname(options.configPath)}/nirifx/animations.kdl`;
const profilePath = GLib.getenv("NIRIFX_TEST_PROFILE");
const profile = read(profilePath);
await c.reload();
check(Object.keys(c.presets).length === 64 && !c.undoTransaction, "Catalog/history");
c.filter("explosion");
check(
  c.items.some((row) => row.id === "explosion"),
  "Search",
);
c.select("explosion");
check(!(await c.apply()) && !exists(include), "Selection activated without review");
check(
  (await c.review()) && c.canApply && read(options.configPath) === original,
  "Read-only review",
);
check(await c.apply(), c.error);
const installed = read(options.configPath);
check(!read(include).includes("window-resize"), "Built-in resize must remain absent");
check(installed.startsWith(original), "Base settings changed");
check((await c.review()) && !c.canApply && !c.reviewPlan.changes.length, "No-op review");
c.select("balanced");
await c.review();
await c.apply();
check((await c.undo()) && read(options.configPath) === installed, "Undo newest transaction");
check((await c.undo()) && read(options.configPath) === original && !exists(include), "Exact Undo");
check(await c.loadFile(profilePath), c.error);
check(!!c.actions.resize && !c.allowResize, "Profile consent defaults");
await c.review();
check(!(await c.apply()) && !exists(include), "Resize applied without consent");
c.consentResize(true);
check((await c.apply()) && read(include).includes("window-resize"), c.error);
check((await c.undo()) && read(options.configPath) === original, "Profile Undo");
c.openStudio();
check(launched[0].at(-1) === profilePath && launched[0].includes("--custom"), "Studio dispatch");
const invalid = `${profilePath}.invalid`;
write(invalid, '{"schema":999}');
const previous = c.document.name;
check(
  !(await c.loadFile(invalid)) && c.document.name === previous && !c.reviewPlan,
  "Invalid import changed selection",
);
c.select("custom");
await c.review();
c.consentResize(true);
const changed = JSON.parse(profile);
changed.actions.open.particles = 300;
write(profilePath, JSON.stringify(changed));
check(
  !(await c.apply()) && c.error.includes("plan changed") && !exists(include),
  "Stale JSON applied",
);
check(!(await c.review()) && c.error.includes("changed since loading"), "Unseen settings approved");
write(profilePath, profile);
c.select("balanced");
await c.review();
const edited = `${original}// External edit\n`;
write(options.configPath, edited);
check(
  !(await c.apply()) &&
    c.error.includes("plan changed") &&
    read(options.configPath) === edited &&
    !exists(include),
  "Stale root config overwritten",
);
write(options.configPath, original);
await c.review();
await c.apply();
const applied = read(options.configPath);
const shader = read(include);
write(options.configPath, `${applied}// Later edit\n`);
check(
  !(await c.undo()) && c.error.includes("File changed") && read(include) === shader,
  "Undo overwrote external changes",
);
write(options.configPath, applied);
await c.refreshUndo();
check(
  (await c.undo()) && read(options.configPath) === original && !exists(include),
  "Final restore",
);
const missing = new PickerController({
  ...options,
  run,
  launch: () => {},
  command: ["/nonexistent/nirifx-test-command"],
});
check(
  !(await missing.reload()) && !missing.busy && !!missing.error,
  "Missing executable left busy state",
);
console.log(
  "PASS GJS catalog, read-only selection/review, no-op, profiles, consent, consecutive Undo, stale files, conflicts, Studio dispatch and missing command",
);
