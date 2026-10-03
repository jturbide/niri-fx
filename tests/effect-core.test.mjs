// Test the actual offline browser core without a DOM or graphics driver.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { runInNewContext } from "node:vm";
import { projectRoot } from "../scripts/lib/browser.mjs";

const { catalog, expected } = JSON.parse(
  execFileSync(
    "python3",
    [
      "-c",
      `
import json
from niri_fx.preview import preview_catalog
from niri_fx.effects import PRESETS, FAMILIES, Effect, shader, resize_shader
print(json.dumps({"catalog": preview_catalog(Effect()), "expected": {
    name: {"open": shader(effect, True), "close": shader(effect, False),
           "resize": resize_shader(effect) if FAMILIES[effect.family]["resize"] else None}
    for name, effect in PRESETS.items()}}))
`,
    ],
    { cwd: projectRoot, encoding: "utf8", maxBuffer: 16 * 1024 * 1024 },
  ),
);
const source = readFileSync(new URL("../niri_fx/effect-core.js", import.meta.url), "utf8");
const create = (catalog) =>
  runInNewContext(source + "\ncreateEffectCore(catalog)", {
    catalog,
    TextEncoder,
    TextDecoder,
    btoa,
    atob,
  });
const core = create(catalog);
const plain = (value) => JSON.parse(JSON.stringify(value));
const cases = JSON.parse(readFileSync(new URL("fixtures/documents.json", import.meta.url)));

test("shared settings round-trip every preset and independent action without mutating inputs", () => {
  const profile = {
    kind: "profile",
    schema: 1,
    name: "Shared profile",
    actions: {
      open: catalog.presets["hexagon-burst"],
      close: catalog.presets["ink-spread"],
      resize: catalog.presets["spring-wobble"],
      movement: catalog.presets["pixel-transfer"],
    },
  };
  const documents = [
    ...Object.entries(catalog.presets).map(([name, effect]) => ({ schema: 3, name, effect })),
    profile,
  ];
  for (const doc of documents) {
    const before = JSON.stringify(doc),
      encoded = core.encodeShareDocument(doc);
    assert.match(encoded, /^[A-Za-z0-9_-]+$/);
    assert(encoded.length < 16000);
    assert.deepEqual(plain(core.decodeShareDocument(encoded)), plain(core.normalizePreset(doc)));
    assert.equal(JSON.stringify(doc), before);
  }
});

test("shared input rejects malformed, oversized and unsupported documents", () => {
  const encode = (value) => Buffer.from(JSON.stringify(value)).toString("base64url");
  for (const encoded of [
    "",
    "!bad",
    "a".repeat(22000),
    "_w",
    encode({ schema: 3, name: "Bad", effect: { shader: "script" } }),
    encode({ schema: 3, name: "Bad", effect: { family: "pixels", resize: true } }),
  ])
    assert.throws(() => core.decodeShareDocument(encoded));
});

for (const item of cases)
  test("document: " + item.name, () => {
    const before = JSON.stringify(item.document);
    if (item.valid) {
      const normalized = core.normalizePreset(item.document);
      assert.deepEqual(plain(core.normalizePreset(normalized)), plain(normalized));
    } else assert.throws(() => core.normalizePreset(item.document));
    assert.equal(JSON.stringify(item.document), before, "validation never edits caller state");
  });

test("every preset exports the same open, close and resize shaders as Python", () => {
  for (const [name, actions] of Object.entries(expected)) {
    const parameters = catalog.presets[name];
    assert.equal(core.shaderFor(parameters, true), actions.open, name + " open");
    assert.equal(core.shaderFor(parameters, false), actions.close, name + " close");
    if (actions.resize)
      assert.equal(core.shaderFor(parameters, false, true), actions.resize, name + " resize");
    else assert.throws(() => core.shaderFor(parameters, false, true), /does not support resize/);
  }
});

test("rounding ties and negative zero match Python's shader number contract", () => {
  assert.equal(core.glslNumber(0.0078125), "0.007813");
  assert.equal(core.glslNumber(-0.0078125), "-0.007813");
  assert.equal(core.glslNumber(-0.0000001), "0.000000");
});

test("unknown template tokens fail rather than generating undefined GLSL", () => {
  const invalid = create({ ...catalog, templates: { ...catalog.templates, pixels: "@MISSING@" } });
  assert.throws(
    () => invalid.shaderFor(catalog.presets["pixel-wipe"], false),
    /Unknown shader token/,
  );
});

test("stock profile KDL keeps resize opt-in and never emits experimental movement", () => {
  const profile = core.normalizePreset({
    kind: "profile",
    schema: 1,
    name: "Example",
    actions: {
      open: catalog.presets["spring-wobble"],
      close: catalog.presets["shockwave"],
      resize: null,
      movement: catalog.presets.balanced,
    },
  });
  const kdl = core.renderKdl(profile);
  assert.match(kdl, /window-open/);
  assert.match(kdl, /window-close/);
  assert.doesNotMatch(kdl, /window-resize|window-movement/);
  profile.actions.resize = catalog.presets.balanced;
  assert.match(core.renderKdl(profile), /window-resize/);
});
