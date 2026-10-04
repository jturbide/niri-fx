# Choose and combine window effects

Open `niri-fx studio` to start in **Library**. Choose a finished look, use one
style across enabled actions, or build a combo with different styles. **Customize
in Studio** opens the detailed controls in the same app.

![Choose a look, mix actions and export a profile](gifs/workflow-library.gif)

## Pick a look

Start with **Recommended**, or browse collections, **Favorites**, **My profiles**
and **All effects**. Searching Recommended searches the full built-in catalog.
Choosing a card updates the actual shader preview without changing your desktop.

The combo builder shows **Open**, **Close**, **Resize** and **Move / swap** together.
Choose **Different styles per action** to mix effects, or **Same style for each
enabled action** to copy a shared style. Optional actions remain off until chosen.
Only supported styles appear in resize and movement selectors. A shared style
that cannot support an enabled optional action returns that action to shell
defaults and explains the change.

Use **Tune** beside an action for its detailed settings. Returning to Library
keeps those edits; **Custom settings** identifies an action that no longer matches
a built-in style. Undo/Redo also works for combo changes. Move and swap share the
compositor's movement effect; they are not independent shader slots.

## Save, export or apply

- **Save to My profiles** keeps a named editable document without activation.
- **Export JSON** produces a portable style/profile for every supported setup.
- **Export Niri config** produces stock Niri shaders. Experimental movement is omitted.
- In the installed app, **Review & apply** lists the configuration changes.
  **Apply these changes** activates exactly that reviewed selection.
- **Restore previous** restores this app's most recent change for the same setup and config. Later file edits
  cause a conflict rather than being overwritten.

The profile name identifies saved looks. Saving the same name replaces that
named library document. Local profiles live in the Studio state directory;
use `--state` to select a separate library and Apply history. Web/offline profiles
stay in that browser's local storage, with a limit of 100. Export JSON to keep or
transfer them; clearing browser data removes browser-saved profiles.

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
