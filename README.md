# Niri Fragments

**Explode windows into pixels. Pull them back together.**

Niri Fragments gives application windows textured particle animations: outward
bursts, inward collapses, gravity, orbit and rotation. Choose from 14 presets or
build your own in Fragments Studio. Niri renders the effects; the optional
iNiR/iRiS adapter adds them to your existing settings picker.

[Get started](docs/getting-started.md) · [Studio & controls](docs/usage.md) ·
[Compatibility](docs/compatibility.md) · [Changelog](CHANGELOG.md) ·
[Contributing](CONTRIBUTING.md)

**Public prerelease · 0.5.0.** Opening and closing work on stock Niri 26.04.
Resize fragments are **off by default and strictly opt-in**. Native move/swap
fragmentation requires the separate experimental Niri patch. Performance and
appearance still need testing across GPUs, applications and display scales.

## See it in motion

[Presets](#fourteen-starting-styles) · [Compare the controls](#one-control-at-a-time) ·
[Custom examples](#three-custom-examples) · [Resize](#resize--opt-in) ·
[Movement](#experimental-movement-and-swaps) · [Install](#try-it)

Opening and closing use the **Explosion** preset. Fragments keep pieces of the
window's actual texture, then reconstruct those pieces in their original places.
These clips use Studio's real shader renderer with synthetic content at 20 fps.

| Open · reconstruct | Close · explode |
| --- | --- |
| ![Opening reconstructs an intact window from fragments](docs/gifs/opening.gif) | ![Closing explodes a window into fragments](docs/gifs/closing.gif) |

### Fourteen starting styles

Every loop closes and opens at that preset's configured timing. Start with
**Balanced** for an everyday burst, **Explosion** for a stronger outward blast,
or **Implosion** for an inward collapse.

| Subtle | Balanced | Dramatic |
| --- | --- | --- |
| ![Subtle: compact fragments separate and return](docs/gifs/preset-subtle.gif) | ![Balanced: a medium-density outward burst](docs/gifs/preset-balanced.gif) | ![Dramatic: a wider, denser burst](docs/gifs/preset-dramatic.gif) |
| Compact · 360 pieces | Everyday · 720 pieces | Wide burst · 1,100 pieces |
| **Explosion** | **Implosion** | **Earth** |
| ![Explosion: a dense outward blast and reconstruction](docs/gifs/preset-explosion.gif) | ![Implosion: pieces collapse into the center and return](docs/gifs/preset-implosion.gif) | ![Earth: falling fragments with randomized spin](docs/gifs/preset-earth.gif) |
| Outward blast · 1,200 pieces | Inward collapse · 1,000 pieces | Downward gravity · 600 pieces |
| **Black Hole** | **Space** | **Vortex** |
| ![Black Hole: fragments turn toward the center](docs/gifs/preset-black-hole.gif) | ![Space: freely spinning fragments drift outward](docs/gifs/preset-space.gif) | ![Vortex: fragments orbit into the center](docs/gifs/preset-vortex.gif) |
| Center pull + turning | Outward drift + free spin | Center pull + orbit |
| **Confetti** | **Updraft** | |
| ![Confetti: a shower of small tumbling fragments](docs/gifs/preset-confetti.gif) | ![Updraft: fragments rise and turn along their travel](docs/gifs/preset-updraft.gif) | |
| Tumbling shower · 1,600 pieces | Upward pull + gentle orbit | |

Counts are targets, not exact totals; square tiles adapt to each window's shape.

**New in 0.5: release waves, movable burst origins and a deeper orbital collapse.**

| Directional Wave | Corner Burst | Orbital Collapse |
| --- | --- | --- |
| ![Directional Wave releases three sections from left to right](docs/gifs/preset-directional-wave.gif) | ![Corner Burst explodes from an off-center origin](docs/gifs/preset-corner-burst.gif) | ![Orbital Collapse spirals fragments into a central point](docs/gifs/preset-orbital-collapse.gif) |
| 900 pieces · staged release | 1,200 pieces · lower-left origin | 1,400 pieces · 300° orbit |
| [Settings JSON](examples/directional-wave.json) | [Settings JSON](examples/corner-burst.json) | [Settings JSON](examples/orbital-collapse.json) |

### One control at a time

These synchronized comparisons use the **same texture, seed, timing and other
settings within each row**. Each closes, pauses and reconstructs; only the named
control changes. They are examples of settings, not additional built-in presets.

**Particle count — 180 / 720 / 2,400.** Fewer pieces give a chunky breakup;
more pieces produce a finer cloud. This is a visual comparison, not a benchmark.

![Synchronized comparison of 180, 720 and 2400 target particles with otherwise identical settings](docs/gifs/compare-density.gif)

**Gravity direction — down / center / outward.** Fall like debris, collapse
into a central point, or spread in every direction.

![Same fragments under downward gravity, center attraction and outward space motion](docs/gifs/compare-gravity.gif)

**Gravity strength — 0.3× / 1× / 2×.** The same downward direction ranges from
a gentle fall to a stronger pull. Strength is an artistic multiplier.

![Same downward gravity at strengths 0.3, 1 and 2](docs/gifs/compare-strength.gif)

**Rotation — none / random / follow travel.** Larger pieces make the change in
orientation easier to see; all three use the same 180-particle target.

![Larger fragments with no rotation, random spin and orientation following travel](docs/gifs/compare-rotation.gif)

**Burst origin — center / upper left / lower right.** Move the point from which
pieces scatter and around which they orbit; everything else is held constant.

![Identical bursts with centered, upper-left and lower-right origins](docs/gifs/compare-origin.gif)

### Three custom examples

Combine the controls to create your own style. These downloadable examples use
existing capabilities; they are separate from the 14 built-ins. **Resize is off
in all three.** The JSON files contain the exact parameters used for the GIFs.

| Meteor Shower | Orbit Burst | Reverse Gravity |
| --- | --- | --- |
| ![Meteor Shower: dense tumbling fragments accelerate downward](docs/gifs/recipe-meteor-shower.gif) | ![Orbit Burst: outward fragments sweep around the window center](docs/gifs/recipe-orbit-burst.gif) | ![Reverse Gravity: spinning fragments rise and arc upward](docs/gifs/recipe-reverse-gravity.gif) |
| 1,800 pieces · 1.7× down · 540° spin | 1,500 pieces · outward drift · 180° orbit | 1,000 pieces · 1.55× up · −70° orbit |
| [Settings JSON](examples/meteor-shower.json) | [Settings JSON](examples/orbit-burst.json) | [Settings JSON](examples/reverse-gravity.json) |

From the checkout, add an example to iRiS and then select it in Settings:

```sh
python3 -m niri_fragments register --custom examples/meteor-shower.json
```

Use the other JSON filenames to add those styles too. Registration does not
activate an effect. [Preview commands and standalone export instructions](examples/README.md)
let you try the same examples without iNiR or any desktop configuration changes.

### Resize — opt-in

**Disabled by default.** When explicitly enabled, the actual resize shader breaks
up the old window texture and rebuilds the contents at the new size.

<img src="docs/gifs/resize.gif" alt="Opt-in resize breaks the window into fragments and reconstructs it at its new size" width="560">

Enable **Fragment windows when resizing** in Studio or pass `--resize` when
saving/rendering a style. Ordinary resizing stays in place unless you opt in.

Three styles let you choose how much of the window breaks apart. **The example
JSON below explicitly enables resize**; importing it loads that choice into the
editor, and applying the resulting preset enables it on the desktop.

| Full Breakup | Edge Rebuild | Soft Reflow |
| --- | --- | --- |
| ![Full Breakup fragments the whole window during resize](docs/gifs/resize-full.gif) | ![Edge Rebuild concentrates fragments around changing edges](docs/gifs/resize-edge.gif) | ![Soft Reflow keeps a readable window beneath lighter fragments](docs/gifs/resize-soft.gif) |
| Whole-window effect | Preserves the center | Gentler blend |
| [Opt-in JSON](examples/resize-full.json) | [Opt-in JSON](examples/resize-edge.json) | [Opt-in JSON](examples/resize-soft.json) |

### Experimental movement and swaps

**Native column swap — requires the patched Niri build.** Two real synthetic
demo clients deconstruct, exchange columns and reconstruct inside a nested
compositor. Both streams overlap during the swap; particles are still rendered
per window, with no shared collision simulation or particle-level interleaving.

![Two real demo windows fragment, exchange columns and reconstruct in patched Niri](docs/gifs/native-swap.gif)

**Studio design concepts:** the two clips below show the intended move/swap
choreography. They are Canvas previews, with different trajectories and particle
ordering from the native patch. Saving them does not install movement effects.

| Move concept | Swap concept |
| --- | --- |
| ![Studio concept of one fragmented window moving between columns](docs/gifs/move-concept.gif) | ![Studio concept of two fragment streams swapping columns](docs/gifs/swap-concept.gif) |

See [the experimental build and limitations](experimental/README.md) before
trying native movement. Direct dragging and seamless interrupted swaps remain
future work. The standard installation uses stock Niri.

All clips use synthetic content; GIF scaling and palette reduction affect fine
edges. [Recording details and reproduction commands](docs/gifs/README.md).

## Try it

Requires Linux, Python 3.10+ and Niri for desktop effects. There are no Python
runtime dependencies. Chromium provides the app-style editor; other WebGL-capable
browsers can open the offline preview.

```sh
git clone https://github.com/jturbide/niri-fragments.git
cd niri-fragments
python3 -m niri_fragments preview --output /tmp/fragments-preview.html
xdg-open /tmp/fragments-preview.html
```

The offline preview changes no desktop settings. Use a new output filename if
you already have that file; existing previews are never overwritten.

For installation with diagnostics and a restore snapshot:

```sh
python3 -m niri_fragments doctor
python3 -m niri_fragments setup            # Review the detected target and file changes
python3 -m niri_fragments setup --apply    # Apply that setup
```

Setup detects iNiR or standalone Niri and adds an application launcher if absent.
On iNiR it registers styles for you to select; standalone setup validates and adds
a managed include that Niri hot reloads. See [setup and restore](docs/setup.md)
for custom paths, updates and recovery.

### Niri + iNiR/iRiS

```sh
python3 -m niri_fragments register --dry-run
python3 -m niri_fragments register
```

Choose a Fragments style in **iRiS Settings → Windows → Movement → Style**.
Registration adds presets without activating them. Your other presets and named
custom styles are preserved. Requires iNiR's external animation preset support.

### Standalone Niri, DankMaterialShell, or another Niri shell

```sh
python3 -m niri_fragments render --preset explosion > /tmp/fragments.kdl
niri validate -c /tmp/fragments.kdl
```

Then follow the [standalone installation guide](docs/getting-started.md#standalone-niri)
to include it after your existing animation settings. The Niri configuration
path is shell-independent; a DMS-native picker has **not** been implemented or
runtime-tested. See [DMS setup and the roadmap](docs/compatibility.md).

## Make it yours

```sh
python3 -m niri_fragments studio
```

![Particle controls in Fragments Studio](docs/studio.png)

Tune particle count, gravity direction and strength, spin, orbit, scatter,
release stagger and timing. Studio opens as a dedicated Chromium app window,
with a browser fallback. **Import preset** opens any showcase JSON in the editor.
Tune release direction, burst origin and resize style, then export JSON/KDL or
**Save to iRiS** and
select your custom style in Settings. Saving does not activate it.

The default Balanced preset targets 720 pieces; Explosion uses 1,200 and
Implosion uses 1,000. Resize stays off until you enable it. The controls and
CLI examples are in the [usage guide](docs/usage.md).

## What works where?

| Feature | Stock Niri | Extra requirement |
| --- | --- | --- |
| Open / close fragments, 14 presets | Yes; validated on 26.04 | Enable Niri animations |
| Optional resize fragments | Yes; disabled by default | Studio checkbox or `--resize` |
| Studio preview and KDL / JSON export | Yes | WebGL browser |
| Preset registration and Studio save | Yes | iNiR external preset support |
| Native movement / column swaps | No | [Pinned experimental Niri build](experimental/README.md) |
| Studio Move / Swap tabs | Visual concepts | Do not activate desktop movement |
| Hyprland, KWin, GNOME | No current backend | Separate compositor work |

## Documentation and development

Start with the [documentation index](docs/README.md) for installation, updating,
rollback, troubleshooting, integration details and the movement experiment.
[Validation results](docs/validation.md) distinguish automated checks from
remaining desktop acceptance. [Related projects](docs/related-projects.md)
cover other Niri shader collections and integrations.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/validate.py --require-glsl --require-niri
python3 scripts/check-docs.py
```

See [Contributing](CONTRIBUTING.md) for dependencies and the full development
workflow. Report reproducible bugs in [Issues](https://github.com/jturbide/niri-fragments/issues);
use the [security policy](SECURITY.md) for vulnerabilities.

## License

Original Fragments code, shaders and demo assets are [MIT licensed](LICENSE).
The optional Niri movement patch is **GPL-3.0-or-later** and ships with
[its license](experimental/COPYING-NIRI). See [third-party notices](THIRD_PARTY.md)
for the exact scope. Independent project, not affiliated with Niri, iNiR or DMS.
