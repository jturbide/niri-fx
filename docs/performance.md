# Measuring shader cost

The GPU harness measures a synthetic window's **WebGL shader draw time** using
[EXT_disjoint_timer_query](https://registry.khronos.org/webgl/extensions/EXT_disjoint_timer_query/).
It does not measure Niri frame time, input latency, damage tracking, capture,
scanout or dropped frames. Browser and compositor drivers can behave differently.

From the checkout, with Python, Node 22+ and hardware-accelerated Chromium:

```sh
node scripts/benchmark-gpu.mjs --output=/tmp/nirifx-gpu.json
# Choose a smaller comparison:
node scripts/benchmark-gpu.mjs --output=/tmp/nirifx-compare.json \
  --presets=balanced,core-detonation,iris-bloom --sizes=1920x1080,3840x2160 --samples=120
# Compare independent draw batches, with no desktop capture:
node scripts/benchmark-gpu.mjs --output=/tmp/nirifx-load.json \
  --presets=balanced,core-detonation --sizes=1920x1080,3840x2160 --draws=1,2,4
```

Set `CHROME_BIN` if needed. The script uses an isolated temporary browser profile,
synthetic textures and no desktop capture. It records renderer/vendor, dimensions,
parameters, seed, browser version, raw GPU samples, p50/p95/p99 and counts above
60/120/144 Hz frame budgets. The window occupies 60% of output width and 50% of
height. It warms up with 12 draws, then samples intermediate animation positions.
These budget counts are shader costs, not measured missed presentation deadlines.
`--draws` accepts counts from 1 to 8. Each sample times that many independent window
passes with staggered animation phases; each pass includes its normal framebuffer
clear. The result is the cost of the whole batch. It does not reproduce simultaneous
compositor windows, their damage/occlusion, or cross-window blending. Omitting
`--draws` retains the single-draw measurement.

Software renderers and unavailable GPU timers produce **unsupported** reports
and exit 2. Disjoint timing, context loss, invalid results and timeouts fail the
run instead of falling back to CPU timing. Use a fresh output filename each time.
`--software=true` is a diagnostic for testing that refusal path.

## Initial hardware sample

Measured on 2026-10-02 local time, NVIDIA RTX 4070 Ti through Chromium ANGLE/OpenGL
ES 3.2, 60 samples per case. Values are p95 shader milliseconds from one run:

| Preset | 1920×1080 | 2560×1440 | 3840×2160 |
| --- | ---: | ---: | ---: |
| Balanced | 0.245 | 0.399 | 0.811 |
| Core Detonation | 4.578 | 7.277 | 14.941 |
| Spring Wobble | 0.091 | 0.158 | 0.340 |
| Noise Dissolve | 0.092 | 0.231 | 0.529 |
| Iris Bloom | 0.143 | 0.264 | 0.587 |

This is a limited local observation, not a hardware guarantee or a ranking across
all presets. Core Detonation's 4K shader cost alone exceeds a 120 Hz frame budget
(8.33 ms). The compact Balanced renderer was substantially cheaper in this run.
Reproduce on your GPU before choosing demanding effects for large windows.

Particle count is a visual control, not a reliable quality setting. Unequal cells,
waves and staged release increase candidate searches; expanded drawing bounds
also cost work. For compact fragments, set size variation, direction variation
and wave strength to zero. Together release reduces the search further. Reduce
slice count for less strip work. See [validation limits](validation.md).

Physical presentation timing and mixed-output measurements remain open. A release-built
nested capture diagnostic is included below; its delivery intervals are not scanout timing.

## New reveal and distortion sample

Measured on 2026-10-03 on the same RTX 4070 Ti / Chromium ANGLE/OpenGL setup,
60 samples per case. Again, these are p95 **shader draw times**, not Niri frame
times, and the synthetic window occupies 60% of output width and 50% of height.

| Preset | 1920×1080 | 3840×2160 |
| --- | ---: | ---: |
| Ember Erosion (revised) | 0.099 ms | 0.376 ms |
| Dust Drift | 0.296 ms | 1.143 ms |
| Ghost Wisps | 0.106 ms | 0.401 ms |
| Shockwave | 0.095 ms | 0.359 ms |
| Wave Fold | 0.109 ms | 0.424 ms |

```sh
node scripts/benchmark-gpu.mjs --output=/tmp/nirifx-new-styles.json \
  --presets=ember-erosion,dust-drift,ghost-wisps,shockwave,wave-fold \
  --sizes=1920x1080,3840x2160 --samples=60
```

Dust's bounded 33-cell search costs more than the other new effects in this run.
The figures do not predict performance on integrated GPUs or under compositor load.


## Bounded fragment lookup comparison

Measured on 2026-10-03 with the same RTX 4070 Ti / Chromium ANGLE/OpenGL setup,
120 samples per case and identical parameters/seed/draw dimensions. The previous
shader searches 7×7 cells per band; the revised shader uses 5×5 when waves are
zero and retains 7×7 for waved fields. Geometry bounds are documented beside the
loop. All 231 reference frame pairs matched byte-for-byte in software WebGL.

| Preset | Output | Before p95 (ms) | After p95 (ms) |
| --- | --- | ---: | ---: |
| balanced | 1920×1080 | 0.246 | 0.242 |
| balanced | 3840×2160 | 0.802 | 0.796 |
| core-detonation | 1920×1080 | 4.532 | 2.374 |
| core-detonation | 3840×2160 | 14.989 | 7.959 |
| mosaic-burst | 1920×1080 | 1.642 | 0.909 |
| mosaic-burst | 3840×2160 | 5.298 | 2.940 |
| orbital-ribbons | 1920×1080 | 1.157 | 1.147 |
| orbital-ribbons | 3840×2160 | 4.372 | 4.318 |

[Raw samples, exact parameters and renderer metadata](benchmarks/fragment-lookup.json)
are available for both runs.

Core Detonation and Mosaic Burst improved roughly 45–47% in this sample. Balanced
uses the compact renderer, and Orbital Ribbons uses waves; their small differences
are within ordinary run variation. These are single-run shader measurements,
not a guarantee of equivalent compositor frame-rate gains.

```sh
node scripts/benchmark-gpu.mjs --output=/tmp/nirifx-lookup.json \
  --presets=balanced,core-detonation,mosaic-burst,orbital-ribbons \
  --sizes=1920x1080,3840x2160 --samples=120
# A checkout of the previous implementation is needed for rendered parity:
node scripts/compare-fragment-renderers.mjs /path/to/reference-checkout
```

## Independent window-draw batches

Measured on 2026-10-03 with the same RTX 4070 Ti / Chromium ANGLE/OpenGL setup,
60 samples after 12 warmup batches. The table shows p95 milliseconds for the
**whole batch at 3840×2160**, with each synthetic window occupying 60% of output
width and 50% of height:

| Preset | 1 draw | 2 draws | 4 draws |
| --- | ---: | ---: | ---: |
| Balanced | 0.805 | 1.295 | 2.179 |
| Core Detonation | 7.846 | 14.591 | 27.128 |
| Spring Wobble | 0.341 | 0.481 | 0.601 |
| Pixel Wipe | 0.438 | 0.498 | 0.620 |
| Shockwave | 0.393 | 0.540 | 0.609 |

[Raw 1080p/4K samples and complete parameters](benchmarks/window-batches.json)
include all 30 cases. This supports Balanced as an everyday starting point and
Spring Wobble, Pixel Wipe or Shockwave as inexpensive alternatives on the measured
hardware. Core Detonation remains a more demanding choice, especially for large
windows or repeated effects. No automatic preset changes or quality reductions
are applied.

Batches repeat independent passes, including clears. GPU scheduling and reuse
make the results non-linear; do not multiply single-window results to predict
desktop performance. Physical presentation, mixed effects and integrated GPUs
still need separate measurements.

```sh
node scripts/benchmark-gpu.mjs --output=/tmp/nirifx-window-batches.json \
  --presets=balanced,core-detonation,spring-wobble,pixel-wipe,shockwave \
  --sizes=1920x1080,3840x2160 --samples=60 --draws=1,2,4
```

## Varied-fragment flight bounds

The varied renderer now rejects pixels outside each velocity group's conservative
flight envelope before searching cells. It also rejects cells belonging to other
groups before calculating jittered boundaries. The envelope includes size
variation, wave displacement, rotation, inward scaling, wander and rotated piece
size. Particle counts, release timing and trajectories are unchanged.

The [reference comparison](../scripts/compare-fragment-renderers.mjs) checks rendered
pixels against the earlier shader. Extended cases include all gravity directions,
maximum variation, low/high wave frequency, offset origins, staged release,
tiny/wide/tall/fractional-size windows and a texture with transparent margins,
a hole and partial alpha. Readbacks use a dedicated framebuffer to isolate them
from displayed-canvas presentation. Hardware mode requires an identified hardware
renderer; software WebGL remains the default.

Measured on 2026-10-03 on the RTX 4070 Ti / Chromium ANGLE/OpenGL setup,
with 120 samples per case after 12 warmup batches. The baseline is commit
`1398399`. Values are p95 **WebGL shader milliseconds before → after**, for the
whole batch; each window occupies 60% of output width and 50% of output height.

| Preset | Output | 1 draw (ms) | 4 draws (ms) |
| --- | --- | ---: | ---: |
| Balanced | 1920×1080 | 0.243 → 0.247 | 0.650 → 0.653 |
| Balanced | 3840×2160 | 0.797 → 0.797 | 2.177 → 2.175 |
| Core Detonation | 1920×1080 | 2.391 → 1.629 | 8.030 → 5.365 |
| Core Detonation | 3840×2160 | 7.860 → 5.034 | 27.165 → 17.080 |
| Mosaic Burst | 1920×1080 | 0.910 → 0.723 | 3.088 → 2.394 |
| Mosaic Burst | 3840×2160 | 2.948 → 2.300 | 10.342 → 7.813 |
| Orbital Ribbons | 1920×1080 | 1.155 → 0.828 | 3.511 → 2.400 |
| Orbital Ribbons | 3840×2160 | 4.298 → 2.929 | 13.141 → 7.834 |

The three varied presets show about 20–40% lower p95 cost in this sample.
Balanced uses a separate compact renderer and is effectively unchanged. The
measurements cover synthetic shader draws; compositor presentation and other
GPUs still need separate measurements. Large batches of demanding effects can
remain expensive even after this improvement.

All 525 extended reference-frame pairs matched byte-for-byte on each renderer
(1,050 pairs across SwiftShader and hardware ANGLE). Existing showcases retain
the same appearance. [Raw GPU samples, source hashes and frame comparisons](benchmarks/fragment-culling.json)
include the exact settings and renderer metadata.

```sh
# Baseline before flight-envelope and early group rejection:
git worktree add --detach /tmp/nirifx-reference 1398399f4fc6d7c7a6e6abaa0453b602e24b58d3
node scripts/compare-fragment-renderers.mjs /tmp/nirifx-reference --extended
node scripts/compare-fragment-renderers.mjs /tmp/nirifx-reference --extended --hardware
node scripts/benchmark-gpu.mjs --output=/tmp/nirifx-fragment-culling.json \
  --presets=balanced,core-detonation,mosaic-burst,orbital-ribbons \
  --sizes=1920x1080,3840x2160 --samples=120 --draws=1,4
```

Re-render or re-register your effects to use the optimized shader. Updating NiriFX
alone does not rewrite shaders already saved in your compositor configuration.

## Vortex distortion

Vortex Fold and Soft Swirl use one inverse texture lookup per output pixel,
without a particle search. Measured on 2026-10-03 with an RTX 4070 Ti through
Chromium ANGLE/OpenGL ES 3.2, 120 samples after 12 warmups per case:

| Preset | 1080p, one draw | 4K, one draw | 4K, four draws |
| --- | ---: | ---: | ---: |
| Balanced | 0.244 ms | 0.808 ms | 2.178 ms |
| Shockwave | 0.095 ms | 0.443 ms | 0.647 ms |
| Vortex Fold | 0.111 ms | 0.451 ms | 0.654 ms |
| Soft Swirl | 0.094 ms | 0.349 ms | 0.486 ms |

Values are p95 synthetic GPU draw costs, including framebuffer clears. Each
window occupies 60% of the output width and 50% of its height. Four-draw batches
use staggered phases; their work differs from repeating one fixed frame four
times. These are not compositor frame times or results for integrated GPUs.
[Raw samples and exact settings](benchmarks/vortex.json).

```sh
node scripts/benchmark-gpu.mjs --output=/tmp/nirifx-vortex.json \
  --presets=balanced,shockwave,vortex-fold,soft-swirl \
  --sizes=1920x1080,3840x2160 --samples=120 --draws=1,4
```

## Native capture-delivery diagnostic

Native measurements require an explicitly selected
[candidate build](../experimental/README.md#isolated-build-candidates).
Set the matching manifest variable in the test terminal before running native
harnesses. Direct Cargo benchmarks use that candidate's `source` directory;
replace `/path/to/candidate` below with its actual path. Recompiling benchmark
code leaves the published `bin/niri` copy unchanged.

```sh
python3 scripts/build-niri-movement.py --release --test
python3 scripts/measure-native-movement.py --timing-source capture --output /tmp/nirifx-capture.json
```

This opens an isolated 1280×800 nested compositor and records six alternating
1200 ms swaps. Fixed-rate encoder resampling is disabled; the report retains
raw captured timestamps and IPC acknowledgement times. The current local sample
reported capture-interval p95 values of 4 ms for Balanced and 9 ms for Core
Detonation, with IPC acknowledgements below 14 ms at p95.
The [before/after diagnostic samples](benchmarks/native-continuity.json) record
the position-handoff patch comparison. Both use uninterrupted swaps; deterministic
state tests and the interruption recordings cover retarget behavior separately.

These unexpectedly short intervals illustrate the measurement boundary: the
nested backend can deliver captures faster than its advertised 60 Hz output.
Host compositor, screencopy and encoder scheduling all contribute. Do not convert
these numbers into physical FPS, input latency or dropped-frame estimates.
Presentation feedback on a real output is still needed for those claims.


## Resize distortion

Measured on 2026-10-03 with an RTX 4070 Ti through Chromium ANGLE/OpenGL,
120 samples after 12 warmup batches. These are p95 GPU shader milliseconds,
not compositor frame times. The synthetic client grows from 60% of output width
and 50% of height to 80% and 70%, using separate old/new textures. Each sample
covers intermediate animation phases; multi-draw batches include a clear per pass.

| Profile | 1080p, one draw | 4K, one draw | 4K, four draws |
| --- | ---: | ---: | ---: |
| Ripple Resize | 0.101 | 0.373 | 0.578 |
| Edge Ripple Subtle | 0.098 | 0.358 | 0.520 |
| Edge Ripple Expressive | 0.099 | 0.359 | 0.520 |
| Torsion Subtle | 0.098 | 0.357 | 0.512 |
| Torsion Expressive | 0.097 | 0.358 | 0.511 |

[Raw samples, parameters and renderer](benchmarks/resize-motion.json) include both
output sizes and draw counts. Edge Ripple and Torsion use two texture samples
without a particle search. Similar Subtle/Expressive costs are expected: strength
changes the displacement, not the number of samples. These single-run observations
do not predict integrated-GPU cost, shrinking, mixed effects or Niri presentation.

```sh
node scripts/benchmark-gpu.mjs --output=/tmp/nirifx-resize-gpu.json \
  --resize-profiles=ripple-resize,edge-ripple-subtle,edge-ripple-expressive,torsion-subtle,torsion-expressive \
  --sizes=1920x1080,3840x2160 --samples=120 --draws=1,4
```

`--resize-profiles` accepts enabled resize profile names from `examples/profiles`
and cannot be combined with `--presets`. Resize reports identify the action,
preview direction and both window sizes. Hardware timers are still required.

## Fragment shapes

The four shaped presets were measured on 2026-10-03 with ANGLE/OpenGL on an
NVIDIA GeForce RTX 4070 Ti. Each cell below is p95 GPU time from 60 samples of the
stated draw count, including a framebuffer clear per draw. The output size is the
canvas size; the window occupies 60% of its width and 50% of its height.

| Preset | 1920×1080 output | 3840×2160 output | Two draws at 3840×2160 |
| --- | --- | --- | --- |
| Triangle Shatter | 0.631 ms | 1.891 ms | 3.387 ms |
| Circle Burst | 0.311 ms | 1.006 ms | 1.667 ms |
| Rectangle Confetti | 0.436 ms | 1.431 ms | 2.536 ms |
| Hex Swarm | 0.279 ms | 0.946 ms | 1.547 ms |

[Raw samples and exact settings](benchmarks/fragment-shapes.json). These are
shader costs on one discrete GPU, not compositor frame times or a guarantee for
integrated GPUs. Two draws are independent passes; they do not measure two
interacting windows in Niri.

The shaped renderer computes its candidate neighborhood from the actual piece
radius, aspect ratio, wandering and inverse-wave bound. It rejects unreachable
cells before calculating motion. A deterministic seed function uses integer-valued
float arithmetic without trigonometric hashing. Software and hardware reference
comparisons cover extreme proportions, waves, gravity and animation progress.
The existing square presets keep their original shader paths unchanged.

Triangles have two pieces per cell. Larger aspect ratios, waves and staged
release can increase lookup work; reducing count alone does not guarantee lower
cost. Start with a finished preset and compare your chosen settings on your GPU.

```sh
node scripts/benchmark-gpu.mjs --output=/tmp/nirifx-shapes.json \
  --presets=triangle-shatter,circle-burst,rectangle-confetti,hex-swarm \
  --sizes=1920x1080,3840x2160 --samples=60 --draws=1,2
```

## General movement and shaped resize

Measured on 2026-10-03 with an NVIDIA RTX 4070 Ti through Chromium ANGLE/OpenGL.
Each value is p95 GPU time over 60 samples after 12 warmup draws. These are single
synthetic-window shader passes, including a framebuffer clear. They exclude
compositor layout, texture capture, simultaneous windows, scanout and input latency.
Movement uses the actual experimental shader with a synthetic directional path;
resize grows between distinct old/new textures.

| Action and preset/profile | 1920×1080 | 2560×1440 |
| --- | ---: | ---: |
| Movement: Fragment Wake | 0.423 ms | 0.706 ms |
| Movement: Ribbon Transfer | 0.177 ms | 0.309 ms |
| Movement: Momentum Glide | 0.095 ms | 0.165 ms |
| Resize: Triangle Edge Rebuild | 0.201 ms | 0.348 ms |
| Resize: Hexagon Edge Rebuild | 0.146 ms | 0.247 ms |
| Resize: Circle Soft Reflow | 0.150 ms | 0.255 ms |

[Movement samples and settings](benchmarks/general-movement.json) ·
[Resize samples and settings](benchmarks/shaped-resize.json)

These results do not establish integrated-GPU performance or compositor frame
budgets. Wider aspect ratios, different output sizes and stronger custom effects
can increase cost. Movement timing changes playback duration, not work per draw.

```sh
node scripts/benchmark-gpu.mjs --output=/tmp/movement-gpu.json --presets=fragment-wake,ribbon-transfer,momentum-glide --action=movement --sizes=1920x1080,2560x1440 --samples=60
node scripts/benchmark-gpu.mjs --output=/tmp/resize-gpu.json --resize-profiles=triangle-edge-rebuild,hexagon-edge-rebuild,circle-soft-reflow --sizes=1920x1080,2560x1440 --samples=60
```

Shaped resize uses a bounded search derived from piece extent and maximum local
drift. A wider reference search covers 72 shape/aspect/mode combinations per
renderer. Software output matches exactly; hardware differences stay within one
8-bit channel step with identical occupancy and overlap counts. Joined translucent
layouts and exact endpoints are checked independently.

## Native output feedback

The experimental compositor retains a bounded history of native output feedback.
Measure six owned swaps separately from encoder delivery:

```sh
python3 scripts/build-niri-movement.py --release --test
python3 scripts/measure-native-movement.py --output /tmp/nirifx-output.json
# On a deliberately installed experimental session, read recent feedback only:
python3 scripts/measure-native-movement.py --running \
  --movement-binary /path/to/patched/niri --output /tmp/nirifx-presentation.json
```

The first command path opens an isolated compositor. It groups frames by output
and excludes gaps between separate swap workloads. Screencopy keeps the nested
backend advancing, so its measurement load is included; timestamps come from
compositor feedback, not encoded frame timestamps. Keep the host unlocked and
the owned window visible. Stalled IPC invalidates the run.

`--running` is read-only and creates no workload. Run it after your chosen
workload; the recent 512-frame history includes idle gaps. Output names are
omitted from reports. It requires a matching executable and verified runtime
contract. Neither path measures input latency or GPU shader duration.

Winit timestamps are estimated **submissions**, not physical scanout. DRM
presentation timestamps qualify as hardware evidence only when every sample
has VSYNC, HW_CLOCK and HW_COMPLETION flags. Other feedback remains estimated.
A report without enough samples fails rather than inferring a rate.

An unlocked nested run on 2026-10-03 produced these p95 submission intervals:

| Preset | Native intervals | p95 (ms) | Hardware presentation |
| --- | ---: | ---: | --- |
| balanced | 1031 | 8.71 | No |
| mixed-confetti | 1026 | 9.23 | No |

[Raw feedback interval samples and patch identity](benchmarks/native-output-feedback.json).
The host, screencopy and nested scheduling affect these intervals. They are not a
physical refresh-rate claim, a dropped-frame count or a comparison of GPU costs.
Physical DRM, mixed-output and integrated-GPU acceptance remain open.

## Mixed fragment shapes

Measured on 2026-10-03 with an RTX 4070 Ti through Chromium ANGLE/OpenGL,
60 samples after warmup. Values are p95 milliseconds per synthetic window shader
pass, including a framebuffer clear. They exclude compositor scheduling, input
latency and scanout.

| Preset | 1920×1080 | 3840×2160 |
| --- | ---: | ---: |
| Mixed Confetti | 1.340 ms | 4.483 ms |
| Orbiting Shapes | 0.309 ms | 1.031 ms |

[Raw samples, parameters and renderer](benchmarks/mixed-fragments.json). The
triangle mixture uses more piece work than the circle/hexagon example. These
styles also differ in physics; this is a preset-cost sample, not an isolated
comparison of shape kinds. Results on integrated GPUs remain open.

```sh
node scripts/benchmark-gpu.mjs --output=/tmp/nirifx-mixed.json \
  --presets=mixed-confetti,orbiting-shapes --sizes=1920x1080,3840x2160 --samples=60
```

## Coordinated resize companions

Measured on 2026-10-03 local time with the same RTX 4070 Ti / Chromium ANGLE
setup, 60 samples per case. Values are p95 shader milliseconds for one draw;
window dimensions and raw samples are in the [report](benchmarks/action-set-resize.json).

| Explicit resize profile | 1920×1080 | 3840×2160 |
| --- | ---: | ---: |
| Fragments Motion | 0.269 | 1.008 |
| Ribbons Motion | 0.097 | 0.366 |
| Elastic Motion | 0.098 | 0.366 |

```sh
node scripts/benchmark-gpu.mjs --output=/tmp/nirifx-action-set-resize.json \
  --resize-profiles=fragments-motion-resize,ribbons-motion-resize,elastic-motion-resize \
  --sizes=1920x1080,3840x2160 --samples=60
```

These are synthetic growth-path shader costs, including framebuffer clearing.
They exclude compositor load, input latency, capture and physical presentation.
No integrated-GPU or concurrent-window result is implied. Choose the
[resize companions](action-sets.md#add-matching-resize) explicitly; none is a
built-in resize default.

## Pointer prototype diagnostics

The optional pointer build was checked with a 500 × 500 synthetic floating
window inside a 1280 × 800 nested Winit output. Each preset follows the same
1.05-second pointer path with reversals, a final flick and release, while
screencopy and recording are active. Native timestamps cover this first drag and
settling; the showcase then returns to its starting position with a real drag.
The optimized build reports submission timestamps separately from input
acknowledgements across all ten lifecycle checks.

The accepted runs reported an NVIDIA GeForce RTX 4070 Ti renderer. The nested
output advertised 60 Hz; its submission intervals are not a measurement of the
host display's refresh rate. Host callbacks, capture and scheduling affect these
diagnostics, so differences from earlier recordings do not establish a renderer
optimization or regression.

| Preset | Native samples | Submission interval p95 | Server round-trip p95 |
| --- | ---: | ---: | ---: |
| Gentle | 90 | 18.41 ms | 31.78 ms |
| Rubber Sheet | 94 | 18.04 ms | 27.44 ms |
| Release Settle | 88 | 17.93 ms | 30.51 ms |

Submission intervals include idle holds while the window settles; maximum gaps
were about 83–309 ms. They are not per-frame GPU cost. Motion commands flush
asynchronously; their local socket acknowledgements are separate from the server
round trips for buttons and synchronization barriers. Those round trips include
protocol and scheduling overhead. None of these measures is physical
input-to-photon latency or a hardware presentation guarantee. The GIFs are encoded
at 50 fps independently of these timestamps.

[Recorded settings, checks and diagnostic scope](benchmarks/pointer-wobble.json) ·
[Reproduce the native pointer run](pointer-wobble.md#reproduce-validation-and-showcases)

## Continuous fragment state

The experimental continuous fragment renderer keeps individual spring states.
Its release-mode CPU benchmark uses default native controls and **actual** cell
counts, rather than the requested particle count before grid rounding. Input
timestamps are simulated; wall-clock measurements cover state updates and sample
allocation, without GPU drawing or physical presentation.

A long idle previously replayed the recent two-second simulation interval even
when the analytical catch-up had already brought every piece to exact rest. That
replay is now skipped only when positions, spread, pinning, rotation and tilt are
at their targets, velocities are zero, and no delayed target remains. Tiny angular
residue and pending motion still take the original path.

On an AMD Ryzen 9 7950X, the paired release-mode rerun measured:

| Actual cells | Ordinary 60 Hz update before / after (ms) | Recovery after 24-hour idle before / after (ms) |
| ---: | ---: | ---: |
| 600 | 0.176 / 0.182 | 15.47 / 0.061 |
| 800 | 0.237 / 0.244 | 20.37 / 0.081 |
| 1200 | 0.359 / 0.369 | 30.99 / 0.120 |
| 4096 | 1.245 / 1.291 | 108.52 / 0.425 |

Values are medians. The idle cases start from one 100 × 20 logical-pixel target
step; they do not measure recovery with a full delayed-input history. Ordinary
60 Hz updates were about 3% slower in this paired run;
this change claims a long-idle recovery improvement, not faster ordinary frames.
The shared host had no CPU-affinity or frequency isolation. The simulated idle
does not test physical suspend/resume. GPU cost, allocation
outside the sampled state and multi-window presentation remain separate work.
The [complete samples and measurement scope](benchmarks/fragment-motion-cpu.json)
include both run pairs, 120 Hz input and sample-allocation costs.

After building the fragment experiment, use a working Rust toolchain and the
same native build dependencies to reproduce the current CPU benchmark. Set
Cargo's output directories to reuse this candidate's compilation cache:

```sh
cd /path/to/candidate/source
export CARGO_TARGET_DIR=../target CARGO_BUILD_BUILD_DIR=../target
NIRIFX_FRAGMENT_BENCHMARK=/tmp/nirifx-fragment-cpu.json \
    cargo test --release --locked --lib fragment_motion_benchmark -- --ignored --nocapture
```

The benchmark refuses a debug build. Native differential tests compare the old
and new integrators across release and held states, timing cutoffs, and extreme
controls. The recorded default motion fixture remains byte-identical.

### Recovery after dense input

The single-step result above does not cover a queue of delayed movement. A
separate release-mode benchmark feeds 255 inputs at 250 Hz, reversing direction
every 32-event block.
Coalescing and retention leave 154 reachable history entries. A second, synthetic
capacity case restores all 256 entries, including the initial rest event; it is
reported separately rather than presented as normal input.

On the same Ryzen 9 7950X, the independent repeat measured these median CPU
recovery costs with default native controls and reachable input history:

| Actual cells | 2.001-second gap (ms) | 4-second gap (ms) | 24-hour gap (ms) |
| ---: | ---: | ---: | ---: |
| 600 | 19.859 | 19.061 | 0.305 |
| 800 | 26.494 | 25.385 | 0.419 |
| 1200 | 40.373 | 38.462 | 0.640 |
| 4096 | 140.376 | 132.261 | 2.180 |

Each combination has seven samples in each of two runs. The extreme-control
case at 4096 cells took about 144 ms after a four-second gap. These are observed
state-update costs on a shared host, not measured dropped frames or physical
suspend/resume results. Shorter gaps still require the bounded recent replay,
so the long-idle shortcut did not remove every recovery spike. The following
comparison measures a subsequent recovery optimization. Preset defaults and
the particle limit are unchanged.

The [complete dense-history report](benchmarks/fragment-motion-dense-cpu.json)
includes both runs, reachable and synthetic histories, default and extreme
controls, raw samples and source fingerprints. To reproduce after building the
fragment experiment:

```sh
cd /path/to/candidate/source
export CARGO_TARGET_DIR=../target CARGO_BUILD_BUILD_DIR=../target
NIRIFX_FRAGMENT_DENSE_BENCHMARK=/tmp/nirifx-fragment-dense-cpu.json \
    cargo test --release --locked --lib fragment_motion_dense_benchmark -- --ignored --nocapture
```

### Cached recovery steps

The development renderer reuses spring coefficients during recovery and walks
each piece's delayed targets in order. It keeps the same 4 ms integration steps,
queued reversals, rotation and release behavior. Ordinary frames of 32 ms or less
retain their existing path.

Paired release builds measured on 2026-10-07 on the same Ryzen 9 7950X show these
median **CPU state-update** costs in the second independent pair. Both builds use
the same compiler and benchmark inputs; run order is reversed for the repeat.

| Actual cells | 2.001 s gap, before → after (ms) | 4 s gap, before → after (ms) |
| ---: | ---: | ---: |
| 600 | 21.982 → 12.583 | 19.605 → 10.175 |
| 800 | 29.593 → 16.774 | 26.238 → 13.636 |
| 1200 | 43.718 → 25.682 | 38.855 → 20.594 |
| 4096 | 152.023 → 86.210 | 134.075 → 69.391 |

Recovery costs fell roughly 41–48% across these cases. Ordinary 60/120 Hz state
updates stayed within about 2% across both pairs. Exact differential tests retain
particle positions and velocities at the short-frame and two-second boundaries,
with default/extreme controls, three rotation modes, reversal, release and regrab.
The native trajectory and mesh traces also remain byte-identical.

The [paired report](benchmarks/fragment-motion-recovery-cpu.json) includes raw
samples, compiler/container identity, source fingerprints and synthetic
history-capacity cases. These measurements exclude GPU drawing, upload,
presentation and physical suspend/resume. Dense recovery remains expensive at
the largest grids; this does not establish a stutter-free desktop or justify
raising the particle limit.

### Continuous mesh GPU probe

The hardware probe uses actual Rust-emitted meshes at 600, 800, 1200 and 4096
source cells, the native vertex shader and mesh epilogue, and the generated
fragment material. It draws one, two or four overlapping synthetic windows in
1080p and 4K framebuffers. Layout scales with framebuffer size. Every window
must contribute visible pixels; rest and settled poses must match the original
source quad, and zero opacity must produce transparent output.

The probe measures a fixed batch of 32 compositions per GPU query. Each
composition clears once and draws all selected windows. Raw query nanoseconds
are retained, then divided by 32 to estimate the cost of one composition. Reported
percentiles describe these batch averages, not individual frames. Fixed batching
improves resolution for short draws; zero or disjoint results still fail the run.
Software renderers and missing hardware timers are rejected.

Buffers and textures are uploaded before measurement, and pixel checks finish
before warmup. The timed work excludes particle simulation, uploads, compilation,
readbacks, compositor work and presentation. It repeats one moving pose with warm
caches. Texture dimensions and aspect ratios also vary with density, so the
matrix does not isolate per-cell cost or establish desktop frame rates.

The RTX 4070 Ti / Chromium ANGLE OpenGL run passed all 24 combinations twice,
with 2880 valid queries and no discarded measurement samples. The table shows
the larger P95 **batch-average milliseconds per composition** from the two runs
for four overlapping windows:

| Cells per window | 1920×1080 | 3840×2160 |
| ---: | ---: | ---: |
| 600 | 0.0152 | 0.0454 |
| 800 | 0.0178 | 0.0558 |
| 1200 | 0.0210 | 0.0606 |
| 4096 | 0.0320 | 0.0609 |

The [full GPU report](benchmarks/fragment-motion-gpu.json) includes one- and
two-window cases, both repeats, raw query times, per-window pixel contributions,
coverage, geometry and source fingerprints. Pixel coverage ranges from 15.8% to
54.9% of the framebuffer. Earlier single-composition attempts returned zero
timer values and were rejected; they are not part of these results. This evidence
does not remove the CPU recovery work above or establish performance on another
GPU. Native buffer preparation, uploads and presentation still need separate
measurement before raising particle limits.

After building the experiment, emit the fixture with the same native toolchain,
then run the hardware probe from the repository root:

```sh
(
    cd /path/to/candidate/source
    export CARGO_TARGET_DIR=../target CARGO_BUILD_BUILD_DIR=../target
    NIRIFX_FRAGMENT_MESH_BENCH_FIXTURE=/tmp/nirifx-fragment-meshes.json \
        cargo test --release --locked --lib fragment_mesh_emit_benchmark_fixture -- --ignored --nocapture
)
node scripts/benchmark-fragment-gpu.mjs \
    --fixture /tmp/nirifx-fragment-meshes.json \
    --native-source /path/to/candidate/source \
    --output /tmp/nirifx-fragment-gpu.json
```

Use a fresh output filename. Defaults collect 60 query samples per case after
12 warmup queries and repeat the matrix in two independent Chromium profiles.
`--check` validates fixture and source inputs without launching a browser;
`--software` exercises rejection and must not produce a hardware measurement.
