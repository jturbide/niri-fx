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
nodes are refused by default: copying a config that still includes mutable stock
files would not preserve a binary/configuration pair. The source config is never
edited. Use the reviewed include snapshot below for a split configuration.
KDL node type annotations remain unsupported by the isolation scanner.

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

### Import an existing include tree

Add `--snapshot-includes` to `native stage` when the source config uses includes:

```sh
niri-fx native stage \
  --manifest /path/to/candidate/manifest.json \
  --source /path/to/candidate/source \
  --repository /path/to/niri-fx \
  --config /path/to/desktop/config.kdl \
  --snapshot-includes
```

The review lists every source file and hash, including any missing optional
includes. Apply copies the complete include tree and rewrites only include paths
to files inside the bundle. File boundaries, include order and repeated includes
are preserved. Later source edits do not affect the installed snapshot; they
require another review and stage operation.

Literal quoted and raw-string paths, absolute paths and `~/` paths are supported.
A missing `optional=true` include becomes an empty owned file, keeping its absent
state even if the original appears later. Cycles, symlinks, special files, glob
paths, unsupported annotations and trees beyond the file, size or depth limits
are refused. Niri still validates the copied result before selection.

Only Niri configuration includes are copied. Applications, startup scripts,
wallpapers and other paths referenced inside ordinary settings remain external
dependencies. In particular, a frozen bundle does not redirect iRiS's config
writer: iRiS continues editing its usual stock Niri files. For this experimental
workflow, edit the source configuration and stage a new pair to change persistent
settings in the NiriFX session. Do not redirect global `XDG_CONFIG_HOME` to work
around this boundary.

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

### Inspect the running and selected versions

`native status` returns JSON with one entry per retained bundle, including missing
or damaged bundles referenced by the selection. Each entry has a `roles` list:

| Role | Meaning |
| --- | --- |
| `next-login` | Selected for the next login through this installation's launcher. |
| `rollback` | Previous selection retained by the selector. |
| `running` | The advertised Niri IPC process matches this bundle's executable and startup configuration path. |

A bundle may have several roles. Selecting an update while Niri is running can
leave one bundle marked `running` and another marked `next-login`.

The top-level `running` result distinguishes a `matched` bundle from an `external`
session, `offline` inspection and `unknown` identity. The CLI uses `NIRI_SOCKET`;
it checks the kernel-reported peer, executable identity, process lifetime and
explicit config argument. It never launches an executable found through IPC.
Use `--offline` to inspect retained files without contacting a session:

```sh
niri-fx native status --offline
```

This observes only the advertised IPC session, which could be a nested preview.
It does not discover every session or prove that the running renderer has enabled
an effect. Continue to use `doctor` and the manual acceptance checks below. An
empty role list is not permission to delete a bundle; cleanup remains planned.

Each bundle's `storage` reports logical regular-file bytes and filesystem-allocated
regular-file bytes, deduplicating hard links within that bundle. The measurement
does not follow symbolic links or include directory metadata, link storage,
separate Python environments, source checkouts or transaction history outside the
bundle. Filesystem compression and shared extents can make allocated bytes differ
from reclaimable space. An interrupted, inaccessible or bounded scan reports
incomplete results instead of treating unknown space as zero.

## Add the login entry

```sh
niri-fx native session-entry
niri-fx native session-entry --apply --expect-plan REVIEWED_SHA256
```

Use `--name "NiriFX (managed test)"` on both commands to distinguish a new test
entry from an existing experimental login. The name is part of the reviewed plan.

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

After logging in, run:

```sh
niri-fx doctor --niri-binary /path/to/bundle/bin/niri --config /path/to/bundle/config.kdl
```

Its `fragment_capability` result distinguishes
continuous fragments from timed movement; a matching version string or working
timed animation is not evidence that the continuous-fragment renderer is enabled.

| Manual check | Expected result |
| --- | --- |
| Sign in | Familiar shell, outputs, shortcuts and input settings load. |
| Open, close and resize | Chosen effects run; client content and input remain usable. |
| Drag, pause, reverse and drop | With continuous fragments configured, held pieces remain separated and reconstruct after release. |
| Keyboard move and swap | The selected movement style runs and window focus/order stay correct. |
| Screen sharing | The portal picker opens and the selected stream reaches a test application. |
| Suspend and resume | Displays, input, shell and capture recover normally. |
| Logout and stock login | The temporary lease is removed and stock Niri starts without native config nodes. |
| Previous candidate | Reviewed rollback selects the retained pair for the next login. |

See [Niri packaging](https://niri-wm.github.io/niri/Packaging-niri.html),
[Niri session setup](https://niri-wm.github.io/niri/Getting-Started.html) and
[SDDM session directories](https://github.com/sddm/sddm/blob/develop/data/man/sddm.conf.rst.in)
for the upstream session and dependency contracts.
