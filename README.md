# NiriFX

![NiriFX — window effects for niri](docs/assets/nirifx-banner.svg)

**Explode windows into fragments. Slide them into ribbons. Make them wobble.**

NiriFX brings customizable animations to the **niri Wayland compositor**.
Choose from **64 presets across nine effect families**, then tune them in the
Studio, online or on your desktop. Use different effects for opening and closing, from a quiet ripple
to a full window explosion.

Works **standalone** or with **iNiR/iRiS, DankMaterialShell and Noctalia**.
Quickshell is optional. Studio opens as an app-style window or a browser tab.

[Interactive gallery](https://jturbide.github.io/niri-fx/gallery/) ·
[Web Studio](https://jturbide.github.io/niri-fx/studio/) ·
[All presets & comparisons](docs/catalog.md) · [Documentation](docs/README.md) ·
[Roadmap](ROADMAP.md) · [Changelog](CHANGELOG.md)

Opening, closing and optional resize work on **stock Niri**, tested with 26.04.
Resize is **off in every built-in preset**. Native movement, swaps and the
interruption improvements require the [experimental compositor](experimental/README.md).

This README describes `main`, which can include features newer than the latest
release. See [choosing a version](docs/releases.md).

## Quick start

**Try without installing:** open [Web Studio](https://jturbide.github.io/niri-fx/studio/),
or choose **Try in Studio** from the [gallery](https://jturbide.github.io/niri-fx/gallery/).
Tune an effect, share its settings or download JSON. Previewing does not change your desktop.
[Bring a downloaded style to Niri](docs/web-studio.md).

Linux, Python 3.10+ and a WebGL browser are enough to try Studio:

```sh
git clone https://github.com/jturbide/niri-fx.git
cd niri-fx
python3 -m niri_fx studio --target standalone
```

Previewing changes no active animations. To install Balanced on plain Niri,
review the plan, then apply it:

```sh
python3 -m niri_fx setup --target standalone --preset balanced
python3 -m niri_fx setup --target standalone --preset balanced --apply
```

Already using a shell's animation picker? Follow its guide:
[iNiR / iRiS](docs/getting-started.md#inir-and-iris) · [DMS](docs/dms.md) ·
[Noctalia](docs/noctalia.md) · [Standalone / Waybar](docs/standalone.md).
The [scenario guide](docs/scenarios.md) helps choose the right setup and restore path.

## See it in motion

The [interactive gallery](https://jturbide.github.io/niri-fx/gallery/) has search,
family/scenario filters and click-to-play previews. It starts paused and loads one
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

### Slices, springs and hexagons

| Alternating Blinds | Spring Wobble | Hexagon Burst |
| --- | --- | --- |
| ![Alternating strips slide apart](docs/gifs/preset-alternating-blinds.gif) | ![A springy whole-window wobble](docs/gifs/preset-spring-wobble.gif) | ![Spinning hexagonal tiles burst outward](docs/gifs/preset-hexagon-burst.gif) |
| **Ribbon Fold** | **Twist Snap** | **Hive Collapse** |
| ![Ribbons rotate and fold](docs/gifs/preset-ribbon-fold.gif) | ![A window twists and settles](docs/gifs/preset-twist-snap.gif) | ![Hexagonal tiles collapse inward](docs/gifs/preset-hive-collapse.gif) |

### Pixels, ink and distortion

| Pixel Wipe | Ink Spread | Signal Glitch |
| --- | --- | --- |
| ![A pixel grid wipes away](docs/gifs/preset-pixel-wipe.gif) | ![Dark ink spreads through a window](docs/gifs/preset-ink-spread.gif) | ![Horizontal signal distortion](docs/gifs/preset-signal-glitch.gif) |
| **Frost Vanish** | **Ink Bloom** | **Chromatic Glitch** |
| ![A cool frost edge dissolves a window](docs/gifs/preset-frost-vanish.gif) | ![A pale ink reveal grows from an offset origin](docs/gifs/preset-ink-bloom.gif) | ![Signal distortion with color separation](docs/gifs/preset-chromatic-glitch.gif) |

Also explore [dust, wisps, iris reveals and shockwaves](docs/catalog.md).
Ember Erosion and Signal Glitch start monochrome; their colors are configurable.
Original NiriFX shaders are inspired by the wider [desktop-effects community](docs/related-projects.md).

## Resize — opt-in

Choose fragment breakup, **Elastic Stretch**, **Accordion Resize** or **Ripple
Resize**. These work on stock Niri's animated size changes, such as cycling column
widths. They do not add pointer-driven wobble while dragging an edge.

![Elastic stretch, accordion folds and radial ripples compared](docs/gifs/compare-resize-families.gif)

[Resize guide](docs/resize.md) · [Elastic profile](examples/profiles/elastic-resize.json) ·
[Accordion profile](examples/profiles/accordion-resize.json) ·
[Ripple profile](examples/profiles/ripple-resize.json)

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
or one combined depth order. Studio's Move/Swap tabs are labelled concept previews.

## Make it yours

Studio offers a **Basic / Advanced** control view, search and favorites, independent
action profiles, Undo/Redo and pinned A/B comparisons. Pause or scrub any preview;
Reduced Motion shows endpoints without playback and respects the system preference.
Preview preferences do not change exported effects.

Import one of the [JSON examples](examples/README.md), edit it and export a preset
or Niri config. [Studio guide](docs/usage.md) · [Profiles](docs/profiles.md) ·
[Control reference](docs/effect-controls.md).

## A desktop picker for Quickshell

Run `python3 -m niri_fx picker` from the checkout to browse styles and load JSON
profiles. Review the affected files before Apply; Undo restores the previous
settings. Resize requires explicit consent. The controller and view can also
be embedded in a custom Quickshell settings page.

![Quickshell picker search, reviewed Apply and Undo](docs/gifs/workflow-quickshell-picker.gif)

[Picker guide and embedding example](docs/quickshell.md). Requires Quickshell;
Studio and standalone setup remain independent of it. Available on `main` after v0.8.0.

## Performance and compatibility

Effect cost depends on the renderer, window size and settings. The
[performance guide](docs/performance.md) includes reproducible shader benchmarks;
the [validation record](docs/validation.md) describes native tests and remaining
hardware limits. Particle count is a visual control, not a universal quality setting.

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
The optional Niri patch is **GPL-3.0-or-later**, with [its license](experimental/COPYING-NIRI).
See [third-party notices](THIRD_PARTY.md). NiriFX is independent and is not affiliated
with Niri, iNiR, DMS or Noctalia.
