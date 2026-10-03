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
            : spec.glsl_type === "int"
              ? String(p[key])
              : glslNumber(p[key]),
        ]),
    );
    Object.assign(tokens, {
      VARIED_RADIUS: p.wave_strength === 0 ? "2" : "3",
      ELASTIC_ORIGIN_X: glslNumber(catalog.elastic_anchors[p.elastic_anchor][0]),
      ELASTIC_ORIGIN_Y: glslNumber(catalog.elastic_anchors[p.elastic_anchor][1]),
      ENTRY: opening ? "open_color" : "close_color",
      PROGRESS: opening ? "1.0 - niri_clamped_progress" : "niri_clamped_progress",
    });
    return (
      resizing
        ? catalog.templates[catalog.resize_templates[p.family]]
        : p.family !== "fragments"
          ? catalog.templates[p.family]
          : p.size_variation || p.direction_variation || p.wave_strength
            ? catalog.templates.varied
            : classic
              ? catalog.templates.classic
              : catalog.templates.gravity
    ).replace(/@([A-Z_]+)@/g, (_, key) => {
      if (!Object.hasOwn(tokens, key)) throw new Error("Unknown shader token: " + key);
      return tokens[key];
    });
  }
  function normalizePreset(doc) {
    if (doc?.kind === "profile") {
      if (
        doc.schema !== catalog.profile_schema ||
        Object.keys(doc).sort().join() !== "actions,kind,name,schema" ||
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
  function renderKdl(document) {
    const parameters = document.effect;
    let result = "// Generated by NiriFX Studio\nanimations {\n";
    const selected = document.actions || {
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
    renderKdl,
    encodeShareDocument,
    decodeShareDocument,
  };
}
