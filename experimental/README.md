# NiriFX compositor source and developer checks

For the complete NiriFX session, use **`python3 scripts/build-nirifx-session.py`**
and follow [session setup](../docs/native-session.md). It includes all patches,
desktop features and regression tests in one optimized build. Choose effects
through Library or the CLI; individual patch variants below are for development
and regression comparisons.

This directory contains a patch for Niri **8ed0da44d974c32c6877d2f4630c314da0717ecb**
(26.04). These rendering interfaces are maintained by NiriFX, not upstream Niri.
The patches are **GPL-3.0-or-later**, matching Niri;
see [COPYING-NIRI](COPYING-NIRI). NiriFX's original Python/GLSL code remains MIT.
Niri's original source and copyright notices remain in the patched checkout.

From the repository root, with Niri's native build dependencies and a working
Rust toolchain installed:

```sh
python3 scripts/build-niri-movement.py --release --test
# Use the exact candidate manifest printed by the builder:
NIRIFX_MOVEMENT_MANIFEST=/path/to/candidate/manifest.json python3 scripts/nested-demo.py
```

For the separate [pointer-wobble prototype](../docs/pointer-wobble.md):

```sh
python3 scripts/build-niri-movement.py --pointer-wobble --release --test
NIRIFX_POINTER_MANIFEST=/path/to/candidate/manifest.json \
  python3 scripts/nested-demo.py --pointer-wobble gentle
```

This adds `niri-pointer-wobble.patch` on top of the movement patch in its own
checkout and build directory. Drag a synthetic card by its title bar. Gentle,
Rubber Sheet and Release Settle are available; the normal movement build keeps
its existing behavior. Neither command installs a login compositor.

