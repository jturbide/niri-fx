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
[managed tool updates](tool-updates.md) to update those retained tools; system
Python is not a replacement for the required persistent virtual environment.
This separation keeps ordinary package replacement from overwriting a selected
or previous login runtime.

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
desktop, suspend, display-manager or screen-sharing acceptance. Full-session
packaging remains on the [roadmap](../ROADMAP.md#arch-packaging-and-full-session-adoption).
