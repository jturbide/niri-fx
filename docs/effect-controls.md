# Shapes, hinges, waves and wobble

These controls are included in **0.7.0**. Earlier packages contain a smaller
selection. All built-ins leave resize disabled.

## Fragments

Ordinary fragments use a compact renderer. Effects use a separate renderer when size variation, direction variation or a travelling wave
is nonzero. Set all three to zero to return to the compact renderer.

| Control / CLI flag | Meaning |
| --- | --- |
| Extra piece shrink / `--fragment-shrink` | 0–1. Adds up to 85% scale reduction during flight on top of the ordinary dissolution. |
| Rounded corners / `--fragment-roundness` | 0–1. Corners round after release; 1 turns square pieces into discs. Unequal cells become rounded rectangles. Endpoints remain intact. |
| Spatial release / `--release` | Adds `center`, `edges`, `diagonal` and `checkerboard` to the directional sequences. Center/edges use the configured burst origin; checkerboard alternates two groups in a 6×6 spatial partition. `--wave-span` controls their separation. |
| Unequal piece sizes / `--size-variation` | 0–1. Jitters shared grid boundaries, creating rectangular pieces without missing texture between cells. Zero retains square tiles. |
| Direction variation / `--direction-variation` | 0–1. Rotates each of three seeded motion bands by up to ±180°. Existing dispersion adds independent per-piece path variation. |
| Wave strength / `--wave-strength` | 0–1. Bends the field of rigid pieces along a sinusoidal path. |
| Wave frequency / `--wave-frequency` | 0.25–4 spatial cycles. Lower values produce broader waves. |
| Wave speed / `--wave-speed` | 0–4 temporal cycles over the animation. Zero freezes phase while the wave's amplitude still grows and fades. |

Shared boundaries move at most 20% of a cell, so individual widths/heights range
from 60% to 140% of the nominal size. Particle count remains a target. Randomness
is fixed within an animation; **New variation** changes the seed in Studio.
Niri supplies a fresh seed for each animation.

**Tidal Fragments** makes a broad wave; **Mosaic Burst** emphasizes unequal pieces;
**Chaotic Confetti** mixes tumbling fragments and varied paths; **Crosswind** sweeps
sideways; **Orbital Ribbons** combines waves with an inward orbit.

```sh
python3 -m niri_fx preview --preset crosswind --output /tmp/crosswind.html
python3 -m niri_fx render --preset balanced --size-variation 0.8 \
  --wave-strength 0.7 --wave-frequency 0.5 --wave-speed 1.5 > /tmp/waves.kdl
```

Shape and shrink work in both fragment renderers without increasing their
candidate search radius. Try **Pixel Dust**, **Bubble Burst**, **Core Detonation**
and **Checker Scatter**. The Canvas move/swap concepts approximate these controls;
only the native experiment uses the actual movement shader.

A travelling wave changes pieces' paths. The existing **release direction / wave
span** controls instead delay three sections' departure. They can be combined.
The new controls affect opening, closing and the separate movement experiment;
**they do not change the resize shader**.

## Slices

**Slide Apart now alternates adjacent horizontal strips left and right.**
**Split Curtain** retains the former outward split. Choose the direction explicitly when tuning a custom style.

| Control / CLI flag | Meaning |
| --- | --- |
| Hinge position / `--slice-pivot` | −1–1 along the strip's tangent: first end, center, other end. Requires nonzero rotation to make the hinge visible. Diagonal strips use the window's projected extent. |
| Width collapse / `--slice-collapse` | 0–1. Compresses the strip perpendicular to its length during flight. A positive scale floor keeps the inverse transform finite. |
| Direction / `--slice-direction` | `outward`, `alternate`, `positive`, `negative`, or `random`. Random chooses each strip independently, so neither half nor the total is forced to split evenly. |
| Release order / `--slice-order` | `forward`, `reverse`, `center`, `edges`, `random`, or `together`. Together ignores stagger. |
| Unequal sizes / `--size-variation` | Jitters shared strip boundaries by up to 45% of a strip, preserving a complete texture partition. |
| Direction variation / `--direction-variation` | Adds a seeded angular offset per strip to its selected heading. |
| Travel variation / `--slice-travel-variation` | 0–1. Independent variation of distance; 0.1 preserves the old distance jitter. |
| Rotation variation / `--slice-rotation-variation` | 0–1. Varies the configured strip rotation, including its sign. Has no effect when strip rotation is zero. |
| Wave strength / frequency / speed | Same units as Fragments; moves strips transversely to their travel. |

**Ribbon Wave** uses alternating strips along a broad wave; **Shuffled Slats**
combines random direction/order, unequal sizes and spin; **Venetian Sweep** sends
vertical strips away from a center-first release. Count, angle, distance and
rotation remain independently adjustable. Slices supports stock open/close only.

