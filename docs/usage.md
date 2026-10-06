# Studio and controls

![Fragment controls in NiriFX Studio](studio.png)

```sh
python3 -m niri_fx studio
```

This opens a dedicated Chromium app window, with no tabs or address bar and a
separate profile. The optional application launcher opens the same window.
If Chromium is unavailable, Studio opens in your default browser; use
`studio --browser` to request a browser tab. The app starts in [Library](library.md)
for finished looks and action combos. Use **Customize in Studio**, an action's
**Tune** button, or `studio --edit` for the controls described below.
Choose an **Effect family** first. The starting styles and
controls follow the selected family. Switching families starts with that family's
first preset; export a custom style before switching if you want to keep it.

## Try and share online

[Web Studio](https://jturbide.github.io/niri-fx/studio/) uses the same editor and
shader templates without a local server. Gallery cards open their recorded settings.
**Share settings** copies a link with the document and preview position; JSON
and Niri config downloads work without installation. See [Web Studio](web-studio.md)
for local import, sharing limits and the distinction between previews and activation.

## Slices

Slices preserve broad strips of the actual window texture. They support opening
and closing on stock Niri, with Accordion resize. Native slice movement
requires the experimental build. Opening reverses the closing path with its own duration.

| Control | Range / meaning |
| --- | --- |
| Slice count | 2–48 strips; more strips also increase shader work |
| Slice angle | −90° to 90°; 0° horizontal, ±90° vertical |
| Travel direction | Split outward, alternating strips, along the angle, against the angle, or independent random signs |
| Travel distance | 0–600 logical pixels |
| Release stagger | 0–0.75; delay between first and last strip |
| Strip rotation | −60° to 60° during travel |
| Opening / closing time | Independent 100–1500 ms durations |

```sh
python3 -m niri_fx preview --preset diagonal-shear --output /tmp/slices.html
python3 -m niri_fx render --family slices --slice-count 20 --slice-angle 30 \
  --slice-direction alternate --slice-rotation 8 > /tmp/slices.kdl
```

Built-in presets preserve existing resize settings. See [effect controls](effect-controls.md) for
waves, variation, wobble, colors and distortion, with examples and performance notes.

## Fragments

Live fragment controls include:

- **Shape mixture:** a secondary built-in shape, a 0–1 cell mixture and a stable layout seed; see [fragment shapes](fragment-shapes.md#mix-two-shapes).
- **Gravity direction:** none, down, up, left, right, center, or outward.
- **Gravity strength:** 0–3×. Downward gravity accelerates; outward space motion
  drifts at a constant radial rate. Strength is artistic, not an SI unit.
- **Particles:** a target of 16–4096 pieces, or a fixed square size of 8–128
  logical pixels. Target counts are approximate so fragments remain square;
  very small windows also have a four-pixel minimum tile size.
- **Rotation:** none, random spin, or orientation toward the travel direction.
- **Spin:** 0–720 degrees; the random spin range or the alignment limit.
- **Orbit:** −360 to +360 degrees around the selected burst origin.
- **Spread:** 0–240 logical pixels of initial radial scatter.
- **Path dispersion:** 0–1; separates fragment speeds and curves their paths.
- **Release stagger:** 0–0.4; varies when fragments separate and dissolve.
- **Release pattern:** together; center-out, inward, diagonal or checkerboard groups; or waves starting at the left, right,
  top or bottom. **Wave span** (0–0.7) separates the first and last wave; larger
  values make the sweep more pronounced. Random stagger still varies individual pieces.
- **Burst origin X/Y:** 0–1 within the window, from left/top to right/bottom.
  The same point controls scatter, central attraction and orbit.
- **Timing:** independent opening, closing and resizing durations, 100–1500 ms.
- **Resize:** Preserve keeps existing settings; choose NiriFX Style or Off in a profile. Breakup strength (0–1) controls how bounded fragments
  reconstruct the window at its new size. Resize shares particle count, gravity
  direction and rotation; its strength is separate from open/close gravity.
  Choose **Full Breakup**, **Edge Rebuild** (keeps the center intact) or **Soft
  Reflow** (lighter breakup over the ordinary resize image). Selecting a style
  alone does not change the action choice.

The editor uses the same shader templates as the CLI. Click **Reconstruct** or
**Deconstruct**, or scrub the timeline. With the iNiR save target, set a name and
choose **Save to iRiS**;
then select that named style in iRiS's existing picker. Saving does not activate
it. Saving the same name updates that custom preset, with a backup.

The **Move** and **Swap** tabs are visual concepts: textured particles cross
between columns and reconstruct at their destinations. They are not installed
movement effects. Saving/exporting changes open/close and enabled resize behavior.
Run `python3 scripts/nested-demo.py` after building the isolated experiment
to try actual native movement. See [the compositor work](movement.md).

The controls live in NiriFX Studio. iRiS's native page lists the resulting
presets; its stock thumbnail still shows generic timing rather than this shader.

The editor binds only to loopback and uses a per-session save token and origin
checks. The iNiR save target reads its installed helper and writes its preset
registry. Standalone and Noctalia targets download files without activation.
The editor page makes no external network requests. It exits within 15 minutes of the app window or tab
closing (or immediately with Ctrl+C when launched from a terminal).

For an app-launcher entry tied to this checkout:

```sh
python3 scripts/install-desktop.py
```

Search for **NiriFX Studio** in your application launcher. This is
on-demand; nothing is added to session startup. Keep the checkout at its current
path, or recreate the launcher after moving it.

An offline editor is also available:

```sh
python3 -m niri_fx preview --preset earth --output /tmp/fragments.html
xdg-open /tmp/fragments.html
```

Both offline and app-style Studio support **Import preset**, JSON export and
standalone KDL export. Import validates the entire file before replacing editor
settings; it does not save or activate anything. Files are limited to 32 KiB in
current source (16 KiB in 0.20) and
contain named parameters, never arbitrary shaders. Missing effect fields use defaults;
single-effect documents without `resize` leave the underlying resize settings
unchanged. An explicit `resize: true` is retained. Schema 4
[fragment responses](profiles.md#portable-fragment-response) require all 18 values.

Open the same file directly from the CLI:

```sh
python3 -m niri_fx studio --custom examples/corner-burst.json
python3 -m niri_fx render --custom examples/corner-burst.json > /tmp/corner-burst.kdl
```

Use `--custom` without effect overrides. To save an imported file to iNiR:

```sh
python3 -m niri_fx register --custom ~/Downloads/nirifx-preset.json
```

## Command-line options

```sh
# Save a custom option alongside the built-in pack.
python3 -m niri_fx register --name "Heavy Meteor" --preset earth \
  --gravity-strength 1.8 --particles 400 --rotation random --spin 360

# Render a standalone override; includes no shell integration or activation.
python3 -m niri_fx render --preset black-hole --gravity-strength 0.8 \
  --swirl 120 --rotation gravity --particles 300 > fragments.kdl
niri validate -c fragments.kdl
```

`--tile-size` switches off target-count mode. `--particles 0` also selects fixed
sizing. `list` prints the built-in parameters as JSON. `--preset` chooses the
starting values for `render`, `preview`, `studio`, or a named `register`.

## Presets

The current checkout has 80 built-ins across nine families. The original styles are listed below;
[new styles and controls](effect-controls.md) cover five varied Fragments, four
additional Fragments, Slices and Elastic presets, including piece shapes, hinges and spring transforms.


| Preset | Motion |
| --- | --- |
| Subtle / Balanced / Dramatic | Increasingly dense bursts: 360 / 720 / 1,100 pieces |
| Explosion | 1,200 tumbling pieces burst outward; opening implodes them into place |
| Implosion | 1,000 pieces collapse toward the center; opening reverses the collapse |
| Earth | Accelerates downward with randomized spin |
| Black Hole | Draws pieces inward and turns them toward the center |
| Space | Drifts outward in every direction with free spin |
| Vortex | Spirals inward while pieces follow their travel direction |
| Confetti | Small tumbling pieces with downward gravity |
| Updraft | Rises with a slight orbit and direction-following rotation |
| Directional Wave | Three stages release from left to right, with upward drift |
| Corner Burst | 1,200 pieces scatter from a lower-left origin |
| Orbital Collapse | 1,400 pieces spiral inward with 300° orbit |
| Slide Apart (Slices) | 12 horizontal strips travel alternately |
| Alternating Blinds (Slices) | 16 vertical strips travel alternately and rotate |
| Diagonal Shear (Slices) | 10 diagonal strips travel alternately |

Particle targets are approximate and depend on window geometry. Opening reverses
the closing trajectory with its own duration; the effect is artistic rather than
a physical simulation. There are no particle collisions.

## Choose a resize style

Resize effects are available for **Fragments, Elastic, Slices and Distortion**.
See the [resize guide](resize.md) for profiles, controls and supported Niri actions.

Built-in presets and fresh Studio sessions add no resize override. Imported
custom presets retain their explicit choice. Set Resize to **NiriFX Style** in
Library or Studio, then choose a supported preset; or pass `--resize`:

```sh
python3 -m niri_fx register --name "Resize experiment" --preset balanced --resize
python3 -m niri_fx render --preset balanced --resize --resize-mode edge > /tmp/fragments-resize.kdl
```

`--no-resize` suppresses the override. With the iNiR adapter, the base preset's
resize behavior is preserved when the resize override is omitted. Standalone exports
omit `window-resize`, leaving your existing Niri settings in charge. Saved custom
presets keep their explicit choices; JSON without `resize` opts out.

See [installation, updating and rollback](getting-started.md) before applying
exports. The CLI's `--help` and subcommand `--help` list every available option.

See [independent profiles and Studio workflow](profiles.md) for action selection,
undo/redo, favorites, A/B comparison and shell save targets. The [effect controls](effect-controls.md)
also cover Dissolve, Iris, Pixels, Wisps and Distortion; the [GPU harness](performance.md) measures shader draw cost.

## Basic and Advanced views

Studio starts with the main controls visible. Enable **Advanced controls** for
variation, origins, palettes and detailed motion settings. Hiding a control never
resets its value. **Pause** stops playback; the timeline always supports manual
inspection. **Reduced motion** shows endpoints when Play is pressed, respects
the system preference and changes only the preview, not exported settings.

Native movement strength appears in Advanced view for supported families.
It controls the experimental compositor export; the stock open/close and resize
shaders ignore it. Use the nested demo to evaluate native movement.

[Desktop motion packs](desktop-motion.md) add optional workspace, camera and overview springs to independent profiles. Ordinary presets preserve those timings.
