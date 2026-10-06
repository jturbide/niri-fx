# Arch Linux and CachyOS

The `niri-fx` AUR package builds the released CLI and Studio from source. It
includes the preset library, portable examples, optional picker resources and
an application-menu entry. It works with stock Niri and keeps shell integrations
optional.

The full NiriFX compositor and login session still use the
[session installation guide](native-session.md). Installing this tools package
does not add movement hooks to stock Niri or install a new login session.

## Install and try

Choose one package:

| Package | Source | Update behavior |
| --- | --- | --- |
| [`niri-fx`](https://aur.archlinux.org/packages/niri-fx) | Latest packaged release | Versioned updates through your AUR helper |
| [`niri-fx-git`](https://aur.archlinux.org/packages/niri-fx-git) | Current `main` branch | Development checks or an explicit rebuild |

Both install the same command and menu entry and conflict with each other.
Start with `niri-fx` for the versioned release. Development builds can contain
changes beyond its release notes; read [Unreleased](../CHANGELOG.md).

Review the [AUR package](https://aur.archlinux.org/packages/niri-fx) and its build
files before installing. With an existing AUR helper, for example:

```sh
paru -S niri-fx
# Alternatively: yay -S niri-fx
/usr/bin/niri-fx studio --active
```

You can also build with standard Arch tools:

```sh
git clone https://aur.archlinux.org/niri-fx.git
cd niri-fx
# Review PKGBUILD, .SRCINFO, README.Arch and the desktop entry.
makepkg --syncdeps --install
```

Choose **NiriFX Studio** in your application launcher. Chromium provides an
app-style window; otherwise Studio uses your default browser. Install Niri to
validate and apply effects. Preview and JSON export also work without a running
compositor. Quickshell and GTK pickers remain optional.

Choose the style for each action, then **Review & apply**. Package installation
does not enable effects or change your configuration. Start with
[the first-combo walkthrough](getting-started.md#choose-your-first-combo).
Importable JSON examples are installed in `/usr/share/doc/niri-fx/examples/`.

## Updates and existing installations

Use your normal AUR update workflow, then close and reopen Studio. Refreshing a
browser page still uses its existing Studio process. A system Python minor-version
upgrade can require rebuilding AUR Python packages.

For `niri-fx-git`, enable your helper's development-package checks (for example,
`paru -Syu --devel` or `yay -Syu --devel`) or rebuild the recipe. The AUR metadata
does not change for every Git commit. Switch channels through the package manager
and review its replacement transaction; do not force conflicting files to overwrite.

Existing per-user launchers may take precedence over packaged commands or menu
entries. Use `/usr/bin/niri-fx --version` and `/usr/bin/niri-fx studio --active`
to inspect and open this package explicitly. Do not delete a managed launcher to
make the versions appear equal.

An existing full NiriFX session retains its own tool environment and compositor
bundles. An AUR update does not switch that selection. Follow
[managed tool updates](tool-updates.md) for source installations. The full-session
package workflow below instead retains a private copy of the packaged Python
sources. Ordinary package replacement never overwrites either selected runtime.

## Full-session package development

The repository includes a `niri-fx-compositor-git` recipe for the complete
compositor and a **NiriFX (package)** login entry. It is not yet published on AUR
or declared a supported full-session distribution. Use the
[packaging workflow](../packaging/arch/README.md#full-session-packaging) to build
and validate it together with `niri-fx-git` from the same source revision.
Physical login, capture, suspend and mixed-monitor acceptance remain open.

After installing the paired development packages in a test environment, review
first adoption as the normal user:

```sh
/usr/bin/niri-fx native adopt --config ~/.config/niri/config.kdl
```

Review the proposed files and `plan_sha256`, then repeat the command with
`--apply --expect-plan REVIEWED_SHA256`. This copies the compositor, configuration
and tools into retained user storage and selects them for the next login. It
does not enable new effects or restart your desktop. Select **NiriFX (package)**
at the next login; keep **Niri** available for recovery.

For subsequent package updates, omit `--config`:

```sh
/usr/bin/niri-fx native adopt
/usr/bin/niri-fx native adopt --apply --expect-plan REVIEWED_SHA256
```

Use the explicit `/usr/bin/` command to adopt the newly installed tools. The
ordinary user launcher intentionally keeps using the previously retained tools
until adoption succeeds. Updates preserve the selected recipe and exact shader
bytes, including shared stock/native projections. Shared settings continue to
follow the existing normal Niri configuration. Frozen installations retain their
snapshot; adoption does not silently switch them to shared settings.

Existing managed launchers must complete [tool migration](tool-updates.md#migrate-existing-launchers-once)
before package adoption. Customized or unrecognized launchers are preserved and
refused. The generic entry uses the current user's default XDG data storage;
custom-root sessions keep their existing per-user entry.

Use reviewed `native rollback` for the compositor and `native tools-rollback`
for tools, passing the packaged entry as `--registered-entry` for tools. Earlier
copies remain available after package replacement. They still depend on system
Python and shared libraries; this does not freeze the distribution's ABI.
Removing the compositor package removes its chooser entry, not retained settings
or bundles. Stock Niri remains available.

If adoption is interrupted, return through stock Niri and review the same system
command again. Exact partial copies and dispatcher updates can be resumed.
Changed or unrecognized files are preserved and refused; do not delete retained
storage to force an update.

## Restore or remove

Use Studio's **Restore previous** for changes applied by the standalone tools.
Restore refuses to overwrite later external edits. Native session rollback is
a separate operation described in the [session guide](native-session.md#roll-back).

```sh
sudo pacman -R niri-fx
# Use niri-fx-git instead if you installed the development package.
```

Removal leaves saved profiles, configuration and Restore history in place.
Restore effects before removal if you want the underlying configuration back.
Stock Niri and shell packages remain installed.

## Package scope and validation

The package owns its CLI, Python module, Studio menu entry, icon, examples and
licenses. It has no installation hooks, service activation, shell patches or
writes to home directories. It neither provides nor conflicts with stock Niri.

The [packaging checks](../packaging/arch/README.md) cover source checksums,
metadata, unit tests, extracted-package CLI/Studio resources, isolated Arch
installation/removal and stock-file preservation. They do not establish physical
desktop, suspend, display-manager or screen-sharing acceptance. The remaining
full-session gates are on the [roadmap](../ROADMAP.md#arch-packaging-and-full-session-adoption).
