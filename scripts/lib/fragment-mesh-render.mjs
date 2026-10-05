// Shared software-GPU oracle. Native fixtures contain the actual Rust-emitted
// mesh; this module performs rasterization only and has no follower simulation.
export const meshVertex = `attribute vec2 vert;
attribute vec4 vert_position;
attribute vec3 vert_extra;
uniform mat3 matrix;
varying vec2 niri_mesh_source_uv, niri_mesh_local, niri_mesh_half_extent;
varying float niri_mesh_edge_blend;
void main() {
 niri_mesh_source_uv=vert_position.xy; niri_mesh_local=vert_position.zw;
 niri_mesh_half_extent=vert_extra.xy; niri_mesh_edge_blend=vert_extra.z;
 gl_Position=vec4(matrix*vec3(vert,1.),1.);
}`;
export const meshEpilogue = `varying vec2 niri_mesh_source_uv, niri_mesh_local, niri_mesh_half_extent;
varying float niri_mesh_edge_blend;
void main() { gl_FragColor=fragment_motion_mesh_color(niri_mesh_source_uv,
 niri_mesh_local,niri_mesh_half_extent,niri_mesh_edge_blend)*niri_alpha; }`;

// This function is serialized into the isolated browser, so keep it self-contained.
export function renderFragmentMeshes(payload) {
  const canvas = globalThis.document.createElement("canvas");
  canvas.width = payload.fixture ? 1024 : 256;
  canvas.height = payload.fixture ? 768 : 192;
  const gl = canvas.getContext("webgl", { antialias: false, premultipliedAlpha: true });
  if (!gl) throw new Error("WebGL is unavailable");
  const header = `precision highp float;
uniform sampler2D niri_tex;
uniform mat3 niri_geo_to_tex;
uniform float niri_clamped_progress,niri_random_seed,niri_scale,niri_alpha;
uniform vec2 niri_move_delta,niri_move_impulse,test_size,test_origin;\n`;
  function compile(type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS))
      throw new Error(gl.getShaderInfoLog(shader));
    return shader;
  }
  function program(vertex, fragment) {
    const result = gl.createProgram();
    gl.attachShader(result, compile(gl.VERTEX_SHADER, vertex));
    gl.attachShader(result, compile(gl.FRAGMENT_SHADER, fragment));
    gl.linkProgram(result);
    if (!gl.getProgramParameter(result, gl.LINK_STATUS))
      throw new Error(gl.getProgramInfoLog(result));
    return result;
  }
  const mesh = program(
    payload.vertex,
    header + "#define NIRIFX_FRAGMENT_MESH 1\n" + payload.source + payload.epilogue,
  );
  const reference = program(
    payload.vertex,
    header +
      `
varying vec2 niri_mesh_source_uv;
void main(){vec2 uv=niri_mesh_source_uv;
 if(any(lessThan(uv,vec2(0.)))||any(greaterThanEqual(uv,vec2(1.))))gl_FragColor=vec4(0.);
 else gl_FragColor=texture2D(niri_tex,uv);}`,
  );
  const textureRect = payload.fixture?.texture_rect || [0, 0, 160, 120];
  const width = textureRect[2],
    height = textureRect[3];
  const texture = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, texture);
  const filter = payload.filter === "linear" ? gl.LINEAR : gl.NEAREST;
  for (const [key, value] of [
    [gl.TEXTURE_MIN_FILTER, filter],
    [gl.TEXTURE_MAG_FILTER, filter],
    [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE],
    [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE],
  ])
    gl.texParameteri(gl.TEXTURE_2D, key, value);
  const data = new Uint8Array(width * height * 4);
  for (let y = 0; y < height; y++)
    for (let x = 0; x < width; x++) {
      const a = x < 8 || y < 8 || x >= width - 8 || y >= height - 8 ? 96 : 255;
      const checker = ((x >> 4) + (y >> 4)) % 2;
      data.set(
        [
          Math.round((0.2 + (0.65 * x) / width) * a),
          Math.round((0.2 + (0.65 * y) / height) * a),
          Math.round((checker ? 0.7 : 0.25) * a),
          a,
        ],
        (y * width + x) * 4,
      );
    }
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, data);
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  const buffer = gl.createBuffer();
  const origin = payload.fixture ? [220, 100] : [48, 36];
  function uniform(p, name, kind, ...values) {
    gl[kind](gl.getUniformLocation(p, name), ...values);
  }
  function frame(p, vertices, area, target = [0, 0]) {
    gl.useProgram(p);
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(vertices.flat()), gl.STREAM_DRAW);
    for (let i = 0; i < gl.getParameter(gl.MAX_VERTEX_ATTRIBS); i++) gl.disableVertexAttribArray(i);
    for (const [name, size, offset] of [
      ["vert", 2, 0],
      ["vert_position", 4, 8],
      ["vert_extra", 3, 24],
    ]) {
      const index = gl.getAttribLocation(p, name);
      if (index < 0) continue;
      gl.enableVertexAttribArray(index);
      gl.vertexAttribPointer(index, size, gl.FLOAT, false, 36, offset);
    }
    uniform(p, "matrix", "uniformMatrix3fv", false, [
      (2 * area[2]) / canvas.width,
      0,
      0,
      0,
      (-2 * area[3]) / canvas.height,
      0,
      (2 * (origin[0] + target[0] + area[0])) / canvas.width - 1,
      1 - (2 * (origin[1] + target[1] + area[1])) / canvas.height,
      1,
    ]);
    uniform(p, "niri_scale", "uniform1f", 1);
    uniform(p, "niri_alpha", "uniform1f", 1);
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    gl.drawArrays(gl.TRIANGLES, 0, vertices.length);
    const pixels = new Uint8Array(canvas.width * canvas.height * 4);
    gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    if (gl.getError() !== gl.NO_ERROR) throw new Error("Mesh render failed");
    return pixels;
  }
  const corners = [
    [0, 0],
    [1, 0],
    [0, 1],
    [0, 1],
    [1, 0],
    [1, 1],
  ];
  const quad = corners.map(([x, y]) => [
    x,
    y,
    x,
    y,
    (x - 0.5) * width,
    (y - 0.5) * height,
    width / 2,
    height / 2,
    0,
  ]);
  function difference(a, b) {
    let changed = 0,
      max = 0,
      alphaMax = 0;
    for (let i = 0; i < a.length; i++) {
      const d = Math.abs(a[i] - b[i]);
      if (d) changed++;
      max = Math.max(max, d);
      if (i % 4 === 3) alphaMax = Math.max(alphaMax, d);
    }
    return { changed, max, alphaMax };
  }
  function premultiplied(pixels) {
    for (let i = 0; i < pixels.length; i += 4)
      if (Math.max(pixels[i], pixels[i + 1], pixels[i + 2]) > pixels[i + 3] + 1) return false;
    return true;
  }
  const result = {};
  if (payload.fixture) {
    const frames = payload.fixture.frames;
    const byName = Object.fromEntries(frames.map((f) => [f.name, f]));
    const render = (name) => {
      const f = byName[name];
      return frame(mesh, f.vertices, f.area, f.target);
    };
    result.rest = difference(render("rest"), frame(reference, quad, textureRect));
    result.settled = difference(
      render("settled"),
      frame(reference, quad, textureRect, byName.settled.target),
    );
    result.press = difference(render("rest"), render("press"));
    const moving = render("step-540");
    result.premultiplied = premultiplied(moving);
    result.moving = difference(
      moving,
      frame(reference, quad, textureRect, byName["step-540"].target),
    );
    result.regrab = difference(render("regrab-before"), render("regrab-after"));
    // A protected source has transparent pixels beyond its rectangle, including
    // cells whose rotated corners extend outside its original texture margins.
    result.sourceClip = frame(
      mesh,
      quad.map((v) => [...v.slice(0, 2), v[2] + 2, v[3], ...v.slice(4)]),
      textureRect,
    ).every((v) => v === 0);
    if (payload.proof) {
      render("step-540");
      result.proof = canvas.toDataURL("image/png");
    }
  } else {
    result.rest = difference(frame(mesh, quad, textureRect), frame(reference, quad, textureRect));
    result.sourceClip = frame(
      mesh,
      quad.map((v) => [...v.slice(0, 2), v[2] + 2, v[3], ...v.slice(4)]),
      textureRect,
    ).every((v) => v === 0);
    const timedVertex = "attribute vec2 p;void main(){gl_Position=vec4(p,0.,1.);}";
    const timedMain =
      "\nvoid main(){gl_FragColor=move_color(vec3((gl_FragCoord.xy-test_origin)/test_size,1.),vec3(test_size,1.));}";
    const programs = [
      payload.baseline,
      ...[0, 1, 2, 3].map(
        (v) => (v ? `#define NIRIFX_FRAGMENT_MOTION ${v}\n` : "") + payload.source,
      ),
    ].map((s) => program(timedVertex, header + s + timedMain));
    function timed(p, progress) {
      gl.useProgram(p);
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(
        gl.ARRAY_BUFFER,
        new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
        gl.STREAM_DRAW,
      );
      for (let i = 0; i < gl.getParameter(gl.MAX_VERTEX_ATTRIBS); i++)
        gl.disableVertexAttribArray(i);
      const index = gl.getAttribLocation(p, "p");
      gl.enableVertexAttribArray(index);
      gl.vertexAttribPointer(index, 2, gl.FLOAT, false, 0, 0);
      uniform(p, "test_size", "uniform2f", width, height);
      uniform(p, "test_origin", "uniform2f", 48, 36);
      uniform(p, "niri_geo_to_tex", "uniformMatrix3fv", false, [1, 0, 0, 0, 1, 0, 0, 0, 1]);
      uniform(p, "niri_clamped_progress", "uniform1f", progress);
      uniform(p, "niri_random_seed", "uniform1f", 0.372);
      uniform(p, "niri_move_impulse", "uniform2f", 0.7, 0.3);
      uniform(p, "niri_move_delta", "uniform2f", 350, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
      const pixels = new Uint8Array(canvas.width * canvas.height * 4);
      gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
      if (gl.getError() !== gl.NO_ERROR) throw new Error("Timed fallback render failed");
      return pixels;
    }
    result.fallback = [];
    for (const progress of [0, 0.32, 0.75, 1]) {
      const expected = timed(programs[0], progress);
      for (const p of programs.slice(1))
        result.fallback.push(difference(expected, timed(p, progress)));
    }
  }
  return result;
}
