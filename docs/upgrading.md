# Updating NiriFX

Read the [changelog](../CHANGELOG.md) before updating. NiriFX is in early
development, so a new version can change commands and preset formats. For a
tagged release, follow the documentation shipped with that version.

## From 0.14 to 0.15

Update before importing the new mixture fields or optional profile `motion`
settings. Single effects remain schema 3; profiles remain schema 1 with additive
optional desktop timing. Old documents keep their existing defaults. Re-register
or re-export shell packs to make the two presets and three profiles selectable.
This does not activate them or change the current style.

Choosing a desktop motion pack intentionally changes three stock springs.
Ordinary presets and profiles preserve those timings. Resize and movement remain
unset in every built-in profile. Review the [setup plan](setup.md) before Apply.

Rebuild the experimental compositor to get contract 1 and frame feedback. Older
experimental binaries still parse movement shaders but cannot pass verified live
activation. NiriFX never replaces the login compositor; use an isolated demo or
an explicitly selected experimental session. [Runtime requirements](../experimental/README.md#runtime-verification-and-output-feedback).

## From 0.13 to 0.14

Seven curated collections and three new pairings require 0.14 or newer. Update the
CLI, then re-register the iNiR pack or re-export your shell pack to expose Geometric
Flow, Ribbon Current and Soft Landing. Existing preset values, document schemas
and the experimental compositor patch are unchanged. Updating does not select a
style or enable resize. Collection filters only change which choices are shown.

## From 0.12 to 0.13

The 0.13 series adds Fragment Wake, Ribbon Transfer and Momentum Glide, shaped
fragment resize, independent movement editing and read-only movement diagnostics.
Update the CLI before importing documents with those movement controls. Re-register
or re-export to expose the three presets in shell pickers. Stock exports continue
to omit experimental movement, and every built-in keeps resize off. Explicit
fragment resize now honors shape, rounding, shrink and size variation.

## From 0.11 to 0.12

Fragment shapes and their four new presets require 0.12 or newer. Update the CLI
before importing those documents. Schema 3 is unchanged; missing shape settings
use square, aspect 1, orientation 0 and emergence 0.28. Existing built-in shaders
are unchanged. Re-register or re-export to expose the new presets in shell pickers.
Installing or updating alone does not change active effects. Resize stays off.
The experimental compositor patch is unchanged from 0.11.

## From 0.10 to 0.11

Vortex Fold, Soft Swirl, Edge Ripple and Torsion Resize require 0.11 or newer.
Update the CLI before importing their documents. The existing preset schema
remains 3; older files receive defaults for the added controls. Existing built-in
values and appearance are unchanged. Re-register or re-export a shell pack to
expose the new styles. Installing the package alone does not update active shaders.

Resize stays off in all built-ins. Distortion still defaults to Ripple Resize;
Edge Ripple and Torsion are separate choices with explicit opt-in profiles. A
missing `distortion_resize_mode` or `resize_twist` uses its default.

The gallery now starts with nine recommended looks. Search, All examples and
existing filtered links still reach every style. The experimental compositor patch
is unchanged from 0.10; regenerate its movement shader to try Vortex Fold.

## From 0.9 to 0.10

The seven [curated pairings](profiles.md#choose-a-finished-pairing) and `--profile`
selection are included in 0.10. Update the CLI and your copied DMS adapter together.
The packaged desktop pickers update with the Python package. Re-register the iNiR
pack or re-export the Noctalia folder to make the pairings available in those pickers.

Integrations can use `list --documents` for complete style/profile documents or
`list --profiles` for pairings only. The existing `list` JSON format remains the
single-effect parameter map. Schema versions and individual effect defaults are
unchanged; every built-in pairing leaves resize and movement untouched.

Re-render or re-register saved effects to pick up the varied-fragment shader
optimization. It preserves the particles and motion; updating the application
alone does not rewrite active shaders. See [updating your effects](#update-your-effects)
for each setup and [performance results](performance.md#varied-fragment-flight-bounds).

For the experimental compositor, 0.10 adds layout-velocity continuity during
interrupted swaps. Build from a fresh 0.10 source directory with
`python3 scripts/build-niri-movement.py --release --test`, keeping the older
patched checkout for rollback. The helper refuses to overwrite an earlier patch
and never replaces the login compositor. Stock open/close effects do not need
this build. See [experimental movement](../experimental/README.md).

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

## From 0.12 to 0.13

Update the CLI or checkout before importing the new movement parameters. The
preset collection now has 88 styles and profiles. Re-register iNiR/iRiS or re-export your
Noctalia pack to add Fragment Wake, Ribbon Transfer and Momentum Glide. Existing
selection and restore snapshots remain under your control.

Studio's **Movement (experimental shader)** preview uses the same GLSL as the
pinned compositor. **Include experimental movement in JSON** stores a separate
action; stock exports omit it. Use `scripts/nested-demo.py --custom PATH.json`
to try an exported movement profile in isolation. The pinned patch is unchanged.

Resize remains off in every built-in style. Explicit fragment resize effects now
honor shapes, orientation, rounding, shrink and size variation. The new shaped
profiles enable resize deliberately; previewing one does not activate it. Export
your current custom profile before editing if you want to preserve its settings.
