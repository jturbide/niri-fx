# Updating NiriFX

Read the [changelog](../CHANGELOG.md) before updating. NiriFX is in early
development, so a new version can change commands and preset formats. For a
tagged release, follow the documentation shipped with that version. The
[stability policy](stability.md) describes the planned 1.x compatibility contract;
that freeze has not happened yet.

For shell or compositor upgrades, see [Desktop updates](desktop-updates.md).
Users of the earlier compact iRiS source integration should follow its reviewed
removal path before updating the shell. Normal preset registration remains
available without modifying iNiR's checkout.

## From 0.18 to 0.19

Install the verified wheel in the same environment and reopen Studio:

```sh
.venv/bin/python -m pip install --no-index --no-deps --upgrade ./niri_fx-0.19.0-py3-none-any.whl
.venv/bin/niri-fx studio --active
```

Installation preserves existing files, Library profiles, favorites, registrations
and Restore history. Keep the NiriFX state directory when updating.

Version 0.19 exports schema 2 profiles with independent
**Preserve / NiriFX Style / Off** choices. Existing schema 1 profiles still load
with the same behavior and normalize to schema 2 when inspected or saved.
Single-style documents remain schema 3. Version 0.18 cannot read schema 2;
keep an original JSON copy if you need to return to it.

Preserve means the underlying Niri or shell configuration. When replacing an
active NiriFX profile, Preserve removes that profile's action override. It does
not copy Niri's factory settings or keep the previous NiriFX action.

The experimental compositor contracts move to version 2. Rebuild the matching
movement/pointer variant before native Apply. The old executable is left intact;
do not replace a login compositor while testing. Per-action movement `off` now
affects timed movement only; use explicit pointer strength 0 to disable dragging
and global animation `off` to suppress both. Explicit preservation flags keep
one native action from resetting its sibling's existing settings.

Before downgrading, use the current version's Restore for active native changes
and export profiles you want to retain. A lower native contract is rejected for
new activation. A package update remains separate from changing your compositor.

## From 0.17 to 0.18

Install the verified 0.18 wheel in the same virtual environment, then reopen
Studio:

```sh
.venv/bin/python -m pip install --no-index --no-deps --upgrade ./niri_fx-0.18.0-py3-none-any.whl
.venv/bin/niri-fx studio --active
```

Existing schema 3 styles and schema 1 profiles need no conversion. Updating the
package preserves exported JSON, **My profiles**, favorites, shell registrations,
active configuration and both CLI and Library Restore histories. Keep
`$XDG_STATE_HOME/niri-fx` (normally `~/.local/state/niri-fx`): reinstalling the
package is separate from restoring or deleting its saved state. Existing
launchers remain valid when the installation stays at the same path.

Profiles can now include optional `pointer` settings. Studio previews dragging
and includes it in combo previews when selected; saving or previewing a profile
does not activate those settings. Old profiles inherit their existing pointer
behavior, and built-in profiles leave pointer settings unset. Existing resize
behavior remains unchanged unless the profile selects resize. Stock exports omit
movement shaders and pointer nodes, even when pointer
strength is explicitly zero. See the [pointer guide](pointer-wobble.md).

Native pointer activation requires the separate pointer extension for the pinned
experimental Niri build, standalone mode, and a verified running renderer.
Rebuild from the 0.18 source with
`python3 scripts/build-niri-movement.py --pointer-wobble --release --test`, using
a fresh 0.18 source directory if the helper detects an earlier patch. Keep your previous
build for rollback. The helper never replaces the login compositor. Existing
movement-only builds can continue to use timed movement; they cannot activate
pointer settings. Review the [native limitations](pointer-wobble.md) before
choosing an experimental session.

Restore now checks compositor support before reintroducing a previous native
pointer or movement selection. Use the matching executable through
`--niri-binary PATH` and the supported running session. Restoring stock settings
remains available; a rejected native Restore leaves configuration and snapshots
untouched.

Before downgrading to 0.17, use 0.18 to restore any active pointer configuration
you want to undo and export profiles you want to keep. Version 0.17 cannot read
profiles containing the new `pointer` field. Keep their JSON separately, or make
a copy without that field for 0.17; do not overwrite your only copy. Reinstall
the verified 0.17 wheel with `--force-reinstall` and keep the state directory.
Updating the Python package does not change the compositor executable.

## From 0.16 to 0.17

