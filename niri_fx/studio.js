const catalog = JSON.parse(document.getElementById("effect-catalog").textContent);
const byId = (id) => document.getElementById(id);
const numeric = [
  "tile_size",
  "scatter",
  "gravity_strength",
  "particles",
  "spin",
  "swirl",
  "open_ms",
  "close_ms",
  "dispersion",
  "stagger",
  "resize_ms",
  "resize_strength",
  "origin_x",
  "origin_y",
  "wave_span",
  "slice_count",
  "slice_angle",
  "slice_distance",
  "slice_stagger",
  "slice_rotation",
  "size_variation",
  "direction_variation",
  "wave_strength",
  "wave_frequency",
  "wave_speed",
  "slice_travel_variation",
  "slice_rotation_variation",
  "elastic_strength",
  "elastic_frequency",
  "elastic_damping",
];
const units = {
  tile_size: " px",
  scatter: " px",
  gravity_strength: "×",
  particles: "",
  spin: "°",
  swirl: "°",
  open_ms: " ms",
  close_ms: " ms",
  dispersion: "",
  stagger: "",
  resize_ms: " ms",
  resize_strength: "",
  origin_x: "",
  origin_y: "",
  wave_span: "",
  slice_count: "",
  slice_angle: "°",
  slice_distance: " px",
  slice_stagger: "",
  slice_rotation: "°",
  size_variation: "",
  direction_variation: "",
  wave_strength: "",
  wave_frequency: " cycles",
  wave_speed: " cycles",
  slice_travel_variation: "",
  slice_rotation_variation: "",
  elastic_strength: "",
  elastic_frequency: " cycles",
  elastic_damping: "",
};
let parameters = { ...catalog.parameters },
  frame = 0,
  seed = 0.37,
  program = null,
  lastSource = "",
  mode = "effect";
const query = new URLSearchParams(location.search);
if (catalog.presets[query.get("preset")]) parameters = { ...catalog.presets[query.get("preset")] };
let progress = Number(query.get("breakup") ?? 0.45);
progress = Number.isFinite(progress) ? Math.min(1, Math.max(0, progress)) : 0.45;
const title = (s) => s.replaceAll("-", " ").replace(/\b\w/g, (c) => c.toUpperCase());
const customOption = document.createElement("option");
customOption.value = "";
customOption.textContent = "Custom / imported";
byId("preset").append(customOption);
for (const name of Object.keys(catalog.presets)) {
  const option = document.createElement("option");
  option.value = name;
  option.textContent = title(name);
  byId("preset").append(option);
}
byId("preset").value = query.get("preset") || (catalog.presets[catalog.name] ? catalog.name : "");
byId("name").value = catalog.presets[catalog.name]
  ? "My " + title(byId("preset").value)
  : catalog.name;
