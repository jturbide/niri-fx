// Exercise resize-only choices against the actual Studio WebGL renderer.
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";

export async function checkResize(evaluate, setProgress, sample) {
  await evaluate(
    "byId('preset').value='ripple-collapse';byId('preset').dispatchEvent(new Event('change'))",
  );
  const change = async (field, value) =>
    evaluate(
      `byId(${JSON.stringify(field)}).value=${JSON.stringify(value)};byId(${JSON.stringify(field)}).dispatchEvent(new Event('input'))`,
    );
  const hash = () =>
    evaluate(
      `(()=>{const gl=byId('stage').getContext('webgl'),data=new Uint8Array(1000*760*4);gl.readPixels(0,0,1000,760,gl.RGBA,gl.UNSIGNED_BYTE,data);let hash=2166136261;for(const value of data)hash=Math.imul(hash^value,16777619);return hash;})()`,
    );
  const images = {};
  for (const mode of ["edge-ripple", "torsion"]) {
    await change("distortion_resize_mode", mode);
    await change("resize_strength", 1);
    await change("distortion_strength", 80);
    await change("resize_twist", 45);
    const parameters = await evaluate("parameters");
    assert.equal(parameters.resize, false, "choosing a mode never enables resize");
    const shader = execFileSync(
      "python3",
      [
        "-c",
        "import json,sys;from niri_fx.effects import Effect,resize_shader;print(resize_shader(Effect(**json.load(sys.stdin))),end='')",
      ],
      { input: JSON.stringify(parameters), encoding: "utf8" },
    );
    assert.equal(await evaluate("shaderFor(parameters,false,true)"), shader);
    const endpoints = {};
    for (const direction of ["grow", "shrink"]) {
      await evaluate(
        `byId('resize-direction').value='${direction}';byId('resize-direction').dispatchEvent(new Event('change'))`,
      );
      for (const p of [0, 0.2, 0.5, 0.8, 1]) {
        await setProgress(p);
        const geometry = direction === "grow" ? p : 1 - p;
        const result = await sample();
        assert.equal(
          result.occupied,
          (600 + 200 * geometry) * (380 + 60 * geometry),
          `${mode} ${direction} keeps every pixel in bounds at ${p}`,
        );
        assert.equal(result.error, 0);
        if (p === 0 || p === 1) endpoints[direction + p] = await hash();
        if (p === 0.5) images[mode + direction] = await hash();
      }
    }
    assert.equal(endpoints.grow0, endpoints.shrink1, "small texture restored exactly");
    assert.equal(endpoints.grow1, endpoints.shrink0, "large texture restored exactly");
    assert.notEqual(
      images[mode + "grow"],
      images[mode + "shrink"],
      "shrink changes direction at forward elapsed time",
    );
    await setProgress(0.5);
    await change("resize_strength", 0);
    const unchanged = await hash();
    await change("resize_strength", 1);
    if (mode === "torsion") {
      await change("resize_twist", 0);
      assert.equal(await hash(), unchanged, "zero twist is the base crossfade");
      await change("resize_twist", -45);
      assert.notEqual(await hash(), images[mode + "shrink"], "signed twist reverses rotation");
    } else {
      await change("distortion_strength", 0);
      assert.equal(await hash(), unchanged, "zero displacement is the base crossfade");
      await change("distortion_strength", 80);
    }
    // Stress matrices directly using the same shader program: extreme aspect
    // changes and no size change. Restore normal uniforms on the next draw.
    for (const [from, to] of [
      [
        [100, 600],
        [900, 40],
      ],
      [
        [900, 40],
        [100, 600],
      ],
      [
        [600, 380],
        [600, 380],
      ],
    ]) {
      await setProgress(0.5);
      await evaluate(`(()=>{const gl=byId('stage').getContext('webgl'),program=gl.getParameter(gl.CURRENT_PROGRAM),from=${JSON.stringify(from)},to=${JSON.stringify(to)},size=from.map((v,i)=>(v+to[i])/2);
        gl.uniform2f(gl.getUniformLocation(program,'fx_resize_from'),...from);gl.uniform2f(gl.getUniformLocation(program,'fx_resize_to'),...to);
        for(const [name,geometry] of [['prev',from],['next',to]])gl.uniformMatrix3fv(gl.getUniformLocation(program,'niri_curr_geo_to_'+name+'_geo'),false,new Float32Array([size[0]/geometry[0],0,0,0,size[1]/geometry[1],0,0,0,1]));gl.drawArrays(gl.TRIANGLES,0,6);})()`);
      const result = await sample();
      assert.equal(
        result.occupied,
        ((from[0] + to[0]) * (from[1] + to[1])) / 4,
        mode + " seals extreme aspect ratios",
      );
      assert.equal(result.error, 0);
    }
  }
  assert.notEqual(images["edge-ripplegrow"], images.torsiongrow, "modes have distinct interiors");
  const document = await evaluate("effectDocument()");
  await evaluate("byId('reduced-motion').checked=true;byId('open').click()");
  assert.equal(await evaluate("progress"), 1);
  assert.equal((await sample()).occupied, 600 * 380);
  await evaluate("byId('close').click()");
  assert.equal((await sample()).occupied, 800 * 440);
  assert.deepEqual(
    await evaluate("effectDocument()"),
    document,
    "preview direction and reduced motion leave exports unchanged",
  );
  await evaluate("byId('reduced-motion').checked=false;byId('resize-direction').value='grow'");
}
