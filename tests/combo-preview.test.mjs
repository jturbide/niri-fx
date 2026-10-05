// Exercise the real catalog and portable validator; no DOM or graphics driver.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import { projectRoot } from "../scripts/lib/browser.mjs";

const catalog = JSON.parse(
  execFileSync(
    "python3",
    [
      "-c",
      "import json;from niri_fx.preview import preview_catalog;from niri_fx.effects import Effect;print(json.dumps(preview_catalog(Effect())))",
    ],
    { cwd: projectRoot, encoding: "utf8", maxBuffer: 4 * 1024 * 1024 },
  ),
);
const core = runInNewContext(
  readFileSync(new URL("../niri_fx/effect-core.js", import.meta.url), "utf8") +
    "\ncreateEffectCore(catalog)",
  { catalog },
);
const createComboPreview = runInNewContext(
  readFileSync(new URL("../niri_fx/combo-preview.js", import.meta.url), "utf8") +
    "\ncreateComboPreview",
  { structuredClone },
);
const createPointerDemo = runInNewContext(
  readFileSync(new URL("../niri_fx/pointer-preview.js", import.meta.url), "utf8") +
    "\ncreatePointerDemo",
);
const plain = (value) => JSON.parse(JSON.stringify(value));
const effect = (name, changes = {}) => ({ ...catalog.presets[name], resize: false, ...changes });
const mixed = () => ({
  kind: "profile",
  schema: catalog.profile_schema,
  name: "Mixed actions",
  actions: {
    open: effect("balanced", { open_ms: 320 }),
    close: effect("frost-vanish", { close_ms: 800 }),
    resize: effect("spring-wobble", { resize_ms: 120 }),
    movement: effect("pixel-transfer", { movement_ms: 240 }),
  },
});
function harness(extra = {}) {
  const frames = new Map(),
    cancelled = [],
    rendered = [],
    finished = [];
  let nextFrame = 0;
  const controller = createComboPreview({
    normalizeDocument: core.normalizePreset,
    families: catalog.families,
    pointerDemo: createPointerDemo,
    now: () => 1000,
    requestFrame: (callback) => {
      const id = nextFrame++;
      frames.set(id, callback);
      return id;
    },
    cancelFrame: (id) => cancelled.push(id),
    render: (state) => rendered.push(plain(state)),
    onFinish: (state) => finished.push(plain(state)),
    ...extra,
  });
  return { controller, frames, cancelled, rendered, finished };
}

test("a mixed combo plays each action's own style, duration and direction", () => {
  const { controller: c } = harness();
  const plan = c.plan(mixed(), { holdMs: 100, seed: 0.42 });
  assert.equal(plan.totalMs, 2340);
  const checks = [
    [0, "open", "fragments", 1, null],
    [160, "open", "fragments", 0.5, null],
    [320, "open", "fragments", 0, null],
    [480, "resize", "elastic", 0.5, "grow"],
    [700, "resize", "elastic", 0.5, "shrink"],
    [980, "movement", "pixels", 0.5, "right"],
    [1320, "movement", "pixels", 0.5, "left"],
    [1940, "close", "dissolve", 0.5, null],
    [2340, "close", "dissolve", 1, null],
  ];
  for (const [time, action, family, progress, direction] of checks) {
    const state = c.sample(plan, time);
    assert.equal(state.action, action, String(time));
    assert.equal(state.effect.family, family);
    assert.equal(state.progress, progress);
    assert.equal(state.direction, direction);
    assert.equal(state.seed, 0.42);
  }
  assert.match(c.sample(plan, 980).label, /Experimental movement shader preview/);
  assert.match(c.sample(plan, 980).support, /stock Niri exports omit movement/);
  assert.match(c.sample(plan, 480).support, /Stock Niri resize/);
  assert(c.sample(plan, 2340).complete);
});