function populate() {
  for (const key of numeric) {
    byId(key).step =
      key.endsWith("_ms") || ["particles", "slice_count"].includes(key) ? "1" : "any";
    byId(key).value = key === "particles" ? parameters.particles || 240 : parameters[key];
  }
  for (const key of [
    "gravity",
    "rotation",
    "release",
    "resize_mode",
    "slice_direction",
    "slice_order",
    "elastic_axis",
  ])
    byId(key).value = parameters[key];
  byId("resize").checked = parameters.resize;
  byId("density").value = parameters.particles ? "count" : "tile";
  byId("family").value = parameters.family;
  labels();
  if (
    (mode === "resize" && !catalog.families[parameters.family].resize) ||
    (["move", "swap"].includes(mode) && !catalog.families[parameters.family].concept)
  )
    document.querySelector("[data-mode=effect]").click();
}
function labels() {
  const fragment = parameters.family === "fragments",
    capabilities = catalog.families[parameters.family];
  byId("fragment-controls").hidden = !fragment;
  byId("fragment-note").hidden = !fragment;
  byId("slice-controls").hidden = parameters.family !== "slices";
  byId("elastic-controls").hidden = parameters.family !== "elastic";
  byId("resize-controls").hidden = !capabilities.resize;
  byId("family-note").textContent = fragment
    ? "Open, close and optional resize. Move/swap previews are experimental concepts."
    : parameters.family === "elastic"
      ? "Whole-window wobble. Open/close on stock Niri; native movement requires the patched compositor."
      : "Open and close. Slice resize and movement are not supported in this release.";
  for (const option of byId("preset").options)
    option.hidden = !!option.value && catalog.presets[option.value].family !== parameters.family;
  for (const tab of document.querySelectorAll("[data-mode]"))
    tab.disabled =
      tab.dataset.mode === "resize"
        ? !capabilities.resize
        : ["move", "swap"].includes(tab.dataset.mode)
          ? !capabilities.concept
          : false;
  byId("variation-controls").hidden = mode === "resize" || parameters.family === "elastic";
  byId("slice-variation").hidden = fragment;
  byId("wave_frequency").disabled = byId("wave_speed").disabled = !parameters.wave_strength;
  byId("slice_stagger").disabled = parameters.slice_order === "together";
  byId("variation-note").textContent = fragment
    ? "Uneven cells and waves cost more to render. These controls affect open/close and the separate movement experiment, not resize."
    : "Size variation keeps adjacent strip boundaries joined. Frequency controls the wavelength; lower frequencies make wider waves.";
  byId("count-control").hidden = byId("density").value !== "count";
  byId("tile-control").hidden = byId("density").value !== "tile";
  for (const key of numeric)
    byId(key + "-value").textContent = Number(Number(byId(key).value).toFixed(3)) + units[key];
  for (const key of [
    "scatter",
    "dispersion",
    "stagger",
    "swirl",
    "open_ms",
    "close_ms",
    "origin_x",
    "origin_y",
    "release",
    "wave_span",
  ])
    byId(key).disabled = mode === "resize";
  byId("seed").disabled = mode === "resize" || parameters.family === "elastic";
  byId("wave_span").disabled = mode === "resize" || parameters.release === "together";
  byId("gravity_strength").disabled = mode === "resize" || byId("gravity").value === "none";
  byId("spin").disabled = byId("rotation").value === "none";
}
function shaderFor(p, opening, resizing = false) {
  if (resizing && !catalog.families[p.family].resize)
    throw new Error("This effect family does not support resize.");
  const classic =
    p.gravity === "none" &&
    !p.particles &&
    p.rotation === "none" &&
    p.swirl === 0 &&
    p.dispersion === 0 &&
    p.stagger === 0 &&
    p.release === "together" &&
    p.origin_x === 0.5 &&
    p.origin_y === 0.5;
  const tokens = {
    ELASTIC_STRENGTH: p.elastic_strength.toFixed(6),
    ELASTIC_FREQUENCY: p.elastic_frequency.toFixed(6),
    ELASTIC_DAMPING: p.elastic_damping.toFixed(6),
    ELASTIC_AXIS: String(catalog.elastic_axes.indexOf(p.elastic_axis)),
    SIZE_VARIATION: p.size_variation.toFixed(6),
    DIRECTION_VARIATION: p.direction_variation.toFixed(6),
    WAVE_STRENGTH: p.wave_strength.toFixed(6),
    WAVE_FREQUENCY: p.wave_frequency.toFixed(6),
    WAVE_SPEED: p.wave_speed.toFixed(6),
    SLICE_ORDER: String(catalog.slice_orders.indexOf(p.slice_order)),
    SLICE_TRAVEL_VARIATION: p.slice_travel_variation.toFixed(6),
    SLICE_ROTATION_VARIATION: p.slice_rotation_variation.toFixed(6),
    SLICE_COUNT: String(p.slice_count),
    SLICE_ANGLE: p.slice_angle.toFixed(6),
    SLICE_DISTANCE: p.slice_distance.toFixed(6),
    SLICE_STAGGER: p.slice_stagger.toFixed(6),
    SLICE_ROTATION: p.slice_rotation.toFixed(6),
    SLICE_DIRECTION: String(catalog.slice_directions.indexOf(p.slice_direction)),
    RELEASE: String(catalog.releases.indexOf(p.release)),
    WAVE_SPAN: p.wave_span.toFixed(6),
    ORIGIN_X: p.origin_x.toFixed(6),
    ORIGIN_Y: p.origin_y.toFixed(6),
    RESIZE_MODE: String(catalog.resize_modes.indexOf(p.resize_mode)),
    RESIZE: p.resize_strength.toFixed(6),
    TILE: p.tile_size.toFixed(6),
    SCATTER: p.scatter.toFixed(6),
    PARTICLES: p.particles.toFixed(6),
    GRAVITY: String(catalog.gravities.indexOf(p.gravity)),
    STRENGTH: p.gravity_strength.toFixed(6),
    ROTATION: String(catalog.rotations.indexOf(p.rotation)),
    SPIN: p.spin.toFixed(6),
    SWIRL: p.swirl.toFixed(6),
    DISPERSION: p.dispersion.toFixed(6),
    STAGGER: p.stagger.toFixed(6),
    ENTRY: opening ? "open_color" : "close_color",
    PROGRESS: opening ? "1.0 - niri_clamped_progress" : "niri_clamped_progress",
  };
  return (
    resizing
      ? catalog.templates.resize
      : p.family !== "fragments"
        ? catalog.templates[p.family]
        : p.size_variation || p.direction_variation || p.wave_strength
          ? catalog.templates.varied
          : classic
            ? catalog.templates.classic
            : catalog.templates.gravity
  ).replace(/@([A-Z_]+)@/g, (_, key) => tokens[key]);
}
function normalizePreset(doc) {
  if (
    !doc ||
    Array.isArray(doc) ||
    ![1, 2, 3].includes(doc.schema) ||
    !doc.effect ||
    typeof doc.effect !== "object" ||
    Array.isArray(doc.effect)
  )
    throw new Error("Expected schema: 1, 2 or 3, name and an effect object.");
  if (doc.schema === 1 && (doc.effect.family ?? "fragments") !== "fragments")
    throw new Error("Non-fragment families require preset schema: 2.");
  if (
    doc.schema < 3 &&
    (doc.effect.family === "elastic" ||
      catalog.variation_fields.some((key) => Object.hasOwn(doc.effect, key)) ||
      doc.effect.slice_direction === "random")
  )
    throw new Error("Wave and variation parameters require preset schema: 3.");
  if (typeof doc.name !== "string" || !/^[A-Za-z0-9][A-Za-z0-9 _-]{0,47}$/.test(doc.name))
    throw new Error("Name must be 1–48 letters, numbers, spaces, hyphens or underscores.");
  for (const key of Object.keys(doc.effect))
    if (!Object.hasOwn(catalog.defaults, key))
      throw new Error("Unsupported effect parameter: " + key);
  const effect = { ...catalog.defaults, ...doc.effect };
  for (const [key, [low, high]] of Object.entries(catalog.limits)) {
    const value = effect[key];
    if (typeof value !== "number" || !Number.isFinite(value) || value < low || value > high)
      throw new Error(key + " must be a finite number from " + low + " to " + high + ".");
    if (
      (key.endsWith("_ms") || ["particles", "slice_count"].includes(key)) &&
      !Number.isInteger(value)
    )
      throw new Error(key + " must be a whole number.");
  }
  if (effect.particles !== 0 && effect.particles < 16)
    throw new Error("Particle count must be zero or at least 16.");
  if (typeof effect.resize !== "boolean") throw new Error("Resize must be true or false.");
  for (const [key, choices] of Object.entries({
    family: Object.keys(catalog.families),
    slice_direction: catalog.slice_directions,
    slice_order: catalog.slice_orders,
    elastic_axis: catalog.elastic_axes,
    gravity: catalog.gravities,
    rotation: catalog.rotations,
    release: catalog.releases,
    resize_mode: catalog.resize_modes,
  }))
    if (!choices.includes(effect[key])) throw new Error("Unknown " + key + ".");
  if (effect.resize && !catalog.families[effect.family].resize)
    throw new Error("This effect family does not support resize.");
  return { schema: doc.schema, name: doc.name, effect };
}
byId("import").onclick = () => byId("import-file").click();
function effectDocument() {
  const effect = { ...parameters },
    extended =
      effect.family === "elastic" ||
      catalog.variation_fields.some((key) => effect[key] !== catalog.defaults[key]) ||
      effect.slice_direction === "random",
    schema = extended ? 3 : effect.family === "fragments" ? 1 : 2;
  if (schema < 3) for (const key of catalog.variation_fields) delete effect[key];
  if (schema === 1) for (const key of catalog.family_fields) delete effect[key];
  return { schema, name: byId("name").value.trim(), effect };
}
function download(name, text, type) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
byId("export").onclick = () =>
  download(
    "nirifx-preset.json",
    JSON.stringify(effectDocument(), null, 2) + "\n",
    "application/json",
  );
