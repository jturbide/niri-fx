# Choose your setup

**NiriFX works standalone. Quickshell is optional.** Niri renders the window
effects; a shell or bar only supplies buttons, launchers and settings. Studio
also previews synthetic windows without a running Niri session.

Start from a checkout with Python 3.10+ and a WebGL browser:

```sh
git clone https://github.com/jturbide/niri-fx.git
cd niri-fx
python3 -m niri_fx studio --target standalone
```

This opens the editor and changes no active animations. Chromium supplies the
app-style window; other browsers open a normal tab. The commands below assume
you are still in the checkout. [Install the CLI](getting-started.md#get-the-source-and-preview)
if you want to run it from elsewhere.

| Your scenario | Starting command | What happens next |
| --- | --- | --- |
| Preview only, including a machine without Niri | `python3 -m niri_fx studio --target standalone` | Tune synthetic previews; download KDL or editable JSON. |
| Plain Niri, with any bar or no bar | `python3 -m niri_fx setup --target standalone --preset balanced` | Review the plan, then add `--apply`. [Standalone guide](standalone.md). |
| Niri + iNiR / iRiS | `python3 -m niri_fx register --dry-run` | Register, then select a style in iRiS. [iNiR guide](getting-started.md#inir-and-iris). |
| Niri + DankMaterialShell | `python3 -m niri_fx studio --target standalone` | Use a managed include or the optional `fx` launcher. [DMS guide](dms.md). |
| Niri + Noctalia Niri Animations | `python3 -m niri_fx export-pack --output ~/.config/niri/nirifx-presets` | Review/export the pack and connect the existing picker. [Noctalia guide](noctalia.md). |
| Niri + Quickshell | `python3 -m niri_fx picker` | Browse styles, load profiles, review/apply and Undo. [Quickshell picker](quickshell.md). |
| Niri + AGS/Astal or Waybar | `python3 -m niri_fx setup --target standalone --preset balanced` | The same Niri include works independently of the UI. [Custom shell/bar guide](custom-shells.md). |
| A config managed by Nix/Home Manager or another generator | `python3 -m niri_fx render --preset balanced` | Put the output into that manager's source and include it after base animations; avoid editing generated files with `setup`. |
| Different effects on opening and closing | `python3 -m niri_fx studio --target standalone` | Enable Independent action effects. [Profiles guide](profiles.md). |
| Native movement/swap experiment | `python3 scripts/nested-demo.py` | Requires the separately built patched compositor. [Experimental guide](../experimental/README.md). |
| Hyprland, GNOME or KWin | No NiriFX desktop backend | Studio previews still work; exported Niri shaders cannot be installed into these compositors. |

Use one animation manager at a time. A late standalone include overrides earlier
iRiS/Noctalia choices. Registration, previewing and pack export do not select a
style; standalone `setup --apply` does. Resize remains opt-in on every path.

For nonstandard locations, use `--config`, `--state`, `--registry` or `--inir-root`
as appropriate; see [setup and restore](setup.md). Future native UI integrations
are prioritized in the [roadmap](roadmap.md).