The shared [Library](library.md) becomes Studio's starting view. Choose a finished
look, combine different styles for each action, preview the combination, or open
**Customize** for the full controls. Existing commands and portable document
formats remain supported: schema 3 styles and schema 1 profiles.

Replace the package in the same virtual environment, then reopen Studio. After
verifying the release's `SHA256SUMS`, install its wheel:

```sh
.venv/bin/python -m pip install --no-index --no-deps --upgrade ./niri_fx-0.17.0-py3-none-any.whl
.venv/bin/niri-fx studio --active
```

Use the Python executable from your installation if its virtual environment is
elsewhere. Existing launchers keep working when that environment stays at the
same path. Updating the package leaves active shaders, shell registry entries,
saved JSON, favorites and restore snapshots untouched. There is no need to
re-register a pack merely to use the Library.

In iNiR/iRiS, recognized registered custom styles appear with **from shell**.
Import an exported JSON document and choose **Save to My profiles** to create a
Library-owned copy. Copy, rename and removal operate on those copies; registered
shell entries remain managed by the shell. Standalone and connected Noctalia
setups use the same Library with their own reviewed Apply/Restore path. Existing
DMS and other picker workflows remain available. See the [connection guide](library.md#one-interface-different-configuration-owners).

Keep the NiriFX state directory when updating:
`$XDG_STATE_HOME/niri-fx`, normally `~/.local/state/niri-fx`. It contains Studio
favorites, **My profiles**, CLI setup snapshots and separate Library Apply
snapshots. CLI snapshots still restore through `niri-fx restore`; Library Apply
snapshots restore through **Restore previous** or `niri-fx studio --restore` using
the same target and configuration. Existing custom JSON files remain usable
without conversion.

Existing resize settings remain unchanged unless a profile includes resize.
Stock Niri provides opening, closing and resize; custom movement/swap shaders
require the verified experimental compositor. Combo previews demonstrate selected actions and do not activate
them. The experimental patch is unchanged from 0.16.

To return to 0.16, use the current app to restore any Library Apply you want to
undo, then reinstall the verified 0.16 wheel in the same environment with
`--force-reinstall`. Keep exported JSON and the state directory. The older Studio
does not provide My profiles or the new combo workflow, but the documents remain
available for export/import when you update again.

## From 0.15 to 0.16

Update the CLI and refresh registered or exported shell packs to add Fragments
Motion, Ribbons Motion and Elastic Motion. Existing selections and preset settings
stay unchanged. Each built-in set includes stock workspace, camera and overview
springs while leaving resize and experimental movement unset.

Studio suggests a matching optional action without enabling it. The CLI's
`profile --action-set` creates a base document unless `--include-resize` or
`--include-movement` is explicitly passed. Resize-only and native example files
already include their named actions; review them before applying.
[Action-set guide](action-sets.md).

Document schemas and the experimental compositor patch are unchanged. A 0.15
experimental build remains usable; stock exports continue to omit movement.

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
to omit experimental movement, and built-ins preserve existing resize settings. Explicit
fragment resize now honors shape, rounding, shrink and size variation.

## From 0.11 to 0.12

Fragment shapes and their four new presets require 0.12 or newer. Update the CLI
before importing those documents. Schema 3 is unchanged; missing shape settings
use square, aspect 1, orientation 0 and emergence 0.28. Existing built-in shaders
are unchanged. Re-register or re-export to expose the new presets in shell pickers.
Installing or updating alone does not change active effects or resize settings.
The experimental compositor patch is unchanged from 0.11.

## From 0.10 to 0.11

Vortex Fold, Soft Swirl, Edge Ripple and Torsion Resize require 0.11 or newer.
Update the CLI before importing their documents. The existing preset schema
remains 3; older files receive defaults for the added controls. Existing built-in
values and appearance are unchanged. Re-register or re-export a shell pack to
expose the new styles. Installing the package alone does not update active shaders.

Built-ins preserve existing resize settings. Distortion still defaults to Ripple Resize;
Edge Ripple and Torsion have dedicated resize profiles. A
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
not change active effects or existing resize behavior. Keep your custom JSON
and snapshots.

## From 0.7 to 0.8

Schema 3 styles and schema 1 action profiles remain supported. Back up custom
JSON and restore snapshots before updating. New defaults, including the monochrome
Ember palette, take effect only when you regenerate or select those presets.
Your active files, including resize settings, are not rewritten by a package upgrade.

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
only when you explicitly regenerate or save them.
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