byId("kdl").onclick = () => {
  let result = "// Generated by NiriFX Studio\nanimations {\n";
  for (const opening of [true, false])
    result += `    window-${opening ? "open" : "close"} {\n        duration-ms ${opening ? parameters.open_ms : parameters.close_ms}\n        curve "linear"\n        custom-shader r"\n${shaderFor(parameters, opening)}\n        "\n    }\n`;
  if (parameters.resize)
    result += `    window-resize {\n        duration-ms ${parameters.resize_ms}\n        curve "linear"\n        custom-shader r"\n${shaderFor(parameters, false, true)}\n        "\n    }\n`;
  download("nirifx.kdl", result + "}\n", "text/plain");
};
byId("save").disabled = !catalog.connection;
if (catalog.connection)
  setInterval(
    () => fetch("/ping?token=" + encodeURIComponent(catalog.connection.token)).catch(() => {}),
    45000,
  );
if (!catalog.connection)
  byId("status").textContent =
    "Offline preview: export a preset, or run “python3 -m niri_fx studio” to save directly to iRiS.";
byId("save").onclick = async () => {
  byId("save").disabled = true;
  byId("error").textContent = "";
  try {
    const response = await fetch("/save", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Fragments-Token": catalog.connection.token,
      },
      body: JSON.stringify(effectDocument()),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    byId("status").textContent =
      `Saved ${data.name}. Select it in iRiS Settings → Windows → Movement → Style.`;
  } catch (error) {
    byId("error").textContent = error.message;
  } finally {
    byId("save").disabled = false;
  }
};
try {
  const canvas = byId("stage"),
    gl = canvas.getContext("webgl", {
      alpha: true,
      premultipliedAlpha: true,
      preserveDrawingBuffer: true,
    });
  if (!gl)
    throw new Error(
      "WebGL is unavailable. Enable browser hardware acceleration to preview effects.",
    );
  const vertex =
    "attribute vec2 position; varying vec2 uv; void main(){uv=(position+1.0)*0.5; gl_Position=vec4(position,0.0,1.0);}";
  function compile(type, source) {
    const s = gl.createShader(type);
    gl.shaderSource(s, source);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      const error = gl.getShaderInfoLog(s);
      gl.deleteShader(s);
      throw new Error(error);
    }
    return s;
  }
  const vertices = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, vertices);
  gl.bufferData(
    gl.ARRAY_BUFFER,
    new Float32Array([-1, -1, 1, -1, -1, 1, -1, 1, 1, -1, 1, 1]),
    gl.STATIC_DRAW,
  );
  const sample = document.createElement("canvas");
  sample.width = 600;
  sample.height = 380;
  const ctx = sample.getContext("2d");
  ctx.fillStyle = "#202c3b";
  ctx.fillRect(0, 0, 600, 380);
  ctx.fillStyle = "#2d3d50";
  ctx.fillRect(0, 0, 600, 44);
  ["#f09494", "#ead089", "#98d4b1"].forEach((color, i) => {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(22 + i * 23, 22, 5, 0, Math.PI * 2);
    ctx.fill();
  });
  ctx.fillStyle = "#d7e6f5";
  ctx.font = "14px sans-serif";
  ctx.fillText("Fragments / workspace", 210, 27);
  ctx.fillStyle = "#a5e8dd";
  ctx.font = "bold 30px sans-serif";
  ctx.fillText("Everything in its place.", 32, 104);
  ctx.fillStyle = "#9eb0c7";
  ctx.font = "16px sans-serif";
  ctx.fillText("A window, taken apart. A window, put together.", 32, 138);
  for (let i = 0; i < 3; i++) {
    ctx.fillStyle = ["#345b70", "#4c4f75", "#416755"][i];
    ctx.fillRect(32 + i * 182, 175, 170, 112);
    ctx.fillStyle = "#d8e8f5";
    ctx.font = "20px sans-serif";
    ctx.fillText(["Create", "Arrange", "Explore"][i], 48 + i * 182, 212);
  }
  ctx.fillStyle = "#627991";
  for (let i = 0; i < 3; i++) ctx.fillRect(32, 315 + i * 14, 400 - i * 60, 5);
  const motionPreview = new MotionPreview(byId("motion-stage"), sample);
  const nextSample = document.createElement("canvas");
  nextSample.width = 800;
  nextSample.height = 440;
  const nextCtx = nextSample.getContext("2d");
  nextCtx.drawImage(sample, 0, 0, 800, 440);
  nextCtx.fillStyle = "#264d50";
  nextCtx.fillRect(25, 340, 750, 75);
  nextCtx.fillStyle = "#a5e8dd";
  nextCtx.font = "22px sans-serif";
  nextCtx.fillText("More room for what comes next.", 44, 386);
  function uploadTexture(image, unit) {
    gl.activeTexture(gl.TEXTURE0 + unit);
    const texture = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  }
  uploadTexture(sample, 0);
  uploadTexture(nextSample, 1);
  function rebuild() {
    const resizing = mode === "resize",
      source = shaderFor(parameters, false, resizing);
    if (source === lastSource) return;
    const uniforms = resizing
      ? "uniform sampler2D niri_tex_prev;uniform sampler2D niri_tex_next;uniform mat3 niri_geo_to_tex_prev;uniform mat3 niri_geo_to_tex_next;uniform mat3 niri_curr_geo_to_next_geo;"
      : "uniform sampler2D niri_tex;uniform mat3 niri_geo_to_tex;uniform float niri_random_seed;";
    const geometry = resizing
      ? "mix(vec2(600.0,380.0),vec2(800.0,440.0),niri_clamped_progress)"
      : "vec2(600.0,380.0)";
    const fragment = `precision highp float;varying vec2 uv;uniform float niri_clamped_progress;${uniforms}${source}\nvoid main(){vec2 pixel=vec2(uv.x,1.0-uv.y)*vec2(1000.0,760.0);vec2 size=${geometry};vec2 origin=${resizing ? "(vec2(1000.0,760.0)-size)*0.5" : "vec2(200.0,180.0)"};gl_FragColor=${resizing ? "resize_color" : "close_color"}(vec3((pixel-origin)/size,1.0),vec3(size,1.0));}`;
    const vs = compile(gl.VERTEX_SHADER, vertex),
      fs = compile(gl.FRAGMENT_SHADER, fragment),
      next = gl.createProgram();
    gl.attachShader(next, vs);
    gl.attachShader(next, fs);
    gl.linkProgram(next);
    gl.deleteShader(vs);
    gl.deleteShader(fs);
    if (!gl.getProgramParameter(next, gl.LINK_STATUS)) {
      const error = gl.getProgramInfoLog(next);
      gl.deleteProgram(next);
      throw new Error(error);
    }
    if (program) gl.deleteProgram(program);
    program = next;
    lastSource = source;
    gl.useProgram(program);
    const attribute = gl.getAttribLocation(program, "position");
    gl.enableVertexAttribArray(attribute);
    gl.vertexAttribPointer(attribute, 2, gl.FLOAT, false, 0, 0);
    for (const name of ["niri_tex", "niri_tex_prev"])
      gl.uniform1i(gl.getUniformLocation(program, name), 0);
    gl.uniform1i(gl.getUniformLocation(program, "niri_tex_next"), 1);
    for (const name of ["niri_geo_to_tex", "niri_geo_to_tex_prev", "niri_geo_to_tex_next"])
      gl.uniformMatrix3fv(
        gl.getUniformLocation(program, name),
        false,
        new Float32Array([1, 0, 0, 0, 1, 0, 0, 0, 1]),
      );
  }
  function draw(value) {
    progress = value;
    if (["move", "swap"].includes(mode)) motionPreview.draw(value, mode, parameters, seed);
    else {
      gl.uniformMatrix3fv(
        gl.getUniformLocation(program, "niri_curr_geo_to_next_geo"),
        false,
        new Float32Array([
          (600 + 200 * value) / 800,
          0,
          0,
          0,
          (380 + 60 * value) / 440,
          0,
          0,
          0,
          1,
        ]),
      );
      gl.uniform1f(gl.getUniformLocation(program, "niri_clamped_progress"), value);
      gl.uniform1f(gl.getUniformLocation(program, "niri_random_seed"), seed);
      gl.drawArrays(gl.TRIANGLES, 0, 6);
    }
    byId("progress").value = Math.round(value * 1000);
    byId("amount").textContent = Math.round(value * 100) + "%";
  }
  function refresh() {
    try {
      rebuild();
      draw(progress);
      byId("error").textContent = "";
      const tile = parameters.particles
        ? Math.max(4, Math.sqrt((600 * 380) / parameters.particles))
        : parameters.tile_size;
      const count = Math.ceil(600 / tile) * Math.ceil(380 / tile);
      byId("caption").textContent =
        mode === "resize"
          ? `Resize · ${parameters.resize_ms} ms · ${parameters.resize ? "Included when you save" : "Preview only — resize is disabled for this style"}`
          : `${parameters.family === "slices" ? parameters.slice_count + " slices" : parameters.family === "elastic" ? "Elastic window" : count + " pieces in this window"} · ${parameters.open_ms} ms opening · ${parameters.close_ms} ms closing`;
      document.documentElement.dataset.shaderStatus = "ready";
    } catch (error) {
      byId("error").textContent = error.message;
      document.documentElement.dataset.shaderStatus = "error";
    }
  }
  function update() {
    cancelAnimationFrame(frame);
    parameters.resize = byId("resize").checked;
    for (const key of numeric) parameters[key] = Number(byId(key).value);
    for (const key of [
      "gravity",
      "rotation",
      "release",
      "resize_mode",
      "slice_direction",
      "slice_order",
      "elastic_axis",
    ])
      parameters[key] = byId(key).value;
    if (byId("density").value === "tile") parameters.particles = 0;
    labels();
    refresh();
  }
  for (const id of [
    ...numeric,
    "gravity",
    "rotation",
    "release",
    "resize_mode",
    "slice_direction",
    "slice_order",
    "elastic_axis",
    "density",
    "resize",
  ])
    byId(id).addEventListener("input", update);
  byId("family").onchange = () => {
    byId("preset").value = Object.keys(catalog.presets).find(
      (name) => catalog.presets[name].family === byId("family").value,
    );
    byId("preset").dispatchEvent(new Event("change"));
  };
  byId("preset").onchange = () => {
    if (!byId("preset").value) return;
    cancelAnimationFrame(frame);
    parameters = { ...catalog.presets[byId("preset").value] };
    byId("name").value = "My " + title(byId("preset").value);
    populate();
    refresh();
  };
  function animate(opening) {
    cancelAnimationFrame(frame);
    const start = performance.now(),
      duration =
        mode === "effect"
          ? opening
            ? parameters.open_ms
            : parameters.close_ms
          : mode === "resize"
            ? parameters.resize_ms
            : Math.max(900, parameters.open_ms + parameters.close_ms);
    function tick(now) {
      const p = Math.min(1, (now - start) / duration);
      draw(opening ? 1 - p : p);
      if (p < 1) frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
  }
  byId("open").onclick = () => animate(true);
  byId("close").onclick = () => animate(false);
  byId("seed").onclick = () => {
    seed = Math.random();
    draw(progress);
  };
  byId("progress").oninput = () => {
    cancelAnimationFrame(frame);
    draw(Number(byId("progress").value) / 1000);
  };
  for (const button of document.querySelectorAll("[data-mode]"))
    button.onclick = () => {
      if (button.disabled) return;
      cancelAnimationFrame(frame);
      mode = button.dataset.mode;
      for (const tab of document.querySelectorAll("[data-mode]"))
        tab.setAttribute("aria-pressed", String(tab === button));
      const concept = ["move", "swap"].includes(mode);
      byId("stage").hidden = concept;
      byId("motion-stage").hidden = !concept;
      byId("concept-note").hidden = !concept;
      byId("open").textContent = mode === "effect" ? "Reconstruct" : "Reverse";
      byId("close").textContent = mode === "effect" ? "Deconstruct" : "Play";
      byId("timeline-label").textContent = mode === "effect" ? "Breakup" : "Journey";
      byId("save").textContent = concept ? "Save supported effects" : "Save to iRiS";
      labels();
      refresh();
    };
  let importEpoch = 0;
  byId("import-file").onchange = async () => {
    const epoch = ++importEpoch,
      file = byId("import-file").files[0];
    if (!file) return;
    try {
      if (file.size > 16384) throw new Error("Preset must be at most 16 KiB.");
      const imported = normalizePreset(JSON.parse(await file.text()));
      if (epoch !== importEpoch) return;
      const previous = { parameters, name: byId("name").value, preset: byId("preset").value };
      cancelAnimationFrame(frame);
      parameters = imported.effect;
      byId("name").value = imported.name;
      byId("preset").value = "";
      populate();
      refresh();
      if (document.documentElement.dataset.shaderStatus !== "ready") {
        const message = byId("error").textContent;
        parameters = previous.parameters;
        byId("name").value = previous.name;
        byId("preset").value = previous.preset;
        populate();
        refresh();
        throw new Error(message);
      }
      byId("status").textContent =
        "Imported " +
        imported.name +
        ". Resize is " +
        (parameters.resize ? "enabled in this document" : "off") +
        ". Preview or edit, then save/export when ready.";
    } catch (error) {
      if (epoch === importEpoch) byId("error").textContent = "Import failed: " + error.message;
    } finally {
      if (epoch === importEpoch) byId("import-file").value = "";
    }
  };
  populate();
  refresh();
} catch (error) {
  byId("error").textContent = error.message;
  document.documentElement.dataset.shaderStatus = "error";
}
