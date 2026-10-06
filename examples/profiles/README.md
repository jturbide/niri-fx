# Importable action profiles

Each profile assigns independent opening and closing effects. All built-in pairings leave
resize and experimental movement unset, preserving the user's existing behavior.
Choose one by name with `--profile`, import its JSON in Studio, or preview it using the commands below. Previewing
and exporting do not activate animations.

The first five entries are Library's recommended complete combos. They refine
the named source styles for coordinated timing, travel and settling. Their JSON
contains the built-in profiles' resolved parameters; the individual presets keep their own
settings. Use **Preview combo** in Library to try the opening and closing sequence
before exporting or applying.

| Profile | Opening | Closing | Showcase |
| --- | --- | --- | --- |
| [Fragment Flow](fragment-flow.json) | Balanced | Implosion | [GIF](../../docs/gifs/profile-fragment-flow.gif) |
| [Soft Landing](soft-landing.json) | Momentum Glide | Frost Vanish | [GIF](../../docs/gifs/profile-soft-landing.gif) |
| [Ribbon Current](ribbon-current.json) | Ribbon Wave | Ribbon Transfer | [GIF](../../docs/gifs/profile-ribbon-current.gif) |
| [Playful Motion](playful-motion.json) | Spring Wobble | Bubble Burst | [GIF](../../docs/gifs/profile-playful-motion.gif) |
| [Geometric Flow](geometric-flow.json) | Triangle Shatter | Hex Swarm | [GIF](../../docs/gifs/profile-geometric-flow.gif) |
| [Burst and Drift](burst-and-drift.json) | Explosion | Dust Drift | [GIF](../../docs/gifs/profile-burst-and-drift.gif) |
| [Frost and Fragments](frost-and-fragments.json) | Frost Vanish | Pixel Dust | [GIF](../../docs/gifs/profile-frost-and-fragments.gif) |
| [Spring and Ember](spring-and-ember.json) | Spring Wobble | Ember Erosion | [GIF](../../docs/gifs/profile-spring-and-ember.gif) |
| [Ghost and Shockwave](ghost-and-shockwave.json) | Ghost Wisps | Shockwave | [GIF](../../docs/gifs/profile-ghost-and-shockwave.gif) |
| [Pixel Shuffle](pixel-shuffle.json) | Pixel Wipe | Pixelate | [GIF](../../docs/gifs/profile-pixel-shuffle.gif) |
| [Ribbon Exit](ribbon-exit.json) | Alternating Blinds | Ribbon Fold | [GIF](../../docs/gifs/profile-ribbon-exit.gif) |

Run from the checkout:

```sh
python3 -m niri_fx preview --profile fragment-flow --output /tmp/fragment-flow.html
python3 -m niri_fx preview --profile pixel-shuffle --output /tmp/pixel-shuffle.html
python3 -m niri_fx preview --profile ribbon-exit --output /tmp/ribbon-exit.html
python3 -m niri_fx preview --custom examples/profiles/burst-and-drift.json --output /tmp/burst-and-drift.html
python3 -m niri_fx preview --custom examples/profiles/frost-and-fragments.json --output /tmp/frost-and-fragments.html
python3 -m niri_fx preview --custom examples/profiles/spring-and-ember.json --output /tmp/spring-and-ember.html
python3 -m niri_fx preview --custom examples/profiles/ghost-and-shockwave.json --output /tmp/ghost-and-shockwave.html
```

Export one profile as stock Niri KDL and check it without applying:

```sh
python3 -m niri_fx render --custom examples/profiles/burst-and-drift.json > /tmp/burst-and-drift.kdl
niri validate -c /tmp/burst-and-drift.kdl
```

To make a new combination, use Library's combo builder, Studio's **Independent action effects** or
`python3 -m niri_fx profile --help`. See the [profile guide](../../docs/profiles.md)
for editing, saving and resize selection; follow [setup and restore](../../docs/setup.md)
when ready to apply a profile.

## Portable continuous-fragment combos

These examples require NiriFX 0.21 or newer. They keep Fragment Flow's opening and closing,
preserve Resize and Swap, and add a square Move material with all 18 response
values. Import one in local, hosted or offline Studio. JSON, My profiles and
share links retain the whole recipe; NiriFX 0.20 cannot import their schema 4.

| Profile | Response |
| --- | --- |
| [Continuous Gentle](continuous-gentle.json) | Short delays, restrained spread and a quick return |
| [Continuous Tear](continuous-tear.json) | A delayed, uneven wave following the grabbed region |
| [Continuous Cascade](continuous-cascade.json) | More pieces, longer delays and stronger separation |
| [Continuous Long Trail](continuous-long-trail.json) | A custom Tear response: 96 batches, 520 ms far delay, 500 ms far catch-up and 32° rotation |