The current Studio Library can store these choices in portable profiles and
export the native config. `nested-demo.py --custom PATH.json` accepts a pointer
profile with or without a timed movement shader. See the
[profile and activation guide](../docs/pointer-wobble.md#choose-it-in-studio).

For [continuous square fragments](../docs/fragment-drag.md), build with
`--fragment-drag --release --test`, then run the printed command with
`NIRIFX_FRAGMENT_MANIFEST` pointing to that candidate's manifest.
This adds `niri-fragment-drag.patch` after both existing patches in a separate
checkout. Eligible square movement shaders use persistent springs for dragging
and timed moves; earlier builds retain their timed shader behavior. The extension
has its own renderer capability query and remains a local prototype.
Run `python3 scripts/fragment-demo.py` to compare Gentle, Tear and Cascade in
the same owned preview using buttons or `Alt+1/2/3`; `Alt+0` turns movement effects
off there. See the [fragment guide](../docs/fragment-drag.md#native-settings) for
controls and the difference between a preset reload and an active drag.

Build dependencies are documented in the pinned source's `docs/wiki/Getting-Started.md` (Building section).
The script fetches the exact upstream commit, applies the patch, builds with
`--locked --no-default-features` by default, and records the patch/binary hashes.
Add `--desktop` to retain upstream desktop features such as D-Bus, portals and
PipeWire when preparing a build for a desktop session. Source and
build output stay below `artifacts/`; Cargo uses the selected toolchain's cache.
It refuses unrelated source changes. `--release` builds
an optimized binary; the default debug build is for development, not benchmarking.
The launcher rejects a changed binary or patch until rebuilt.

### Isolated build candidates

Every invocation creates a new `artifacts/native-builds/` candidate directory.
Its source, Cargo target directory, copied patches and published executable are
separate from every earlier attempt. Both Cargo's final-output and intermediate
[build directories](https://doc.rust-lang.org/cargo/reference/config.html#buildbuild-dir)
are scoped to that attempt. Successful builds publish `manifest.json`
and an independent `bin/niri`; a later Cargo build cannot overwrite that copy.
Failed or interrupted attempts remain available for diagnosis and do not become
selectable candidates. A retry creates another directory.

The builder prints the candidate path and a command to test it. There is no
automatic latest-build selection. Set the matching variable for the commands
you intend to run; do not add these development selections to shell startup:

| Build | Manifest selection |
| --- | --- |
| Movement | `NIRIFX_MOVEMENT_MANIFEST` |
| Pointer wobble | `NIRIFX_POINTER_MANIFEST` |
| Continuous fragments | `NIRIFX_FRAGMENT_MANIFEST` |
| Unmodified baseline | `NIRIFX_BASELINE_MANIFEST` |

For several checks, export the variable in that test terminal and unset it
afterward. An explicit selection must pass its build metadata, variant, binary
and current-patch checks; invalid selections fail rather than falling back.
Recorded patch copies preserve provenance, but do not make an older executable
compatible with a changed harness or configuration contract.

Without a variable, existing tools retain their earlier fixed manifest paths.
New builds never replace those manifests, binaries or source directories. Legacy
Movement Demo launchers therefore keep their previous build; use the printed
candidate command to try a newer one. Candidate testing does not install or
select a login session. Versioned installation and rollback are still planned.

### Inspect build identity

New builds also record a versioned `native_build` block in their candidate
manifest: the pinned upstream revision, ordered patch hashes, Cargo lockfile,
reported executable features, build profile, Rust compiler and native host target.
The input fingerprint and binary hash identify different things: recorded build
inputs and output bytes. They are not a signature or a reproducible-build claim.
The builder selects `RUSTC` when set, otherwise `rustc` on its selected `PATH`,
and passes that same compiler to Cargo. Ambient Cargo configuration, wrappers
and compiler flags are not a complete part of this fingerprint.

Inspect a build without running its executable:

```sh
python3 scripts/inspect-native-build.py \
  --manifest /path/to/candidate/manifest.json \
  --source /path/to/candidate/source
# Check the release/default-feature prerequisites for a desktop candidate:
python3 scripts/inspect-native-build.py \
  --manifest /path/to/candidate/manifest.json \
  --source /path/to/candidate/source --desktop
```

The inspector reads the manifest, binary, current patch files and source lockfile.
It reports `metadata-match`, `stale`, `incompatible` or `unknown`; only a metadata
match exits successfully. Older manifests without the new evidence remain
`unknown` to this inspector. Existing demo readers still accept their original
fields; old artifacts are not rewritten to invent missing build inputs.

`--desktop` checks recorded release mode and the full default desktop feature set.
It does not establish renderer support, library/driver compatibility or physical
desktop acceptance. Neither inspection mode executes a candidate, changes
configuration or installs/selects a session. Continue with the separate
[native-session workflow](../docs/native-session.md) for next-login selection;
[distribution packages](../docs/desktop-updates.md#available-commands-and-planned-distribution-packages)
remain planned.

### Toolchain and isolated demo

The prototype was validated with Rust 1.99.0. A working toolchain on `PATH` is
sufficient. For an isolated toolchain, the build script also detects rustup under
`artifacts/toolchain/{cargo,rustup}`. Toolchain installation is separate from the
build helper; it does not change system packages or shell startup files.

The demo requires an existing Niri desktop and Quickshell. It opens a separate
Niri window with two synthetic app cards. Click inside it, then use:

- **Alt+Left / Alt+Right:** exchange adjacent columns.
- **Alt+R:** change column width (fragment resize requires `--resize`).
- **Alt+Q:** close the demo.

The parent desktop may reserve some keys. The demo runs without `--session`,
uses a generated config with no startup shell/bar, and directs its clients to
its own Wayland socket. Closing it stops its own clients. It does not install a
binary, session, service, or movement shader into your normal Niri configuration.
Logs and captures stay in a new `artifacts/nested-demo-*` directory each run.

```sh
python3 scripts/nested-demo.py --preset vortex --duration-ms 1200
# Reduce native deformation without changing the preset:
python3 scripts/nested-demo.py --preset slice-exchange --movement-strength 0.35
# Include resize fragments as well:
python3 scripts/nested-demo.py --resize
# Optional automated native rendering check (also requires grim and Pillow):
python3 scripts/nested-demo.py --smoke
```

## Prototype shader contract

Only this patched build accepts `custom-shader` inside `window-movement`.
It calls `vec4 move_color(vec3 coords_geo, vec3 size_geo)` with the same single
texture and geometry matrices as the opening shader, plus `niri_move_delta`
(total displacement in logical pixels). `niri_clamped_progress` runs 0 to 1;
`niri_random_seed` is stable while that tile's movement effect is active.
`niri_move_impulse` blends direction changes without snapping the shader's orientation.
Retargeting preserves shader phase and its sampled speed, then continues toward
reconstruction. Cubic direction transitions also carry their incoming speed,
including another reversal before the first transition finishes.
With a custom movement shader configured, interrupted tile and column offsets
retain their sampled velocity through a cubic position handoff. The new path ends
at the destination with zero velocity on the movement clock. Initial moves keep
the configured easing/spring curve. A reversal can briefly continue in its previous
direction; it does not clamp away momentum or guarantee acceleration continuity.
Output colors use premultiplied alpha. The geometry follows Niri's animated
position; shaders should deform around it rather than translate by the full
movement again. Fragments uses a symmetric breakup/reassembly pulse.

The hook combines column and tile animation state, draws current window contents
and decorations into an offscreen texture, and renders into an expanded area.
Its element reports no opaque region. It reuses the normal render context for
capture filtering. Opening takes priority; a concurrent resize can be rendered
into the movement texture. Removing the shader restores ordinary movement.
Compilation errors keep the last working shader, following Niri's existing
custom-shader behavior; without a previous shader, ordinary rendering remains.

## Runtime verification and output feedback

The patch adds two versioned NiriFX IPC requests, separate from upstream APIs:

```sh
niri msg -j niri-fx-capabilities
niri msg -j niri-fx-frame-timings
```

Capabilities report schema 1, movement shader contract 2, whether a probe compiled
in the running renderer, whether movement is configured and whether frame feedback
is available. The isolated probe is destroyed after compilation; it does not
replace the active movement shader. NiriFX's [setup workflow](../docs/setup.md#activate-movement-in-a-running-session)
also compares executable identity before allowing explicit standalone activation.
Older experimental builds lack this handshake and must be rebuilt.

Frame feedback is a bounded history of at most 512 submitted/presented frames,
including output name, monotonic nanoseconds, sequence and protocol flags. Winit
records estimated submission time. DRM records presentation feedback; hardware
claims require VSYNC, HW_CLOCK and HW_COMPLETION flags. This history does not
contain application content, window titles or monitor serial numbers. Public
reports omit output names. [Measurement commands and limits](../docs/performance.md#native-output-feedback).

## Interruption behavior

Closing while a window is opening carries its original opening shader, seed and
clock into a fading continuation. Particles keep approaching their destinations;
they do not reverse into a fresh explosion. Closing during movement similarly
retains its phase, impulse, seed and remaining displacement while fading. The
continuation uses the compositor clock and starts its translation with the
sampled layout velocity and actual remaining offset; shader phase no longer
determines the remaining travel distance. Fading has its own closing clock.
This interruption path takes precedence over the usual closing style, including
when a profile has different opening and closing families.

With a custom movement shader or a selected NiriFX resize shader configured,
interrupted resizing also retains the displayed width and height and their
sampled velocities. Each axis owns its curve: changing width leaves an ongoing
height transition on its original deadline. Matching neighbor movement keeps
stacked and adjacent edges together through the tested reversals and minimum-size
retargets. Active paths keep their timing across a reload; newly moving axes use
the new timing. Profiles preserve existing resize settings unless NiriFX Style
or Off is selected for Resize.

The current development build also retains the original phase, reference geometry
and shader program for generated resize shaders carrying the continuity marker.
New client content blends on a separate clock; a replacement shader takes effect
on the next episode. Stock Niri and unmarked shaders keep their existing interface.
Build the experimental compositor from the same checkout to use this behavior;
movement contract 2 alone does not establish retained resize support.

Closing during a marked resize continues its frozen material, phase and size
paths. Rendering applies resize, then any continuing opening or movement effect,
then the closing fade. Borders and shadows follow the changing geometry.
Fullscreen windows and transitions, changed output scale and unavailable material
keep the protected snapshot fallback.
See the [closing handoff](../docs/resize.md#closing-during-resize),
[width and height comparisons](../docs/validation.md#resize-geometry-continuity)
and their [reproduction guide](../docs/gifs/README.md#native-resize-geometry-comparisons).

The path retains separate normal/blocked-out snapshots for Niri capture rules.
It does not make a cross-window particle simulation or guarantee velocity
continuity for every layout event. See the [recordings](../docs/showcases.md).

```sh
python3 scripts/record-native-gif.py --all
python3 scripts/record-movement-scenarios.py
```

Keep the host unlocked and the owned test window visible. The harness rejects unexpected output sizes and stalled interruption commands. Recorders require Quickshell, Pillow, grim, wf-recorder and FFmpeg. They capture
only their own nested compositor with synthetic mint/violet app cards.

## Scope and remaining work

Verified locally: column swaps with both textured windows fragmented, intact
arrival, animated resize, shader removal on hot reload, legacy config parsing,
repeated retargets, close-during-open and close-during-move, width/height reversal
with matching neighbor geometry, orthogonal resize retargets,
and resize/cancellation layout regression tests. Marked resize shaders also pass
retained phase/reference, shader reload/removal, and changing capture restrictions
in owned nested Output, ScreenCapture and debug Screencast views. See the
[material acceptance scope](../docs/validation.md#retained-material-acceptance-unreleased).

The shared base patch also tracks pointer presses and consumed bindings per
device. Virtual-device removal releases only presses without a surviving owner;
another device's valid grab and suppression state are retained. The
[ownership gate](../docs/validation.md#pointer-driven-wobble) covers the base and
optional pointer builds. Physical unplug/replug remains untested.

This is not the complete transaction/particle engine described in
[the movement design](../docs/movement.md):

- It follows existing tile/column animation clocks. The separate
  [pointer extension](../docs/pointer-wobble.md) adds bounded drag deformation;
  neither path gives workspace/camera panning a particle timeline.
- Repeated actions preserve shader phase, seed and the sampled phase/direction
  derivatives. Interrupted tile/column position paths retain velocity too;
  acceleration, camera transitions and one shared swap transaction remain
  separate work.
- Two streams overlap, but each window is still a separate render element.
  Particle-level interleaving/collisions and shared physics are not implemented.
- Large excursions can clip at output/workspace boundaries. The expanded draw
  region and offscreen pass cost GPU work; there is no frame-time acceptance yet.
- Sequential 1×/1.5×/2× scales and resize/fullscreen interruptions have a nested
  stress harness. Resize-to-close has separate phase, privacy, margin and popup
  checks. Real mixed outputs, blurred-background capture, PipeWire and
  graphics-reset behavior need broader validation
  before replacing a login compositor. The TTY path compiles but was not activated.

Stock configuration exports contain supported window actions and selected stock
desktop timing. Studio retains experimental movement and pointer settings in
portable JSON. `doctor --niri-binary PATH` checks the selected executable's parser,
the running session's identity and its versioned renderer contracts. Reviewed
standalone activation requires a matching, verified runtime and separate explicit
consent for each experiment. Shell adapters apply stock actions. See
[movement diagnostics](../docs/setup.md#movement-support) and
[pointer activation](../docs/pointer-wobble.md#reviewed-activation).

Portable profiles with an explicit movement slot are accepted by
`python3 scripts/nested-demo.py --custom PATH.json`. The demo uses owned synthetic
Quickshell cards and isolated configuration, state and D-Bus directories. It uses
the selected movement duration unless `--duration-ms` overrides it. General
rearrangement checks run with `python3 scripts/test-movement.py`; see the
[movement guide](../docs/movement.md#movement-presets-and-general-rearrangement).
## Independent swap styles

The full NiriFX builder includes `niri-swap.patch` after movement, pointer and
continuous-fragment support. This is part of the complete session, not a separate
consumer build. Older retained three-patch bundles remain readable and keep their
shared movement behavior.

`animations { window-swap { ... } }` selects a timed movement shader for explicit
`swap-window-left` and `swap-window-right` commands. Omission uses the movement
configuration; `off` disables these swaps independently. Pointer dragging and
column reordering retain their movement style. An active swap retains its shader
through reloads and closing; later episodes use the new settings. Explicit Off
wins when another swap starts. The separate `NiriFxSwapCapabilities` IPC contract
reports parser-independent renderer verification without activating an effect.

Build the full session, select its manifest, and run:

```sh
NIRIFX_FRAGMENT_MANIFEST=/path/to/candidate/manifest.json \
  python3 scripts/test-native-swap.py
```

The owned nested test uses synthetic color shaders to distinguish action routing,
including singleton and stacked columns, reload, close, inheritance and Off.
It does not replace the running desktop or establish physical-monitor acceptance.
