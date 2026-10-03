# README animation recordings

The recordings use synthetic window contents. No personal desktop or application
content is captured.

- `opening.gif`, `closing.gif`, `resize.gif`: Studio's actual GLSL shader renderer.
  Resize is shown as an opt-in feature; recording it does not change a preset.
- `preset-*.gif`: each built-in style closes and opens at its configured timing.
  Each family uses its own real shader.
- `compare-slice-count.gif`: four, twelve and thirty-two strips, with the same
  seed, texture and other settings.
- `compare-*.gif`: synchronized three-panel comparisons of density, gravity
  direction, gravity strength, rotation and burst origin. Single-control comparisons keep other settings fixed. New variation and
  Elastic comparisons explicitly compare combinations/styles at matched timing.
- `recipe-*.gif`: custom Meteor Shower, Orbit Burst and Reverse Gravity settings
  from the importable JSON in [examples](../../examples/README.md).
- `resize-full.gif`, `resize-edge.gif`, `resize-soft.gif`: opt-in resize styles
  using the corresponding example JSON files.
- `move-concept.gif`, `swap-concept.gif`: Studio's labelled Canvas design previews.
  These are not recordings of compositor movement or promises of its appearance.
- `compare-swap-styles.gif`: three labelled Canvas swap concepts.
- `native-swap-crosswind.gif`, `native-swap-orbital-ribbons.gif`,
  `native-swap-spring-wobble.gif`: actual native swaps for the new styles.
  Parameters, byte sizes and backend are recorded in `native-manifest.json`.
- `native-swap.gif`: actual recording of two synthetic Alacritty windows inside
  the separately built, patched Niri compositor. This remains experimental.

All loops are sampled at 20 fps, with holds at endpoints. GIF palette reduction
and scaling affect fine edges. These clips demonstrate appearance, not GPU frame
time. The move/swap concepts use a 1.1-second journey; the native recording uses
a 1.2-second movement duration.

## Reproduce

From the checkout, with Python 3.10+, Node 22+, Chromium and FFmpeg:

```sh
node scripts/render-readme-gifs.mjs
```

The script creates an offline Studio document and an isolated headless browser
profile. It samples the real controls at known progress values and encodes PNG
frames with FFmpeg. Sources remain under ignored `artifacts/`; the browser
profile is removed. `manifest.json` records the Studio clips' frame counts,
modes and file sizes.

To render only the comparison, custom recipe and resize showcase clips:

```sh
node scripts/render-readme-gifs.mjs --showcase-only
```

[showcases.json](showcases.json) defines those clips. Comparison panels use
matched closing/opening durations (750 or 1100 ms) and the same seed; custom
examples and profiles use their saved action durations. The renderer verifies Python/browser shader parity and
records resolved parameters in `manifest.json`. This allows the documentation
check to catch a changed recipe whose recording has not been regenerated.
The partial render preserves manifest entries for the other existing clips.

To regenerate the slice presets and their count comparison:

```sh
node scripts/render-readme-gifs.mjs --slices-only
```

The recordings remain valid when only serialization, packaging or application
branding changes. The docs check compares recorded effect values with current
presets and examples; regenerate clips when those values or rendered behavior change.

To record the native experiment, also prepare the patched compositor, Alacritty
and `wf-recorder`, then run inside the existing Niri desktop:

```sh
python3 scripts/record-native-gif.py
```

That script opens a nested demo and makes only its own newly created window
floating at 1280×800. It verifies the nested sockets and synthetic clients,
records that compositor's `winit` output, then closes its own demo. No audio or
parent desktop output is recorded. The source video and logs remain under
`artifacts/native-gif-*`.

To reproduce the new post-0.6 presets/comparisons and native recordings:

```sh
node scripts/render-readme-gifs.mjs --new-only
python3 scripts/record-native-gif.py --preset crosswind --name native-swap-crosswind
python3 scripts/record-native-gif.py --preset orbital-ribbons --name native-swap-orbital-ribbons
python3 scripts/record-native-gif.py --preset spring-wobble --name native-swap-spring-wobble
```

