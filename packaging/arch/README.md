# Arch packaging

`niri-fx/` contains the release recipe mirrored to the AUR. It builds a fixed,
checksum-verified source release with standard Python build tools. A GitHub
prerelease is still a fixed release; this recipe does not track a moving Git tip.
`niri-fx-git/` tracks `main` and derives its version from source metadata, the
commit count and commit ID. It provides and conflicts with `niri-fx`. Keep the
two recipes' payloads consistent; users install one channel at a time.
The package contains CLI/Studio and their resources. See the
[user guide](../../docs/arch-linux.md) for installation and managed-session limits.
The packaging sources use 0BSD, as recorded in each recipe's `LICENSE` and
`REUSE.toml`. This does not change the application's MIT/GPL licensing.

## Validate a recipe

Work from a copy of the recipe so build files remain outside the source tree:

```sh
mkdir -p artifacts/arch-package/review
cp packaging/arch/niri-fx/{PKGBUILD,.SRCINFO,README.Arch,niri-fx-studio.desktop,LICENSE,REUSE.toml} \
  artifacts/arch-package/review/
cd artifacts/arch-package/review
makepkg --verifysource
makepkg --printsrcinfo > .SRCINFO.generated
diff -u .SRCINFO .SRCINFO.generated
namcap PKGBUILD
makepkg --cleanbuild
namcap niri-fx-*.pkg.tar.zst
```

Repeat with `packaging/arch/niri-fx-git/` in its own build directory for the
development channel. Verify submitted `.SRCINFO` before building: `pkgver()`
updates the copied development recipe to its resolved source revision. Retain
that revision and its regenerated metadata with the build evidence.

From the repository root, inspect and exercise the resulting package outside
the checkout without installing it:

```sh
python3 scripts/check-arch-package.py \
  artifacts/arch-package/review/niri-fx-VERSION-RELEASE-any.pkg.tar.zst
```

The checker requires Python and `zstd`. It rejects unsafe archive paths, links,
installation hooks and files outside the tools package's declared locations.
It verifies installed resources, license texts, desktop integration, portable
recipes, stock exports and offline preview generation. Package metadata supplies
the tested version, so the recipe can remain on the latest release while `main`
develops the next one.

The **Arch package** workflow builds in an official Arch container, tests a real
installation and removal, and verifies that stock Niri files and a disposable
user's settings remain intact. Its container-only helper refuses host execution.
Keep physical desktop acceptance separate from this package test.

Namcap can report the optional Quickshell/QML imports and interpret the
`niri_fx.cli.main` entry-point function as an external Python module. Review those
warnings against the package's optional dependencies and actual installed CLI
execution; do not silence all namcap diagnostics.

## Publish an update

1. Use a published source release and verify its checksum independently.
2. Update `pkgver` and reset `pkgrel` for a new upstream release. Increment
   `pkgrel` for packaging changes to the same upstream version.
3. Refresh checksums for changed local source files and regenerate `.SRCINFO`.
4. Pass local and isolated Arch checks; inspect the archive for unintended files.
5. Copy only the recipe, `.SRCINFO`, desktop entry, `README.Arch`, `LICENSE` and
   `REUSE.toml` into the AUR checkout. Create a signed commit and verify the remote
   ref after pushing.

Do not publish build artifacts, downloaded archives, credentials or raw test
evidence. Do not use package installation hooks to adopt or activate effects.

## Full-session packaging

The full session will need a package-aware adoption workflow before publication:

- Build the complete pinned four-patch compositor from explicitly prepared source,
  with locked dependencies, desktop features and offline compilation.
- Package a relocatable candidate and provenance. Complete binary processing
  before computing the recorded hash, and prevent later stripping from changing it.
- Supply a generic login entry that resolves the current user's retained tools.
  Never embed the packager's home directory or Python site-packages path.
- Copy tools and compositor candidates into retained user storage through explicit
  review. Keep selected, previous and running copies independent of `/usr` updates.
- Test two package versions, multiple users, Python path changes, interrupted
  adoption and missing dependencies. Retaining a binary does not retain its system
  libraries; stock Niri remains a recovery option.

These are implementation and acceptance requirements, not current package
features. They extend the existing managed transactions instead of adding a
second settings writer. See the [native distribution gates](../../docs/releasing.md#native-release-candidates).
