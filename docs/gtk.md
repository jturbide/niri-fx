# GTK picker and AGS integration

Browse NiriFX styles, import a JSON profile, review its changes and apply or undo
them in a native GTK window. The reusable view is an ordinary GTK 4 widget, so
GTK-based shells can embed it in their own settings. Niri renders the effects.

![GTK picker search, reviewed Apply and Undo](gifs/workflow-gtk-picker.gif)

## Open the standalone GTK picker

Requires Python 3.10+, Niri, GJS (`gjs`) and GTK 4.10 or newer, including their
GObject introspection data. Quickshell, AGS and Astal are not required for the
standalone window. Install these optional desktop dependencies through your
distribution; installing the Python package does not install GTK or GJS.
Available since v0.9.0.

From a [source checkout](getting-started.md):

```sh
python3 -m niri_fx picker --toolkit gtk
python3 -m niri_fx picker --toolkit gtk --custom examples/profiles/elastic-resize.json
```

After installing a version containing the picker, use `niri-fx picker --toolkit gtk`.
The default `niri-fx picker` continues to open the [Quickshell UI](quickshell.md).

1. Search by style, profile name or either action family, or **Load JSON** to import a local style/profile.
2. **Preview in Studio** opens the selection for editing. Export the edited JSON
   and load it again when ready.
3. **Review changes** validates the selection and lists the affected files.
4. **Apply reviewed changes** activates the reviewed plan through Niri's reload.
5. **Undo last change** restores the previous file bytes. Repeat to undo earlier
   changes from this picker's history.

Search `profile` for the seven curated pairings, alongside the 64 single styles.
Browsing, importing and reviewing are read-only. All built-ins use your base
Niri resize settings. A custom selection with resize effects requires the visible
consent checkbox before Apply. Replacing a previously applied NiriFX resize
override with a built-in style removes that override, exposing the base settings.
Experimental movement can be loaded and edited in Studio; this picker activates
stock Niri actions only.

Shortcuts: **Ctrl+F** search, **Ctrl+O** load JSON, **Ctrl+R** review,
**Ctrl+Enter** apply, **Ctrl+Alt+U** undo settings. Enter in search selects the
first result without applying it. Ctrl+Z remains a text-editing shortcut.

## Config ownership and history

This uses the standalone setup path, appending a managed include to your Niri
config. Choose one animation manager at a time: the include overrides earlier
open/close settings. iNiR/iRiS, DMS and Noctalia users can retain their existing
[integration paths](scenarios.md). Declarative or generated configs should use
rendered exports through their owning configuration manager.

GTK history is separate from ordinary setup and the Quickshell picker:
`$XDG_STATE_HOME/niri-fx/gtk`, falling back to `~/.local/state/niri-fx/gtk`.

```sh
niri-fx picker --toolkit gtk --config /path/to/niri/config.kdl --state /path/to/gtk-state
niri-fx restore --state /path/to/gtk-state
niri-fx restore --state /path/to/gtk-state --apply
```

Apply rebuilds the plan and checks it against the review. Changed files, settings,
paths or permissions require a new review; an edited JSON document must be loaded
again. Undo refuses external edits. Keep snapshots and resolve the reported
conflict using the [setup/restore guide](setup.md).

Closing the standalone window hides it immediately and waits for active CLI
operations before exiting. Abrupt process termination can still interrupt a
multi-file transaction; the CLI provides rollback and snapshots, not crash-atomic
writes across every file.

## Run the AGS 3 example

