# Standalone Niri: choose, apply and restore

Use NiriFX with plain Niri, Waybar or a custom shell. No iNiR, iRiS, DMS, Noctalia
or Quickshell installation is required. Niri renders the ordinary animation
configuration that NiriFX writes.

## Start in Library

[Install the wheel](getting-started.md#install-and-open-library), then open:

```sh
niri-fx studio --target standalone
```

Use `.venv/bin/niri-fx` if the installation's virtual environment is not active.
From a source checkout, substitute `python3 -m niri_fx`.

Choose a recommended combo such as **Fragment Flow**, then press **Preview combo**.
Each action offers **Preserve / NiriFX Style / Off**. Preserve keeps your underlying
Niri settings, Style uses your selected preset, and Off disables that action.
Recommended combos preserve resize, movement and pointer drag. You can change
Open and Close independently and leave the others alone.

**Save to My profiles** keeps an editable copy without changing the desktop.
**Review & apply** shows the files that will change; **Apply these changes**
activates that selection. Apply creates `nirifx/animations.kdl` beside your main
config, adds its managed include and keeps an exact-file restore snapshot. Niri
reloads the included settings. Open and close a test window to try the result.

Use **Restore previous** to undo the app's last Apply for this target and config.
It works after reopening Studio and keeps your saved Library profile. Later edits
to the affected files cause a conflict rather than being overwritten. See
[Library](library.md) for per-action tuning and saved-profile management.

Resize Style and Off are explicit overrides supported by stock Niri. Movement
and pointer drag require separate experimental activation; designing those
choices alone leaves stock configuration unchanged.

## Nonstandard or generated configs

Pass the real main config when opening Studio:

```sh
niri-fx studio --target standalone --config /path/to/config.kdl
```

The default config honors `XDG_CONFIG_HOME`; profiles and snapshots honor
`XDG_STATE_HOME`. If you use `--state`, reopen with the same value for your saved
profiles and Restore history.

For a declarative or generated config, use **Export stock Niri config**. Put
that content into your configuration manager's source and include it after
earlier animation settings. The CLI can also generate and validate a file:

```sh
niri-fx render --preset shockwave > /tmp/nirifx-shockwave.kdl
niri validate -c /tmp/nirifx-shockwave.kdl
```

For a manually maintained config, back up the main config first, then copy the
validated output into its own include. GNU `cp` retains numbered backups:

```sh
mkdir -p ~/.config/niri/nirifx
cp --backup=numbered /tmp/nirifx-shockwave.kdl ~/.config/niri/nirifx/animations.kdl
```

Add this once, after earlier animation settings and shell-generated includes:

```kdl
include "nirifx/animations.kdl"
```

Run `niri validate` for the full config, or `niri validate -c /path/to/config.kdl`
for a nonstandard path. Adapt the include location if you use `XDG_CONFIG_HOME`.
The app's Restore cannot undo a manual copy; use your own backups or configuration
manager for that path. Keep one owner for the same animation action: a late
standalone include overrides a shell preset selected earlier in the config.

## Apply from the terminal

For a guided text interface, run `niri-fx`; see the [terminal guide](terminal.md).
For repeatable commands, preview a setup plan before applying it:

```sh
niri-fx setup --target standalone --preset balanced
niri-fx setup --target standalone --preset balanced --apply
niri validate
```

Setup also installs the Studio launcher unless you pass `--no-launcher`.
Use `--custom /path/to/my-style.json` instead of `--preset balanced` to apply an
exported style or [independent action profile](profiles.md). Add the same
`--config` or `--state` to both setup calls when using nondefault paths.

For these command-line changes, use the exact restore command printed by setup,
or review its latest snapshot and apply Restore:

```sh
niri-fx restore
niri-fx restore --apply
```

The Library maintains its own scoped Apply history: use **Restore previous** for
changes made there. Command-line Restore refuses later edits and requires the
same `--state` used for setup. Repeated Restore steps back through earlier changes.

Updating NiriFX alone leaves the active shader unchanged. Reopen Studio and
review/apply a revised preset when wanted. See [upgrading](upgrading.md) and
[troubleshooting](troubleshooting.md).
