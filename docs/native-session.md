# The NiriFX session

The NiriFX session includes the complete compositor feature set: movement and
swaps, pointer wobble, continuous fragments and interruption improvements,
alongside opening, closing and resize effects. Pick the effects you want in
Library; individual patches are a development detail.

Prepare the full build and a separate configuration, then select that pair for
the next login. Stock Niri stays installed and available. These commands never
restart the running compositor or modify a shell checkout.

The current source installation is a **single-user, systemd-based** workflow.
Distribution packages are not published yet. It requires the
stock `/usr/bin/niri`, `/usr/bin/niri-session`, `niri.service` and
`niri-shutdown.target`, plus the distribution's Niri portal configuration and
runtime dependencies. Dinit, NixOS integration and multi-user distribution
packages remain on the [roadmap](../ROADMAP.md#installation-selection-and-rollback).
Keep using the nested preview if you do not want a separate login session.

## Prepare a version

The session commands below are available in the current source checkout; they
are newer than the published 0.19 package. Install that checkout in a persistent
Python environment and retain it, for example:

```sh
python3 -m venv ~/.local/share/niri-fx/session-tools
~/.local/share/niri-fx/session-tools/bin/pip install .
```

Use `~/.local/share/niri-fx/session-tools/bin/niri-fx` in place of `niri-fx` below.
Commands also work as `python3 -m niri_fx` from the checkout, but its location and
Python interpreter must remain available to the login launcher. Keep the
installation used by an existing launcher until you have reviewed its replacement.

Use the default tool and session-storage paths, or paths without spaces or
command metacharacters. SDDM splits the login command without interpreting quoted
arguments. Entry preparation therefore accepts only letters, digits and
`_./:@+-` in its interpreter and launcher paths, and rejects incompatible paths
before staging. Configuration source paths are not subject to this entry-specific
restriction.

Build a desktop candidate from the NiriFX checkout:

```sh
python3 scripts/build-nirifx-session.py
```

This command includes all patches, desktop features, release optimization and
focused regression tests. Use the exact candidate directory printed by the
builder. Reduced-feature builds exist only as developer regression controls and
cannot be staged as full desktop sessions. Run the candidate's
[native acceptance checks](fragment-drag.md) before deciding to use it.

Install that full candidate using your existing Niri configuration as the
baseline:

```sh
niri-fx native install --candidate /path/to/candidate \
  --config ~/.config/niri/config.kdl
niri-fx native install --candidate /path/to/candidate \
  --config ~/.config/niri/config.kdl --apply --expect-plan REVIEWED_SHA256
```

The first command reviews all files without writing or running the candidate.
Use its `plan_sha256` in the second command. Apply copies the executable and
include tree, prepares the **NiriFX** entry and selects the pair for the next
login in one transaction. It reads frozen patch evidence from that candidate,
not another mutable checkout. Incomplete, reduced-feature and debug builds are
refused. A handled validation failure restores the transaction's owned changes.

Use `--root /path/to/native-storage` for a separate test installation and
`--name "NiriFX (test)"` for a distinct chooser label; repeat the same arguments
when applying. Your source configuration, shell checkout and running desktop are
unchanged. Continue with [choosing effects](#choose-effects-in-studio) and
[registering the login entry](#add-the-login-entry). The configuration must
already contain the terminal, shell startup and exit bindings you want to use.

### Advanced: stage without selecting

Create and review a **self-contained** candidate configuration. You can start
with the pinned Niri source's `resources/default-config.kdl` and add your desired
effects using Studio after staging. Configure your
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
version does not overwrite an earlier one. Use [Studio](#choose-effects-in-studio)
to change effects, or edit the source candidate config and stage it again for
other desktop settings. Do not edit a stored bundle.

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
writer: iRiS continues editing its usual stock Niri files. For this source-based
workflow, use Studio's native target for effects; edit the source configuration
and stage a new pair for other desktop settings. Do not redirect global
`XDG_CONFIG_HOME` to work around this boundary.

Following live shell settings beneath a separate NiriFX effect layer is on the
[integration checklist](../ROADMAP.md#one-integrated-product). Until that lands,
changing a shell's ordinary desktop settings requires importing a new baseline
to see those changes in the managed session.

## Choose effects in Studio

Inside a managed NiriFX session, `niri-fx studio` detects it automatically.
You can also prepare choices from another session with an explicit native
target. Both work independently of iNiR, DMS, Noctalia or another shell:

```sh
niri-fx studio --target native
# Use the same storage root if you prepared a separate test installation:
niri-fx studio --target native --native-root /path/to/native-storage
```

Studio captures the selected bundle when it opens. To start from another retained
bundle, add `--native-base BUNDLE_ID`. The storage root and base are fixed for that
Studio session; imported JSON cannot select filesystem paths or executables.

Choose **Open**, **Close**, **Resize** or **Move / swap**, then click a style
to preview and assign it. **Combos** selects a complete look; **More options**
contains shared styles and detailed action controls. Each action can use
**Preserve / NiriFX Style / Off**. Preserve
inherits the chosen baseline, including its existing user settings and effects.
When reopening a previously customized bundle, Preserve returns to its original
baseline for that action. It does not retain an override you are removing.

For a fragment-capable build, the continuous-fragment selector offers **Gentle**,
**Tear** and **Cascade**. Selecting one explicitly sets its matching movement
material and native controls. **Use profile movement** uses the profile's normal
movement choice. The continuous settings belong to the managed bundle's recipe;
portable profile JSON alone does not contain those extra native controls.
The browser preview is still a timed movement preview, not a simulation of the
continuous fragment renderer.

Review your choices, then choose **Apply to desktop** when Studio verifies a
running managed session using the same build and baseline. Studio prepares and
validates a new retained configuration, then asks Niri to load it without
restarting your desktop. It waits for a successful configuration-load event before
reporting success. The same choices are selected for the next login.

From stock Niri, an offline session or a different compositor build, Studio offers
**Select for next login** instead. Existing bundles remain unchanged. A handled
staging or validation failure restores files still owned by the transaction; if a
subsequent live reload fails or cannot be confirmed, Studio reports that separately
from the saved next-login selection. Niri's reload event has no request identifier,
so avoid simultaneously loading configurations through another tool.
The launcher validates the selected pair again before starting it.

Reopen the selected recipe to continue editing. Repeated edits replace the effect
overlay relative to the same original baseline; they do not stack includes or
require older bundles to supply configuration files. The status distinguishes
the startup session, last confirmed Studio reload, next login and rollback.
Rollback has its own review and confirmation. It also reloads immediately when the previous selection
uses the same verified running build and baseline; otherwise it changes the next login.

Only the installed local Studio can manage bundles. The online Studio remains
a place to preview effects and export portable JSON. You can import that JSON
locally and review it against your selected build. Live standalone activation
continues to require a verified running renderer; preparing a native next-login
configuration validates the retained build instead and makes no claim about the
current session.

Choose prefabs from the CLI without writing JSON:

```sh
niri-fx list --profiles --text
niri-fx native presets --text
niri-fx native configure BASE_BUNDLE_ID --profile fragments-motion --fragment-preset tear
```

Use `--preset balanced` for a single opening/closing style, or `--document` for
your saved combo. An explicit `--fragment-preset` replaces only its movement
choice with the matching continuous material and response. Other actions retain
the selected profile's choices. Applying still requires the reviewed fingerprint:

```sh
niri-fx native configure BASE_BUNDLE_ID --document ./my-combo.json
niri-fx native configure BASE_BUNDLE_ID --document ./my-combo.json \
  --apply --expect-plan REVIEWED_SHA256
```

Use the same selection arguments and `--root` on review and Apply. The available
continuous presets are `gentle`, `tear` and `cascade`. Baseline global
animation Off/slowdown settings remain in force and can suppress or alter the
chosen effects.

### Apply from the terminal

Add `--live` to both review and Apply to update the running managed session:

```sh
niri-fx native configure BASE_BUNDLE_ID --document ./my-combo.json --live
niri-fx native configure BASE_BUNDLE_ID --document ./my-combo.json --live \
  --apply --expect-plan REVIEWED_SHA256
```

The command verifies the session advertised by `NIRI_SOCKET`, requires the same
compositor build and original baseline, and waits for configuration-load
confirmation. A missing or incompatible session is refused before saving a new
selection. A changed session or receipt invalidates the review. Without `--live`,
`native configure` continues to select settings only for the next login.

The JSON result separates `activation` from `live.status`. Only
`live.status: "applied"` confirms the reload. A rejected or unconfirmed reload
returns exit status 1; its saved next-login selection remains available. Review
the reported state before retrying. Avoid concurrent configuration reloads from
other tools, as described in the Studio flow above.

To recover the previous same-build selection on the current desktop:

```sh
niri-fx native rollback --live
niri-fx native rollback --live --apply --expect-plan REVIEWED_SHA256
```

Live rollback requires a retained compatible target. Use ordinary
`native rollback` to prepare a different build for the next login.

### Keep the login runtime compatible

Customized bundles use a newer receipt format. Upgrade the NiriFX Python
installation recorded in the login launcher before selecting one. A launcher
pinned to an older, separate installation will not gain support merely because
a newer CLI or Studio creates the bundle. Keep the original installation and
stock session available while reviewing a launcher migration.

Current source builds provide [managed tool updates](tool-updates.md) for this
migration. After registering the stable entry once, CLI, Studio and login use
one reviewed runtime selection, with compatibility checks and tool rollback.

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

Once registered, log out when convenient and choose **NiriFX**, or the custom
name you supplied.
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
