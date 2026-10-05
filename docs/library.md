# Choose and combine window effects

Open `niri-fx studio` to start in **Library**. Choose a finished look, use one
style across selected actions, or build a combo with different styles. **Customize
in Studio** opens the detailed controls in the same app.

![Choose a look, mix actions and export a profile](gifs/workflow-library.gif)

## First use: choose, review and restore

After [installation](getting-started.md#install-and-open-library), open
`niri-fx studio` and choose **Fragment Flow** in Recommended. Press **Preview
combo**, then try setting Close to **Off** while leaving Open on **NiriFX Style**
and Resize, Move / swap and Pointer drag on **Preserve**.

Use **Save to My profiles** if you want a named copy. Press **Review & apply**,
inspect the listed files, then **Apply these changes**. **Cancel** leaves the
config untouched. Open and close a test window to see the result; **Restore
previous** returns to the settings from before Apply while keeping your saved
profile. Reopening the app with the same target, config and state directory
retains this Restore history.

The default connection detects iNiR's helper or uses standalone Niri. Choose an
explicit [connection](#one-interface-different-configuration-owners) if several
shells coexist or another tool owns the animation file. Previewing, naming and
saving do not require registration of the built-in catalog.

## Pick a look

Start with **Recommended** for five complete combos, beginning with Fragment
Flow. Soft Landing offers a quiet frosted exit; Ribbon Current has flowing strips;
Playful Motion combines a spring with bubbles; Geometric Flow uses triangles and
hexagons. Single-style recommendations and coordinated action sets remain
available, along with collections, **Favorites**, **My profiles** and **All effects**.
Searching Recommended searches the full built-in catalog.
Choosing a card updates the actual shader preview without changing your desktop.

The combo builder shows Open, Close, Resize and Move / swap together, with
Pointer drag below. Each has **Preserve / NiriFX Style / Off**. Preserve keeps
the underlying desktop or shell configuration; Off disables the selected action.
Choose a preset after selecting NiriFX Style.

Choose **Different styles per action** to mix effects, or **Same style for each
NiriFX Style action** to share a style across actions already set to NiriFX Style.
Preserve and Off choices stay unchanged. If a shared style cannot support a
selected resize or movement action, its existing style stays selected and the
interface explains why. See [action choices](profiles.md#choose-which-actions-to-customize).

Use **Tune** beside an action for its detailed settings. Returning to Library
keeps those edits. Refined actions show the matching combo name, such as
**Fragment Flow · Open**; **Custom settings** identifies settings that no longer
match a built-in style or combo action. Undo/Redo also works for combo changes. Move and swap share the
compositor's movement effect; they are not independent shader slots.

**Pointer drag** controls the NiriFX session's drag response independently of the
window style, with a browser preview in version 0.18 and newer. Select **NiriFX Style**, choose Gentle, Rubber Sheet or
Release Settle, then expand its controls to tune strength, damping and frequency.
**Preserve** leaves
the underlying pointer behavior alone; **Off** stores an explicit zero-strength
override. Changing the shared window style preserves this independent choice.
See [pointer-driven wobble](pointer-wobble.md) for its compositor requirements.

## Preview the sequence

Press **Preview combo** to play the selected opening effect, hold the intact
window and finish with its closing effect. Each action uses its own settings and
duration. Resize and movement join the sequence only when explicitly selected in
the combo. Preserve uses no invented animation: its real behavior needs the
desktop context. Off shows the action's endpoint immediately. Previewing leaves
the saved document and your desktop configuration unchanged.

The movement phase uses the NiriFX movement shader on a synthetic path. It
does not test native compositor movement or desktop springs. See the
[movement guide](movement.md) for live support and the
[desktop motion recordings](desktop-motion.md) for workspace, camera and overview
behavior. If the profile explicitly selects pointer drag with strength above
zero, the combo also plays a scripted drag and release before closing. **Preserve** and **Off** add no pointer phase. Use **Tune** to adjust
any shader action before previewing again.

For an interactive pointer preview, choose **Try pointer drag**, then drag the
sample window, reverse direction and release. **Play drag demo** runs the same
repeatable path used by the combo; Enter or Space also starts it while the canvas
has keyboard focus. **Reset position** recenters the window, and **Return to
effects** or Escape restores the editor view without changing the profile.

These browser previews use the native spring and shader math with synthetic
window content. They do not test compositor input routing, layout, capture
behavior or display latency. With **Reduced motion**, interactive dragging moves
the sample directly without deformation or settling, and combo playback skips
the pointer phase. Previewing is available without a patched compositor.

## Save, export or apply

- **Save to My profiles** asks for a name and keeps an editable document without activation.
  An existing name shows **Replace saved profile** before replacing that Library copy.
- **Export JSON** produces a portable style/profile for every supported setup.
- **Export stock Niri config** produces stock Niri shaders. Movement and pointer nodes are omitted.
- **Export NiriFX session config** appears when pointer settings are selected. It includes
  those settings and any selected movement shader in one movement block, for the
  matching NiriFX compositor only. Neither download activates settings.
- In the installed app, **Review & apply** lists the configuration changes.
  **Apply these changes** activates exactly that reviewed selection.
- **Restore previous** restores this app's most recent change for the same setup and config. Later file edits
  cause a conflict rather than being overwritten.

The **NiriFX session** (`native`) target uses **Select for next login** and reviewed
rollback instead of live Apply/Restore. Each selection retains a separate
binary/configuration pair. See [managed session editing](native-session.md#choose-effects-in-studio)
for baseline semantics and continuous fragment presets.

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
every setup. Live activation requires the verified NiriFX compositor and
the separate **Apply movement** checkbox on the standalone target.
Pointer drag has its own **Apply pointer drag** checkbox, available
only for a verified running pointer renderer on the standalone target. Choosing
another pointer setting clears that consent. An iNiR or Noctalia adapter applies
stock actions only; its portable JSON retains the NiriFX session choices.

## One interface, different configuration owners

| Setup | Launch | Apply path |
| --- | --- | --- |
| Plain Niri, Waybar or a custom shell | `niri-fx studio --target standalone` | Existing standalone setup, reviewed include and snapshots |
| iNiR, including iRiS | `niri-fx studio --target inir --active` | Installed iNiR serializer, external registry and watched animation block |
| DankMaterialShell / Material Shell | Use the NiriFX launcher's Studio entry | Standalone include outside DMS-owned files |
| Noctalia 5 with Niri Animations | Connect the folder/file below | Existing picker's preset folder and target file |
| NiriFX session, with any shell | `niri-fx studio --target native` | New retained bundle and reviewed next-login selection |
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

## iRiS access without source changes

Use `niri-fx studio --target inir` or the NiriFX app launcher for Library,
customization and Restore. Preset registration uses iNiR's external registry;
it does not require changes to the shell's QML source.

The earlier compact Window Motion entry patched the iNiR checkout and could
block shell updates. New installation of that prototype is retired. Existing
users can [review and remove just that integration](desktop-updates.md#removing-the-earlier-compact-iris-entry)
while keeping their profiles and active effects. A future embedded entry needs
a supported upstream extension point.
