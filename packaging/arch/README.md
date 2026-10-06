# Arch packaging

There are exactly two package recipes. `niri-fx/` builds a fixed release tag;
`niri-fx-git/` tracks `main` and derives its version from the source version,
commit count and commit ID. Users install one channel. **Both contain the full
product:** CLI, Studio, presets, examples, compositor and login entry.

Each recipe uses one NiriFX checkout for the wheel, native patches and session
launcher. The native source is pinned separately to the canonical upstream Niri
revision and receives the complete four-patch stack. Stock Niri stays installed
for service lifecycle, portal configuration and recovery. Users can continue to
use stock Niri with the tools without adopting the included session.

See the [user guide](../../docs/arch-linux.md) for installation and updates.
Packaging sources use 0BSD, as recorded in each recipe's `LICENSE` and
`REUSE.toml`; application and upstream licensing is preserved in the payload.

## Validate a recipe

Work from a copy so downloaded sources and build files stay outside the checkout:

```sh
mkdir -p artifacts/arch-package/review
cp packaging/arch/niri-fx/{PKGBUILD,.SRCINFO,README.Arch,niri-fx-studio.desktop,niri-fx-packaged.desktop,LICENSE,REUSE.toml} \
  artifacts/arch-package/review/
cd artifacts/arch-package/review
makepkg --verifysource
makepkg --printsrcinfo > .SRCINFO.generated
diff -u .SRCINFO .SRCINFO.generated
namcap PKGBUILD
makepkg --cleanbuild
namcap niri-fx-*.pkg.tar.zst
```

Repeat with `niri-fx-git/` in a separate directory. Check submitted `.SRCINFO`
before building: development `pkgver()` updates the copied recipe after resolving
its source. Retain the exact source commit and effective metadata with evidence.

The release recipe uses a fixed Git tag and checks its Python version against
`pkgver`. Makepkg uses `SKIP` checksums for VCS sources; this is not automatic
SSH tag-signature authentication. Maintainers verify the signed release tag and
its commit before publishing the recipe. Local desktop, README and license files
have explicit SHA-256 checksums.

From the repository root, audit the complete archive without installing it:

```sh
python3 scripts/check-arch-package.py \
  artifacts/arch-package/review/niri-fx-VERSION-RELEASE-x86_64.pkg.tar.zst
```

The bounded archive reader rejects unsafe paths, links, installation hooks,
unexpected files and incomplete tools or compositor payloads. It verifies wheel
resources and metadata, licenses, both desktop entries, native provenance and
final binary hashes. It also exercises extracted CLI commands, portable recipes,
stock exports and offline previews outside the checkout.

## Clean build and installed acceptance

The **Arch package** workflow builds both channels in official Arch containers.
Its helper, `scripts/test-arch-package.sh`, refuses host execution. Candidate
checks explicitly substitute the exact tested checkout for the release tag or
moving branch and retain the original and effective source metadata. This lets a
pull request validate the new package before its release tag exists. It does not
establish that the release tag has been published.

The build downloads locked Cargo dependencies in `prepare()`, then runs native
regressions and release compilation offline. Each complete archive is audited
and installed in a disposable container. The session acceptance helper exercises
two synthetic users, read-only review, stale-review refusal, adoption, retained
tools after removal and unchanged stock Niri files. No graphical session starts.

The installation helper also accepts a previously published tools-only archive
for upgrade checks. Keep its archive hash and package identity with the evidence;
never point the helper at a host installation.

To test adoption after an update, provide an earlier complete archive from the
same channel through `NIRIFX_ARCH_PREVIOUS_SESSION_ARCHIVE` when running
`test-arch-package.sh` inside the disposable container. The helper adopts that
baseline before installing the freshly built candidate. You can also test two
existing archives without recompiling:

```sh
# Inside a disposable official Arch container, as root:
NIRIFX_ARCH_PACKAGE_CONTAINER=1 bash scripts/test-arch-session-package.sh \
  /evidence/adopted-update /fixtures/baseline.pkg.tar.zst /fixtures/candidate.pkg.tar.zst
```

The check reviews adoption for one user, preserves the other user's selection,
and exercises rollback separately for changed tools and compositor identities.
Same-archive reinstallation cannot establish an upgrade or rollback; the report
distinguishes unchanged identities from exercised transitions. A changed binary
hash from a rebuild does not establish changed compositor behavior. Keep the
source revisions and package hashes with the results.

Physical login, mixed monitors, PipeWire capture, suspend/resume and compatibility
with changed system Python or shared libraries have separate acceptance gates.

The producer strips its owned executable before recording its final SHA-256.
Makepkg stripping and debug splitting are disabled to preserve that identity.
Makepkg's C/C++ LTO flags are also disabled because GCC LTO objects from
PipeWire's C helpers cannot link with Rust's LLVM linker. Rust's release-profile
thin LTO remains enabled. See Arch's
[package options](https://man.archlinux.org/man/PKGBUILD.5.en#options_(array)).

Namcap cannot infer every dynamically used session dependency or optional QML
import. Review warnings against the actual payload and installed execution;
do not suppress all diagnostics. Errors block publication.

## Publish an update

1. Verify the signed release tag and commit for `niri-fx`, or the tested development
   revision for `niri-fx-git`. Confirm the release recipe's tag actually exists.
2. Update `pkgver` and reset `pkgrel` for a new release. Increment `pkgrel` for a
   packaging-only change to the same source version.
3. Refresh changed local source checksums and regenerate `.SRCINFO`.
4. Pass clean build, archive and installed acceptance for each channel. Check
   upgrades from the earlier tools-only packages when changing file ownership.
5. Copy only the recipe, `.SRCINFO`, both desktop entries, `README.Arch`, `LICENSE`
   and `REUSE.toml` into the matching AUR checkout. Sign the commit, verify its
   signature and confirm the published remote ref.

Do not publish downloaded sources, binaries, credentials or raw evidence in AUR
Git. Package installation must not adopt settings, enable effects, switch the
selected runtime or restart a compositor. Reviewed per-user adoption happens
through the included CLI after installation.

## Prepared offline builds

The same producer can build from an already-patched tree and populated Cargo
cache without running makepkg:

```sh
python3 scripts/build-nirifx-session.py \
  --prepared-source /path/to/prepared-niri \
  --build-root /path/to/build-attempts \
  --cargo-home /path/to/cargo-cache \
  --target-cache /path/to/compatible-target-cache \
  --output /path/to/new-session-candidate \
  --strip-program /usr/bin/strip
```

Use a fresh output path. The producer verifies the upstream commit and exact
patch diff, copies source without Git hardlinks, and neither changes the prepared
tree nor fetches dependencies during compilation. The export contains a relative
manifest, binary, Cargo lockfile, upstream license/readme and frozen patches.

A retained copy still depends on distribution libraries, Python and drivers.
Keep the [native distribution acceptance](../../docs/releasing.md#native-release-candidates)
and [validation limits](../../docs/validation.md) aligned with actual results.
