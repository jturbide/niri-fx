# Releases and downloads

Find tagged versions and release notes on the
[GitHub releases page](https://github.com/jturbide/niri-fx/releases).
NiriFX is in early development; prereleases may change commands or preset formats.
Read the notes for the version you install.

## Choose a version

- **Tagged release:** use its source archive or tag and follow the documentation
  included with that version. Its README may differ from the one on `main`.
- **Development branch (`main`):** includes the latest merged changes. Read
  [Unreleased](../CHANGELOG.md) for changes beyond the latest tag.

[Getting started](getting-started.md) documents installation from source or into
a Python virtual environment. Official PyPI, AUR and Flatpak distribution is not
currently provided by this project.

## 0.15.0 prerelease

[Download v0.15.0](https://github.com/jturbide/niri-fx/releases/tag/v0.15.0) for 75
presets, 13 profiles and eight collections. [Desktop motion packs](desktop-motion.md)
coordinate stock workspace, camera and overview springs. [Mixed shapes](fragment-shapes.md#mix-two-shapes)
add deterministic two-shape layouts and two finished looks. The experimental
compositor adds verified activation and native output feedback. Resize and custom
movement remain opt-in. Read [upgrade notes](upgrading.md#from-014-to-015).

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
| Source archive | Python code, Studio assets, shader sources, documentation, examples, tests, recording tools and the optional experimental patch |
| Python wheel | The `niri-fx` command and terminal guide, Python package, Studio resources, reusable QML/GTK pickers, shaders, application icon and license notices |

Installing the Python package does not install a patched compositor. Opening and
closing use stock Niri; native movement requires the separate
[experimental build](../experimental/README.md). Fragment resize is off by default.
See [license notices](../THIRD_PARTY.md) for the MIT application and GPL-licensed patch.

## Update or roll back

Follow [Updating NiriFX](upgrading.md) before replacing an existing installation.
Updating the source or package does not automatically replace active shaders.
[Setup and restore](setup.md) explains how to review changes and use saved
snapshots. Keep exported custom presets and restore snapshots when updating.

For maintainers, [Maintaining releases](releasing.md) covers building, testing,
signing and publishing a version.
