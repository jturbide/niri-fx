# Waves, variation and wobble

These additions are in the **development checkout after 0.6.0**. The published
0.6.0 package has the earlier Fragments and Slices controls. Use the current
checkout for the examples below; all built-ins still leave resize disabled.

## Fragments

Ordinary fragments use a compact renderer. Effects use a separate renderer when size variation, direction variation or a travelling wave
is nonzero. Set all three to zero to return to the compact renderer.

| Control / CLI flag | Meaning |
| --- | --- |
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

A travelling wave changes pieces' paths. The existing **release direction / wave
span** controls instead delay three sections' departure. They can be combined.
The new controls affect opening, closing and the separate movement experiment;
**they do not change the resize shader**.

## Slices

**Slide Apart now alternates adjacent horizontal strips left and right.**
**Split Curtain** retains the former outward split. Choose the direction explicitly when tuning a custom style.

| Control / CLI flag | Meaning |
| --- | --- |
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
| Axis / `--elastic-axis` | `both`, `horizontal`, `vertical` |

```sh
python3 -m niri_fx preview --preset spring-wobble --output /tmp/wobble.html
python3 scripts/nested-demo.py --preset spring-wobble --duration-ms 1200
```

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
or **441** with directional release. The compact renderer uses 27/81. These are
bounded lookup counts, not benchmark results. Slices checks up to its configured
2–48 strips; Elastic uses a whole-window warp without particle searches. Window
area and expanded drawing bounds matter, and fewer particles alone do not
necessarily make a shader faster. See [validation limits](validation.md).
