# NiriFX

![NiriFX — window effects for niri](docs/assets/nirifx-banner.svg)

**Explode windows into fragments. Slide them into ribbons. Make them wobble.**

NiriFX brings customizable animations to the **niri Wayland compositor**.
Pick a finished style from **75 presets**, **9 effect families** and **16 ready-made profiles**. For further
customization, tune it in Studio, online or on your desktop. Use different effects for opening and closing, from a quiet ripple
to a full window explosion.

Works **standalone** or with **iNiR/iRiS, DankMaterialShell and Noctalia**.
Quickshell is optional. Studio opens as an app-style window or a browser tab.

[Interactive gallery](https://jturbide.github.io/niri-fx/gallery/) ·
[Web Studio](https://jturbide.github.io/niri-fx/studio/) ·
[All presets & comparisons](docs/catalog.md) · [Preset reference](docs/presets.md) ·
[Documentation](docs/README.md) ·
[Roadmap](ROADMAP.md) · [Changelog](CHANGELOG.md)

Opening, closing and resize effects work on **stock Niri**, tested with 26.04.
Built-in presets leave resize unchanged. Native movement and swaps, pointer
deformation and the interruption improvements require the [experimental compositor](experimental/README.md).

This README describes `main`, which can include features newer than the latest
release. [Download v0.18.0](https://github.com/jturbide/niri-fx/releases/tag/v0.18.0)
for the versioned package, or read [choosing a version](docs/releases.md).

## Quick start

**Try without installing:** choose from [nine starter looks](https://jturbide.github.io/niri-fx/gallery/?collection=starter), open [Web Studio](https://jturbide.github.io/niri-fx/studio/),
or choose **Try in Studio** from the [gallery](https://jturbide.github.io/niri-fx/gallery/).
Choose a ready-made combo in **Library**, use one style for every action or mix
opening and closing styles. Click **Preview combo** to watch the whole sequence.
Choose resize and Move / swap styles separately, or keep the desktop's current
behavior. Save a named profile, share its
settings or download JSON. Previewing does not change your desktop.
[Bring a downloaded style to Niri](docs/web-studio.md).

For a small install without the source gallery, use the [release wheel](docs/releases.md#0180-prerelease).
On Niri with Python 3.10+, you can also start the guided workflow from source:

```sh
git clone --depth 1 https://github.com/jturbide/niri-fx.git
cd niri-fx
python3 -m niri_fx
```

Choose a preset, review its files and type `apply`. Run it again and choose `undo`
to restore the previous settings. With iNiR, it registers the collection for your
existing iRiS picker. No extra UI toolkit is required. [Terminal guide](docs/terminal.md).

Browse by look with `python3 -m niri_fx list --collections --text`, then try
`python3 -m niri_fx list --collection shapes --text`. The same
[nine collections](docs/collections.md) appear in Studio and the gallery.

For a visual editor, run `python3 -m niri_fx studio --target standalone`.
Previewing changes no active animations. For scriptable setup on plain Niri:

```sh
python3 -m niri_fx setup --target standalone --preset balanced
python3 -m niri_fx setup --target standalone --preset balanced --apply
```

Already using a shell's animation picker? Follow its guide:
[iNiR / iRiS](docs/getting-started.md#inir-and-iris) · [DMS](docs/dms.md) ·
[Noctalia](docs/noctalia.md) · [Standalone / Waybar](docs/standalone.md).
The [scenario guide](docs/scenarios.md) helps choose the right setup and restore path.

**Using an AI agent?** Start with `python3 -m niri_fx agent-info` for structured
command discovery, or read the [agent guide](docs/agents.md). The CLI provides
compact preset search, parameter bounds, validated exports and reviewed
Apply/Restore. A reusable skill is included in version 0.18 and newer.

## See it in motion

The [interactive gallery](https://jturbide.github.io/niri-fx/gallery/) starts with
nine recommended looks, with Fragments first. Choose **Open/close pairings** for
finished combinations or **All examples** to explore the whole collection. Search,
family/scenario filters and click-to-play previews help narrow it down. It starts paused and loads one
animation at a time. Style cards link to editable settings, JSON downloads and
a local Studio command. Share a filtered view or a customized Studio link.
The [full catalog](docs/catalog.md) includes every preset,
control comparison and downloadable example.

### Fragments first

Fragments preserve pieces of the window's texture and reconstruct them in their
original places. Start with **Balanced**, use **Explosion** for a stronger burst,
or **Implosion** for an inward collapse.

| Balanced | Explosion | Implosion |
| --- | --- | --- |
| ![An everyday fragment burst](docs/gifs/preset-balanced.gif) | ![A dense outward explosion](docs/gifs/preset-explosion.gif) | ![Pieces collapse inward](docs/gifs/preset-implosion.gif) |
| **Core Detonation** | **Mosaic Burst** | **Orbital Ribbons** |
| ![A staged explosion spreads from the center](docs/gifs/preset-core-detonation.gif) | ![Unequal textured pieces burst outward](docs/gifs/preset-mosaic-burst.gif) | ![Fragments curve toward the center](docs/gifs/preset-orbital-ribbons.gif) |

Tune particle density, gravity, spin, release order, waves, size variation and
burst origin. [Compare those controls](docs/catalog.md#one-control-at-a-time).
These clips use Studio's real shaders with synthetic window content.

### More fragment shapes

**Triangle Shatter**, **Circle Burst**, **Rectangle Confetti** and **Hex Swarm**
combine new geometry with the existing gravity and spin controls. Studio also
supports ellipses, diamonds and stars, with adjustable proportions, orientation
and silhouette timing. Available since v0.12.0; resize stays off.

| Triangle Shatter | Circle Burst |
| --- | --- |
| ![Triangular fragments scatter and reassemble](docs/gifs/preset-triangle-shatter.gif) | ![Circular fragments burst outward and reconstruct](docs/gifs/preset-circle-burst.gif) |
| **Rectangle Confetti** | **Hex Swarm** |
| ![Rectangular fragments tumble with downward gravity](docs/gifs/preset-rectangle-confetti.gif) | ![Hexagonal pieces spread and return](docs/gifs/preset-hex-swarm.gif) |

[Shape controls and comparisons](docs/fragment-shapes.md) ·
[Try Triangle Shatter](https://jturbide.github.io/niri-fx/gallery/#preset-triangle-shatter)

The [experimental compositor](experimental/README.md) also uses these shapes for
native movement and swaps:

| Triangle swap | Hexagon swap |
| --- | --- |
| ![Two windows exchange positions with triangular pieces](docs/gifs/native-swap-triangle-shatter.gif) | ![Two windows exchange positions with hexagonal pieces](docs/gifs/native-swap-hex-swarm.gif) |

### Mixed fragment shapes

Choose **Mixed Confetti** for tumbling squares and triangles, or **Orbiting Shapes**
for circles and hexagons. Tune the second shape, mixture and stable layout seed.

| Mixed Confetti | Orbiting Shapes |
| --- | --- |
| ![Squares and triangles tumble together](docs/gifs/preset-mixed-confetti.gif) | ![Circles and hexagons orbit together](docs/gifs/preset-orbiting-shapes.gif) |

[Shape mixtures and settings](docs/fragment-shapes.md#mix-two-shapes) ·
[Controlled comparison](docs/gifs/compare-fragment-mixture.gif)

### Coordinated action sets

Choose **Fragments Motion**, **Ribbons Motion** or **Elastic Motion** for matching
opening, closing and desktop timing. Studio suggests a companion when you view
Resize or Movement; choose the companion to include it in your profile.

| Fragments Motion | Ribbons Motion | Elastic Motion |
| --- | --- | --- |
| ![Mixed pieces arrive and orbit away](docs/gifs/profile-fragments-motion.gif) | ![Ribbons wave in and zipper shut](docs/gifs/profile-ribbons-motion.gif) | ![A springy arrival and rubber-sheet exit](docs/gifs/profile-elastic-motion.gif) |
| **Edge rebuild** | **Ribbon resize** | **Spring resize** |
| ![Mixed fragments rebuild a resized edge](docs/gifs/fragments-motion-resize.gif) | ![Ribbons wave during resize](docs/gifs/ribbons-motion-resize.gif) | ![Elastic resize settles gently](docs/gifs/elastic-motion-resize.gif) |
| **Experimental fragment swap** | **Experimental ribbon swap** | **Experimental elastic swap** |
| ![Two windows swap with mixed fragments](docs/gifs/native-swap-fragments-motion.gif) | ![Two windows swap with flowing ribbons](docs/gifs/native-swap-ribbons-motion.gif) | ![Two windows glide into exchanged positions](docs/gifs/native-swap-elastic-motion.gif) |

The first two rows use real shaders with synthetic content. Swaps are native
nested-compositor recordings and require the experimental build.
[Build a combo from an action set](docs/action-sets.md) ·
[Browse coordinated sets](https://jturbide.github.io/niri-fx/gallery/?collection=action-sets)

### Coordinated desktop motion

**Gentle**, **Balanced** and **Playful** pair window effects with stock workspace,
camera and overview springs.

| Gentle | Balanced | Playful |
| --- | --- | --- |
| ![Gentle desktop motion](docs/gifs/stock-gentle-motion.gif) | ![Balanced desktop motion](docs/gifs/stock-balanced-motion.gif) | ![Playful desktop motion](docs/gifs/stock-playful-motion.gif) |

[Try a motion pack](docs/desktop-motion.md) · [Browse desktop profiles](https://jturbide.github.io/niri-fx/gallery/?collection=desktop)

### Finished pairings

Choose a coordinated opening and closing look by name; detailed tuning is optional.

| Geometric Flow | Ribbon Current | Soft Landing |
| --- | --- | --- |
| ![Triangles assemble and hexagons drift away](docs/gifs/profile-geometric-flow.gif) | ![Waving ribbons arrive and alternating strips leave](docs/gifs/profile-ribbon-current.gif) | ![A gentle elastic arrival and a frosted exit](docs/gifs/profile-soft-landing.gif) |

[Browse all sixteen profiles](docs/profiles.md) · [Choose by collection](docs/collections.md)

### Slices, springs and hexagons

| Alternating Blinds | Spring Wobble | Hexagon Burst |
| --- | --- | --- |
| ![Alternating strips slide apart](docs/gifs/preset-alternating-blinds.gif) | ![A springy whole-window wobble](docs/gifs/preset-spring-wobble.gif) | ![Spinning hexagonal tiles burst outward](docs/gifs/preset-hexagon-burst.gif) |
| **Ribbon Fold** | **Twist Snap** | **Hive Collapse** |
| ![Ribbons rotate and fold](docs/gifs/preset-ribbon-fold.gif) | ![A window twists and settles](docs/gifs/preset-twist-snap.gif) | ![Hexagonal tiles collapse inward](docs/gifs/preset-hive-collapse.gif) |

### Pointer-driven wobble prototype

Grab a window, change direction and let it settle. The pointer extension
adds actual drag response to the isolated experimental compositor. It is available
from source; Studio's timed Elastic effects remain separate.
Choose **Pointer drag** in Library to save a preset or tune its strength, damping
and frequency. Use **Try pointer drag** to drag the sample window, or **Play drag
demo** for a repeatable comparison. **Preview combo** includes dragging when
pointer strength is above zero. These browser previews use native spring and shader math with
synthetic input; they work online without changing your desktop.
Portable JSON retains the choice on every setup. Live activation
requires the verified experimental compositor and an explicit standalone Apply.

| Gentle | Rubber Sheet | Release Settle |
| --- | --- | --- |
| ![A firm, subtle pointer-driven bend](docs/gifs/native-pointer-gentle.gif) | ![A softer window bends with the pointer and rebounds](docs/gifs/native-pointer-rubber-sheet.gif) | ![A dragged window settles after release](docs/gifs/native-pointer-release-settle.gif) |

These recordings use real pointer events and synthetic windows in nested Niri.
[Try the prototype and its three presets](docs/pointer-wobble.md).

These complete Studio combos pair Fragment Flow with each drag preset. Import
the [portable examples](examples/profiles/README.md#pointer-preview-combos) to try
them online or in version 0.18 and newer. The source archive includes the examples.

| Gentle Fragments | Rubber Sheet Fragments | Release Settle Fragments |
| --- | --- | --- |
| ![Fragment opening, gentle drag and fragment closing in Studio](docs/gifs/pointer-preview-gentle.gif) | ![Fragment opening, rubber sheet drag and fragment closing in Studio](docs/gifs/pointer-preview-rubber-sheet.gif) | ![Fragment opening, spring settling and fragment closing in Studio](docs/gifs/pointer-preview-release-settle.gif) |

### Pixels, ink and distortion

| Pixel Wipe | Ink Spread | Signal Glitch |
| --- | --- | --- |
| ![A pixel grid wipes away](docs/gifs/preset-pixel-wipe.gif) | ![Dark ink spreads through a window](docs/gifs/preset-ink-spread.gif) | ![Horizontal signal distortion](docs/gifs/preset-signal-glitch.gif) |
| **Frost Vanish** | **Ink Bloom** | **Chromatic Glitch** |
| ![A cool frost edge dissolves a window](docs/gifs/preset-frost-vanish.gif) | ![A pale ink reveal grows from an offset origin](docs/gifs/preset-ink-bloom.gif) | ![Signal distortion with color separation](docs/gifs/preset-chromatic-glitch.gif) |

Also explore [dust, wisps, iris reveals and shockwaves](docs/catalog.md).
Ember Erosion and Signal Glitch start monochrome; their colors are configurable.
Original NiriFX shaders are inspired by the wider [desktop-effects community](docs/related-projects.md).

### Vortex distortion

**Vortex Fold** curls the window into its center; **Soft Swirl** gives it a quicker,
gentler counterclockwise turn. Change twist direction, contraction, falloff and
origin in Studio. Available since v0.11.0.

| Vortex Fold | Soft Swirl |
| --- | --- |
| ![The window curls inward and unwinds intact](docs/gifs/preset-vortex-fold.gif) | ![A gentle counterclockwise warp fades and returns](docs/gifs/preset-soft-swirl.gif) |

[Compare spin directions](docs/gifs/compare-vortex-twist.gif) ·
[Controls and settings](docs/catalog.md#vortex-and-swirl)

## Pick an opening and closing pair

Choose a finished combination with no JSON editing. In the terminal guide, type
`profiles`; in Studio, start with **Library** and **Preview combo**. The desktop pickers
include the same collection. Resize stays off.

The five recommended combos balance arrival and departure timing. Resize and
movement stay off until selected. These clips show the complete shader cycle with
synthetic window content.

| Fragment Flow | Geometric Flow | Soft Landing |
| --- | --- | --- |
| ![Fragments assemble and collapse inward](docs/gifs/profile-fragment-flow.gif) | ![Triangles assemble and hexagons drift away](docs/gifs/profile-geometric-flow.gif) | ![A gentle arrival with a frosted departure](docs/gifs/profile-soft-landing.gif) |
| **Ribbon Current** | **Playful Motion** | **Burst and Drift** |
| ![Waving ribbons arrive and alternating strips leave](docs/gifs/profile-ribbon-current.gif) | ![Springy arrival and a light fragment departure](docs/gifs/profile-playful-motion.gif) | ![Explosion opening with drifting pixel dust on close](docs/gifs/profile-burst-and-drift.gif) |

```sh
python3 -m niri_fx list --profiles --text
python3 -m niri_fx studio --profile fragment-flow
```

[All 16 profiles, commands and downloads](docs/profiles.md) ·
[Ghost and Shockwave](docs/gifs/profile-ghost-and-shockwave.gif)

## Resize

Choose fragment breakup, **Elastic Stretch**, **Accordion Resize**, **Ripple
Resize**, **Edge Ripple** or **Torsion Resize**. These work on stock Niri's animated size changes, such as cycling column
widths. They do not add pointer-driven wobble while dragging an edge.

![Elastic stretch, accordion folds and radial ripples compared](docs/gifs/compare-resize-families.gif)

[Resize guide](docs/resize.md) · [Elastic profile](examples/profiles/elastic-resize.json) ·
[Accordion profile](examples/profiles/accordion-resize.json) ·
[Ripple profile](examples/profiles/ripple-resize.json)

**Edge Ripple** and **Torsion Resize** each offer Subtle and Expressive profiles
since v0.11.0. Compare both strengths below, then download a
profile from the [resize guide](docs/resize.md#edge-ripple-and-torsion-resize).

| Edge Ripple | Torsion Resize |
| --- | --- |
| ![Subtle and expressive edge ripple resize](docs/gifs/compare-edge-ripple-resize.gif) | ![Subtle and expressive torsion resize](docs/gifs/compare-torsion-resize.gif) |


## Experimental movement and swaps

These recordings run in a **separate, patched Niri instance** with synthetic app
cards. The standard installation does not replace your compositor.

| Fragment explosion | Slice Exchange |
| --- | --- |
| ![Two windows swap through an explosion](docs/gifs/native-swap.gif) | ![Alternating strips exchange columns](docs/gifs/native-swap-slice-exchange.gif) |
| **Pixel Transfer** | **Soft Phase** |
| ![Pixel grains transfer during a swap](docs/gifs/native-swap-pixel-transfer.gif) | ![A soft wave follows a column swap](docs/gifs/native-swap-soft-phase.gif) |

Repeated swaps preserve the current deformation and seed, with blended direction
changes. Closing during an opening continues its original trajectory while fading
out. Closing during movement retains the movement state instead of creating a new
particle field.

| Redirect a moving window | Close during opening |
| --- | --- |
| ![Repeated swaps keep their deformation](docs/gifs/native-interrupted.gif) | ![Opening particles continue their path as the window closes](docs/gifs/native-close-during-open.gif) |

Eight quick direction changes, carrying the wobble through each retarget:

![Wobble continues through eight rapid reversals](docs/gifs/native-rapid-reversals.gif)

[Run the nested demo](experimental/README.md) · [Movement behavior and limits](docs/movement.md) ·
[All native swaps and interruption recordings](docs/showcases.md#resize-movement-and-swaps)

The windows still render independently; particles do not share collision physics
or one combined depth order. Studio now previews the actual movement shader on a
synthetic directional path; its older Move/Swap sketches remain labelled concepts.

### Movement beyond horizontal swaps

Fragment Wake, Ribbon Transfer and Momentum Glide provide three movement looks.
The patched compositor also handles vertical reorder and consume/expel animation
paths. The [pointer extension](docs/pointer-wobble.md) adds drag response; custom
workspace effects remain on the [roadmap](ROADMAP.md).

| Fragment Wake | Ribbon Transfer | Momentum Glide |
| --- | --- | --- |
| ![Triangle wake](docs/gifs/native-swap-fragment-wake.gif) | ![Alternating ribbons](docs/gifs/native-swap-ribbon-transfer.gif) | ![Gentle elastic movement](docs/gifs/native-swap-momentum-glide.gif) |

![Consume, vertical reorder and expel](docs/gifs/native-rearrangement.gif)

[Controls, profile export and isolated demos](docs/movement.md#movement-presets-and-general-rearrangement)

### Shaped resize

Use triangles, hexagons and other fragment shapes during resize with these
ready-made profiles.

| Triangle Edge Rebuild | Hexagon Edge Rebuild | Circle Soft Reflow |
| --- | --- | --- |
| ![Triangle resize](docs/gifs/triangle-edge-rebuild.gif) | ![Hexagon resize](docs/gifs/hexagon-edge-rebuild.gif) | ![Circle resize](docs/gifs/circle-soft-reflow.gif) |

[Importable profiles and resize controls](docs/resize.md#shaped-resize)

## Make it yours

Open `niri-fx studio` to choose a finished look in **Library**. Choose opening
and closing styles, then add resize, Move / swap or pointer settings to your
combo. **Customize in Studio** opens detailed tuning in the same app.

![Choose effects and build a combo](docs/gifs/workflow-library.gif)

The installed app provides reviewed **Apply** and **Restore previous** through
standalone, iNiR/iRiS or connected Noctalia configuration. The same library works
in [Web Studio](https://jturbide.github.io/niri-fx/studio/) for previews and JSON/config
downloads. [Library and shell setup](docs/library.md).
My profiles keeps saved combos together, with copy, rename and remove controls.
Saving over a name asks you to replace that Library copy; active effects change
only through Review & apply.

Studio offers a **Basic / Advanced** control view, search and favorites, independent
action profiles, Undo/Redo and pinned A/B comparisons. **Preview combo** plays
opening, a pause, selected resize/movement loops and closing using each action's
style and timing. Pause or scrub individual action previews;
Reduced Motion shows endpoints without playback and respects the system preference.
Preview preferences do not change exported effects.

Import one of the [JSON examples](examples/README.md), edit it and export a preset
or Niri config. [Studio guide](docs/usage.md) · [Profiles](docs/profiles.md) ·
[Control reference](docs/effect-controls.md).

## Desktop pickers

Prefer your terminal? `niri-fx` provides preset search, reviewed Apply and Undo
without a graphical toolkit. [Guided workflow](docs/terminal.md):

![Terminal preset selection, reviewed Apply and Undo](docs/gifs/workflow-terminal.gif)

Run `python3 -m niri_fx picker` from the checkout to browse styles and load JSON
profiles. Review the affected files before Apply; Undo restores the previous
settings. Custom resize effects require explicit consent. Choose a toolkit:

| Toolkit | Command from a checkout | Integration guide |
| --- | --- | --- |
| Quickshell | `python3 -m niri_fx picker` | [Reusable QML picker](docs/quickshell.md) |
| GTK 4 / GJS | `python3 -m niri_fx picker --toolkit gtk` | [Standalone GTK and AGS 3 example](docs/gtk.md) |

Both provide reusable components for custom settings pages.

![Quickshell picker search, reviewed Apply and Undo](docs/gifs/workflow-quickshell-picker.gif)

![GTK picker search, reviewed Apply and Undo](docs/gifs/workflow-gtk-picker.gif)

Only the chosen UI's toolkit is needed; the GTK picker also works without AGS.
Studio and standalone setup remain independent of both toolkits.
Available since v0.9.0; built-in open/close pairings require v0.10.0.

## Performance and compatibility

Effect cost depends on the renderer, window size and settings. The
[performance guide](docs/performance.md) includes reproducible shader benchmarks;
the [validation record](docs/validation.md) describes native tests and remaining
hardware limits. Particle count is a visual control, not a universal quality setting.
The [fragment optimization results](docs/performance.md#varied-fragment-flight-bounds)
compare shader costs while keeping the same particles and motion.

| Feature | Requirement |
| --- | --- |
| Open/close, nine families | Stock Niri with animations enabled |
| Resize, four families | Stock Niri; explicit checkbox, profile slot or `--resize` |
| Native movement and interruption continuity | Pinned experimental Niri build |
| iNiR/iRiS, DMS, Noctalia pickers | Optional [shell integrations](docs/compatibility.md) |
| Waybar or another bar on Niri | Standalone path; no effects plugin needed |

## Built with and connected to

Built for [niri](https://github.com/niri-wm/niri) with Python, GLSL and WebGL.
Shell adapters share the same effect catalog and CLI. Explore the
[related projects](docs/related-projects.md), [integration roadmap](docs/roadmap.md)
and [brand assets](docs/branding.md).

## Help and contributing

[Open an issue](https://github.com/jturbide/niri-fx/issues) with your Niri version,
effect settings and steps to reproduce a problem. Remove personal information
from logs and recordings. See [security reporting](SECURITY.md) for vulnerabilities.

Contributions are welcome: presets, documentation, hardware results and code.
[Contributing](CONTRIBUTING.md) explains the checks and review process;
[ROADMAP.md](ROADMAP.md) describes the next priorities.

## License

Original code, shaders and sample artwork are [MIT licensed](LICENSE).
The optional Niri patches and derived browser pointer preview use
**GPL-3.0-or-later**, with [their license](experimental/COPYING-NIRI).
See [third-party notices](THIRD_PARTY.md). NiriFX is independent and is not affiliated
with Niri, iNiR, DMS or Noctalia.
