# Continuous fragment motion

Continuous fragments let square pieces follow a window at
different speeds. Pressing expands the pieces around the grabbed region before
you move. A fresh grab at rest pins its piece to your hand. Distant pieces wait
near their previous screen positions, then catch up with individually varied
delays and response speeds. Reversing direction retains queued motion. Pausing
keeps the held spread; releasing reconstructs the window, including a press
that never became a drag.

This is included in the **NiriFX 0.20 session**, built from the matching source.
It uses the selected movement material for pointer dragging and timed window
movement, including column reordering. A long drag is driven by incoming motion;
it does not finish when a fixed movement timer expires or repeatedly play an
opening animation. Each window owns its own state. Pieces do not transfer
between windows during a swap.

Open `niri-fx studio --target native` after [session setup](native-session.md).
Choose **Gentle**, **Tear** or **Cascade** under continuous fragments, keep or
change your other action presets, then review your changes. Studio offers
**Apply to desktop** on a matching running session or **Select for next login**
otherwise. Shared configurations use **Apply shared settings**, which updates
the watched includes and reports file writes separately from confirmed activation.
There is no separate fragment build to install. The detailed controls and
developer checks below explain the current renderer's limits.

**Save to My profiles**, **Download JSON**, **Share settings** and config downloads
keep the portable styles but omit these native response controls. Applying or
selecting for the next login retains the continuous preset in the managed session
recipe; reopen that recipe in local Studio to continue editing it.

## Supported fragment material

The first renderer supports an unmixed square grid with no grid orientation,
roundness, shrink, size variation, direction variation or waves. Pieces must use
the Together release order and either Random or None rotation. Other fragment
shapes and effect families keep their existing timed movement behavior. The
generated material marks eligible effects automatically. The compositor draws
each source cell as a separate textured quad and retains its motion history;
far pieces no longer share one outer sheet's translation.
The native mesh is limited to 4096 source cells. A valid profile can still exceed
that budget after grid rounding or client margins; the renderer then falls back
instead of silently discarding cells. Profile validation already limits the
requested particle count to 4096.
An unsupported grid falls back for the rest of the current motion episode;
it does not keep rebuilding the same failed mesh while the pointer is held.
The next fresh episode can try the current configuration again.

Opening, closing and selected resize effects remain independent. Continuous
interactive resize is a later step. Movement duration still controls Niri's
timed placement animation; it does not limit the length of a pointer drag.
Particle count or tile size sets the source grid. Native controls govern delay,
response variation, directional motion, tilt and held spread. Portable movement
strength, focus, spin and gravity settings still govern the timed fallback shown
in existing previews. Zero movement strength disables continuous eligibility;
positive strength and the other portable controls are not mapped to native
motion yet. Like other 0.x interfaces, native control names and ranges can
change before the [stable contract](stability.md) is defined.
Closing during continuous fragment motion uses the existing protected baked
snapshot and configured close effect; it does not carry these fragment springs
through closing.

Each piece follows delayed window positions. Distance from the grab influences
its delay and response, with stable variation between neighboring pieces.
This creates a real waiting interval before a far piece begins catching up.
Its existing state continues across direction changes and release.
Lag defaults to a 768-logical-pixel cap, with a supported maximum of 1024 pixels.
The release tail ends within two seconds.
Initial screen-position retention applies below that lag cap; once it is reached,
additional window travel also carries the distant pieces.
Those caps are limits, not target animation durations. A fresh grab at rest pins
its anchor immediately. Regrabbing during motion carries the remaining state
through the anchor transition. Input hit testing and window layout retain their
normal rectangles; the visible spread does not change where clients receive
input.

The fragment material takes priority over the optional whole-window pointer
wobble while it is active. A profile does not need a pointer-wobble choice to use
continuous fragments. This renderer requires its own capability check; support
for the earlier movement or wobble extension alone is insufficient.

Movement Off disables both timed and pointer-driven fragments.
Pointer Off controls the separate whole-window wobble; it does not disable the
fragment material. Independent drag-fragment controls remain future integration
work, so this behavior should not be treated as a frozen public contract.

Niri retains its 8-pixel threshold for recognizing a drag. Once recognized,
tiled windows using a continuous fragment style verified by the display renderer
skip the separate 256-pixel pull threshold and usual lift animation. This keeps the grabbed piece
with the cursor while the distant pieces catch up. Horizontal titlebar gestures
can still scroll the viewport; use a vertical start or Niri's modifier drag to
move a tiled window. Other styles retain the usual pull threshold. Drop placement
and window ownership remain Niri's own. A shader that fails to compile keeps
ordinary drag handling, even if its metadata requests continuous fragments.

## Native settings

For a quick comparison, the isolated demo provides three starting points:

| Preset | Particles | Feel |
| --- | --- | --- |
| Gentle | 600 | Smaller separation, shorter delay and a quicker return. |
| Tear | 800 | A visible spread on press with individually delayed following. |
| Cascade | 1200 | Wider separation, longer waiting and more pronounced rotation and tilt. |

After building the fragment experiment, select its printed manifest path in
the test terminal, then launch it from the checkout:

