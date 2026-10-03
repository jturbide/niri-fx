const catalog = JSON.parse(document.getElementById("effect-catalog").textContent);
const byId = (id) => document.getElementById(id);
const specs = catalog.specifications;
const numeric = Object.keys(specs).filter((key) => specs[key].type === "number");
const choices = Object.keys(specs).filter(
  (key) => specs[key].type === "choice" && key !== "family",
);
const units = Object.fromEntries(Object.entries(specs).map(([key, spec]) => [key, spec.unit]));
function glslNumber(value) {
  const scaled = Math.floor(Math.abs(value) * 1000000 + 0.5);
  return (
    (value < 0 && scaled ? "-" : "") +
    Math.floor(scaled / 1000000) +
    "." +
    String(scaled % 1000000).padStart(6, "0")
  );
}
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
let actions = catalog.profile ? structuredClone(catalog.profile.actions) : null;
let editingAction = "open",
  pinned = null,
  comparing = false;
let editHistory = [],
  historyIndex = -1;
let favorites = [];
try {
  favorites = JSON.parse(localStorage.getItem("nirifx-favorites") || "[]").filter((name) =>
    Object.hasOwn(catalog.presets, name),
  );
} catch {
  /* Storage may be unavailable in an offline file. */
}
if (catalog.preferences) favorites = catalog.preferences.favorites;
function commitAction() {
  if (actions)
    actions[editingAction] =
      editingAction === "resize" && !byId("action-enabled").checked
        ? null
        : { ...parameters, resize: false };
}
function chooseAction(action) {
  commitAction();
  editingAction = action;
  parameters = { ...(actions[action] || catalog.presets.balanced), resize: false };
  byId("action-enabled").checked = !!actions[action];
  byId("action").value = action;
}
function loadDocument(doc, action = "open") {
  editingAction = action;
  actions = doc.actions ? structuredClone(doc.actions) : null;
  if (!actions) editingAction = "open";
  parameters = { ...(actions ? actions[editingAction] || catalog.presets.balanced : doc.effect) };
  byId("independent").checked = !!actions;
  byId("action").value = editingAction;
  byId("action-enabled").checked = !!actions?.resize;
  byId("name").value = doc.name;
}
function recordHistory() {
  const snapshot = JSON.stringify({
    document: effectDocument(),
    preset: byId("preset").value,
    action: editingAction,
  });
  if (editHistory[historyIndex] === snapshot) return;
  editHistory = editHistory.slice(0, historyIndex + 1);
  editHistory.push(snapshot);
  if (editHistory.length > 100) editHistory.shift();
  historyIndex = editHistory.length - 1;
  historyButtons();
}
function historyButtons() {
  byId("undo").disabled = historyIndex < 1;
  byId("redo").disabled = historyIndex >= editHistory.length - 1;
}
function filterPresets() {
  const query = byId("search").value.toLowerCase().trim();
  for (const option of byId("preset").options) {
    if (!option.value) continue;
    option.hidden =
      catalog.presets[option.value].family !== parameters.family ||
      !option.textContent.toLowerCase().includes(query) ||
      (byId("favorites-only").checked && !favorites.includes(option.value));
  }
  const favorite = favorites.includes(byId("preset").value);
  byId("favorite").disabled = !byId("preset").value;
  byId("favorite").textContent = favorite ? "Remove favorite" : "Favorite this style";
  byId("favorite").setAttribute("aria-pressed", String(favorite));
}
byId("search").oninput = byId("favorites-only").onchange = filterPresets;
byId("favorite").onclick = () => {
  const name = byId("preset").value;
  if (!name) return;
  favorites = favorites.includes(name)
    ? favorites.filter((value) => value !== name)
    : [...favorites, name];
  try {
    localStorage.setItem("nirifx-favorites", JSON.stringify(favorites));
  } catch {
    /* Session favorites still work. */
  }
  if (catalog.connection)
    fetch("/preferences", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-NiriFX-Token": catalog.connection.token },
      body: JSON.stringify({ favorites }),
    })
      .then((response) => {
        if (!response.ok) throw new Error("Could not save favorites");
      })
      .catch((error) => {
        byId("status").textContent = error.message;
      });
  filterPresets();
};
function populate() {
  for (const key of numeric) {
    byId(key).step = specs[key].integer ? "1" : "any";
    byId(key).value = key === "particles" ? parameters.particles || 240 : parameters[key];
  }
  for (const key of choices) byId(key).value = parameters[key];
  byId("resize").checked = parameters.resize;
  byId("density").value = parameters.particles ? "count" : "tile";
  byId("family").value = parameters.family;
  byId("independent").checked = !!actions;
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
  byId("dissolve-controls").hidden = parameters.family !== "dissolve";
  byId("iris-controls").hidden = parameters.family !== "iris";
  for (const wrapper of document.querySelectorAll("[data-parameter]")) {
    const families = specs[wrapper.dataset.parameter].families;
    if (wrapper.id !== "count-control" && wrapper.id !== "tile-control")
      wrapper.hidden = families.length > 0 && !families.includes(parameters.family);
  }
  byId("resize-controls").hidden = !capabilities.resize;
  byId("family-note").textContent = fragment
    ? "Open, close and optional resize. Move/swap previews are experimental concepts."
    : ["dissolve", "iris"].includes(parameters.family)
      ? "Open and close reveal effects. Resize and native movement are unavailable."
      : parameters.family === "elastic"
        ? "Whole-window wobble. Open/close on stock Niri; native movement requires the patched compositor."
        : "Open and close. Slice resize and movement are not supported in this release.";
  filterPresets();
  byId("action-controls").hidden = !actions;
  byId("action-enable-label").hidden = editingAction !== "resize";
  if (actions) {
    byId("resize").closest(".parameter").hidden = true;
    byId("open_ms").closest(".parameter").hidden = editingAction !== "open";
    byId("close_ms").closest(".parameter").hidden = editingAction !== "close";
    byId("resize-controls").hidden = editingAction !== "resize";
  }
  for (const tab of document.querySelectorAll("[data-mode]"))
    tab.disabled =
      tab.dataset.mode === "resize"
        ? !capabilities.resize
        : ["move", "swap"].includes(tab.dataset.mode)
          ? !capabilities.concept
          : false;
  byId("variation-controls").hidden =
    mode === "resize" || !["fragments", "slices"].includes(parameters.family);
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
    "fragment_shrink",
    "fragment_roundness",
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
  byId("seed").disabled = mode === "resize" || ["elastic", "iris"].includes(parameters.family);
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
    p.origin_y === 0.5 &&
    !p.fragment_shrink &&
    !p.fragment_roundness;
  const tokens = Object.fromEntries(
    Object.entries(specs)
      .filter(([, spec]) => spec.token)
      .map(([key, spec]) => [
        spec.token,
        spec.type === "choice"
          ? String(spec.choices.indexOf(p[key]))
          : key === "slice_count"
            ? String(p[key])
            : glslNumber(p[key]),
      ]),
  );
  Object.assign(tokens, {
    ELASTIC_ORIGIN_X: glslNumber(catalog.elastic_anchors[p.elastic_anchor][0]),
    ELASTIC_ORIGIN_Y: glslNumber(catalog.elastic_anchors[p.elastic_anchor][1]),
    ENTRY: opening ? "open_color" : "close_color",
    PROGRESS: opening ? "1.0 - niri_clamped_progress" : "niri_clamped_progress",
  });
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
  if (doc?.kind === "profile") {
    if (
      doc.schema !== 1 ||
      Object.keys(doc).sort().join() !== "actions,kind,name,schema" ||
      !doc.actions ||
      Object.keys(doc.actions).sort().join() !== "close,movement,open,resize"
    )
      throw new Error("Expected profile schema 1 with open, close, resize and movement actions.");
    const normalized = {};
    for (const action of ["open", "close", "resize", "movement"]) {
      const value = doc.actions[action];
      if (value === null && ["resize", "movement"].includes(action)) {
        normalized[action] = null;
        continue;
      }
      const effect = normalizePreset({
        schema: catalog.schema,
        name: doc.name,
        effect: value,
      }).effect;
      if (effect.resize) throw new Error("Profile actions use a separate resize slot.");
      if (["resize", "movement"].includes(action) && !catalog.families[effect.family][action])
        throw new Error("This family does not support " + action);
      normalized[action] = effect;
    }
    return { kind: "profile", schema: 1, name: doc.name, actions: normalized };
  }
  if (
    !doc ||
    Array.isArray(doc) ||
    doc.schema !== catalog.schema ||
    !doc.effect ||
    typeof doc.effect !== "object" ||
    Array.isArray(doc.effect)
  )
    throw new Error(`Expected schema: ${catalog.schema}, name and an effect object.`);
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
    if (specs[key].integer && !Number.isInteger(value))
      throw new Error(key + " must be a whole number.");
  }
  if (effect.particles !== 0 && effect.particles < 16)
    throw new Error("Particle count must be zero or at least 16.");
  if (typeof effect.resize !== "boolean") throw new Error("Resize must be true or false.");
  for (const [key, spec] of Object.entries(specs))
    if (spec.choices && !spec.choices.includes(effect[key]))
      throw new Error("Unknown " + key + ".");
  if (effect.resize && !catalog.families[effect.family].resize)
    throw new Error("This effect family does not support resize.");
  return { schema: doc.schema, name: doc.name, effect };
}
byId("import").onclick = () => byId("import-file").click();
function effectDocument() {
  if (actions) {
    commitAction();
    return {
      kind: "profile",
      schema: 1,
      name: byId("name").value.trim(),
      actions: structuredClone(actions),
    };
  }
  return { schema: catalog.schema, name: byId("name").value.trim(), effect: { ...parameters } };
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
function kdlDocument() {
  commitAction();
  let result = "// Generated by NiriFX Studio\nanimations {\n";
  const selected = actions || {
    open: parameters,
    close: parameters,
    resize: parameters.resize ? parameters : null,
  };
  for (const action of ["open", "close", "resize"]) {
    const effect = selected[action];
    if (!effect) continue;
    result += `    window-${action} {\n        duration-ms ${effect[action + "_ms"]}\n        curve "linear"\n        custom-shader r"\n${shaderFor(effect, action === "open", action === "resize")}\n        "\n    }\n`;
  }
  return result + "}\n";
}
byId("kdl").onclick = () => download("nirifx.kdl", kdlDocument(), "text/plain");
function saveTarget() {
  const target = byId("save-target").value;
  byId("save").disabled = target === "inir" && !catalog.connection;
  byId("save").textContent = target === "inir" ? "Save to iRiS" : "Download preset file";
}
byId("save-target").onchange = saveTarget;
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
  const target = byId("save-target").value;
  if (target !== "inir") {
    try {
      const doc = normalizePreset(effectDocument());
      download(
        "nirifx-" + doc.name.toLowerCase().replace(/[ _-]+/g, "-") + ".kdl",
        kdlDocument(),
        "text/plain",
      );
      byId("status").textContent =
        target === "noctalia"
          ? "Place the downloaded file in the Noctalia Niri Animations preset folder, then select it in the picker."
          : "Downloaded a Niri animation include. Include it from your config to activate.";
    } catch (error) {
      byId("error").textContent = error.message;
    }
    return;
  }
  byId("save").disabled = true;
  byId("error").textContent = "";
  try {
    const response = await fetch("/save", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-NiriFX-Token": catalog.connection.token,
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
      source = shaderFor(comparing ? pinned.parameters : parameters, false, resizing);
    if (source === lastSource) return;
    const uniforms = resizing
      ? "uniform sampler2D niri_tex_prev;uniform sampler2D niri_tex_next;uniform mat3 niri_geo_to_tex_prev;uniform mat3 niri_geo_to_tex_next;uniform mat3 niri_curr_geo_to_next_geo;"
      : "uniform sampler2D niri_tex;uniform mat3 niri_geo_to_tex;uniform float niri_random_seed;";
    const geometry = resizing
      ? "mix(vec2(600.0,380.0),vec2(800.0,440.0),niri_clamped_progress)"
      : "fx_window";
    const fragment = `precision highp float;varying vec2 uv;uniform float niri_clamped_progress;uniform vec2 fx_surface;uniform vec2 fx_window;${uniforms}${source}\nvoid main(){vec2 pixel=vec2(uv.x,1.0-uv.y)*fx_surface;vec2 size=${geometry};vec2 origin=${resizing ? "(vec2(1000.0,760.0)-size)*0.5" : "(fx_surface-size)*vec2(0.5,0.473684210526)"};gl_FragColor=${resizing ? "resize_color" : "close_color"}(vec3((pixel-origin)/size,1.0),vec3(size,1.0));}`;
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
  let benchmarkWindow = null;
  function draw(value) {
    progress = value;
    if (["move", "swap"].includes(mode)) motionPreview.draw(value, mode, parameters, seed);
    else {
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(gl.getUniformLocation(program, "fx_surface"), canvas.width, canvas.height);
      gl.uniform2f(gl.getUniformLocation(program, "fx_window"), ...(benchmarkWindow || [600, 380]));
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
      gl.uniform1f(
        gl.getUniformLocation(program, "niri_random_seed"),
        comparing ? pinned.seed : seed,
      );
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
      const caption =
        mode === "resize"
          ? `Resize · ${parameters.resize_ms} ms · ${parameters.resize ? "Included when you save" : "Preview only — resize is disabled for this style"}`
          : `${parameters.family === "slices" ? parameters.slice_count + " slices" : parameters.family !== "fragments" ? catalog.families[parameters.family].label + " window" : count + " pieces in this window"} · ${parameters.open_ms} ms opening · ${parameters.close_ms} ms closing`;
      byId("caption").textContent = (comparing ? "Pinned A · " : pinned ? "B · " : "") + caption;
      document.documentElement.dataset.shaderStatus = "ready";
    } catch (error) {
      byId("error").textContent = error.message;
      document.documentElement.dataset.shaderStatus = "error";
    }
  }
  // Shader-only GPU microbenchmark. No screen capture or compositor timing claims.
  window.niriFxBenchmark = async ({ width = 1920, height = 1080, samples = 60 } = {}) => {
    if (
      ![width, height, samples].every(Number.isInteger) ||
      width < 320 ||
      height < 240 ||
      width > 7680 ||
      height > 4320 ||
      samples < 10 ||
      samples > 1000
    )
      throw new Error("Invalid benchmark dimensions or sample count");
    const debug = gl.getExtension("WEBGL_debug_renderer_info");
    const renderer = debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : "unavailable";
    const vendor = debug ? gl.getParameter(debug.UNMASKED_VENDOR_WEBGL) : "unavailable";
    const timer = gl.getExtension("EXT_disjoint_timer_query");
    const report = {
      kind: "webgl-shader-gpu",
      renderer,
      vendor,
      width,
      height,
      samples,
      preset: byId("preset").value,
      effect: { ...parameters },
      seed,
      userAgent: navigator.userAgent,
    };
    if (/swiftshader|llvmpipe|software|unavailable/i.test(renderer) || !timer)
      return {
        ...report,
        status: "unsupported",
        reason: !timer ? "GPU timer queries unavailable" : "Hardware renderer not verified",
      };
    if (mode !== "effect" || comparing)
      throw new Error("Use the current open/close preview, with A/B comparison off");
    cancelAnimationFrame(frame);
    const original = { width: canvas.width, height: canvas.height, progress };
    const measurements = [];
    try {
      canvas.width = width;
      canvas.height = height;
      benchmarkWindow = [Math.round(width * 0.6), Math.round(height * 0.5)];
      for (let index = -12; index < samples; index++) {
        const query = timer.createQueryEXT();
        try {
          gl.getParameter(timer.GPU_DISJOINT_EXT);
          timer.beginQueryEXT(timer.TIME_ELAPSED_EXT, query);
          draw(0.1 + (((index + 12) % 31) / 31) * 0.8);
          timer.endQueryEXT(timer.TIME_ELAPSED_EXT);
          gl.flush();
          const deadline = performance.now() + 10000;
          while (!timer.getQueryObjectEXT(query, timer.QUERY_RESULT_AVAILABLE_EXT)) {
            if (gl.isContextLost() || performance.now() > deadline)
              throw new Error("GPU query timed out or context lost");
            await new Promise((resolve) => setTimeout(resolve, 5));
          }
          if (gl.getParameter(timer.GPU_DISJOINT_EXT))
            throw new Error("GPU timer became disjoint; discard this run");
          const ms = timer.getQueryObjectEXT(query, timer.QUERY_RESULT_EXT) / 1000000;
          if (!Number.isFinite(ms) || ms <= 0 || gl.getError() !== gl.NO_ERROR)
            throw new Error("Invalid GPU measurement");
          if (index >= 0) measurements.push(ms);
        } finally {
          timer.deleteQueryEXT(query);
        }
      }
      const sorted = [...measurements].sort((a, b) => a - b);
      const percentile = (p) => sorted[Math.ceil(p * sorted.length) - 1];
      return {
        ...report,
        status: "measured",
        window: benchmarkWindow,
        warmup: 12,
        milliseconds: measurements,
        p50: percentile(0.5),
        p95: percentile(0.95),
        p99: percentile(0.99),
        budgetExceeded: Object.fromEntries(
          [60, 120, 144].map((hz) => [hz, measurements.filter((ms) => ms > 1000 / hz).length]),
        ),
      };
    } finally {
      canvas.width = original.width;
      canvas.height = original.height;
      benchmarkWindow = null;
      draw(original.progress);
    }
  };
  function update() {
    cancelAnimationFrame(frame);
    parameters.resize = byId("resize").checked;
    for (const key of numeric) parameters[key] = Number(byId(key).value);
    for (const key of choices) parameters[key] = byId(key).value;
    if (byId("density").value === "tile") parameters.particles = 0;
    if (actions) parameters.resize = false;
    labels();
    refresh();
    recordHistory();
  }
  for (const id of [...numeric, ...choices, "density", "resize"])
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
    if (actions && editingAction === "resize" && !catalog.families[parameters.family].resize) {
      parameters = { ...catalog.presets.balanced };
      byId("status").textContent = "Resize currently supports Fragments only.";
    }
    byId("name").value = "My " + title(byId("preset").value);
    populate();
    refresh();
    recordHistory();
  };
  function animate(opening) {
    cancelAnimationFrame(frame);
    if (actions && mode === "effect") {
      chooseAction(opening ? "open" : "close");
      populate();
      refresh();
    }
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
      if (mode !== "effect") comparing = false;
      byId("compare").disabled = !pinned || mode !== "effect";
      byId("compare").textContent = comparing ? "Show B" : "Show A";
      byId("compare").setAttribute("aria-pressed", String(comparing));
      for (const tab of document.querySelectorAll("[data-mode]"))
        tab.setAttribute("aria-pressed", String(tab === button));
      const concept = ["move", "swap"].includes(mode);
      byId("stage").hidden = concept;
      byId("motion-stage").hidden = !concept;
      byId("concept-note").hidden = !concept;
      byId("open").textContent = mode === "effect" ? "Reconstruct" : "Reverse";
      byId("close").textContent = mode === "effect" ? "Deconstruct" : "Play";
      byId("timeline-label").textContent = mode === "effect" ? "Breakup" : "Journey";
      saveTarget();
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
      const previous = {
        document: effectDocument(),
        preset: byId("preset").value,
        action: editingAction,
      };
      cancelAnimationFrame(frame);
      loadDocument(imported);
      byId("preset").value = "";
      populate();
      refresh();
      if (document.documentElement.dataset.shaderStatus !== "ready") {
        const message = byId("error").textContent;
        loadDocument(previous.document, previous.action);
        byId("preset").value = previous.preset;
        populate();
        refresh();
        throw new Error(message);
      }
      recordHistory();
      byId("status").textContent =
        "Imported " +
        imported.name +
        ". Resize is " +
        ((actions ? actions.resize : parameters.resize) ? "enabled in this document" : "off") +
        ". Preview or edit, then save/export when ready.";
    } catch (error) {
      if (epoch === importEpoch) byId("error").textContent = "Import failed: " + error.message;
    } finally {
      if (epoch === importEpoch) byId("import-file").value = "";
    }
  };
  byId("independent").onchange = () => {
    if (byId("independent").checked) {
      const effect = { ...parameters, resize: false };
      actions = {
        open: { ...effect },
        close: { ...effect },
        resize: parameters.resize ? { ...effect } : null,
        movement: null,
      };
      editingAction = "open";
      byId("action").value = "open";
      byId("action-enabled").checked = !!actions.resize;
      parameters.resize = false;
    } else {
      commitAction();
      parameters = { ...actions.open };
      actions = null;
      editingAction = "open";
    }
    populate();
    refresh();
    recordHistory();
  };
  byId("action").onchange = () => {
    chooseAction(byId("action").value);
    byId("preset").value = "";
    populate();
    document
      .querySelector(editingAction === "resize" ? "[data-mode=resize]" : "[data-mode=effect]")
      .click();
    refresh();
  };
  byId("action-enabled").onchange = () => {
    commitAction();
    refresh();
    recordHistory();
  };
  for (const direction of ["undo", "redo"])
    byId(direction).onclick = () => {
      historyIndex += direction === "undo" ? -1 : 1;
      const snapshot = JSON.parse(editHistory[historyIndex]);
      editingAction = snapshot.action;
      loadDocument(snapshot.document, snapshot.action);
      byId("action").value = editingAction;
      byId("preset").value = snapshot.preset;
      populate();
      refresh();
      historyButtons();
    };
  for (const button of document.querySelectorAll("[data-reset]"))
    button.onclick = () => {
      parameters[button.dataset.reset] = specs[button.dataset.reset].default;
      populate();
      refresh();
      recordHistory();
    };
  byId("name").onchange = recordHistory;
  byId("pin").onclick = () => {
    pinned = { parameters: { ...parameters }, seed };
    comparing = false;
    byId("compare").disabled = mode !== "effect";
    byId("compare").textContent = "Show A";
    byId("compare").setAttribute("aria-pressed", "false");
    byId("status").textContent = "Pinned A. Edit B, then toggle to compare at the same progress.";
    refresh();
  };
  byId("compare").onclick = () => {
    comparing = !comparing;
    byId("compare").textContent = comparing ? "Show B" : "Show A";
    byId("compare").setAttribute("aria-pressed", String(comparing));
    refresh();
  };
  if (catalog.profile) loadDocument(catalog.profile);
  populate();
  refresh();
  recordHistory();
} catch (error) {
  byId("error").textContent = error.message;
  document.documentElement.dataset.shaderStatus = "error";
}
