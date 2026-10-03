# Custom showcase examples

The checked-in JSON supplies the exact settings used in the README recordings.
Use **Import preset** in Studio to inspect any file without applying it. The
three recipes and three new built-in examples leave resize off; the three
resize examples explicitly enable it.

| Example | Starting preset | Main changes |
| --- | --- | --- |
| [Meteor Shower](meteor-shower.json) | Earth | 1,800 pieces, heavier downward gravity and tumbling |
| [Orbit Burst](orbit-burst.json) | Explosion | 1,500 pieces, an outward sweep and 180° orbit |
| [Reverse Gravity](reverse-gravity.json) | Updraft | 1,000 pieces, stronger lift and randomized spin |

| New example | Behavior | Resize |
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

These use schema 2. Fragment examples retain schema 1 for compatibility. Slice
presets cannot enable resize or native movement. Import them into Studio first,
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

## New preset and resize previews

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
