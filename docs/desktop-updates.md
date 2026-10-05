# Updating your desktop with NiriFX

NiriFX should not make your shell or compositor checkout harder to update.
Use external user configuration and supported shell interfaces for stock
effects. The NiriFX compositor has its own maintained build and update lifecycle.

## Stock Niri and desktop shells

Update stock Niri and your shell through their normal package manager or updater.
NiriFX keeps profiles, generated effects and Restore history in user-owned
configuration and state directories. Keep those directories when updating the
NiriFX package; see [Updating NiriFX](upgrading.md).

| Setup | Integration boundary |
| --- | --- |
| iNiR/iRiS | Its external preset registry and existing configuration helper; Library and Studio run as a separate app. |
| DankMaterialShell | Its supported launcher adapter, with a NiriFX include outside shell-managed files. |
| Noctalia | Its existing Niri Animations plugin and external preset directory. |
| Other shells and bars | The standalone include, app launcher or a supported external widget/plugin. |

Normal installation must not patch a shell's tracked QML, scripts or module
declarations. A custom placement in a settings page needs a supported extension
point or an accepted upstream change. Quickshell itself does not provide one
common settings API for every shell.

If a shell changes its helper contract, NiriFX should report the incompatible
adapter and preserve the current configuration. The standalone app and stock
export remain separate ways to use NiriFX. Do not work around a failed update
with a blanket reset, overwrite or stash deletion.

Run `niri-fx doctor` after an update and check an ordinary open/close cycle.
If configuration validation fails, retain your saved profile and use the
[reviewed Restore workflow](setup.md#restore-a-setup). Source-managed dotfiles
may still need their owner's normal merge process; NiriFX cannot resolve
unrelated local modifications automatically.

## Removing the earlier compact iRiS entry

The earlier source-checkout installer placed a compact entry directly inside
iRiS Window Motion. That modified two tracked iNiR files and could block an
iNiR pull. New installations no longer use this approach.

Open `niri-fx studio --target inir` to choose, customize, apply and restore
effects. The existing external preset registration still works. From a NiriFX
checkout, `python3 scripts/install-desktop.py` adds an on-demand app launcher.

To remove only the earlier source integration, review the cleanup first:

```sh
python3 scripts/install-iris-integration.py --remove
python3 scripts/install-iris-integration.py --remove --apply
```

Use `--source /path/to/inir` for a nonstandard checkout. Cleanup removes the
recognized NiriFX insertion and module entry, plus unchanged owned component
and icon files. It retains unrelated and newer upstream content, makes a
recovery snapshot, and refuses ambiguous or customized integration files.
Removing this UI entry does not remove your profiles or disable active effects.
Reopen settings after cleanup; if your shell disables live reload, restart the
shell through its normal launcher when convenient.

Historical `--restore` remains available for installations whose complete
files still match the original snapshot. After upstream edits, that exact
Restore correctly refuses; use the reviewed `--remove` migration instead.
Other personal changes in iNiR can still require reconciliation. Automatic
stashing is not the NiriFX integration model.

## The full NiriFX compositor

The native patches are tied to an exact Niri revision and ordered patch stack.
They are not plugins that an arbitrary newer Niri executable can load. A newer
upstream release may need a port and fresh rendering, input and capture tests.

New source builds record [versioned build identity](../experimental/README.md#inspect-build-identity).
The read-only inspector detects changed files and missing desktop build
prerequisites. Its result does not approve a login-session upgrade.

Every build now creates an [isolated candidate](../experimental/README.md#isolated-build-candidates)
with separate source, build output and a copied executable. Failed attempts
cannot overwrite an earlier working build. Testing requires choosing that
candidate's manifest explicitly; no build updates a launcher or login selection.

Start with `python3 scripts/build-nirifx-session.py` and an isolated nested preview.
The [session installer](native-session.md) prepares the full desktop bundle,
login entry and next-login selection in one reviewed operation. Building alone never installs or selects
a compositor. Preserve your stock session; do not apply the patch inside a
distribution's package source or replace its installed executable manually.

Desktop builds need the upstream desktop feature set, not just the minimal
nested-test binary. Session wiring also covers D-Bus, portals and service
lifetime; upstream documents this in [Packaging niri](https://niri-wm.github.io/niri/Packaging-niri.html)
and [Getting started](https://niri-wm.github.io/niri/Getting-Started.html).
Successful compilation or matching file hashes do not establish desktop or
capture acceptance.

### Available commands and planned distribution packages

The CLI supports reviewed local bundles, next-login selection, rollback and
a staged per-user systemd login entry. [Studio's native target](native-session.md#choose-effects-in-studio)
adds reviewed effect changes and rollback using the same retained bundles.
Registering the entry with a display manager remains an administrator step.
Dependency-aware distribution packages and signed compositor downloads are still
planned:

1. Install a separately named NiriFX compositor package/session alongside stock
   Niri. Keep stock configuration free of unsupported native nodes.
2. Download or build a candidate with an exact upstream revision, ordered patch
   hashes, build features, toolchain information and binary identity.
3. Validate the candidate and its configuration in isolation. Publish supported
   distribution/architecture combinations and known limitations with each build.
4. Select the candidate for the **next login** after review. Never replace or
   restart a running compositor as part of a background update.
5. Retain the previous working version and its matching configuration for
   rollback. Stock Niri remains available from the session chooser.

Normal Niri and shell updates must remain independent of that selection. The
native package still needs compatible shared libraries and drivers; keeping an
old executable alone is not a guarantee after a system upgrade. Package metadata
must express those dependencies, and unsupported builds need a clear return to
stock rather than a system-wide update hold.

The maintainer flow is: select an upstream revision, port the patch stack, run
native and package acceptance, then publish a versioned candidate. The
[upstream compatibility checks](native-compatibility.md) test declared build
combinations without altering any user's installation. Narrow upstream
contributions may eventually reduce the patch
burden, but their acceptance cannot be assumed.

The [update lifecycle checklist](../ROADMAP.md#updates-and-native-build-lifecycle)
tracks the remaining packaging, session, rollback and compatibility work.
