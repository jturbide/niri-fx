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
  process.argv.length >= 3 &&
    process.argv.slice(3).every((arg) => ["--extended", "--hardware"].includes(arg)),
  "Usage: node scripts/compare-fragment-renderers.mjs REFERENCE_CHECKOUT [--extended] [--hardware]",
);
const extended = process.argv.includes("--extended");
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
  browser = await launchBrowser({ software: !process.argv.includes("--hardware") });
  await browser.navigate(pathToFileURL(page).href);
  const renderer = await browser.evaluate(`(() => {
    const gl=byId('stage').getContext('webgl'), debug=gl.getExtension('WEBGL_debug_renderer_info');
    return debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : 'unavailable';
  })()`);
  if (process.argv.includes("--hardware")) {
    assert(
      !/swiftshader|llvmpipe|software|unavailable/i.test(renderer),
      "Hardware renderer not verified",
    );
  }
  console.log("Renderer: " + renderer);
  const cases =
    await browser.evaluate(`(()=>{    const cases=Object.entries(catalog.presets).filter(([,p])=>p.family==='fragments'&&(p.size_variation||p.wave_strength||p.direction_variation));
    for(const gravity of ['none','down','center','space']) cases.push(['uniform-grid-'+gravity,{...catalog.defaults,gravity,direction_variation:1,particles:4096,spin:720,dispersion:1,gravity_strength:3}]);
    return cases.map(([name, effect]) => [name, effect, [600, 380]]);})()`);
  if (extended) {
    const stress = await browser.evaluate(`(() => {
      const cases = [], gravities = catalog.specifications.gravity.choices;
      const geometries = [[900,280],[280,660],[5,3],[73,41],[600.5,380.25],[600,380],[960,120]];
      for (const [i, gravity] of gravities.entries()) {
        for (const wave of [0,1]) {
          const effect = {...catalog.defaults, gravity, gravity_strength:3,
            size_variation:1, direction_variation:1, dispersion:1,
            wave_strength:wave, wave_frequency:i%2 ? 4 : 0.25, wave_speed:4,
            swirl:i%2 ? -360 : 360, spin:720, rotation:i%2 ? 'gravity' : 'random',
            particles:i%2 ? 4096 : 0, tile_size:i%2 ? 8 : 128,
            origin_x:i%2, origin_y:(i+1)%2, scatter:240,
            stagger:0.4, release:catalog.specifications.release.choices[i+1], wave_span:0.7};
          cases.push(['extreme-'+gravity+'-wave-'+wave,effect,geometries[i]]);
        }
      }
      return cases;
    })()`);
    cases.push(...stress);
    // Include transparent margins, a hole and partial alpha in the sampled
    // texture. Both programs receive the same premultiplied WebGL upload.
    await browser.evaluate(`(() => {
      const texture = document.createElement('canvas'); texture.width=600; texture.height=380;
      const ctx=texture.getContext('2d');
      ctx.fillStyle='#b7e8db';ctx.fillRect(12,12,576,356);
      ctx.clearRect(110,80,180,110);
      ctx.clearRect(320,190,180,120);ctx.fillStyle='rgba(214,197,239,0.45)';ctx.fillRect(320,190,180,120);
      const gl=byId('stage').getContext('webgl'); gl.activeTexture(gl.TEXTURE0);
      gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL,true);
      gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,gl.RGBA,gl.UNSIGNED_BYTE,texture);
    })()`);
  }
  const results = [];
  for (const pair of cases) {
    const result = await browser.evaluate(`(async()=>{
    const reference=${JSON.stringify(template)}, optimized=catalog.templates.varied;
    const cases=[${JSON.stringify(pair)}];
    const gl=byId('stage').getContext('webgl'), length=byId('stage').width*byId('stage').height*4;
    // Isolate readbacks from displayed-canvas presentation and compositing.
    const target=gl.createFramebuffer(), color=gl.createTexture();
    gl.activeTexture(gl.TEXTURE2);gl.bindTexture(gl.TEXTURE_2D,color);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,byId('stage').width,byId('stage').height,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);
    gl.bindFramebuffer(gl.FRAMEBUFFER,target);
    gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,color,0);
    if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE) throw new Error('Incomplete comparison framebuffer');
    gl.activeTexture(gl.TEXTURE0);
    const results=[];
    for(const [name,p,geometry] of cases) {
      let worst=0, changed=0; const differences=[], referenceFrames=[];
      parameters=normalizePreset({schema:3,name:'Comparison',effect:p}).effect; populate();
      byId('pause').click();
      for(const [pass,source] of [reference,optimized].entries()) {
        catalog.templates.varied=source; refresh();
        if(document.documentElement.dataset.shaderStatus!=='ready') throw new Error(byId('error').textContent);
        const program=gl.getParameter(gl.CURRENT_PROGRAM);
        let index=0;
        for(const variant of [0.07,0.37,0.83]) for(const position of [0,0.03,0.25,0.5,0.8,0.97,1]) {
          // Use the same compiled program and texture with a different logical
          // window size. Set uniforms directly to avoid an extra default-size
          // Studio draw per frame; the full stage checks escaped particles too.
          gl.uniform1f(gl.getUniformLocation(program,'niri_random_seed'),variant);
          gl.uniform1f(gl.getUniformLocation(program,'niri_clamped_progress'),position);
          gl.uniform2f(gl.getUniformLocation(program,'fx_window'),...geometry);
          gl.drawArrays(gl.TRIANGLES,0,6);
          gl.finish();
          const pixels=new Uint8Array(length);
          gl.readPixels(0,0,byId('stage').width,byId('stage').height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
          if(gl.getError()!==gl.NO_ERROR||gl.isContextLost()) throw new Error("WebGL read failed");
          if(pass===0 && (position===0 || position===1)) {
            const visible=pixels.some((value,index)=>index%4===3 && value>0);
            if(visible!==(position===0)) throw new Error('Invalid reference endpoint: '+name);
          }
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
      results.push({name,geometry,worst,changed,differences});
    }
    gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.deleteFramebuffer(target);gl.deleteTexture(color);
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
