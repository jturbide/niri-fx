# Choose your setup

**NiriFX works standalone. Quickshell is optional.** Use [Studio's Library](library.md)
to choose styles for each action, preview your combo and review changes before
applying them. Niri renders the window effects; a shell or bar only supplies
buttons, launchers and settings. Studio also previews synthetic windows without
a running Niri session. Prefer a terminal? Use the [terminal preset guide](terminal.md).

Start from a checkout with Python 3.10+ and a WebGL browser:

```sh
git clone https://github.com/jturbide/niri-fx.git
cd niri-fx
python3 -m niri_fx studio --target standalone
```

This opens the editor and changes no active animations. Chromium supplies the
app-style window; other browsers open a normal tab. The commands below assume
you are still in the checkout. [Install the CLI](getting-started.md#install-and-open-library)
to use `niri-fx` from elsewhere in place of `python3 -m niri_fx`.

| Your scenario | Starting command | What happens next |
| --- | --- | --- |
| Preview only, including a machine without Niri | `python3 -m niri_fx studio --target standalone` | Tune synthetic previews; download KDL or editable JSON. |
| NiriFX session, with any shell | `python3 -m niri_fx studio --target native` | After [session setup](native-session.md), choose all supported effects in Studio. Apply live on a matching session or select them for the next login. |
| Plain Niri, with any bar or no bar | `python3 -m niri_fx studio --target standalone` | Choose styles, then Review & apply to a managed include. [Standalone guide](standalone.md). |
| Niri + iNiR / iRiS | `python3 -m niri_fx studio --target inir` | Review & apply through the installed helper; opening shell settings is optional. [iNiR guide](getting-started.md#inir-and-iris). |
| Niri + DankMaterialShell | `python3 -m niri_fx studio --target standalone` | Use a managed include or the optional `fx` launcher. [DMS guide](dms.md). |
| Niri + Noctalia Niri Animations | `python3 -m niri_fx studio --target noctalia --preset-dir ~/.config/niri/nirifx-presets --picker-file ~/.config/niri/animations.kdl` | Use your connected preset folder and target file. For first-time connection, follow the [Noctalia guide](noctalia.md). |
| Niri + custom Quickshell | `python3 -m niri_fx studio --target standalone` | The shared Studio works independently of the shell. An optional [Quickshell picker](quickshell.md) is available. |
| Niri + GTK 4 / AGS 3 | `python3 -m niri_fx studio --target standalone` | Use the shared Studio or the optional [GTK picker and AGS widget](gtk.md). |
| Niri + Waybar or another UI | `python3 -m niri_fx studio --target standalone` | The same Niri include works independently of the UI. [Custom shell/bar guide](custom-shells.md). |
| A config managed by Nix/Home Manager or another generator | `python3 -m niri_fx render --preset balanced` | Put the output into that manager's source and include it after base animations; avoid editing generated files with `setup`. |
| Different effects on opening and closing | `python3 -m niri_fx studio` | Choose Open and Close styles separately, or start from Combos. [Profiles guide](profiles.md). |
| Hyprland, GNOME or KWin | No NiriFX desktop backend | Studio previews still work; exported Niri shaders cannot be installed into these compositors. |

Use one animation manager at a time. A late standalone include overrides earlier
iRiS/Noctalia choices. Registration, previewing and pack export do not activate
effects. Use Studio's reviewed Apply or the terminal guide when ready.

For nonstandard locations, use `--config`, `--state`, `--registry` or `--inir-root`
as appropriate; see [setup and restore](setup.md). Future native UI integrations
are prioritized in the [roadmap](roadmap.md).
