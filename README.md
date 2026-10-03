# NiriFX

![NiriFX — window effects for niri](docs/assets/nirifx-banner.svg)

**Explode windows into fragments. Slide them into ribbons. Make them wobble.**

NiriFX is a configurable window effects studio for the **niri Wayland compositor**. Choose from **55 presets across eight effect families**, preview the
actual shaders, and tune the controls for each family. The optional iNiR/iRiS
adapter adds your styles to its settings picker. A preset-folder export also
feeds Noctalia’s existing animation picker. Independent action profiles combine different
opening and closing styles; the optional DMS launcher adapter offers preset selection and undo.

[Get started](docs/getting-started.md) · [Studio & controls](docs/usage.md) ·
[Compatibility](docs/compatibility.md) · [Changelog](CHANGELOG.md) ·
[Contributing](CONTRIBUTING.md) · [GPU measurements](docs/performance.md)

**Development checkout after the 0.7.0 prerelease.** Includes independent profiles,
eight effect families, shell adapters and GPU measurements. See [Unreleased](CHANGELOG.md)
for changes newer than the tagged release. Opening and closing work on stock Niri 26.04.
Resize fragments are **off by default and strictly opt-in**. Native move/swap
fragmentation requires the separate experimental Niri patch. Performance and
appearance still need testing across GPUs, applications and display scales.

## TL;DR — try it or install it

**Works standalone on Niri. Quickshell and desktop-shell plugins are optional.**
Linux, Python 3.10+ and a WebGL browser are enough to try Studio:

```sh
git clone https://github.com/jturbide/niri-fx.git
cd niri-fx
python3 -m niri_fx studio --target standalone
```

Previewing changes no active animations. To install an effect on plain Niri,
review the setup plan, then apply it:

```sh
python3 -m niri_fx setup --target standalone --preset balanced
python3 -m niri_fx setup --target standalone --preset balanced --apply
```

