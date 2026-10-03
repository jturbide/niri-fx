# Niri Fragments

**Explode windows into pixels. Pull them back together.**

Niri Fragments gives application windows textured particle animations: outward
bursts, inward collapses, gravity, orbit and rotation. Choose from 11 presets or
build your own in Fragments Studio. Niri renders the effects; the optional
iNiR/iRiS adapter adds them to your existing settings picker.

[Get started](docs/getting-started.md) · [Studio & controls](docs/usage.md) ·
[Compatibility](docs/compatibility.md) · [Changelog](CHANGELOG.md) ·
[Contributing](CONTRIBUTING.md)

**Early prototype · 0.4.1.** Opening and closing work on stock Niri 26.04.
Resize fragments are **off by default and strictly opt-in**. Native move/swap
fragmentation requires the separate experimental Niri patch. Performance and
appearance still need testing across GPUs, applications and display scales.

## See it in motion

Opening and closing use the **Explosion** preset. These are recordings of
Studio's real shader renderer with synthetic content, sampled at 20 fps.

| Open · reconstruct | Close · explode |
| --- | --- |
| ![Opening reconstructs an intact window from fragments](docs/gifs/opening.gif) | ![Closing explodes a window into fragments](docs/gifs/closing.gif) |

**Resize — opt-in, disabled by default.** This uses the actual resize shader.

<img src="docs/gifs/resize.gif" alt="Opt-in resize breaks the window into fragments and reconstructs it at its new size" width="560">

<details>
<summary>Compare all 11 styles — each loop closes and opens</summary>

| Subtle | Balanced | Dramatic |
| --- | --- | --- |
| ![Subtle](docs/gifs/preset-subtle.gif) | ![Balanced](docs/gifs/preset-balanced.gif) | ![Dramatic](docs/gifs/preset-dramatic.gif) |
| **Explosion** | **Implosion** | **Earth** |
| ![Explosion](docs/gifs/preset-explosion.gif) | ![Implosion](docs/gifs/preset-implosion.gif) | ![Earth](docs/gifs/preset-earth.gif) |
| **Black Hole** | **Space** | **Vortex** |
| ![Black Hole](docs/gifs/preset-black-hole.gif) | ![Space](docs/gifs/preset-space.gif) | ![Vortex](docs/gifs/preset-vortex.gif) |
| **Confetti** | **Updraft** | |
| ![Confetti](docs/gifs/preset-confetti.gif) | ![Updraft](docs/gifs/preset-updraft.gif) | |

</details>

<details>
<summary>Experimental movement: native recording and design previews</summary>

**Native column swap — requires the patched Niri build.** These are two real
synthetic demo clients in a nested compositor, not an overlay on the desktop.

![Two real demo windows fragment, exchange columns and reconstruct in patched Niri](docs/gifs/native-swap.gif)

The two clips below are **Studio design concepts**, not recordings of the native
prototype. Their trajectories and particle ordering differ from the current patch.

| Move concept | Swap concept |
| --- | --- |
| ![Studio concept of one fragmented window moving between columns](docs/gifs/move-concept.gif) | ![Studio concept of two fragment streams swapping columns](docs/gifs/swap-concept.gif) |

See [the experimental build and limitations](experimental/README.md).

</details>

[Recording details and reproduction commands](docs/gifs/README.md).

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
with a browser fallback. Export JSON/KDL anywhere, or **Save to iRiS** and then
select your custom style in Settings. Saving does not activate it.

The default Balanced preset targets 720 pieces; Explosion uses 1,200 and
Implosion uses 1,000. Resize stays off until you enable it. The controls and
CLI examples are in the [usage guide](docs/usage.md).

## What works where?

| Feature | Stock Niri | Extra requirement |
| --- | --- | --- |
| Open / close fragments, 11 presets | Yes; validated on 26.04 | Enable Niri animations |
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