test("selected pointer settings insert a deterministic drag and settle before closing", () => {
  const { controller: c } = harness();
  const document = mixed();
  document.pointer = { strength: 0.9, damping: 50, frequency: 6 };
  const before = structuredClone(document),
    plan = c.plan(document, { holdMs: 100 });
  assert.equal(plan.totalMs, 5540);
  const index = plan.stages.findIndex((stage) => stage.action === "pointer"),
    stage = plan.stages[index];
  assert.equal(plan.stages[index - 1].action, "movement");
  assert.equal(plan.stages[index + 1].action, "close");
  assert(Object.isFrozen(stage.pointerSettings));
  assert.deepEqual(plain(stage.pointerSettings), document.pointer);
  assert.deepEqual(plain(c.sample(plan, stage.startMs).offset), [0, 0]);
  const state = c.sample(plan, stage.startMs + 250);
  assert.equal(state.mode, "pointer");
  assert.equal(state.phase, "drag");
  assert(state.pointer.deformation.some((value) => value !== 0));
  assert.deepEqual(plain(state.offset), plain(state.pointer.offset));
  assert.match(state.support, /not compositor validation/);
  assert.equal(c.sample(plan, stage.startMs + 1400).phase, "settle");
  assert.deepEqual(plain(c.sample(plan, stage.startMs + 3199).offset), [0, 0]);
  assert.deepEqual(plain(c.sample(plan, stage.startMs + 3200).offset), [0, 0]);
  assert.deepEqual(document, before);
  // Capture scripts may serialize a plan and seek backwards without prior frames.
  const restored = plain(plan);
  for (const time of [1800, 1700, 3200, 1550, 4300, 1800])
    assert.deepEqual(plain(c.sample(restored, time)), plain(c.sample(plan, time)));
});

test("disabled and reduced-motion profiles omit the pointer stage", () => {
  const { controller: c } = harness();
  const document = mixed();
  for (const pointer of [null, { strength: 0, damping: 50, frequency: 6 }]) {
    document.pointer = pointer;
    assert(!c.plan(document).stages.some((stage) => stage.action === "pointer"));
  }
  document.pointer = { strength: 2, damping: 10, frequency: 2 };
  assert(
    !c.plan(document, { reducedMotion: true }).stages.some((stage) => stage.action === "pointer"),
  );
});

test("unavailable pointer preview does not interrupt existing playback", () => {
  const { controller: c, cancelled } = harness({ pointerDemo: undefined });
  c.play(mixed());
  const previous = c.currentPlan,
    document = mixed();
  document.pointer = { strength: 0.4, damping: 85, frequency: 10 };
  assert.throws(() => c.play(document), /Pointer preview is unavailable/);
  assert.equal(c.currentPlan, previous);
  assert(c.active);
  assert.deepEqual(cancelled, []);
});

test("paired movement keeps window position continuous and returns to the center", () => {
  const { controller: c } = harness();
  const plan = c.plan(mixed(), { holdMs: 100 });
  const offsets = [
    [860, 0],
    [980, 80],
    [1100, 160],
    [1200, 160],
    [1320, 80],
    [1440, 0],
    [1540, 0],
  ];
  for (const [time, x] of offsets) assert.deepEqual(plain(c.sample(plan, time).offset), [x, 0]);
});

test("disabled optional actions and shared styles never invent a movement or resize preview", () => {
  const { controller: c } = harness();
  const doc = mixed();
  doc.actions.resize = doc.actions.movement = null;
  const plan = c.plan(doc, { holdMs: 100 });
  assert.equal(plan.totalMs, 1220);
  for (let time = 0; time <= plan.totalMs; time += 20)
    assert(["open", "close"].includes(c.sample(plan, time).action));

  const shared = { schema: catalog.schema, name: "Shared", effect: effect("balanced") };
  assert.deepEqual(
    [...new Set(c.plan(shared).stages.map((stage) => stage.action))],
    ["open", "close"],
  );
  shared.effect.resize = true;
  assert.deepEqual(
    [...new Set(c.plan(shared).stages.map((stage) => stage.action))],
    ["open", "resize", "close"],
  );
});

