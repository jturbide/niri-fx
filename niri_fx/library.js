// Library-first presentation over the same validated documents as Studio.
// Selecting a card changes only the preview. Review and Apply are separate,
// and optional actions are never inferred from a family capability.
function createFxLibrary({ catalog, getDocument, select, edit, favorites, favorite }) {
  const element = (id) => document.getElementById(id);
  const core = createEffectCore(catalog);
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
  const actionNames = { open: "Open", close: "Close", resize: "Resize", movement: "Move / swap" };
  let customs = {},
    managed = {},
    warnings = [],
    pendingProfile = null,
    review = null,
    busy = false,
    revision = 0;
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
  const normalized = (effect) => ({ ...effect, resize: false });
  const equal = (a, b) =>
    !!a && !!b && Object.keys(catalog.defaults).every((key) => a[key] === b[key]);
  const actionEffects = (doc) =>
    doc.actions || {
      open: normalized(doc.effect),
      close: normalized(doc.effect),
      resize: doc.effect.resize ? normalized(doc.effect) : null,
      movement: null,
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
  function selectOptions(select, action, effect) {
    const option = (value, text) => {
      const node = document.createElement("option");
      node.value = value;
      node.textContent = text;
      select.append(node);
    };
    if (!select.options.length) {
      option(
        "",
        ["resize", "movement"].includes(action) ? "Use shell defaults" : "Custom settings",
      );
      for (const [id, doc] of Object.entries(styles))
        if (["open", "close"].includes(action) || catalog.families[doc.effect.family][action])
          option(id, doc.name);
    }
    select.querySelector('[value="custom"]')?.remove();
    const match = Object.keys(styles).find((id) => equal(normalized(styles[id].effect), effect));
    if (effect && !match) {
      const combo = Object.values(catalog.profiles).find((doc) =>
        equal(doc.actions[action], effect),
      );
      option("custom", combo ? combo.name + " · " + actionNames[action] : "Custom settings");
    }
    select.value = match || (effect ? "custom" : "");
  }
  for (const [action, label] of Object.entries(actionNames)) {
    const row = document.createElement("div");
    row.className = "combo-row";
    const caption = document.createElement("label");
    caption.htmlFor = "combo-" + action;
    caption.textContent = label + (["resize", "movement"].includes(action) ? " (optional)" : "");
    const picker = document.createElement("select");
    picker.id = "combo-" + action;
    const tune = document.createElement("button");
    tune.textContent = "Tune";
    tune.setAttribute("aria-label", "Customize " + label);
    tune.onclick = () => edit(action);
    picker.onchange = () => {
      const doc = profile(),
        id = picker.value;
      if (id === "custom" || (!id && ["open", "close"].includes(action))) return;
      doc.actions[action] = id ? normalized(styles[id].effect) : null;
      select(doc, action);
    };
    row.append(caption, picker, tune);
    element("combo-actions").append(row);
  }
  // Pointer drag has its own native spring contract. It is profile metadata,
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
    const match = settings && pointerMatch(settings);
    element("combo-pointer").value = !settings
      ? ""
      : settings.strength === 0
        ? "disabled"
        : match?.[0] || "custom";
    element("pointer-description").textContent = !settings
      ? "Keep the desktop's current pointer behavior."
      : settings.strength === 0
        ? "Explicitly disable pointer deformation when these settings are applied."
        : match
          ? match[1].description
          : "Your custom spring response.";
    for (const key of pointerKeys) {
      const input = element("pointer-" + key);
      input.min = catalog.pointer_limits[key][0];
      input.max = catalog.pointer_limits[key][1];
      input.value = (settings || catalog.pointer_defaults)[key];
      input.disabled = !settings;
    }
    const summary = !settings
      ? "desktop settings"
      : settings.strength === 0
        ? "disabled"
        : match?.[1].name || "custom";
    element("editor-pointer-summary").textContent =
      "Pointer drag: " + summary + ". Try it from the Library or Preview combo.";
    element("try-pointer").disabled = !settings || settings.strength <= 0;
    element("pointer-export-note").hidden = element("pointer-kdl").hidden = !settings;
    const consentValue = JSON.stringify(settings || null);
    if (pointerConsentValue !== consentValue) element("activate-pointer").checked = false;
    pointerConsentValue = consentValue;
    element("activate-pointer-label").hidden = !settings || !pointerReady;
    element("activate-pointer-text").textContent =
      settings?.strength === 0 ? "Apply pointer drag disabled" : "Apply experimental pointer drag";
    return summary;
  }
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
    element("pointer-settings").scrollIntoView({ block: "nearest" });
    element("combo-pointer").focus();
  };
  for (const [id, collection] of Object.entries(catalog.collections)) {
    const option = document.createElement("option");
    option.value = id;
    option.textContent = collection.label;
    element("library-collection").append(option);
  }
  function cards() {
    const group = element("library-collection").value,
      search = element("library-search").value.trim().toLowerCase(),
      entries =
        group === "customs"
          ? customs
          : group === "favorites"
            ? { ...builtins, ...customs }
            : builtins;
    const list = Object.entries(entries).filter(([id, doc]) => {
      const effects = Object.values(actionEffects(doc)).filter(Boolean),
        text = [doc.name, id, ...effects.map((effect) => effect.family)].join(" ").toLowerCase();
      if (search && !text.includes(search)) return false;
      if (search && group === "recommended") return true;
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
          Number(actionEffects(b).open.family === "fragments") -
          Number(actionEffects(a).open.family === "fragments"),
      );
    element("library-results").replaceChildren();
    element("library-empty").hidden = list.length > 0;
    element("library-warning").textContent = [...new Set(warnings)].join(" ");
    for (const [id, doc] of list) {
      const button = document.createElement("button");
      button.className = "library-look";
      button.dataset.style = id;
      button.setAttribute(
        "aria-pressed",
        String(JSON.stringify(doc) === JSON.stringify(getDocument())),
      );
      const name = document.createElement("strong");
      name.textContent = doc.name;
      const detail = document.createElement("small"),
        a = actionEffects(doc);
      detail.textContent = doc.actions
        ? `${title(a.open.family)} → ${title(a.close.family)} combo`
        : title(doc.effect.family);
      if (Object.hasOwn(catalog.recommended_profiles, id))
        detail.textContent += " · " + catalog.recommended_profiles[id];
      if (id.startsWith("custom-") && !Object.hasOwn(managed, id))
        detail.textContent += " · from shell";
      button.append(name, detail);
      button.onclick = () => select(core.normalizePreset(doc), "open");
      const star = document.createElement("button");
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
  }
  function view(editor) {
    element("library-panel").hidden = editor;
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
  element("library-search").oninput = element("library-collection").onchange = cards;
  function sameStyle() {
    const doc = profile(),
      chosen = element("combo-same").value,
      effect = Object.hasOwn(styles, chosen) ? normalized(styles[chosen].effect) : doc.actions.open;
    const unsupported = [];
    for (const action of Object.keys(actionNames)) {
      if (["open", "close"].includes(action)) doc.actions[action] = { ...effect };
      else if (doc.actions[action]) {
        if (!catalog.families[effect.family][action]) unsupported.push(actionNames[action]);
        doc.actions[action] = catalog.families[effect.family][action] ? { ...effect } : null;
      }
    }
    select(doc, "open");
    if (unsupported.length)
      element("status").textContent =
        `${title(effect.family)} does not support ${unsupported.join(" and ")}. Those actions use shell defaults.`;
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
      same = Object.values(actions)
        .filter(Boolean)
        .every((effect) => equal(actions.open, effect));
    element("selection-name").textContent = doc.name;
    element("selection-actions").textContent =
      Object.entries(actionNames)
        .map(
          ([action, label]) =>
            label +
            ": " +
            (actions[action]
              ? title(
                  Object.keys(styles).find((id) =>
                    equal(normalized(styles[id].effect), actions[action]),
                  ) || actions[action].family,
                )
              : "shell default"),
        )
        .join(" · ") +
      " · Pointer drag: " +
      syncPointer(doc);
    element("combo-name").value = doc.name;
    element("combo-mode").value = same ? "same" : "mixed";
    selectOptions(element("combo-same"), "open", actions.open);
    element("combo-same").disabled = !same;
    for (const action of Object.keys(actionNames))
      selectOptions(element("combo-" + action), action, actions[action]);
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
    element("active-look").textContent = "Active: " + data.active_name;
    cards();
  }
  async function operation(work) {
    if (busy) return;
    busy = true;
    element("library-panel").inert = element("editor-panel").inert = true;
    element("error").textContent = "";
    for (const id of [
      "review-selection",
      "store-profile",
      "copy-profile",
      "rename-profile",
      "remove-profile",
      "restore-selection",
      "apply-selection",
    ])
      element(id).disabled = true;
    try {
      await work();
    } catch (error) {
      element("error").textContent = error.message;
    } finally {
      await listing().catch((error) => {
        element("error").textContent = error.message;
      });
      busy = false;
      element("library-panel").inert = element("editor-panel").inert = false;
      element("review-selection").disabled =
        element("store-profile").disabled =
        element("copy-profile").disabled =
        element("rename-profile").disabled =
        element("remove-profile").disabled =
        element("apply-selection").disabled =
          false;
    }
  }
  element("review-selection").onclick = () =>
    operation(async () => {
      const reviewedRevision = revision;
      const doc = core.normalizePreset(getDocument()),
        actions = actionEffects(doc);
      const selection = {
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
      element("review-summary").textContent = "Apply " + doc.name + ". " + plan.notes.join(" ");
      element("review-files").replaceChildren();
      for (const file of plan.changes) {
        const row = document.createElement("li");
        row.textContent = file.action + ": " + file.path;
        element("review-files").append(row);
      }
      if (!plan.changes.length)
        element("review-summary").textContent = "This look is already applied.";
      element("apply-review").hidden = false;
    });
  element("apply-selection").onclick = () =>
    operation(async () => {
      if (!review) throw new Error("Review the current selection first");
      await post("/apply", review);
      invalidate();
      element("status").textContent =
        "Applied. Use Restore previous to return to your earlier settings.";
    });
  element("cancel-review").onclick = invalidate;
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
      await post("/restore", {});
      invalidate();
      element("status").textContent = "Restored previous settings.";
    });
  element("movement-availability").textContent =
    catalog.connection?.target === "standalone"
      ? "Movement can be designed here. Applying it requires an explicitly selected experimental compositor and verified running support."
      : catalog.connection
        ? "Movement can be designed and saved here. This integration applies opening, closing and enabled resize only."
        : "Preview movement and save it in JSON. Stock Niri config exports include opening, closing and enabled resize only.";
  element("activation-controls").hidden = !catalog.connection;
  element("activate-movement-label").hidden = catalog.connection?.target !== "standalone";
  element("activate-movement").onchange = invalidate;
  element("activate-pointer").onchange = invalidate;
  element("pointer-availability").textContent = !catalog.connection
    ? "Save pointer settings here, then use the local app with a verified pointer-enabled compositor to apply them."
    : pointerReady
      ? "This running compositor supports pointer drag. Select settings, then explicitly enable them in Review & apply."
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
