// SPDX-License-Identifier: MIT
import Gtk from "gi://Gtk?version=4.0";
import Gdk from "gi://Gdk?version=4.0";
import Gio from "gi://Gio";
import GLib from "gi://GLib";
import Pango from "gi://Pango";
import { PickerController, title } from "./controller.mjs";
import { displayPath, environmentOptions, launch, run } from "./transport.mjs";

const label = (text, css = "") =>
  new Gtk.Label({ label: text, xalign: 0, wrap: true, css_classes: css ? [css] : [] });
const box = (vertical = true, spacing = 12) =>
  new Gtk.Box({
    orientation: vertical ? Gtk.Orientation.VERTICAL : Gtk.Orientation.HORIZONTAL,
    spacing,
  });
function button(text, callback) {
  const widget = new Gtk.Button({ label: text });
  widget.connect("clicked", callback);
  return widget;
}

/** Returns a normal Gtk.Box and controller, suitable for an existing settings page.
 * The host owns lifetime: dispose the view when removed, and keep the application
 * alive until controller.busy is false. No shell registry or global theme changes.
 */
export function createPicker(options = {}) {
  const settings = { ...environmentOptions(), ...options };
  const controller = new PickerController({ run, launch, displayPath, ...settings });
  const root = box();
  root.add_css_class("nirifx-picker");
  root.set_size_request(720, 540);
  const provider = new Gtk.CssProvider();
  provider.load_from_file(
    Gio.File.new_for_uri(import.meta.url)
      .get_parent()
      .get_child("picker.css"),
  );
  const display = Gdk.Display.get_default();
  Gtk.StyleContext.add_provider_for_display(
    display,
    provider,
    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
  );

  const header = box(false);
  const heading = box(true, 4);
  heading.set_hexpand(true);
  heading.append(label("NiriFX Picker", "nirifx-title"));
  heading.append(label("Choose a style. Review the changes. Make it yours.", "nirifx-muted"));
  header.append(heading);
  const load = button("Load JSON", () => {
    const filter = new Gtk.FileFilter();
    filter.set_name("NiriFX JSON");
    filter.add_pattern("*.json");
    const filters = new Gio.ListStore({ item_type: Gtk.FileFilter });
    filters.append(filter);
    const dialog = new Gtk.FileDialog({ title: "Load a NiriFX style or profile", filters });
    dialog.open(root.get_root(), null, (source, result) => {
      try {
        const path = source.open_finish(result).get_path();
        if (!path) throw new Error("Choose a local JSON file.");
        void controller.loadFile(path);
      } catch (error) {
        if (error.matches?.(Gtk.DialogError, Gtk.DialogError.DISMISSED)) return;
        controller.error = error.message;
        controller.emit();
      }
    });
  });
  const refresh = button("Refresh", () => void controller.reload());
  header.append(load);
  header.append(refresh);
  root.append(header);

  const body = box(false, 24);
  body.set_vexpand(true);
  const sidebar = box();
  sidebar.set_size_request(240, -1);
  const search = new Gtk.SearchEntry({ placeholder_text: "Search styles or families…" });
  const family = new Gtk.DropDown();
  const count = label("", "nirifx-muted");
  const list = new Gtk.ListBox({ selection_mode: Gtk.SelectionMode.SINGLE });
  const listScroll = new Gtk.ScrolledWindow({
    hscrollbar_policy: Gtk.PolicyType.NEVER,
    vexpand: true,
    child: list,
  });
  for (const widget of [search, family, count, listScroll]) sidebar.append(widget);
  body.append(sidebar);
  body.append(new Gtk.Separator({ orientation: Gtk.Orientation.VERTICAL }));
  const details = box(true, 16);
  details.set_hexpand(true);
  const kind = label("", "nirifx-accent");
  const name = label("Choose a style", "nirifx-title");
  const source = label("", "nirifx-muted");
  source.set_wrap_mode(Pango.WrapMode.WORD_CHAR);
  const actions = label("");
  const resize = new Gtk.CheckButton({ label: "Allow this selection to change resize effects" });
  const movement = label(
    "Experimental movement settings are retained in the file. This picker applies stock Niri actions only.",
    "nirifx-muted",
  );
  const preview = button("Preview in Studio", () => controller.openStudio());
  const review = button("Review changes", () => void controller.review());
  const controls = box(false);
  controls.append(preview);
  controls.append(review);
  const config = label(displayPath(controller.context.configPath), "nirifx-muted");
  config.set_wrap_mode(Pango.WrapMode.WORD_CHAR);
  const plan = label("", "nirifx-plan");
  plan.set_wrap_mode(Pango.WrapMode.WORD_CHAR);
  const apply = button("Apply reviewed changes", () => void controller.apply());
  apply.set_halign(Gtk.Align.START);
  apply.add_css_class("suggested-action");
  const status = label("", "nirifx-accent");
  const error = label("", "nirifx-error");
  error.set_wrap_mode(Pango.WrapMode.WORD_CHAR);
  for (const widget of [
    kind,
    name,
    source,
    actions,
    resize,
    movement,
    controls,
    label("Applies to standalone Niri", "heading"),
    config,
    label(
      "The managed include overrides earlier open/close effects. Use one animation picker at a time.",
      "nirifx-muted",
    ),
    plan,
    apply,
    status,
    error,
  ])
    details.append(widget);
  body.append(
    new Gtk.ScrolledWindow({
      hscrollbar_policy: Gtk.PolicyType.NEVER,
      hexpand: true,
      child: details,
    }),
  );
  root.append(body);
  root.append(new Gtk.Separator());
  const footer = box(false);
  const undo = button("Undo last change", () => void controller.undo());
  const undoStatus = label("", "nirifx-muted");
  undoStatus.set_hexpand(true);
  footer.append(undo);
  footer.append(undoStatus);
  footer.append(label("Choose resize separately", "nirifx-accent"));
  root.append(footer);

  // Retain actual widgets across state changes so search focus, keyboard
  // selection and accessibility objects survive subprocess completion.
  let updating = false;
  let rowsKey = "";
  let familiesKey = "";
  const rows = new Map();
  search.connect("notify::text", () => {
    if (!updating) controller.filter(search.get_text());
  });
  search.connect("activate", () => {
    if (controller.items.length) controller.select(controller.items[0].id);
  });
  family.connect("notify::selected", () => {
    if (!updating)
      controller.filter(controller.query, controller.families[family.get_selected()] || "");
  });
  list.connect("row-selected", (_, row) => {
    if (row && !updating) controller.select(row.nirifxId);
  });
  resize.connect("toggled", () => {
    if (!updating) controller.consentResize(resize.get_active());
  });
  const unsubscribe = controller.subscribe((state) => {
    updating = true;
    const families = state.families;
    if (familiesKey !== JSON.stringify(families)) {
      familiesKey = JSON.stringify(families);
      family.set_model(Gtk.StringList.new(families.map((id) => (id ? title(id) : "All families"))));
    }
    family.set_selected(families.indexOf(state.family));
    if (search.get_text() !== state.query) search.set_text(state.query);
    const items = state.items;
    if (rowsKey !== JSON.stringify(items)) {
      rowsKey = JSON.stringify(items);
      rows.clear();
      while (list.get_first_child()) list.remove(list.get_first_child());
      for (const item of items) {
        const row = new Gtk.ListBoxRow();
        row.nirifxId = item.id;
        const content = box(true, 4);
        content.append(label(item.name, "heading"));
        content.append(
          label(
            item.id === "custom"
              ? "Loaded JSON"
              : item.kind === "profile"
                ? "Open / close profile · " + item.families.map(title).join(" · ")
                : item.families.map(title).join(" · "),
            "nirifx-muted",
          ),
        );
        row.set_child(content);
        list.append(row);
        rows.set(item.id, row);
      }
    }
    list.select_row(rows.get(state.selectedId) || null);
    count.set_label(`${items.length} ${items.length === 1 ? "result" : "results"}`);
    kind.set_label(state.selectedId === "custom" ? "CUSTOM JSON" : "BUILT-IN STYLE");
    name.set_label(state.document?.name || "Choose a style");
    source.set_label(
      state.selectedId === "custom"
        ? displayPath(state.customPath)
        : "Tune the look in Studio, or apply its current settings here.",
    );
    const effect = state.actions;
    actions.set_label(
      `Opening   ${effect.open ? `${title(effect.open.family)} · ${effect.open.open_ms} ms` : "—"}\n\nClosing    ${effect.close ? `${title(effect.close.family)} · ${effect.close.close_ms} ms` : "—"}\n\nResize     ${effect.resize ? `${title(effect.resize.family)} · explicit override` : "Use base Niri settings"}`,
    );
    resize.set_visible(!!effect.resize);
    resize.set_active(state.allowResize);
    movement.set_visible(!!effect.movement);
    plan.set_visible(!!state.reviewPlan);
    plan.set_label(
      state.reviewPlan
        ? "Reviewed changes\n" +
            (state.reviewPlan.changes
              .map((change) => `${title(change.action)} · ${displayPath(change.path)}`)
              .join("\n") || "Already matches this selection.")
        : "",
    );
    for (const widget of [load, refresh, list, resize]) widget.set_sensitive(!state.busy);
    for (const widget of [preview, review]) widget.set_sensitive(!state.busy && !!state.document);
    apply.set_sensitive(state.canApply);
    undo.set_sensitive(!state.busy && !!state.undoTransaction);
    status.set_label(state.status);
    error.set_label(state.error);
    error.set_visible(!!state.error);
    undoStatus.set_label(state.undoStatus);
    updating = false;
  });

  const shortcuts = new Gtk.ShortcutController({ scope: Gtk.ShortcutScope.MANAGED });
  for (const [trigger, callback] of [
    ["<Control>f", () => search.grab_focus()],
    [
      "<Control>o",
      () => {
        if (load.sensitive) load.emit("clicked");
      },
    ],
    ["<Control>r", () => void controller.review()],
    ["<Control>Return", () => void controller.apply()],
    ["<Control><Alt>u", () => void controller.undo()],
  ])
    shortcuts.add_shortcut(
      new Gtk.Shortcut({
        trigger: Gtk.ShortcutTrigger.parse_string(trigger),
        action: Gtk.CallbackAction.new(() => {
          callback();
          return true;
        }),
      }),
    );
  root.add_controller(shortcuts);
  return {
    widget: root,
    controller,
    ready: controller.reload(settings.startupFile),
    dispose() {
      unsubscribe();
      Gtk.StyleContext.remove_provider_for_display(display, provider);
    },
  };
}

