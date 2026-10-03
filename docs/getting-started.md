# Getting started

**Standalone Niri is fully supported; Quickshell is optional.** Start with the
[scenario guide](scenarios.md) or [standalone walkthrough](standalone.md) if you
do not use an existing shell picker.

## Requirements

- Linux and Python 3.10 or newer. The application has no Python runtime dependencies.
- Niri with inline animation shaders. Tested with **26.04 (`8ed0da4`)**;
  older versions and other compositors are not validated.
- A WebGL-capable browser for previews. Chromium is used for the app-style Studio;
  without it, Studio falls back to the default browser.
- For native preset selection and saving: iNiR with `NiriAnimationPresets` and
  external user presets. The adapter uses iNiR's installed helper; no shell QML
  files are changed. See the [integration contract](integration.md).

Niri animations must be enabled. Standalone exports and offline previews do not
need iNiR, a Rust toolchain or the experimental compositor.

## Get the source and preview

```sh
git clone https://github.com/jturbide/niri-fx.git
cd niri-fx
python3 -m niri_fx --version
python3 -m niri_fx preview --output /tmp/fragments-preview.html
xdg-open /tmp/fragments-preview.html
```

Use a new output filename if that preview already exists. All `python3 -m`
commands in these guides run from the checkout. To install the CLI in a virtual
environment instead:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/niri-fx --help
```

Use `.venv/bin/niri-fx` in place of `python3 -m niri_fx` when running
the installed package. Source installation is the documented distribution path;
there is no official PyPI, AUR or Flatpak release yet.

## iNiR and iRiS

For a planned installation with diagnostics, launcher creation and exact-file
restore snapshots, use [the setup workflow](setup.md). `setup` previews changes;
`setup --apply` performs them. The manual registration workflow remains available:

```sh
python3 -m niri_fx register --dry-run
python3 -m niri_fx register
```

Registration backs up and updates the user preset registry atomically. It adds
the built-in pack, preserves named custom presets and other providers, and does
not activate a style. Choose one in **iRiS Settings → Windows → Movement → Style**.
Enable animations if the picker is hidden.

Each entry snapshots the recognized active preset's other animation settings.
Open and close are replaced; ordinary resize is preserved unless you explicitly
opt into fragments. If the current preset is unrecognized, select a known base:

```sh
python3 -m niri_fx register --base bouncy --dry-run
python3 -m niri_fx register --base bouncy
```

An explicit base chooses those timings for the saved entries. It does not capture
unrecognized custom timings. Later base changes are not inherited automatically.

For visual editing and saving:

```sh
python3 -m niri_fx studio --target inir
# Optional launcher, tied to this checkout's current path:
python3 scripts/install-desktop.py
```

Save a named preset in Studio, then select it in iRiS. Registration and saving are
separate from activation. Nothing is added to session startup.

The default registry is `~/.config/inir/niri-animation-presets.json` (honoring
`XDG_CONFIG_HOME`). If the legacy `illogical-impulse` config directory exists,
its registry is used instead. The helper is normally under `~/.local/share/inir`
(honoring `XDG_DATA_HOME`).
`--registry` and `--inir-root` support other installations. Existing registry
symlinks are preserved and backup paths are printed by the command.

## Standalone Niri

For a managed include and restore snapshot, use `setup --target standalone`,
review the plan, then repeat with `--apply`. See [setup and restore](setup.md).
The manual export workflow below is useful when another tool manages your config.

This path also applies to Niri with DankMaterialShell or another shell. Keep the
generated file outside shell-managed directories. First generate and validate:

```sh
python3 -m niri_fx render --preset explosion > /tmp/fragments.kdl
niri validate -c /tmp/fragments.kdl
```

After validation succeeds, copy it into its own include. GNU `cp` keeps a numbered
backup if the target already exists:

```sh
mkdir -p ~/.config/niri/nirifx
cp --backup=numbered /tmp/fragments.kdl ~/.config/niri/nirifx/animations.kdl
```

Back up your main Niri config before editing it. Add the following **once**, after
existing animation settings and shell-generated includes:

```kdl
include "nirifx/animations.kdl"
```

Run `niri validate` to check the full configuration. Use `-c` for a nonstandard
config location. Niri watches included files and reloads changes. Adjust paths
above if you use a nondefault `XDG_CONFIG_HOME`.

To switch styles, repeat generation, validation and the backed-up copy. Studio's
offline **Export Niri config** produces the same override. Resize is omitted
unless you pass `--resize` or explicitly enable it in Studio.

Use one owner for open/close animations: a late standalone include continues to
override settings selected through a shell preset manager. See the
[DMS guide](compatibility.md#niri--dankmaterialshell) and
[Niri include rules](https://niri-wm.github.io/niri/Configuration:-Include.html).

## Update

Read the [development update policy](upgrading.md) before updating an older
checkout. NiriFX uses one current API and preset format; obsolete interfaces
are removed during development.

Review the [changelog](../CHANGELOG.md), then update a clean checkout:

```sh
git pull --ff-only
```

If installed in a virtual environment, reinstall with `.venv/bin/python -m pip
install .`. For iNiR, re-register the built-in pack and **reselect the style in
Settings**; updating registry entries does not replace a shader already embedded
in the active config. If its old version is now reported as custom, specify the
same known base you originally used. Custom styles keep their saved shaders until
you explicitly save or import them again.

For standalone Niri, regenerate, validate and replace your include. Restart
Studio to pick up editor changes. Recreate the optional launcher if the checkout
moves. Existing custom resize choices survive updates; new presets stay opted out.

## Roll back or remove

For iNiR, **first select your previous non-NiriFX style in Settings**, then:

```sh
python3 -m niri_fx unregister --dry-run
python3 -m niri_fx unregister
```

This removes all NiriFX registry entries, including named custom styles; export
any you want to keep first. Unregister does not rewrite the shader currently in
Niri's config and retains registry backups. Restore a printed backup path if you
need the previous registry; reselect a style afterward.

For standalone Niri, remove the NiriFX include and run `niri validate`. Your
underlying animation settings take over. Keep or remove the generated file and
its backups as needed.

Remove the optional `niri-fx-studio.desktop` entry from
`~/.local/share/applications` (or your XDG data directory) to remove the launcher.
The checkout, virtual environment and Studio profile can then be removed when
no longer needed. The profile is under
`~/.local/state/niri-fx/studio-profile` by default.
