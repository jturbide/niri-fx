# README animation recordings

The recordings use synthetic window contents. No personal desktop or application
content is captured.

- `opening.gif`, `closing.gif`, `resize.gif`: Studio's actual GLSL shader renderer.
  Resize is shown as an opt-in feature; recording it does not change a preset.
- `preset-*.gif`: each built-in style closes and opens at its configured timing.
- `move-concept.gif`, `swap-concept.gif`: Studio's labelled Canvas design previews.
  These are not recordings of compositor movement or promises of its appearance.
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
