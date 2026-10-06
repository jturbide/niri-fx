// Library-first presentation over the same validated documents as Studio.
// Selecting a card changes only the preview. Review and Apply are separate,
// and optional actions are never inferred from a family capability.
function createFxLibrary({
  catalog,
  getDocument,
  select: selectDocument,
  preview,
  edit,
  favorites,
  favorite,
  sessionSettings,
  sessionChanged,
}) {
  const element = (id) => document.getElementById(id);
  const core = createEffectCore(catalog);
  const native = catalog.connection?.target === "native";
  const nativeOptions = catalog.connection?.native;
  let nativeListing = null,
    nativeRestoreAvailable = false,
    nativeSetupChanged = false;
  const sharedBase = nativeOptions?.shared === true;
  const sharedSelectionChanged = () =>
    nativeSetupChanged ||
    (!!nativeListing && sharedBase !== (nativeListing.shared_state?.selected === true));
  const nativeSettings = sessionSettings || { fragment_preset: null };
  const title = (id) => id.replaceAll("-", " ").replace(/\b\w/g, (c) => c.toUpperCase());
  const styles = Object.fromEntries(
    Object.entries(catalog.presets).map(([id, effect]) => [
      id,
      {
        schema: catalog.schema,
        name: title(id),
        effect,
      },
    ]),
  );
  const builtins = { ...styles, ...catalog.profiles };
  const actionNames = {
    open: "Open",
    close: "Close",
    resize: "Resize",
    movement: "Move",
    swap: "Swap",
  };
  const capabilityFor = (action) => (action === "swap" ? "movement" : action);
  let browseAction = "open";
  let customs = {},
    managed = {},
    warnings = [],
    pendingProfile = null,
    review = null,
    busy = false,
    revision = 0;
  function select(doc, action, play = false) {
    selectDocument(doc, action);
    if (play && Object.hasOwn(actionNames, action)) preview(action);
  }
  function readBrowserProfiles() {
    customs = {};
    warnings = [];
    try {
      const saved = JSON.parse(localStorage.getItem("nirifx-my-profiles") || "{}");
      if (!saved || typeof saved !== "object" || Array.isArray(saved))
        throw new Error("Invalid browser library");
      for (const [id, doc] of Object.entries(saved)) {
        try {
          const normalized = core.normalizePreset(doc);
          if (id !== profileId(normalized.name)) throw new Error("Profile name mismatch");
          customs[id] = normalized;
        } catch {
          warnings.push(
            "A saved browser profile could not be read. Export your valid profiles before clearing browser storage.",
          );
        }
      }
    } catch {
      warnings.push("Browser profiles could not be read. JSON import and export remain available.");
    }
  }
  if (!catalog.connection) readBrowserProfiles();
  function profileId(name) {
    return (
      "custom-" +
      name
        .toLowerCase()
        .replace(/[ _-]+/g, "-")
        .replace(/-$/, "")
    );
  }
  const sameDocument = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  function selectedSaved() {
    return Object.entries(managed).find(([, entry]) => sameDocument(entry.document, getDocument()));
  }
  const isStyle = (value) => value !== null && typeof value === "object";
  const actionMode = (value) => (isStyle(value) ? "style" : value === "off" ? "off" : "preserve");
  const remembered = {};
  let rememberedPointer = null;
  const normalized = (effect) => ({ ...effect, resize: false });
  const equal = (a, b) =>
    isStyle(a) && isStyle(b) && Object.keys(catalog.defaults).every((key) => a[key] === b[key]);
  const fragmentChoices = nativeOptions?.fragment_choices || {};
  function chooseFragment(id) {
    nativeSettings.fragment_preset = id || null;
    if (id) {
      const doc = profile();
      doc.actions.movement = structuredClone(fragmentChoices[id].effect);
      select(doc, "movement", true);
    } else sessionChanged();
  }
  function sessionName(bundle, fallback) {
    if (!bundle) return fallback;
    const item = nativeListing?.bundles.find((row) => row.bundle_id === bundle);
    if (item?.status === "unavailable") return "Unavailable selection";
    return item?.customization?.document?.name || "NiriFX session";
  }
  for (const [id, choice] of Object.entries(fragmentChoices)) {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = choice.name;
    element("native-fragment-preset").append(option);
  }
  element("native-fragments").hidden = !native || nativeOptions.variant !== "fragment";
  element("native-fragment-preset").onchange = () =>
    chooseFragment(element("native-fragment-preset").value);
  const actionEffects = (doc) =>
    doc.actions
      ? { swap: null, ...doc.actions }
      : {
          open: normalized(doc.effect),
          close: normalized(doc.effect),
          resize: doc.effect.resize ? normalized(doc.effect) : null,
          movement: null,
          swap: null,
        };
  function profile() {
    const doc = getDocument();
    return {
      kind: "profile",
      schema: catalog.profile_schema,
      name: doc.name,
      actions: structuredClone(actionEffects(doc)),
      ...(doc.motion ? { motion: structuredClone(doc.motion) } : {}),
      ...(doc.pointer ? { pointer: structuredClone(doc.pointer) } : {}),
    };
  }
  const actionLabels = {
    open: "Choose an opening style",
    close: "Choose a closing style",
    resize: "Choose a resize style",
    movement: "Choose a move style",
    swap: "Choose a swap style",
    combo: "Choose a complete combo",
  };
  function chooseBrowseAction(action) {
    browseAction = action;
    if (action !== "combo" && element("library-collection").value === "customs")
      element("library-collection").value = "recommended";
    syncBrowse();
    cards();
    if (action !== "combo") preview(action);
  }
  for (const [action, label] of Object.entries({ ...actionNames, combo: "Combos" })) {
    const button = document.createElement("button");
    button.dataset.libraryAction = action;
    const caption = document.createElement("strong");
    caption.textContent = label;
    const selection = document.createElement("small");
    button.append(caption, selection);
    button.onclick = () => chooseBrowseAction(action);
    element("library-actions").append(button);
  }
  function styleName(effect) {
    return title(
      Object.keys(styles).find((id) => equal(normalized(styles[id].effect), effect)) ||
        effect.family,
    );
  }
  function syncBrowse() {
    const actions = actionEffects(getDocument());
    for (const button of element("library-actions").children) {
      const action = button.dataset.libraryAction;
      button.setAttribute("aria-pressed", String(action === browseAction));
      button.querySelector("small").textContent =
        action === "combo"
          ? "All actions together"
          : action === "movement" && nativeSettings.fragment_preset
            ? fragmentChoices[nativeSettings.fragment_preset].name
            : isStyle(actions[action])
              ? styleName(actions[action])
              : title(actionMode(actions[action]));
    }
    element("library-heading").textContent = actionLabels[browseAction];
    element("library-action-choices").hidden = browseAction === "combo";
    for (const choice of ["preserve", "off"])
      element("library-" + choice).setAttribute(
        "aria-pressed",
        String(actionMode(actions[browseAction]) === choice),
      );
    element("library-action-help").textContent =
      browseAction === "combo"
        ? "A combo replaces all the choices shown above. Select an action to mix in another style."
        : browseAction === "swap"
          ? native && !nativeOptions.swap_supported
            ? "Preview and save a separate swap style here. Applying it requires an updated NiriFX compositor; this retained build shares the Move setting."
            : "For Swap window left/right commands. Preserve keeps the underlying swap setting, which follows Move when unset. Dragging and column reordering use Move."
          : browseAction === "movement" && native
            ? "Choose a style to preview its material. Continuous fragments follow your gestures on the NiriFX desktop."
            : "Click a style to preview it. Your other choices stay the same.";
  }
  for (const choice of ["preserve", "off"])
    element("library-" + choice).onclick = () => {
      const doc = profile();
      doc.actions[browseAction] = choice === "off" ? "off" : null;
      select(doc, browseAction, true);
    };
  element("library-replay").onclick = () => preview(browseAction);
  function selectOptions(select, action, effect) {
    const option = (value, text) => {
      const node = document.createElement("option");
      node.value = value;
      node.textContent = text;
      select.append(node);
    };
    if (!select.options.length) {
      option("", "Choose a style");
      for (const [id, doc] of Object.entries(styles))
        if (
          ["open", "close"].includes(action) ||
          catalog.families[doc.effect.family][capabilityFor(action)]
        )
          option(id, doc.name);
    }
    select.querySelector('[value="custom"]')?.remove();
    const match = Object.keys(styles).find((id) => equal(normalized(styles[id].effect), effect));
    if (isStyle(effect) && !match) {
      const combo = Object.values(catalog.profiles).find((doc) =>
        equal(doc.actions[action], effect),
      );
      option("custom", combo ? combo.name + " · " + actionNames[action] : "Custom settings");
    }
    select.value = match || (isStyle(effect) ? "custom" : "");
  }
  for (const [action, label] of Object.entries(actionNames)) {
    const row = document.createElement("div");
    row.className = "combo-row";
    const caption = document.createElement("label");
    caption.htmlFor = "combo-" + action + "-mode";
    caption.textContent = label;
    const mode = document.createElement("select");
    mode.id = "combo-" + action + "-mode";
    mode.setAttribute("aria-label", label + " behavior");
    for (const [value, text] of [
      ["preserve", "Preserve"],
      ["style", "NiriFX Style"],
      ["off", "Off"],
    ]) {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = text;
      mode.append(option);
    }
    mode.onchange = () => {
      const doc = profile();
      doc.actions[action] =
        mode.value === "style"
          ? { ...(remembered[action] || catalog.presets.balanced), resize: false }
          : mode.value === "off"
            ? "off"
            : null;
      select(doc, action, true);
    };
    const picker = document.createElement("select");
    picker.id = "combo-" + action;
    picker.setAttribute("aria-label", label + " style");
    const tune = document.createElement("button");
    tune.id = "combo-" + action + "-tune";
    tune.textContent = "Tune";
    tune.setAttribute("aria-label", "Customize " + label);
    tune.onclick = () => edit(action);
    picker.onchange = () => {
      const doc = profile(),
        id = picker.value;
      if (id === "custom") return;
      doc.actions[action] = id ? normalized(styles[id].effect) : null;
      select(doc, action, true);
    };
    row.append(caption, mode, picker, tune);
    element("combo-actions").append(row);
  }
  // Pointer wobble has its own native spring contract. It is profile metadata,
  // never an inferred fifth shader action or a timed preview.
  let pointerConsentValue = null;
  const pointerReady =
    catalog.connection?.target === "standalone" &&
    catalog.connection.pointer?.activation_ready === true &&
    catalog.connection.pointer?.target_supported === true;
  for (const [id, preset] of Object.entries(catalog.pointer_presets)) {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = preset.name;
    element("combo-pointer").append(option);
  }
  const pointerCustom = document.createElement("option");
  pointerCustom.value = "custom";
  pointerCustom.textContent = "Custom settings";
  element("combo-pointer").append(pointerCustom);
  const pointerKeys = ["strength", "damping", "frequency"];
  const pointerMatch = (settings) =>
    Object.entries(catalog.pointer_presets).find(([, preset]) =>
      pointerKeys.every((key) => preset.settings[key] === settings[key]),
    );
  function syncPointer(doc) {
    const settings = doc.pointer;
    if (settings?.strength > 0) rememberedPointer = { ...settings };
    element("combo-pointer-mode").value = !settings
      ? "preserve"
      : settings.strength === 0
        ? "off"
        : "style";
    element("combo-pointer").disabled = !settings || settings.strength === 0;
    const match = settings && pointerMatch(settings);
    element("combo-pointer").value = !settings
      ? ""
      : settings.strength === 0
        ? "disabled"
        : match?.[0] || "custom";
    element("pointer-description").textContent = !settings
      ? native
        ? sharedBase
          ? "Preserve whole-window wobble from your shared Niri configuration."
          : "Preserve whole-window wobble from this session's original saved baseline."
        : "Preserve the underlying desktop or shell whole-window wobble configuration."
      : settings.strength === 0
        ? "Disable whole-window wobble when these settings are applied."
        : match
          ? match[1].description
          : "Your custom spring response.";
    const movement = actionEffects(doc).movement;
    element("pointer-movement-note").hidden = !native || nativeOptions.variant !== "fragment";
    element("pointer-movement-note").textContent = element("pointer-movement-note").hidden
      ? ""
      : movement === "off"
        ? "Move is Off: fragment dragging and timed Move effects are disabled. Pointer wobble remains a separate choice."
        : (nativeSettings.fragment_preset
            ? "Your continuous fragments take priority over whole-window wobble. "
            : "When Move uses continuous fragments, they take priority over whole-window wobble. ") +
          "Pointer wobble Off does not stop those fragments. Set Move to Off to disable fragment dragging and timed Move effects.";
    for (const key of pointerKeys) {
      const input = element("pointer-" + key);
      input.min = catalog.pointer_limits[key][0];
      input.max = catalog.pointer_limits[key][1];
      input.value = (settings || catalog.pointer_defaults)[key];
      input.disabled = !settings || settings.strength === 0;
    }
    const summary = !settings
      ? "Preserve"
      : settings.strength === 0
        ? "Off"
        : match?.[1].name || "custom";
    element("editor-pointer-summary").textContent =
      "Pointer wobble: " + summary + ". Try it from the Library or Preview combo.";
    element("try-pointer").disabled = !settings || settings.strength <= 0;
    element("pointer-export-note").hidden = element("pointer-kdl").hidden =
      !settings && !doc.actions?.movement && !doc.actions?.swap;
    const consentValue = JSON.stringify(settings || null);
    if (pointerConsentValue !== consentValue) element("activate-pointer").checked = false;
    pointerConsentValue = consentValue;
    element("activate-pointer-label").hidden = !settings || !pointerReady;
    element("activate-pointer-text").textContent =
      settings?.strength === 0 ? "Apply pointer wobble disabled" : "Apply pointer wobble";
    return summary;
  }
  element("combo-pointer-mode").onchange = () => {
    const doc = profile(),
      mode = element("combo-pointer-mode").value;
    if (mode === "preserve") delete doc.pointer;
    else
      doc.pointer =
        mode === "off"
          ? { ...(doc.pointer || rememberedPointer || catalog.pointer_defaults), strength: 0 }
          : { ...(rememberedPointer || catalog.pointer_defaults) };
    select(core.normalizePreset(doc), "open");
  };
  element("combo-pointer").onchange = () => {
    const doc = profile(),
      id = element("combo-pointer").value;
    if (!id) delete doc.pointer;
    else if (id === "disabled")
      doc.pointer = { ...(doc.pointer || catalog.pointer_defaults), strength: 0 };
    else if (id === "custom") doc.pointer = { ...(doc.pointer || catalog.pointer_defaults) };
    else doc.pointer = { ...catalog.pointer_presets[id].settings };
    select(core.normalizePreset(doc), "open");
    element("pointer-tuning").open = id === "custom";
  };
  for (const key of pointerKeys)
    element("pointer-" + key).onchange = () => {
      const doc = profile();
      if (!doc.pointer) return;
      try {
        const value = element("pointer-" + key).value.trim();
        if (!value) throw new Error("Enter a value for " + key + ".");
        doc.pointer = core.normalizePointer({ ...doc.pointer, [key]: Number(value) });
        select(core.normalizePreset(doc), "open");
        element("error").textContent = "";
      } catch (error) {
        syncPointer(getDocument());
        element("error").textContent = error.message;
      }
    };
  element("edit-pointer").onclick = () => {
    view(false);
    element("combo-options").open = true;
    element("pointer-settings").scrollIntoView({ block: "nearest" });
    element(element("combo-pointer").disabled ? "combo-pointer-mode" : "combo-pointer").focus();
  };
  for (const [id, collection] of Object.entries(catalog.collections)) {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = collection.label;
    element("library-collection").append(option);
  }
  function cards() {
    const results = element("library-results"),
      scroll = results.scrollTop;
    const focused = results.contains(document.activeElement)
      ? { ...document.activeElement.dataset }
      : null;
    const group = element("library-collection").value,
      search = element("library-search").value.trim().toLowerCase(),
      entries =
        group === "customs"
          ? customs
          : group === "favorites"
            ? { ...builtins, ...customs }
            : builtins;
    const list = Object.entries(entries).filter(([id, doc]) => {
      if (browseAction === "combo") {
        if (!doc.actions && group !== "customs") return false;
      } else if (
        doc.actions ||
        (["resize", "movement", "swap"].includes(browseAction) &&
          !catalog.families[doc.effect.family][capabilityFor(browseAction)])
      )
        return false;
      const effects = Object.values(actionEffects(doc)).filter(isStyle),
        text = [doc.name, id, ...effects.map((effect) => effect.family)].join(" ").toLowerCase();
      if (search && !text.includes(search)) return false;
      if (search && group === "recommended") return true;
      if (group === "recommended" && ["movement", "swap"].includes(browseAction))
        return catalog.collections.movement.styles.includes(id);
      if (group === "recommended")
        return (
          Object.hasOwn(catalog.recommended_profiles, id) ||
          Object.hasOwn(catalog.recommended, id) ||
          Object.hasOwn(catalog.action_companions, id)
        );
      if (group === "favorites") return favorites().includes(id);
      return (
        !Object.hasOwn(catalog.collections, group) || catalog.collections[group].styles.includes(id)
      );
    });
    if (group === "recommended") {
      const order = Object.keys(catalog.recommended_profiles);
      list.sort(
        ([a], [b]) =>
          (order.includes(a) ? order.indexOf(a) : order.length) -
          (order.includes(b) ? order.indexOf(b) : order.length),
      );
    }
    // Keep fragments first across the full catalog; retain the curated ordering
    // inside other collections. Filtering never changes a user's current look.
    if (group === "all")
      list.sort(
        ([, a], [, b]) =>
          Number(actionEffects(b).open?.family === "fragments") -
          Number(actionEffects(a).open?.family === "fragments"),
      );
    element("library-results").replaceChildren();
    const continuous =
      browseAction === "movement" &&
      nativeOptions?.variant === "fragment" &&
      ["recommended", "all"].includes(group)
        ? Object.entries(fragmentChoices).filter(([id, choice]) =>
            [id, choice.name, "continuous fragments"].join(" ").toLowerCase().includes(search),
          )
        : [];
    element("library-empty").hidden = list.length + continuous.length > 0;
    element("library-warning").textContent = [...new Set(warnings)].join(" ");
    for (const [id, choice] of continuous) {
      const button = document.createElement("button");
      button.className = "library-look";
      button.dataset.fragment = id;
      button.setAttribute("aria-pressed", String(nativeSettings.fragment_preset === id));
      const name = document.createElement("strong");
      name.textContent = choice.name;
      const detail = document.createElement("small");
      detail.textContent = "Continuous fragments · " + choice.description;
      button.append(name, detail);
      button.onclick = () => chooseFragment(id);
      element("library-results").append(button);
    }
    for (const [id, doc] of list) {
      const button = document.createElement("button");
      button.className = "library-look";
      button.dataset.style = id;
      button.setAttribute(
        "aria-pressed",
        String(
          browseAction === "combo"
            ? sameDocument(doc, getDocument())
            : !(browseAction === "movement" && nativeSettings.fragment_preset) &&
                equal(actionEffects(getDocument())[browseAction], normalized(doc.effect)),
        ),
      );
      const name = document.createElement("strong");
      name.textContent = doc.name;
      const detail = document.createElement("small"),
        a = actionEffects(doc);
      detail.textContent = doc.actions
        ? `${isStyle(a.open) ? title(a.open.family) : title(actionMode(a.open))} → ${isStyle(a.close) ? title(a.close.family) : title(actionMode(a.close))} combo`
        : title(doc.effect.family) +
          (["movement", "swap"].includes(browseAction) ? " · Timed movement" : "");
      if (Object.hasOwn(catalog.recommended_profiles, id))
        detail.textContent += " · " + catalog.recommended_profiles[id];
      if (id.startsWith("custom-") && !Object.hasOwn(managed, id))
        detail.textContent += " · from shell";
      button.append(name, detail);
      button.onclick = () => {
        if (browseAction === "combo") select(core.normalizePreset(doc), "open", true);
        else {
          const chosen = profile();
          if (browseAction === "movement") nativeSettings.fragment_preset = null;
          chosen.actions[browseAction] = normalized(doc.effect);
          select(chosen, browseAction, true);
        }
      };
      const star = document.createElement("button");
      star.dataset.favorite = id;
      star.textContent = favorites().includes(id) ? "★" : "☆";
      star.setAttribute(
        "aria-label",
        (favorites().includes(id) ? "Remove favorite " : "Favorite ") + doc.name,
      );
      star.onclick = () => {
        favorite(id);
        cards();
      };
      const row = document.createElement("div");
      row.className = "combo-row";
      row.append(button, star);
      element("library-results").append(row);
    }
    const saved = selectedSaved();
    for (const id of ["copy-profile", "rename-profile", "remove-profile"])
      element(id).hidden = !saved;
    if (focused) {
      // Rebuilding cards must not strand keyboard users or jump a long catalog
      // back to its beginning after a selection or favorite changes.
      const key = ["style", "fragment", "favorite"].find((key) => focused[key]);
      if (key)
        [...results.querySelectorAll("button")]
          .find((button) => button.dataset[key] === focused[key])
          ?.focus({ preventScroll: true });
    }
    results.scrollTop = scroll;
  }
  function view(editor) {
    element("library-panel").hidden = editor;
    element("library-actions").hidden = editor;
    element("editor-panel").hidden = !editor;
    element("show-library").setAttribute("aria-pressed", String(!editor));
    element("show-editor").setAttribute("aria-pressed", String(editor));
    document.documentElement.dataset.workspace = editor ? "editor" : "library";
  }
  element("show-library").onclick = () => {
    view(false);
    sync();
  };
  element("show-editor").onclick = () => view(true);
  element("library-search").oninput = cards;
  element("library-collection").onchange = () => {
    if (element("library-collection").value === "customs") browseAction = "combo";
    syncBrowse();
    cards();
  };
  function sameStyle() {
    const doc = profile(),
      chosen = element("combo-same").value,
      effect = Object.hasOwn(styles, chosen)
        ? normalized(styles[chosen].effect)
        : Object.values(doc.actions).find(isStyle) || normalized(catalog.presets.balanced);
    const unsupported = [];
    for (const action of Object.keys(actionNames)) {
      if (!isStyle(doc.actions[action])) continue;
      if (
        ["resize", "movement", "swap"].includes(action) &&
        !catalog.families[effect.family][capabilityFor(action)]
      ) {
        unsupported.push(actionNames[action]);
        continue;
      }
      doc.actions[action] = { ...effect };
    }
    select(doc, "open", true);
    if (unsupported.length)
      element("status").textContent =
        `${title(effect.family)} does not support ${unsupported.join(" and ")}. Their selected styles were kept.`;
  }
  element("combo-same").onchange = sameStyle;
  element("combo-mode").onchange = () => {
    if (element("combo-mode").value === "same") sameStyle();
    else element("combo-same").disabled = true;
  };
  element("combo-name").onchange = () => {
    const doc = getDocument();
    try {
      select(core.normalizePreset({ ...doc, name: element("combo-name").value.trim() }), "open");
      element("error").textContent = "";
    } catch (error) {
      element("combo-name").value = doc.name;
      element("error").textContent = error.message;
    }
  };
  function invalidate() {
    revision++;
    review = null;
    element("apply-review").hidden = true;
  }
  function sync() {
    invalidate();
    const doc = getDocument(),
      actions = actionEffects(doc),
      selectedStyles = Object.values(actions).filter(isStyle),
      sharedStyle = selectedStyles[0] || remembered.open || normalized(catalog.presets.balanced),
      same = selectedStyles.every((effect) => equal(sharedStyle, effect));
    if (
      nativeSettings.fragment_preset &&
      !equal(actions.movement, fragmentChoices[nativeSettings.fragment_preset]?.effect)
    )
      nativeSettings.fragment_preset = null;
    const fragmentPreset = nativeSettings.fragment_preset;
    element("native-fragment-preset").value = fragmentPreset || "";
    element("native-fragment-description").textContent = fragmentPreset
      ? fragmentChoices[fragmentPreset].description +
        " The canvas previews its material only; the continuous response runs on your NiriFX desktop."
      : "Preserve keeps the base movement. A movement Style uses its timed effect; Off disables movement animation. Choosing a continuous preset explicitly replaces the movement style. Editing that style clears the continuous preset.";
    element("selection-name").textContent = doc.name;
    element("selection-actions").textContent =
      Object.entries(actionNames)
        .map(
          ([action, label]) =>
            label +
            ": " +
            (isStyle(actions[action])
              ? "NiriFX Style · " +
                title(
                  Object.keys(styles).find((id) =>
                    equal(normalized(styles[id].effect), actions[action]),
                  ) || actions[action].family,
                )
              : title(actionMode(actions[action]))),
        )
        .join(" · ") +
      " · Pointer wobble: " +
      syncPointer(doc);
    element("combo-name").value = doc.name;
    element("combo-mode").value = same ? "same" : "mixed";
    selectOptions(element("combo-same"), "open", sharedStyle);
    element("combo-same").disabled = !same;
    for (const action of Object.keys(actionNames)) {
      const value = actions[action],
        style = isStyle(value);
      if (style) remembered[action] = { ...value };
      element("combo-" + action + "-mode").value = actionMode(value);
      selectOptions(element("combo-" + action), action, style ? value : remembered[action]);
      element("combo-" + action).disabled = !style;
      element("combo-" + action + "-tune").disabled = !style;
    }
    syncBrowse();
    cards();
  }
  async function post(path, body) {
    const response = await fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-NiriFX-Token": catalog.connection.token,
      },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    return data;
  }
  async function listing() {
    if (!catalog.connection) {
      managed = Object.fromEntries(
        Object.entries(customs).map(([id, document]) => [
          id,
          { document, expected: JSON.stringify(document) },
        ]),
      );
      cards();
      return;
    }
    const response = await fetch("/library?token=" + encodeURIComponent(catalog.connection.token));
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    customs = data.customs;
    managed = data.managed;
    warnings = data.warnings;
    element("restore-selection").disabled = !data.restore;
    element("active-look").textContent = (native ? "Next login: " : "Active: ") + data.active_name;
    if (native) {
      nativeListing = data.native;
      nativeRestoreAvailable = data.restore;
      const live = nativeListing.live;
      element("native-session-help").textContent = sharedSelectionChanged()
        ? "Your selected setup changed. Save or export any draft edits, then close and reopen Studio to continue with that setup."
        : sharedBase
          ? "Normal Niri settings are shared with this setup. Sessions already using the shared files reload them automatically; other NiriFX sessions use them at the next login."
          : live?.ready
            ? "Apply your choices directly to this desktop and keep them for your next NiriFX login."
            : "Choose your effects here and select them for your next NiriFX login.";
      element("review-selection").textContent =
        sharedBase || live?.ready ? "Review & apply" : "Review next login";
      const selection = nativeListing.selection;
      element("native-base").textContent = sharedBase
        ? "Editing shared settings. Preserve follows your normal Niri configuration beneath the NiriFX effects."
        : "Editing bundle: " +
          nativeListing.base_bundle +
          ". Preserve inherits original baseline " +
          nativeListing.baseline_bundle +
          ".";
      element("native-selected").textContent =
        "Next login: " + sessionName(selection.selected, "Stock Niri");
      element("native-rollback").textContent =
        "Retained rollback: " +
        (Object.hasOwn(selection, "previous")
          ? sessionName(selection.previous, "Stock Niri")
          : "No previous selection");
      const running = nativeListing.running;
      element("native-running").textContent =
        "Running: " +
        (running.status === "matched"
          ? sharedBase
            ? "NiriFX; loaded effects not independently confirmed"
            : live && !live.ready
              ? "NiriFX; effects not confirmed"
              : sessionName(live?.loaded_bundle || running.bundle_id, "NiriFX session")
          : running.status === "external"
            ? "Another Niri session"
            : running.status === "offline"
              ? "No session detected"
              : "Not verified");
      element("native-running-detail").textContent =
        "Advertised running session: " +
        running.status +
        (running.bundle_id ? " · " + running.bundle_id : "") +
        ". " +
        running.detail +
        (live?.detail ? " " + live.detail : "");
      element("native-bundles").textContent =
        "Next-login bundle: " +
        (selection.selected || "None") +
        ". Retained rollback bundle: " +
        (Object.hasOwn(selection, "previous") ? selection.previous || "None" : "No history") +
        ".";
      element("native-reopen").disabled = !nativeListing.reopen;
      element("native-reopen-note").textContent = nativeListing.reopen
        ? "Reopen the saved choices without selecting or activating them."
        : nativeListing.recipe
          ? "This recipe uses another baseline. Relaunch Studio with that bundle as --native-base to edit it."
          : "This bundle has no editable recipe. Preserve keeps its existing configuration.";
      const selectedShared = nativeListing.shared_state?.selected === true;
      element("native-share").hidden = !nativeOptions.shared_config_configured || selectedShared;
      element("native-recovery").hidden = !nativeListing.recovery_available;
      element("native-shared-settings").hidden =
        !nativeOptions.shared_config_configured && !sharedBase && !selectedShared;
      element("native-shared-help").textContent = selectedShared
        ? "Normal Niri settings stay in their original files. NiriFX manages separate effect files. Frozen recovery selects a saved configuration for the next login without undoing your normal settings."
        : nativeListing.recipe
          ? "Share the selected saved settings with your normal Niri configuration. Review the connected files first. Your unsaved Studio draft is not used or changed."
          : "Choose your effects and apply them first, then share the saved settings. Your unsaved Studio draft is not used for sharing.";
      updateNativeButtons();
    }
    cards();
  }
  function updateNativeButtons() {
    if (!native || !nativeListing) return;
    const changed = sharedSelectionChanged();
    element("review-selection").disabled = busy || changed;
    element("restore-selection").disabled = busy || changed || !nativeRestoreAvailable;
    element("apply-selection").disabled = busy || (changed && !review?.recovery);
    element("native-reopen").disabled = busy || changed || !nativeListing.reopen;
    element("native-share").disabled =
      busy || changed || !nativeListing.recipe || element("native-share").hidden;
    element("native-recovery").disabled = busy || element("native-recovery").hidden;
  }
  async function operation(work) {
    if (busy) return;
    busy = true;
    element("library-actions").inert =
      element("library-panel").inert =
      element("editor-panel").inert =
        true;
    element("error").textContent = "";
    for (const id of [
      "review-selection",
      "store-profile",
      "copy-profile",
      "rename-profile",
      "remove-profile",
      "restore-selection",
      "apply-selection",
      "native-reopen",
      "native-share",
      "native-recovery",
    ])
      element(id).disabled = true;
    try {
      await work();
    } catch (error) {
      if (native) invalidate();
      element("error").textContent = error.message;
    } finally {
      await listing().catch((error) => {
        element("error").textContent = error.message;
      });
      busy = false;
      element("library-actions").inert =
        element("library-panel").inert =
        element("editor-panel").inert =
          false;
      element("review-selection").disabled =
        element("store-profile").disabled =
        element("copy-profile").disabled =
        element("rename-profile").disabled =
        element("remove-profile").disabled =
        element("apply-selection").disabled =
          false;
      updateNativeButtons();
    }
  }
  element("review-selection").onclick = () =>
    operation(async () => {
      const reviewedRevision = revision;
      const doc = core.normalizePreset(getDocument()),
        actions = actionEffects(doc);
      const selection = native
        ? {
            document: doc,
            fragment_preset: nativeSettings.fragment_preset,
          }
        : {
            document: doc,
            allow_resize: !!actions.resize,
            allow_movement:
              !!actions.movement &&
              catalog.connection.target === "standalone" &&
              element("activate-movement").checked,
            allow_pointer: !!doc.pointer && pointerReady && element("activate-pointer").checked,
          };
      const plan = await post("/review", selection);
      if (revision !== reviewedRevision)
        throw new Error("Selection changed. Review again before applying.");
      review = { selection, expected: plan.plan_sha256 };
      showReview(
        plan,
        (native && plan.activation === "config-written"
          ? "Update shared settings: "
          : native && plan.activation !== "live-and-next-login"
            ? "Select for next login: "
            : "Apply ") +
          doc.name +
          ". ",
      );
    });
  function showReview(plan, message) {
    const live = native && plan.activation === "live-and-next-login";
    const shared = native && plan.activation === "config-written";
    element("apply-selection").textContent = native
      ? shared
        ? "Apply shared settings"
        : live
          ? "Apply to desktop"
          : "Select for next login"
      : "Apply these changes";
    element("review-summary").textContent =
      message +
      (native
        ? shared
          ? "Update the shared configuration files. Sessions already using these files reload automatically; other NiriFX sessions use them at the next login. Studio cannot independently confirm what the running desktop loaded."
          : live
            ? "Update this desktop and your next NiriFX login. Your previous selection stays available for rollback."
            : "Your current desktop stays unchanged. The previous selection stays available for rollback."
        : plan.notes.join(" "));
    element("review-file-details").open = !native || shared;
    element("review-notes").hidden = !native;
    element("review-notes").textContent = native ? plan.notes.join(" ") : "";
    element("review-files").replaceChildren();
    for (const file of plan.changes) {
      const row = document.createElement("li");
      row.textContent = file.action + ": " + file.path;
      element("review-files").append(row);
    }
    if (!plan.changes.length && !live)
      element("review-summary").textContent = shared
        ? "Shared configuration files already match these choices. Running settings have not been independently confirmed."
        : native
          ? "This next-login selection is already stored. The running session stays unchanged."
          : "This look is already applied.";
    element("apply-review").hidden = false;
    element("apply-review").scrollIntoView({ block: "nearest" });
  }
  function nativeResultMessage(result, { adopted, recovered }) {
    if (recovered)
      return "Selected frozen recovery for your next NiriFX login. Normal Niri settings were not changed. Save any draft edits, then close and reopen Studio.";
    if (adopted)
      return "Shared saved configuration files updated. Sessions already using these files reload automatically; other NiriFX sessions use them at the next login. The running desktop has not been independently confirmed. Your draft is unchanged. Save or export it, then close and reopen Studio.";
    if (result.activation === "config-written")
      return "Updated shared configuration files. Sessions already using these files reload automatically; other NiriFX sessions use them at the next login. The running desktop has not been independently confirmed.";
    if (result.live?.status === "applied")
      return "Applied to this desktop and saved for your next NiriFX login.";
    if (result.live && ["failed", "unconfirmed", "unavailable"].includes(result.live.status))
      return "Saved for next login. The desktop update was not confirmed. " + result.live.detail;
    return result.selection?.selected === null
      ? "No managed version is selected. Your current session stays unchanged. Choose stock Niri at the next login."
      : "Selected for next login. Your current session stays unchanged. Log out when ready and choose NiriFX.";
  }
  element("apply-selection").onclick = () =>
    operation(async () => {
      if (!review) throw new Error("Review the current selection first");
      const adopted = review.shared,
        recovered = review.recovery;
      const result = adopted
        ? await post("/shared-apply", { expected: review.expected })
        : recovered
          ? await post("/recovery-apply", { expected: review.expected })
          : review.rollback
            ? await post("/rollback-apply", { expected: review.expected })
            : await post("/apply", review);
      if (adopted || recovered) nativeSetupChanged = true;
      invalidate();
      element("status").textContent = native
        ? nativeResultMessage(result, { adopted, recovered })
        : "Applied. Use Restore previous to return to your earlier settings.";
    });
  element("cancel-review").onclick = invalidate;
  element("native-share").onclick = () =>
    operation(async () => {
      const reviewedRevision = revision;
      const plan = await post("/shared-review", {});
      if (revision !== reviewedRevision)
        throw new Error("Selection changed. Review sharing again.");
      review = { shared: true, expected: plan.plan_sha256 };
      showReview(plan, "Share saved settings. Your unsaved Studio draft is not used or changed. ");
    });
  element("native-recovery").onclick = () =>
    operation(async () => {
      const reviewedRevision = revision;
      const plan = await post("/recovery-review", {});
      if (revision !== reviewedRevision)
        throw new Error("Selection changed. Review recovery again.");
      review = { recovery: true, expected: plan.plan_sha256 };
      showReview(
        plan,
        "Select frozen recovery for the next login. Your normal Niri settings and unsaved Studio draft stay unchanged. ",
      );
    });
  function suggestedCopy(name) {
    for (let index = 1; ; index++) {
      const suffix = " copy" + (index > 1 ? " " + index : "");
      const candidate = name.slice(0, 48 - suffix.length).trimEnd() + suffix;
      if (!Object.hasOwn(customs, profileId(candidate))) return candidate;
    }
  }
  function profileDialog(action) {
    if (busy) return;
    const saved = selectedSaved();
    if (["rename", "remove"].includes(action) && !saved) return;
    let document;
    try {
      document = core.normalizePreset(getDocument());
    } catch (error) {
      element("error").textContent = error.message;
      return;
    }
    pendingProfile = { action, document, saved, entries: structuredClone(managed) };
    const input = element("profile-save-name");
    input.value = action === "copy" ? suggestedCopy(document.name) : document.name;
    input.required = action !== "remove";
    element("profile-dialog-name").hidden = action === "remove";
    element("profile-dialog-error").textContent = "";
    updateProfileDialog();
    element("profile-dialog").showModal();
    if (action !== "remove") input.select();
  }
  function updateProfileDialog() {
    const { action, document, entries } = pendingProfile;
    const exists = Object.hasOwn(entries, profileId(element("profile-save-name").value.trim()));
    element("profile-dialog-title").textContent =
      action === "remove"
        ? "Remove " + document.name + "?"
        : action === "rename"
          ? "Rename saved profile"
          : action === "copy"
            ? "Save a copy"
            : "Save to My profiles";
    element("profile-confirm").textContent =
      action === "remove"
        ? "Remove from My profiles"
        : action === "rename"
          ? "Rename profile"
          : exists && action === "save"
            ? "Replace saved profile"
            : "Save profile";
    element("profile-dialog-help").textContent =
      action === "remove"
        ? "This removes the Library copy only. Your active effects and shell presets stay available. Export JSON first if you want to keep a copy."
        : action === "rename"
          ? "Rename this Library copy. Your active effects and shell presets keep their current names."
          : exists && action === "save"
            ? "A saved profile already uses this name. Replacing it updates the Library copy only; your active effects stay the same."
            : "Keep an editable Library copy. Your active effects stay the same.";
    if (native && nativeSettings.fragment_preset && ["save", "copy"].includes(action))
      element("profile-dialog-help").textContent +=
        " My profiles and exported JSON keep the portable styles, but exclude continuous fragment response. Select for next login retains that response in the session recipe.";
  }
  for (const [id, action] of Object.entries({
    "store-profile": "save",
    "copy-profile": "copy",
    "rename-profile": "rename",
    "remove-profile": "remove",
  }))
    element(id).onclick = () => profileDialog(action);
  element("profile-save-name").oninput = () => {
    element("profile-dialog-error").textContent = "";
    updateProfileDialog();
  };
  element("profile-cancel").onclick = () => element("profile-dialog").close();
  element("profile-dialog").onclose = () => {
    // Browsers queue close events. A previous dialog may finish closing after
    // another operation has opened; preserve that new operation's context.
    if (!element("profile-dialog").open) pendingProfile = null;
  };
  element("profile-form").onsubmit = (event) => {
    event.preventDefault();
    const input = element("profile-save-name");
    operation(async () => {
      element("profile-confirm").disabled = true;
      try {
        const { action, document: original, saved, entries } = pendingProfile;
        const document =
          action === "remove"
            ? original
            : core.normalizePreset({ ...original, name: input.value.trim() });
        const id = profileId(document.name),
          previous = entries[id];
        if ((action === "copy" || (action === "rename" && id !== saved[0])) && previous)
          throw new Error("That name already belongs to a saved profile. Choose another.");
        if (catalog.connection) {
          if (["rename", "remove"].includes(action))
            await post("/profiles", {
              action,
              id: saved[0],
              expected: saved[1].expected,
              ...(action === "rename" ? { name: document.name } : {}),
            });
          else await post("/store", { document, expected: previous?.expected ?? null });
        } else {
          // Read again before writing so another tab's newer profiles survive.
          // Only the selected name is replaced, renamed or removed.
          const next = JSON.parse(localStorage.getItem("nirifx-my-profiles") || "{}");
          if (!next || typeof next !== "object" || Array.isArray(next))
            throw new Error(
              "Browser profiles could not be read. Export JSON before clearing browser storage.",
            );
          const sourceId = saved && ["rename", "remove"].includes(action) ? saved[0] : id;
          const expected =
            saved && ["rename", "remove"].includes(action)
              ? saved[1].expected
              : (previous?.expected ?? null);
          const observed = Object.hasOwn(next, sourceId)
            ? JSON.stringify(core.normalizePreset(next[sourceId]))
            : null;
          if (
            observed !== expected ||
            (action === "rename" && id !== sourceId && Object.hasOwn(next, id))
          )
            throw new Error("Saved profile changed in another tab. Reload before trying again.");
          if (
            !Object.hasOwn(next, id) &&
            action !== "remove" &&
            action !== "rename" &&
            Object.keys(next).length >= 100
          )
            throw new Error("My profiles is full. Remove a profile or export JSON.");
          if (["remove", "rename"].includes(action)) delete next[sourceId];
          if (action !== "remove") next[id] = document;
          localStorage.setItem("nirifx-my-profiles", JSON.stringify(next));
          readBrowserProfiles();
        }
        if (saved && ["rename", "remove"].includes(action) && favorites().includes(saved[0]))
          favorite(saved[0], action === "rename" ? id : null);
        element("profile-dialog").close();
        if (action !== "remove") select(document, "open");
        element("status").textContent =
          (action === "remove" ? "Removed " : action === "rename" ? "Renamed to " : "Saved ") +
          document.name +
          ". Your active look stays the same.";
      } catch (error) {
        element("profile-dialog-error").textContent = error.message;
      } finally {
        element("profile-confirm").disabled = false;
      }
    });
  };
  element("restore-selection").onclick = () =>
    operation(async () => {
      if (native) {
        const reviewedRevision = revision;
        const plan = await post("/rollback-review", {});
        if (revision !== reviewedRevision)
          throw new Error("Selection changed. Review rollback again.");
        review = { rollback: true, expected: plan.plan_sha256 };
        showReview(
          plan,
          plan.activation === "config-written"
            ? "Restore shared effects. "
            : plan.activation === "live-and-next-login"
              ? "Restore your previous effects. "
              : "Restore the previous next-login selection. ",
        );
        return;
      }
      await post("/restore", {});
      invalidate();
      element("status").textContent = "Restored previous settings.";
    });
  element("native-reopen").onclick = () => {
    if (busy || !nativeListing?.reopen) return;
    nativeSettings.fragment_preset = nativeListing.recipe.fragment_preset;
    select(nativeListing.recipe.document, "open");
    element("status").textContent =
      "Reopened your saved choices. Review any edits before applying them.";
  };
  element("native-session").hidden = !native;
  if (native) {
    element("active-look").hidden = true;
    element("review-selection").textContent = sharedBase ? "Review & apply" : "Review next login";
    element("restore-selection").textContent = "Review rollback";
    element("apply-selection").textContent = sharedBase
      ? "Apply shared settings"
      : "Select for next login";
    element("native-reopen").textContent = "Reopen saved choices";
    document.querySelector('[data-mode="movement"] small').textContent = "shader preview";
    element("pointer-kdl").textContent = "Export NiriFX session config";
  }
  element("movement-availability").textContent = native
    ? "Move controls normal movement and dragging. Swap overrides explicit left/right window swaps. Continuous fragments follow your gestures on the desktop; the canvas previews their material only."
    : catalog.connection?.target === "standalone"
      ? "Movement can be designed here. Applying it requires a matching NiriFX session with action-preservation support and verified running support."
      : catalog.connection
        ? "Movement can be designed and saved here. This integration applies selected opening, closing and resize overrides only."
        : "Preview movement and save it in JSON. Stock Niri config exports include selected opening, closing and resize overrides only.";
  element("activation-controls").hidden = !catalog.connection;
  element("activate-movement-label").hidden = catalog.connection?.target !== "standalone";
  element("activate-movement").onchange = invalidate;
  element("activate-pointer").onchange = invalidate;
  element("pointer-availability").textContent = !catalog.connection
    ? "Save pointer settings here, then use the local app with a verified pointer-enabled compositor to apply them."
    : native
      ? "Pointer wobble choices are validated against your NiriFX build. Review shows whether they can be applied to this desktop or saved for your next login."
      : pointerReady
        ? "This running compositor supports pointer wobble. Select settings, then explicitly enable them in Review & apply."
        : catalog.connection.pointer?.target_detail ||
          "Pointer activation requires the standalone target and a verified running pointer extension. These settings can still be saved and exported.";
  view(
    catalog.connection?.view === "editor" ||
      !!location.hash ||
      new URLSearchParams(location.search).has("preset"),
  );
  sync();
  listing().catch((error) => {
    element("error").textContent = error.message;
  });
  return { sync, edit: () => view(true) };
}