```sh
export NIRIFX_FRAGMENT_MANIFEST=/path/to/candidate/manifest.json
python3 scripts/fragment-demo.py
# Start with another choice, or list choices without opening a window:
python3 scripts/fragment-demo.py --preset cascade
python3 scripts/fragment-demo.py --list
```

Choose a preset or Off in either synthetic card. Hold its top strip to spread
the pieces, pull down slightly, then drag in any direction. `Alt+1`, `Alt+2`,
`Alt+3` and `Alt+0` select Gentle, Tear, Cascade and Off. `Alt+F` toggles floating,
`Alt+Left/Right` reorders columns, and `Alt+Q` closes the owned preview.
Closing either card also ends the demo. Settings are temporary; this tool does
not install or activate anything in the login session.

Native controls and the source grid stay fixed throughout an active drag and
its settling tail. Changing presets takes effect on the next fresh gesture
after settling. Regrabbing before settling continues the current settings. This
avoids a jump from changing delays, release duration or lag limits mid-flight.
Off takes effect immediately. Release and let the pieces settle before comparing
another preset. The Python defaults, bounds and presets are maintained in
[`fragment_motion.py`](../niri_fx/fragment_motion.py); they are not yet portable
profile settings or Studio controls.

The NiriFX compositor accepts a `fragment-motion` block inside the same
`window-movement` node as the generated eligible shader. Omitting the block uses
these defaults. Keep the existing shader in that node; these settings alone do
not select a material. This block is not supported by stock Niri or stored in
portable Studio profiles yet.

```kdl
fragment-motion {
    batches 64
    delay-near-ms 0
    delay-far-ms 360
    delay-jitter 0.25
    response-near-ms 120
    response-far-ms 360
    response-jitter 0.30
    distance-exponent 1.2
    max-lag 768
    pin-radius 24
    press-spread 20
    press-response-ms 140
    rotation-mode "movement"
    rotation-degrees 20
    rotation-response-ms 180
    rotation-speed 1000
    tilt 0.55
    release-ms 1800
}
```

| Setting | What it changes | Supported values |
| --- | --- | --- |
| `batches` | Number of delay stages across the window. Each piece still has its own response, variation and orientation. Particle count comes from the selected material. | 1–4096 |
| `delay-near-ms`, `delay-far-ms` | How long near and far pieces wait before following incoming window positions. | 0–600 ms, near ≤ far |
| `delay-jitter` | Stable variation in each piece's waiting time. | 0–1 |
| `response-near-ms`, `response-far-ms` | How quickly pieces catch up after their waiting time. Larger values feel softer. | 20–800 ms, near ≤ far |
| `response-jitter` | Stable variation in catch-up speed between pieces. | 0–1 |
| `distance-exponent` | How strongly timing changes with distance from the grab. | Greater than 0, up to 4 |
| `max-lag` | Maximum separation from a piece's current window position. | 1–1024 logical pixels |
| `pin-radius` | Region that stays attached to the grab. | 0–256 logical pixels |
| `press-spread` | Radial expansion while pressed; zero disables press expansion. | 0–128 logical pixels |
| `press-response-ms` | How quickly the held spread opens and settles. | 20–800 ms |
| `rotation-mode` | In-plane rotation derived from each piece's movement, a stable random axis, or no rotation. | `"movement"`, `"random"`, `"none"` |
| `rotation-degrees` | Maximum in-plane rotation. | 0–60 degrees |
| `rotation-response-ms` | How quickly rotation and tilt follow changing motion. | 20–800 ms |
| `rotation-speed` | Reference movement speed for rotation and tilt; lower values make slower motion more expressive. | 1–5000 logical pixels/second |
| `tilt` | Maximum apparent depth tilt, separate from in-plane rotation. | 0–1.1 radians |
| `release-ms` | Maximum settling time after release. | 200–2000 ms |

For a longer waiting effect, increase `delay-far-ms`. Increase
`response-far-ms` for slower catch-up after that wait. More batches and jitter
spread the response across more pieces. Set `rotation-mode "none"` and `tilt 0`
for flat pieces, or `press-spread 0` to keep a press visually unchanged until
movement starts. Delay and response variation stay within their hard time bounds.

## Build and check

From a checkout with Niri's build dependencies, a Rust toolchain, Quickshell,
Wayland development tools, `grim` and Pillow:

```sh
python3 scripts/build-niri-movement.py --fragment-drag --release --test
export NIRIFX_FRAGMENT_MANIFEST=/path/to/candidate/manifest.json
python3 scripts/test-fragment-drag.py
python3 scripts/test-fragment-presets.py
python3 scripts/test-fragment-privacy.py
python3 scripts/test-fragment-fallback.py
python3 scripts/test-fragment-concurrency.py
unset NIRIFX_FRAGMENT_MANIFEST
```

