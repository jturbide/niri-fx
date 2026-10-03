# Setup, diagnostics and restore

For a guided preset workflow, run `niri-fx` in a terminal or
`python3 -m niri_fx` from the checkout. [Choose, review, apply and undo](terminal.md)
without installing another interface. The commands below remain available for scripts.

Run from the checkout, or replace `python3 -m niri_fx` with the installed
`niri-fx` command. Python 3.10+ and a working Niri configuration are required.

## Inspect first

```sh
python3 -m niri_fx doctor
python3 -m niri_fx setup
```

`doctor` reports the Niri version, config validation, iNiR helper, browser,
optional Quickshell/GJS/GTK interfaces and advertised session socket as JSON.
Use `--text` for a readable report. Missing optional interfaces do not fail core
health. It does not change settings. A socket being
present does not prove a live compositor connection. Exit status is 0 when Niri
and its config are healthy, 1 for missing prerequisites, or 2 for a command error.

`setup` prints a plan by default. Check its target, affected paths and activation
note. `--dry-run` is an explicit alias for this preview. It may create and remove
a temporary sibling config to validate relative includes; it does not install
files or create a restore snapshot until `--apply`.

For a UI or script that separates review from activation, retain the JSON
`plan_sha256` and pass it back as `--expect-plan HASH` with `--apply`, keeping
the other setup arguments identical. NiriFX rebuilds the plan and rejects changed
selections or observed file state before writing. The [Quickshell picker](quickshell.md)
uses this contract. It supplements validation and per-write conflict checks;
it does not lock your files while you review them.

`python3 -m niri_fx inspect --custom /path/to/style.json` validates and prints
normalized style/profile JSON without requiring Niri or modifying a config.

## Apply

```sh
python3 -m niri_fx setup --apply
```

Automatic targeting uses iNiR when its external-preset helper is installed;
otherwise it uses standalone Niri. `--target inir` or `--target standalone`
selects explicitly. A launcher is created if absent; `--no-launcher` skips it.
Existing launchers are preserved. Nothing starts at login.

| Target | Changes | Activation |
| --- | --- | --- |
| iNiR | Merge the 64 built-ins into the user registry; preserve other providers and named styles | Select a style in iRiS Settings → Windows → Movement → Style |
| Standalone | Generate `nirifx/animations.kdl` beside the root config; append one marked include | Niri hot reloads the validated include |

All built-ins leave resize fragments off. To save an iNiR custom style, use
`--name`; custom options cannot silently modify the whole built-in pack.

```sh
python3 -m niri_fx setup --target inir --base bouncy --no-launcher
python3 -m niri_fx setup --target standalone --preset directional-wave --no-launcher
python3 -m niri_fx setup --custom examples/corner-burst.json
```

These are previews; repeat the chosen command with `--apply`. `--custom` cannot
be combined with effect overrides. `--config`, `--registry`, `--inir-root` and
`--state` support nonstandard locations and fixtures. XDG locations are honored.

Use one owner for animation settings. A standalone include takes precedence over
earlier shell settings, so it can override a shell's preset picker. Setup refuses
a known existing manual NiriFX include or an unowned destination file rather
than stacking another override. Remove or migrate a manual installation first;
see [the manual guide](getting-started.md#standalone-niri). Config managers outside
the root config may need their own include ordering adjustments.

## Restore a setup

Each changed file gets its original bytes, permissions and hashes recorded under
`$XDG_STATE_HOME/niri-fx/setup` (normally `~/.local/state/...`). Setup prints
the snapshot ID and an exact restore command, including a custom state path.
Run it from the same checkout/environment; it uses your current Python interpreter
and does not require a separately installed `niri-fx` executable.
Reapplying identical settings is a no-op and creates no new snapshot.

```sh
python3 -m niri_fx restore               # Preview the latest applied setup
python3 -m niri_fx restore --apply       # Restore it
python3 -m niri_fx restore --transaction SNAPSHOT # Preview a specific snapshot
```

For iNiR, select your previous non-NiriFX style **before restoring**. Registry
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
