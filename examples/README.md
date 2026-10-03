# Custom showcase examples

For independent opening/closing combinations, see the [action profiles](profiles/README.md).
For a visual starting point, use the [scenario index](../docs/showcases.md).

The checked-in JSON supplies the exact settings used in the README recordings.
Use **Import preset** in Studio to inspect any file without applying it. The
three recipes and three built-in examples leave resize off; the three
resize examples explicitly enable it.

| Example | Starting preset | Main changes |
| --- | --- | --- |
| [Meteor Shower](meteor-shower.json) | Earth | 1,800 pieces, heavier downward gravity and tumbling |
| [Orbit Burst](orbit-burst.json) | Explosion | 1,500 pieces, an outward sweep and 180° orbit |
| [Reverse Gravity](reverse-gravity.json) | Updraft | 1,000 pieces, stronger lift and randomized spin |

| Example | Behavior | Resize |
| --- | --- | --- |
| [Directional Wave](directional-wave.json) | Three sections release from left to right | Off |
| [Corner Burst](corner-burst.json) | Burst from a lower-left origin | Off |
| [Orbital Collapse](orbital-collapse.json) | Strong center pull and 300° orbit | Off |
| [Full Breakup](resize-full.json) | Whole-window resize fragmentation | **On** |
| [Edge Rebuild](resize-edge.json) | Fragment changing edges, preserve the center | **On** |
| [Soft Reflow](resize-soft.json) | Lighter breakup over a readable window | **On** |

## Slices (NiriFX 0.6+)

| Example | Controls | Supported events |
| --- | --- | --- |
| [Slide Apart](slide-apart.json) | 12 horizontal strips, split outward | Open / close |
| [Alternating Blinds](alternating-blinds.json) | 16 vertical strips, alternating travel and rotation | Open / close |
| [Diagonal Shear](diagonal-shear.json) | 10 strips at −35°, alternating travel | Open / close |

All single-style examples use schema 3. Slices supports stock open/close,
opt-in Accordion Resize and experimental movement. Import into Studio to preview,
then save/apply when ready.

```sh
python3 -m niri_fx preview --custom examples/slide-apart.json --output /tmp/slide-apart.html
python3 -m niri_fx preview --custom examples/alternating-blinds.json --output /tmp/alternating-blinds.html
python3 -m niri_fx preview --custom examples/diagonal-shear.json --output /tmp/diagonal-shear.html
```

## Import into iNiR / iRiS

From the checkout, register any examples you want:

```sh
python3 -m niri_fx register --custom examples/meteor-shower.json
python3 -m niri_fx register --custom examples/orbit-burst.json
python3 -m niri_fx register --custom examples/reverse-gravity.json
```

Then select the named style in **iRiS Settings → Windows → Movement → Style**.
Registration saves the entry without activating it. Each style snapshots the
recognized base preset's other animation settings; use an explicit `--base` if
the active settings are unrecognized. See [installation and rollback](../docs/getting-started.md).

## Preview without changing desktop settings

These commands reproduce the JSON parameters using the existing preset controls.
Run them from the checkout and open the output with your browser. Use a new output
filename if that file already exists; `preview` does not overwrite it.

### Meteor Shower

```sh
python3 -m niri_fx preview --preset earth \
  --particles 1800 --gravity-strength 1.7 --scatter 100 \
  --rotation random --spin 540 --dispersion 1 --stagger 0.28 \
  --open-ms 760 --close-ms 820 --no-resize --output /tmp/meteor-shower.html
xdg-open /tmp/meteor-shower.html
```

### Orbit Burst

```sh
python3 -m niri_fx preview --preset explosion \
  --particles 1500 --gravity-strength 0.85 --scatter 150 \
  --rotation random --spin 240 --swirl 180 --dispersion 0.8 --stagger 0.16 \
  --open-ms 900 --close-ms 900 --no-resize --output /tmp/orbit-burst.html
xdg-open /tmp/orbit-burst.html
```

### Reverse Gravity

```sh
python3 -m niri_fx preview --preset updraft \
  --particles 1000 --gravity-strength 1.55 --scatter 85 \
  --rotation random --spin 360 --swirl -70 --dispersion 0.9 --stagger 0.22 \
  --open-ms 750 --close-ms 800 --no-resize --output /tmp/reverse-gravity.html
xdg-open /tmp/reverse-gravity.html
```

