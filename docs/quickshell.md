# Quickshell picker

Browse NiriFX styles in a desktop window, load a JSON profile, preview it in Studio,
then review and apply its changes. The same QML components can be embedded in a
custom Quickshell settings page. Effects still run in Niri; Quickshell supplies the UI.

![Search, review, apply and restore in the Quickshell picker](gifs/workflow-quickshell-picker.gif)

## Open the picker

Requires Niri, Python 3.10+ and Quickshell (`qs`); tested with Niri 26.04 and
Quickshell 0.3.1. Available since v0.9.0.
From a [source checkout](getting-started.md):

```sh
python3 -m niri_fx picker
python3 -m niri_fx picker --custom examples/profiles/burst-and-drift.json
```

After installing a version containing the picker, use `niri-fx picker`.
No shell plugin installation or autostart is required. NiriFX Studio and the CLI
continue to work without Quickshell.

1. Search by style, profile name or either action family, or choose **Load JSON** for a downloaded style/profile.
2. **Preview in Studio** opens the selected settings for editing. Export your
   edited JSON and load it into the picker when ready.
3. **Review changes** validates the selection and your Niri config, then lists
   the files to create or update. Browsing, loading and reviewing do not activate effects.
4. **Apply reviewed changes** activates them through Niri's config reload.
5. **Undo last change** restores the previous file bytes. Repeat to step back
   through changes made with this picker's state directory.

The catalog includes 64 single styles and seven ready-made open/close profiles.
Search `profile` to show the pairings. Resize stays unchanged for all built-ins. A custom style/profile that specifies
resize requires the visible **Allow this selection to change resize effects**
checkbox before Apply. Experimental movement data can be loaded and sent to
Studio, but this picker activates stock Niri actions only.

Keyboard shortcuts: **Ctrl+F** search, **Ctrl+O** load JSON, **Ctrl+R** review,
**Ctrl+Enter** apply and **Ctrl+Alt+U** undo settings. Enter in search selects the
first result; it does not apply it. Ctrl+Z retains its normal text-editing role.

## Configuration ownership and restore

The picker uses the standalone setup path, appending a managed include to
`$XDG_CONFIG_HOME/niri/config.kdl` (or `~/.config/niri/config.kdl`). The include
overrides earlier opening/closing effects. Use one animation manager at a time;
the [iRiS](getting-started.md#inir-and-iris), [DMS](dms.md) and [Noctalia](noctalia.md)
guides describe their existing integration paths.

Snapshots are separate from ordinary setup and DMS:
`$XDG_STATE_HOME/niri-fx/quickshell`, falling back to `~/.local/state/niri-fx/quickshell`.
For nonstandard locations:

```sh
niri-fx picker --config /path/to/niri/config.kdl --state /path/to/picker-state
niri-fx restore --state /path/to/picker-state
niri-fx restore --state /path/to/picker-state --apply
```

Apply rebuilds the plan and checks its fingerprint against the review. If the
selection, managed files, resolved paths or captured permissions changed, review
again. If an imported document changed since loading, load it again first.
Undo refuses externally edited files instead of overwriting them. Read the error
and use [setup and restore](setup.md) for recovery; do not delete snapshots to
silence a conflict. Generated or declaratively managed configs should use
[rendered exports](scenarios.md) through their owning configuration manager.

## Embed in a custom Quickshell

Find the installed component directory:

```sh
niri-fx picker --qml-dir
```

Import that directory by its absolute QML URL, replacing the example path below.
Keep the controller alive for as long as it has an operation in progress:

```qml
import QtQuick
import Quickshell
import "file:///absolute/path/to/niri_fx/qml" as NiriFX

ShellRoot {
    NiriFX.NiriFXController {
        id: fx
        command: ["/absolute/path/to/niri-fx"]
        // Optional: configPath and statePath for this shell's own config/history.
    }
    FloatingWindow {
        title: "Window effects"
        implicitWidth: 980
        implicitHeight: 780
        minimumSize: Qt.size(780, 600)
        NiriFX.NiriFXPicker { anchors.fill: parent; controller: fx }
    }
}
```

Use an absolute executable path when the desktop session does not activate your
Python environment. `command` is an argument array, never a shell command string.
The controller and view are separate: custom shells can supply their own controls
while retaining the same catalog, validation, review and restore behavior.

| Controller API | Use |
| --- | --- |
| `query`, `family`, `items`, `families` | Search and filtering; an empty family selects all |
| `select(id)`, `selectedDocument`, `actions` | Choose a catalog ID or the loaded `custom` entry; inspect its action settings |
| `loadFile(path)`, `loadUrl(fileUrl)` | Validate a local style/profile JSON |
| `review()`, `reviewPlan` | Request a fresh read-only plan |
| `allowResize`, `canApply`, `apply()` | Explicit resize consent and guarded activation |
| `refreshUndo()`, `undoTransaction`, `undo()` | Check and restore the latest available snapshot |
| `openStudio()` | Open the current selection in the standalone Studio |
| `busy`, `status`, `error`, `undoStatus` | Disable conflicting controls and display progress/failures |
| `completed(action, success)` | Observe catalog, import, review, apply, restore and history results |

The launcher disables QML file watching and waits for active operations when its
last window closes. An embedding shell must preserve that lifecycle: do not
destroy/reload the controller while `busy`. Quickshell terminates child processes
on configuration reload or exit; force-killing it can interrupt a file transaction.
The CLI has rollback and snapshots, but writes across multiple files are not
crash-atomic. See the official [Process lifecycle](https://quickshell.org/docs/v0.3.1/types/Quickshell.Io/Process/)
and [Quickshell lifecycle](https://quickshell.org/docs/v0.3.1/types/Quickshell/Quickshell/) documentation.

## Validation

`python3 scripts/test-quickshell-picker.py` runs the real QML view/controller and
CLI against temporary files. `--record` additionally tests keyboard interaction
in an owned nested Niri window and regenerates the GIF. Tests cover search,
profiles, consent, repeated Undo, no-op apply, stale reviews, externally edited
files and missing executables. Studio argument dispatch is checked without
launching a browser in this harness. See [validation scope](validation.md#workflow-and-compositor-scenarios).
