# Standalone Niri: try, apply, change and undo

No iNiR, iRiS, DMS, Noctalia or Quickshell installation is required. NiriFX writes
ordinary Niri animation configuration. A bar such as Waybar has no role in the
shader renderer. Start with [the three-command preview](scenarios.md).

## Apply a built-in style

From the checkout, check the environment and review the proposed files:

```sh
python3 -m niri_fx doctor
python3 -m niri_fx setup --target standalone --preset balanced
```

Apply that plan when ready:

```sh
python3 -m niri_fx setup --target standalone --preset balanced --apply
niri validate
```

Setup keeps a restore snapshot, creates `nirifx/animations.kdl` beside your main
config and adds its managed include. It also installs the Studio launcher unless
you pass `--no-launcher`. Niri reloads the included settings; open and close a
test window to see the effect. No daemon or login-compositor replacement is used.

Choose `--preset pixel-wipe`, `ghost-wisps` or `shockwave` on a later setup call
to switch styles. `python3 -m niri_fx list` prints the current catalog. Changes to
the owned include outside NiriFX cause setup to refuse rather than overwrite them.

## Tune and apply a custom style or profile

```sh
python3 -m niri_fx studio --target standalone
```

Use **Export preset** to save editable JSON. The **Standalone file** save target
downloads a KDL include; it does not activate the effect. To apply the saved JSON
with the same managed setup and snapshots:

```sh
python3 -m niri_fx setup --target standalone --custom /path/to/my-style.json
python3 -m niri_fx setup --target standalone --custom /path/to/my-style.json --apply
```

This also accepts [independent action profiles](profiles.md). Resize is left at
your existing behavior unless the JSON explicitly opts into fragment resize.

## Nonstandard or generated configs

Pass the real main config to both the preview and apply calls:

```sh
python3 -m niri_fx setup --target standalone --config /path/to/config.kdl --preset balanced
```

The default honors `XDG_CONFIG_HOME`; snapshots honor `XDG_STATE_HOME`. For
declarative/generated configs, export instead:

```sh
python3 -m niri_fx render --preset shockwave > /tmp/nirifx-shockwave.kdl
niri validate -c /tmp/nirifx-shockwave.kdl
```

Put that content into your configuration manager's source and include it after
earlier animation settings. Keep one owner for open/close animations. The
[manual include instructions](getting-started.md#standalone-niri) cover this path.

## Undo or update

Use the exact restore command printed by setup, or preview the latest snapshot:

```sh
python3 -m niri_fx restore
python3 -m niri_fx restore --apply
```

Restore refuses to overwrite later edits. If you used a custom `--state`, use
the same value for restore. Repeated restore steps back through earlier changes;
the first setup snapshot restores the config from before installation.

Updating the source alone does not change your active shader. Reopen Studio for
editor updates; run setup again to apply a revised preset. See [upgrading](upgrading.md)
and [troubleshooting](troubleshooting.md).
