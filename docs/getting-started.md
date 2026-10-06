# Getting started

Install NiriFX, choose a combo in **Library**, then review and apply it. You can
return to your previous settings with **Restore previous**. Choosing a preview
or saving a profile leaves the desktop unchanged.

This guide covers the app on stock Niri. For movement, swaps, continuous
fragments and pointer wobble, use the [complete NiriFX session](native-session.md).
Its source installer prepares all compositor features together; full-session
packages are still being prepared. Both paths use the same Library
and leave shell source code untouched.

This guide covers version 0.21. The wheel includes Studio and the managed-session
tools; the compositor still builds from the matching source archive or tag.
For another version, follow its included [release documentation](releases.md).

## Requirements

- Linux and Python 3.10 or newer. NiriFX has no Python runtime dependencies.
- Niri with inline animation shaders. Tested with **26.04 (`8ed0da4`)**;
  older versions and other compositors are not validated.
- A WebGL-capable browser. Chromium opens Studio as an app; otherwise Studio
  uses your default browser.
- Niri animations enabled. Plain Niri needs no shell integration, Quickshell,
  Rust toolchain or NiriFX compositor.

## Install and open Library

On Arch Linux or CachyOS, use the [AUR package guide](arch-linux.md) for a
source-built system package of CLI and Studio.

Download the wheel and `SHA256SUMS` from the same
[release](releases.md), then run these commands in the download directory:

```sh
sha256sum --ignore-missing -c SHA256SUMS
python3 -m venv .venv
.venv/bin/python -m pip install --no-index --no-deps ./niri_fx-0.21.0-py3-none-any.whl
.venv/bin/niri-fx studio
```

Continue only after the checksum reports `OK` for your wheel. The source gallery
and a checkout are optional. Installing the package does not activate effects.
In the examples below, use `.venv/bin/niri-fx` wherever you see `niri-fx`, or
activate the environment with `source .venv/bin/activate`.

## Choose your first combo

1. In Library, choose **Combos → Recommended**, then **Fragment Flow**. Try **Soft Landing**
   for a quieter frosted exit, **Ribbon Current** for strips, **Playful Motion**
   for a spring and bubbles, or **Geometric Flow** for triangles and hexagons.
2. Press **Preview combo** to see the opening and closing sequence. The recommended
   combos preserve resize, movement and pointer drag.
3. Choose each action's mode: **Preserve** keeps the underlying desktop or shell
   configuration; **NiriFX Style** uses the preset you select; **Off** disables
   that action. For example, keep Fragment Flow for Open, set Close to Off, and
   leave Resize, Move, Swap and Pointer wobble on Preserve.
4. Optionally use **Save to My profiles** and give the combo a name. This keeps
   an editable copy; it does not apply it. **Download JSON** makes a portable backup.
5. Press **Review & apply** and inspect the listed files. **Cancel** leaves them
   unchanged. **Apply these changes** applies the reviewed selection and keeps
   a restore snapshot.
6. Open and close a test window. Use **Restore previous** to recover the settings
   from before Apply. Your saved Library profile remains available.

Keep the same target, config and `--state` when reopening the app to access its
Restore history. Restore reports a conflict if those files changed afterward.
[Library](library.md) covers mixing styles, tuning, saved profiles and previews.
The [online gallery](https://jturbide.github.io/niri-fx/gallery/?collection=profiles)
is also available before installation; it cannot apply desktop settings.

Resize changes only when explicitly set to NiriFX Style or Off. Move, Swap and
Pointer wobble can be previewed and saved, but live changes require the matching
NiriFX session and separate activation choices. Leave them on Preserve
for this first stock-Niri setup. See [compatibility](compatibility.md).

## iNiR and iRiS

If the installed iNiR helper is detected, `niri-fx studio` uses it automatically.
To choose the owner explicitly and start from the recognized active look:

```sh
niri-fx studio --target inir --active
```

Use the same Library, action choices, **Review & apply** and **Restore previous**
flow above. The iNiR helper serializes the animation block; NiriFX reviews and
snapshots the resulting files. You do not need to register the full catalog or
find each NiriFX entry in iRiS Settings first. Saving to My profiles remains
separate from activation.

NiriFX preserves the other settings from your recognized shell preset. An
unrecognized custom animation block requires an explicit known base, for example
`niri-fx studio --target inir --base bouncy`. That base supplies shell timings;
it does not capture unknown custom timings. Review it before applying.

Use normal iNiR paths. The registry defaults to
`~/.config/inir/niri-animation-presets.json`, or the existing legacy
`illogical-impulse` directory, honoring `XDG_CONFIG_HOME`. The helper normally
lives under `~/.local/share/inir`, honoring `XDG_DATA_HOME`. `--registry` and
`--inir-root` support other installations.

Registering the entire built-in pack for selection through iRiS Settings is an
optional [setup workflow](setup.md), not a prerequisite for Library. Use the
[app launcher](library.md#iris-access-without-source-changes) to keep access
independent of the shell's source files.

## Standalone Niri

For plain Niri, Waybar or a custom shell, launch:

```sh
niri-fx studio --target standalone
```

Use the first-combo flow above. Apply creates a managed `nirifx/animations.kdl`
include beside the main config and adds its include after existing settings.
Niri reloads it. **Restore previous** removes the first managed include and
restores the original config, or steps back to the previous NiriFX change.
For a different main config, add `--config /path/to/config.kdl` when launching.

If another tool generates your configuration, use **Export stock Niri config**
and put the result in that tool's source instead of applying to a generated
file. Follow the [manual include instructions](standalone.md#nonstandard-or-generated-configs).
A late standalone include overrides earlier animation settings, including a
shell picker's choices; use the [connection matching your setup](library.md#one-interface-different-configuration-owners).
See the connection guides for [DMS](dms.md) and [Noctalia](noctalia.md).

## Get the source and preview

For development or running directly from a checkout:

```sh
git clone --depth 1 https://github.com/jturbide/niri-fx.git
cd niri-fx
python3 -m niri_fx studio
```

Use `python3 -m niri_fx` in place of `niri-fx` in these guides while in the checkout.
An offline preview is also available with
`python3 -m niri_fx preview --output /tmp/fragments-preview.html`; choose a new
filename and open it in your browser. Offline previews export without activation.

For a text interface, run `niri-fx` after installation, or `python3 -m niri_fx`
from the checkout. The [terminal guide](terminal.md) supports search, review,
Apply and Undo through the same transaction backend.

## Update or remove

Follow [Updating NiriFX](upgrading.md) when replacing an installed version.
Restart Studio afterward; installing a newer version does not change the active
shader. Choose a look and review/apply again when you want updated settings.

To undo a Library activation, reopen the same connection and use **Restore
previous** before removing NiriFX. For changes made through `setup` or the terminal,
use their printed Restore/Undo instructions. If you registered a pack for iRiS,
select a non-NiriFX shell style before [unregistering it](integration.md).

Export any saved profiles you want to keep. You can then remove the virtual
environment or checkout and any optional launcher. The app's library and history
live under `~/.local/state/niri-fx` by default, honoring `XDG_STATE_HOME`; keep that
directory while you still need its profiles or Restore snapshots.
