// SPDX-License-Identifier: MIT
// Toolkit-independent picker state. Validation, rendering and writes stay in the
// Python CLI; the injected transport lets Node test races without a GTK session.
export const title = (value) =>
  value
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");

function documentFamilies(doc) {
  const effects =
    doc.kind === "profile" ? Object.values(doc.actions).filter(Boolean) : [doc.effect];
  return [...new Set(effects.map((effect) => effect.family))];
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === "object")
    return Object.fromEntries(
      Object.keys(value)
        .sort()
        .map((key) => [key, canonical(value[key])]),
    );
  return value;
}

export class PickerController {
  constructor({ run, launch, command = ["niri-fx"], configPath, statePath, displayPath = String }) {
    if (
      !Array.isArray(command) ||
      !command.length ||
      command.some((arg) => typeof arg !== "string" || !arg)
    )
      throw new Error("command must be a nonempty argument array");
    if (!configPath || !statePath) throw new Error("configPath and statePath are required");
    this.context = Object.freeze({ command: Object.freeze([...command]), configPath, statePath });
    this.run = run;
    this.launch = launch;
    this.displayPath = displayPath;
    this.listeners = new Set();
    this.presets = {};
    this.selectedId = "";
    this.customPath = "";
    this.customDocument = null;
    this.query = "";
    this.family = "";
    this.reviewPlan = null;
    this.allowResize = false;
    this.busy = false;
    this.status = "Loading styles…";
    this.error = "";
    this.undoTransaction = "";
    this.undoStatus = "Checking Undo…";
  }

  subscribe(listener) {
    this.listeners.add(listener);
    listener(this);
    return () => this.listeners.delete(listener);
  }

  emit() {
    for (const listener of this.listeners) listener(this);
  }

  get document() {
    return this.selectedId === "custom"
      ? this.customDocument
      : this.presets[this.selectedId]
        ? this.presets[this.selectedId]
        : null;
  }

  get actions() {
    const doc = this.document;
    return !doc
      ? {}
      : doc.kind === "profile"
        ? doc.actions
        : {
            open: doc.effect,
            close: doc.effect,
            resize: doc.effect.resize ? doc.effect : null,
            movement: null,
          };
  }

  get canApply() {
    return (
      !this.busy && !!this.reviewPlan?.changes.length && (!this.actions.resize || this.allowResize)
    );
  }

  get families() {
    return [
      "",
      ...new Set(Object.values(this.presets).flatMap((doc) => documentFamilies(doc))),
    ].sort((a, b) =>
      !a ? -1 : !b ? 1 : a === "fragments" ? -1 : b === "fragments" ? 1 : a.localeCompare(b),
    );
  }

  get items() {
    const rows = Object.entries(this.presets).map(([id, doc]) => ({
      id,
      name: doc.name,
      families: documentFamilies(doc),
      kind: doc.kind === "profile" ? "profile" : "style",
    }));
    if (this.customDocument) {
      const doc = this.customDocument;
      const effects =
        doc.kind === "profile" ? Object.values(doc.actions).filter(Boolean) : [doc.effect];
      rows.unshift({
        id: "custom",
        name: doc.name,
        families: [...new Set(effects.map((effect) => effect.family))],
      });
    }
    const query = this.query.toLowerCase().trim();
    return rows.filter(
      (row) =>
        (!this.family || row.families.includes(this.family)) &&
        `${row.id} ${row.name} ${row.kind || ""} ${row.families.join(" ")}`
          .toLowerCase()
          .includes(query),
    );
  }

  filter(query, family = this.family) {
    this.query = query;
    this.family = family;
    this.emit();
  }

  select(id) {
    if (this.busy) return false;
    if (!(id === "custom" && this.customDocument) && !Object.hasOwn(this.presets, id)) {
      this.error = "Unknown style. Refresh the catalog.";
      this.emit();
      return false;
    }
    this.selectedId = id;
    this.reviewPlan = null;
    this.allowResize = false;
    this.error = "";
    this.status = "Selection only. Review changes before applying.";
    this.emit();
    return true;
  }

  consentResize(value) {
    if (this.busy) return;
    this.allowResize = !!value;
    this.emit();
  }

  selectionArguments() {
    return this.selectedId === "custom"
      ? ["--custom", this.customPath]
      : [this.document.kind === "profile" ? "--profile" : "--preset", this.selectedId];
  }

  setupArguments() {
    return [
      "setup",
      "--target",
      "standalone",
      "--config",
      this.context.configPath,
      "--state",
      this.context.statePath,
      "--no-launcher",
      ...this.selectionArguments(),
    ];
  }