```sh
python3 -m niri_fx studio --custom examples/profiles/continuous-tear.json
python3 -m niri_fx preview --custom examples/profiles/continuous-gentle.json --output /tmp/continuous-gentle.html
python3 -m niri_fx preview --custom examples/profiles/continuous-tear.json --output /tmp/continuous-tear.html
python3 -m niri_fx preview --custom examples/profiles/continuous-cascade.json --output /tmp/continuous-cascade.html
python3 -m niri_fx preview --custom examples/profiles/continuous-long-trail.json --output /tmp/continuous-long-trail.html
python3 -m niri_fx render --custom examples/profiles/continuous-gentle.json > /tmp/continuous-gentle-stock.kdl
niri validate -c /tmp/continuous-gentle-stock.kdl
```

Browser previews show the movement material, not continuous compositor gestures.
Stock Niri receives the opening and closing effects; the native response needs a
verified compatible NiriFX session. Move Off, Preserve or an incompatible
material keeps response values dormant. **Timed movement** removes them.
See [portable response editing](../../docs/profiles.md#portable-fragment-response)
and [native behavior](../../docs/fragment-drag.md).

## Pointer preview combos

These source-checkout examples add the three experimental drag presets to
Fragment Flow. Opening and closing work on stock Niri; pointer deformation
requires the optional compositor extension for live use. Resize and timed
movement stay unset.

| Portable JSON | Studio showcase |
| --- | --- |
| [Gentle Fragments](pointer-preview-gentle.json) | [GIF](../../docs/gifs/pointer-preview-gentle.gif) |
| [Rubber Sheet Fragments](pointer-preview-rubber-sheet.json) | [GIF](../../docs/gifs/pointer-preview-rubber-sheet.gif) |
| [Release Settle Fragments](pointer-preview-release-settle.json) | [GIF](../../docs/gifs/pointer-preview-release-settle.gif) |

Import one into [Web Studio](https://jturbide.github.io/niri-fx/studio/) and choose
**Preview combo**, or use **Try pointer drag** in Library for interactive dragging.
The recordings use native spring/shader math with synthetic input and textures.
They do not measure compositor input, capture behavior or display latency.

```sh
python3 -m niri_fx preview --custom examples/profiles/pointer-preview-gentle.json --output /tmp/pointer-preview-gentle.html
python3 -m niri_fx preview --custom examples/profiles/pointer-preview-rubber-sheet.json --output /tmp/pointer-preview-rubber-sheet.html
python3 -m niri_fx preview --custom examples/profiles/pointer-preview-release-settle.json --output /tmp/pointer-preview-release-settle.html
```

## Resize profiles

These four profiles keep Balanced opening and closing and explicitly enable a
separate resize effect. They require NiriFX 0.11 or newer. See the
[resize guide](../../docs/resize.md) for controls and limitations.

| Profile | Showcase |
| --- | --- |
| [Edge Ripple Subtle](edge-ripple-subtle.json) | [GIF](../../docs/gifs/edge-ripple-subtle.gif) |
| [Edge Ripple Expressive](edge-ripple-expressive.json) | [GIF](../../docs/gifs/edge-ripple-expressive.gif) |
| [Torsion Subtle](torsion-subtle.json) | [GIF](../../docs/gifs/torsion-subtle.gif) |
| [Torsion Expressive](torsion-expressive.json) | [GIF](../../docs/gifs/torsion-expressive.gif) |

```sh
python3 -m niri_fx preview --custom examples/profiles/edge-ripple-subtle.json --output /tmp/edge-ripple-subtle.html
python3 -m niri_fx preview --custom examples/profiles/edge-ripple-expressive.json --output /tmp/edge-ripple-expressive.html
python3 -m niri_fx preview --custom examples/profiles/torsion-subtle.json --output /tmp/torsion-subtle.html
python3 -m niri_fx preview --custom examples/profiles/torsion-expressive.json --output /tmp/torsion-expressive.html
```

## Shaped resize and experimental movement

These examples require NiriFX 0.13 or newer. The resize profiles deliberately
enable resize; the movement profile leaves resize unset and needs the pinned
experimental compositor. None is enabled by importing or previewing it.

| Profile | Action | Showcase |
| --- | --- | --- |
| [Triangle Edge Rebuild](triangle-edge-rebuild.json) | Resize | [GIF](../../docs/gifs/triangle-edge-rebuild.gif) |
| [Hexagon Edge Rebuild](hexagon-edge-rebuild.json) | Resize | [GIF](../../docs/gifs/hexagon-edge-rebuild.gif) |
| [Circle Soft Reflow](circle-soft-reflow.json) | Resize | [GIF](../../docs/gifs/circle-soft-reflow.gif) |
| [Fragment Wake Motion](fragment-wake-motion.json) | Movement | [GIF](../../docs/gifs/native-swap-fragment-wake.gif) |

```sh
python3 -m niri_fx studio --custom examples/profiles/triangle-edge-rebuild.json
python3 -m niri_fx studio --custom examples/profiles/fragment-wake-motion.json
python3 scripts/nested-demo.py --custom examples/profiles/fragment-wake-motion.json
```

The movement shader preview uses a synthetic directional path;
[native recordings](../../docs/movement.md) show compositor-owned trajectories.

![Movement shader preview](../../docs/gifs/movement-fragment-wake.gif)

```sh
python3 -m niri_fx preview --custom examples/profiles/triangle-edge-rebuild.json --output /tmp/triangle-edge-rebuild.html
python3 -m niri_fx preview --custom examples/profiles/hexagon-edge-rebuild.json --output /tmp/hexagon-edge-rebuild.html
python3 -m niri_fx preview --custom examples/profiles/circle-soft-reflow.json --output /tmp/circle-soft-reflow.html
python3 -m niri_fx preview --custom examples/profiles/fragment-wake-motion.json --output /tmp/fragment-wake-motion.html
```

The [desktop motion packs](../../docs/desktop-motion.md) add optional stock springs:
[Gentle](gentle-motion.json), [Balanced](balanced-motion.json) and [Playful](playful-motion.json).
[Movement Overlaps](movement-overlaps.json) deliberately enables resize and experimental movement for the native regression fixture.

```sh
python3 -m niri_fx preview --custom examples/profiles/gentle-motion.json --output /tmp/gentle-motion.html
python3 -m niri_fx preview --custom examples/profiles/balanced-motion.json --output /tmp/balanced-motion.html
python3 -m niri_fx preview --custom examples/profiles/playful-motion.json --output /tmp/playful-motion.html
python3 -m niri_fx preview --custom examples/profiles/movement-overlaps.json --output /tmp/movement-overlaps.html
```

## Coordinated action sets

These NiriFX 0.16 examples include opening, closing and stock desktop timing.
Base versions leave resize and movement unset. Resize versions include resize;
native versions include resize **and** experimental movement. Importing or previewing never activates a style.
[Action-set guide](../../docs/action-sets.md).

| Look | Base JSON | Resize-only JSON | Resize and movement JSON |
| --- | --- | --- | --- |
| Fragments Motion | [Base](fragments-motion.json) | [Resize](fragments-motion-resize.json) | [Native](fragments-motion-native.json) |
| Ribbons Motion | [Base](ribbons-motion.json) | [Resize](ribbons-motion-resize.json) | [Native](ribbons-motion-native.json) |
| Elastic Motion | [Base](elastic-motion.json) | [Resize](elastic-motion-resize.json) | [Native](elastic-motion-native.json) |

Preview any version from the checkout:

```sh
python3 -m niri_fx preview --custom examples/profiles/fragments-motion.json --output /tmp/fragments-motion.html
python3 -m niri_fx preview --custom examples/profiles/fragments-motion-resize.json --output /tmp/fragments-motion-resize.html
python3 -m niri_fx preview --custom examples/profiles/fragments-motion-native.json --output /tmp/fragments-motion-native.html
python3 -m niri_fx preview --custom examples/profiles/ribbons-motion.json --output /tmp/ribbons-motion.html
python3 -m niri_fx preview --custom examples/profiles/ribbons-motion-resize.json --output /tmp/ribbons-motion-resize.html
python3 -m niri_fx preview --custom examples/profiles/ribbons-motion-native.json --output /tmp/ribbons-motion-native.html
python3 -m niri_fx preview --custom examples/profiles/elastic-motion.json --output /tmp/elastic-motion.html
python3 -m niri_fx preview --custom examples/profiles/elastic-motion-resize.json --output /tmp/elastic-motion-resize.html
python3 -m niri_fx preview --custom examples/profiles/elastic-motion-native.json --output /tmp/elastic-motion-native.html
```

The [guide](../../docs/action-sets.md) links all nine recordings and explains
which compositor each action needs.
