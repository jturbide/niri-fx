// UI state and event wiring. Portable document validation and shader expansion
// live in effect-core.js; this file alone coordinates history and active actions.
const catalog = JSON.parse(document.getElementById("effect-catalog").textContent);
const byId = (id) => document.getElementById(id);
const specs = catalog.specifications;
const { shaderFor, normalizePreset, renderKdl, encodeShareDocument, decodeShareDocument } =
  createEffectCore(catalog);
const numeric = Object.keys(specs).filter((key) => specs[key].type === "number");
const choices = Object.keys(specs).filter(
  (key) => specs[key].type === "choice" && key !== "family",
);
const units = Object.fromEntries(Object.entries(specs).map(([key, spec]) => [key, spec.unit]));
let parameters = { ...catalog.parameters },
  frame = 0,
  seed = 0.37,
  program = null,
  lastSource = "",
  mode = "effect";
const query = new URLSearchParams(location.search);
const requestedPreset = Object.hasOwn(catalog.presets, query.get("preset"))
  ? query.get("preset")
  : null;
// The catalog already contains CLI/imported edits. Only an explicit preview-link
// choice replaces them; a document name alone cannot select different settings.
if (requestedPreset) parameters = { ...catalog.presets[requestedPreset] };
const initialPreset =
  requestedPreset ||
  (Object.hasOwn(catalog.presets, catalog.name) &&
  Object.keys(catalog.defaults).every(
    (key) => parameters[key] === catalog.presets[catalog.name][key],
  )
    ? catalog.name
    : "");
let progress = Number(query.get("breakup") ?? 0.45);
progress = Number.isFinite(progress) ? Math.min(1, Math.max(0, progress)) : 0.45;
const title = (s) => s.replaceAll("-", " ").replace(/\b\w/g, (c) => c.toUpperCase());
for (const [id, collection] of Object.entries(catalog.collections)) {
  const option = document.createElement("option");
  option.value = id;
  option.textContent = collection.label;
  byId("preset-collection").append(option);
}
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
byId("preset").value = Object.hasOwn(catalog.presets, initialPreset) ? initialPreset : "";
byId("name").value =
  initialPreset && catalog.presets[catalog.name]
    ? "My " + title(byId("preset").value)
    : catalog.name;
for (const [id, doc] of Object.entries(catalog.profiles)) {
  const option = document.createElement("option");
  option.value = id;
  option.textContent = doc.name;
  byId("profile").append(option);
}
let actions = catalog.profile ? structuredClone(catalog.profile.actions) : null;
let desktopMotion = catalog.profile?.motion ? structuredClone(catalog.profile.motion) : null;
let pointerSettings = catalog.profile?.pointer ? structuredClone(catalog.profile.pointer) : null;
// Native response settings are editor history, not portable profile parameters.
// Bundle recipes persist them separately; JSON export remains shell independent.
const sessionSettings =
  catalog.connection?.target === "native"
    ? { fragment_preset: catalog.connection.native.recipe?.fragment_preset || null }
    : null;
const isActionStyle = (value) => value !== null && typeof value === "object";
const actionMode = (value) =>
  isActionStyle(value) ? "style" : value === "off" ? "off" : "preserve";
const rememberedActions = {};
let editingAction = "open",
  pinned = null,
  comparing = false;
let editHistory = [],
  historyIndex = -1;
