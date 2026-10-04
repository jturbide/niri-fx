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
optional Quickshell/GJS/GTK interfaces, and separate movement and pointer
capability reports as JSON.
Use `--text` for a readable report. Missing optional interfaces do not fail core
health. It does not change settings. Exit status is 0 when Niri
and its config are healthy, 1 for missing prerequisites, or 2 for a command error.

### Movement support

`doctor` compares temporary baseline configurations with movement-shader and
pointer-wobble nodes separately. This distinguishes stock Niri, the movement
experiment and the additional pointer extension even when they share a version
number. The pointer profile and activation workflow requires version 0.18 or
newer and the separate native extension for live deformation.

```sh
python3 -m niri_fx doctor --text
# Inspect a trusted experimental build without installing or starting it:
python3 -m niri_fx doctor --text --niri-binary artifacts/niri-pointer-src/target/release/niri
```

`--niri-binary PATH` selects the trusted executable for version reporting, existing
configuration validation and both capability probes. `--movement-binary` is an
alias for the same option. Without either flag, Niri on `PATH` is used. Standalone
setup and Studio use the selected executable to validate their generated config too.

When `NIRI_SOCKET` is available, the diagnostic makes a read-only version request
and compares the IPC peer's executable with the probed binary using Linux peer
credentials and `/proc`. It never executes a binary discovered through IPC.
A matching version string or socket filename alone is not evidence of support.

JSON integrations can read `movement_capability` and `pointer_capability`
separately. Each exposes parser `status`, running executable `session.status`,
renderer `session.contract.status` and the resulting `activation_ready`:

| Status | Meaning |
| --- | --- |
| `supported` | The tested executable accepts the probed experimental node |
| `unsupported` | The baseline configuration passes, but the experimental node is rejected |
| `unknown` | The probe could not establish support, or the running executable differs or cannot be identified |

Parser results remain separate from `session.contract.status`. A matching running
experimental binary must advertise movement contract 1 and compile an isolated
probe in its own renderer. `activation_ready` is true only when both checks pass.
`movement_configured` reports whether a shader is configured; it does not claim an
arbitrary custom shader compiled. The probe does not replace the active shader.
Missing sockets, mismatched binaries, incompatible contracts and timeouts never
count as verified support. Stock effects still work.

Pointer readiness requires pointer contract 1 and a verified built-in drag renderer
from the additional extension. Its `configured` and `enabled` values describe the
current settings, not whether the extension can be activated. A supported but
unconfigured pointer renderer can be ready. Strength zero keeps it configured
and explicitly disabled.

### Activate experimental movement

Only use this after deliberately starting the experimental compositor as your
session. NiriFX does not install or replace a compositor. The default setup and
all stock exports continue to omit movement shaders.

```sh
# Preview a plan against the executable running your experimental session:
niri-fx setup --target standalone --preset fragment-wake --enable-movement \
  --niri-binary /path/to/patched/niri --no-launcher
# Repeat the setup command with --apply --expect-plan REVIEWED_PLAN_SHA256.
# Then use the returned transaction for reviewed Restore:
niri-fx restore --transaction TRANSACTION_ID
niri-fx restore --transaction TRANSACTION_ID --apply
```

