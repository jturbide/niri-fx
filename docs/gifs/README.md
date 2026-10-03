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
750 ms closing/opening durations and the same seed; the custom examples use
their saved durations. The renderer verifies Python/browser shader parity and
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

The gallery has 75 GIFs, including all 41 presets. The latest addition contains
12 preset loops, five comparisons and three native swaps. Shape comparisons
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
