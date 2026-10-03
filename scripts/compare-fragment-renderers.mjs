// Compare optimized fragment output against an archived reference template.
// This is a development regression check, not a compositor performance claim.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { launchBrowser, projectRoot } from "./lib/browser.mjs";

assert(
  process.argv.length === 3,
  "Usage: node scripts/compare-fragment-renderers.mjs REFERENCE_CHECKOUT",
);
const reference = resolve(process.argv[2]);
const template = readFileSync(join(reference, "niri_fx/shaders/varied.glsl"), "utf8").replace(
  "@ACTION_ENTRY@",
  readFileSync(join(reference, "niri_fx/shaders/varied-entry.glsl"), "utf8").trimEnd(),
);
const scratch = mkdtempSync(join(tmpdir(), "nirifx-parity-"));
let browser;
try {
  const page = join(scratch, "preview.html");
  execFileSync("python3", ["-m", "niri_fx", "preview", "--output", page], { cwd: projectRoot });
  browser = await launchBrowser();
  await browser.navigate(pathToFileURL(page).href);
  const cases =
    await browser.evaluate(`(()=>{    const cases=Object.entries(catalog.presets).filter(([,p])=>p.family==='fragments'&&(p.size_variation||p.wave_strength||p.direction_variation));
    for(const gravity of ['none','down','center','space']) cases.push(['uniform-grid-'+gravity,{...catalog.defaults,gravity,direction_variation:1,particles:4096,spin:720,dispersion:1,gravity_strength:3}]);
return cases;})()`);
  const results = [];
  for (const pair of cases) {
    const result = await browser.evaluate(`(async()=>{
    const reference=${JSON.stringify(template)}, optimized=catalog.templates.varied;
    const cases=[${JSON.stringify(pair)}];
    const gl=byId('stage').getContext('webgl'), length=byId('stage').width*byId('stage').height*4;
    const results=[];
    for(const [name,p] of cases) {
      let worst=0, changed=0; const differences=[], referenceFrames=[];
      parameters={...p}; populate();
      for(const [pass,source] of [reference,optimized].entries()) {
        catalog.templates.varied=source; refresh();
        if(document.documentElement.dataset.shaderStatus!=='ready') throw new Error(byId('error').textContent);
        let index=0;
        for(const variant of [0.07,0.37,0.83]) for(const position of [0,0.03,0.25,0.5,0.8,0.97,1]) {
          seed=variant;
          byId('progress').value=position*1000;byId('progress').dispatchEvent(new Event('input'));
          gl.finish();
          const pixels=new Uint8Array(length);
          gl.readPixels(0,0,byId('stage').width,byId('stage').height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
          if(gl.getError()!==gl.NO_ERROR||gl.isContextLost()) throw new Error("WebGL read failed");
          if(pass===0) referenceFrames.push(pixels);
          else {
            const a=referenceFrames[index]; let frameWorst=0, frameChanges=0;
            for(let i=0;i<length;i++){const d=Math.abs(a[i]-pixels[i]);worst=Math.max(worst,d);frameWorst=Math.max(frameWorst,d);if(d){changed++;frameChanges++;}}
            if(frameWorst>1) differences.push({variant,position,frameWorst,frameChanges});
          }
          index++;
          await new Promise(resolve=>setTimeout(resolve,0));
        }
      }
      results.push({name,worst,changed,differences});
    }
    return results;
  })()`);
    results.push(result[0]);
    console.log(JSON.stringify(result[0]));
  }
  assert(
    results.every((r) => r.worst <= 1),
    "All comparisons must stay within one 8-bit quantization step",
  );
  console.log(`PASS ${results.length * 21} pairs of rendered frames`);
} finally {
  await browser?.close();
  rmSync(scratch, { recursive: true, force: true });
}
