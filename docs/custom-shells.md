# Custom shells and bars on Niri

Use [standalone setup](standalone.md) first. It works through Niri's animation
configuration, independently of the UI toolkit. No custom shell adapter is
required for the effects themselves.

## Waybar

[Waybar](https://github.com/Alexays/Waybar) is a bar. It neither renders application
windows nor supplies Niri's shader hooks. There is nothing to port for ordinary
NiriFX use. An optional bar button can open Studio, just like an application launcher.

The same distinction applies to other bars and widgets: their own layer-shell
surfaces are not the application open/close animations targeted by this pack.

## Custom Quickshell and AGS/Astal

[Quickshell](https://quickshell.org/), [AGS](https://aylur.github.io/ags/) and
[Astal](https://aylur.github.io/astal/) provide tools for building desktop UIs.
They have no single shared animation-preset registry. A custom UI can use these
existing commands after NiriFX is installed on the session's `PATH`:

```sh
niri-fx studio --target standalone
niri-fx list
niri-fx families
niri-fx setup --target standalone --preset balanced --no-launcher
niri-fx setup --target standalone --preset balanced --no-launcher --apply
```

Use the executable's absolute path if it lives in a virtual environment that
your desktop session does not activate. `list` and `families` produce JSON;
`studio` opens the editor, and `setup --apply` activates the chosen preset.
An adapter should pass arguments as an array, restrict preset IDs to the loaded
catalog, display failures and keep a dedicated `--state` directory for Undo.
The [DMS adapter](dms.md) demonstrates that contract.

An optional Niri binding, assuming `niri-fx` is on the session's PATH:

```kdl
binds {
    Mod+Shift+F { spawn "niri-fx" "studio" "--target" "standalone"; }
}
```

Merge the binding into your existing `binds` block and choose an unused shortcut.
It only opens Studio. Custom Quickshell and AGS/Astal picker UIs are future work;
the generic CLI/config path does not imply those UIs have been tested.

## Caelestia and ML4W

The currently documented [Caelestia shell](https://github.com/caelestia-dots/shell)
uses Hyprland, and [ML4W](https://github.com/mylinuxforwork/dotfiles) describes its
dotfiles as a Hyprland setup. A new settings button would not make Niri shaders
work in Hyprland. If you run a separate Niri session, use its standalone NiriFX
configuration and keep the Hyprland configuration separate.

We do not currently claim a Caelestia/ML4W native integration. See the
[prioritized roadmap](roadmap.md) for the prerequisites and next steps.
