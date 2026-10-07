# Releases and downloads

Find tagged versions and release notes on the
[GitHub releases page](https://github.com/jturbide/niri-fx/releases).
NiriFX is in early development; prereleases may change commands or preset formats.
Read the notes for the version you install. The [path to 1.0](stability.md)
defines future stability gates. Releases continue through 0.21 and later 0.x
versions while the interfaces and installation workflow develop; 1.0 has no
release date or interface freeze yet.

## Choose a version

- **Tagged release:** use its source archive or tag and follow the documentation
  included with that version. Its README may differ from the one on `main`.
- **Development branch (`main`):** includes the latest merged changes. Read
  [Unreleased](../CHANGELOG.md) for changes beyond the latest tag.

[Getting started](getting-started.md) documents installation from source or into
a Python virtual environment. Arch Linux and CachyOS users can use the
[AUR packages](arch-linux.md). Starting with 0.22, both release and development
packages include Studio, CLI, presets and the complete compositor session. The
Python wheel remains a tools installation. PyPI and Flatpak packages are not
currently provided by this project.

## 0.22.1 prerelease

0.22.1 is a recovery patch for managed sessions. Retrying an interrupted
package adoption resumes exact partial compositor copies for shared and frozen
settings, while preserving and refusing changed or unexpected files. Session
startup identifies unavailable compositor executables separately from invalid
configuration, and retained tool startup failures include recovery guidance.

Effect defaults, compositor patches and document schemas are unchanged from
0.22.0. Package updates leave adopted users on their retained tools and compositor
until they explicitly review and apply adoption. Follow
[the patch upgrade steps](upgrading.md#from-0220-to-0221), or
[migration from a source-managed session](upgrading.md#from-a-source-managed-session-to-an-arch-package).
These recovery changes do not extend [physical desktop acceptance](validation.md).

## 0.22.0 prerelease

[NiriFX 0.22](https://github.com/jturbide/niri-fx/releases/tag/v0.22.0) brings complete Arch packages: choose `niri-fx` for the release or
`niri-fx-git` for development. Each includes Studio, CLI, presets, the full
compositor and its login entry. Keep using the tools in stock Niri, or follow
[session setup](arch-linux.md#use-the-nirifx-session) to use the included compositor.
Updating from 0.21 adds these files without enabling effects or changing settings.

Reviewed `native adopt` retains the package's tools and compositor in user
storage. Later adoption preserves the saved recipe and shared or frozen settings;
previous copies remain available for rollback. Package replacement does not
switch the running or next-login runtime automatically. See
[upgrading from 0.21](upgrading.md#from-021-to-022).

The Python wheel continues to provide the tools for other installation methods.
The source archive includes the matching compositor patches and build tools.
Complete packaging does not extend the current physical desktop acceptance:
check [tested environments and known limits](validation.md) for login, capture,
suspend and mixed-monitor coverage.

## 0.21.0 prerelease

[Download v0.21.0](https://github.com/jturbide/niri-fx/releases/tag/v0.21.0) to
create, customize and share complete continuous-fragment recipes in local,
online or offline Studio. Choose **Gentle**, **Tear** or **Cascade** for Move,
then adjust its response under **Customize fragment response**. JSON, share
links and My profiles retain every response value alongside your action choices.
Try the [four importable examples](../examples/profiles/README.md#portable-continuous-fragment-combos).

Download the wheel and `SHA256SUMS` from the same release. In their download
directory, verify the wheel before installing it in a new environment:

```sh
sha256sum --ignore-missing -c SHA256SUMS
python3 -m venv .venv
.venv/bin/python -m pip install --no-index --no-deps ./niri_fx-0.21.0-py3-none-any.whl
.venv/bin/niri-fx studio
```

For an existing installation, follow [the 0.20 to 0.21 upgrade guide](upgrading.md#from-020-to-021).
Managed installations select a new tool environment through a reviewed update;
their previous environment remains available. The source archive includes
documentation, examples, showcases and the full compositor build tools.

Schema 4 saves all five action choices and 18 explicit fragment-response values.
Move Off, Preserve or an incompatible material keeps those values dormant;
**Timed movement** removes the continuous response. Older profile schemas keep
their existing meaning. The read-only `native export` command also recovers
complete recipes from retained 0.20 bundles without changing them.

This is a tools release; the compositor patch stack is unchanged from 0.20.
Continuous gesture behavior still requires a compatible NiriFX compositor and
verified activation. Browser previews show the movement material, while stock
exports omit native actions. The wheel does not install a compositor, and no
supported compositor binary is included. See [session setup and tested limits](native-session.md).

## 0.20.0 prerelease

[Download v0.20.0](https://github.com/jturbide/niri-fx/releases/tag/v0.20.0) for a
simpler Studio with independent Open, Close, Resize, Move and Swap choices, five
new movement presets, and reviewed management of the complete NiriFX session.
[Shared desktop settings](shared-settings.md) lets stock Niri and NiriFX use your
normal configuration and one saved effects recipe. [Tool updates](tool-updates.md)
keep CLI, Studio and the login launcher on one selected installation, with the
previous version retained for recovery.

The source-built NiriFX compositor adds continuous square-fragment motion,
retained resize effects and resize-to-close continuation. These features require
the matching full compositor build; installing the wheel does not install or
replace a compositor. Distribution packages and supported compositor downloads
remain in development. See [session setup and tested limits](native-session.md).

```sh
sha256sum --ignore-missing -c SHA256SUMS
python3 -m venv .venv
.venv/bin/python -m pip install --no-index --no-deps ./niri_fx-0.20.0-py3-none-any.whl
.venv/bin/niri-fx studio
```

Download the wheel and `SHA256SUMS` from the same release. Use the source archive
for the matching build tools, compositor patches, documentation and showcases.
Installation preserves active settings; effect changes and shared-setting adoption
have their own review. [Upgrade from 0.19](upgrading.md#from-019-to-020) before
replacing an existing installation.

In 0.20, profiles without a Swap override remain schema 2; a separate Swap style or Off
uses schema 3, which older tools cannot read. Portable JSON retains action styles
and pointer wobble, but continuous-fragment response still belongs to the managed
session recipe. Keep that retained bundle when updating.

## 0.19.0 prerelease

[Download v0.19.0](https://github.com/jturbide/niri-fx/releases/tag/v0.19.0) for
independent **Preserve / NiriFX Style / Off** choices in Library, Studio and the
CLI. Preserve uses your underlying Niri or shell configuration. Choose a style
for selected actions, disable others, and save the combination as portable JSON.
[See the action-selection workflow](profiles.md).

Existing profiles import with their behavior intact; newly saved profiles use
schema 2. Native movement and pointer choices require the updated experimental
compositor with contract 2. Resize geometry also retains active timing through
configuration reloads. Retained resize shader state and minimum-size neighbor
alignment remain under development. [Upgrade from 0.18](upgrading.md#from-018-to-019).

```sh
sha256sum --ignore-missing -c SHA256SUMS
python3 -m venv .venv
.venv/bin/python -m pip install --no-index --no-deps ./niri_fx-0.19.0-py3-none-any.whl
.venv/bin/niri-fx studio
```

Download the wheel and `SHA256SUMS` from the same release. The source archive
includes documentation, recordings and experimental compositor patches.
Installing the package leaves active desktop settings unchanged.

## 0.18.0 prerelease

[Download v0.18.0](https://github.com/jturbide/niri-fx/releases/tag/v0.18.0) for
interactive pointer previews, portable pointer profiles and
[agent command discovery](agents.md). Choose Gentle, Rubber Sheet or Release
Settle in Library, drag the synthetic window in Studio, or preview the complete
combo. Profiles retain independent opening, closing and optional actions.

The wheel includes the editor, CLI and reusable agent guidance. Actual
pointer-driven window deformation requires the separately built
[native extension](pointer-wobble.md) and explicit activation in a verified
session. Its input/capture limitations remain documented.
[Upgrade from 0.17](upgrading.md#from-017-to-018).

Download the wheel and `SHA256SUMS` from the same release, verify the checksum,
then install and browse:

```sh
sha256sum --ignore-missing -c SHA256SUMS
python3 -m venv .venv
.venv/bin/python -m pip install --no-index --no-deps ./niri_fx-0.18.0-py3-none-any.whl
.venv/bin/niri-fx studio
```

Use [Updating NiriFX](upgrading.md) for an existing installation. The source
archive includes experimental patches, native test tools and the full catalog.

## 0.17.0 prerelease

[Download v0.17.0](https://github.com/jturbide/niri-fx/releases/tag/v0.17.0) for the
shared [NiriFX Library](library.md), independent action combinations and a
complete combo preview. Choose a finished look, use one style for every selected
action, or mix opening, closing and optional resize/movement choices. **My
profiles** adds named saves, explicit replacement, copies, rename and removal.
Portable JSON transfers a combination between the online Studio and installed
app. [Upgrade from 0.16](upgrading.md#from-016-to-017).

The Library runs standalone and connects to supported shell workflows. Local
Apply shows a plan and keeps a restore snapshot; the online Studio previews and
exports JSON/KDL without accessing your desktop. Detailed controls remain in
**Customize**. Installing the package or choosing a preview leaves active effects
unchanged. Built-in profiles leave resize unchanged; custom movement requires
the separate experimental compositor.

Download the wheel and `SHA256SUMS` from the same release, verify the checksum,
then install and browse:

```sh
sha256sum --ignore-missing -c SHA256SUMS
python3 -m venv .venv
.venv/bin/python -m pip install --no-index --no-deps ./niri_fx-0.17.0-py3-none-any.whl
.venv/bin/niri-fx studio
```

Use [Updating NiriFX](upgrading.md) for an existing installation and
[Getting started](getting-started.md) for setup-specific connections.

## 0.16.0 prerelease

[Download v0.16.0](https://github.com/jturbide/niri-fx/releases/tag/v0.16.0) for
75 presets, 16 profiles and nine collections. [Coordinated action sets](action-sets.md)
combine Fragments, Ribbons and Elastic looks with stock desktop timing and
separately enabled resize/movement companions. Nine portable examples and nine
showcases cover their defaults and optional actions.
[Upgrade notes](upgrading.md#from-015-to-016).

```sh
python3 -m venv .venv
.venv/bin/python -m pip install ./niri_fx-0.16.0-py3-none-any.whl
.venv/bin/niri-fx list --collection action-sets --text
.venv/bin/niri-fx studio --profile fragments-motion
```

Verify the download against the release's `SHA256SUMS` before installing.
Installing and previewing do not activate a style. Resize works on stock Niri
when explicitly enabled; native movement requires the experimental compositor.

## 0.15.0 prerelease

[Download v0.15.0](https://github.com/jturbide/niri-fx/releases/tag/v0.15.0) for 75
presets, 13 profiles and eight collections. [Desktop motion packs](desktop-motion.md)
coordinate stock workspace, camera and overview springs. [Mixed shapes](fragment-shapes.md#mix-two-shapes)
add deterministic two-shape layouts and two finished looks. The experimental
compositor adds verified activation and native output feedback. Resize and custom
movement are selected separately. Read [upgrade notes](upgrading.md#from-014-to-015).

Install the wheel without the source gallery:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install ./niri_fx-0.15.0-py3-none-any.whl
.venv/bin/niri-fx list --collection desktop --text
.venv/bin/niri-fx
```

Download `SHA256SUMS` from the same release and verify your package with
`sha256sum --ignore-missing -c SHA256SUMS` before installing. The signed tag and
reviewed source archive are also available. Installing does not activate a style.

## 0.14.0 prerelease

[Download v0.14.0](https://github.com/jturbide/niri-fx/releases/tag/v0.14.0) for 73
presets across nine families and ten open/close pairings. Seven
[curated collections](collections.md) group styles by look in the CLI, Studio and
gallery. Geometric Flow, Ribbon Current and Soft Landing add finished combinations
with their own previews and portable settings. All built-ins leave resize and
movement unset. Read [upgrading from 0.13](upgrading.md#from-013-to-014).

Choose the **wheel** for normal use. It includes the command, shaders and Studio
without downloading the source gallery. Choose the source archive for development,
offline documentation or all showcase media. No additional Python runtime
packages or patched compositor are needed for stock effects.

Download your chosen package and `SHA256SUMS` from the same release. In their
download folder, run `sha256sum --ignore-missing -c SHA256SUMS` and confirm that
your package reports `OK`. The other package can remain undownloaded. The Git tag
is signed; checksums detect corrupted or mismatched assets and are not a substitute
for checking a trusted signing key.

Install the verified wheel into a dedicated environment, then browse the pairings:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install ./niri_fx-0.14.0-py3-none-any.whl
.venv/bin/niri-fx list --profiles --text
.venv/bin/niri-fx
```

The terminal guide reviews changes before Apply. Installing the wheel alone does
not activate effects. For iNiR/iRiS, DMS and Noctalia, follow the
[setup-specific guides](getting-started.md).

## Package contents

| Format | Contents |
| --- | --- |
| Source archive | Python code, Studio assets, shader sources, documentation, examples, tests, recording tools and the complete compositor patch stack |
| Python wheel | The `niri-fx` command and terminal guide, Python package, Studio resources, reusable QML/GTK pickers, shaders, application icon and license notices |

Installing the Python package does not install a compositor. Opening, closing
and selected resize effects work with stock Niri; movement, swaps, pointer wobble
and continuous fragments require the [full NiriFX session](native-session.md).
Built-in profiles preserve existing resize settings.
See [license notices](../THIRD_PARTY.md) for the MIT application and GPL-licensed patch.

## Update or roll back

Follow [Updating NiriFX](upgrading.md) before replacing an existing installation.
Updating the source or package does not automatically replace active shaders.
[Setup and restore](setup.md) explains how to review changes and use saved
snapshots. Keep exported custom presets and restore snapshots when updating.

For maintainers, [Maintaining releases](releasing.md) covers building, testing,
signing and publishing a version.

## Verify an upgrade

Maintainers can exercise a published release wheel and a candidate wheel with
`scripts/test-upgrade.py`. Download the old wheel and its `SHA256SUMS` from
[v0.20.0](https://github.com/jturbide/niri-fx/releases/tag/v0.20.0), build the
0.22.1 candidate wheel, then run from the checkout:

```sh
python3 scripts/test-upgrade.py \
  --from-wheel artifacts/upgrade-v020/niri_fx-0.20.0-py3-none-any.whl \
  --checksums artifacts/upgrade-v020/SHA256SUMS \
  --to-wheel dist/niri_fx-0.22.1-py3-none-any.whl \
  --browser
```

This requires stock Niri, Python's venv/pip support, Node 22 or newer and
Chromium/Chrome. Omit `--browser` for the CLI/HTTP checks. The script creates its
own virtual environment, configuration, shell registry and state; it verifies
old JSON, favorites, named Library profiles and active files survive installation,
and restores existing CLI and Library snapshots exactly. Both Restore paths must
refuse external edits without changing the files or consuming recovery history.
The 0.20 source creates an active mixture of Preserve and Off plus an independent
Swap profile, checking both schema 2 and schema 3. Earlier wheels from 0.17 through
0.19 remain supported for legacy migration checks. The candidate also round-trips
pointer and complete fragment-response documents without activating native effects.
Its synthetic shell
base tests registry preservation; the
[adapter checks](validation.md) cover real shell serializers separately. No login
session or personal browser profile is used, and temporary files are removed.
