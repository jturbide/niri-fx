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

`niri-fx-compositor-git/` is the development recipe for the complete pinned
four-patch compositor. Pair it with `niri-fx-git` built from the same commit.
It does not replace stock Niri, which supplies the established service lifecycle
and portal configuration. The distinct `niri-fx-packaged.desktop` entry resolves
each user's retained selection without adopting anything during login.

The recipe fetches locked Cargo dependencies in `prepare()`, then builds and
runs native regressions offline. The shared producer copies and strips the
executable before recording its hash. Its compact export contains a relative
manifest, binary, Cargo lockfile, upstream license/readme and frozen patch stack.
Makepkg stripping/debug splitting is disabled to preserve that final hash.

For a prepared, already-patched source tree and populated Cargo cache, the same
producer can be exercised independently:

```sh
python3 scripts/build-nirifx-session.py \
  --prepared-source /path/to/prepared-niri \
  --build-root /path/to/build-attempts \
  --cargo-home /path/to/cargo-cache \
  --target-cache /path/to/compatible-target-cache \
  --output /path/to/new-session-candidate \
  --strip-program /usr/bin/strip
```

Use a fresh output path for each attempt. The producer verifies the upstream
commit and exact canonical patch diff, uses a local copy without Git hardlinks,
and does not alter prepared source or fetch dependencies during compilation.

Inspect paired package archives without installing them:

```sh
python3 scripts/check-arch-session-package.py /path/to/niri-fx-compositor-git-VERSION.pkg.tar.zst \
  --tools-package /path/to/niri-fx-git-VERSION.pkg.tar.zst
```

Run `scripts/test-arch-session-package.sh` only in a disposable Arch container
with its explicit container marker. The harness accepts paired archive paths,
tests separate users and retained selections, then removes packages and compares
stock files. It never starts the display-manager session. See its usage for the
required paths and marker; do not bypass its host-execution guard.

The prepared offline producer has passed its 168 native test executions and
relocation checks. Staged archives using that real binary have also passed
installation, two-user adoption, stale-review refusal, package removal and
stock-file preservation in disposable Arch. These archives used an explicit
working-tree fixture version; that evidence does not certify the recipe's full
source-fetch and clean distribution build path.

Publication remains gated on actual package acceptance and the
[native distribution gates](../../docs/releasing.md#native-release-candidates).
In particular, package checks do not establish physical login, screen sharing,
suspend, mixed-monitor behavior or compatibility across system Python/library
upgrades. Retaining sources and binaries does not retain the distribution ABI.
