# Experimental NiriFX login sessions

Prepare a patched Niri binary and a separate configuration, then select that
pair for the next login. Stock Niri stays installed and available. These commands
never restart the running compositor or modify a shell checkout.

This is an experimental **single-user, systemd-based** workflow. It requires the
stock `/usr/bin/niri`, `/usr/bin/niri-session`, `niri.service` and
`niri-shutdown.target`, plus the distribution's Niri portal configuration and
runtime dependencies. Dinit, NixOS integration and multi-user distribution
packages remain on the [roadmap](../ROADMAP.md#installation-selection-and-rollback).
Keep using the nested preview if you do not want a separate login session.

## Prepare a version

Install NiriFX in a persistent Python environment and retain that installation.
Commands below also work as `python3 -m niri_fx` from a source checkout, but its
location and Python interpreter must remain available to the login launcher.

Build a desktop candidate from the NiriFX checkout:

```sh
python3 scripts/build-niri-movement.py --fragment-drag --release --desktop
```

Use the exact candidate directory printed by the builder. Minimal nested-test
builds cannot be staged as desktop sessions. Run the candidate's
[native acceptance checks](fragment-drag.md) before deciding to use it.

Create and review a **self-contained** candidate configuration. You can start
with the pinned Niri source's `resources/default-config.kdl` and add your desired
effects using the [experimental guide](../experimental/README.md). Configure your
terminal, shell startup and exit binding before logging in. Active `include`
nodes are refused: copying a config that still includes mutable stock files
would not preserve a binary/configuration pair. The source config is never edited.
KDL node type annotations are also refused by the initial isolation scanner.

```sh
niri-fx native stage \
  --manifest /path/to/candidate/manifest.json \
  --source /path/to/candidate/source \
  --repository /path/to/niri-fx \
  --config /path/to/candidate.kdl
```

Review the paths, bundle ID and `plan_sha256`. Repeat the same command with
`--apply --expect-plan REVIEWED_SHA256` to copy the files. Apply runs the selected
trusted executable to validate the copied KDL; review alone does not run it.
Failed validation rolls back files still owned by that transaction.

Bundles live under `$XDG_DATA_HOME/niri-fx/native`, or
`~/.local/share/niri-fx/native` by default. Every bundle retains its executable,
configuration, build manifest, lockfile and patch evidence. Preparing another
version does not overwrite an earlier one. Edit the source candidate config and
stage it again to create a new pair; do not edit the stored bundle.

All commands accept `--root /path/to/native-storage` for a separate installation
or temporary testing. Use that same root throughout the workflow.

## Select the next login

```sh
niri-fx native status
niri-fx native select BUNDLE_ID
niri-fx native select BUNDLE_ID --apply --expect-plan REVIEWED_SHA256
```

Selection validates the selected configuration again and changes only the
next-login pointer. It retains the previous selection. The running session keeps
its existing binary and config, even if you select another pair while logged in.
`metadata-match` means recorded files and desktop build prerequisites match;
it does not certify graphics drivers, portals, capture or physical-desktop behavior.

## Add the login entry

```sh
niri-fx native session-entry
niri-fx native session-entry --apply --expect-plan REVIEWED_SHA256
```

This prepares `session/launch.py` and `session/niri-fx.desktop` inside native
storage. Review the desktop entry's Python and launcher paths. It is a per-user
entry, so it must point to this user's persistent installation, not a temporary
checkout or another account's private files.

Display managers read their configured session directories. For example, SDDM
defaults to `/usr/local/share/wayland-sessions` and
`/usr/share/wayland-sessions`; placing the entry in a user application folder is
not enough. An administrator can copy the reviewed file as `niri-fx.desktop`
with mode `0644` into a supported directory. Check for an existing entry before
registration and preserve it if it belongs to another installation. NiriFX does
not perform this privileged step or change the default login selection.

Once registered, log out when convenient and choose **NiriFX (experimental)**.
For recovery, choose the ordinary **Niri** entry instead. A TTY session can use
the prepared launcher with its recorded Python interpreter after the graphical
session has stopped; running it inside an active Niri session is refused.

The launcher uses a temporary, process-bound override of `niri.service` and
delegates environment import and shutdown to upstream `niri-session`. Keeping
this unit identity preserves shell integrations that discover Niri through its
MainPID. It captures the selected bundle once, validates it, then verifies the
actual compositor process and IPC peer. Expired leases execute stock Niri.
Other compositor-command overrides are refused, including a leftover earlier
test-session override; review their owner before removing them.

## Roll back

```sh
niri-fx native rollback
niri-fx native rollback --apply --expect-plan REVIEWED_SHA256
```

Rollback exchanges the current and previous next-login selections. Both bundles
remain installed. After the first selection, rollback returns to **no native
selection**; choose stock Niri. Another rollback restores the former selection.
If the previous bundle was edited or no longer validates against installed
libraries, rollback refuses and stock Niri remains the recovery path.

Generic `niri-fx restore` does not remove native bundles or bypass this selection
validation. Automatic cleanup is not available yet. Retain running, selected and
previous bundles, along with their transaction records.

## Updates and acceptance

Normal system and shell updates remain independent. A retained binary can still
stop working after a shared-library or driver update. Each login rechecks file
identity and config parsing; this is not a substitute for dependency-aware
distribution packages or real desktop acceptance.

Before adopting a version for daily use, check shell startup, open/close,
move/swap, resize, screen sharing, suspend/resume, clean logout and return to
stock. Automated temporary-storage tests cover failed writes, edited files,
selection races, rollback and stale leases. Physical login, GPU, portal and
suspend behavior remain separate acceptance gates.

See [Niri packaging](https://niri-wm.github.io/niri/Packaging-niri.html),
[Niri session setup](https://niri-wm.github.io/niri/Getting-Started.html) and
[SDDM session directories](https://github.com/sddm/sddm/blob/develop/data/man/sddm.conf.rst.in)
for the upstream session and dependency contracts.
