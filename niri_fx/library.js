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
    review = null,
    busy = false,
    revision = 0;
  if (!catalog.connection) {
    try {
      const saved = JSON.parse(localStorage.getItem("nirifx-my-profiles") || "{}");
      for (const [id, doc] of Object.entries(saved).slice(0, 100))
        if (/^custom-[a-z0-9-]+$/.test(id)) customs[id] = core.normalizePreset(doc);
    } catch {
      /* Imports and JSON exports remain available without browser storage. */
    }
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
      ...(doc.motion ? { motion: doc.motion } : {}),
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
    if (effect && !match && ["resize", "movement"].includes(action))
      option("custom", "Custom settings");
    select.value = match || (effect && ["resize", "movement"].includes(action) ? "custom" : "");
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
          Object.hasOwn(catalog.recommended, id) || Object.hasOwn(catalog.action_companions, id)
        );
      if (group === "favorites") return favorites().includes(id);
      return (
        !Object.hasOwn(catalog.collections, group) || catalog.collections[group].styles.includes(id)
      );
    });
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
      effect = chosen ? normalized(styles[chosen].effect) : doc.actions.open;
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
    doc.name = element("combo-name").value.trim();
    select(doc, "open");
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
    element("selection-actions").textContent = Object.entries(actionNames)
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
      .join(" · ");
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
    if (!catalog.connection) return;
    const response = await fetch("/library?token=" + encodeURIComponent(catalog.connection.token));
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    customs = data.customs;
    element("restore-selection").disabled = !data.restore;
    element("active-look").textContent = "Active: " + data.active_name;
    cards();
  }
  async function operation(work) {
    if (busy) return;
    busy = true;
    element("library-panel").inert = element("editor-panel").inert = true;
    element("error").textContent = "";
    for (const id of ["review-selection", "store-profile", "restore-selection", "apply-selection"])
      element(id).disabled = true;
    try {
      await work();
    } catch (error) {
      element("error").textContent = error.message;
    } finally {
      busy = false;
      element("library-panel").inert = element("editor-panel").inert = false;
      element("review-selection").disabled =
        element("store-profile").disabled =
        element("apply-selection").disabled =
          false;
      await listing().catch((error) => {
        element("error").textContent = error.message;
      });
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
  element("store-profile").onclick = () =>
    operation(async () => {
      const document = core.normalizePreset(getDocument());
      let saved;
      if (catalog.connection) saved = await post("/store", document);
      else {
        const id =
          "custom-" +
          document.name
            .toLowerCase()
            .replace(/[ _-]+/g, "-")
            .replace(/-$/, "");
        if (!Object.hasOwn(customs, id) && Object.keys(customs).length >= 100)
          throw new Error("My profiles is full. Export JSON to keep another profile.");
        const next = { ...customs, [id]: document };
        localStorage.setItem("nirifx-my-profiles", JSON.stringify(next));
        customs = next;
        saved = document;
        cards();
      }
      element("status").textContent =
        "Saved " + saved.name + " to My profiles. Your active look stays the same.";
    });
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
