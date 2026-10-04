# Noctalia and preset folders

NiriFX can export a reversible folder of built-in presets and curated open/close pairings for the
existing Noctalia **Niri Animations** picker. Export the pack, connect the picker
and select a style. No additional daemon is required.

The [community plugin](https://noctalia.dev/plugins/community/niri-animations)
reads `.kdl` files from `presets_dir` and writes a dedicated `target_file` containing
an include plus animation slowdown. Its
[source and settings](https://github.com/noctalia-dev/community-plugins/tree/main/niri-animations)
define this file contract. These instructions target **Noctalia 5 / Niri Animations 0.2.0**. Noctalia Shell 4
uses a different plugin system; use [standalone setup](standalone.md) with that version.

Tested with **Noctalia 5.2.1 and Niri Animations 0.2.0**: the picker loads all
the exported pack, applies a mixed-action profile and returns to the base settings.
[Watch the workflow](gifs/workflow-noctalia.gif) or read the
[test details](validation.md#workflow-and-compositor-scenarios).

## Export without changing the active desktop

From this checkout, preview the plan, then apply it:

```sh
python3 -m niri_fx export-pack --output ~/.config/niri/nirifx-presets
python3 -m niri_fx export-pack --output ~/.config/niri/nirifx-presets --apply
```

This creates `nirifx-<id>.kdl` files and `.nirifx-pack.json`, with a snapshot
and restore command. Every file contains only opening and closing overrides;
resize stays off. Exporting does not select a preset or edit Niri/Noctalia config.
The [curated pairings](profiles.md#choose-a-finished-pairing), including Fragment Flow
and Pixel Shuffle, appear alongside the single-effect choices.
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

## Shared NiriFX library

Once the Niri Animations folder and target file are connected, use the
[shared library](library.md#one-interface-different-configuration-owners) to
combine and directly apply named profiles. Its reviewed changes preserve the
picker's off/slowdown controls and have their own Restore history.

An optional Noctalia 5 shortcut (plugin API 24+) lives in `integrations/noctalia/niriFX`.
Copy it into your local Noctalia plugin directory, enable `jturbide/niri-fx`,
add `jturbide/niri-fx:library` to the Control Center shortcuts,
and set its **Preset folder** and **Animation target file** to the same values
used by Niri Animations. The shortcut opens the shared app; it does not manage
animations independently. The existing Niri Animations plugin remains available.

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
