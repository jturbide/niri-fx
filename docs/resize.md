# Resize effects

Resize is off in every built-in preset. You can enable it explicitly for
Fragments, Elastic, Slices or Distortion, or assign a separate resize effect in
a [profile](profiles.md).

Niri animates selected size changes, including cycling preset column widths and
maximizing a column. This does not turn continuous pointer resizing into a spring
simulation. Very small changes may not animate; see [Niri's resize interface](https://niri-wm.github.io/niri/Configuration:-Animations.html#window-resize).

| Style | Behavior | Importable profile | Preview |
| --- | --- | --- | --- |
| Elastic Stretch | A damped stretch in the changing dimensions; edges stay sealed | [JSON](../examples/profiles/elastic-resize.json) | [GIF](gifs/elastic-resize.gif) |
| Accordion Resize | Alternating folds across the changing geometry | [JSON](../examples/profiles/accordion-resize.json) | [GIF](gifs/accordion-resize.gif) |
| Ripple Resize | Radial texture ripples with adjustable origin, wavelength and strength | [JSON](../examples/profiles/ripple-resize.json) | [GIF](gifs/ripple-resize.gif) |
| Fragment breakup | Full, Edge Rebuild or Soft Reflow | [Examples](../examples/README.md) | [Comparison](gifs/resize-full.gif) |

The profiles above use Balanced for opening and closing. Previewing or importing
one does not change your desktop; applying it enables its resize slot.

```sh
python3 -m niri_fx preview --custom examples/profiles/elastic-resize.json --output /tmp/elastic-resize.html
python3 -m niri_fx render --custom examples/profiles/elastic-resize.json > /tmp/nirifx-resize.kdl
niri validate -c /tmp/nirifx-resize.kdl
```

Use [standalone setup](standalone.md) or your shell's documented installation path
when ready to apply. For a single style, `--resize --resize-strength 0.5` explicitly
adds resize; omitting the flag preserves your existing resize configuration.

All families share resize time and strength. Elastic uses spring strength,
frequency, damping, axis and origin. Slices uses strip count, angle and stagger.
Distortion uses displacement, wavelength, travel cycles, falloff and origin.
Open/close-only controls such as ink color or glitch bands do not affect resize.
