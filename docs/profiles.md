# Independent action profiles

A style describes one effect. A profile assigns separate styles to opening,
closing and optionally resizing or moving. Desktop springs and pointer drag can
be stored separately from those four shader actions. For example: open with Balanced
fragments, close with Implosion, and leave your existing resize behavior unchanged.

![Textured fragments assemble and collapse inward in one profile](gifs/profile-fragment-flow.gif)

## Choose a finished pairing

Start with **Recommended** in Library for five complete combos: Fragment Flow,
Soft Landing, Ribbon Current, Playful Motion and Geometric Flow. Their opening
and closing effects have coordinated timing and modest refinements to travel,
rotation or spring settling. The individual source presets keep their settings.

Choose any built-in pairing by name. Select **profiles** in the
terminal guide, use **Ready-made profile** in the detailed Studio controls, or search a name
in the Quickshell, GTK, DMS or iRiS picker. No JSON file is needed. Existing iNiR
registrations and Noctalia preset packs need a reviewed update to add the new names.

| Profile | Opens with | Closes with | Look |
| --- | --- | --- | --- |
| `fragment-flow` | Balanced | Implosion | Everyday textured assembly and a compact inward collapse |
| `soft-landing` | Momentum Glide | Frost Vanish | A gentle arrival and a quiet frosted exit |
| `ribbon-current` | Ribbon Wave | Ribbon Transfer | Flowing waves and an exit with matching alternating strips |
| `playful-motion` | Spring Wobble | Bubble Burst | A damped spring, light bubbles and bouncing desktop springs |
| `geometric-flow` | Triangle Shatter | Hex Swarm | Triangles assemble and hexagons drift away at matching density |
| `burst-and-drift` | Explosion | Dust Drift | A strong arrival followed by drifting dust |
| `frost-and-fragments` | Frost Vanish | Pixel Dust | A frosted reveal that breaks into pixels |
| `spring-and-ember` | Spring Wobble | Ember Erosion | A playful spring with a monochrome fade |
| `ghost-and-shockwave` | Ghost Wisps | Shockwave | Soft wisps followed by a ripple |
| `pixel-shuffle` | Pixel Wipe | Pixelate | A pixel reveal and a chunky exit |
| `ribbon-exit` | Alternating Blinds | Ribbon Fold | Alternating strips that fold away |
| `gentle-motion` | Momentum Glide | Frost Vanish | Gentle desktop springs |
| `balanced-motion` | Balanced | Implosion | Restrained desktop springs |
| `fragments-motion` | Mixed Confetti | Orbiting Shapes | Mixed geometry with Balanced desktop timing |
| `ribbons-motion` | Ribbon Wave | Zipper | Flowing strips with Gentle desktop timing |
| `elastic-motion` | Spring Wobble | Rubber Band | Springy sheets with Playful desktop timing |

| Fragment Flow | Soft Landing | Ribbon Current |
| --- | --- | --- |
| ![Textured fragments assemble and collapse inward](gifs/profile-fragment-flow.gif) | ![A gentle elastic arrival and a quiet frosted exit](gifs/profile-soft-landing.gif) | ![Waving ribbons arrive and matching alternating strips leave](gifs/profile-ribbon-current.gif) |

| Playful Motion | Geometric Flow |
| --- | --- |
| ![A damped spring arrival and a light bubble exit](gifs/profile-playful-motion.gif) | ![Triangles assemble and hexagons drift away at matching density](gifs/profile-geometric-flow.gif) |

Browse by look in the [preset collections](collections.md). Pairings build on
the named source presets; the five recommended combos refine their action settings
as described above. Their JSON files contain the exact resolved parameters.
The [motion packs](desktop-motion.md) and [coordinated action sets](action-sets.md) additionally coordinate stock desktop springs. Action sets suggest separately enabled resize and movement companions in Studio or through `profile --action-set`. All leave resize and experimental
movement and pointer drag unset. Their shader cost is the cost of the chosen action; profiles do
not add a second rendering pass. See [performance measurements](performance.md).