Install NiriFX from this checkout into a virtual environment, then run the supplied
example with [AGS 3 for GTK 4](https://aylur.github.io/ags/guide/quick-start.html):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
NIRIFX_GTK_DIR="$(.venv/bin/niri-fx picker --gtk-dir)" \
  PATH="$PWD/.venv/bin:$PATH" \
  ags run integrations/ags/app.js
```

When `niri-fx` is already on your desktop session's PATH, omit the PATH override.
AGS launches GJS beside the entry file; an installed executable avoids depending
on the source checkout's working directory. For custom command arguments,
`NIRIFX_COMMAND` accepts a JSON argument array.

The [example](../integrations/ags/app.js) uses AGS's application object and imports
the installed widget dynamically, preserving its stylesheet location. It owns a
separate application instance and exits after its last window closes safely.
An existing shell should use its own application lifecycle. See
[AGS application behavior](https://aylur.github.io/ags/guide/app-cli.html).

## Embed in a GTK 4 settings page

Find the module directory with `niri-fx picker --gtk-dir`. Import `picker.mjs` by
its absolute file URL, then choose a normal window or an embeddable box:

```js
const { createPickerWindow, createPicker } = await import(
  "file:///absolute/path/to/niri_fx/gtk/picker.mjs"
);

// A separate window in an existing Gtk.Application, including AGS 3.
const picker = createPickerWindow(app, {
  command: ["/absolute/path/to/niri-fx"],
  configPath: "/absolute/path/to/niri/config.kdl",
  statePath: "/absolute/path/to/this-shell/nirifx-history",
});
picker.window.present();

// Alternatively, append a widget to your existing GTK 4 settings container.
// const embedded = createPicker({ command: ["/absolute/path/to/niri-fx"] });
// settingsBox.append(embedded.widget);
```

The returned object exposes `widget`, `controller`, a `ready` promise and
`dispose()`. `createPickerWindow` additionally exposes `window` and manages busy
operation lifetime. For `createPicker`, the host must wait until `controller.busy`
is false before removing the widget, calling `dispose()` or exiting/reloading the
application. The scoped stylesheet leaves unrelated widgets and global GTK
settings alone. No global Gio prototype modifications are used.

| Controller API | Purpose |
| --- | --- |
| `filter(query, family)`, `items`, `families` | Read-only search; an empty family means all |
| `select(id)`, `document`, `actions` | Choose a catalog ID or the loaded `custom` entry |
| `loadFile(path)`, `reload()` | Validate a local document or refresh the catalog |
| `review()`, `reviewPlan` | Request a read-only plan |
| `consentResize(bool)`, `canApply`, `apply()` | Explicit resize consent and guarded activation |
| `refreshUndo()`, `undoTransaction`, `undo()` | Restore the latest available snapshot |
| `openStudio()` | Open the selected document in standalone Studio |
| `subscribe(listener)` | Observe state; returns an unsubscribe function |
| `busy`, `status`, `error`, `undoStatus` | Progress and recoverable errors |

`command` is an argument array, never a shell string. Config and state paths are
fixed when constructing a controller; create a new controller to change targets.
Keep its lifetime intact during operations. [Astal](https://aylur.github.io/astal/)
GTK 4 hosts can use this ordinary widget; Astal-specific containers and full shell
sessions are not covered by the example's runtime tests. GTK 3 and legacy AGS APIs
need their own adapter, or can launch the standalone picker/CLI.

## Validation

Tested with GJS 1.88.1, GTK 4.22.5, Niri 26.04 and AGS source tag v3.1.2
(`bbee2f1`; its CLI embeds the version label 3.1.0). The AGS example passes real
keyboard selection, Review, Apply, exact Undo and clean exit in a private session.
The standalone tests also cover imported profiles, resize consent, repeated Undo,
stale documents/configs, external-edit refusal, missing commands and closing during
Apply. Studio dispatch is checked without launching a browser in this harness.

```sh
python3 scripts/test-gtk-picker.py
python3 scripts/test-gtk-picker.py --ags /path/to/ags
python3 scripts/test-gtk-picker.py --record
```

Run inside Niri with `wtype`; recording additionally needs `wf-recorder` and
`ffmpeg`. Tests use temporary configs and capture only an owned nested output.
CI runs the toolkit-independent controller tests and package-resource checks;
the real GTK/AGS workflow is a local acceptance gate. The
[validation record](validation.md) distinguishes this coverage from full desktop
integration and hardware testing.
