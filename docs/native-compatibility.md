# Native compatibility and package preparation

The NiriFX compositor combines all native features in one pinned source and
patch stack. Build that complete session candidate with:

```sh
python3 scripts/build-nirifx-session.py
```

This command always uses all three patches, upstream desktop features, release
optimization and focused native regressions. It reuses the isolated builder;
there is no feature-subset choice or automatic installation. The
[compatibility matrix](../experimental/native-compatibility.json) describes
specific compile targets to check before considering a new candidate. It does
not install a compositor, select a session or certify a distribution or physical
desktop. Keep the stock Niri session available throughout manual testing.

## Declared CI targets

The initial matrix targets upstream revision
`8ed0da44d974c32c6877d2f4630c314da0717ecb`, its exact `Cargo.lock`, Rust 1.99.0
and `x86_64-unknown-linux-gnu` on Ubuntu 24.04. Rust 1.99.0 is an
[official stable release](https://blog.rust-lang.org/2026/10/01/Rust-1.99.0/).
These are declared test inputs; consult the matching workflow run for results.
Adding a matrix row alone does not establish compatibility.

| Case | Ordered patch stack | Cargo feature policy |
| --- | --- | --- |
| `nirifx-desktop` (default) | Movement, pointer wobble, continuous fragments | Upstream defaults |
| `movement-desktop` (internal control) | Movement | Upstream defaults |
| `pointer-desktop` (internal control) | Movement, pointer wobble | Upstream defaults |
| `fragment-minimal` (internal control) | Movement, pointer wobble, continuous fragments | `--no-default-features` |

Desktop features include D-Bus, systemd and GNOME screencasting support, with
the PipeWire feature enabled by the latter. The runner checks Cargo's actual
feature list, compiler host, binary and lockfile against the selected row. The
word `desktop` in a case name describes this feature policy, not a login test.
The default CI run compiles only the complete NiriFX case. A manual run can
request the expanded matrix to compile the three internal controls as well.
These controls are regression fixtures, not separate products or session
choices. All CI cases use debug builds so the binary and focused library tests
share compilation work. A release candidate needs the separate optimized build
produced by `build-nirifx-session.py`.

Every run first checks clean patch application for unmodified, movement,
pointer and fragment variants. Compile cases reuse the existing builder's
configuration, layout, animation, resize, input ownership and renderer-helper
regressions, plus the pointer and fragment tests applicable to each stack.
They do not launch a compositor or exercise GPU rendering and capture.

## Run a check

From the source checkout, inspect the validated CI matrix:

```sh
python3 scripts/check-native-compatibility.py matrix
# Include internal compile controls:
python3 scripts/check-native-compatibility.py matrix --expanded
```

Check all patch stacks without compiling. An optional existing Niri checkout
supplies Git objects for the exact pinned commit; its worktree, index and refs
are not changed or used as candidate source:

```sh
python3 scripts/check-native-compatibility.py patches \
  --source-cache /path/to/existing/niri-checkout \
  --report artifacts/compatibility-patches.json
```

Without `--source-cache`, the checker fetches the exact commit from upstream.
Each stack gets a fresh attempt under `artifacts/native-compatibility/attempts`.
The checker copies the patch inputs, verifies the applied diff and lockfile,
then retains a report and local command logs. Failed attempts also remain for
diagnosis. Existing report paths are refused; choose a new path for a repeat.

To compile one case, install the declared Rust toolchain and the native build
dependencies first. The workflow uses the development libraries listed by the
[pinned upstream CI](https://github.com/niri-wm/niri/blob/8ed0da44d974c32c6877d2f4630c314da0717ecb/.github/workflows/ci.yml):

```sh
rustup toolchain install 1.99.0 --profile minimal
CARGO_BUILD_JOBS=2 python3 scripts/check-native-compatibility.py build \
  --case nirifx-desktop \
  --report artifacts/compatibility-nirifx.json
```

The runner selects the exact Rust toolchain for this process and reuses
`build-niri-movement.py` to allocate an independent source, Cargo target,
intermediate build directory and copied executable. It never reuses an
accepted binary or manifest. A successful build manifest remains compilation
evidence; the separate compatibility report must also pass its matrix checks.
The report includes recorded build identity and file hashes without local
source or executable paths. A build ID is an input fingerprint, not a signature
or a claim that all ambient compiler flags and system libraries were captured.

The [native workflow](../.github/workflows/native-compatibility.yml) runs manually
or on pull requests that change its matrix, patches and build tools. It does not
repeat the same compilation automatically after merging to main. It pins action revisions,
limits compilation to two simultaneous jobs with two Cargo workers each, and
caches dependency downloads only. Every job compiles and tests fresh outputs.
Diagnostic artifacts contain reports and build logs, not distributable binaries
or session configurations. Logs can contain runner paths and should be reviewed
before copying them into public documentation.

## Prepare a distribution release candidate

The current [managed session workflow](native-session.md) already stores
versioned binary/configuration pairs and preserves stock Niri. The next package
step should reuse that model rather than create a second selection mechanism.
The following is a package plan, not an available distribution package:

1. Build the full optimized NiriFX candidate with the same reviewed inputs using
   `python3 scripts/build-nirifx-session.py`.
   Retain its exact upstream revision, ordered patches, lockfile, compiler,
   features, binary checksum and source/license material.
2. Package the compositor under a separate name such as `niri-fx-compositor`
   and a versioned private path, for example
   `/usr/lib/niri-fx/compositor/<build-id>/niri`. Do not replace `/usr/bin/niri`
   or declare a package conflict with stock Niri. Keep the separate NiriFX
   session entry and managed selection/rollback behavior.
3. Build and declare runtime dependencies for each intended distribution and
   architecture. A successful Ubuntu compile does not establish CachyOS package
   compatibility. System library updates can invalidate an otherwise unchanged
   executable; source and checksum identity do not prove the host ABI still fits.
4. Validate the exact optimized package in an owned nested session, including
   renderer capability checks, configuration, input cancellation, protected
   capture and fallback. Then record physical login/logout, rollback, suspend,
   output hotplug, mixed scales and actual PipeWire screencasting on the intended
   display manager, service manager and GPU combinations.
5. Review source availability, licenses, package dependency bounds, checksums
   and signatures before publishing a release candidate. Record failed gates
   and supported combinations explicitly. No package should download a mutable
   nightly, promote itself or overwrite a selected/running version on update.

Promotion remains a separate reviewed operation affecting the next login. The
running binary/configuration pair and rollback bundle must stay available.
Normal distribution updates to stock Niri remain independent; compatibility
tests should assess candidate upstream revisions in new attempts before changing
the pinned matrix. Physical acceptance and distro packaging remain separate
gates even after all compile jobs pass.
