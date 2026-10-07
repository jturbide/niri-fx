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

## Custom Quickshell

Use `niri-fx picker` for a standalone desktop window, or embed the packaged QML
controller and view into your settings page. The [Quickshell guide](quickshell.md)
includes an example and documents reviewed Apply, JSON profiles, resize consent
and dedicated Undo history. Existing iRiS, DMS and Noctalia users can keep their
own pickers; choose one owner for Niri's animation configuration.

## GTK 4, AGS and Astal

Use `niri-fx picker --toolkit gtk` for a standalone GJS/GTK window, or embed its
ordinary GTK 4 widget in a settings page. The [GTK guide](gtk.md) includes a tested
AGS 3 entry point, lifecycle rules, resize consent and dedicated Undo history.
GTK 3 and older AGS APIs can use the standalone launcher or CLI instead.

## Other custom UIs

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
It only opens Studio. The generic CLI/config path does not imply that every
shell-specific UI has been tested.
