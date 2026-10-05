// The browser receives native Rust vertex arrays, not a second motion model.
// Keep this function self-contained: CDP serializes it into an owned context.
export async function benchmarkFragmentMesh(payload) {
  const canvas = globalThis.document.createElement("canvas");
  canvas.width = payload.width;
  canvas.height = payload.height;
  const gl = canvas.getContext("webgl", {
    alpha: true,
    antialias: false,
    depth: false,
    stencil: false,
    premultipliedAlpha: true,
    preserveDrawingBuffer: true,
  });
  if (!gl) throw new Error("WebGL is unavailable");
  const started = performance.now();
  const textures = [],
    buffers = [],
    programs = [],
    shaders = [];
  const debug = gl.getExtension("WEBGL_debug_renderer_info");
  const timer = gl.getExtension("EXT_disjoint_timer_query");
  const hardware = {
    renderer: debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : "unavailable",
    vendor: debug ? gl.getParameter(debug.UNMASKED_VENDOR_WEBGL) : "unavailable",
    webgl: gl.getParameter(gl.VERSION),
    shadingLanguage: gl.getParameter(gl.SHADING_LANGUAGE_VERSION),
    userAgent: globalThis.navigator.userAgent,
    timer: Boolean(timer),
    timerBits: timer ? timer.getQueryEXT(timer.TIME_ELAPSED_EXT, timer.QUERY_COUNTER_BITS_EXT) : 0,
  };
  const fail = (message) => {
    throw new Error(message);
  };
  function checkTime() {
    if (gl.isContextLost() || performance.now() - started > 45000)
      fail("GPU case timed out or context was lost");
  }
  function checkGl() {
    checkTime();
    const error = gl.getError();
    if (error !== gl.NO_ERROR) fail("WebGL error: " + error);
  }
  try {
    if (
      /swiftshader|llvmpipe|lavapipe|softpipe|software|unavailable|unknown|basic render/i.test(
        hardware.renderer,
      )
    )
      return { status: "unsupported", reason: "Hardware renderer not verified", hardware };
    if (!timer || hardware.timerBits < 1)
      return { status: "unsupported", reason: "GPU timer queries unavailable", hardware };
    if (Math.max(canvas.width, canvas.height) > gl.getParameter(gl.MAX_RENDERBUFFER_SIZE))
      fail("Requested framebuffer exceeds hardware limits");
    if (gl.drawingBufferWidth !== canvas.width || gl.drawingBufferHeight !== canvas.height)
      fail("Browser did not allocate the requested framebuffer");

    function compile(type, source) {
      const result = gl.createShader(type);
      shaders.push(result);
      gl.shaderSource(result, source);
      gl.compileShader(result);
      if (!gl.getShaderParameter(result, gl.COMPILE_STATUS)) fail(gl.getShaderInfoLog(result));
      return result;
    }
    const header = `precision highp float;
uniform sampler2D niri_tex;
uniform mat3 niri_geo_to_tex;
uniform float niri_clamped_progress,niri_random_seed,niri_scale,niri_alpha;
uniform vec2 niri_move_delta,niri_move_impulse;
`;
    function program(fragment) {
      const value = gl.createProgram();
      programs.push(value);
      gl.attachShader(value, compile(gl.VERTEX_SHADER, payload.vertex));
      gl.attachShader(value, compile(gl.FRAGMENT_SHADER, header + fragment));
      gl.linkProgram(value);
      if (!gl.getProgramParameter(value, gl.LINK_STATUS)) fail(gl.getProgramInfoLog(value));
      return {
        value,
        matrix: gl.getUniformLocation(value, "matrix"),
        scale: gl.getUniformLocation(value, "niri_scale"),
        alpha: gl.getUniformLocation(value, "niri_alpha"),
        texture: gl.getUniformLocation(value, "niri_tex"),
        attributes: [
          [gl.getAttribLocation(value, "vert"), 2, 0],
          [gl.getAttribLocation(value, "vert_position"), 4, 8],
          [gl.getAttribLocation(value, "vert_extra"), 3, 24],
        ],
      };
    }
    const mesh = program("#define NIRIFX_FRAGMENT_MESH 1\n" + payload.source + payload.epilogue);
    const reference = program(`varying vec2 niri_mesh_source_uv;
void main() {
 vec2 uv=niri_mesh_source_uv;
 if(any(lessThan(uv,vec2(0.)))||any(greaterThanEqual(uv,vec2(1.)))) gl_FragColor=vec4(0.);
 else gl_FragColor=texture2D(niri_tex,uv)*niri_alpha;
}`);
    const fixture = payload.fixture;
    const rect = fixture.texture_rect;
    const width = rect[2],
      height = rect[3];
    if (Math.max(width, height) > gl.getParameter(gl.MAX_TEXTURE_SIZE))
      fail("Native fixture texture exceeds hardware limits");
    const scale = Math.min((canvas.width * 0.54) / width, (canvas.height * 0.54) / height);
    const centers = {
      1: [[0.5, 0.5]],
      2: [
        [0.42, 0.42],
        [0.58, 0.58],
      ],
      4: [
        [0.36, 0.36],
        [0.64, 0.36],
        [0.36, 0.64],
        [0.64, 0.64],
      ],
    }[payload.windows];
    const layout = centers.map(([x, y]) => ({
      origin: [x * canvas.width - (width * scale) / 2, y * canvas.height - (height * scale) / 2],
      size: [width * scale, height * scale],
    }));
    for (let window = 0; window < payload.windows; window++) {
      const texture = gl.createTexture();
      textures.push(texture);
      gl.bindTexture(gl.TEXTURE_2D, texture);
      for (const [key, value] of [
        [gl.TEXTURE_MIN_FILTER, gl.LINEAR],
        [gl.TEXTURE_MAG_FILTER, gl.LINEAR],
        [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE],
        [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE],
      ])
        gl.texParameteri(gl.TEXTURE_2D, key, value);
      const data = new Uint8Array(width * height * 4);
      for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x++) {
          const alpha = x < 8 || y < 8 || x >= width - 8 || y >= height - 8 ? 96 : 255;
          const checker = ((x >> 4) + (y >> 4)) % 2;
          const rgb = [0.15 + (0.7 * x) / width, 0.15 + (0.7 * y) / height, checker ? 0.72 : 0.26];
          const offset = (y * width + x) * 4;
          for (let c = 0; c < 3; c++)
            data[offset + c] = Math.round(rgb[(c + window) % 3] * alpha * (1 - window * 0.06));
          data[offset + 3] = alpha;
        }
      }
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, data);
    }
    function upload(vertices, area) {
      const value = gl.createBuffer();
      buffers.push(value);
      gl.bindBuffer(gl.ARRAY_BUFFER, value);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(vertices.flat()), gl.STATIC_DRAW);
      return { value, count: vertices.length, area };
    }
    const states = Object.fromEntries(
      fixture.states.map((state) => [state.name, upload(state.vertices, state.area)]),
    );
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
    const original = upload(quad, rect);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    gl.disable(gl.DEPTH_TEST);
    gl.disable(gl.CULL_FACE);
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.clearColor(0, 0, 0, 0);
    const opacity = 0.88;
    function draw(p, state, omit = -1, alpha = opacity) {
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.useProgram(p.value);
      gl.bindBuffer(gl.ARRAY_BUFFER, state.value);
      for (let i = 0; i < 3; i++) gl.disableVertexAttribArray(i);
      for (const [index, size, offset] of p.attributes) {
        if (index < 0) continue;
        gl.enableVertexAttribArray(index);
        gl.vertexAttribPointer(index, size, gl.FLOAT, false, 36, offset);
      }
      gl.uniform1f(p.scale, scale);
      gl.uniform1f(p.alpha, alpha);
      gl.uniform1i(p.texture, 0);
      gl.activeTexture(gl.TEXTURE0);
      const area = state.area;
      for (let window = 0; window < payload.windows; window++) {
        if (window === omit) continue;
        const origin = layout[window].origin;
        gl.uniformMatrix3fv(p.matrix, false, [
          (2 * area[2] * scale) / canvas.width,
          0,
          0,
          0,
          (-2 * area[3] * scale) / canvas.height,
          0,
          (2 * (origin[0] + (area[0] - rect[0]) * scale)) / canvas.width - 1,
          1 - (2 * (origin[1] + (area[1] - rect[1]) * scale)) / canvas.height,
          1,
        ]);
        gl.bindTexture(gl.TEXTURE_2D, textures[window]);
        gl.drawArrays(gl.TRIANGLES, 0, state.count);
      }
    }
    function pixels(p, state, omit = -1, alpha = opacity) {
      draw(p, state, omit, alpha);
      const result = new Uint8Array(canvas.width * canvas.height * 4);
      gl.readPixels(0, 0, canvas.width, canvas.height, gl.RGBA, gl.UNSIGNED_BYTE, result);
      checkGl();
      return result;
    }
    function difference(a, b) {
      let changedPixels = 0,
        max = 0;
      for (let i = 0; i < a.length; i += 4) {
        let changed = false;
        for (let c = 0; c < 4; c++) {
          const d = Math.abs(a[i + c] - b[i + c]);
          if (d) changed = true;
          if (d > max) max = d;
        }
        if (changed) changedPixels++;
      }
      return { changedPixels, max };
    }
    // All readbacks and endpoint/negative controls finish before warmup or queries.
    const expected = pixels(reference, original);
    const rest = difference(pixels(mesh, states.rest), expected);
    const settled = difference(pixels(mesh, states.settled), expected);
    if (rest.max || settled.max) fail("Native identity mesh differs from the source quad");
    const moving = pixels(mesh, states.moving);
    const deformation = difference(moving, expected);
    if (deformation.changedPixels < canvas.width * canvas.height * 0.01)
      fail("Native moving mesh did not produce meaningful deformation");
    let coveredPixels = 0;
    for (let i = 0; i < moving.length; i += 4) {
      if (moving[i + 3]) coveredPixels++;
      if (Math.max(moving[i], moving[i + 1], moving[i + 2]) > moving[i + 3] + 1)
        fail("Mesh output is not premultiplied");
    }
    if (coveredPixels < canvas.width * canvas.height * 0.08)
      fail("Too few visible pixels for a useful window workload");
    const contributions = layout.map(
      (_, window) => difference(moving, pixels(mesh, states.moving, window)).changedPixels,
    );
    if (contributions.some((count) => count < canvas.width * canvas.height * 0.01))
      fail("An overlapping window did not contribute meaningful pixels");
    if (pixels(mesh, states.moving, -1, 0).some((value) => value !== 0))
      fail("Zero-opacity negative control produced pixels");
    gl.finish();
    checkGl();

    const measurements = [],
      batchNanoseconds = [];
    // A single mesh draw can be close to this driver's timer granularity. Use
    // the same fixed work amplification for every sample, case and repeat.
    // These are averages of warm, repeated compositions, not frame percentiles.
    const compositionsPerQuery = 32;
    const warmup = 12;
    for (let index = -warmup; index < payload.samples; index++) {
      checkTime();
      if (gl.getParameter(timer.GPU_DISJOINT_EXT))
        fail("GPU timer became disjoint; discard this run");
      const query = timer.createQueryEXT();
      try {
        timer.beginQueryEXT(timer.TIME_ELAPSED_EXT, query);
        for (let composition = 0; composition < compositionsPerQuery; composition++)
          draw(mesh, states.moving);
        timer.endQueryEXT(timer.TIME_ELAPSED_EXT);
        gl.flush();
        const deadline = performance.now() + 3000;
        while (!timer.getQueryObjectEXT(query, timer.QUERY_RESULT_AVAILABLE_EXT)) {
          checkTime();
          if (performance.now() > deadline) fail("GPU timer query timed out");
          await new Promise((resolve) => setTimeout(resolve, 2));
        }
        if (gl.getParameter(timer.GPU_DISJOINT_EXT))
          fail("GPU timer became disjoint; discard this run");
        const nanoseconds = timer.getQueryObjectEXT(query, timer.QUERY_RESULT_EXT);
        const ms = nanoseconds / 1000000 / compositionsPerQuery;
        checkGl();
        if (!Number.isFinite(ms) || ms <= 0)
          fail(`Invalid GPU timer result (${nanoseconds} ns; sample ${index})`);
        if (index >= 0) {
          batchNanoseconds.push(nanoseconds);
          measurements.push(ms);
        }
      } finally {
        timer.deleteQueryEXT(query);
      }
    }
    const sorted = [...measurements].sort((a, b) => a - b);
    const percentile = (p) => sorted[Math.ceil(sorted.length * p) - 1];
    return {
      status: "measured",
      hardware,
      framebuffer: [canvas.width, canvas.height],
      actualCells: fixture.actual_cells,
      verticesPerWindow: states.moving.count,
      windows: payload.windows,
      windowLayout: layout,
      scale,
      opacity,
      filter: "LINEAR",
      texture: [width, height],
      pose: "moving",
      poseMs: fixture.states.find((state) => state.name === "moving").ms,
      warmup,
      compositionsPerQuery,
      samples: measurements.length,
      batchNanoseconds,
      compositionAveragesMs: measurements,
      batchAverageMs: { p50: percentile(0.5), p95: percentile(0.95), p99: percentile(0.99) },
      validation: {
        rest,
        settled,
        deformation,
        coveredPixels,
        coverage: coveredPixels / (canvas.width * canvas.height),
        contributionPixels: contributions,
        zeroOpacity: true,
        premultiplied: true,
      },
      elapsedMs: performance.now() - started,
    };
  } catch (error) {
    return {
      status: "failed",
      reason: error.message,
      hardware,
      elapsedMs: performance.now() - started,
    };
  } finally {
    for (const value of textures) gl.deleteTexture(value);
    for (const value of buffers) gl.deleteBuffer(value);
    for (const value of programs) gl.deleteProgram(value);
    for (const value of shaders) gl.deleteShader(value);
    gl.getExtension("WEBGL_lose_context")?.loseContext();
  }
}