test("every built-in profile can finish without enabling its suggested optional actions", () => {
  const { controller: c } = harness();
  for (const [id, document] of Object.entries(catalog.profiles)) {
    const original = JSON.stringify(document),
      plan = c.plan(document),
      final = c.sample(plan, plan.totalMs + 500);
    assert.equal(final.action, "close", id);
    assert.equal(final.progress, 1, id);
    assert(final.complete, id);
    assert.equal(JSON.stringify(document), original, id);
    for (const action of ["resize", "movement"])
      assert.equal(
        plan.stages.some((stage) => stage.action === action),
        !!document.actions[action],
      );
  }
});

test("the snapshot is isolated from later editing, Undo or renderer mutation", () => {
  const { controller: c } = harness();
  const document = mixed(),
    original = JSON.stringify(document),
    plan = c.plan(document);
  assert.equal(JSON.stringify(document), original);
  document.actions.open.open_ms = 1000;
  document.actions.resize = null;
  assert.equal(plan.document.actions.open.open_ms, 320);
  assert(plan.document.actions.resize);
  const state = c.sample(plan, 160);
  assert.throws(() => {
    state.effect.open_ms = 1500;
  }, TypeError);
  assert.equal(c.sample(plan, 160).effect.open_ms, 320);
});

test("reduced motion presents only endpoints with readable bounded holds", () => {
  const { controller: c } = harness();
  const plan = c.plan(mixed(), { holdMs: 100, reducedMotion: true });
  assert.equal(plan.totalMs, 500);
  for (let time = 0; time <= 500; time++) {
    const state = c.sample(plan, time);
    assert([0, 1].includes(state.progress));
    assert([0, 160].includes(state.offset[0]));
  }
  assert.equal(c.sample(plan, 0).progress, 0);
  assert.equal(c.sample(plan, 100).direction, "grow");
  assert.equal(c.sample(plan, 200).direction, "shrink");
  assert.equal(c.sample(plan, 300).direction, "right");
  assert.equal(c.sample(plan, 400).direction, "left");
  assert(c.sample(plan, 500).complete);
  const { controller: immediate, frames, rendered, finished } = harness();
  immediate.play(mixed(), { holdMs: 0, reducedMotion: true });
  assert.equal(frames.size, 0);
  assert.equal(rendered.at(-1).action, "close");
  assert.equal(rendered.at(-1).progress, 1);
  assert.equal(finished.length, 1);
});

test("stop cancels frames, including handle zero, and late callbacks cannot render old settings", () => {
  const { controller: c, frames, cancelled, rendered, finished } = harness();
  c.play(mixed());
  const initial = plain(rendered);
  c.stop();
  assert.equal(c.active, false);
  assert.deepEqual(cancelled, [0]);
  frames.get(0)(1160);
  assert.deepEqual(rendered, initial);
  assert.equal(finished.length, 0);

  const replacement = mixed();
  replacement.actions.open = effect("spring-wobble", { open_ms: 640 });
  c.play(replacement);
  frames.get(0)(1200);
  assert.equal(rendered.at(-1).effect.family, "elastic");
  frames.get(1)(1320);
  assert.equal(rendered.at(-1).progress, 0.5);
});

test("seek suspends automatic frames and yields the same capture on independent runs", () => {
  const first = harness(),
    second = harness();
  first.controller.play(mixed(), { seed: 0.82, holdMs: 100 });
  second.controller.play(mixed(), { seed: 0.82, holdMs: 100, manual: true });
  assert.equal(second.frames.size, 0);
  for (const time of [0, 160, 320, 420, 700, 980, 1320, 1940, 2340]) {
    assert.deepEqual(plain(first.controller.seek(time)), plain(second.controller.seek(time)));
    const captured = plain(first.rendered);
    first.frames.get(0)(2000);
    assert.deepEqual(first.rendered, captured);
  }
  assert.equal(first.frames.size, 1);
  assert.equal(first.finished.length, 1);
  assert.equal(second.finished.length, 1);
});