Replace the example path with the one printed after a successful build. Each
attempt adds the fragment extension after the movement and pointer patches in
a fresh candidate directory. Earlier builds are preserved. See
[candidate selection](../experimental/README.md#isolated-build-candidates).
These commands do not replace the login compositor.
The default build is minimal for nested tests. Add `--desktop` when preparing a
candidate for a later real desktop session; that retains upstream D-Bus,
portal and PipeWire features. Building it does not install or activate it.
The test launches its own nested compositor with synthetic app cards and sends
virtual-pointer events only to that owned session. Configuration and captures
stay under ignored `artifacts/`; no personal desktop is recorded.

The focused acceptance harness checks:

- A press with no pointer motion, visible held expansion, unchanged logical
  geometry and reconstruction after releasing without a drag.
- A 40-pixel pointer step from a stable held pose. The
  pinned piece must follow the step while the far piece initially moves less
  than 10 pixels, measured within 60 ms. Far pieces must also remain within one
  pixel at 100 ms before catching up.
- Sixteen identifiable source-cell landmarks, with at least five independent
  movement histories and at least three among similarly distant far cells.
- Reversing a short input pulse before far pieces react, retaining their queued
  movement, then reconstructing at the released destination.
- A drag longer than the configured 350 ms placement animation, with visible
  fragment gaps after that duration has elapsed.
- Pausing while still holding the window, then moving in the opposite direction.
- Release, rapid regrab, stable reconstruction and ordinary client input.
- Timed floating-window movement with the same material, followed by column
  reordering with preserved window ownership and working input.
- A tiled window that stays attached after a 4-pixel vertical step, detaches
  after 9 pixels, then handles a prolonged drag, return drop and subsequent input.

Landmarks measure actual screen displacement, rather than accepting visible gaps
as evidence of delayed following. Interior gaps separately distinguish breakup
from a translated or bent solid sheet. Held frames must reach a stable expanded
pose; released frames must reconstruct and stop changing. Exact pose and velocity
continuity belong to native and renderer checks. Screenshots do not establish
physical input-to-photon latency. Read the local
`fragment-drag-acceptance.json` for the candidate's results and build identity.
Long-drag evidence also includes `winit-submit` frame intervals to reveal obvious
submission stalls. These intervals describe the nested output; they are not GPU
execution time, physical presentation timing or an input-latency measurement.

The companion preset harness checks all three starting points, exact
reconstruction, settings changes during holding and release, adoption on a fresh
gesture, and immediate Off with working client input. Native unit checks cover
unchanged pose/velocity at reload and a failed mesh becoming quiet until a fresh
episode. Preset acceptance does not establish a performance budget at the maximum
particle count or after a long suspended interval.

The concurrency harness checks two floating windows swapping positions and
reversing before placement finishes, then four windows retargeting together.
Every source must visibly fragment in the same captured frame, reconstruct with
its own content and retain working input. A subsequent move of one window must
leave the other three unchanged. The recorded Tear runs reconstructed with zero
changed pixels. These overlapping IPC actions are not an atomic multi-window
transaction, and pieces do not interact across windows.

The privacy harness exercises dynamic capture restrictions while pieces move,
settle and close, plus abrupt client exit and pointer-owner disconnection. It
uses a public companion as a positive control in every screenshot. Direct
`grim` captures check ScreenCapture: a `screen-capture` rule must redact content,
while a `screencast`-only rule must leave these screenshots visible. This does not
verify Output, actual Screencast transport or PipeWire privacy.

The fallback harness deliberately fails mesh GLSL compilation while retaining
valid configuration and marker metadata. Fragment-specific input requires a
matching program verified by the Output renderer. A failed effect retains Niri's
ordinary tiled pull behavior, and a valid reload restores fragment dragging.
Capture passes cannot authorize that input behavior. Expected compiler errors
are part of this test, not a successful effect activation.

See [continuous fragment performance](performance.md#continuous-fragment-state)
for measured CPU cost and the exact-rest optimization used after a long idle.

## Desktop testing and compatibility

Native use requires logging into the matching NiriFX session. Keep the
stock login session available as a return path. NiriFX Apply does not replace a
running compositor. The selected executable, running IPC peer and fragment
renderer contract must agree before native activation.

Stock Niri does not support movement shaders. Earlier experimental builds and
browser previews retain the existing timed shader fallback; they do not preview
the new persistent fragment state. A successful nested test does not establish
physical monitor, suspend/resume, Output/Screencast privacy or PipeWire support
for this new path. Those remain dedicated acceptance work before broader use.

See [native movement](movement.md), [pointer wobble](pointer-wobble.md) and the
[roadmap](../ROADMAP.md#epic-4-pointer-driven-wobble) for the related behavior and
remaining work.

## Window size and texture reuse

A window can shrink when it moves to a smaller display while its offscreen
texture keeps a larger allocation. Fragment UV coordinates use that allocation's
dimensions; window layout and cell positions keep using the content dimensions.
This preserves the window's proportions during the drag and its settling tail.

Run the owned nested regression against a finished full candidate:

```sh
NIRIFX_FRAGMENT_MANIFEST=/path/to/candidate/manifest.json \
  python3 scripts/test-fragment-texture-reuse.py
```

It compares source pixels while a synthetic window shrinks under a held grab and
after release, for width, height and both dimensions. The software-GPU mesh
check also covers retained allocation sizes. Physical mixed-monitor interaction
still needs desktop testing.
