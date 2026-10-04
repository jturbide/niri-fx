// A translucent texture exposes gaps and double ownership that opaque demos hide.
/* global document */
import assert from "node:assert/strict";

export function renderShape(
  source,
  {
    entry = "close_color",
    progress = 0,
    seed = 0.37,
    width = 144,
    height = 96,
    from = [144, 96],
    to = [192, 144],
    alphaValue = 128,
    includePixels = false,
    impulse = [1, 0],
  } = {},
) {
  // Reuse one owned context; repeatedly losing contexts can race GPU cleanup.
  if (!renderShape.context) {
    const canvas = document.createElement("canvas");
    canvas.width = 240;
    canvas.height = 192;
    renderShape.context = canvas.getContext("webgl", {
      premultipliedAlpha: true,
      preserveDrawingBuffer: true,
    });
  }
  const gl = renderShape.context,
    canvas = gl?.canvas;
  if (!gl) throw new Error("WebGL unavailable");
  const shaders = [];
  const program = gl.createProgram(),
    buffer = gl.createBuffer(),
    texture = gl.createTexture();
  const compile = (type, text) => {
    const shader = gl.createShader(type);
    shaders.push(shader);
    gl.shaderSource(shader, text);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS))
      throw new Error(gl.getShaderInfoLog(shader));
    return shader;
  };
  try {
    gl.attachShader(
      program,
      compile(gl.VERTEX_SHADER, "attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}"),
    );
    gl.attachShader(
      program,
      compile(
        gl.FRAGMENT_SHADER,
        `precision highp float;
      uniform sampler2D niri_tex;uniform mat3 niri_geo_to_tex;
      uniform float niri_random_seed;uniform float niri_clamped_progress;
      uniform sampler2D niri_tex_prev;uniform sampler2D niri_tex_next;
      uniform mat3 niri_geo_to_tex_prev;uniform mat3 niri_geo_to_tex_next;
      uniform mat3 niri_curr_geo_to_prev_geo;uniform mat3 niri_curr_geo_to_next_geo;
      uniform vec2 niri_move_delta;uniform vec2 niri_move_impulse;
      ${source}
      void main(){vec2 size=vec2(${width}.0,${height}.0);vec2 coords=(gl_FragCoord.xy-(vec2(240.,192.)-size)*.5)/size;
        gl_FragColor=${entry}(vec3(coords,1.),vec3(size,1.)${entry === "fragments_phase" ? ",0.0,0" : ""});}`,
      ),
    );
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS))
      throw new Error(gl.getProgramInfoLog(program));
    gl.useProgram(program);
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(
      gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
      gl.STATIC_DRAW,
    );
    const location = gl.getAttribLocation(program, "p");
    gl.enableVertexAttribArray(location);
    gl.vertexAttribPointer(location, 2, gl.FLOAT, false, 0, 0);
    gl.bindTexture(gl.TEXTURE_2D, texture);
    const pixels = new Uint8Array(width * height * 4);
    for (let i = 0; i < pixels.length; i += 4) {
      pixels[i] = 20 + ((i / 4) % 80);
      pixels[i + 1] = 45;
      pixels[i + 2] = 70;
      pixels[i + 3] = alphaValue;
    }
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    for (const name of [gl.TEXTURE_MIN_FILTER, gl.TEXTURE_MAG_FILTER])
      gl.texParameteri(gl.TEXTURE_2D, name, gl.NEAREST);
    for (const name of [gl.TEXTURE_WRAP_S, gl.TEXTURE_WRAP_T])
      gl.texParameteri(gl.TEXTURE_2D, name, gl.CLAMP_TO_EDGE);
    gl.uniformMatrix3fv(
      gl.getUniformLocation(program, "niri_geo_to_tex"),
      false,
      new Float32Array([1, 0, 0, 0, 1, 0, 0, 0, 1]),
    );
    for (const name of ["niri_geo_to_tex_prev", "niri_geo_to_tex_next"])
      gl.uniformMatrix3fv(
        gl.getUniformLocation(program, name),
        false,
        new Float32Array([1, 0, 0, 0, 1, 0, 0, 0, 1]),
      );
    for (const [name, size] of [
      ["prev", from],
      ["next", to],
    ])
      gl.uniformMatrix3fv(
        gl.getUniformLocation(program, "niri_curr_geo_to_" + name + "_geo"),
        false,
        new Float32Array([width / size[0], 0, 0, 0, height / size[1], 0, 0, 0, 1]),
      );
    gl.uniform2f(gl.getUniformLocation(program, "niri_move_impulse"), ...impulse);
    gl.uniform2f(gl.getUniformLocation(program, "niri_move_delta"), ...impulse.map((v) => v * 160));
    gl.uniform1f(gl.getUniformLocation(program, "niri_random_seed"), seed);
    gl.uniform1f(gl.getUniformLocation(program, "niri_clamped_progress"), progress);
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    // Exercise a new program before reading its settled framebuffer. This is
    // a rendering check, not a first-use shader compilation timing benchmark.
    gl.drawArrays(gl.TRIANGLES, 0, 6);
    gl.finish();
    gl.drawArrays(gl.TRIANGLES, 0, 6);
    gl.finish();
    const output = new Uint8Array(canvas.width * canvas.height * 4);
    gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, output);
    let occupied = 0,
      overlap = 0,
      alpha = 0,
      hash = 2166136261;
    for (let i = 0; i < output.length; i++) {
      hash = Math.imul(hash ^ output[i], 16777619);
      if (i % 4 === 3) {
        if (output[i]) occupied++;
        if (output[i] > 128) overlap++;
        alpha += output[i];
      }
    }
    return {
      occupied,
      overlap,
      alpha,
      hash,
      error: gl.getError(),
      ...(includePixels ? { pixels: Array.from(output) } : {}),
    };
  } finally {
    gl.deleteProgram(program);
    gl.deleteBuffer(buffer);
    gl.deleteTexture(texture);
    for (const shader of shaders) gl.deleteShader(shader);
  }
}

