# DankMaterialShell launcher adapter

Included in 0.7.0, the optional adapter provides an `fx` launcher provider with searchable built-in
presets, **Open NiriFX Studio**, and **Undo last NiriFX change**. It uses NiriFX's
existing CLI and reversible setup; no renderer or shader logic is duplicated in
QML. It targets DMS on **Niri**.

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
the DMS launcher currently lists built-in styles, not saved custom profiles.

## Validation scope

The real QML component passed catalog loading/search, rejection of unknown preset
actions, CLI apply and exact restore in offscreen Quickshell 0.3.1 with temporary
Niri configs. Reproduce with `python3 scripts/test-dms-adapter.py`. The adapter
also passed discovery and launcher instantiation through the actual **DMS 1.6.2
PluginService**, followed by search, apply and exact restore. Reproduce that check
with `python3 scripts/test-dms-service.py --source /path/to/dms-qml`. It uses a
private D-Bus session and temporary XDG directories; no running shell is replaced.
This covers the real plugin service contract. Visual acceptance of the full DMS
launcher remains separate; the isolated service test does not render that modal.