test("completion renders the transparent endpoint once and leaves no scheduled frame", () => {
  const { controller: c, frames, rendered, finished } = harness();
  const plan = c.play(mixed(), { holdMs: 0 });
  frames.get(0)(1000 + plan.totalMs + 1000);
  assert.equal(c.active, false);
  assert.equal(rendered.at(-1).action, "close");
  assert.equal(rendered.at(-1).progress, 1);
  assert.equal(finished.length, 1);
  assert.equal(frames.size, 1);
  frames.get(0)(1000 + plan.totalMs + 2000);
  c.seek(plan.totalMs);
  assert.equal(finished.length, 1);
});

test("an edit during rendering prevents completion or rescheduling of the cancelled preview", () => {
  let controller;
  const h = harness({
    render: () => controller.stop(),
  });
  controller = h.controller;
  controller.play(mixed());
  assert.equal(controller.active, false);
  assert.equal(h.frames.size, 0);
  assert.equal(h.finished.length, 0);
});

test("invalid documents or capture settings cannot interrupt a valid running preview", () => {
  const { controller: c, frames, cancelled } = harness();
  c.play(mixed());
  const plan = c.currentPlan;
  const invalid = mixed();
  invalid.actions.resize = effect("frost-vanish");
  assert.throws(() => c.play(invalid), /does not support resize/);
  assert.throws(() => c.play(mixed(), { seed: NaN }), /seed/);
  assert.throws(() => c.play(mixed(), { holdMs: 5001 }), /hold/);
  assert.throws(() => c.seek(Infinity), /timestamp/);
  assert.equal(c.currentPlan, plan);
  assert.equal(c.active, true);
  assert.equal(frames.size, 1);
  assert.deepEqual(cancelled, []);
});

test("a completion callback can start a new preview without an old frame being queued", () => {
  let controller;
  const h = harness({ onFinish: () => controller.play(mixed()) });
  controller = h.controller;
  const plan = controller.play(mixed(), { holdMs: 0 });
  h.frames.get(0)(1000 + plan.totalMs);
  assert.equal(controller.active, true);
  assert.equal(h.frames.size, 2);
  assert.equal(h.rendered.at(-1).progress, 1);
  h.frames.get(0)(1000 + plan.totalMs + 1000);
  assert.equal(h.frames.size, 2);
});

test("Preserve and Off need no fallback effect and keep distinct visible endpoints", () => {
  const { controller: c } = harness();
  for (const value of [null, "off"]) {
    const document = {
      kind: "profile",
      schema: 2,
      name: "No custom shaders",
      actions: { open: value, close: value, resize: value, movement: value },
    };
    const plan = c.plan(document, { holdMs: 100 });
    assert(plan.stages.every((stage) => stage.mode === "idle" && stage.effect === null));
    assert.equal(c.sample(plan, 0).visible, true);
    assert.equal(c.sample(plan, plan.totalMs).visible, value === null);
    assert.match(
      c.sample(plan, 0).support,
      value === null ? /desktop.*context/ : /animation disabled/,
    );
    assert.deepEqual(plain(plan.document), document);
    if (value === null)
      assert.deepEqual(plain(plan.stages.map((stage) => stage.action)), ["open", "close"]);
    else {
      const grow = plan.stages.find((stage) => stage.direction === "grow");
      assert.deepEqual(plain(c.sample(plan, grow.startMs).size), [800, 440]);
      const right = plan.stages.find((stage) => stage.direction === "right");
      assert.deepEqual(plain(c.sample(plan, right.startMs).offset), [160, 0]);
    }
  }
  const pointerOnly = {
    kind: "profile",
    schema: 2,
    name: "Pointer only",
    actions: { open: null, close: null, resize: null, movement: null },
    pointer: { strength: 0.9, damping: 50, frequency: 6 },
  };
  const plan = c.plan(pointerOnly),
    pointer = plan.stages.find((stage) => stage.action === "pointer");
  assert.equal(c.sample(plan, pointer.startMs + 250).mode, "pointer");
  assert(c.sample(plan, pointer.startMs + 250).pointer.deformation.some((value) => value !== 0));
});
