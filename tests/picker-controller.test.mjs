import assert from "node:assert/strict";
import test from "node:test";
import { PickerController } from "../niri_fx/gtk/controller.mjs";

const balanced = { family: "fragments", open_ms: 520, close_ms: 480, resize: false };
const catalog = { balanced, shockwave: { ...balanced, family: "distortion" } };
const profile = {
  kind: "profile",
  schema: 1,
  name: "Independent",
  actions: {
    open: balanced,
    close: catalog.shockwave,
    resize: { ...balanced, family: "elastic" },
    movement: null,
  },
};
const hash = "a".repeat(64);
function harness(handler = () => ({})) {
  const calls = [];
  const launches = [];
  const controller = new PickerController({
    command: ["/a path/niri-fx"],
    configPath: "/config.kdl",
    statePath: "/private-state",
    run: async (argv) => {
      calls.push(argv);
      return handler(argv.slice(1));
    },
    launch: (argv) => launches.push(argv),
  });
  controller.presets = Object.fromEntries(
    Object.entries(catalog).map(([id, effect]) => [
      id,
      { schema: 3, name: id, effect: structuredClone(effect) },
    ]),
  );
  controller.select("balanced");
  return { controller, calls, launches };
}
const plan = (effect, changes = [{ path: "/config.kdl", action: "update" }]) => ({
  effect,
  changes,
  plan_sha256: hash,
});

test("built-in profiles keep both actions and dispatch --profile through review and Studio", async () => {
  const doc = { ...profile, actions: { ...profile.actions, resize: null } };
  const {
    controller: c,
    calls,
    launches,
  } = harness((args) => (args[0] === "setup" ? plan(doc.actions) : {}));
  c.presets["paired"] = doc;
  c.filter("profile", "distortion");
  assert.deepEqual(
    c.items.map((row) => row.id),
    ["paired"],
  );
  c.select("paired");
  assert.equal(c.actions.close.family, "distortion");
  assert.equal(c.actions.resize, null);
  assert(await c.review());
  assert(c.canApply);
  assert(calls[0].includes("--profile"));
  c.openStudio();
  assert.deepEqual(launches[0].slice(-2), ["--profile", "paired"]);
  c.select("balanced");
  assert.equal(c.reviewPlan, null);
});

test("search and selection cannot activate settings or execute unknown IDs", async () => {
  const { controller: c, calls } = harness();
  c.filter("shock");
  assert.deepEqual(
    c.items.map((row) => row.id),
    ["shockwave"],
  );
  c.filter("", "fragments");
  assert.deepEqual(
    c.items.map((row) => row.id),
    ["balanced"],
  );
  assert.equal(c.families[1], "fragments");
  assert.equal(c.select("../not-a-preset"), false);
  assert.equal(c.selectedId, "balanced");
  assert.equal(await c.apply(), false);
  assert.deepEqual(calls, []);
});

test("activation passes the review hash and Undo pins its dedicated transaction", async () => {
  let applied = false;
  const { controller: c, calls } = harness((args) => {
    if (args[0] === "setup" && args.includes("--apply")) {
      applied = true;
      return { changed: true };
    }
    if (args[0] === "setup") return plan(balanced);
    if (args.includes("--apply")) {
      applied = false;
      return { transaction: "saved-transaction" };
    }
    if (!applied) throw new Error("No applied setup snapshot remains");
    return { transaction: "saved-transaction" };
  });
  assert.equal(await c.review(), true);
  assert.equal(c.canApply, true);
  assert.equal(await c.apply(), true);
  const apply = calls.find((args) => args[1] === "setup" && args.includes("--apply"));
  assert.deepEqual(apply.slice(-3), ["--expect-plan", hash, "--apply"]);
  assert.equal(c.reviewPlan, null);
  assert.equal(await c.undo(), true);
  assert.equal(c.error, "");
  assert.ok(
    calls.some((args) => args.includes("--transaction") && args.includes("saved-transaction")),
  );
  assert.equal(c.undoTransaction, "");
  assert.match(c.undoStatus, /No picker changes/);
});

