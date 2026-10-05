// Portable CI checks deliberately do not require an experimental native checkout.
// The real Rust-emitted fixture is checked explicitly by test-fragment-mesh-render.mjs.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { test } from "node:test";
import { launchBrowser, projectRoot } from "../scripts/lib/browser.mjs";
import {
  meshVertex,
  meshEpilogue,
  renderFragmentMeshes,
} from "../scripts/lib/fragment-mesh-render.mjs";

test("square mesh material rejoins exactly and older renderers retain timed pixels", async () => {
  const shaders = JSON.parse(
    execFileSync(
      "python3",
      [
        "-c",
        `
import json
from dataclasses import replace
from niri_fx.effects import PRESETS, movement_shader, shader_templates, renderer_name, _expand
p=replace(PRESETS['balanced'],particles=800)
print(json.dumps(dict(source=movement_shader(p),baseline=_expand(shader_templates()['move-'+renderer_name(p)],p,False))))
`,
      ],
      { cwd: projectRoot, encoding: "utf8" },
    ),
  );
  const browser = await launchBrowser({ profilePrefix: "niri-fx-fragment-material-" });
  try {
    for (const filter of ["nearest", "linear"]) {
      const result = await browser.callFunction(renderFragmentMeshes.toString(), [
        { ...shaders, vertex: meshVertex, epilogue: meshEpilogue, filter },
      ]);
      assert.equal(result.rest.max, 0, `${filter}: stationary source pixels must be exact`);
      assert.ok(result.sourceClip, `${filter}: out-of-texture UVs must stay transparent`);
      assert.ok(
        result.fallback.every((v) => v.max === 0),
        `${filter}: timed fallback differs on old/native/browser interface`,
      );
    }
  } finally {
    await browser.close();
  }
});