/** A lifecycle-safe ordinary Gtk.ApplicationWindow, also usable by AGS 3. */
export function createPickerWindow(application, options = {}) {
  const picker = createPicker(options);
  const window = new Gtk.ApplicationWindow({
    application,
    title: "NiriFX GTK Picker",
    default_width: 1000,
    default_height: 820,
    child: picker.widget,
  });
  window.set_name("nirifx-picker");
  let closing = false;
  let held = false;
  let disposed = false;
  const stop = picker.controller.subscribe((state) => {
    if (state.busy && !held) {
      application.hold();
      held = true;
    }
    if (!state.busy && held) {
      application.release();
      held = false;
    }
    if (closing && !state.busy && !disposed) {
      // Defer destruction until the notification loop finishes; no GTK callback
      // should touch a disposed widget when a write or history read completes.
      GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
        if (!disposed && !picker.controller.busy) {
          disposed = true;
          stop();
          picker.dispose();
          window.destroy();
        }
        return GLib.SOURCE_REMOVE;
      });
    }
  });
  window.connect("close-request", () => {
    closing = true;
    window.set_visible(false);
    if (!picker.controller.busy && !disposed) {
      disposed = true;
      stop();
      picker.dispose();
      window.destroy();
    }
    return true;
  });
  return { ...picker, window };
}
