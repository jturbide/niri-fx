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

For managed NiriFX sessions in version 0.20 and newer, use
[tool-runtime updates](tool-updates.md) to keep CLI, Studio and the login launcher
on the same installation. That workflow retains complete environments for
rollback; the historical in-place package commands below describe their releases.

The 0.20 build tools use [isolated native candidates](../experimental/README.md#isolated-build-candidates).
Use the manifest selection printed after building; newer attempts no longer
replace the fixed manifests used by older releases and launchers. The versioned
upgrade notes below describe their original release workflows.

## From 0.22.0 to 0.22.1

0.22.1 fixes interrupted package-adoption recovery and startup diagnostics.
Effect defaults, compositor patches and document schemas are unchanged. Keep
saved profiles, Restore history and retained runtimes in place.

Update your Arch package through your normal AUR workflow. An adopted user's
CLI, Studio and next-login session still use their retained tools until an
explicit adoption succeeds. Use the newly installed system command to review
the update, then apply the exact fingerprint it reports:

```sh
/usr/bin/niri-fx native adopt
/usr/bin/niri-fx native adopt --apply --expect-plan REVIEWED_SHA256
```

Omit `--config` for an existing selection. Adoption preserves its saved recipe,
shader bytes and shared or frozen settings mode, with previous selections kept
for rollback. Save open drafts and reopen Studio after adopting; the running
compositor continues until logout.

If an earlier adoption was interrupted, review the same adoption command again
with 0.22.1. It resumes matching partial copies and refuses changed or unexpected
files. Use the new fingerprint rather than a review made before the interruption.
Unavailable Python or compositor libraries still require repairing system
dependencies; see [recovery guidance](arch-linux.md#recover-after-a-dependency-update).

For a managed wheel or source installation, prepare 0.22.1 in a new persistent
environment and use [tool-runtime updates](tool-updates.md). Keep the previous
environment intact. Moving to an Arch package instead follows the
[source-managed migration](#from-a-source-managed-session-to-an-arch-package) below.

## From 0.21 to 0.22

Arch users keep the same package choice: `niri-fx` or `niri-fx-git`. Update through
your AUR helper. Both now build and install the complete compositor and login
entry alongside Studio, CLI and presets, so the first build takes longer than
0.21. Stock Niri and your current settings remain in place.

To keep using stock Niri, reopen Studio and continue normally. If no native bundle
is selected, follow [first adoption](arch-linux.md#use-the-nirifx-session) to use
the included session. An existing source-managed session follows
[the migration below](#from-a-source-managed-session-to-an-arch-package).
No additional package or shell-source modification is needed.

After subsequent package updates, run `/usr/bin/niri-fx native adopt` without
`--config`, review the plan and apply its fingerprint. This preserves the saved
effects and shared or frozen settings mode. Keep previous retained copies for
rollback and reopen Studio after the tools selection changes.

For wheel installations, install the 0.22 wheel in a new persistent environment
and use [managed tool updates](tool-updates.md) if that environment supplies your
login launcher. The wheel remains tools-only; existing source-built compositor
bundles stay available. Profile formats and effect defaults are unchanged.

### From a source-managed session to an Arch package

Install or update `niri-fx` or `niri-fx-git`, keeping the existing retained bundles,
tool environments and configuration. If the installation still uses an older
per-user launcher, complete the
[one-time launcher migration](tool-updates.md#migrate-existing-launchers-once)
first. An already active managed-tools selection does not need that migration
again. Customized or unrecognized launcher files are preserved and refused.

For an already selected native session, including shared settings created with
the 0.20 source tools, use the packaged command **without `--config`**:

```sh
/usr/bin/niri-fx native adopt
/usr/bin/niri-fx native adopt --apply --expect-plan REVIEWED_SHA256
```

Review the first command's plan before applying its `plan_sha256`. This retains
the packaged tools and compositor while preserving the selected recipe and
shared configuration; a frozen selection keeps its frozen snapshot. The ordinary
managed `niri-fx` launcher continues to use the older selected tools until adoption
succeeds. Select **NiriFX (package)** at the next login. The package entry uses the
default XDG native storage; custom-root installations keep their existing entry.

Direct upgrades from 0.20 follow the same
[portable-recipe migration rules](#portable-fragment-recipes) introduced in 0.21.
Existing schema 1, 2 and 3 documents keep their meaning. The newer tools can
export a retained 0.20 fragment recipe as schema 4 with its recorded response values,
without rewriting the old bundle. Keep original documents and bundles: 0.20
tools cannot read schema 4, and compatibility checks may refuse tool rollback
while selected or previous bundles contain newer recipes.

## From 0.20 to 0.21

Download the 0.21 wheel and `SHA256SUMS` from the same
[release](releases.md#0210-prerelease), and verify the checksum before installing.
If CLI, Studio or the login launcher use a managed runtime, prepare the wheel in
a new persistent environment and follow [managed tool updates](tool-updates.md).
Keep the previous environment intact for recovery; do not upgrade its files in place.

For an ordinary standalone virtual environment that is not used by a managed
login launcher, update the package and reopen Studio:

```sh
sha256sum --ignore-missing -c SHA256SUMS
.venv/bin/python -m pip install --no-index --no-deps --upgrade ./niri_fx-0.21.0-py3-none-any.whl
.venv/bin/niri-fx studio --active
```

Keep the configuration and NiriFX state directories, saved JSON and retained
compositor bundles. Updating the tools preserves active effects, shell
registrations, profiles and Restore snapshots. Save any open draft, close the
older Studio and reopen it through the updated launcher; reloading its page
alone does not replace the running server.

The compositor patch stack is unchanged from 0.20. Existing compatible full
builds remain usable; this tool update does not rebuild, replace or restart
the compositor. Native settings still require a compatible retained build;
live activation checks the running renderer contract.

### Portable fragment recipes

NiriFX 0.21 saves continuous-fragment response values in profile
schema 4. **Download JSON**, **Share settings** and **My profiles** now retain
the whole combo, including custom delays, rotation and release timing. Existing
schema 1, 2 and 3 profiles keep their meaning and acquire no response implicitly.
The document limit increases from 16 to 32 KiB for complete five-action recipes.

NiriFX 0.20 retained a continuous preset separately from its portable profile.
Keep those bundles and use the 0.21 tools to read the complete recipe:

```sh
niri-fx native status --offline
niri-fx native export BUNDLE_ID > ./saved-combo.json
niri-fx inspect --custom ./saved-combo.json
```

Export resolves the retained response into explicit values without rewriting
the bundle, changing selection or contacting the desktop. Import the document
into Studio 0.21 or newer to edit, save or share it. Applying remains a separate
review against the chosen compositor. Older 0.20 tools cannot import schema 4;
retain their original bundles and documents for rollback.

Move Off, Preserve or an incompatible material keeps the response dormant in
the saved profile. Selecting **Timed movement** explicitly removes it and
returns to schema 2 or 3 according to the Swap choice. Stock KDL still omits
native actions. See [portable profiles](profiles.md#portable-fragment-response).

### Returning to 0.20

Keep original 0.20 documents and bundles alongside any schema 4 exports. Version
0.20 cannot read schema 4 profiles or managed recipes that contain them. Managed
tool rollback checks the selected and previous bundles, including their baseline
references, and refuses an incompatible older runtime. Switching only the selected
bundle back does not make rollback possible while a newer recipe remains in the
previous slot. Use the newer tools to review compatible retained selections first.
Keep the 0.21 environment so you can reopen or export newer recipes. Do not
overwrite or edit retained bundles to make an older tool accept them.

## From 0.19 to 0.20

For a standalone wheel installation, verify the new release's `SHA256SUMS`,
install it in the same environment and reopen Studio:

```sh
.venv/bin/python -m pip install --no-index --no-deps --upgrade ./niri_fx-0.20.0-py3-none-any.whl
.venv/bin/niri-fx studio --active
```

Keep the configuration and NiriFX state directories. Existing profiles, favorites,
registrations and Restore history remain available. Studio now starts with
individual action choices; complete looks are under **Combos**. Its footer shows
the tool version and UI build. Close an older editor after saving any draft, then
launch Studio again to use the updated installation.

If a NiriFX login launcher uses this environment, use the
[managed tool update workflow](tool-updates.md) instead of upgrading its files in
place. Prepare 0.20 in a new persistent environment, review launcher migration
if needed, then select it for CLI, Studio and future logins together. Preserve the
previous environment for rollback. A separately running Studio or compositor
keeps its current process until it closes normally.

### Move and Swap choices

Updated NiriFX builds add independent styles for explicit left/right window swaps.
Existing profiles and retained builds keep their current shared Move behavior.
Selecting a Swap style or Off writes profile schema 3, which older NiriFX tools
cannot read. Choosing Preserve again removes the override and saves schema 2.
Update tools and the full NiriFX compositor before applying independent swaps;
Studio reports older retained builds without replacing them. Stock Niri exports
omit Swap overrides and portable JSON retains them.

### Full session and shared desktop settings

Build the complete compositor from the 0.20 source archive or tag using
`python3 scripts/build-nirifx-session.py`, then follow the
[session guide](native-session.md). Select a reviewed build for the next login;
installing or updating the Python package does not replace your running compositor.
Earlier retained builds remain available. Use one full build for all native
features rather than selecting individual patch variants.

Existing frozen configurations remain frozen after upgrading. To have both
sessions follow the normal Niri files, first save an effects recipe to the
selected bundle, then review [shared-setting adoption](shared-settings.md).
First adoption requires the next NiriFX login. Later shared changes update watched
includes for both sessions, with stock-compatible effects kept separate from
native-only effects. A written configuration is reported separately from verified
live activation. Frozen recovery remains available if a shell or stock Niri
update introduces syntax the selected NiriFX build cannot read.

In 0.20, continuous-fragment presets are retained in managed session recipes. **Download
JSON**, **Share settings** and **My profiles** omit those native response
controls. Keep the bundle and reopen its recipe in local Studio when updating;
portable profile export alone is not a complete backup of continuous motion.
The **Pointer wobble** Off choice disables whole-window wobble; use Move Off to
disable continuous fragments as well as the timed movement effect.

If you used the earlier compact iRiS source integration, follow its
[reviewed removal](desktop-updates.md#removing-the-earlier-compact-iris-entry)
before a shell update. Current installation uses external configuration and does
not patch the shell checkout.

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
kind `profile`, schema 2, or schema 3 when a separate Swap style or Off is saved.
NiriFX 0.21 adds schema 4 for an explicit continuous-fragment
response, keeping all five action keys and all 18 response values.
Schema 1 profiles still import with their existing meaning; see [profiles](profiles.md).
Unknown fields and malformed names are rejected rather than ignored.

Unsupported older command aliases and document formats require migration.
Re-export or recreate those presets for the current format, keeping each
original until its replacement works. If an older distribution is
installed in the same virtual environment, remove it before installing NiriFX.

For custom file locations, see [setup options](setup.md) and the
[iNiR integration reference](integration.md).