```sh
python3 -m niri_fx preview --preset ribbon-wave --output /tmp/ribbons.html
python3 -m niri_fx render --preset slide-apart --slice-direction random \
  --slice-order edges --size-variation 0.8 --wave-strength 0.6 > /tmp/slats.kdl
```

**Hinged Fan**, **Venetian Shutter**, **Ribbon Fold** and **Zipper** combine
hinges, width collapse and release order. These are 2D affine strip transforms,
not perspective or 3D folding.

## Elastic: a Compiz-inspired wobble

![Elastic controls in NiriFX Studio](studio-elastic.png)

**Spring Wobble**, **Rubber Band** and **Jelly** bend the whole window texture,
with spring oscillation and settling. They use stock Niri open/close shaders;
movement and column swaps require the [patched compositor](../experimental/README.md).
Native movement keeps the window opaque while it bends and returns intact.

| Control / CLI flag | Range |
| --- | --- |
| Strength / `--elastic-strength` | 0–1 deformation |
| Frequency / `--elastic-frequency` | 1–5 oscillation cycles |
| Damping / `--elastic-damping` | 0–8; higher values settle earlier |
| Axis / `--elastic-axis` | `both`, `horizontal`, `vertical`; applies to the shear bend |
| Spring twist / `--elastic-twist` | −90–90° signed rotation amplitude; rotates in logical pixels to respect aspect ratio |
| Extra stretching / `--elastic-stretch` | 0–1 additional stretch/compression; strength also scales stretching |
| Spatial bend frequency / `--elastic-ripple` | 0.5–4× the basic bend's spatial frequency; separate from temporal spring oscillations |
| Transform origin / `--elastic-anchor` | `center`, four edges, or `top-left`, `top-right`, `bottom-left`, `bottom-right`; affects rotation, stretch and collapse, not a pinned edge |

```sh
python3 -m niri_fx preview --preset spring-wobble --output /tmp/wobble.html
python3 scripts/nested-demo.py --preset spring-wobble --duration-ms 1200
```

Try **Twist Snap**, **Flag Wave**, **Corner Spring** and **Accordion**. The new
controls also drive actual native movement. Two sequential shear inverses and
positive scales keep the warp invertible, including maximum ripple/strength;
the effect is not a cloth simulation.

The second command requires the experimental build. This is a timed shader
animation, **not Compiz's interactive spring mesh attached to the pointer**.
Direct dragging and resize wobble are not implemented. Studio disables the
unsupported Resize/Move/Swap concept tabs for this family; the native swap GIF is
an actual nested compositor recording. Elastic does not use a random seed.

## Saved presets and rendering cost

All families use **schema 3**. Older formats and command aliases have been removed.
Omitted parameters use current defaults, and resize stays off unless explicitly
requested. See the [update policy](upgrading.md).

The varied fragment renderer checks up to **147 candidate cells per output pixel**,
or **441** with staged release. The compact renderer uses 27/81. These are
bounded lookup counts, not benchmark results. Slices checks up to its configured
2–48 strips; Elastic uses a whole-window warp without particle searches. Window
area and expanded drawing bounds matter, and fewer particles alone do not
necessarily make a shader faster. See [validation limits](validation.md).

## Dissolve

Noise Dissolve erodes the texture without moving its contents. Ember Erosion and
Frost Vanish add a colored edge and a directional bias. These are procedural masks,
not simulated flames or ice. All preserve the source texture's premultiplied alpha.

| CLI flag | Range / meaning |
| --- | --- |
| `--dissolve-scale` | 4–160 logical pixels; noise cell size |
| `--dissolve-softness` | 0.005–0.25; feathering around the erosion boundary |
| `--dissolve-direction` | none, left, right, up, down, center; starting region |
| `--dissolve-bias` | 0–1; blend from noise order toward directional order |
| `--edge-width` | 0–0.3; colored boundary width; zero disables it |
| `--edge-hue` | 0–360 degrees around the hue wheel |

## Iris

Iris Bloom closes inward. Portal Out expands a hole instead. Diamond Turn rotates
the reveal mask; the window texture itself remains stationary. Distances use
logical pixels to preserve shape proportions on wide or tall windows.

| CLI flag | Range / meaning |
| --- | --- |
| `--iris-shape` | circle, diamond, square |
| `--iris-direction` | inward or outward during closing; opening reverses it |
| `--iris-softness` | 0.005–0.3; feathered mask edge |
| `--iris-twist` | −180–180 degrees of mask rotation; visible on non-circular shapes |
| `--iris-x`, `--iris-y` | 0–1; reveal origin within the window |

Both families support stock opening and closing only. Use an independent
[profile](profiles.md) to combine them with other families. Neither adds resize
or native movement support. [GPU benchmark scope](performance.md).