test("a resize profile requires consent, which resets when the selection changes", async () => {
  const { controller: c, calls } = harness((args) =>
    args[0] === "inspect"
      ? structuredClone(profile)
      : args[0] === "setup"
        ? plan(profile.actions)
        : { transaction: "" },
  );
  await c.loadFile("/style with spaces.json");
  await c.review();
  assert.equal(c.canApply, false);
  const before = calls.length;
  assert.equal(await c.apply(), false);
  assert.equal(calls.length, before);
  c.consentResize(true);
  assert.equal(c.canApply, true);
  c.select("balanced");
  c.select("custom");
  assert.equal(c.allowResize, false);
  assert.equal(c.reviewPlan, null);
});

test("a style-level resize flag also requires consent", async () => {
  const doc = { schema: 3, name: "Resize", effect: { ...balanced, resize: true } };
  const { controller: c } = harness((args) =>
    args[0] === "inspect" ? doc : args[0] === "setup" ? plan(doc.effect) : { transaction: "" },
  );
  await c.loadFile("/style.json");
  await c.review();
  assert.equal(c.canApply, false);
  c.consentResize(true);
  assert.equal(c.canApply, true);
});

test("a JSON changed before review cannot introduce an unseen resize override", async () => {
  const shown = { ...profile, actions: { ...profile.actions, resize: null } };
  const { controller: c } = harness((args) =>
    args[0] === "inspect"
      ? shown
      : args[0] === "setup"
        ? plan(profile.actions)
        : { transaction: "" },
  );
  await c.loadFile("/profile.json");
  assert.equal(await c.review(), false);
  assert.match(c.error, /changed since loading/);
  assert.equal(c.canApply, false);
});

test("review compares data independent of object key order", async () => {
  const reordered = Object.fromEntries(Object.entries(balanced).reverse());
  const { controller: c } = harness(() => plan(reordered));
  assert.equal(await c.review(), true);
  assert.equal(c.canApply, true);
});

test("a backend refusal discards the review and preserves its error through history refresh", async () => {
  const { controller: c } = harness((args) => {
    if (args.includes("--apply")) throw new Error("The setup plan changed");
    if (args[0] === "restore") throw new Error("No setup snapshots exist");
    return plan(balanced);
  });
  await c.review();
  assert.equal(await c.apply(), false);
  assert.match(c.error, /plan changed/);
  assert.equal(c.reviewPlan, null);
  assert.equal(c.busy, false);
});

test("busy operations reject overlapping requests and selection changes", async () => {
  let finish;
  const { controller: c, calls } = harness(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const pending = c.review();
  assert.equal(c.busy, true);
  assert.equal(c.select("shockwave"), false);
  assert.equal(await c.loadFile("/other.json"), false);
  assert.equal(await c.apply(), false);
  assert.equal(calls.length, 1);
  finish(plan(balanced));
  assert.equal(await pending, true);
  assert.equal(c.selectedId, "balanced");
});

test("no-op reviews cannot create another transaction", async () => {
  const { controller: c, calls } = harness(() => plan(balanced, []));
  await c.review();
  assert.equal(c.canApply, false);
  await c.apply();
  assert.equal(calls.length, 1);
});

test("invalid imports retain the previous document but discard approval", async () => {
  const { controller: c } = harness((args) => {
    if (args[0] === "inspect") throw new Error("Unsupported parameters");
    if (args[0] === "setup") return plan(balanced);
    return { transaction: "" };
  });
  await c.review();
  await c.loadFile("/invalid.json");
  assert.equal(c.selectedId, "balanced");
  assert.equal(c.reviewPlan, null);
  assert.match(c.error, /Unsupported/);
});

test("Studio arguments preserve a literal custom path without shell evaluation", async () => {
  const { controller: c, launches } = harness((args) =>
    args[0] === "inspect" ? profile : { transaction: "" },
  );
  await c.loadFile("/styles/literal ; $(text).json");
  c.openStudio();
  assert.deepEqual(launches[0], [
    "/a path/niri-fx",
    "studio",
    "--target",
    "standalone",
    "--custom",
    "/styles/literal ; $(text).json",
  ]);
});

test("missing executables and malformed responses recover without a stuck busy state", async () => {
  for (const handler of [
    () => {
      throw new Error("Executable not found");
    },
    () => null,
  ]) {
    const { controller: c } = harness(handler);
    assert.equal(await c.review(), false);
    assert.ok(c.error);
    assert.equal(c.busy, false);
    assert.equal(c.canApply, false);
  }
});
