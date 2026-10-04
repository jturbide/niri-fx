# Compatibility and next integrations

NiriFX targets the **Niri Wayland compositor**. A desktop shell
provides settings and launchers; it does not render these application windows.
The iNiR/iRiS preset adapter is optional: `render` and the offline Studio preview
do not need iNiR installed.

| Setup | Current path | Tested setup and limitations |
| --- | --- | --- |
| Niri + iNiR/iRiS | Native preset registration and Studio save | iNiR/iRiS c08bb92 gallery selection, apply and restore tested with Quickshell 0.3.1. |
| Standalone Niri | Generated KDL include; Studio exports | Generated configs validated with Niri 26.04. |
| Niri + DankMaterialShell | [Launcher adapter](dms.md) or KDL include | DMS 1.6.2 launcher selection, apply and undo tested in a component host. |
| Niri + Noctalia 5 | [Exported KDL preset pack](noctalia.md) for its existing Niri Animations plugin | All 91 current style/profile includes validated; Noctalia 5.2.1 picker selected styles and returned to base in an isolated UI test. |
| Niri + custom Quickshell | [Reusable picker](quickshell.md), or standalone config | Quickshell 0.3.1 controller/view and real keyboard workflow tested in isolated hosts; shell-specific embedding remains the integrator's responsibility. |
| Niri + GTK 4 / AGS 3 | [GTK picker and reusable widget](gtk.md) | GJS 1.88.1 / GTK 4.22.5 and AGS source v3.1.2 keyboard Apply/Undo tested in isolated hosts. Full Astal shell embedding and GTK 3 are not covered. |
| Niri + Waybar | [Standalone Niri](standalone.md); optional CLI launcher | No native UI adapter required for rendering. |
| Niri + another shell | The same shell-independent KDL include | Check include ordering and that shell's config ownership. |
| DMS on another compositor | No current NiriFX backend | Installing a shell does not supply Niri's shader interface. |
| Move/swap effects | Pinned experimental Niri patch | Separate nested demo only; shell plugins cannot add this rendering hook. |
| Pointer-driven wobble | Optional pointer extension to the pinned build | [Native prototype](pointer-wobble.md); portable profiles and Studio controls in version 0.18 and newer. Live Apply requires a verified standalone session. |

See [tested versions and reproduction details](validation.md#workflow-and-compositor-scenarios)
for the scope of each integration check.

The standard preset pack leaves existing resize behavior unchanged. Add a resize
style with `--resize` or Studio's checkbox.

## Niri + DankMaterialShell

DMS documents its Niri integration as several included KDL files for layout,
colors and keybindings. Keep NiriFX in its own file, outside the `dms/`
directory, so DMS does not own that file. This is an integration recommendation
based on the [official compositor setup](https://danklinux.com/docs/dankmaterialshell/compositors#niri-configuration),
the optional launcher adapter automates the reversible standalone setup.

From this checkout:

```sh
python3 -m niri_fx render --preset explosion \
  > /tmp/nirifx.kdl
niri validate -c /tmp/nirifx.kdl
```

After validation succeeds, copy it with a backup:

```sh
mkdir -p ~/.config/niri/nirifx
cp --backup=numbered /tmp/nirifx.kdl ~/.config/niri/nirifx/animations.kdl
```

Back up your main config before editing it.
Add this **once**, after the existing animation settings and DMS includes in
`~/.config/niri/config.kdl`:

```kdl
include "nirifx/animations.kdl"
```

Then run `niri validate`. To switch styles, generate, validate and copy again with
a different `--preset`. To revert, remove the NiriFX include. Niri merges
included configuration in order; a later animation override takes precedence.
See [Niri includes](https://niri-wm.github.io/niri/Configuration:-Include.html).
Avoid combining this include with another animation preset manager for the
same open/close settings.

For visual tuning without the iNiR save adapter:

```sh
python3 -m niri_fx preview --output /tmp/nirifx-preview.html
xdg-open /tmp/nirifx-preview.html
```

Use **Export Niri config**, then put the exported contents in the NiriFX
include file. **Save to iRiS** is specific to iNiR; it is not a DMS save action.
Choose the standalone save target for a KDL download; iRiS registration requires iNiR.

## Shell adapters

The optional [DMS launcher adapter](dms.md) provides searchable built-in
styles, Studio and reversible apply/undo. Its real QML component passed an
isolated Quickshell/CLI test and the actual DMS 1.6.2 launcher modal passed visual
search, selection, Undo and Studio launch in a test host. See [workflow acceptance](validation.md#workflow-and-compositor-scenarios).
Noctalia reuses its existing picker through [export-pack](noctalia.md). Studio's
save-target selector also downloads individual Noctalia or standalone KDL files,
including independent profiles. Only the iNiR target writes its native registry.

Shell integrations share the same CLI and effect model. Quickshell is a toolkit;
there is no universal settings registry shared by every shell. Native movement
still needs Niri rendering support regardless of shell.

Choose a [setup scenario](scenarios.md). The [roadmap](roadmap.md) ranks future
full-shell embedding, Caelestia and ML4W work; Waybar needs no shader adapter.
