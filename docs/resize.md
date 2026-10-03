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
| Edge Ripple | Waves travel inward from the right/bottom edges; changed axes and growth/shrink determine displacement | [Subtle](../examples/profiles/edge-ripple-subtle.json), [Expressive](../examples/profiles/edge-ripple-expressive.json) | [Comparison](gifs/compare-edge-ripple-resize.gif) |
| Torsion Resize | A twist in the interior, with a steady border; shrink reverses the twist | [Subtle](../examples/profiles/torsion-subtle.json), [Expressive](../examples/profiles/torsion-expressive.json) | [Comparison](gifs/compare-torsion-resize.gif) |
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

## Edge Ripple and Torsion Resize

These modes require current `main` after 0.10.0. Start with **Subtle** for everyday
use or **Expressive** for a stronger deformation. All four profiles keep Balanced
opening and closing, and explicitly assign a resize effect at 650 ms. Import the
JSON in Studio, select the Resize action, and use **Grow** or **Shrink** to preview.

![Subtle and expressive edge ripples](gifs/compare-edge-ripple-resize.gif)
![Subtle and expressive torsion](gifs/compare-torsion-resize.gif)

| Control | Applies to | Meaning |
| --- | --- | --- |
| `--distortion-resize-mode ripple` | Radial Ripple | Existing radial resize effect, still the default |
| `--distortion-resize-mode edge-ripple` | Edge Ripple | Wave displacement follows the signed width/height change |
| `--distortion-resize-mode torsion` | Torsion Resize | Twist follows the dominant changing dimension |
| `--resize-strength` | All resize modes | Overall strength, 0 to 1; zero retains the normal texture crossfade |
| `--resize-twist` | Torsion Resize | Signed twist, -45 to 45 degrees before size-change scaling; zero removes the twist |
| `--distortion-strength`, `--distortion-wavelength` | Edge Ripple | Displacement in pixels and spacing between waves |
| `--distortion-cycles`, `--distortion-falloff` | Edge Ripple | Wave travel and attenuation toward the opposite edge |

Niri supplies old and new dimensions, but this shader interface does not identify
the physical edge being dragged. Edge Ripple uses the right edge for width changes
and the bottom edge for height changes. Torsion uses logical pixels to keep wide
and tall windows balanced. Both modes smoothly limit displacement within the
current rectangle, preserving transparent source pixels and exact endpoints.

Selecting a mode or adjusting its controls does **not** enable resize. A single
style still needs `--resize`; a profile needs an explicit resize slot. These modes
do not add pointer physics or carry shader velocity across interrupted resizes.
Niri owns interruption handling; the tests check settling and cleanup rather than
claiming uninterrupted velocity.