For a profile, its `movement` slot must explicitly select a supported style.
Create one with `profile --movement-preset fragment-wake`, or use
[an example profile](../examples/profiles/fragment-wake-motion.json).
Activation requires explicit `--target standalone`. The connected standalone
Studio also offers a separate movement activation choice when the running contract
is verified. iNiR registration, Noctalia exports, terminal-guided setup and stock
shell packs omit experimental nodes.
The Apply step rechecks the socket and running contract before writing, including
when a prior plan has no file changes. File-state and plan-hash checks still apply.
[Runtime support and limits](../experimental/README.md#runtime-verification-and-output-feedback).

### Activate experimental pointer drag

Create a profile with `--pointer gentle`, `rubber-sheet` or `release-settle`.
`--pointer off` saves an explicit zero-strength override. Leaving the option out
inherits the existing pointer behavior. These settings do not require a timed
movement action or change resize behavior.

```sh
python3 -m niri_fx profile --name 'Gentle Fragments' \
  --open-preset subtle --close-preset subtle --pointer gentle > /tmp/gentle-fragments.json
python3 -m niri_fx doctor --niri-binary /path/to/pointer-enabled/niri
python3 -m niri_fx setup --target standalone --custom /tmp/gentle-fragments.json \
  --enable-pointer --niri-binary /path/to/pointer-enabled/niri --no-launcher
```

Use an executable matching the running experimental session. Parser support or
a nested demo alone does not prove support in the login compositor. Check
`pointer_capability.activation_ready`, review the setup plan, then repeat the
same setup command with `--apply --expect-plan REVIEWED_PLAN_SHA256`. A profile
containing both native choices needs both `--enable-pointer` and `--enable-movement`
to activate both. They share one `window-movement` block.

Local Studio can follow the same workflow:

```sh
python3 -m niri_fx studio --target standalone --custom /tmp/gentle-fragments.json \
  --niri-binary /path/to/pointer-enabled/niri
```

Choose **Apply experimental pointer drag**, review, then Apply. The choice is
shown only for a verified standalone connection with pointer settings selected.
**Disabled** requires explicit consent too. Settings remain editable and shareable
in hosted/offline Studio or unsupported shells; ordinary exports omit the native
node. Changing settings clears pointer consent and invalidates the prior review.
Apply rechecks the running contract before writing, including otherwise unchanged
plans. Losing runtime support between review and Apply refuses the change.

Retain the returned transaction and state path, or use **Restore** in the same
Studio connection. CLI restoration supports the same review-first flow as stock
setup. See [Restore a setup](#restore-a-setup), the [pointer guide](pointer-wobble.md)
and the [isolated native demo](profiles.md#optional-pointer-drag).

## Review a setup

`setup` prints a plan by default. Check its target, affected paths and activation
note. `--dry-run` is an explicit alias for this preview. It may create and remove
a temporary sibling config to validate relative includes; it does not install
files or create a restore snapshot until `--apply`.

For a UI or script that separates review from activation, retain the JSON
`plan_sha256` and pass it back as `--expect-plan HASH` with `--apply`, keeping
the other setup arguments identical. The plan exposes action settings in `effect`
and optional stock springs in `desktop_motion`, plus saved pointer controls in
`pointer`. Activation is reported separately in `movement` and `pointer_activation`;
loaded selections and their consent flags are checked before Apply. NiriFX rebuilds the plan and rejects changed
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
| iNiR | Merge built-in styles and profiles into the user registry; preserve other providers and named styles | Select a style in iRiS Settings → Windows → Movement → Style |
| Standalone | Generate `nirifx/animations.kdl` beside the root config; append one marked include | Niri hot reloads the include when that config is loaded |

All built-ins leave resize off; built-in profiles leave movement and pointer choices unset. To save an iNiR custom style, use
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

Restoring an earlier native pointer or movement selection verifies the running
renderer again. New snapshots retain the selected validation executable; for an
older snapshot or an explicitly changed path, pass `--niri-binary PATH` to both
review and Restore. Unsupported reactivation leaves the files and snapshot
untouched. Removing native settings to return to stock needs no experimental
session. Restored native configurations are validated, with rollback on failure.

Each file replacement is atomic; the complete multi-file operation is not a
filesystem transaction. Detected failures roll back files still matching the
operation. A power loss or forced termination may require manual recovery from
the retained `manifest.json` and numbered `.before` files. Do not remove snapshots
until you are satisfied with the installation.

## Agent-driven workflows

The [agent guide](agents.md) covers catalog discovery, portable documents and
reviewed Apply/Restore through the same CLI. `python3 -m niri_fx agent-info` prints
the operation map; `--parameters` prints canonical bounds and `--skill` prints the
packaged reusable instructions. These commands are included in version 0.18 and newer.
Agents do not need a separate server or configuration writer. A request to design
or preview an effect does not by itself authorize activation.
