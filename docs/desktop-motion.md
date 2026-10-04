# Coordinated desktop motion

Choose a finished pack that pairs window effects with stock Niri workspace,
horizontal camera and overview springs. These are ordinary compositor timing
settings, so they work without the movement patch or a desktop shell.

| Pack | Window effects | Desktop character |
| --- | --- | --- |
| `gentle-motion` | Momentum Glide / Frost Vanish | Slower settling with no spring overshoot |
| `balanced-motion` | Balanced / Implosion | Restrained, responsive motion |
| `playful-motion` | Spring Wobble / Bubble Burst | A small amount of spring overshoot |

| Gentle | Balanced | Playful |
| --- | --- | --- |
| ![Gentle workspace, camera and overview transitions](gifs/stock-gentle-motion.gif) | ![Balanced workspace, camera and overview transitions](gifs/stock-balanced-motion.gif) | ![Playful workspace, camera and overview transitions](gifs/stock-playful-motion.gif) |

These recordings show workspace switching, horizontal scrolling and overview
opening/closing in stock Niri with synthetic clients. They show spring motion;
workspace textures are not fragmented or merged. The window effects have their
own [recordings and settings](presets.md#openclose-pairings).

## Try a pack

```sh
niri-fx list --collection desktop --text
niri-fx studio --profile balanced-motion
# Review the plan, then repeat with --apply to activate:
niri-fx setup --target standalone --profile balanced-motion --no-launcher
# Restore the last setup transaction:
niri-fx restore --apply
```

From a checkout, replace `niri-fx` with `python3 -m niri_fx`. Existing iNiR users
can re-register the collection and choose a pack in their animation picker.
DMS, Noctalia and other adapters use the same profile documents and exported KDL;
follow the [guide for your setup](scenarios.md).

Applying a motion pack intentionally overrides `workspace-switch`,
`horizontal-view-movement` and `overview-open-close`. Ordinary presets and
pairings preserve those timings. Resize and experimental movement stay unset
in all three packs. Saving or previewing a pack does not activate it.

## Customize without another tool

In Studio, enable **Independent action effects** and choose **Desktop timing**.
The selector offers Preserved, Gentle, Balanced and Playful. Canvas previews
show the window shaders; try workspace/camera/overview motion in Niri after a
reviewed Apply. Undo and imported/shareable settings retain the desktop timing.

```sh
niri-fx profile --name 'My desktop motion' \
  --open-preset triangle-shatter --close-preset frost-vanish \
  --desktop-motion gentle > /tmp/my-motion.json
niri-fx render --custom /tmp/my-motion.json > /tmp/my-motion.kdl
niri validate -c /tmp/my-motion.kdl
```

A profile's optional `motion` object has `workspace`, `camera` and `overview`
spring objects. Each accepts `damping_ratio` (0.1–1), integer `stiffness`
(1–10000) and `epsilon` (0.00001–0.01). Lower stiffness settles more slowly;
lower damping adds overshoot. Finished packs avoid excessive bouncing.
Missing spring parameters use 1, 800 and 0.0001 respectively. Omit `motion`
to preserve existing desktop timings. No application rules or pointer hooks
are added. See [action profiles](profiles.md) and [movement support](movement.md)
for the separate experimental window action.
