// Test the actual offline browser core without a DOM or graphics driver.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync } from "node:fs";
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
from niri_fx.effects import PRESETS, FAMILIES, Effect, shader, resize_shader, movement_shader
print(json.dumps({"catalog": preview_catalog(Effect()), "expected": {
    name: {"open": shader(effect, True), "close": shader(effect, False),
           "resize": resize_shader(effect) if FAMILIES[effect.family]["resize"] else None,
           "movement": movement_shader(effect) if FAMILIES[effect.family]["movement"] else None}
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
const compatibilityRoot = new URL("fixtures/compatibility/", import.meta.url);
const compatibility = readdirSync(compatibilityRoot, { withFileTypes: true })
  .filter((entry) => entry.isDirectory())
  .map((entry) =>
    JSON.parse(readFileSync(new URL(`${entry.name}/contract.json`, compatibilityRoot))),
  );
const subset = (actual, expected) =>
  expected && typeof expected === "object" && !Array.isArray(expected)
    ? Object.fromEntries(
        Object.entries(expected).map(([key, value]) => [key, subset(actual[key], value)]),
      )
    : actual;

test("versioned document examples retain Python and browser semantics", () => {
  assert(compatibility.length, "The versioned compatibility corpus is missing");
  const cases = compatibility.flatMap((corpus) => corpus.accepted_documents);
  const normalized = cases.map((item) => plain(core.normalizePreset(item.document)));
  const references = JSON.parse(
    execFileSync(
      "python3",
      [
        "-c",
        `
import json, sys
sys.path.insert(0, 'tests')
from helpers import stock_action_contract
from niri_fx.documents import parse_document, effect_document
from niri_fx.effects import render_kdl
data = json.load(sys.stdin)
result = []
for document, browser_export in zip(data['documents'], data['exports'], strict=True):
    name, _, effect = parse_document(document)
    result.append({'normalized': effect_document(name, effect),
                   'python_stock': stock_action_contract(render_kdl(effect)),
                   'browser_stock': stock_action_contract(browser_export)})
print(json.dumps(result))
`,
      ],
      {
        cwd: projectRoot,
        input: JSON.stringify({
          documents: cases.map((item) => item.document),
          exports: normalized.map((document) => core.renderKdl(document)),
        }),
        encoding: "utf8",
        maxBuffer: 4 * 1024 * 1024,
      },
    ),
  );
  for (const [index, item] of cases.entries()) {
    assert.deepEqual(subset(normalized[index], item.normalized), item.normalized, item.id);
    for (const key of item.absent) assert(!Object.hasOwn(normalized[index], key), item.id);
    assert.deepEqual(normalized[index], references[index].normalized, item.id);
    assert.deepEqual(references[index].python_stock, item.stock_actions, item.id);
    assert.deepEqual(references[index].browser_stock, item.stock_actions, item.id);
  }
});

test("versioned unsupported documents fail instead of dropping settings", () => {
  for (const corpus of compatibility)
    for (const item of corpus.rejected_documents)
      assert.throws(() => core.normalizePreset(item.document), undefined, item.id);
});

test("versioned catalog IDs retain their representative style and profile meanings", () => {
  for (const corpus of compatibility)
    for (const [identifier, expected] of Object.entries(corpus.catalog_documents)) {
      const document = catalog.profiles[identifier] || {
        schema: catalog.schema,
        name: identifier,
        effect: catalog.presets[identifier],
      };
      assert.deepEqual(
        subset(plain(core.normalizePreset(document)), expected),
        expected,
        identifier,
      );
    }
});

test("movement shader previews match the native exports and reject unsupported families", () => {
  for (const [name, effect] of Object.entries(catalog.presets)) {
    if (expected[name].movement)
      assert.equal(core.shaderFor(effect, false, false, true), expected[name].movement, name);
    else
      assert.throws(() => core.shaderFor(effect, false, false, true), /does not support movement/);
  }
});

test("continuous square movement eligibility matches Python without replacing unsupported materials", () => {
  const changes = [
    {},
    { movement_strength: 0 },
    { fragment_shape: "triangle" },
    { fragment_secondary: "circle", fragment_mix: 0.5 },
    { fragment_shape: "circle", fragment_secondary: "square", fragment_mix: 1 },
    { fragment_orientation: 12 },
    { fragment_roundness: 0.2 },
    { fragment_shrink: 0.2 },
    { size_variation: 0.2 },
    { direction_variation: 0.2 },
    { wave_strength: 0.2 },
    { rotation: "gravity" },
    { rotation: "none" },
    { release: "left" },
    { fragment_aspect: 4 },
  ];
  const references = JSON.parse(
    execFileSync(
      "python3",
      [
        "-c",
        `
import json, sys
from dataclasses import replace
from niri_fx.effects import PRESETS, movement_shader
print(json.dumps([movement_shader(replace(PRESETS['balanced'], **p)) for p in json.load(sys.stdin)]))
`,
      ],
      { cwd: projectRoot, input: JSON.stringify(changes), encoding: "utf8" },
    ),
  );
  changes.forEach((change, index) => {
    const effect = { ...catalog.presets.balanced, ...change };
    assert.equal(
      core.shaderFor(effect, false, false, true),
      references[index],
      JSON.stringify(change),
    );
  });
  for (const value of [null, undefined, "off", false, []])
    assert.equal(core.fragmentMotionEligible(value), false);
});

test("shaped lookup bounds and shaders match Python at extreme controls", () => {
  const shapes = catalog.specifications.fragment_shape.choices;
  const effects = shapes.flatMap((shape) =>
    [0.25, 4].map((aspect) => ({
      ...catalog.defaults,
      fragment_shape: shape,
      fragment_aspect: aspect,
      fragment_orientation: 37,
      fragment_roundness: 1,
      fragment_transition: 0.6,
      wave_strength: 1,
      dispersion: 1,
    })),
  );
  const expected = JSON.parse(
    execFileSync(
      "python3",
      [
        "-c",
        "import json,sys;from niri_fx.effects import Effect,shader;print(json.dumps([shader(Effect(**p),False) for p in json.load(sys.stdin)]))",
      ],
      { input: JSON.stringify(effects), encoding: "utf8", maxBuffer: 4 * 1024 * 1024 },
    ),
  );
  for (const [index, effect] of effects.entries())
    assert.equal(core.shaderFor(effect, false), expected[index]);
});

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

test("desktop motion survives share round-trips and exports the Python spring groups", () => {
  for (const [name, doc] of Object.entries(catalog.profiles)) {
    if (!doc.motion) continue;
    const normalized = core.normalizePreset(doc);
    assert.deepEqual(
      plain(core.decodeShareDocument(core.encodeShareDocument(doc))),
      plain(normalized),
    );
    const kdl = core.renderKdl(normalized);
    for (const action of ["workspace-switch", "horizontal-view-movement", "overview-open-close"])
      assert(kdl.includes(action), name + " " + action);
    assert.doesNotMatch(kdl, /window-resize|window-movement/);
    for (const bad of [true, NaN, Infinity, -1]) {
      const invalid = structuredClone(doc);
      invalid.motion.camera.stiffness = bad;
      assert.throws(() => core.normalizePreset(invalid), /Motion/);
    }
  }
});

test("pointer settings survive share links and normalize inheritance without changing builtins", () => {
  for (const doc of Object.values(catalog.profiles)) assert.equal(doc.pointer, undefined);
  const profile = {
    kind: "profile",
    schema: 1,
    name: "Pointer combo",
    actions: { open: {}, close: {}, resize: null, movement: null },
  };
  const inherited = core.normalizePreset({ ...profile, pointer: null });
  assert.equal(Object.hasOwn(inherited, "pointer"), false);
  for (const settings of [
    catalog.pointer_defaults,
    ...Object.values(catalog.pointer_presets).map((item) => item.settings),
    { ...catalog.pointer_defaults, strength: 0 },
  ]) {
    const document = { ...profile, pointer: settings };
    assert.deepEqual(
      plain(core.decodeShareDocument(core.encodeShareDocument(document))),
      plain(core.normalizePreset(document)),
    );
    assert.doesNotMatch(
      core.renderKdl(core.normalizePreset(document)),
      /window-movement|pointer-wobble/,
    );
  }
  for (const [key, bad] of [
    ["strength", NaN],
    ["strength", Infinity],
    ["damping", true],
    ["frequency", 8.5],
  ]) {
    assert.throws(
      () => core.normalizePointer({ ...catalog.pointer_defaults, [key]: bad }),
      /Pointer/,
    );
  }
});

test("native pointer and timed movement KDL match Python and share one animation node", () => {
  const document = core.normalizePreset({
    kind: "profile",
    schema: 1,
    name: "Pointer combo",
    actions: {
      open: catalog.presets["spring-wobble"],
      close: catalog.presets["balanced"],
      resize: null,
      movement: catalog.presets["pixel-transfer"],
    },
    motion: catalog.motion_packs.gentle,
    pointer: { ...catalog.pointer_defaults, strength: 0.0078125 },
  });
  for (const movement of [false, true]) {
    for (const pointer of [false, true]) {
      const kdl = core.renderKdl(document, { movement, pointer });
      const expected = execFileSync(
        "python3",
        [
          "-c",
          "import json,sys;from niri_fx.documents import parse_document;from niri_fx.effects import render_kdl;data=json.load(sys.stdin);print(render_kdl(parse_document(data['document'])[2], **data['options']), end='')",
        ],
        { input: JSON.stringify({ document, options: { movement, pointer } }), encoding: "utf8" },
      );
      // Generated-by comments identify the caller; all emitted config is shared.
      assert.equal(kdl.slice(kdl.indexOf("\n")), expected.slice(expected.indexOf("\n")));
      assert.equal(
        (kdl.match(/ {4}window-movement \{/g) || []).length,
        movement || pointer ? 1 : 0,
      );
      assert.equal((kdl.match(/pointer-wobble \{/g) || []).length, pointer ? 1 : 0);
    }
  }
  for (const doc of [
    { ...document, pointer: null },
    { schema: 3, name: "Style", effect: catalog.defaults },
  ])
    assert.throws(() => core.renderKdl(doc, { pointer: true }), /explicitly choose pointer/);
  assert.throws(
    () =>
      core.renderKdl(
        { ...document, actions: { ...document.actions, movement: null } },
        { movement: true, pointer: true },
      ),
    /explicitly choose a movement/,
  );
});

test("schema 2 action modes round-trip and legacy input migrates without changing choices", () => {
  const document = {
    kind: "profile",
    schema: 2,
    name: "Action modes",
    actions: { open: null, close: "off", resize: "off", movement: "off" },
    pointer: { ...catalog.pointer_defaults, strength: 0 },
  };
  assert.deepEqual(plain(core.decodeShareDocument(core.encodeShareDocument(document))), document);
  const stock = core.renderKdl(document);
  assert.doesNotMatch(stock, /window-open|window-movement|pointer-wobble|custom-shader/);
  assert.match(stock, /window-close \{\n {8}off/);
  assert.match(stock, /window-resize \{\n {8}off/);
  assert.match(
    core.renderKdl(document, { movement: true }),
    /window-movement \{\n {8}off\n {8}preserve-pointer/,
  );
  assert.match(
    core.renderKdl(document, { pointer: true }),
    /window-movement \{\n {8}preserve-movement\n {8}pointer-wobble/,
  );
  const combined = core.renderKdl(document, { movement: true, pointer: true });
  assert.doesNotMatch(combined, /preserve-pointer|preserve-movement/);
  assert.equal((combined.match(/window-movement/g) || []).length, 1);
  const old = {
    ...document,
    schema: 1,
    actions: { open: {}, close: {}, resize: null, movement: null },
  };
  const upgraded = core.normalizePreset(old);
  assert.equal(upgraded.schema, 2);
  assert.equal(upgraded.actions.resize, null);
  assert.equal(upgraded.actions.movement, null);
  for (const actions of [
    document.actions,
    { ...old.actions, open: null },
    { ...old.actions, close: "off" },
  ])
    assert.throws(() => core.normalizePreset({ ...old, actions }));
  for (const name of ["", "bad\n", null])
    assert.throws(() => core.normalizePreset({ ...document, name }), /Name must/);
});

test("independent swaps round-trip and export their own timed shader", () => {
  for (const swap of [catalog.presets["pixel-relay"], catalog.presets.balanced, "off", null]) {
    const input = {
      kind: "profile",
      schema: 3,
      name: "Independent swaps",
      actions: {
        open: null,
        close: "off",
        resize: null,
        movement: catalog.presets["fragment-wake"],
        swap,
      },
    };
    const doc = core.normalizePreset(input);
    assert.equal(doc.schema, swap === null ? 2 : 3);
    assert.deepEqual(plain(core.decodeShareDocument(core.encodeShareDocument(doc))), plain(doc));
    for (const enabled of [false, ...(swap === null ? [] : [true])]) {
      const options = { movement: true, swap: enabled };
      const actual = core.renderKdl(doc, options);
      const expected = execFileSync(
        "python3",
        [
          "-c",
          "import json,sys;from niri_fx.documents import parse_document;from niri_fx.effects import render_kdl;d=json.load(sys.stdin);print(render_kdl(parse_document(d['document'])[2], **d['options']), end='')",
        ],
        { input: JSON.stringify({ document: doc, options }), encoding: "utf8" },
      );
      assert.equal(actual.slice(actual.indexOf("\n")), expected.slice(expected.indexOf("\n")));
      assert.equal(actual.includes("window-swap"), enabled);
    }
  }
  assert.throws(() =>
    core.normalizePreset({
      kind: "profile",
      schema: 2,
      name: "Invalid",
      actions: {
        open: null,
        close: null,
        resize: null,
        movement: null,
        swap: "off",
      },
    }),
  );
});

const fragmentDefaults = () =>
  Object.fromEntries(
    Object.entries(catalog.fragment_controls).map(([name, control]) => [name, control.default]),
  );
const fragmentProfile = (fragment_motion = fragmentDefaults()) => ({
  kind: "profile",
  schema: 4,
  name: "Portable response",
  actions: {
    open: null,
    close: "off",
    resize: null,
    movement: catalog.fragment_presets.tear.effect,
    swap: null,
  },
  fragment_motion,
});

test("complete fragment responses preserve preset values, dormant choices and shared links", () => {
  assert.equal(Object.keys(catalog.fragment_controls).length, 18);
  for (const preset of Object.values(catalog.fragment_presets)) {
    for (const movement of [null, "off", preset.effect, catalog.presets["pixel-relay"]]) {
      const input = fragmentProfile(preset.settings);
      input.actions.movement = movement;
      const before = JSON.stringify(input);
      const normalized = core.normalizePreset(input);
      assert.equal(normalized.schema, 4);
      assert.equal(normalized.actions.swap, null);
      assert.deepEqual(plain(normalized.fragment_motion), preset.settings);
      assert.deepEqual(
        plain(core.decodeShareDocument(core.encodeShareDocument(input))),
        plain(normalized),
      );
      assert.deepEqual(plain(core.normalizePreset(normalized)), plain(normalized));
      assert.doesNotMatch(core.renderKdl(normalized), /window-movement|fragment-motion/);
      assert.equal(JSON.stringify(input), before);
    }
  }
  assert.equal(core.normalizeFragmentMotion(null), null);
});

test("fragment responses reject incomplete maps, invalid controls and inverted timing ranges", () => {
  const invalid = [null, {}, [], true, "tear", { ...fragmentDefaults(), unknown: 1 }];
  for (const [key, control] of Object.entries(catalog.fragment_controls)) {
    const missing = fragmentDefaults();
    delete missing[key];
    invalid.push(missing);
    const bad =
      control.kind === "choice"
        ? [0, true, "elsewhere"]
        : [
            true,
            "1",
            null,
            control.minimum - 1,
            control.maximum + 1,
            ...(control.exclusive_min ? [control.minimum] : []),
            ...(control.kind === "integer" ? [control.default + 0.5] : []),
          ];
    invalid.push(...bad.map((value) => ({ ...fragmentDefaults(), [key]: value })));
    if (control.kind !== "choice")
      for (const value of [NaN, Infinity, -Infinity])
        assert.throws(() => core.normalizeFragmentMotion({ ...fragmentDefaults(), [key]: value }));
  }
  invalid.push(
    { ...fragmentDefaults(), delay_near_ms: 100, delay_far_ms: 99 },
    { ...fragmentDefaults(), response_near_ms: 100, response_far_ms: 99 },
  );
  const documents = invalid.map(fragmentProfile);
  for (const schema of [1, 2, 3]) {
    const actions = { ...fragmentProfile().actions };
    if (schema < 3) delete actions.swap;
    documents.push({ ...fragmentProfile(), schema, actions });
  }
  const missingResponse = fragmentProfile();
  delete missingResponse.fragment_motion;
  const missingSwap = fragmentProfile();
  delete missingSwap.actions.swap;
  documents.push(missingResponse, missingSwap);
  for (const document of documents) assert.throws(() => core.normalizePreset(document));
  const accepted = JSON.parse(
    execFileSync(
      "python3",
      [
        "-c",
        `
import json, sys
from niri_fx.documents import parse_document
accepted=[]
for document in json.load(sys.stdin):
    try:
        parse_document(document)
        accepted.append(True)
    except ValueError:
        accepted.append(False)
print(json.dumps(accepted))
`,
      ],
      { input: JSON.stringify(documents), encoding: "utf8" },
    ),
  );
  assert.deepEqual(
    accepted,
    documents.map(() => false),
  );
});

test("portable fragment KDL matches Python without rounding native response precision", () => {
  const settings = {
    ...fragmentDefaults(),
    batches: 64.0,
    distance_exponent: 1e-8,
    delay_jitter: 0.12345678912345678,
    response_jitter: 0,
    tilt: -0,
  };
  const cases = [];
  for (const movement of [
    null,
    "off",
    catalog.fragment_presets.tear.effect,
    catalog.presets["pixel-relay"],
    { ...catalog.fragment_presets.tear.effect, fragment_shape: "circle" },
  ]) {
    const document = fragmentProfile(settings);
    document.actions.movement = movement;
    document.actions.swap = catalog.presets.balanced;
    document.pointer = catalog.pointer_defaults;
    for (const options of [
      {},
      { pointer: true },
      { swap: true },
      ...(movement === null
        ? []
        : [
            { movement: true, pointer: true, swap: true },
            { movement: true, continuous_fragments: false },
          ]),
    ])
      cases.push({ document, options });
  }
  const references = JSON.parse(
    execFileSync(
      "python3",
      [
        "-c",
        `
import json, sys
from niri_fx.documents import parse_document, effect_document
from niri_fx.effects import render_kdl
result=[]
for item in json.load(sys.stdin):
    name, _, profile=parse_document(item['document'])
    result.append({'document':effect_document(name, profile),
                   'kdl':render_kdl(profile, **item['options'])})
print(json.dumps(result))
`,
      ],
      { input: JSON.stringify(cases), encoding: "utf8", maxBuffer: 4 * 1024 * 1024 },
    ),
  );
  const semantic = (kdl) =>
    kdl.slice(kdl.indexOf("\n")).replace(/( {12}[a-z-]+) ([^\n]+)(?=\n)/g, (line, key, value) => {
      // Python and JavaScript use different valid JSON exponent spellings.
      // Compare native scalar values while retaining every shader byte.
      if (
        !Object.keys(catalog.fragment_controls).some(
          (name) => key.trim() === name.replaceAll("_", "-"),
        )
      )
        return line;
      return key + " " + JSON.stringify(JSON.parse(value));
    });
  cases.forEach(({ document, options }, index) => {
    const normalized = core.normalizePreset(document);
    assert.deepEqual(plain(normalized), references[index].document);
    const actual = core.renderKdl(normalized, options);
    assert.equal(semantic(actual), semantic(references[index].kdl));
    const active =
      options.movement &&
      options.continuous_fragments !== false &&
      core.fragmentMotionEligible(normalized.actions.movement);
    assert.equal(actual.includes("fragment-motion {"), Boolean(active));
    if (active) {
      assert.match(actual, /distance-exponent 1e-8\n/);
      assert.match(actual, /delay-jitter 0\.12345678912345678\n/);
    }
    if (options.swap)
      assert.doesNotMatch(actual.split("    window-swap {")[1], /fragment-motion|NIRIFX_FRAGMENT/);
  });
});