`--new-only` also regenerates Slide Apart and its count comparison after the
default direction change. The original native swap remains a historical recording;
new native demos display NiriFX and the preset name.

## Piece shapes, hinges and spring transforms

The shape/hinge/spring expansion added 12 preset loops, five comparisons and
three native swaps. Shape comparisons
change corner rounding or shrink from the same baseline; hinge and collapse
comparisons change one scalar; release comparisons change the spatial sequence;
elastic comparisons add either twist or spatial ripples.

Regenerate one or more exact clip names without touching the rest of the gallery:

```sh
node scripts/render-readme-gifs.mjs --only=preset-bubble-burst,compare-fragment-shapes
node scripts/render-readme-gifs.mjs --only=compare-slice-hinges,compare-slice-collapse,compare-elastic-transforms
python3 scripts/record-native-gif.py --preset bubble-burst --name native-swap-bubble-burst
python3 scripts/record-native-gif.py --preset core-detonation --name native-swap-core-detonation
python3 scripts/record-native-gif.py --preset twist-snap --name native-swap-twist-snap
```

`--only` accepts preset clip names (`preset-NAME`) and names from `showcases.json`.
Unknown/empty names fail before any frames are recorded. Use one selection option
at a time. Recordings use exact current parameters with resize off except the
explicit resize examples.

The 0.7.0 reveals added six preset loops, two controlled comparisons and
`profile-spring-and-ember.gif`: its source profile records separate opening and
closing effects. Metadata includes both parameter sets.

## Pixels, wisps, distortion and configurable erosion

The current gallery has **106 GIFs**, including all **55 presets**. Eight new
preset loops and three comparisons show pixel modes, curling wisps, distortion
patterns and black/white/warm Ember palettes. Dissolve preset loops, its noise-scale
comparison and the Spring/Ember profile were regenerated for the revised shaders.

```sh
node scripts/render-readme-gifs.mjs --only=preset-pixel-wipe,preset-pixelate,preset-dust-drift
node scripts/render-readme-gifs.mjs --only=preset-ghost-wisps,preset-ink-current
node scripts/render-readme-gifs.mjs --only=preset-shockwave,preset-ripple-collapse,preset-wave-fold
node scripts/render-readme-gifs.mjs --only=compare-ember-palette,compare-pixel-modes,compare-distortion-patterns
```

These are original implementations inspired by broad visual ideas, not captures
or ports of Burn My Windows. Upstream reference media is not bundled.

## Tuning scenarios and mixed profiles

Eight additional comparisons cover pixel release direction, dust size and wind,
wisp curl and palettes, ripple displacement, shockwave origin and erosion flow.
Three additional profiles show Explosion/Dust Drift, Frost Vanish/Pixel Dust and
Ghost Wisps/Shockwave. The [visual scenario index](../showcases.md) maps the full
gallery to practical choices, with recordings and importable profile JSON.

```sh
node scripts/render-readme-gifs.mjs --only=compare-pixel-directions,compare-dust-size,compare-dust-wind
node scripts/render-readme-gifs.mjs --only=compare-wisp-curl,compare-wisp-palette
node scripts/render-readme-gifs.mjs --only=compare-distortion-strength,compare-shockwave-origin,compare-dissolve-flow
node scripts/render-readme-gifs.mjs --only=profile-burst-and-drift,profile-frost-and-fragments,profile-ghost-and-shockwave
```

All new comparisons use 1100 ms for each action. They change the labelled control
or palette while keeping other settings fixed. Dust travel stays in cell units;
increasing cell size also increases pixel travel. Profile loops close, then open,
with separate shader parameters recorded for both actions. Resize remains off.
The documentation check enforces a recording for each preset and profile example,
and a documentation link for each GIF, as well as parameter and file-size agreement.
Fourteen early preset loops were also refreshed to complete parameter metadata
for all 55 built-ins. The introductory clips and original movement concepts retain
their older, smaller metadata records; the original native swap is documented separately.
