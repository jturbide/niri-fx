# Compatibility and next integrations

Checked on 2026-10-02. NiriFX (formerly Niri Fragments) targets **Niri**. A desktop shell
provides settings and launchers; it does not render these application windows.
The iNiR/iRiS preset adapter is optional: `render` and the offline Studio preview
do not need iNiR installed.

| Setup | Current path | Validation / limitation |
| --- | --- | --- |
| Niri + iNiR/iRiS | Native preset registration and Studio save | Tested locally. |
| Standalone Niri | Generated KDL include; Studio exports | Generated configs validated with Niri 26.04. |
| Niri + DankMaterialShell | The same KDL include and exported presets | Compatible at the Niri configuration layer; DMS-specific UI/runtime acceptance is pending. |
| Niri + Noctalia 5 | [Exported KDL preset pack](noctalia.md) for its existing Niri Animations plugin | File/include contract validated; Noctalia UI acceptance pending. |
| Niri + another shell | The same shell-independent KDL include | Check include ordering and that shell's config ownership. |
| DMS on another compositor | No current Fragments backend | Installing a shell does not supply Niri's shader interface. |
| Move/swap effects | Pinned experimental Niri patch | Separate nested demo only; shell plugins cannot add this rendering hook. |

Resize fragments are **opt-in everywhere**. The standard preset pack and KDL
exports change only opening and closing. Enable resize deliberately with
`--resize` or Studio's checkbox.

## Niri + DankMaterialShell

DMS documents its Niri integration as several included KDL files for layout,
colors and keybindings. Keep Fragments in its own file, outside the `dms/`
directory, so DMS does not own that file. This is an integration recommendation
based on the [official compositor setup](https://danklinux.com/docs/dankmaterialshell/compositors#niri-configuration),
not a claim that a DMS plugin has been shipped or tested.

From this checkout:

```sh
python3 -m niri_fx render --preset explosion \
  > /tmp/fragments.kdl
niri validate -c /tmp/fragments.kdl
```

After validation succeeds, copy it with a backup:

```sh
mkdir -p ~/.config/niri/nirifx
cp --backup=numbered /tmp/fragments.kdl ~/.config/niri/nirifx/animations.kdl
```

Back up your main config before editing it.
Add this **once**, after the existing animation settings and DMS includes in
`~/.config/niri/config.kdl`:

```kdl
include "nirifx/animations.kdl"
```

Then run `niri validate`. To switch styles, generate, validate and copy again with
a different `--preset`. To revert, remove the Fragments include. Niri merges
included configuration in order; a later animation override takes precedence.
See [Niri includes](https://niri-wm.github.io/niri/Configuration:-Include.html).
Avoid combining this include with another animation preset manager for the
same open/close settings.

For visual tuning without the iNiR save adapter:

```sh
python3 -m niri_fx preview --output /tmp/fragments-preview.html
xdg-open /tmp/fragments-preview.html
```

Use **Export Niri config**, then put the exported contents in the Fragments
include file. **Save to iRiS** is specific to iNiR; it is not a DMS save action.
The regular Studio app can also export, but its save adapter still expects iNiR.

## Recommended scope

Noctalia can reuse its existing picker through `export-pack`; see the
[setup guide](noctalia.md). A possible next integration is a **small DMS plugin for Niri users**: a preset
picker, an explicitly opt-in resize switch, restore action, and an Open Studio
button. It should reuse the Python generator, validate KDL before replacing its
own file, and detect the compositor before enabling any controls. It should
preserve other animation timings and avoid editing DMS-generated config.

DMS exposes QML plugins with settings, launcher actions and Control Center
widgets, so that is a supported extension route rather than a shell fork.
See the [official plugin overview](https://danklinux.com/docs/dankmaterialshell/plugins-overview).
This adapter is a recommendation, not an implemented feature in this release.

Keep one Niri renderer and add shell adapters around it. A Hyprland, KWin or
GNOME version would be a separate compositor backend with its own lifecycle,
texture, damage and input contracts. Defer those ports until the current Niri
effects and experimental movement behavior are settled. The **NiriFX** name reflects multiple effect families while retaining Niri as
the supported renderer. Shell support does not imply support for another compositor.
