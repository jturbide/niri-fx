# Updating NiriFX

Read the [changelog](../CHANGELOG.md) before updating. NiriFX is in early
development, so a new version can change commands and preset formats. For a
tagged release, follow the documentation shipped with that version.

## Current development version (after 0.9)

The seven [curated pairings](profiles.md#choose-a-finished-pairing) and `--profile`
selection require a checkout of current `main`; they are not in the 0.9.0 release
assets. Update the CLI and your copied DMS adapter together. The packaged desktop
pickers update with the Python package. Re-register the iNiR pack or re-export the
Noctalia folder to make the pairings available in those pickers.

Integrations can use `list --documents` for complete style/profile documents or
`list --profiles` for pairings only. The existing `list` JSON format remains the
single-effect parameter map. Schema versions and individual effect defaults are
unchanged; every built-in pairing leaves resize and movement untouched.

## From 0.8 to 0.9

Run `niri-fx` in a terminal for guided preset selection. With redirected input or
output, it prints help instead. Existing `list`, `doctor`, `setup` and `restore`
JSON workflows remain available; add `--text` to `list` or `doctor` for readable
output. The terminal guide omits the Studio launcher unless explicitly requested.

The optional [Quickshell](quickshell.md) and [GTK](gtk.md) pickers ship in the
package. Install only the chosen UI's toolkit; neither is needed for the CLI.
Their Undo histories are separate from CLI setup. `inspect --custom` validates
portable JSON, and `setup --expect-plan` binds activation to a reviewed plan.

Preset values, shader sources and the experimental compositor patch are unchanged
from 0.8. Schema 3 styles and schema 1 profiles remain supported. Upgrading does
not change active effects; resize stays opt-in. Keep your custom JSON and snapshots.

## From 0.7 to 0.8

Schema 3 styles and schema 1 action profiles remain supported. Back up custom
JSON and restore snapshots before updating. New defaults, including the monochrome
Ember palette, take effect only when you regenerate or select those presets.
Your active files are not rewritten by a package upgrade. Resize stays opt-in.

The experimental movement patch changed. Rebuild it from the 0.8 source using
`python3 scripts/build-niri-movement.py --release --test`; an older patched source
checkout is deliberately rejected. Keep that checkout and use a fresh 0.8 source
directory for a separate build. The build helper never replaces the login compositor.

[Web Studio](web-studio.md) and the gallery track `main`. Use the local editor from
your installed tag for version-specific exports. Keep a JSON copy of shared settings.

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