  async request(action, args, consume) {
    if (this.busy) return false;
    this.busy = true;
    if (action !== "history") this.error = "";
    this.emit();
    try {
      const data = await this.run([...this.context.command, ...args]);
      if (!data || Array.isArray(data) || typeof data !== "object")
        throw new Error("Invalid response from NiriFX.");
      consume(data);
      return true;
    } catch (problem) {
      const message = this.displayPath(problem.message);
      if (action === "history") {
        this.undoTransaction = "";
        this.undoStatus = /No setup snapshots|No applied setup snapshot/.test(message)
          ? "No picker changes to undo."
          : `Undo unavailable: ${message}`;
      } else {
        this.reviewPlan = null;
        this.error = message;
        this.status = "The operation did not complete. Review the error below.";
      }
      return false;
    } finally {
      this.busy = false;
      this.emit();
    }
  }

  async reload(startupFile = "") {
    if (this.busy) return false;
    this.reviewPlan = null;
    const ok = await this.request("catalog", ["list", "--documents"], (data) => {
      this.presets = data;
      if (!this.document) this.selectedId = "balanced";
      this.status = `${Object.keys(data).length} styles and profiles available.`;
    });
    if (ok && startupFile) await this.loadFile(startupFile);
    else await this.refreshUndo();
    return ok;
  }

  async loadFile(file) {
    if (this.busy || !file) return false;
    this.reviewPlan = null;
    this.status = "Validating JSON…";
    const ok = await this.request("inspect", ["inspect", "--custom", file], (data) => {
      this.customDocument = data;
      this.customPath = file;
      this.selectedId = "custom";
      this.query = this.family = "";
      this.allowResize = false;
      this.status = `Loaded ${data.name}. Nothing has been applied.`;
    });
    await this.refreshUndo();
    return ok;
  }

  async review() {
    if (this.busy || !this.document) return false;
    this.reviewPlan = null;
    this.status = "Checking the selected effect and Niri configuration…";
    const shown = this.document.kind === "profile" ? this.document.actions : this.document.effect;
    return this.request("review", this.setupArguments(), (data) => {
      if (!/^[0-9a-f]{64}$/.test(data.plan_sha256) || !Array.isArray(data.changes))
        throw new Error("Update NiriFX to a version with reviewed-plan support.");
      // Re-read by the CLI: a file edited since import must not introduce an
      // unseen resize override or a different effect behind an old description.
      if (
        JSON.stringify(canonical(data.effect)) !== JSON.stringify(canonical(shown)) ||
        JSON.stringify(canonical(data.desktop_motion || null)) !==
          JSON.stringify(canonical(this.document.motion || null))
      )
        throw new Error(
          "The selection changed since loading. Reload its JSON or refresh the catalog, then review again.",
        );
      this.reviewPlan = data;
      this.status = data.changes.length
        ? "Review ready. Apply activates this selection."
        : "Already applied; no files need changing.";
    });
  }

  async apply() {
    if (!this.canApply) return false;
    this.status = "Applying the reviewed changes…";
    const ok = await this.request(
      "apply",
      [...this.setupArguments(), "--expect-plan", this.reviewPlan.plan_sha256, "--apply"],
      (data) => {
        this.reviewPlan = null;
        this.status = data.changed
          ? `Applied ${this.document.name}. Undo restores the previous settings.`
          : "No files changed.";
      },
    );
    await this.refreshUndo();
    return ok;
  }

  refreshUndo() {
    return this.request("history", ["restore", "--state", this.context.statePath], (data) => {
      this.undoTransaction = data.transaction;
      this.undoStatus = "Undo the latest change made by this picker.";
    });
  }

  async undo() {
    if (this.busy || !this.undoTransaction) return false;
    this.reviewPlan = null;
    this.status = "Restoring previous settings…";
    const ok = await this.request(
      "undo",
      [
        "restore",
        "--state",
        this.context.statePath,
        "--transaction",
        this.undoTransaction,
        "--apply",
      ],
      () => {
        this.status = "Previous settings restored exactly.";
      },
    );
    await this.refreshUndo();
    return ok;
  }

  openStudio() {
    if (this.busy || !this.document) return false;
    try {
      this.launch([
        ...this.context.command,
        "studio",
        "--edit",
        "--target",
        "standalone",
        "--config",
        this.context.configPath,
        ...this.selectionArguments(),
      ]);
      this.error = "";
      this.status = "Opening Studio for this selection. Previewing does not activate it.";
      this.emit();
      return true;
    } catch (problem) {
      this.error = this.displayPath(problem.message);
      this.emit();
      return false;
    }
  }
}
