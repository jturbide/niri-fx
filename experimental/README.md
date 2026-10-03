# Experimental Niri movement hook

This directory contains a patch for Niri **8ed0da44d974c32c6877d2f4630c314da0717ecb**
(26.04). It is an isolated prototype, not an upstream Niri API or an installed
compositor replacement. The patch is **GPL-3.0-or-later**, matching Niri;
see [COPYING-NIRI](COPYING-NIRI). NiriFX's original Python/GLSL code remains MIT.
Niri's original source and copyright notices remain in the patched checkout.

From the repository root, with Niri's native build dependencies and a working
Rust toolchain installed:

```sh
python3 scripts/build-niri-movement.py --release --test
python3 scripts/nested-demo.py
```

Build dependencies are documented in the pinned source's `docs/wiki/Getting-Started.md` (Building section).
The script fetches the exact upstream commit, applies the patch, builds with
`--locked --no-default-features`, and records the patch/binary hashes. Source and
build output stay below `artifacts/`; Cargo uses the selected toolchain's cache.
It refuses unrelated source changes. `--release` builds
an optimized binary; the default debug build is for development, not benchmarking.
The launcher rejects a changed binary or patch until rebuilt.

The prototype was validated with Rust 1.99.0. A working toolchain on `PATH` is
sufficient. For an isolated toolchain, the build script also detects rustup under
`artifacts/toolchain/{cargo,rustup}`. Toolchain installation is separate from the
build helper; it does not change system packages or shell startup files.

The demo requires an existing Wayland desktop and Alacritty. It opens a separate
Niri window with two colored synthetic clients. Click inside it, then use:

- **Alt+Left / Alt+Right:** exchange adjacent columns.
- **Alt+R:** change column width (fragment resize requires `--resize`).
- **Alt+Q:** close the demo.

For an optional app-launcher entry, run `python3 scripts/install-desktop.py --movement-demo`,
then open **NiriFX Movement Demo**. Remove
`~/.local/share/applications/niri-fx-movement-demo.desktop` to remove it.

The parent desktop may reserve some keys. The demo runs without `--session`,
uses a generated config with no startup shell/bar, and directs its clients to
its own Wayland socket. Closing it stops its own clients. It does not install a
binary, session, service, or movement shader into your normal Niri configuration.
Logs and captures stay in a new `artifacts/nested-demo-*` directory each run.

```sh
python3 scripts/nested-demo.py --preset vortex --duration-ms 1200
# Reduce native deformation without changing the preset:
python3 scripts/nested-demo.py --preset slice-exchange --movement-strength 0.35
# Opt into resize fragments as well:
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

## Interruption behavior

Closing while a window is opening carries its original opening shader, seed and
clock into a fading continuation. Particles keep approaching their destinations;
they do not reverse into a fresh explosion. Closing during movement similarly
retains its phase, impulse, seed and remaining displacement while fading. The
continuation uses the compositor clock and starts its translation with the
sampled layout velocity; fading has its own closing clock.
This interruption path takes precedence over the usual closing style, including
when a profile has different opening and closing families.

The path retains separate normal/blocked-out snapshots for Niri capture rules.
It does not make a cross-window particle simulation or guarantee velocity
continuity for every layout event. See the [recordings](../docs/showcases.md).

```sh
python3 scripts/record-native-gif.py --all
python3 scripts/record-movement-scenarios.py
```

Recorders require Quickshell, Pillow, grim, wf-recorder and FFmpeg. They capture
only their own nested compositor with synthetic mint/violet app cards.

## Scope and remaining work

Verified locally: column swaps with both textured windows fragmented, intact
arrival, animated resize, shader removal on hot reload, legacy config parsing,
repeated retargets, close-during-open and close-during-move,
and existing resize/cancellation layout regression tests.

This is not the complete transaction/particle engine described in
[the movement design](../docs/movement.md):

- It follows existing tile/column animation clocks. Direct pointer dragging and
  workspace/camera panning do not get a new particle timeline.
- Repeated actions preserve shader phase, seed and the sampled phase/direction
  derivatives. Layout-position velocity, acceleration and one shared swap
  transaction remain separate work.
- Two streams overlap, but each window is still a separate render element.
  Particle-level interleaving/collisions and shared physics are not implemented.
- Large excursions can clip at output/workspace boundaries. The expanded draw
  region and offscreen pass cost GPU work; there is no frame-time acceptance yet.
- Sequential 1×/1.5×/2× scales and resize/fullscreen interruptions have a nested
  stress harness. Real mixed outputs, capture restrictions, popups,
  interrupted resize/close and graphics-reset behavior need broader validation
  before replacing a login compositor. The TTY path compiles but was not activated.

Stock Studio saves only supported open, close and optional resize settings.
Movement settings should be exposed in iRiS only after capability detection and
the compositor contract are settled.