For standalone Niri, DMS or another Niri shell, choose **Export Niri config** in
the preview and follow the [standalone guide](../docs/getting-started.md#standalone-niri).
You can also replace `preview` with `render`, remove `--output`, and redirect
stdout to a KDL file. Validate the generated file before including it.

## Preset and resize previews

The same JSON works with `preview`, `studio`, `render`, `register` and `setup`.
These commands only create offline editors. Importing a resize example does not
change the desktop until you apply its generated configuration or select it in iRiS.

```sh
python3 -m niri_fx preview --custom examples/directional-wave.json --output /tmp/directional-wave.html
python3 -m niri_fx preview --custom examples/corner-burst.json --output /tmp/corner-burst.html
python3 -m niri_fx preview --custom examples/orbital-collapse.json --output /tmp/orbital-collapse.html
python3 -m niri_fx preview --custom examples/resize-full.json --output /tmp/resize-full.html
python3 -m niri_fx preview --custom examples/resize-edge.json --output /tmp/resize-edge.html
python3 -m niri_fx preview --custom examples/resize-soft.json --output /tmp/resize-soft.html
```

## Reproducing the gallery

The six synchronized comparisons, three custom recipes and three resize examples are defined
in [showcases.json](../docs/gifs/showcases.json). Each comparison changes just one
parameter between its panels and uses the same seed and timeline. The rotation
comparison uses larger pieces to make their orientation visible.

Run `node scripts/render-readme-gifs.mjs --showcase-only` to regenerate these twelve
GIFs. The renderer validates the parameters, compares browser/Python shader output
and records the resolved settings in the GIF manifest. The documentation check
detects mismatches between this page's preview commands, the JSON and recorded
settings. See the [recording guide](../docs/gifs/README.md) for dependencies.

## Waves, variation and elastic styles

These examples use preset schema 3; use them with a version that supports that format.
Resize stays off in all of them. See [effect controls](../docs/effect-controls.md).

```sh
python3 -m niri_fx preview --custom examples/tidal-fragments.json --output /tmp/tidal-fragments.html
python3 -m niri_fx preview --custom examples/mosaic-burst.json --output /tmp/mosaic-burst.html
python3 -m niri_fx preview --custom examples/chaotic-confetti.json --output /tmp/chaotic-confetti.html
python3 -m niri_fx preview --custom examples/crosswind.json --output /tmp/crosswind.html
python3 -m niri_fx preview --custom examples/orbital-ribbons.json --output /tmp/orbital-ribbons.html
python3 -m niri_fx preview --custom examples/split-curtain.json --output /tmp/split-curtain.html
python3 -m niri_fx preview --custom examples/ribbon-wave.json --output /tmp/ribbon-wave.html
python3 -m niri_fx preview --custom examples/shuffled-slats.json --output /tmp/shuffled-slats.html
python3 -m niri_fx preview --custom examples/venetian-sweep.json --output /tmp/venetian-sweep.html
python3 -m niri_fx preview --custom examples/spring-wobble.json --output /tmp/spring-wobble.html
python3 -m niri_fx preview --custom examples/rubber-band.json --output /tmp/rubber-band.html
python3 -m niri_fx preview --custom examples/jelly.json --output /tmp/jelly.html
```

## Piece shapes, hinges and elastic transforms

These 12 presets keep resize off. Each command reproduces the corresponding
JSON and the preset GIF in the main README.

```sh
python3 -m niri_fx preview --preset pixel-dust --output /tmp/pixel-dust.html
python3 -m niri_fx preview --preset bubble-burst --output /tmp/bubble-burst.html
python3 -m niri_fx preview --preset core-detonation --output /tmp/core-detonation.html
python3 -m niri_fx preview --preset checker-scatter --output /tmp/checker-scatter.html
python3 -m niri_fx preview --preset hinged-fan --output /tmp/hinged-fan.html
python3 -m niri_fx preview --preset venetian-shutter --output /tmp/venetian-shutter.html
python3 -m niri_fx preview --preset ribbon-fold --output /tmp/ribbon-fold.html
python3 -m niri_fx preview --preset zipper --output /tmp/zipper.html
python3 -m niri_fx preview --preset twist-snap --output /tmp/twist-snap.html
python3 -m niri_fx preview --preset flag-wave --output /tmp/flag-wave.html
python3 -m niri_fx preview --preset corner-spring --output /tmp/corner-spring.html
python3 -m niri_fx preview --preset accordion --output /tmp/accordion.html
```

## Dissolve and iris

[Noise Dissolve](noise-dissolve.json)

```sh
python3 -m niri_fx preview --preset noise-dissolve --output /tmp/noise-dissolve.html
```

[Ember Erosion](ember-erosion.json)

```sh
python3 -m niri_fx preview --preset ember-erosion --output /tmp/ember-erosion.html
```

[Frost Vanish](frost-vanish.json)

```sh
python3 -m niri_fx preview --preset frost-vanish --output /tmp/frost-vanish.html
```

[Iris Bloom](iris-bloom.json)

```sh
python3 -m niri_fx preview --preset iris-bloom --output /tmp/iris-bloom.html
```

[Diamond Turn](diamond-turn.json)

```sh
python3 -m niri_fx preview --preset diamond-turn --output /tmp/diamond-turn.html
```

[Portal Out](portal-out.json)

```sh
python3 -m niri_fx preview --preset portal-out --output /tmp/portal-out.html
```

An [independent Spring and Ember profile](profiles/spring-and-ember.json) opens with
Spring Wobble and closes with Ember Erosion. See the [profile guide](../docs/profiles.md).

## Pixel, wisp and distortion examples

These styles use stock Niri open/close shaders. Resize stays off.

[Pixel Wipe](pixel-wipe.json)

```sh
python3 -m niri_fx preview --custom examples/pixel-wipe.json --output /tmp/pixel-wipe.html
```

[Pixelate](pixelate.json)

```sh
python3 -m niri_fx preview --custom examples/pixelate.json --output /tmp/pixelate.html
```

[Dust Drift](dust-drift.json)

```sh
python3 -m niri_fx preview --custom examples/dust-drift.json --output /tmp/dust-drift.html
```

[Ghost Wisps](ghost-wisps.json)

```sh
python3 -m niri_fx preview --custom examples/ghost-wisps.json --output /tmp/ghost-wisps.html
```

[Ink Current](ink-current.json)

```sh
python3 -m niri_fx preview --custom examples/ink-current.json --output /tmp/ink-current.html
```

[Shockwave](shockwave.json)

```sh
python3 -m niri_fx preview --custom examples/shockwave.json --output /tmp/shockwave.html
```

[Ripple Collapse](ripple-collapse.json)

```sh
python3 -m niri_fx preview --custom examples/ripple-collapse.json --output /tmp/ripple-collapse.html
```

[Wave Fold](wave-fold.json)

```sh
python3 -m niri_fx preview --custom examples/wave-fold.json --output /tmp/wave-fold.html
```

## Hexagons, ink, glitch and movement styles

These examples keep resize disabled. Movement styles also work for open/close; native swaps require the [experimental build](../experimental/README.md).

```sh
python3 -m niri_fx preview --custom examples/hexagon-burst.json --output /tmp/hexagon-burst.html
python3 -m niri_fx preview --custom examples/hive-collapse.json --output /tmp/hive-collapse.html
python3 -m niri_fx preview --custom examples/signal-glitch.json --output /tmp/signal-glitch.html
python3 -m niri_fx preview --custom examples/chromatic-glitch.json --output /tmp/chromatic-glitch.html
python3 -m niri_fx preview --custom examples/ink-spread.json --output /tmp/ink-spread.html
python3 -m niri_fx preview --custom examples/ink-bloom.json --output /tmp/ink-bloom.html
python3 -m niri_fx preview --custom examples/slice-exchange.json --output /tmp/slice-exchange.html
python3 -m niri_fx preview --custom examples/pixel-transfer.json --output /tmp/pixel-transfer.html
python3 -m niri_fx preview --custom examples/soft-phase.json --output /tmp/soft-phase.html
```

## Resize profiles (explicit opt-in)

These profiles use Balanced for open/close and a separate resize effect. Importing previews them; applying their generated config enables resize.

```sh
python3 -m niri_fx preview --custom examples/profiles/elastic-resize.json --output /tmp/elastic-resize.html
python3 -m niri_fx preview --custom examples/profiles/accordion-resize.json --output /tmp/accordion-resize.html
python3 -m niri_fx preview --custom examples/profiles/ripple-resize.json --output /tmp/ripple-resize.html
```

## Vortex distortion

[Vortex Fold](vortex-fold.json) contracts into a pronounced clockwise spiral.
[Soft Swirl](soft-swirl.json) uses a shorter, gentler counterclockwise warp.
Both leave resize off.

```sh
python3 -m niri_fx preview --custom examples/vortex-fold.json --output /tmp/vortex-fold.html
python3 -m niri_fx preview --custom examples/soft-swirl.json --output /tmp/soft-swirl.html
```
