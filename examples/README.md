# Custom showcase examples

These are named custom styles built with the existing controls, not new built-in
presets. The checked-in JSON is the source of the README recordings. All three
explicitly disable resize fragments.

| Example | Starting preset | Main changes |
| --- | --- | --- |
| [Meteor Shower](meteor-shower.json) | Earth | 1,800 pieces, heavier downward gravity and tumbling |
| [Orbit Burst](orbit-burst.json) | Explosion | 1,500 pieces, an outward sweep and 180° orbit |
| [Reverse Gravity](reverse-gravity.json) | Updraft | 1,000 pieces, stronger lift and randomized spin |

## Import into iNiR / iRiS

From the checkout, register any examples you want:

```sh
python3 -m niri_fragments register --custom examples/meteor-shower.json
python3 -m niri_fragments register --custom examples/orbit-burst.json
python3 -m niri_fragments register --custom examples/reverse-gravity.json
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
python3 -m niri_fragments preview --preset earth \
  --particles 1800 --gravity-strength 1.7 --scatter 100 \
  --rotation random --spin 540 --dispersion 1 --stagger 0.28 \
  --open-ms 760 --close-ms 820 --no-resize --output /tmp/meteor-shower.html
xdg-open /tmp/meteor-shower.html
```

### Orbit Burst

```sh
python3 -m niri_fragments preview --preset explosion \
  --particles 1500 --gravity-strength 0.85 --scatter 150 \
  --rotation random --spin 240 --swirl 180 --dispersion 0.8 --stagger 0.16 \
  --open-ms 900 --close-ms 900 --no-resize --output /tmp/orbit-burst.html
xdg-open /tmp/orbit-burst.html
```

### Reverse Gravity

```sh
python3 -m niri_fragments preview --preset updraft \
  --particles 1000 --gravity-strength 1.55 --scatter 85 \
  --rotation random --spin 360 --swirl -70 --dispersion 0.9 --stagger 0.22 \
  --open-ms 750 --close-ms 800 --no-resize --output /tmp/reverse-gravity.html
xdg-open /tmp/reverse-gravity.html
```

For standalone Niri, DMS or another Niri shell, choose **Export Niri config** in
the preview and follow the [standalone guide](../docs/getting-started.md#standalone-niri).
You can also replace `preview` with `render`, remove `--output`, and redirect
stdout to a KDL file. Validate the generated file before including it.

## Reproducing the gallery

The four synchronized comparisons and these three custom examples are defined
in [showcases.json](../docs/gifs/showcases.json). Each comparison changes just one
parameter between its panels and uses the same seed and timeline. The rotation
comparison uses larger pieces to make their orientation visible.

Run `node scripts/render-readme-gifs.mjs --showcase-only` to regenerate these seven
GIFs. The renderer validates the parameters, compares browser/Python shader output
and records the resolved settings in the GIF manifest. The documentation check
detects mismatches between this page's preview commands, the JSON and recorded
settings. See the [recording guide](../docs/gifs/README.md) for dependencies.