```sh
python3 -m niri_fx list --profiles --text
python3 -m niri_fx studio --profile burst-and-drift
# Review standalone activation, then append --apply to write that selection:
python3 -m niri_fx setup --target standalone --profile burst-and-drift --no-launcher
# Register just this pairing for selection in iRiS:
python3 -m niri_fx register --profile burst-and-drift
# Export editable JSON or stock Niri KDL:
python3 -m niri_fx inspect --profile burst-and-drift > /tmp/burst-and-drift.json
python3 -m niri_fx render --profile burst-and-drift > /tmp/burst-and-drift.kdl
```

`--profile` chooses both actions; `--preset` chooses one style for both. They cannot
be combined. Effect override flags are deliberately rejected with `--profile`,
so a change cannot silently target the wrong action. Open it in Studio to customize.
[All JSON files and preview commands](../examples/profiles/README.md) and
[gallery loops](showcases.md#different-effects-for-each-action) remain available.

## Preview a complete combo

Choose a card in Library, then press **Preview combo**. The sequence plays the
opening effect, holds the intact window and plays the closing effect using each
action's own style and duration. Selected resize and movement effects are included
when those profile slots are enabled; leaving them at shell defaults skips them.
Previewing never enables an optional action or applies desktop settings. In
version 0.18 and newer, an explicit pointer choice with strength above
zero adds a scripted drag and release before closing. Unset and disabled pointer
choices add no animation. **Reduced motion** skips this pointer phase.

Use **Try pointer drag** in Library for interactive dragging, or **Play drag demo**
for a repeatable comparison. **Reset position** recenters the sample; **Return to
effects** or Escape restores the editor view. With **Reduced motion**, interactive
dragging moves the sample without bending or settling. These browser previews
use native spring and shader math with synthetic window content; native input,
layout, capture behavior and display latency require compositor checks. See
[pointer-driven wobble](pointer-wobble.md).

Resize requires an explicit choice. **Movement (experimental)** shows the shader
on a synthetic path; live move/swap effects require the verified experimental
compositor. See [movement support](movement.md). Playful Motion also includes stock
desktop spring settings, whose workspace, camera and overview behavior is shown
in the [native desktop recordings](desktop-motion.md), separately from the
window shader preview.

## Create your own combination

In Studio, enable **Independent action effects**, choose **Editing action**, and
pick/tune its style. Reconstruct previews the opening action; Deconstruct previews
the closing action. Viewing Resize never enables it: tick **Enable resize effect**
deliberately. Fragments, Slices, Elastic and Distortion support resize. Turning independent
effects off uses the opening style for both actions; Undo recovers the profile.

Create the same profile from the CLI:

```sh
python3 -m niri_fx profile --name 'Spring and Ember' \
  --open-preset spring-wobble --close-preset ember-erosion > /tmp/my-profile.json
python3 -m niri_fx preview --custom /tmp/my-profile.json --output /tmp/my-profile.html
python3 -m niri_fx render --custom /tmp/my-profile.json > /tmp/my-profile.kdl
niri validate -c /tmp/my-profile.kdl
```

Use `--resize-preset balanced` when creating a profile to opt in. To register it
without activation, use `register --custom /tmp/my-profile.json`; standalone
`setup --custom /tmp/my-profile.json --target standalone` first prints a plan.
`--apply` activates the backed-up standalone include. See [setup](setup.md).

Profiles are **kind `profile`, schema 1** documents with `name` and `actions`.
`open` and `close` contain effect objects; `resize` and `movement` are nullable.
Each nested effect keeps `resize: false`: the separate resize slot is the opt-in.
Single-style documents continue to use effect schema 3; these are different
document types, not compatibility aliases. [Complete example](../examples/profiles/spring-and-ember.json).

The experimental `movement` slot is validated and preserved on import/export.
Studio can edit it and preview the actual shader in **Movement (experimental shader)**.
Tick **Include experimental movement in JSON** to store the choice; viewing it
alone leaves the slot unset. Stock KDL and iRiS exports omit it by default; explicit standalone activation requires a verified running contract. See [Apply and Restore](setup.md#activate-experimental-movement). Movement requires the separate [compositor experiment](../experimental/README.md).
Profiles do not add application-specific rules. Pointer drag uses a separate
optional native extension, described below.

## Optional pointer drag

Pointer settings in profiles, Studio and reviewed activation are available in
**0.18 and newer**. Live pointer deformation requires the separately built
[experimental compositor](pointer-wobble.md).

In Library, **Pointer drag (optional)** offers **Use desktop settings**, **Disabled**,
**Gentle**, **Rubber Sheet** and **Release Settle**. **Customize pointer drag** exposes
strength, damping and frequency. These choices are independent of the opening,
closing, resize and timed movement styles. Switching to one shared window style
preserves the pointer choice; Undo/Redo, JSON import/export and share links preserve it too.

```sh
python3 -m niri_fx profile --name 'Gentle Fragments' \
  --open-preset subtle --close-preset subtle --pointer gentle > /tmp/gentle-fragments.json
python3 -m niri_fx inspect --custom /tmp/gentle-fragments.json
python3 scripts/nested-demo.py --custom /tmp/gentle-fragments.json
```

Build the [pointer extension](pointer-wobble.md) before running that demo. The
profile can contain pointer settings with no timed `movement` action. The nested
window uses its own compositor and configuration.

A profile's optional top-level `pointer` object contains all three controls:
`{"strength": 0.4, "damping": 85, "frequency": 10}`. Strength is a finite number
from 0 to 2, damping is a whole percentage from 10 to 100, and frequency is a whole
number from 2 to 16 Hz. Omitting `pointer` or setting it to `null` inherits existing
behavior. Strength zero is an explicit disabled override; use `profile --pointer off`
to generate one. The four `actions` keys remain unchanged, and existing schema 1
profiles remain valid.

Saving a pointer choice does not activate it. Stock KDL, iNiR registrations and
Noctalia preset downloads omit pointer nodes, including a disabled override.
Portable JSON retains the settings. Studio's **Export experimental config** includes
pointer settings and any selected timed movement in one `window-movement` block;
that file requires the matching compositor extensions.

Live activation is available through the standalone adapter after verifying the
running pointer contract. **Apply experimental pointer drag** is a separate
choice from **Apply experimental movement**. Changing the pointer settings clears
its activation choice and invalidates the review. A disabled override also requires
explicit activation. See [reviewed pointer Apply and Restore](setup.md#activate-experimental-pointer-drag).

![Independent action editing in Studio](studio-profiles.png)

## Studio workflow

- Search filters the current family's presets; favorites can narrow the list.
  Local Studio stores favorites in `$XDG_STATE_HOME/niri-fx/studio-preferences.json`
  (or `--state`). Offline previews use browser-local storage when available.
- Undo/Redo keeps the last 100 editing states, including profile actions and imports.
  Reset returns an individual parameter to its catalog default.
- **Pin A** remembers the current effect and random seed. Edit B, then **Show A/B**
  compares them at the same timeline position. Saving always exports B. Comparison
  is available for open/close effects; it does not alter either action.
- **Save target** selects iNiR registration or a named KDL download for Noctalia
  or standalone Niri. Downloads do not activate effects. For Noctalia, put the file
  in the picker's configured preset folder; see [Noctalia setup](noctalia.md).
- Detailed wave controls are collapsible. Each family shows applicable controls
  using the same parameter definitions as the CLI and Python validation.

Launch with `python3 -m niri_fx studio --target standalone` to start with file
downloads, or choose `--target inir` / `--target noctalia`. The default `auto`
selects iNiR when its helper is installed, otherwise standalone. Offline previews
also default to standalone. The target changes the save UI, not your active effect.

Test an exported movement profile without replacing the login compositor:

```sh
python3 scripts/nested-demo.py --custom examples/profiles/fragment-wake-motion.json
```

The demo uses the movement action's duration and strength. `--duration-ms` and
`--movement-strength` are explicit demo overrides. A profile with pointer settings
and an unset movement slot demonstrates pointer drag without adding a timed shader.
A profile with neither choice is rejected. `--pointer-wobble gentle` can override
its pointer settings for the demo without changing the JSON. See
[native movement](movement.md) and [pointer drag](pointer-wobble.md).
