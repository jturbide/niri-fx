# Pointer-driven wobble

The pointer prototype bends a window around the point where you grab it. The
rest of the surface lags behind your hand, responds when you change direction,
and settles after release. Its spring responds to actual drag events.

This is an **opt-in native experiment**, available from the source checkout.
It requires the separate pointer extension to the pinned Niri build. Stock Niri,
Studio's timed Elastic styles and the 0.17.0 package do not provide this drag hook.
Portable profiles and Studio integration are the next steps on the
[roadmap](../ROADMAP.md#epic-4-pointer-driven-wobble).

## Try it

From a checkout with Niri's build dependencies, a Rust toolchain and Quickshell:

```sh
python3 scripts/build-niri-movement.py --pointer-wobble --release --test
python3 scripts/nested-demo.py --pointer-wobble gentle
```

The demo opens a separate Niri window containing two floating synthetic app cards. Drag a
card by its title bar, reverse direction, then let go. No modifier key is needed.
Floating windows respond immediately. Use **Alt+Q** to close the demo.
The normal login compositor and desktop settings are not replaced.

Tiled windows keep Niri's normal title-bar gesture: start vertically to select
window dragging, then move far enough to lift the window out of its column.
A horizontal gesture can scroll the viewport instead. The pinned build's tile
detachment threshold is 256 logical pixels; the automated checks cover that path.

Choose another look by changing the last argument:

| Preset | Character | Example configuration |
| --- | --- | --- |
| `gentle` | Small, firm flex with quick settling | [Gentle KDL](../examples/experimental/pointer-wobble-gentle.kdl) |
| `rubber-sheet` | Deeper, slower bend and soft rebound | [Rubber Sheet KDL](../examples/experimental/pointer-wobble-rubber-sheet.kdl) |
| `release-settle` | A more visible spring after release | [Release Settle KDL](../examples/experimental/pointer-wobble-release-settle.kdl) |

These are compositor configuration snippets, not Studio JSON. The pointer option
is separate from resize and timed movement effects. To compare it with an existing
movement shader in the same isolated demo:

```sh
python3 scripts/nested-demo.py --pointer-wobble rubber-sheet --preset momentum-glide
```

## Controls

| Gentle | Rubber Sheet | Release Settle |
| --- | --- | --- |
| ![Gentle pointer drag and settling](gifs/native-pointer-gentle.gif) | ![Rubber Sheet pointer reversal](gifs/native-pointer-rubber-sheet.gif) | ![Release Settle pointer release](gifs/native-pointer-release-settle.gif) |

The clips show compositor output at its actual speed. Their synthetic input path
and exact settings are recorded in the [scenario manifest](gifs/scenario-manifest.json).

The optional node belongs inside `animations` → `window-movement`:

```kdl
animations {
    window-movement {
        pointer-wobble {
            strength 0.7
            damping 65
            frequency 8
        }
    }
}
```

- **Strength**, from 0 to 2, controls how much pointer motion excites the spring.
  Zero disables deformation.
- **Damping**, an integer from 10 to 100, controls how quickly oscillations fade.
  Higher values settle more firmly; 100 is critical damping.
- **Frequency**, an integer from 2 to 16 Hz, controls spring responsiveness.
  Lower values feel looser; higher values feel firmer.

Omitting the node leaves pointer wobble disabled. Global `animations { off; }`
and `window-movement { off; }` also disable it. The built-in shader needs no
`custom-shader` entry. Do not put this node in a stock Niri configuration.

## How it behaves

The spring belongs to the window, so release does not restart its motion.
Another grab carries the remaining deformation forward while blending to the new
anchor. Deformation is bounded to 64 logical pixels and reduced for small windows;
the release tail fades to rest within two seconds on the animation clock. The input rectangle and Niri's
layout placement retain their normal behavior.

An opening animation takes priority. During an active pointer drag or settling,
the pointer effect takes priority over a timed movement shader. Existing resize
rendering may be drawn inside the deformed texture. After opening has finished,
closing takes a snapshot and uses the configured close effect; it does not continue the pointer spring.
This is a bounded surface bend, without a cloth mesh or shared window physics.

The pointer build layers [its own patch](../experimental/niri-pointer-wobble.patch)
on the existing movement prototype. Its source, target directory, executable and
build manifest are separate. Rebuilding one experiment does not replace the
other. Both builds target the revision documented in the
[experimental guide](../experimental/README.md).

## Reproduce validation and showcases

The native harness sends real Wayland pointer events only to its owned nested
compositor. Synthetic cards expose a drag handle and click counter so it can
check input after release and cancellation.

```sh
python3 scripts/test-pointer-wobble.py --all
python3 scripts/test-pointer-wobble.py --all --record
```

In addition to the demo requirements, the harness uses a C compiler,
`wayland-scanner`, `pkg-config`, Wayland client development files, the wlr virtual
pointer protocol XML, Pillow, grim, wf-recorder and FFmpeg. It finds the XML in a
standard system installation or the pinned build's Cargo cache; an explicit
`--pointer-protocol PATH` is also accepted. Bindings are generated locally.

Keep the owned test window visible and the host unlocked during recording.
Native recordings and input acknowledgements do not measure physical
input-to-photon latency. Physical displays, mixed outputs, capture restrictions,
popups and graphics resets need broader acceptance before a login-session rollout.