Already using a shell's animation picker? Follow its guide instead of adding a
second manager: [iNiR / iRiS](docs/getting-started.md#inir-and-iris) ·
[DMS](docs/dms.md) · [Noctalia](docs/noctalia.md). Other paths:
[Standalone / Waybar](docs/standalone.md) · [Choose your scenario](docs/scenarios.md) ·
[Custom shells and future priorities](docs/roadmap.md).

## See it in motion

[Fragments](#twenty-three-fragment-styles) · [Slices](#eleven-slice-styles) · [Wobble](#seven-elastic-styles) · [Reveals](#dissolve-and-iris-reveals) · [Pixels](#pixel-wipes-and-dust) · [Wisps](#wisps-and-currents) · [Distortions](#shockwaves-and-distortions) · [Profiles](#combine-different-actions) · [Compare the controls](#one-control-at-a-time) ·
[Custom examples](#three-custom-examples) · [Resize](#resize--opt-in) ·
[Movement](#experimental-movement-and-swaps) · [Install](#try-it)

Opening and closing use the **Explosion** preset. Fragments keep pieces of the
window's actual texture, then reconstruct those pieces in their original places.
These clips use Studio's real shader renderer with synthetic content at 20 fps.

| Open · reconstruct | Close · explode |
| --- | --- |
| ![Opening reconstructs an intact window from fragments](docs/gifs/opening.gif) | ![Closing explodes a window into fragments](docs/gifs/closing.gif) |

### Twenty-three fragment styles

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

### Five new fragment variations

Unequal pieces, travelling waves and seeded direction variation add more organic
motion. These controls also feed the separate native movement experiment.

| Tidal Fragments | Mosaic Burst | Chaotic Confetti |
| --- | --- | --- |
| ![Tidal Fragments travel along a broad wave](docs/gifs/preset-tidal-fragments.gif) | ![Mosaic Burst uses unequal rectangular pieces](docs/gifs/preset-mosaic-burst.gif) | ![Chaotic Confetti tumbles along varied paths](docs/gifs/preset-chaotic-confetti.gif) |
| [Settings JSON](examples/tidal-fragments.json) | [Settings JSON](examples/mosaic-burst.json) | [Settings JSON](examples/chaotic-confetti.json) |
| **Crosswind** | **Orbital Ribbons** | |
| ![Crosswind carries fragments sideways in a wave](docs/gifs/preset-crosswind.gif) | ![Orbital Ribbons curve toward the center](docs/gifs/preset-orbital-ribbons.gif) | |
| [Settings JSON](examples/crosswind.json) | [Settings JSON](examples/orbital-ribbons.json) | |

**Uniform / unequal cells / travelling wave.** Same starting preset and timing;
size variation and wave motion are shown separately.

![Comparison of uniform fragments, unequal cells and a travelling wave](docs/gifs/compare-fragment-variation.gif)

### Piece shapes and spatial releases

**Pixel Dust** shrinks into fine debris; **Bubble Burst** rounds the textured
pieces. **Core Detonation** spreads outward from the burst origin, while
**Checker Scatter** releases alternating spatial groups. Each rebuilds an intact window.

| Pixel Dust | Bubble Burst |
| --- | --- |
| ![Tiny fragments shrink and rise](docs/gifs/preset-pixel-dust.gif) | ![Rounded texture fragments burst outward](docs/gifs/preset-bubble-burst.gif) |
| [Settings JSON](examples/pixel-dust.json) | [Settings JSON](examples/bubble-burst.json) |
| **Core Detonation** | **Checker Scatter** |
| ![A staged explosion spreads from the center](docs/gifs/preset-core-detonation.gif) | ![Checkerboard groups break apart in sequence](docs/gifs/preset-checker-scatter.gif) |
| [Settings JSON](examples/core-detonation.json) | [Settings JSON](examples/checker-scatter.json) |

**Square / rounded / extra shrink.** Same timing, density, seed and trajectory;
only the named shape control changes.

![Fragment corner rounding and shrink comparison](docs/gifs/compare-fragment-shapes.gif)

**Core / outer regions / diagonal.** Compare three spatial release sequences.
The Checker Scatter preset above demonstrates the fourth new sequence.

![Center-out, inward and diagonal release comparison](docs/gifs/compare-fragment-release.gif)

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
the Fragments family; they are separate from the built-in presets. **Resize is off
in all three.** The JSON files contain the exact parameters used for the GIFs.

| Meteor Shower | Orbit Burst | Reverse Gravity |
| --- | --- | --- |
| ![Meteor Shower: dense tumbling fragments accelerate downward](docs/gifs/recipe-meteor-shower.gif) | ![Orbit Burst: outward fragments sweep around the window center](docs/gifs/recipe-orbit-burst.gif) | ![Reverse Gravity: spinning fragments rise and arc upward](docs/gifs/recipe-reverse-gravity.gif) |
| 1,800 pieces · 1.7× down · 540° spin | 1,500 pieces · outward drift · 180° orbit | 1,000 pieces · 1.55× up · −70° orbit |
| [Settings JSON](examples/meteor-shower.json) | [Settings JSON](examples/orbit-burst.json) | [Settings JSON](examples/reverse-gravity.json) |

From the checkout, add an example to iRiS and then select it in Settings:

```sh
python3 -m niri_fx register --custom examples/meteor-shower.json
```

Use the other JSON filenames to add those styles too. Registration does not
activate an effect. [Preview commands and standalone export instructions](examples/README.md)
let you try the same examples without iNiR or any desktop configuration changes.

### Eleven slice styles

Whole strips slide, rotate and reassemble. **Slide Apart now alternates adjacent
horizontal strips**, while **Split Curtain** keeps the original outward split.
Choose random directions, release order, unequal widths and travelling waves.
Slices uses stock Niri open/close shaders; resize and movement are unsupported.

| Slide Apart | Alternating Blinds | Diagonal Shear |
| --- | --- | --- |
| ![Adjacent horizontal strips slide in alternating directions](docs/gifs/preset-slide-apart.gif) | ![Vertical strips travel alternately and rotate](docs/gifs/preset-alternating-blinds.gif) | ![Diagonal strips shear away](docs/gifs/preset-diagonal-shear.gif) |
| [Settings JSON](examples/slide-apart.json) | [Settings JSON](examples/alternating-blinds.json) | [Settings JSON](examples/diagonal-shear.json) |
| **Split Curtain** | **Ribbon Wave** | **Shuffled Slats** |
| ![Split Curtain retains the outward split](docs/gifs/preset-split-curtain.gif) | ![Ribbon Wave moves alternating strips along a wave](docs/gifs/preset-ribbon-wave.gif) | ![Shuffled Slats uses unequal sizes and random directions](docs/gifs/preset-shuffled-slats.gif) |
| [Settings JSON](examples/split-curtain.json) | [Settings JSON](examples/ribbon-wave.json) | [Settings JSON](examples/shuffled-slats.json) |
| **Venetian Sweep** | | |
| ![Venetian Sweep releases vertical strips from the center](docs/gifs/preset-venetian-sweep.gif) | | |
| [Settings JSON](examples/venetian-sweep.json) | | |

**Hinges and shutters.** Rotate around either end, compress strip width, or
combine both with travelling waves and staggered release. These are 2D strip
transforms, not a 3D page-turn simulation.

| Hinged Fan | Venetian Shutter |
| --- | --- |
| ![Strips rotate around one end like a fan](docs/gifs/preset-hinged-fan.gif) | ![Strips narrow into a center-first shutter](docs/gifs/preset-venetian-shutter.gif) |
| [Settings JSON](examples/hinged-fan.json) | [Settings JSON](examples/venetian-shutter.json) |
| **Ribbon Fold** | **Zipper** |
| ![Vertical ribbons rotate and narrow](docs/gifs/preset-ribbon-fold.gif) | ![Alternating strips separate in a zipper sequence](docs/gifs/preset-zipper.gif) |
| [Settings JSON](examples/ribbon-fold.json) | [Settings JSON](examples/zipper.json) |

**Hinge position — first end / center / other end.** Same strip rotation and travel.

![Three slice hinge positions compared](docs/gifs/compare-slice-hinges.gif)

**Width collapse — none / half / full.** Watch shutter strips become progressively thinner.

![Three slice width-collapse strengths compared](docs/gifs/compare-slice-collapse.gif)

**Direction — split halves / alternate / random.** Each random strip chooses its
own direction; there is no forced 50/50 distribution.

![Slice direction comparison with otherwise identical settings](docs/gifs/compare-slice-directions.gif)

**Release order — forward / center / random.** Control where separation begins.

![Slice release order comparison](docs/gifs/compare-slice-order.gif)

**Slice count — 4 / 12 / 32.** Same timing, texture and alternating motion.

![Comparison of four, twelve and thirty-two slices](docs/gifs/compare-slice-count.gif)

### Seven elastic styles

A Compiz-inspired spring feel: bend the whole window, let it oscillate, then
settle. Tune strength, frequency, damping and axis. These are timed open/close
shaders; native swaps use the experimental compositor. Interactive drag physics
and resize wobble are not implemented.

| Spring Wobble | Rubber Band | Jelly |
| --- | --- | --- |
| ![Spring Wobble bends and settles](docs/gifs/preset-spring-wobble.gif) | ![Rubber Band stretches sideways](docs/gifs/preset-rubber-band.gif) | ![Jelly oscillates in both axes](docs/gifs/preset-jelly.gif) |
| [Settings JSON](examples/spring-wobble.json) | [Settings JSON](examples/rubber-band.json) | [Settings JSON](examples/jelly.json) |

Twist around the center or a corner, add spatial ripples, and exaggerate spring
stretching. **Transform origin** controls rotation, stretching and collapse;
it does not pin an edge to the pointer or simulate cloth.

| Twist Snap | Flag Wave |
| --- | --- |
| ![A window twists and springs back](docs/gifs/preset-twist-snap.gif) | ![Whole-window ripples resemble a waving flag](docs/gifs/preset-flag-wave.gif) |
| [Settings JSON](examples/twist-snap.json) | [Settings JSON](examples/flag-wave.json) |
| **Corner Spring** | **Accordion** |
| ![Rotation and stretching use a lower-corner origin](docs/gifs/preset-corner-spring.gif) | ![Repeated bends combine with strong elastic stretching](docs/gifs/preset-accordion.gif) |
| [Settings JSON](examples/corner-spring.json) | [Settings JSON](examples/accordion.json) |

**Simple bend / twist / ripple.** Matched timing and spring settings, with one
added control in each comparison panel.

![Elastic twist and spatial ripple comparison](docs/gifs/compare-elastic-transforms.gif)

**Same duration, different springs:** compare all three at matched timing.

![Synchronized Spring Wobble, Rubber Band and Jelly comparison](docs/gifs/compare-elastic.gif)

[Controls, CLI examples and costs](docs/effect-controls.md) explain the new
parameters. Resize remains off in all built-ins.

### Dissolve and iris reveals

Erode the window through seeded noise, or reveal it with an aspect-correct mask.
These are stock Niri open/close shaders. Resize stays off.

| Noise Dissolve | Ember Erosion | Frost Vanish |
| --- | --- | --- |
| ![Noise erodes and rebuilds the window](docs/gifs/preset-noise-dissolve.gif) | ![Charcoal and white edges follow layered erosion](docs/gifs/preset-ember-erosion.gif) | ![A cool edge sweeps through fine noise](docs/gifs/preset-frost-vanish.gif) |
| [Settings](examples/noise-dissolve.json) | [Settings](examples/ember-erosion.json) | [Settings](examples/frost-vanish.json) |
| **Iris Bloom** | **Diamond Turn** | **Portal Out** |
| ![Circular reveal closes inward and reconstructs](docs/gifs/preset-iris-bloom.gif) | ![A rotating diamond mask reveals the window](docs/gifs/preset-diamond-turn.gif) | ![An off-center hole expands and closes](docs/gifs/preset-portal-out.gif) |
| [Settings](examples/iris-bloom.json) | [Settings](examples/diamond-turn.json) | [Settings](examples/portal-out.json) |

**Noise size — 12 / 32 / 90 logical pixels.** Direction, color and timing stay fixed.

![Fine, medium and broad dissolution patterns](docs/gifs/compare-dissolve-scale.gif)

**Reveal shape — circle / diamond / square.** Same origin, softness and timing.

![Three iris mask shapes compared](docs/gifs/compare-iris-shapes.gif)

**Ember now defaults to charcoal and white.** Saturation and brightness are
configurable alongside hue: choose white, black or bring back a warm edge.
Layered noise, flowing detail and a narrower rim improve the transition.
Frost keeps its cool, fine-grained look.

![White, black and warm Ember edge palettes](docs/gifs/compare-ember-palette.gif)

### Pixel wipes and dust

A radial grid wipe, progressive pixelation, or fine grains drifting on the wind.
Choose the starting point, wipe direction, grain size, randomness and dust travel.
The origin is a configured point in the window, not the live mouse pointer.

| Pixel Wipe | Pixelate | Dust Drift |
| --- | --- | --- |
| ![A radial wave removes and rebuilds grid pixels](docs/gifs/preset-pixel-wipe.gif) | ![A window pixelates into disappearing blocks](docs/gifs/preset-pixelate.gif) | ![Window-textured dust lifts away from a moving front](docs/gifs/preset-dust-drift.gif) |
| [Settings](examples/pixel-wipe.json) | [Settings](examples/pixelate.json) | [Settings](examples/dust-drift.json) |

![Pixel wipe, pixelation and drifting dust at the same grain size and timing](docs/gifs/compare-pixel-modes.gif)

### Wisps and currents

Threaded erosion and flowing texture distortion produce wisps. Adjust curl,
drift, thread density, direction and highlight color; the original texture alpha
is preserved. These are shader flows, not a fluid simulation.

| Ghost Wisps | Ink Current |
| --- | --- |
| ![Pale curling threads carry the window away](docs/gifs/preset-ghost-wisps.gif) | ![Dark diagonal currents dissolve and rebuild the window](docs/gifs/preset-ink-current.gif) |
| [Settings](examples/ghost-wisps.json) | [Settings](examples/ink-current.json) |

### Shockwaves and distortions

Bend the actual window texture with an expanding shock front, concentric ripples
or travelling planar waves. Control displacement, wavelength, falloff and origin.
These use stock Niri open/close shaders; resize and native movement stay unsupported.

| Shockwave | Ripple Collapse | Wave Fold |
| --- | --- | --- |
| ![An expanding ring warps and clears the window](docs/gifs/preset-shockwave.gif) | ![Concentric ripples distort a fading window](docs/gifs/preset-ripple-collapse.gif) | ![Travelling waves fold and restore the window texture](docs/gifs/preset-wave-fold.gif) |
| [Settings](examples/shockwave.json) | [Settings](examples/ripple-collapse.json) | [Settings](examples/wave-fold.json) |

![Shock front, radial ripples and planar waves with matched settings](docs/gifs/compare-distortion-patterns.gif)

[Burn My Windows](https://github.com/Schneegans/Burn-My-Windows) supplied the visual
references for pixel wipes, disintegration and wisps. These NiriFX shaders are
original implementations; no upstream shaders or preview assets are bundled.
[Controls and limits](docs/effect-controls.md).

### Combine different actions

Open with Spring Wobble and close with Ember Erosion in the same profile.
Studio now includes independent action editing, undo/redo, parameter reset,
search, favorites and a pinned A/B comparison. [Profile guide](docs/profiles.md).

![One profile opens with spring motion and closes with ember erosion](docs/gifs/profile-spring-and-ember.gif)

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

Three more **actual native swaps**, each recorded in the isolated patched Niri:

| Crosswind | Orbital Ribbons | Spring Wobble |
| --- | --- | --- |
| ![Native Crosswind swap](docs/gifs/native-swap-crosswind.gif) | ![Native Orbital Ribbons swap](docs/gifs/native-swap-orbital-ribbons.gif) | ![Native Spring Wobble swap](docs/gifs/native-swap-spring-wobble.gif) |
| Sideways fragment wave | Curved fragment streams | Continuous elastic windows |

Three additional **actual native swaps** show the new geometry controls:

| Bubble Burst | Core Detonation | Twist Snap |
| --- | --- | --- |
| ![Rounded fragments swap in native Niri](docs/gifs/native-swap-bubble-burst.gif) | ![Center-released fragments exchange columns](docs/gifs/native-swap-core-detonation.gif) | ![Twisting elastic windows swap columns](docs/gifs/native-swap-twist-snap.gif) |
| Rounded texture pieces | Staged breakup | Opaque spring rotation |

**Studio concept comparison — Crosswind / Orbital Ribbons / Tidal Fragments.**
This is the Canvas choreography preview, separate from the native recordings.

![Three labelled Studio swap concepts](docs/gifs/compare-swap-styles.gif)

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
git clone https://github.com/jturbide/niri-fx.git
cd niri-fx
python3 -m niri_fx preview --output /tmp/fragments-preview.html
xdg-open /tmp/fragments-preview.html
```

The offline preview changes no desktop settings. Use a new output filename if
you already have that file; existing previews are never overwritten.

For installation with diagnostics and a restore snapshot:

```sh
python3 -m niri_fx doctor
python3 -m niri_fx setup            # Review the detected target and file changes
python3 -m niri_fx setup --apply    # Apply that setup
```

Setup detects iNiR or standalone Niri and adds an application launcher if absent.
On iNiR it registers styles for you to select; standalone setup validates and adds
a managed include that Niri hot reloads. See [setup and restore](docs/setup.md)
for custom paths, updates and recovery.

### Niri + iNiR/iRiS

```sh
python3 -m niri_fx register --dry-run
python3 -m niri_fx register
```

Choose a NiriFX style in **iRiS Settings → Windows → Movement → Style**.
Registration adds presets without activating them. Your other presets and named
custom styles are preserved. Requires iNiR's external animation preset support.

### Standalone Niri, DankMaterialShell, or another Niri shell

```sh
python3 -m niri_fx render --preset explosion > /tmp/fragments.kdl
niri validate -c /tmp/fragments.kdl
```

Then follow the [standalone installation guide](docs/getting-started.md#standalone-niri)
to include it after your existing animation settings. The Niri configuration
path is shell-independent; a DMS-native picker has **not** been implemented or
runtime-tested. See [DMS setup and the roadmap](docs/compatibility.md).
For Noctalia’s existing picker, use the [preset-pack setup guide](docs/noctalia.md).

## Make it yours

```sh
python3 -m niri_fx studio
```

![Fragment controls in NiriFX Studio](docs/studio.png)

Select an effect family to see its controls. Tune fragments by particles, gravity,
spin, orbit and waves; slices by count, angle, direction and release order; or
elastic motion by spring strength, frequency and damping. Opening and closing
have separate timings. Studio opens as a dedicated Chromium app window,
with a browser fallback. **Import preset** opens any showcase JSON in the editor.
Tune release direction, burst origin and resize style, then export JSON/KDL or
**Save to iRiS** and
select your custom style in Settings. Saving does not activate it.

The default Balanced preset targets 720 pieces; Explosion uses 1,200 and
Implosion uses 1,000. Resize stays off until you enable it. The controls and
CLI examples are in the [usage guide](docs/usage.md).

## Development status

NiriFX is moving quickly and maintains one current API: `niri-fx`, the `niri_fx`
Python package, effect schema 3 and independent profile schema 1. Obsolete command aliases and formats are
removed. Read [the update policy](docs/upgrading.md) when upgrading a checkout.

## What works where?

| Feature | Stock Niri | Extra requirement |
| --- | --- | --- |
| Open / close effects, 55 presets in eight families | Yes; validated on 26.04 | Enable Niri animations |
| Optional resize (Fragments family only) | Yes; disabled by default | Studio checkbox or `--resize` |
| Studio preview and KDL / JSON export | Yes | WebGL browser |
| Independent open/close profiles | Yes | [Studio or CLI](docs/profiles.md) |
| DMS launcher adapter | Reversible KDL setup | [Plugin setup and validation scope](docs/dms.md) |
| Preset registration and Studio save | Yes | iNiR external preset support |
| Noctalia preset picker | KDL file integration | [Export pack and setup](docs/noctalia.md); tested in Noctalia 5.2.1 |
| Native movement / column swaps | No | [Pinned experimental Niri build](experimental/README.md) |
| Studio Move / Swap tabs | Visual concepts | Do not activate desktop movement |
| Hyprland, KWin, GNOME | No current backend | Separate compositor work |

## Built with and connected to

Built for [niri](https://github.com/niri-wm/niri), using **Python**, **GLSL** and
**WebGL**. Studio runs locally and exports self-contained previews.

- **iNiR / iRiS:** [external presets and Studio save](docs/integration.md).
- **Noctalia:** [KDL preset export](docs/noctalia.md) for its existing animation picker.
- **DankMaterialShell / DMS:** [standalone niri configuration](docs/compatibility.md),
  with an optional [launcher adapter](docs/dms.md) for presets, Studio and undo.
- **Quickshell:** the toolkit behind iNiR and DMS; NiriFX itself uses a web editor.

Explore [related shader projects](docs/related-projects.md), [brand assets](docs/branding.md)
and [community contribution opportunities](docs/community/README.md). NiriFX is
independent of these upstream projects.

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
workflow. Report reproducible bugs in [Issues](https://github.com/jturbide/niri-fx/issues);
use the [security policy](SECURITY.md) for vulnerabilities.

## License

Original NiriFX code, shaders and demo assets are [MIT licensed](LICENSE).
The optional Niri movement patch is **GPL-3.0-or-later** and ships with
[its license](experimental/COPYING-NIRI). See [third-party notices](THIRD_PARTY.md)
for the exact scope. Independent project, not affiliated with Niri, iNiR, DMS or Noctalia.
