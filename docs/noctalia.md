# Noctalia and preset folders

NiriFX can export a reversible folder of all 47 open/close presets for the
existing Noctalia **Niri Animations** picker. This support is included in 0.7.0. It adds no daemon and does not modify Noctalia source.

The [community plugin](https://noctalia.dev/plugins/community/niri-animations)
reads `.kdl` files from `presets_dir` and writes a dedicated `target_file` containing
an include plus animation slowdown. Its
[source and settings](https://github.com/noctalia-dev/community-plugins/tree/main/niri-animations)
define this file contract. Current Noctalia 5 uses Luau plugins; legacy Noctalia
Shell 4 uses a different QML plugin system. These instructions target the current
plugin, not an interchangeable plugin for both versions.

The exported configs and picker-style include chain have been validated with
stock Niri. **Noctalia 5.2.1 with Niri Animations 0.2.0 passed an isolated UI test:**
the picker found all 47 styles, keyboard dropdown selection applied Iris Bloom
and Ember Erosion, and selecting the base pack removed the preset include.
Niri validated the resulting configurations. For legacy
Noctalia or a picker without this contract, use [standalone setup](setup.md).

## Export without changing the active desktop

From this checkout, preview the plan, then apply it:

```sh
python3 -m niri_fx export-pack --output ~/.config/niri/nirifx-presets
python3 -m niri_fx export-pack --output ~/.config/niri/nirifx-presets --apply
```

This creates `nirifx-<preset>.kdl` files and `.nirifx-pack.json`, with a snapshot
and restore command. Every file contains only opening and closing overrides;
resize stays off. Exporting does not select a preset or edit Niri/Noctalia config.
Unrelated files survive. Modified owned files, name collisions and per-file
symlinks stop updates for review instead of being overwritten.

## Connect the existing picker

1. Install **Niri Animations** (`imjustdoingmypart/niri-animations`) through
   Noctalia's plugin settings.
2. In that plugin, set `presets_dir` to `~/.config/niri/nirifx-presets`,
   `include_prefix` to `./nirifx-presets`, and `target_file` to
   `~/.config/niri/animations.kdl`. This target is owned by the picker; choose
   another dedicated file if it already contains your hand-written settings.
3. Choose a NiriFX preset so the plugin creates its target file.
4. Back up your main Niri config. Add `include "animations.kdl"` once, after
   earlier animation definitions and shell includes, then run `niri validate`.

Keep one manager responsible for open/close. A later standalone NiriFX include
can override the picker's choice; restore that setup or remove its managed
include before switching ownership to the picker. The iNiR save button in
Studio remains specific to iNiR.

You can tune a style in the offline Studio and export its KDL into this folder
under your own filename, outside the `nirifx-` prefix. The picker will discover it
and pack updates will preserve it. Native move/swap effects still require the
separate compositor patch; no shell plugin can supply that hook.

## Update or undo

Run the same export command from a newer checkout to update generated files.
The command is idempotent and preserves other providers' presets. If a generated
file was edited, move your version to a custom filename before updating.

Before restoring the export snapshot, select a non-NiriFX preset and ensure the
picker's active include no longer points into the pack. Then run the exact
`restore --state … --transaction … --apply` command printed by the export.
Restoration refuses to overwrite later edits. Noctalia's target file and your
main config remain under your control. The same pack can feed other Niri pickers
that consume standalone KDL animation files.

Studio can also download a single named KDL file: select **Noctalia preset file**
as its save target. This supports [independent profiles](profiles.md), including
different families for opening and closing. Put the file in `presets_dir`.
