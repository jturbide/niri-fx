# Compatibility and next integrations

Checked on 2026-10-02. NiriFX (formerly Niri Fragments) targets **Niri**. A desktop shell
provides settings and launchers; it does not render these application windows.
The iNiR/iRiS preset adapter is optional: `render` and the offline Studio preview
do not need iNiR installed.

| Setup | Current path | Validation / limitation |
| --- | --- | --- |
| Niri + iNiR/iRiS | Native preset registration and Studio save | Tested locally. |
| Standalone Niri | Generated KDL include; Studio exports | Generated configs validated with Niri 26.04. |
| Niri + DankMaterialShell | [Launcher adapter](dms.md) or KDL include | Real QML/CLI apply/restore tested; full DMS launcher UI acceptance pending. |
| Niri + Noctalia 5 | [Exported KDL preset pack](noctalia.md) for its existing Niri Animations plugin | All 47 files validated; Noctalia 5.2.1 picker selected styles and returned to base in an isolated UI test. |
| Niri + another shell | The same shell-independent KDL include | Check include ordering and that shell's config ownership. |
| DMS on another compositor | No current NiriFX backend | Installing a shell does not supply Niri's shader interface. |
| Move/swap effects | Pinned experimental Niri patch | Separate nested demo only; shell plugins cannot add this rendering hook. |

Resize fragments are **opt-in everywhere**. The standard preset pack and KDL
exports change only opening and closing. Enable resize deliberately with
`--resize` or Studio's checkbox.

## Niri + DankMaterialShell

DMS documents its Niri integration as several included KDL files for layout,
colors and keybindings. Keep NiriFX in its own file, outside the `dms/`
directory, so DMS does not own that file. This is an integration recommendation
based on the [official compositor setup](https://danklinux.com/docs/dankmaterialshell/compositors#niri-configuration),
the optional launcher adapter automates the reversible standalone setup.

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
a different `--preset`. To revert, remove the NiriFX include. Niri merges
included configuration in order; a later animation override takes precedence.
See [Niri includes](https://niri-wm.github.io/niri/Configuration:-Include.html).
Avoid combining this include with another animation preset manager for the
same open/close settings.

For visual tuning without the iNiR save adapter:

```sh
python3 -m niri_fx preview --output /tmp/fragments-preview.html
xdg-open /tmp/fragments-preview.html
```

Use **Export Niri config**, then put the exported contents in the NiriFX
include file. **Save to iRiS** is specific to iNiR; it is not a DMS save action.
Choose the standalone save target for a KDL download; iRiS registration requires iNiR.

## Shell adapters

The optional [DMS launcher adapter](dms.md) now provides searchable built-in
styles, Studio and reversible apply/undo. Its real QML component passed an
isolated Quickshell/CLI test; full launcher UI acceptance is tracked separately.
Noctalia reuses its existing picker through [export-pack](noctalia.md). Studio's
save-target selector also downloads individual Noctalia or standalone KDL files,
including independent profiles. Only the iNiR target writes its native registry.

Shell integrations share the same CLI and effect model. Quickshell is a toolkit;
there is no universal settings registry shared by every shell. Native movement
still needs Niri rendering support regardless of shell.
