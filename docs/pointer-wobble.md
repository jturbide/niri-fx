# Pointer-driven wobble

Pointer wobble bends a window around the point where you grab it. The
rest of the surface lags behind your hand, responds when you change direction,
and settles after release. Its spring responds to actual drag events.

Pointer wobble is included in the full **NiriFX session**. After
[session setup](native-session.md), open `niri-fx studio --target native`, choose
a **Pointer wobble** preset and review **Select for next login**. It does not
require a separate pointer build. The 0.18 wheel includes portable profiles, interactive browser previews
and Studio controls, with reviewed standalone Apply/Restore when the running
renderer verifies support. Browser previews use synthetic window content and
work without the extension; they do not establish native support.

## Isolated developer preview

From a checkout with Niri's build dependencies, a Rust toolchain and Quickshell:

```sh
python3 scripts/build-niri-movement.py --pointer-wobble --release --test
export NIRIFX_POINTER_MANIFEST=/path/to/candidate/manifest.json
python3 scripts/nested-demo.py --pointer-wobble gentle
```

Replace the manifest path with the one printed by the builder. Keep it set for
the other pointer checks in this terminal, then `unset NIRIFX_POINTER_MANIFEST`.
Each build gets a [separate candidate directory](../experimental/README.md#isolated-build-candidates)
and leaves earlier builds untouched.

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

## Choose it in Studio

In **Library**, keep your chosen opening and closing effects, then use **Pointer
drag** to choose a preset. Expand its controls to adjust strength, damping and
frequency. **Use desktop settings** leaves the pointer choice unset; **Disabled**
stores a zero-strength override. Resize and timed movement remain separate choices.

Choose **Try pointer drag** to drag the sample window in the preview. Reverse
direction, release it, or grab it again while it settles. **Play drag demo** runs
a repeatable drag and release; Enter or Space starts the demo when the canvas has
keyboard focus. **Reset position** recenters the sample. **Return to effects** or
Escape restores the previous editor view without changing your profile.

**Preview combo** adds a scripted pointer phase after the selected shader actions
and before closing when pointer strength is above zero. An unset pointer choice
or **Disabled** does not add that phase. With **Reduced motion**, interactive
dragging moves the sample directly without bending or settling, while the scripted
pointer phase is skipped. The demo button leaves the sample at rest.

The browser uses the native analytical spring and inverse texture mapping. It
lets you compare strength, damping and frequency without a compositor build, but
does not reproduce Niri's input routing, layout or capture rules, or measure
display latency. Use the isolated native demo above to check compositor behavior.

Save the result to **My profiles**, share it or export JSON. These paths work
online, offline and in every local shell integration. **Export stock Niri config**
omits pointer and movement. **Export NiriFX session config** includes
the selected native settings, combining pointer and timed movement in one block
when both are chosen. It does not activate them.

The CLI can build the same portable profile:

```sh
python3 -m niri_fx profile --name "Gentle Fragments" \
  --open-preset balanced --close-preset balanced --pointer gentle > ./gentle-fragments.json
python3 -m niri_fx inspect --custom ./gentle-fragments.json
python3 scripts/nested-demo.py --custom ./gentle-fragments.json
```

The demo recognizes a pointer-only profile and uses the separate pointer build.
The JSON retains opening/closing choices, optional shader actions and desktop
springs alongside `pointer`. It can be imported back into Studio.

## Reviewed activation

Live activation requires a session already running the matching NiriFX
compositor. Test its support and open standalone Studio with that executable:

```sh
python3 -m niri_fx doctor --niri-binary /path/to/patched/niri
python3 -m niri_fx studio --target standalone --niri-binary /path/to/patched/niri
```

After choosing a pointer profile, **Apply pointer wobble** is offered
only when the running renderer and executable match. **Review & apply** describes
the changes; Apply verifies support again before writing. **Restore previous**
restores the saved files unless later edits conflict. See [setup](setup.md) for
the CLI equivalent and explicit config paths.

Installed iNiR and connected Noctalia adapters retain pointer settings in JSON
but apply stock actions. An accepted parser probe or a successful isolated demo
does not establish support in the login compositor. NiriFX does not replace that
compositor during Apply.

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
disables it; timed movement Off preserves an explicitly selected pointer style
on the current contract-2 build. The built-in shader needs no
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
python3 scripts/test-pointer-integration.py
python3 scripts/test-pointer-hardening.py
```

The integration check exercises profile review, Apply, runtime capability loss,
combined movement and exact Restore against its own nested session. It does not
write the login session's configuration.

The build command's `--test` also runs native layout regressions for tiled and
floating drags when the destination output disappears, all outputs disappear,
or an output returns before release. They check spring continuity, window
ownership and cleanup after settling. These tests simulate output lifecycle
changes inside Niri's layout; they do not establish physical monitor hotplug or
mixed-monitor behavior.

The hardening harness checks direct ScreenCapture privacy with synthetic visible
controls, rule changes during dragging, redacted closing snapshots, and abrupt
client exit followed by input to a surviving window. Its `screencast` policy case
is a negative control for ScreenCapture, not a test of the Screencast render
target or PipeWire. See the [validation scope and known limits](validation.md#pointer-driven-wobble)
and [sanitized results](benchmarks/pointer-hardening.json).

The development compositor tracks presses and consumed bindings per device.
Removing an idle pointer leaves another pointer's grab alone. Removing the held
owner releases its buttons; when two devices hold the same button, the logical
seat press remains until the final owner releases. This fixes the virtual-device
failure reproduced in [unmodified pinned Niri](benchmarks/native-baseline.json).
Physical unplug/replug still needs hardware acceptance.

The separate stale-output limitation remains: the optional
`python3 scripts/test-pointer-hardening.py --output-targets` probe fails on
the tested GPU because the parent compositor retains a stale child image after
closing. It keeps strict assertions and does not establish Output/Screencast
privacy. The unmodified baseline reproduces this too; compositor, driver and
nested-test causes remain unisolated.

`python3 scripts/test-native-baseline.py --probe overlap` compares two virtual
pointers on the same owned seat. Removing an idle device preserves the other
device's active grab, including after ownership has changed. Removing the held
owner leaves a stale grab in the preserved baseline variants. Paired same-button
presses also expose shared-seat release behavior, so a global button reset would
not establish correct device ownership. The current acceptance command requires
correct removal, overlap, binding suppression and subsequent client clicks:

```sh
python3 scripts/test-pointer-ownership.py
python3 scripts/test-pointer-ownership.py --pointer-wobble
```

See the [scenario results and source audit](validation.md#pointer-driven-wobble)
and [current ownership report](benchmarks/pointer-ownership.json) for the
distinction between the preserved failure and current acceptance.

In addition to the demo requirements, the harness uses a C compiler,
`wayland-scanner`, `pkg-config`, Wayland client development files, the wlr virtual
pointer protocol XML, Pillow, grim, wf-recorder and FFmpeg. It finds the XML in a
standard system installation or the pinned build's Cargo cache; an explicit
`--pointer-protocol PATH` is also accepted. Bindings are generated locally.

Keep the owned test window visible and the host unlocked during recording.
Native recordings and input acknowledgements do not measure physical
input-to-photon latency. Physical displays, mixed outputs, Output/Screencast and
PipeWire capture, popups, blurred backgrounds and graphics resets need broader
acceptance before a login-session rollout.
