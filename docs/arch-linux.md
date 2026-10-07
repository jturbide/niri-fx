# Arch Linux and CachyOS

Choose `niri-fx` for a released version or `niri-fx-git` for current development.
Starting with 0.22, **either package includes everything**: Studio, CLI, presets,
examples, the complete patched compositor and its login entry. There is no
separate tools or compositor package to install.

Use Studio with stock Niri, or set up the included NiriFX session for advanced
movement and pointer effects. Installing the package does not change your
current session, configuration or enabled effects. Shell integrations remain
optional.

## Install and try

Choose one package; they provide the same commands and conflict with each other:

| Package | Source | Update behavior |
| --- | --- | --- |
| [`niri-fx`](https://aur.archlinux.org/packages/niri-fx) | Fixed release tag | Versioned updates through your AUR helper |
| [`niri-fx-git`](https://aur.archlinux.org/packages/niri-fx-git) | Current `main` branch | Development checks or an explicit rebuild |

Review the package's build files before installing. With an existing AUR helper:

```sh
paru -S niri-fx
# Alternatively: yay -S niri-fx
/usr/bin/niri-fx studio --active
```

For development versions, substitute `niri-fx-git`. Read
[Unreleased](../CHANGELOG.md) for changes beyond the latest release.
Both packages build the complete compositor from source and currently target
Arch x86_64. Allow time and memory for the Rust build even if you plan to use
only the tools with stock Niri.

You can also build the release with standard Arch tools:

```sh
git clone https://aur.archlinux.org/niri-fx.git
cd niri-fx
# Review PKGBUILD, .SRCINFO and the included source files.
makepkg --syncdeps --install
```

Choose **NiriFX Studio** in your application launcher. Chromium provides an
app-style window; otherwise Studio uses your default browser. Preview and JSON
export also work without a running compositor. Quickshell and GTK pickers remain
optional. Importable examples are installed in `/usr/share/doc/niri-fx/examples/`.

## Use the tools with stock Niri

Stay in your normal Niri session and open Studio. Choose a style for each
supported action, then **Review & apply**. Start with
[the first-combo walkthrough](getting-started.md#choose-your-first-combo).
Native movement hooks are available only in the NiriFX session; installing the
package does not add them to the running stock compositor.

No separate package, shell source modification or session switch is needed for
stock-supported effects. NiriFX keeps the normal `niri` package installed for
its session services, portal configuration and recovery entry.

## Use the NiriFX session

The package includes the full compositor and a **NiriFX (package)** login entry.
The development version of local Studio offers **Review setup** near the top of
the window. Review the files, then choose **Apply for next login**. First setup
keeps a saved copy of the Niri configuration selected when Studio opened; it does
not apply an unsaved Studio draft. Enable shared settings later from the session
controls if you want normal Niri edits to follow both sessions.

The CLI remains available in released versions. Before first use, review setup
as your normal user:

```sh
/usr/bin/niri-fx native adopt --config ~/.config/niri/config.kdl
```

Read the proposed files and `plan_sha256`, then repeat with the reviewed hash:

```sh
/usr/bin/niri-fx native adopt --config ~/.config/niri/config.kdl \
  --apply --expect-plan REVIEWED_SHA256
```

This retains the compositor, configuration and tools in your user storage and
selects them for the next login. Select **NiriFX (package)** when you next log in.
Keep **Niri** available for recovery. Choose your effects in Studio; setup does
not enable additional effects automatically.

Existing source-installed managed launchers first need the
[one-time tool migration](tool-updates.md#migrate-existing-launchers-once).
Customized or unrecognized launchers are preserved and refused. The generic
entry uses the default XDG data location; custom-root installations keep their
existing per-user entry.

## Updates and existing installations

Update one package through your normal AUR workflow. The first update from the
0.21 tools-only packages also builds and installs the compositor and login entry.
Existing tools remain usable with stock Niri; adopting the session is your choice.
No split-package migration or additional package selection is required.

For `niri-fx-git`, enable your helper's development-package checks (for example,
`paru -Syu --devel` or `yay -Syu --devel`) or rebuild the recipe. The AUR metadata
does not change for every Git commit. Switch channels through the package manager
and review its replacement transaction; do not force conflicting files to overwrite.
A system Python minor-version upgrade can require rebuilding AUR Python packages.

After a standalone tools update, close and reopen Studio. Refreshing a browser
page still uses its existing Studio process. Existing per-user launchers may
precede packaged commands; use `/usr/bin/niri-fx --version` and
`/usr/bin/niri-fx studio --active` to inspect and open the system installation.

In the development version of local Studio, **Review update** uses the installed
package's tools, even if Studio is still running an earlier retained version.
**Cancel** changes nothing. After Apply, save any draft and reopen Studio from
its launcher. The compositor selection takes effect at the next NiriFX login;
Studio never restarts your desktop or installs system packages.

The setup card distinguishes the installed package, running desktop and next
login. If package metadata, launchers or required files cannot be verified, it
shows the reason rather than offering an update. Package installation remains
part of your normal AUR workflow. These controls are local; online Studio cannot
inspect or change a desktop installation.

For the CLI, review an adopted session's newly installed version without `--config`:

```sh
/usr/bin/niri-fx native adopt
/usr/bin/niri-fx native adopt --apply --expect-plan REVIEWED_SHA256
```

Package replacement does not switch the running or next-login runtime. Review
and Apply retain the new package's tools and compositor together, preserving
your selected recipe, exact shader bytes and shared or frozen settings mode.
Use the explicit `/usr/bin/` command: the ordinary managed launcher continues to
use its previously selected tools until adoption succeeds.

Shared settings continue to follow the existing normal Niri configuration.
Frozen installations retain their snapshot; adoption does not silently switch
them to shared settings. Source-installed sessions can continue to use
[managed tool updates](tool-updates.md) instead.

## Roll back or remove

Use Studio's **Restore previous** for effects applied through the standalone
tools. Restore refuses to overwrite later external edits. Session rollback uses
reviewed `native rollback` for the compositor and `native tools-rollback` for
tools. For the latter, pass
`--registered-entry /usr/share/wayland-sessions/niri-fx-packaged.desktop`.
See [session rollback](native-session.md#roll-back).

Earlier retained copies remain available after package replacement. They still
depend on system Python, shared libraries and drivers; retaining a binary does
not freeze those dependencies. If adoption is interrupted, return through stock
Niri and review the same command again. Exact partial copies can be resumed;
changed or unrecognized files are preserved and refused. Review again to get a
new fingerprint before applying; a review made before the interruption no longer
describes the partial copy. Keep that copy for inspection if a conflict is reported.

```sh
sudo pacman -R niri-fx
# Use niri-fx-git instead if you installed the development package.
```

Removal deletes package-owned tools, the candidate and chooser entry. It leaves
saved profiles, configurations, Restore history and retained session bundles
in place. Stock Niri remains installed. Restore effects before removal if you
want the underlying configuration back.

## Recover after a dependency update

Retained tools and compositor copies still use system Python and shared
libraries. A saved copy protects the selected files, not the surrounding system.
Keep your retained bundles and profiles while repairing the affected dependency.

| Symptom | Recovery |
| --- | --- |
| `/usr/bin/niri-fx` reports `No module named niri_fx` after a Python update | Rebuild your chosen AUR package for the installed Python version. An adopted user's retained launcher loads its own copy of the package and can remain usable while system site-packages are unavailable. |
| A retained launcher reports an incompatible interpreter or cannot import its tools | Restore a compatible Python installation, or use the repaired system CLI to review adoption of compatible tools. |
| `/usr/bin/python3` itself is missing or cannot start | Repair the system Python package from a terminal or TTY. Python-based launchers cannot print their own recovery message when their interpreter cannot run. |
| Niri reports a missing shared library or symbol | Repair the distribution's library/package mismatch, then rebuild the chosen NiriFX package if needed. A previous retained binary may depend on the same unavailable library. |

Use the stock **Niri** login entry while repairing a NiriFX-specific failure.
If the missing dependency also affects stock Niri, use a TTY or another working
session for package repair. Restoring a dependency does not change the selected
tools, compositor or recipe; retry the selection after the repair.

Follow Arch's [Python rebuild guidance](https://wiki.archlinux.org/title/Python#Module_not_found_after_Python_version_update)
and [system maintenance guidance](https://wiki.archlinux.org/title/System_maintenance#Partial_upgrades_are_unsupported).
Complete system updates and rebuild affected AUR packages together; avoid mixing
individual library versions as a permanent workaround.

## Scope and tested environments

The package owns its CLI, Python module, Studio menu entry, icon, examples,
compositor candidate, login entry and licenses. It does not replace stock Niri,
modify shell checkouts, write user configuration during installation or activate
services through installation hooks.

The [packaging checks](../packaging/arch/README.md) cover complete archive contents,
builds, installed tools, reviewed adoption and removal using disposable accounts.
Physical login, GPU, mixed-monitor, screen-sharing and suspend acceptance remain
tracked separately in the [validation guide](validation.md) and
[roadmap](../ROADMAP.md#arch-packaging-and-full-session-adoption).
