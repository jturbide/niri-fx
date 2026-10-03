# Setup, diagnostics and restore

Run from the checkout, or replace `python3 -m niri_fragments` with the installed
`niri-fragments` command. Python 3.10+ and a working Niri configuration are required.

## Inspect first

```sh
python3 -m niri_fragments doctor
python3 -m niri_fragments setup
```

`doctor` reports the Niri version, config validation, iNiR helper, browser and
advertised session socket as JSON. It does not change settings. A socket being
present does not prove a live compositor connection. Exit status is 0 when Niri
and its config are healthy, 1 for missing prerequisites, or 2 for a command error.

`setup` prints a plan by default. Check its target, affected paths and activation
note. `--dry-run` is an explicit alias for this preview. It may create and remove
a temporary sibling config to validate relative includes; it does not install
files or create a restore snapshot until `--apply`.

## Apply

```sh
python3 -m niri_fragments setup --apply
```

Automatic targeting uses iNiR when its external-preset helper is installed;
otherwise it uses standalone Niri. `--target inir` or `--target standalone`
selects explicitly. A launcher is created if absent; `--no-launcher` skips it.
Existing launchers are preserved. Nothing starts at login.

| Target | Changes | Activation |
| --- | --- | --- |
| iNiR | Merge the 14 built-ins into the user registry; preserve other providers and named styles | Select a style in iRiS Settings → Windows → Movement → Style |
| Standalone | Generate `fragments/niri-fragments.kdl` beside the root config; append one marked include | Niri hot reloads the validated include |

All built-ins leave resize fragments off. To save an iNiR custom style, use
`--name`; custom options cannot silently modify the whole built-in pack.

```sh
python3 -m niri_fragments setup --target inir --base bouncy --no-launcher
python3 -m niri_fragments setup --target standalone --preset directional-wave --no-launcher
python3 -m niri_fragments setup --custom examples/corner-burst.json
```

These are previews; repeat the chosen command with `--apply`. `--custom` cannot
be combined with effect overrides. `--config`, `--registry`, `--inir-root` and
`--state` support nonstandard locations and fixtures. XDG locations are honored.

Use one owner for animation settings. A standalone include takes precedence over
earlier shell settings, so it can override a shell's preset picker. Setup refuses
a known existing manual Fragments include or an unowned destination file rather
than stacking another override. Remove or migrate a manual installation first;
see [the manual guide](getting-started.md#standalone-niri). Config managers outside
the root config may need their own include ordering adjustments.

## Restore a setup

Each changed file gets its original bytes, permissions and hashes recorded under
`$XDG_STATE_HOME/niri-fragments/setup` (normally `~/.local/state/...`). Setup prints
the snapshot ID and an exact restore command, including a custom state path.
Reapplying identical settings is a no-op and creates no new snapshot.

```sh
python3 -m niri_fragments restore               # Preview the latest applied setup
python3 -m niri_fragments restore --apply       # Restore it
python3 -m niri_fragments restore --transaction SNAPSHOT # Preview a specific snapshot
```

For iNiR, select your previous non-Fragments style **before restoring**. Registry
restoration does not remove a shader already embedded in the active config.
Standalone restoration removes the managed include and restores the original
root config. Files created by setup are removed only if they still match the
recorded setup. Existing symlinks are preserved.

Restore verifies all targets and snapshot hashes before writing. If you changed
a target afterward or retargeted a symlink, it refuses the entire operation.
Keep your later edits and reconcile the snapshot manually; there is no force
overwrite option. Restore setup snapshots in reverse order.

Each file replacement is atomic; the complete multi-file operation is not a
filesystem transaction. Detected failures roll back files still matching the
operation. A power loss or forced termination may require manual recovery from
the retained `manifest.json` and numbered `.before` files. Do not remove snapshots
until you are satisfied with the installation.
