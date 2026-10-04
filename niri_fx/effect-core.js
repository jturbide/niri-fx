// Portable Studio operations: no DOM, WebGL, network, storage or mutation of inputs.
// Keep validation and number formatting equivalent to the Python domain layer.
// This classic script is inlined for file:// previews and tested directly in Node.
function createEffectCore(catalog) {
  const specs = catalog.specifications;
  function glslNumber(value) {
    const scaled = Math.floor(Math.abs(value) * 1000000 + 0.5);
    return (
      (value < 0 && scaled ? "-" : "") +
      Math.floor(scaled / 1000000) +
      "." +
      String(scaled % 1000000).padStart(6, "0")
    );
  }
  function shaderFor(p, opening, resizing = false, moving = false) {
    if (resizing && !catalog.families[p.family].resize)
      throw new Error("This effect family does not support resize.");
    if (moving && !catalog.families[p.family].movement)
      throw new Error("This effect family does not support movement.");
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
    const shape = p.fragment_mix === 1 ? p.fragment_secondary : p.fragment_shape;
    const mixed =
      p.fragment_mix > 0 && p.fragment_mix < 1 && p.fragment_shape !== p.fragment_secondary;
    const tokens = Object.fromEntries(
      Object.entries(specs)
        .filter(([, spec]) => spec.token)
        .map(([key, spec]) => [
          spec.token,
          spec.type === "choice"
            ? String(spec.choices.indexOf(p[key]))
            : spec.glsl_type === "int"
              ? String(p[key])
              : glslNumber(p[key]),
        ]),
    );
    Object.assign(tokens, {
      VARIED_RADIUS: p.wave_strength === 0 ? "2" : "3",
      SHAPED_RADIUS: String(shapeSearchRadius(p)),
      SHAPED_RESIZE_RADIUS: String(shapeSearchRadius(p, true)),
      SHAPED_PARTS:
        shape === "triangle" || (mixed && p.fragment_secondary === "triangle") ? "2" : "1",
      FRAGMENT_SHAPE: String(specs.fragment_shape.choices.indexOf(shape)),
      FRAGMENT_MIX: glslNumber(mixed ? p.fragment_mix : 0),
      ELASTIC_ORIGIN_X: glslNumber(catalog.elastic_anchors[p.elastic_anchor][0]),
      ELASTIC_ORIGIN_Y: glslNumber(catalog.elastic_anchors[p.elastic_anchor][1]),
      ENTRY: opening ? "open_color" : "close_color",
      PROGRESS: opening ? "1.0 - niri_clamped_progress" : "niri_clamped_progress",
    });
    const shaped =
      shape !== "square" ||
      mixed ||
      p.fragment_orientation !== 0 ||
      (p.fragment_roundness > 0 && p.fragment_transition !== 0.28);
    const renderer =
      p.family !== "fragments"
        ? p.family
        : shaped
          ? "shaped"
          : p.size_variation || p.direction_variation || p.wave_strength
            ? "varied"
            : classic
              ? "classic"
              : "gravity";
    return catalog.templates[
      resizing
        ? p.family === "fragments" &&
          (shaped || p.fragment_shrink || p.fragment_roundness || p.size_variation)
          ? "resize-shaped"
          : catalog.resize_templates[p.family]
        : moving
          ? "move-" + renderer
          : renderer
    ].replace(/@([A-Z_]+)@/g, (_, key) => {
      if (!Object.hasOwn(tokens, key)) throw new Error("Unknown shader token: " + key);
      return tokens[key];
    });
  }
  function shapeSearchRadius(p, resizing = false) {
    const shape = p.fragment_mix === 1 ? p.fragment_secondary : p.fragment_shape;
    const mixed =
      p.fragment_mix > 0 && p.fragment_mix < 1 && p.fragment_shape !== p.fragment_secondary;
    const aspect = ["square", "circle"].includes(shape) ? 1 : p.fragment_aspect;
    const stretch = Math.sqrt(Math.max(aspect, 1 / aspect));
    let radius = 0.5 * Math.sqrt(aspect + 1 / aspect);
    let low = 0.5,
      high = 0.5;
    if (shape === "triangle" || (mixed && p.fragment_secondary === "triangle")) {
      radius = Math.sqrt(Math.max(4 * aspect + 1 / aspect, aspect + 4 / aspect)) / 3;
      low = 1 / 3;
      high = 2 / 3;
    }
    let axial = 1;
    if (shape === "hexagon" && !mixed) {
      radius = stretch;
      axial = 2 / 3;
      low = high = 0;
    }
    const reach =
      (radius + (resizing ? 0.4 : 0.72 * p.dispersion)) *
        (!resizing && p.wave_strength ? 1.45 : 1) *
        stretch *
        axial +
      0.00001;
    return Math.max(Math.floor(reach + high), Math.ceil(reach - low));
  }
  function normalizePreset(doc) {
    if (doc?.kind === "profile") {
      if (
        doc.schema !== catalog.profile_schema ||
        !["kind", "schema", "name", "actions"].every((key) => Object.hasOwn(doc, key)) ||
        Object.keys(doc).some(
          (key) => !["kind", "schema", "name", "actions", "motion", "pointer"].includes(key),
        ) ||
        !doc.actions ||
        Object.keys(doc.actions).sort().join() !== "close,movement,open,resize"
      )
        throw new Error(
          `Expected profile schema ${catalog.profile_schema} with open, close, resize and movement actions.`,
        );
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
      return {
        kind: "profile",
        schema: catalog.profile_schema,
        name: doc.name,
        actions: normalized,
        ...(Object.hasOwn(doc, "motion") ? { motion: normalizeMotion(doc.motion) } : {}),
        ...(doc.pointer == null ? {} : { pointer: normalizePointer(doc.pointer) }),
      };
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
    if (Object.keys(doc).sort().join() !== "effect,name,schema")
      throw new Error("Preset requires schema, name and effect only.");
    // JavaScript's $ can match before a final newline; compare the full match to
    // mirror Python fullmatch rather than accepting a name the save API rejects.
    if (
      typeof doc.name !== "string" ||
      /^[A-Za-z0-9][A-Za-z0-9 _-]{0,47}$/.exec(doc.name)?.[0] !== doc.name
    )
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
  function normalizeMotion(data) {
    if (
      !data ||
      Array.isArray(data) ||
      Object.keys(data).sort().join() !== "camera,overview,workspace"
    )
      throw new Error("Desktop motion requires workspace, camera and overview only.");
    return Object.fromEntries(
      ["workspace", "camera", "overview"].map((name) => {
        const settings = data[name];
        if (
          !settings ||
          typeof settings !== "object" ||
          Array.isArray(settings) ||
          Object.keys(settings).some((key) => !Object.hasOwn(catalog.motion_defaults, key))
        )
          throw new Error("Desktop motion requires spring objects with supported parameters.");
        const spring = { ...catalog.motion_defaults, ...settings };
        if (!Number.isInteger(spring.stiffness))
          throw new Error("Motion stiffness must be a whole number.");
        for (const [key, [low, high]] of Object.entries(catalog.motion_limits)) {
          const value = spring[key];
          if (typeof value !== "number" || !Number.isFinite(value) || value < low || value > high)
            throw new Error("Motion " + key + " is outside its supported range.");
        }
        return [name, spring];
      }),
    );
  }
  function normalizePointer(data) {
    if (data === null) return null;
    if (
      !data ||
      typeof data !== "object" ||
      Array.isArray(data) ||
      Object.keys(data).sort().join() !== "damping,frequency,strength"
    )
      throw new Error("Pointer settings require strength, damping and frequency only.");
    const settings = {};
    for (const [key, [low, high]] of Object.entries(catalog.pointer_limits)) {
      const value = data[key];
      if (typeof value !== "number" || !Number.isFinite(value) || value < low || value > high)
        throw new Error(
          "Pointer " + key + " must be a finite number from " + low + " to " + high + ".",
        );
      if (key !== "strength" && !Number.isInteger(value))
        throw new Error("Pointer " + key + " must be a whole number.");
      settings[key] = value;
    }
    return settings;
  }
  function renderKdl(document, { movement = false, pointer = false } = {}) {
    const parameters = document.effect;
    let result = "// Generated by NiriFX Studio\nanimations {\n";
    const selected = document.actions || {
      open: parameters,
      close: parameters,
      resize: parameters.resize ? parameters : null,
      movement: parameters,
    };
    for (const action of ["open", "close", "resize", ...(movement ? ["movement"] : [])]) {
      const effect = selected[action];
      if (!effect) {
        if (action === "movement")
          throw new Error("The profile must explicitly choose a movement action.");
        continue;
      }
      result += `    window-${action} {\n        duration-ms ${effect[action + "_ms"]}\n        curve "linear"\n        custom-shader r"\n${shaderFor(effect, action === "open", action === "resize", action === "movement").trimEnd()}\n        "\n`;
      if (action === "movement" && pointer) result += pointerNode(document);
      result += "    }\n";
    }
    if (pointer && !movement)
      result += "    window-movement {\n" + pointerNode(document) + "    }\n";
    if (document.motion) {
      for (const [key, name] of [
        ["workspace", "workspace-switch"],
        ["camera", "horizontal-view-movement"],
        ["overview", "overview-open-close"],
      ]) {
        const spring = document.motion[key];
        result += `    ${name} {\n        spring damping-ratio=${glslNumber(spring.damping_ratio)} stiffness=${spring.stiffness} epsilon=${glslNumber(spring.epsilon)}\n    }\n`;
      }
    }
    return result + "}\n";
  }
  function pointerNode(document) {
    if (!document.actions || document.pointer == null)
      throw new Error("The profile must explicitly choose pointer settings.");
    const settings = normalizePointer(document.pointer);
    return `        pointer-wobble {\n            strength ${glslNumber(settings.strength)}\n            damping ${settings.damping}\n            frequency ${settings.frequency}\n        }\n`;
  }
  // Share links contain validated parameter data only. Omit unchanged defaults
  // to keep links readable by browsers; decoding uses the regular import rules.
  function encodeShareDocument(document) {
    const doc = normalizePreset(document);
    const compact = (effect) =>
      effect === null
        ? null
        : Object.fromEntries(
            Object.entries(effect).filter(([key, value]) => value !== catalog.defaults[key]),
          );
    const data = doc.actions
      ? {
          ...doc,
          actions: Object.fromEntries(
            Object.entries(doc.actions).map(([key, value]) => [key, compact(value)]),
          ),
        }
      : { ...doc, effect: compact(doc.effect) };
    const bytes = new TextEncoder().encode(JSON.stringify(data));
    if (bytes.length > catalog.max_document_bytes)
      throw new Error("Shared preset must be at most 16 KiB.");
    return btoa(String.fromCharCode(...bytes))
      .replaceAll("+", "-")
      .replaceAll("/", "_")
      .replace(/=+$/, "");
  }
  function decodeShareDocument(encoded) {
    if (
      !encoded ||
      encoded.length > Math.ceil((catalog.max_document_bytes * 4) / 3) ||
      !/^[A-Za-z0-9_-]+$/.test(encoded)
    )
      throw new Error("Invalid or oversized shared preset.");
    const bytes = Uint8Array.from(
      atob(encoded.replaceAll("-", "+").replaceAll("_", "/")),
      (character) => character.charCodeAt(0),
    );
    if (bytes.length > catalog.max_document_bytes)
      throw new Error("Shared preset must be at most 16 KiB.");
    return normalizePreset(JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)));
  }
  return {
    glslNumber,
    shaderFor,
    normalizePreset,
    normalizePointer,
    renderKdl,
    encodeShareDocument,
    decodeShareDocument,
  };
}
