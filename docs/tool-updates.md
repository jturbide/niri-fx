# Updating the NiriFX tools together

The managed tool workflow keeps CLI, Studio and the login launcher on one
selected Python installation. It is available in current source builds. Stock
Niri and shell packages continue to use their normal updaters.

Install each NiriFX update in a new persistent virtual environment. Run the
update command from that environment to select it after review. Existing
environments remain available for rollback; do not upgrade their files in place.
This workflow changes tool launchers, not your effects or compositor selection.
An already running Studio or login session keeps its existing process until you
close it normally.

## Prepare an installation

Use a trusted wheel built from the version you want to install. For example,
replace the paths below with your new persistent environment and wheel:

```sh
python3 -m venv /persistent/path/to/new-runtime
/persistent/path/to/new-runtime/bin/pip install --no-index --no-deps /path/to/niri_fx-VERSION-py3-none-any.whl
```

The update command checks the installed runtime and whether it can read the
selected compositor bundle, its rollback pair and their original baselines.
These checks read retained metadata; they do not start a compositor or certify
physical desktop behavior. An explicitly supplied bootstrap environment is
trusted executable code and is inspected using its own Python interpreter.

## Migrate existing launchers once

For the first migration, supply the current working environment as
`--bootstrap-runtime`. It remains selected while the stable login entry is
prepared. Pass the actual display-manager entry path used by your installation:

```sh
/persistent/path/to/new-runtime/bin/niri-fx native tools-update \
  --bootstrap-runtime /persistent/path/to/current-runtime \
  --registered-entry /usr/local/share/wayland-sessions/niri-fx.desktop
```

Read the phase, notes, affected paths and `plan_sha256`. Repeat the same command
with `--apply --expect-plan REVIEWED_SHA256` to prepare the migration. The
existing CLI, Studio and registered login entry are left intact at this stage.

Register the staged desktop file at the reported display-manager path using your
administrator workflow. Review the source and destination before copying it.
NiriFX does not modify system session directories or request root privileges.
The stable entry still uses the bootstrap runtime, so interrupted registration
can be resumed without promoting the new version.

Once the registered file matches the staged entry, rerun the same update command.
Review its new fingerprint, then repeat with `--apply --expect-plan REVIEWED_SHA256`.
This adopts recognized CLI and Studio launchers and selects the new runtime.
Customized or unrelated launcher files are refused and preserved.

Use `--cli-path` and `--desktop-path` during initial preparation if your launcher
locations differ from the defaults. Keep these paths and `--root` consistent
through review and Apply. Source-checkout launchers or hand-written wrappers may
need manual migration if their ownership cannot be established.

Older installations may have CLI/Studio and login pinned to different environments.
In that case, use the login environment as `--bootstrap-runtime` and add
`--legacy-tools-runtime /path/to/current-cli-runtime` during first preparation.
Both paths are explicit trusted inputs; the migration recognizes their generated
launchers without treating arbitrary files as NiriFX-owned.

## Subsequent updates

Run this from the newly installed environment:

```sh
/persistent/path/to/new-runtime/bin/niri-fx native tools-update \
  --registered-entry /usr/local/share/wayland-sessions/niri-fx.desktop
```

After reviewing, repeat with `--apply --expect-plan REVIEWED_SHA256`. All three
stable launchers resolve the same selected runtime. The selector is written last;
ordinary updates require no new display-manager registration. Changed runtimes,
edited launchers, altered bundle selections or a stale review stop the operation.

After activation, inspect the state through the shared CLI:

```sh
niri-fx native tools-status
```

During the first migration, run `native tools-status` through the new environment's
full command path until your existing CLI has been adopted.

Reopen Studio to use the updated tools. Your current compositor and its login
lease keep running; a tool update does not log you out or replace that process.

## Roll back the tools

```sh
niri-fx native tools-rollback \
  --registered-entry /usr/local/share/wayland-sessions/niri-fx.desktop
niri-fx native tools-rollback \
  --registered-entry /usr/local/share/wayland-sessions/niri-fx.desktop \
  --apply --expect-plan REVIEWED_SHA256
```

Rollback rechecks the previous runtime against the compositor bundles selected
now. It refuses a runtime that cannot read them, even if that version was usable
before newer settings were created. Keep the current tools to review a compatible
recovery path. Tool rollback retains both environments and all configuration.
If the restored version predates these update commands, run `tools-update` through
the newer retained environment's full command path to return to it.

Use `native rollback` for compositor selection and `native rollback --live` for
compatible effect recovery. Those are separate from tool-runtime rollback.
See [session setup](native-session.md) and [desktop updates](desktop-updates.md)
for the rest of the lifecycle.