let workspace = null;
// Playback renders a frozen document through a separate view. Editor settings,
// history and the selected action never become temporary animation state.
let comboPreviewFrame = null;
let pointerPreviewFrame = null;
let cancelComboPreview = () => {};
let cancelPointerPreview = () => {};
let favorites = [];
try {
  favorites = JSON.parse(localStorage.getItem("nirifx-favorites") || "[]").filter(
    (name) =>
      Object.hasOwn(catalog.presets, name) ||
      Object.hasOwn(catalog.profiles, name) ||
      /^custom-[a-z0-9-]+$/.test(name),
  );
} catch {
  /* Storage may be unavailable in an offline file. */
}
if (catalog.preferences) favorites = catalog.preferences.favorites;
function commitAction() {
  if (!actions) return;
  const mode = byId("action-mode").value;
  if (mode === "style") {
    actions[editingAction] = { ...parameters, resize: false };
    rememberedActions[editingAction] = { ...actions[editingAction] };
  } else actions[editingAction] = mode === "off" ? "off" : null;
}
function matchingActionSet() {
  if (!actions) return null;
  // Names and chooser selection can change on import or Undo. Match normalized
  // window settings instead; recommendations never alter a saved document.
  return Object.keys(catalog.action_companions).find((id) =>
    ["open", "close"].every(
      (action) =>
        isActionStyle(actions[action]) &&
        Object.keys(catalog.defaults).every(
          (key) => actions[action][key] === catalog.profiles[id].actions[action][key],
        ),
    ),
  );
}
function actionParameters(action) {
  return (
    (isActionStyle(actions[action]) ? actions[action] : null) ||
    rememberedActions[action] ||
    catalog.action_companions[matchingActionSet()]?.[action] ||
    catalog.presets.balanced
  );
}
function chooseAction(action) {
  commitAction();
  editingAction = action;
  parameters = { ...actionParameters(action), resize: false };
  byId("action-mode").value = actionMode(actions[action]);
  byId("action").value = action;
}
function loadDocument(doc, action = "open") {
  cancelPointerPreview();
  cancelComboPreview();
  editingAction = action;
  const renamed = byId("name").value.trim() !== doc.name;
  if (renamed) for (const key of Object.keys(rememberedActions)) delete rememberedActions[key];
  if (actions && !renamed)
    for (const [slot, value] of Object.entries(actions))
      if (isActionStyle(value)) rememberedActions[slot] = { ...value };
  actions = doc.actions ? structuredClone(doc.actions) : null;
  if (actions)
    for (const [slot, value] of Object.entries(actions))
      if (isActionStyle(value)) rememberedActions[slot] = { ...value };
  desktopMotion = doc.motion ? structuredClone(doc.motion) : null;
  pointerSettings = doc.pointer ? structuredClone(doc.pointer) : null;
  if (!actions) editingAction = "open";
  parameters = { ...(actions ? actionParameters(editingAction) : doc.effect) };
  byId("independent").checked = !!actions;
  byId("action").value = editingAction;
  byId("action-mode").value = actions ? actionMode(actions[editingAction]) : "style";
  byId("name").value = doc.name;
}
function recordHistory() {
  // This chooser starts a document; edits and Undo must never leave a stale
  // pairing selected after the current settings have diverged from it.
  byId("profile").value = "";
  workspace?.sync();
  const snapshot = JSON.stringify({
    document: effectDocument(),
    preset: byId("preset").value,
    action: editingAction,
    ...(sessionSettings ? { session: sessionSettings } : {}),
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
  const collection = catalog.collections[byId("preset-collection").value];
  for (const option of byId("preset").options) {
    if (!option.value) continue;
    option.hidden =
      (collection
        ? !collection.styles.includes(option.value)
        : catalog.presets[option.value].family !== parameters.family) ||
      !option.textContent.toLowerCase().includes(query) ||
      (byId("favorites-only").checked && !favorites.includes(option.value));
  }
  for (const option of byId("profile").options) {
    if (!option.value) continue;
    option.hidden = !!collection && !collection.styles.includes(option.value);
  }
  const favorite = favorites.includes(byId("preset").value);
  byId("favorite").disabled = !byId("preset").value;
  byId("favorite").textContent = favorite ? "Remove favorite" : "Favorite this style";
  byId("favorite").setAttribute("aria-pressed", String(favorite));
}
byId("preset-collection").onchange =
  byId("search").oninput =
  byId("favorites-only").onchange =
    filterPresets;
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
  const motionName = desktopMotion
    ? Object.keys(catalog.motion_packs).find(
        (name) => JSON.stringify(catalog.motion_packs[name]) === JSON.stringify(desktopMotion),
      ) || "custom"
    : "";
  byId("desktop-motion").value = motionName;
  byId("desktop-motion").querySelector('[value="custom"]').hidden = motionName !== "custom";
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
    (["resize", "movement"].includes(mode) && !catalog.families[parameters.family][mode]) ||
    (["move", "swap"].includes(mode) && !supportsConcept())
  )
    document.querySelector("[data-mode=effect]").click();
}
function supportsConcept() {
  return (
    catalog.families[parameters.family].concept &&
    parameters.fragment_shape === "square" &&
    parameters.fragment_orientation === 0
  );
}
function labels() {
  for (const id of [...numeric, ...choices, "density", "resize", "family", "preset"])
    byId(id).disabled = false;
  const fragment = parameters.family === "fragments",
    capabilities = catalog.families[parameters.family];
  byId("fragment-controls").hidden = !fragment;
  byId("fragment-note").hidden = !fragment;
  for (const family of Object.keys(catalog.families)) {
    const group = { fragments: "fragment", slices: "slice" }[family] || family;
    byId(group + "-controls").hidden = parameters.family !== family;
  }
  for (const wrapper of document.querySelectorAll("[data-parameter]")) {
    const families = specs[wrapper.dataset.parameter].families;
    if (wrapper.id !== "count-control" && wrapper.id !== "tile-control")
      wrapper.hidden = families.length > 0 && !families.includes(parameters.family);
  }
  byId("resize-controls").hidden = !capabilities.resize;
  byId("family-note").textContent =
    "Stock Niri open/close" +
    (capabilities.resize ? " and resize." : ".") +
    (capabilities.movement ? " Native movement requires a matching NiriFX session." : "");
  byId("movement-controls").hidden = mode !== "movement" || !capabilities.movement;
  byId("movement-preview-controls").hidden = mode !== "movement";
  filterPresets();
  byId("action-controls").hidden = !actions;
  const selectedMode = actions ? byId("action-mode").value : "style";
  byId("action-mode-note").textContent =
    selectedMode === "preserve"
      ? catalog.connection?.target === "native"
        ? "Preserve uses this session's original saved baseline. Its animation cannot be previewed without that context."
        : "Preserve keeps the underlying desktop or shell configuration. Its animation cannot be previewed without that context."
      : selectedMode === "off"
        ? "Off disables this action animation. The preview shows its endpoint."
        : "Customize the NiriFX style for this action.";
  byId("independent").disabled =
    !!actions &&
    (["open", "close"].some((action) => !isActionStyle(actions[action])) ||
      actions.resize === "off" ||
      actions.movement !== null);
  const companion = ["resize", "movement"].includes(editingAction) && matchingActionSet();
  byId("action-companion-note").hidden = !companion || selectedMode !== "preserve";
  if (companion)
    byId("action-companion-note").textContent =
      `Suggested ${editingAction} settings for ${catalog.profiles[companion].name}. ` +
      "Choose NiriFX Style to include them in your profile.";
  if (actions) {
    byId("resize").closest(".parameter").hidden = true;
    byId("open_ms").closest(".parameter").hidden = editingAction !== "open";
    byId("close_ms").closest(".parameter").hidden = editingAction !== "close";
    byId("resize-controls").hidden = editingAction !== "resize";
  }
  for (const tab of document.querySelectorAll("[data-mode]"))
    tab.disabled = ["resize", "movement"].includes(tab.dataset.mode)
      ? !capabilities[tab.dataset.mode]
      : ["move", "swap"].includes(tab.dataset.mode)
        ? !supportsConcept()
        : false;
  byId("variation-controls").hidden =
    (mode === "resize" && !fragment) || !["fragments", "slices"].includes(parameters.family);
  byId("slice-variation").hidden = fragment;
  byId("wave_frequency").disabled = byId("wave_speed").disabled =
    mode === "resize" || !parameters.wave_strength;
  byId("direction_variation").disabled = mode === "resize";
  byId("slice_stagger").disabled = parameters.slice_order === "together";
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
  byId("fragment_aspect").disabled = ["square", "circle"].includes(parameters.fragment_shape);
  byId("fragment_roundness").disabled = ["circle", "ellipse", "star"].includes(
    parameters.fragment_shape,
  );
  byId("fragment_transition").disabled =
    !["circle", "ellipse", "diamond", "star"].includes(parameters.fragment_shape) &&
    !parameters.fragment_roundness;
  byId("size_variation").disabled = false;
  byId("wave_strength").disabled = mode === "resize";
  byId("fragment_shrink").disabled = false;
  byId("fragment_shape").disabled = false;
  byId("fragment_orientation").disabled = false;
  byId("variation-note").textContent =
    mode === "resize"
      ? "Size variation changes piece sizes during flight. Resize keeps a joined source partition; waves and direction variation do not apply."
      : fragment
        ? parameters.fragment_shape !== "square" || parameters.fragment_orientation !== 0
          ? "Size variation changes piece sizes during flight so the starting layout stays joined. Shapes, elongated pieces and waves can cost more to render."
          : "Uneven cells and waves cost more to render. Resize uses size variation during flight; waves and direction variation affect open/close and NiriFX movement."
        : "Size variation keeps adjacent strip boundaries joined. Frequency controls the wavelength; lower frequencies make wider waves.";
  byId("seed").disabled =
    mode === "resize" ||
    ["elastic", "iris"].includes(parameters.family) ||
    (parameters.family === "distortion" && parameters.distortion_mode !== "glitch");
  byId("edge_hue").disabled = parameters.edge_saturation === 0;
  for (const id of ["pixel_travel", "pixel_wind"])
    byId(id).disabled = parameters.pixel_mode !== "dust";
  byId("pixel_direction").disabled = parameters.pixel_mode === "pixelate";
  const resizeDistortion = mode === "resize" || (actions && editingAction === "resize");
  const torsion = resizeDistortion && parameters.distortion_resize_mode === "torsion";
  byId("distortion_resize_mode").disabled = !resizeDistortion;
  byId("resize_twist").disabled = !torsion;
  byId("distortion_falloff").disabled = !!torsion;
  for (const id of ["distortion_x", "distortion_y"])
    byId(id).disabled = resizeDistortion && parameters.distortion_resize_mode !== "ripple";
  byId("resize-direction-label").hidden = mode !== "resize";
  byId("open").textContent =
    mode === "resize" ? "Shrink" : mode === "effect" ? "Reconstruct" : "Reverse";
  byId("close").textContent =
    mode === "resize" ? "Grow" : mode === "effect" ? "Deconstruct" : "Play";
  const vortex = parameters.distortion_mode === "vortex" && !resizeDistortion;
  for (const id of ["distortion_twist", "distortion_contract"]) byId(id).disabled = !vortex;
  for (const id of ["distortion_strength", "distortion_wavelength", "distortion_cycles"])
    byId(id).disabled = vortex || !!torsion;
  byId("distortion_mode").disabled = !!resizeDistortion;
  for (const id of ["glitch_bands", "glitch_chroma"])
    byId(id).disabled = resizeDistortion || parameters.distortion_mode !== "glitch";
  for (const id of ["dissolve_x", "dissolve_y", "dissolve_turbulence"])
    byId(id).disabled = parameters.dissolve_mode !== "ink";
  byId("distortion_width").disabled =
    resizeDistortion || parameters.distortion_mode !== "shockwave";
  byId("distortion_fade").disabled = resizeDistortion || parameters.distortion_mode === "shockwave";
  byId("distortion_angle").disabled = resizeDistortion || parameters.distortion_mode !== "wave";
  byId("wave_span").disabled = mode === "resize" || parameters.release === "together";
  byId("gravity_strength").disabled = mode === "resize" || byId("gravity").value === "none";
  byId("spin").disabled = byId("rotation").value === "none";
  byId("fragment_secondary").disabled = parameters.fragment_mix === 0;
  byId("fragment_shape_seed").disabled =
    parameters.fragment_mix === 0 || parameters.fragment_mix === 1;
  // A stored fallback is only for switching back to Style, never an active effect.
  for (const id of [...numeric, ...choices, "density", "resize", "family", "preset"])
    if (selectedMode !== "style") byId(id).disabled = true;
  for (const button of document.querySelectorAll("[data-reset]"))
    button.disabled = selectedMode !== "style";
}
byId("import").onclick = () => byId("import-file").click();
function effectDocument() {
  // Pointer settings are profile metadata. Consolidating window styles must
  // keep them even while the editor uses its single-style representation.
  if (actions || pointerSettings) {
    commitAction();
    return {
      kind: "profile",
      schema: catalog.profile_schema,
      name: byId("name").value.trim(),
      actions: actions
        ? structuredClone(actions)
        : {
            open: { ...parameters, resize: false },
            close: { ...parameters, resize: false },
            resize: parameters.resize ? { ...parameters, resize: false } : null,
            movement: null,
          },
      ...(desktopMotion ? { motion: structuredClone(desktopMotion) } : {}),
      ...(pointerSettings ? { pointer: structuredClone(pointerSettings) } : {}),
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
function kdlDocument(options = {}) {
  return renderKdl(effectDocument(), options);
}
byId("kdl").onclick = () => {
  download("nirifx.kdl", kdlDocument(), "text/plain");
  byId("status").textContent =
    "Downloaded stock Niri config. NiriFX movement and pointer drag are omitted; JSON preserves those settings.";
};
byId("pointer-kdl").onclick = () => {
  try {
    const doc = effectDocument();
    download(
      "nirifx-session.kdl",
      renderKdl(doc, { pointer: true, movement: !!doc.actions?.movement }),
      "text/plain",
    );
    byId("status").textContent =
      "Downloaded NiriFX session config with all selected actions and pointer settings. It requires matching compositor extensions.";
  } catch (error) {
    byId("error").textContent = error.message;
  }
};
byId("share").onclick = async () => {
  try {
    // Never copy the current local session URL: it may carry an HTTP save token.
    const url = new URL("https://jturbide.github.io/niri-fx/studio/");
    url.hash = new URLSearchParams({
      style: encodeShareDocument(effectDocument()),
      seed: String(seed),
      progress: String(progress),
      action: editingAction,
      mode,
      ...(mode === "resize"
        ? { direction: byId("resize-direction").value }
        : mode === "movement"
          ? { direction: byId("movement-direction").value }
          : {}),
    });
    byId("share-url").value = url.href;
    byId("share-result").hidden = false;
    try {
      await navigator.clipboard.writeText(url.href);
      byId("status").textContent =
        "Copied preview link. Anyone with the link can preview these settings.";
    } catch {
      byId("share-url").select();
      byId("status").textContent =
        "Copy the preview link below. Anyone with the link can preview these settings.";
    }
  } catch (error) {
    byId("error").textContent = error.message;
  }
};
function saveTarget() {
  const target = byId("save-target").value;
  byId("save").disabled = target === "inir" && !catalog.connection;
  byId("save").textContent = target === "inir" ? "Save to iRiS" : "Download preset file";
  byId("save-help").textContent =
    target === "inir"
      ? "Saving adds a style to iRiS Settings → Windows → Movement → Style. Select it there to activate."
      : target === "noctalia"
        ? "Download the preset into your Noctalia Niri Animations folder, then select it in the picker."
        : "Download a Niri config include or export editable JSON. Apply it through standalone setup when ready.";
}
byId("save-target").onchange = saveTarget;
byId("save-target").value = catalog.save_target;
saveTarget();
if (catalog.connection?.target === "native") {
  byId("save-target").hidden = byId("save").hidden = true;
  document.querySelector('label[for="save-target"]').hidden = true;
  byId("save-help").textContent =
    "Save to My profiles keeps portable settings. Select for next login stores the managed recipe, including its continuous fragment choice. Your current desktop stays unchanged.";
}
if (catalog.connection)
  setInterval(
    () => fetch("/ping?token=" + encodeURIComponent(catalog.connection.token)).catch(() => {}),
    45000,
  );
if (!catalog.connection)
  byId("status").textContent =
    "Preview only: download a Niri preset or export editable JSON. Previewing does not activate effects.";
byId("studio-kind").textContent = catalog.hosted ? "WEB STUDIO" : "LOCAL STUDIO";
byId("hosted-note").hidden = !catalog.hosted;
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
          : "Downloaded a stock Niri animation include. NiriFX movement and pointer drag are omitted; JSON preserves those settings.";
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
    const previewFrame = pointerPreviewFrame || comboPreviewFrame,
      renderMode = previewFrame?.mode || mode,
      resizing = renderMode === "resize",
      moving = renderMode === "movement",
      pointer = renderMode === "pointer",
      idle =
        renderMode === "idle" ||
        (!previewFrame && actions && byId("action-mode").value !== "style"),
      renderEffect = previewFrame?.effect || (comparing ? pinned.parameters : parameters),
      source = pointer
        ? POINTER_PREVIEW_SHADER
        : idle
          ? "vec4 close_color(vec3 coords,vec3 size){vec2 p=coords.xy;if(p.x<0.0||p.y<0.0||p.x>1.0||p.y>1.0)return vec4(0.0);return texture2D(niri_tex,p);}"
          : shaderFor(renderEffect, false, resizing, moving);
    const renderKey =
      source + "\n// " + renderMode + (previewFrame ? " centered preview geometry" : "");
    if (renderKey === lastSource) return;
    const uniforms =
      resizing && !idle
        ? "uniform sampler2D niri_tex_prev;uniform sampler2D niri_tex_next;uniform mat3 niri_geo_to_tex_prev;uniform mat3 niri_geo_to_tex_next;uniform mat3 niri_curr_geo_to_next_geo;uniform mat3 niri_curr_geo_to_prev_geo;uniform vec2 fx_resize_from;uniform vec2 fx_resize_to;"
        : pointer
          ? "uniform vec2 fx_move_origin;"
          : "uniform sampler2D niri_tex;uniform mat3 niri_geo_to_tex;uniform float niri_random_seed;uniform vec2 niri_move_delta;uniform vec2 niri_move_impulse;uniform vec2 fx_move_origin;";
    const geometry =
      resizing && !idle ? "mix(fx_resize_from,fx_resize_to,niri_clamped_progress)" : "fx_window";
    const color = pointer
      ? "pointer_color((pixel-origin)/size,size)"
      : `${resizing && !idle ? "resize_color" : moving && !idle ? "move_color" : "close_color"}(vec3((pixel-origin)/size,1.0),vec3(size,1.0))`;
    const fragment = `precision highp float;varying vec2 uv;uniform float niri_clamped_progress;uniform vec2 fx_surface;uniform vec2 fx_window;${uniforms}${source}\nvoid main(){vec2 pixel=vec2(uv.x,1.0-uv.y)*fx_surface;vec2 size=${geometry};vec2 origin=${resizing ? "(fx_surface-size)*0.5" : (moving && !idle) || pointer || (idle && previewFrame) ? "fx_move_origin" : previewFrame ? "(fx_surface-size)*0.5" : "(fx_surface-size)*vec2(0.5,0.473684210526)"};gl_FragColor=${color};}`;
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
    lastSource = renderKey;
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
    const previewFrame = pointerPreviewFrame || comboPreviewFrame;
    if (!previewFrame) progress = value;
    const renderMode = previewFrame?.mode || mode;
    if (["move", "swap"].includes(renderMode)) motionPreview.draw(value, mode, parameters, seed);
    else {
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(gl.getUniformLocation(program, "fx_surface"), canvas.width, canvas.height);
      gl.uniform2f(
        gl.getUniformLocation(program, "fx_window"),
        ...(previewFrame?.size || benchmarkWindow || [600, 380]),
      );
      const direction = { right: [1, 0], left: [-1, 0], down: [0, 1], up: [0, -1] }[
        (comboPreviewFrame?.mode === "movement" ? comboPreviewFrame.direction : null) ||
          byId("movement-direction").value
      ];
      const windowSize = previewFrame?.size || benchmarkWindow || [600, 380];
      const travel = 160 * (value * value * (3 - 2 * value) - 0.5);
      gl.uniform2f(
        gl.getUniformLocation(program, "fx_move_origin"),
        (canvas.width - windowSize[0]) * 0.5 + (previewFrame?.offset[0] ?? direction[0] * travel),
        (canvas.height - windowSize[1]) * 0.5 + (previewFrame?.offset[1] ?? direction[1] * travel),
      );
      gl.uniform2f(
        gl.getUniformLocation(program, "niri_pointer_anchor"),
        ...(previewFrame?.pointer?.anchor || [0.5, 0.06]),
      );
      gl.uniform2f(
        gl.getUniformLocation(program, "niri_pointer_deformation"),
        ...(previewFrame?.pointer?.deformation || [0, 0]),
      );
      gl.uniform2f(gl.getUniformLocation(program, "niri_move_impulse"), ...direction);
      gl.uniform2f(
        gl.getUniformLocation(program, "niri_move_delta"),
        direction[0] * 160,
        direction[1] * 160,
      );
      // A shrink is a new forward transition, with both geometry and textures
      // exchanged. Reversing growth frames gives the wrong direction to shaders.
      const shrinking =
        renderMode === "resize" &&
        (comboPreviewFrame?.direction || byId("resize-direction").value) === "shrink";
      const small = benchmarkWindow || [600, 380];
      const large = benchmarkWindow
        ? [Math.round(canvas.width * 0.8), Math.round(canvas.height * 0.7)]
        : [800, 440];
      const from = shrinking ? large : small;
      const to = shrinking ? small : large;
      gl.uniform2f(gl.getUniformLocation(program, "fx_resize_from"), ...from);
      gl.uniform2f(gl.getUniformLocation(program, "fx_resize_to"), ...to);
      gl.uniform1i(gl.getUniformLocation(program, "niri_tex_prev"), shrinking ? 1 : 0);
      gl.uniform1i(gl.getUniformLocation(program, "niri_tex_next"), shrinking ? 0 : 1);
      for (const [suffix, size] of [
        ["prev", from],
        ["next", to],
      ])
        gl.uniformMatrix3fv(
          gl.getUniformLocation(program, "niri_curr_geo_to_" + suffix + "_geo"),
          false,
          new Float32Array([
            (from[0] + (to[0] - from[0]) * value) / size[0],
            0,
            0,
            0,
            (from[1] + (to[1] - from[1]) * value) / size[1],
            0,
            0,
            0,
            1,
          ]),
        );
      gl.uniform1f(gl.getUniformLocation(program, "niri_clamped_progress"), value);
      gl.uniform1f(
        gl.getUniformLocation(program, "niri_random_seed"),
        comboPreviewFrame?.seed ?? (comparing ? pinned.seed : seed),
      );
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      const hiddenEndpoint =
        previewFrame?.visible === false ||
        (!previewFrame &&
          actions &&
          byId("action-mode").value === "off" &&
          editingAction === "close");
      if (!hiddenEndpoint) gl.drawArrays(gl.TRIANGLES, 0, 6);
    }
    if (!pointerPreviewFrame) {
      byId("progress").value = Math.round(value * 1000);
      byId("amount").textContent = Math.round(value * 100) + "%";
    }
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
        mode === "movement"
          ? `NiriFX movement · ${parameters.movement_ms} ms · JSON preserves the effect; stock exports omit it`
          : mode === "resize"
            ? `Resize · ${parameters.resize_ms} ms · ${(actions ? actions.resize : parameters.resize) ? "Included when you save" : "Preview only: resize is disabled for this style"}`
            : `${parameters.family === "slices" ? parameters.slice_count + " slices" : parameters.family !== "fragments" ? catalog.families[parameters.family].label + " window" : "About " + count + " pieces in this window"} · ${parameters.open_ms} ms opening · ${parameters.close_ms} ms closing`;
      byId("caption").textContent =
        actions && byId("action-mode").value !== "style"
          ? title(editingAction) + " · " + byId("action-mode-note").textContent
          : (comparing ? "Pinned A · " : pinned ? "B · " : "") + caption;
      document.documentElement.dataset.shaderStatus = "ready";
    } catch (error) {
      byId("error").textContent = error.message;
      document.documentElement.dataset.shaderStatus = "error";
    }
  }
  // Pointer interaction owns a temporary view and clock, never a profile action.
  // Restoring the view leaves the editor's progress, seed and history untouched.
  let pointerView = null,
    pointerSpring = null,
    pointerRaf = 0,
    pointerId = null,
    pointerLast = null,
    pointerOffset = [0, 0],
    pointerDemo = null;
  const pointerWindow = [600, 380];
  const pointerReduced = () => byId("reduced-motion").checked;
  const pointerConfig = () => ({
    ...pointerView.settings,
    ...(pointerReduced() ? { strength: 0 } : {}),
  });
  function releasePointerCapture() {
    const id = pointerId;
    pointerId = null;
    pointerLast = null;
    if (id !== null && canvas.hasPointerCapture(id)) canvas.releasePointerCapture(id);
  }
  function pointerPoint(event) {
    // object-fit:contain can letterbox the canvas when max-height applies. Map
    // the visible bitmap, not its outer CSS box; canvas units are logical pixels.
    const rect = canvas.getBoundingClientRect();
    const scale = Math.min(canvas.clientWidth / canvas.width, canvas.clientHeight / canvas.height);
    return [
      (event.clientX -
        rect.left -
        canvas.clientLeft -
        (canvas.clientWidth - canvas.width * scale) / 2) /
        scale,
      (event.clientY -
        rect.top -
        canvas.clientTop -
        (canvas.clientHeight - canvas.height * scale) / 2) /
        scale,
    ];
  }
  function pointerOrigin() {
    return pointerWindow.map(
      (size, axis) => ((axis ? canvas.height : canvas.width) - size) / 2 + pointerOffset[axis],
    );
  }
  function paintPointer(sample, phase) {
    if (!pointerView) return;
    pointerPreviewFrame = { mode: "pointer", pointer: sample, offset: [...pointerOffset] };
    rebuild();
    draw(0);
    document.documentElement.dataset.pointerPreview = phase;
    byId("pointer-preview-status").textContent = pointerReduced()
      ? "Reduced motion: direct movement, no deformation or settling."
      : phase === "demo"
        ? "Scripted drag and release. Reset position to return to interactive dragging."
        : phase === "dragging"
          ? "Dragging the sample window. Reverse direction, then let go."
          : phase === "settling"
            ? "Released. The spring is settling at the same window position."
            : "Drag the sample window to try these pointer settings.";
    document.documentElement.dataset.shaderStatus = "ready";
  }
  function pointerTick(now) {
    pointerRaf = 0;
    if (!pointerView) return;
    try {
      if (pointerDemo) {
        const elapsed = Math.min(pointerDemo.demo.durationMs, now - pointerDemo.started);
        const state = pointerDemo.demo.sample(elapsed);
        pointerOffset = [...state.offset];
        paintPointer(state, "demo");
        if (elapsed < pointerDemo.demo.durationMs) pointerRaf = requestAnimationFrame(pointerTick);
        else {
          pointerDemo = null;
          pointerSpring = createPointerSpring(pointerView.settings, state.anchor, now);
          paintPointer(pointerSpring.sample(now), "ready");
        }
      } else {
        const state = pointerSpring.sample(now);
        paintPointer(state, pointerId !== null ? "dragging" : state.moving ? "settling" : "ready");
        if (state.moving && !pointerReduced()) pointerRaf = requestAnimationFrame(pointerTick);
      }
    } catch (error) {
      cancelPointerPreview();
      byId("error").textContent = "Cannot preview pointer drag: " + error.message;
    }
  }
  function advancePointer(now = performance.now()) {
    cancelAnimationFrame(pointerRaf);
    pointerTick(now);
  }
  function resetPointer() {
    if (!pointerView) return;
    cancelAnimationFrame(pointerRaf);
    releasePointerCapture();
    pointerDemo = null;
    pointerOffset = [0, 0];
    pointerView.grabbed = false;
    const now = performance.now();
    pointerSpring = createPointerSpring(pointerConfig(), [0.5, 0.06], now);
    advancePointer(now);
  }
  cancelPointerPreview = () => {
    if (!pointerView) return;
    cancelAnimationFrame(pointerRaf);
    pointerRaf = 0;
    releasePointerCapture();
    pointerDemo = null;
    pointerSpring = null;
    pointerPreviewFrame = null;
    for (const [id, hidden] of Object.entries(pointerView.visibility)) byId(id).hidden = hidden;
    for (const [tab, pressed] of pointerView.tabs) tab.setAttribute("aria-pressed", pressed);
    pointerView = null;
    byId("pointer-preview-tools").hidden = true;
    byId("try-pointer").textContent = "Try pointer drag";
    byId("try-pointer").setAttribute("aria-pressed", "false");
    delete document.documentElement.dataset.pointerPreview;
    refresh();
  };
  byId("try-pointer").onclick = () => {
    if (pointerView) {
      cancelPointerPreview();
      return;
    }
    const settings = normalizePreset(effectDocument()).pointer;
    if (!settings || settings.strength <= 0) return;
    cancelComboPreview();
    cancelAnimationFrame(frame);
    pointerView = {
      settings: structuredClone(settings),
      visibility: Object.fromEntries(
        [
          "stage",
          "motion-stage",
          "concept-note",
          "effect-playback-controls",
          "caption",
          "combo-preview-status",
        ].map((id) => [id, byId(id).hidden]),
      ),
      tabs: [...document.querySelectorAll("[data-mode]")].map((tab) => [
        tab,
        tab.getAttribute("aria-pressed"),
      ]),
    };
    canvas.hidden = false;
    for (const id of [
      "motion-stage",
      "concept-note",
      "effect-playback-controls",
      "caption",
      "combo-preview-status",
    ])
      byId(id).hidden = true;
    for (const [tab] of pointerView.tabs) tab.setAttribute("aria-pressed", "false");
    byId("pointer-preview-tools").hidden = false;
    byId("try-pointer").textContent = "Stop pointer preview";
    byId("try-pointer").setAttribute("aria-pressed", "true");
    resetPointer();
    canvas.focus({ preventScroll: true });
  };
  function playPointerDemo() {
    if (!pointerView) return;
    resetPointer();
    if (pointerReduced()) return;
    pointerDemo = { demo: createPointerDemo(pointerView.settings), started: performance.now() };
    advancePointer(pointerDemo.started);
  }
  byId("pointer-demo").onclick = playPointerDemo;
  byId("pointer-reset").onclick = resetPointer;
  byId("pointer-stop").onclick = cancelPointerPreview;
  canvas.addEventListener("pointerdown", (event) => {
    if (!pointerView || pointerDemo || pointerId !== null || event.button !== 0 || !event.isPrimary)
      return;
    const point = pointerPoint(event),
      origin = pointerOrigin();
    const anchor = point.map((value, axis) => (value - origin[axis]) / pointerWindow[axis]);
    if (anchor.some((value) => value < 0 || value > 1)) return;
    event.preventDefault();
    canvas.setPointerCapture(event.pointerId);
    pointerId = event.pointerId;
    pointerLast = point;
    const now = performance.now();
    const previous = pointerSpring.sample(now);
    // Native tiles create a spring at the first grab point. Only a spring that
    // still owns deformation blends a new anchor into its existing motion.
    if (!pointerView.grabbed || (previous.released && !previous.moving))
      pointerSpring = createPointerSpring(pointerConfig(), anchor, now);
    else pointerSpring.grab(anchor, now);
    pointerView.grabbed = true;
    advancePointer(now);
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!pointerView || pointerId !== event.pointerId) return;
    event.preventDefault();
    const point = pointerPoint(event);
    const next = pointerOffset.map((value, axis) => {
      const limit = Math.max(
        0,
        ((axis ? canvas.height : canvas.width) - pointerWindow[axis]) / 2 - 66,
      );
      return Math.max(-limit, Math.min(limit, value + point[axis] - pointerLast[axis]));
    });
    const delta = next.map((value, axis) => value - pointerOffset[axis]);
    pointerLast = point;
    pointerOffset = next;
    const now = performance.now();
    pointerSpring.push(delta, now);
    advancePointer(now);
  });
  canvas.addEventListener("pointerup", (event) => {
    if (!pointerView || pointerId !== event.pointerId) return;
    releasePointerCapture();
    const now = performance.now();
    pointerSpring.release(now);
    advancePointer(now);
  });
  for (const type of ["pointercancel", "lostpointercapture"])
    canvas.addEventListener(type, (event) => {
      if (pointerId === event.pointerId) cancelPointerPreview();
    });
  canvas.addEventListener("keydown", (event) => {
    if (!pointerView) return;
    if (["Enter", " "].includes(event.key)) {
      event.preventDefault();
      playPointerDemo();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (pointerView && event.key === "Escape") {
      event.preventDefault();
      cancelPointerPreview();
    }
  });
  for (const type of ["click", "input", "change"])
    document.addEventListener(
      type,
      (event) => {
        if (
          !pointerView ||
          !(event.target instanceof Element) ||
          event.target.closest("#try-pointer,#pointer-preview-tools,#stage,#reduced-motion") ||
          !event.target.closest("button,input,select")
        )
          return;
        cancelPointerPreview();
      },
      true,
    );
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) cancelPointerPreview();
  });
  addEventListener("blur", cancelPointerPreview);
  addEventListener("resize", cancelPointerPreview);
  // Read-only lifecycle diagnostics let real-browser checks verify that stopping
  // a preview releases capture and leaves no scheduled animation behind.
  window.niriFxPointerPreview = {
    get active() {
      return !!pointerView;
    },
    snapshot() {
      return structuredClone({
        active: !!pointerView,
        captured: pointerId !== null,
        scheduled: !!pointerRaf,
        demo: !!pointerDemo,
        offset: pointerOffset,
        frame: pointerPreviewFrame,
      });
    },
    stop: () => cancelPointerPreview(),
  };

  let comboView = null;
  function comboButton(active) {
    byId("preview-combo").textContent = active ? "Stop preview" : "Preview combo";
    byId("preview-combo").setAttribute("aria-pressed", String(active));
  }
  const comboPreview = createComboPreview({
    normalizeDocument: normalizePreset,
    families: catalog.families,
    pointerDemo: createPointerDemo,
    render(state) {
      comboPreviewFrame = state;
      try {
        rebuild();
        draw(state.progress);
        byId("error").textContent = "";
        byId("combo-preview-status").textContent =
          state.label + (state.phase === "hold" ? " · Pause" : "") + " · " + state.support;
        document.documentElement.dataset.comboAction = state.action;
        document.documentElement.dataset.shaderStatus = "ready";
      } catch (error) {
        comboPreview.stop();
        comboButton(false);
        byId("error").textContent = error.message;
        document.documentElement.dataset.shaderStatus = "error";
      }
    },
    onFinish() {
      // Leave the completed close visible. Returning to editing restores its
      // original view, rather than flashing a partially deconstructed window.
      comboButton(false);
      document.documentElement.dataset.comboState = "complete";
      byId("combo-preview-status").textContent += " · Complete";
    },
  });
  window.niriFxComboPreview = comboPreview;
  cancelComboPreview = () => {
    comboPreview.stop();
    if (!comboView) return;
    comboPreviewFrame = null;
    for (const [id, hidden] of Object.entries(comboView.visibility)) byId(id).hidden = hidden;
    byId("timeline-label").textContent = comboView.timeline;
    for (const [id, disabled] of Object.entries(comboView.disabled)) byId(id).disabled = disabled;
    for (const [tab, pressed] of comboView.tabs) tab.setAttribute("aria-pressed", pressed);
    comboView = null;
    comboButton(false);
    byId("combo-preview-status").hidden = true;
    delete document.documentElement.dataset.comboAction;
    delete document.documentElement.dataset.comboState;
    refresh();
  };
  byId("preview-combo").onclick = () => {
    cancelPointerPreview();
    if (comboPreview.active) {
      cancelComboPreview();
      return;
    }
    cancelComboPreview();
    cancelAnimationFrame(frame);
    try {
      // Validate before changing the view. Only selected actions are planned;
      // a movement preview does not activate an experimental compositor.
      const doc = normalizePreset(effectDocument());
      comboPreview.plan(doc, { seed });
      comboView = {
        visibility: Object.fromEntries(
          ["stage", "motion-stage", "concept-note"].map((id) => [id, byId(id).hidden]),
        ),
        disabled: Object.fromEntries(["progress", "pause"].map((id) => [id, byId(id).disabled])),
        timeline: byId("timeline-label").textContent,
        tabs: [...document.querySelectorAll("[data-mode]")].map((tab) => [
          tab,
          tab.getAttribute("aria-pressed"),
        ]),
      };
      byId("stage").hidden = false;
      byId("motion-stage").hidden = byId("concept-note").hidden = true;
      byId("timeline-label").textContent = "Action progress";
      byId("progress").disabled = byId("pause").disabled = true;
      for (const [tab] of comboView.tabs) tab.setAttribute("aria-pressed", "false");
      byId("combo-preview-status").hidden = false;
      document.documentElement.dataset.comboState = "playing";
      comboButton(true);
      comboPreview.play(doc, { seed, reducedMotion: byId("reduced-motion").checked });
    } catch (error) {
      cancelComboPreview();
      byId("error").textContent = "Cannot preview combo: " + error.message;
    }
  };
  // Stop before event handlers edit or export the document. Keep an incoming
  // slider value: restoring the original view also redraws its progress control.
  for (const eventName of ["click", "input", "change"])
    document.addEventListener(
      eventName,
      (event) => {
        if (
          !comboView ||
          !(event.target instanceof Element) ||
          event.target.closest("#preview-combo") ||
          !event.target.closest("button,input,select")
        )
          return;
        const timelineValue = byId("progress").value;
        cancelComboPreview();
        if (event.target === byId("progress")) byId("progress").value = timelineValue;
      },
      true,
    );
  // Shader-only GPU microbenchmark. No screen capture or compositor timing claims.
  window.niriFxBenchmark = async ({
    width = 1920,
    height = 1080,
    samples = 60,
    draws = 1,
  } = {}) => {
    cancelPointerPreview();
    cancelComboPreview();
    if (
      ![width, height, samples, draws].every(Number.isInteger) ||
      width < 320 ||
      height < 240 ||
      width > 7680 ||
      height > 4320 ||
      samples < 10 ||
      samples > 1000 ||
      draws < 1 ||
      draws > 8
    )
      throw new Error("Invalid benchmark dimensions, sample count or draw count");
    const debug = gl.getExtension("WEBGL_debug_renderer_info");
    const renderer = debug ? gl.getParameter(debug.UNMASKED_RENDERER_WEBGL) : "unavailable";
    const vendor = debug ? gl.getParameter(debug.UNMASKED_VENDOR_WEBGL) : "unavailable";
    const timer = gl.getExtension("EXT_disjoint_timer_query");
    const report = {
      kind: "webgl-shader-gpu",
      action: mode === "effect" ? "close" : mode,
      ...(mode === "resize" ? { direction: byId("resize-direction").value } : {}),
      renderer,
      vendor,
      width,
      height,
      samples,
      draws,
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
    if (!["effect", "resize", "movement"].includes(mode) || comparing)
      throw new Error("Use open/close, resize or movement preview, with A/B comparison off");
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
          // Time a batch of independent window passes, each with its normal
          // framebuffer clear. This is GPU load, not compositor concurrency.
          for (let pass = 0; pass < draws; pass++)
            draw(0.1 + (((index + 12 + pass * 7) % 31) / 31) * 0.8);
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
        ...(mode === "resize"
          ? { resizeLarge: [Math.round(width * 0.8), Math.round(height * 0.7)] }
          : {}),
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
    if (["move", "swap"].includes(mode) && !supportsConcept())
      document.querySelector("[data-mode=effect]").click();
    labels();
    refresh();
    recordHistory();
  }
  for (const id of [...numeric, ...choices, "density", "resize"])
    byId(id).addEventListener("input", update);
  byId("family").onchange = () => {
    byId("preset-collection").value = "";
    byId("preset").value = Object.keys(catalog.presets).find(
      (name) => catalog.presets[name].family === byId("family").value,
    );
    byId("preset").dispatchEvent(new Event("change"));
  };
  byId("preset").onchange = () => {
    if (!byId("preset").value) return;
    cancelAnimationFrame(frame);
    parameters = { ...catalog.presets[byId("preset").value] };
    if (
      actions &&
      ["resize", "movement"].includes(editingAction) &&
      !catalog.families[parameters.family][editingAction]
    ) {
      parameters = { ...catalog.presets.balanced };
      byId("status").textContent =
        "This family does not support " + editingAction + ". Select a supported family.";
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
    if (actions && byId("action-mode").value !== "style") {
      draw(editingAction === "close" ? 1 : 0);
      return;
    }
    if (mode === "resize") byId("resize-direction").value = opening ? "shrink" : "grow";
    if (mode === "movement" && opening)
      byId("movement-direction").value = { right: "left", left: "right", up: "down", down: "up" }[
        (comboPreviewFrame?.mode === "movement" ? comboPreviewFrame.direction : null) ||
          byId("movement-direction").value
      ];
    if (byId("reduced-motion").checked) {
      draw(["resize", "movement"].includes(mode) ? 1 : opening ? 0 : 1);
      return;
    }
    const start = performance.now(),
      duration =
        mode === "effect"
          ? opening
            ? parameters.open_ms
            : parameters.close_ms
          : mode === "resize"
            ? parameters.resize_ms
            : mode === "movement"
              ? parameters.movement_ms
              : Math.max(900, parameters.open_ms + parameters.close_ms);
    function tick(now) {
      const p = Math.min(1, (now - start) / duration);
      draw(["resize", "movement"].includes(mode) ? p : opening ? 1 - p : p);
      if (p < 1) frame = requestAnimationFrame(tick);
    }
    frame = requestAnimationFrame(tick);
  }
  byId("advanced").onchange = () => {
    byId("editor-panel").dataset.view = byId("advanced").checked ? "advanced" : "basic";
  };
  const motionPreference = matchMedia("(prefers-reduced-motion: reduce)");
  byId("reduced-motion").checked = motionPreference.matches;
  motionPreference.addEventListener("change", (event) => {
    cancelComboPreview();
    byId("reduced-motion").checked = event.matches;
    cancelAnimationFrame(frame);
    resetPointer();
  });
  byId("reduced-motion").onchange = () => {
    cancelAnimationFrame(frame);
    resetPointer();
  };
  byId("resize-direction").onchange = () => {
    cancelAnimationFrame(frame);
    draw(progress);
  };
  byId("pause").onclick = () => cancelAnimationFrame(frame);
  byId("open").onclick = () => animate(true);
  byId("close").onclick = () => animate(false);
  byId("movement-direction").onchange = () => {
    cancelAnimationFrame(frame);
    refresh();
  };
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
      if (file.size > catalog.max_document_bytes) throw new Error("Preset must be at most 16 KiB.");
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
        ". Resize override: " +
        ((actions ? actions.resize : parameters.resize) ? "included" : "none") +
        ". Preview or edit, then save/export when ready.";
    } catch (error) {
      if (epoch === importEpoch) byId("error").textContent = "Import failed: " + error.message;
    } finally {
      if (epoch === importEpoch) byId("import-file").value = "";
    }
  };
  byId("profile").onchange = () => {
    const id = byId("profile").value;
    if (!Object.hasOwn(catalog.profiles, id)) return;
    cancelAnimationFrame(frame);
    comparing = false;
    loadDocument(normalizePreset(catalog.profiles[id]));
    byId("preset").value = "";
    populate();
    document.querySelector('[data-mode="effect"]').click();
    recordHistory();
    byId("status").textContent =
      catalog.profile_descriptions[id] +
      ". Existing resize settings are preserved. Previewing does not activate effects.";
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
      byId("action-mode").value = "style";
      parameters.resize = false;
    } else {
      commitAction();
      parameters = { ...actions.open };
      actions = null;
      desktopMotion = null;
      editingAction = "open";
    }
    populate();
    refresh();
    recordHistory();
  };
  byId("desktop-motion").onchange = () => {
    const name = byId("desktop-motion").value;
    desktopMotion = name ? structuredClone(catalog.motion_packs[name]) : null;
    recordHistory();
  };
  byId("action").onchange = () => {
    chooseAction(byId("action").value);
    byId("preset").value = "";
    populate();
    document
      .querySelector(
        ["resize", "movement"].includes(editingAction)
          ? `[data-mode=${editingAction}]`
          : "[data-mode=effect]",
      )
      .click();
    refresh();
  };
  byId("action-mode").onchange = () => {
    if (isActionStyle(actions[editingAction]))
      rememberedActions[editingAction] = { ...parameters, resize: false };
    if (byId("action-mode").value === "style")
      parameters = { ...actionParameters(editingAction), resize: false };
    commitAction();
    populate();
    labels();
    refresh();
    recordHistory();
  };
  for (const direction of ["undo", "redo"])
    byId(direction).onclick = () => {
      historyIndex += direction === "undo" ? -1 : 1;
      const snapshot = JSON.parse(editHistory[historyIndex]);
      if (sessionSettings)
        sessionSettings.fragment_preset = snapshot.session?.fragment_preset || null;
      editingAction = snapshot.action;
      loadDocument(snapshot.document, snapshot.action);
      byId("action").value = editingAction;
      byId("preset").value = snapshot.preset;
      populate();
      refresh();
      historyButtons();
      workspace?.sync();
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
  function loadSharedSettings() {
    const shared = new URLSearchParams(location.hash.slice(1));
    if (!shared.has("style")) return;
    try {
      const doc = decodeShareDocument(shared.get("style"));
      const action = ["open", "close", "resize", "movement"].includes(shared.get("action"))
        ? shared.get("action")
        : "open";
      cancelAnimationFrame(frame);
      loadDocument(doc, action);
      byId("preset").value = "";
      for (const key of ["seed", "progress"]) {
        const value = Number(shared.get(key));
        if (shared.has(key) && Number.isFinite(value) && value >= 0 && value <= 1) {
          if (key === "seed") seed = value;
          else progress = value;
        }
      }
      populate();
      byId("resize-direction").value = shared.get("direction") === "shrink" ? "shrink" : "grow";
      if (["left", "right", "up", "down"].includes(shared.get("direction")))
        byId("movement-direction").value = shared.get("direction");
      const requested = shared.get("mode"),
        button = [...document.querySelectorAll("[data-mode]")].find(
          (item) => item.dataset.mode === requested,
        );
      if (button && !button.disabled) button.click();
      refresh();
      recordHistory();
      byId("status").textContent =
        "Shared settings loaded. Resize override: " +
        ((actions ? actions.resize : parameters.resize) ? "included" : "none") +
        ". Previewing does not activate effects.";
    } catch (error) {
      byId("error").textContent = "Cannot open shared settings: " + error.message;
    }
  }
  loadSharedSettings();
  addEventListener("hashchange", loadSharedSettings);
  workspace = createFxLibrary({
    catalog,
    getDocument: effectDocument,
    sessionSettings,
    sessionChanged: recordHistory,
    select: (doc, action) => {
      cancelAnimationFrame(frame);
      comparing = false;
      loadDocument(normalizePreset(doc), action);
      byId("preset").value = "";
      populate();
      document
        .querySelector(`[data-mode=${["resize", "movement"].includes(action) ? action : "effect"}]`)
        .click();
      refresh();
      recordHistory();
    },
    preview: (action) => {
      cancelPointerPreview();
      cancelComboPreview();
      if (actions) chooseAction(action);
      populate();
      document
        .querySelector(`[data-mode=${["resize", "movement"].includes(action) ? action : "effect"}]`)
        .click();
      refresh();
      animate(action === "open");
    },
    edit: (action) => {
      if (!actions) byId("independent").click();
      byId("action").value = action;
      byId("action").dispatchEvent(new Event("change"));
      workspace.edit();
    },
    favorites: () => favorites,
    favorite: (id, replacement) => {
      favorites =
        replacement !== undefined
          ? [
              ...new Set([
                ...favorites.filter((name) => name !== id),
                ...(replacement ? [replacement] : []),
              ]),
            ]
          : favorites.includes(id)
            ? favorites.filter((name) => name !== id)
            : [...favorites, id];
      try {
        localStorage.setItem("nirifx-favorites", JSON.stringify(favorites));
      } catch {
        /* Session-only favorites still work. */
      }
      if (catalog.connection)
        fetch("/preferences", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-NiriFX-Token": catalog.connection.token,
          },
          body: JSON.stringify({ favorites }),
        })
          .then((response) => {
            if (!response.ok) throw new Error("Could not save favorites");
          })
          .catch((error) => {
            byId("error").textContent = error.message;
          });
      filterPresets();
    },
  });
} catch (error) {
  byId("error").textContent = error.message;
  document.documentElement.dataset.shaderStatus = "error";
}
