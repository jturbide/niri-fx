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
```

Set `CHROME_BIN` if needed. The script uses an isolated temporary browser profile,
synthetic textures and no desktop capture. It records renderer/vendor, dimensions,
parameters, seed, browser version, raw GPU samples, p50/p95/p99 and counts above
60/120/144 Hz frame budgets. The window occupies 60% of output width and 50% of
height. It warms up with 12 draws, then samples intermediate animation positions.
These budget counts are shader costs, not measured missed presentation deadlines.

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

The next performance acceptance step is a release-built nested compositor with
presentation timing, mixed output scales and interrupted animations. The existing
debug movement build and GIF recordings cannot establish those results.