export async function checkShapes(evaluate) {
  await evaluate(`window.niriFxShapeProbe=${renderShape.toString()}`);
  const shapes = [
    "square",
    "rectangle",
    "triangle",
    "circle",
    "ellipse",
    "hexagon",
    "diamond",
    "star",
  ];
  const seen = new Set();
  for (const shape of shapes) {
    for (const aspect of [0.25, 1, 4]) {
      const effect = {
        fragment_shape: shape,
        fragment_aspect: aspect,
        fragment_orientation: 37,
        particles: 120,
        scatter: 90,
        gravity: "none",
        rotation: "random",
        spin: 180,
        dispersion: 0.6,
        stagger: 0,
        size_variation: 0.4,
        wave_strength: 0,
      };
      const expression = `{...catalog.defaults,...${JSON.stringify(effect)}}`;
      const probe = (options = {}, opening = false) =>
        evaluate(
          `window.niriFxShapeProbe(shaderFor(${expression},${opening}),${JSON.stringify({ entry: opening ? "open_color" : "close_color", ...options })})`,
        );
      const intact = await probe();
      const joined = await probe({ entry: "fragments_phase" });
      assert.equal(
        joined.occupied,
        144 * 96,
        `${shape} ${aspect} covers every source pixel without the endpoint shortcut`,
      );
      assert.equal(joined.overlap, 0, `${shape} ${aspect} gives translucent edges one owner`);
      assert.equal(joined.alpha, intact.alpha, `${shape} ${aspect} restores source alpha`);
      assert.equal(joined.error, 0);
      const middle = await probe({ progress: 0.375 });
      assert(middle.occupied > 0 && middle.alpha < intact.alpha, `${shape} visible breakup`);
      assert.equal(middle.error, 0);
      assert.deepEqual(
        await probe({ progress: 0.625 }, true),
        middle,
        `${shape} open and close use the same path`,
      );
      assert.deepEqual(await probe({ progress: 0.375 }), middle, `${shape} has no frame history`);
      assert.equal((await probe({ progress: 1 })).occupied, 0);
      if (aspect === 1) seen.add(middle.hash);
    }
  }
  assert.equal(
    seen.size,
    6,
    "unit-aspect rectangles/squares and ellipses/circles coincide; other silhouettes differ",
  );
  for (const [first, second] of [
    ["square", "triangle"],
    ["circle", "hexagon"],
    ["triangle", "star"],
    ["hexagon", "triangle"],
  ]) {
    for (const aspect of [0.25, 1, 4]) {
      const effect = {
        fragment_shape: first,
        fragment_secondary: second,
        fragment_mix: 0.45,
        fragment_aspect: aspect,
        fragment_orientation: 31,
        particles: 120,
        gravity: "none",
        rotation: "random",
        spin: 180,
        dispersion: 0.6,
        stagger: 0,
        wave_strength: 0.3,
      };
      const expression = `{...catalog.defaults,...${JSON.stringify(effect)}}`;
      const probe = (progress, extra = {}, opening = false) =>
        evaluate(
          `window.niriFxShapeProbe(shaderFor(${expression},${opening}),${JSON.stringify({ progress, entry: opening ? "open_color" : "close_color", ...extra })})`,
        );
      const intact = await probe(0, { entry: "fragments_phase" });
      assert.equal(intact.occupied, 144 * 96, first + "/" + second + " joined coverage");
      assert.equal(intact.overlap, 0, first + "/" + second + " disjoint ownership");
      const flight = await probe(0.375);
      assert(flight.occupied > 0 && flight.alpha < intact.alpha);
      assert.deepEqual(await probe(0.375), flight);
      assert.deepEqual(await probe(0.625, {}, true), flight);
      // A wider independent inverse search must not find any missed pieces.
      const wide = await evaluate(
        `window.niriFxShapeProbe(shaderFor(${expression},false).replace(/int y = -[0-9]+; y <= [0-9]+; y\\+\\+/g,'int y = -10; y <= 10; y++').replace(/int x = -[0-9]+; x <= [0-9]+; x\\+\\+/g,'int x = -10; x <= 10; x++'),{progress:0.375})`,
      );
      assert.deepEqual(wide, flight, first + "/" + second + " bounded lookup");
      assert.equal((await probe(1)).occupied, 0);
    }
  }
  const before = await evaluate("({document:effectDocument(),preset:byId('preset').value})");
  await evaluate(
    "byId('preset').value='triangle-shatter';byId('preset').dispatchEvent(new Event('change'))",
  );
  assert.equal(await evaluate("parameters.resize"), false);
  assert.equal(await evaluate("document.querySelector('[data-mode=swap]').disabled"), true);
  await evaluate("document.querySelector('[data-mode=resize]').click()");
  for (const field of [
    "fragment_shape",
    "fragment_aspect",
    "fragment_orientation",
    "fragment_transition",
  ])
    assert.equal(
      await evaluate(`byId('${field}').disabled`),
      field === "fragment_transition",
      field + " matches shaped resize capability",
    );
  await evaluate("document.querySelector('[data-mode=effect]').click()");
  assert.equal(await evaluate("parameters.fragment_shape"), "triangle");
  assert.equal(await evaluate("parameters.resize"), false);
  await evaluate(
    `loadDocument(${JSON.stringify(before.document)});byId('preset').value=${JSON.stringify(before.preset)};populate();refresh()`,
  );
  await evaluate(
    "window.niriFxShapeProbe.context.getExtension('WEBGL_lose_context')?.loseContext();delete window.niriFxShapeProbe",
  );
  console.log(
    "PASS: eight fragment shapes, joined translucent layouts, extreme aspects, reversibility and deterministic replay",
  );
}
