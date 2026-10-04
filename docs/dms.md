# DankMaterialShell launcher adapter

Use the `fx` launcher command to search built-in presets and open/close pairings, open **NiriFX Studio**
and **Undo last NiriFX change**. This optional adapter works with DMS on **Niri**.

Install the current NiriFX checkout using [getting started](getting-started.md),
and verify `niri-fx --version` works in your shell. Then copy the plugin:

```sh
mkdir -p ~/.config/DankMaterialShell/plugins
cp -r integrations/dms/niriFX ~/.config/DankMaterialShell/plugins/
```

Do not overwrite an independently modified plugin copy without reviewing it.
In DMS Settings → Plugins, scan and enable **NiriFX**. Open the launcher and use
the `fx` trigger, then search for a style. Selecting a style applies it; opening
Studio alone does not. DMS documents the [launcher plugin interface](https://danklinux.com/docs/dankmaterialshell/plugins-overview/).

Studio now opens [Library](library.md), with recommended looks, favorites, saved
profiles and a per-action combo builder. The DMS entry explicitly selects the
standalone target, even if iNiR is also installed. Direct Apply from the app uses
its own Studio Restore history; the launcher's built-in selections keep the
existing DMS history described below.

Application uses `setup --target standalone --no-launcher --apply`. It appends
the managed include to the main Niri config and keeps shaders outside DMS-owned
files. The adapter resolves XDG config/state directories. Snapshots live under
`$XDG_STATE_HOME/niri-fx/dms`; Undo restores the latest plugin transaction, including
its previous preset. Repeated Undo steps back through earlier selections.
Unrelated edits cause restore to refuse, preserving your changes.

Resize remains unchanged. This does not enable native move/swap shaders. Use one
animation manager: an active standalone override takes precedence over iRiS or
Noctalia's earlier animation includes. Remove the override through Undo/restore
before switching to another picker. Disabling the plugin alone does not undo a
Niri configuration change. Studio's standalone save target downloads a file;
the DMS launcher lists the built-in styles and curated profiles. Saved custom
JSON profiles can be opened in Studio or the reusable desktop pickers.

## Tested versions

The adapter has been tested with **DMS 1.6.2 and Quickshell 0.3.1** using the
real launcher and plugin service in an isolated host. Search, preset selection,
Undo and Studio launch pass; Undo also preserves externally edited configs.
Testing a complete DMS desktop session across releases remains planned.

[Watch the workflow](gifs/workflow-dms.gif). Contributor details and reproduction
commands are in [testing](validation.md#workflow-and-compositor-scenarios) and the
[recording guide](gifs/README.md#workflow-and-compositor-recordings).
