# Updating NiriFX

Read the [changelog](../CHANGELOG.md) before updating. NiriFX is in early
development, so a new version can change commands and preset formats. For a
tagged release, follow the documentation shipped with that version.

## Update the application

From a clean source checkout:

```sh
git pull --ff-only
```

If you installed into a virtual environment, reinstall from the updated checkout:

```sh
.venv/bin/python -m pip install .
```

Restart Studio to load the updated editor. If you move the checkout, recreate
its optional desktop launcher. Updating the application does not automatically
change the effect currently running on your desktop.

## Update your effects

- **Standalone Niri:** run setup again with your chosen preset or custom JSON.
  Review the plan before adding `--apply`. If you manage the include manually,
  regenerate it and run `niri validate` after replacement.
- **iNiR/iRiS:** register the updated pack, then select the style again in Settings.
  If the old effect is recognized as custom, provide the same `--base` you used
  originally. Your other presets and saved custom styles are preserved.
- **DMS:** update the adapter copy if its files changed, then select a preset
  from the launcher. Review local modifications before replacing that copy.
- **Noctalia:** export the updated pack and select the preset again. See
  [updating the pack](noctalia.md#update-or-undo) if you edited an exported file.

Keep exported custom styles and restore snapshots. Existing custom shaders change
only when you explicitly regenerate or save them. Fragment resize remains opt-in.
Use [setup and restore](setup.md) to inspect or undo managed changes.

## Preset formats and commands

Use `niri-fx` or `python3 -m niri_fx`. Single-style JSON uses **schema 3** with
exactly `schema`, `name` and `effect` at the top level. Independent profiles use
kind `profile`, schema 1; see [profiles](profiles.md). Unknown fields and malformed
names are rejected rather than ignored.

Older command aliases and preset formats are not supported by the current
version. Re-export or recreate an older preset for the current format, keeping
its original file until the replacement works. If an older distribution is
installed in the same virtual environment, remove it before installing NiriFX.

For custom file locations, see [setup options](setup.md) and the
[iNiR integration reference](integration.md).
