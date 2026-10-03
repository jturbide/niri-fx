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

## 0.8.0 prerelease

[Download v0.8.0](https://github.com/jturbide/niri-fx/releases/tag/v0.8.0) for 64
presets, nine effect families, hosted Studio sharing, opt-in resize profiles and
updated experimental interruption handling. Read [upgrading from 0.7](upgrading.md#from-07-to-08)
before updating custom presets or the optional compositor build.

Download the wheel, source archive and `SHA256SUMS` from the same release. In their
download folder, verify both packages with `sha256sum -c SHA256SUMS`. The Git tag
is signed; checksums detect corrupted or mismatched assets and are not a substitute
for checking a trusted signing key.

## Package contents

| Format | Contents |
| --- | --- |
| Source archive | Python code, Studio assets, shader sources, documentation, examples, tests, recording tools and the optional experimental patch |
| Python wheel | The `niri-fx` command, Python package, Studio resources, shaders, application icon and license notices |

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
