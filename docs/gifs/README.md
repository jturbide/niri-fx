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

Shader-gallery loops are sampled at 20 fps, with holds at endpoints. GIF palette reduction
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

The gallery contains **135 GIFs**, including all **64 presets**. The earlier eight
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
for every built-in. The introductory clips and original movement concepts retain
their older, smaller metadata records; native swaps use their own checked manifest.

## Workflow and compositor recordings

These twelve clips use real controls/clients, with metadata separate from the
shader-comparison manifest in [scenario-manifest.json](scenario-manifest.json).
Run them sequentially; each preserves other entries in that shared file.

For the Studio UI, install the browser tooling from [Contributing](../../CONTRIBUTING.md),
plus `ffmpeg` and stock Niri for exported KDL validation:

```sh
node scripts/record-studio-workflow.mjs
```

The following tools run **inside an existing Niri desktop** and create their own
nested compositor. They require stock `niri`, `qs`, `grim`, `wf-recorder`, `wtype`,
`ffmpeg`, `dbus-run-session`, and Python with Pillow. Test mode leaves the gallery
alone; `--record` writes verified GIFs. Each run retains temporary settings, logs,
PNGs and checks in `artifacts/scenario-*` and closes its owned clients/compositor.
The fixture has transparent margins and a gutter between two colored shapes.

```sh
python3 scripts/test-stock-scenarios.py
python3 scripts/test-stock-scenarios.py --record
```

Stock clips use five fixed scenarios at 1400 ms opening/closing: transparent
Explosion and Ghost Wisps, 900×280 Shockwave, 300×660 Pixel Wipe, and 600×400 Frost
at 1.5× output scale. This slower recording timing does not change preset defaults.
The test checks partial frames, intact content and an empty close endpoint, plus
compositor error logs. One scaled output does not test mixed monitors.

To record pickers, supply your **actual release source/binary paths**. The examples
below use placeholder paths; `--version` labels the tested release, while metadata
also fingerprints the source components or binary. Sources are read/symlinked into
a temporary test host; the installed shell and registry are not modified.

```sh
python3 scripts/test-shell-workflows.py dms --source /path/to/DankMaterialShell \
  --version 'DMS 1.6.2 / Quickshell 0.3.1' --record
python3 scripts/test-shell-workflows.py noctalia --binary /path/to/noctalia \
  --assets /path/to/noctalia/assets --plugin /path/to/niri-animations \
  --version 'Noctalia 5.2.1 / Niri Animations 0.2.0' --record
python3 scripts/test-shell-workflows.py iris --source /path/to/inir \
  --pointer-protocol /path/to/wlr-virtual-pointer-unstable-v1.xml \
  --version 'iNiR/iRiS c08bb92 / Quickshell 0.3.1' --record
```

DMS requires Chromium for its actual Studio launch. iRiS additionally needs a C
compiler, `pkg-config`, Wayland client headers, `wayland-scanner` and the wlr virtual
pointer protocol XML. The small input fixture builds bindings under `artifacts`
and connects only to the owned nested socket. DMS/iRiS use their real launcher/
gallery and services inside minimal hosts; Noctalia runs the full shell. These
are workflow checks, not a claim of full DMS/iRiS desktop-session coverage.
The Noctalia preset folder uses a generic temporary path. The publication crop
excludes the surrounding bar, which may read system services even with a private
session bus. Do not publish uncropped raw recordings.

For actual movement interruption, first follow the
[pinned build instructions](../../experimental/README.md), then run:

```sh
python3 scripts/record-movement-scenarios.py
```

The script verifies the binary and patch hashes, records repeated movement and
close-during-movement with two synthetic app cards, and checks final IDs/positions
and reconstructed color populations. It writes `native-interrupted.gif`,
`native-rapid-reversals.gif`, `native-close-during-move.gif` and
`native-close-during-open.gif` at 50 fps using mint/violet cards and a compact
32-color palette at 720 px wide. Use `python3 scripts/build-niri-movement.py
--release` for an optimized build; these recordings use that profile.

The harness raises its owned nested window so host occlusion cannot stall frame
callbacks and IPC. Each interruption must be acknowledged within 600 ms of the
previous action in the 1200 ms movement; an IPC call taking 150 ms or longer
rejects the capture. Action offsets are saved in the manifest. Pixel checks run
after recording stops to avoid adding machine-dependent idle holds. These are
capture timing checks, not a GPU benchmark. The script does not replace the login
compositor or prove seamless retargeting. [Acceptance scope](../validation.md#workflow-and-compositor-scenarios).


## Expanded styles, resize and native continuity

```sh
node scripts/render-readme-gifs.mjs --only=preset-hexagon-burst,preset-hive-collapse,preset-signal-glitch,preset-chromatic-glitch,preset-ink-spread,preset-ink-bloom
node scripts/render-readme-gifs.mjs --only=preset-slice-exchange,preset-pixel-transfer,preset-soft-phase
node scripts/render-readme-gifs.mjs --only=elastic-resize,accordion-resize,ripple-resize,compare-resize-families
python3 scripts/build-niri-movement.py --release --test
python3 scripts/record-native-gif.py --all
python3 scripts/record-movement-scenarios.py
python3 scripts/build-gallery.py
python3 scripts/check-docs.py
```

Native clips use the mint/violet app-card fixture at 50 fps. Their manifests record
preset values, fixture and patch hashes, release profile and acceptance checks.
The four interruption scenarios cover retargeted swaps, eight rapid wobble reversals,
closing during movement and closing during opening. Stock Niri cannot reproduce the state handoff.

The [hosted gallery](https://jturbide.github.io/niri-fx/gallery/) uses generated WebP
posters. It loads a GIF only after Play, pauses the previous GIF and stops playback
when filtering, pressing Escape or hiding the tab. It also works by opening
`docs/gallery/index.html` locally. Run `build-gallery.py --check` to verify the
catalog, downloadable documents and poster hashes without Pillow. Stage the
complete site, including hosted Studio, with `python3 scripts/build-site.py
--output /tmp/nirifx-site` (choose a new directory).

Additional checks without new recordings:

```sh
python3 scripts/test-interruptions.py
python3 scripts/test-interruptions.py --experimental
```

These use transparent clients at sequential 1×, 1.5× and 2× scales for rapid
open/close, close during resize and fullscreen transitions. The experimental
run also checks eight rapid swaps and movement-shader removal. They verify
state, cleanup and logs; they do not measure physical presentation or certify
mixed-monitor behavior.
