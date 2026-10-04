# Choose and combine window effects

Open `niri-fx studio` to start in **Library**. Choose a finished look, use one
style across enabled actions, or build a combo with different styles. **Customize
in Studio** opens the detailed controls in the same app.

![Choose a look, mix actions and export a profile](gifs/workflow-library.gif)

## Pick a look

Start with **Recommended** for five complete combos, beginning with Fragment
Flow. Soft Landing offers a quiet frosted exit; Ribbon Current has flowing strips;
Playful Motion combines a spring with bubbles; Geometric Flow uses triangles and
hexagons. Single-style recommendations and coordinated action sets remain
available, along with collections, **Favorites**, **My profiles** and **All effects**.
Searching Recommended searches the full built-in catalog.
Choosing a card updates the actual shader preview without changing your desktop.

The combo builder shows **Open**, **Close**, **Resize** and **Move / swap** together.
Choose **Different styles per action** to mix effects, or **Same style for each
enabled action** to copy a shared style. Optional actions remain off until chosen.
Only supported styles appear in resize and movement selectors. A shared style
that cannot support an enabled optional action returns that action to shell
defaults and explains the change.

Use **Tune** beside an action for its detailed settings. Returning to Library
keeps those edits. Refined actions show the matching combo name, such as
**Fragment Flow · Open**; **Custom settings** identifies settings that no longer
match a built-in style or combo action. Undo/Redo also works for combo changes. Move and swap share the
compositor's movement effect; they are not independent shader slots.

## Preview the sequence

Press **Preview combo** to play the selected opening effect, hold the intact
window and finish with its closing effect. Each action uses its own settings and
duration. Resize and movement join the sequence only when explicitly selected in
the combo; shell-default actions are skipped. Previewing leaves the saved document
and your desktop configuration unchanged.

The movement phase is labelled **experimental** and uses a synthetic path. It
does not test native compositor movement or desktop springs. See the
[movement guide](movement.md) for live support and the
[desktop motion recordings](desktop-motion.md) for workspace, camera and overview
behavior. Use **Tune** to adjust any action before previewing again.

## Save, export or apply

- **Save to My profiles** asks for a name and keeps an editable document without activation.
  An existing name shows **Replace saved profile** before replacing that Library copy.
- **Export JSON** produces a portable style/profile for every supported setup.
- **Export Niri config** produces stock Niri shaders. Experimental movement is omitted.
- In the installed app, **Review & apply** lists the configuration changes.
  **Apply these changes** activates exactly that reviewed selection.
- **Restore previous** restores this app's most recent change for the same setup and config. Later file edits
  cause a conflict rather than being overwritten.

The profile name identifies saved looks. Names are case insensitive; spaces,
underscores and hyphens map to the same saved ID. Local profiles live in the
Studio state directory; use `--state` to select a separate library and Apply
history. Web/offline profiles stay in that browser's local storage. Both libraries
hold up to 100 profiles. Export JSON to keep or transfer them; clearing browser
data removes browser-saved profiles.

## Manage My profiles

Choose a saved card to reveal **Save a copy**, **Rename saved profile** and
**Remove saved profile**. A copy suggests an unused name and keeps the original.
Rename keeps the settings and favorites; it cannot replace another profile.
Remove asks for confirmation and leaves the current preview available to export
or save again. Cancel or press Escape to leave the saved document untouched.

These actions manage Library copies only. Applied settings, shell registry
entries and Restore snapshots remain separate. A profile imported from a shell
is labeled **from shell**: save a Library copy before managing it here.

Another local Studio session's edits are checked before replacing, renaming or
removing a profile. Browser saves also preserve other entries and reject a
changed profile from another tab. Refresh or reload before trying again after a
conflict. Damaged or unsupported documents are skipped with a message, so valid
profiles remain available; browsing does not repair or remove their data.

Use **Export JSON** to back up a selected profile or transfer it between the
online Studio and an installed app. **Import preset**, then **Save to My profiles**
adds the imported document to the current Library. Browser storage is local to
the current browser and site; it does not sync to another computer.

Resize is explicitly chosen per profile. Movement can be previewed and saved on
every setup. Live activation requires the verified experimental compositor and
the separate **Apply experimental movement** checkbox on the standalone target.
An iNiR or Noctalia adapter applies stock actions only.

## One interface, different configuration owners

| Setup | Launch | Apply path |
| --- | --- | --- |
| Plain Niri, Waybar or a custom shell | `niri-fx studio --target standalone` | Existing standalone setup, reviewed include and snapshots |
| iNiR, including iRiS | `niri-fx studio --target inir --active` | Installed iNiR serializer, external registry and watched animation block |
| DankMaterialShell / Material Shell | Use the NiriFX launcher's Studio entry | Standalone include outside DMS-owned files |
| Noctalia 5 with Niri Animations | Connect the folder/file below | Existing picker's preset folder and target file |
| Web Studio | [Open online](https://jturbide.github.io/niri-fx/studio/) | Preview, browser-saved profiles and downloads |

All paths share the same FX, presets, profiles and combo builder. No bar or
Quickshell variant is required to use the app. This is Niri compatibility;
opening the editor on another compositor does not supply missing shader hooks.

For Noctalia, use the same paths already configured in Niri Animations:

```sh
niri-fx studio --target noctalia \
  --preset-dir ~/.config/niri/nirifx-presets \
  --picker-file ~/.config/niri/animations.kdl
```

The target must already exist and be included directly by your Niri config.
Apply creates a named owned preset and updates the connected target's include,
preserving its global off/slowdown controls. It does not add another configuration
manager. Read the [Noctalia guide](noctalia.md) for first-time connection and its
optional NiriFX shortcut.

The app chooses iNiR automatically when its helper is installed. If several
shells coexist, choose `--target` explicitly, or launch through the appropriate
shell adapter. With iNiR, use its normal config/registry paths; an unrecognized
custom animation block requires an explicit `--base` instead of guessed timings.

## Compact iRiS entry

The optional source-level iRiS integration replaces the large NiriFX preset grid
with a branded entry showing the active look and **Choose effects**, **Customize**
and **Restore previous**. Native iRiS styles remain available. The entry falls
back to the original preset list when the NiriFX executable is unavailable.

From the source checkout, review the supported gallery patch, then install it:

```sh
python3 scripts/install-iris-integration.py
python3 scripts/install-iris-integration.py --apply
```

Reopen settings afterward. This prototype patches the known gallery and its module declaration,
and adds its component/icon. It makes snapshots and rejects unfamiliar insertion
points; it is not an upstream iNiR feature. To restore its UI files:

```sh
python3 scripts/install-iris-integration.py --restore --apply
```

Restore refuses subsequent source edits. Recheck this optional integration after
an iNiR update. Other shell families can launch the same app without this patch.
