# Independent action profiles

A style describes one effect. A profile assigns separate styles to opening,
closing and optionally resizing. For example: open with Spring Wobble, close
with Ember Erosion, and leave your existing resize behavior unchanged.

![Spring opening and ember closing in one profile](gifs/profile-spring-and-ember.gif)

## Choose a finished pairing

The built-in collection contains seven profiles. Select **profiles** in the
terminal guide, use **Ready-made open / close pairing** in Studio, or search a name
in the Quickshell, GTK, DMS or iRiS picker. No JSON file is needed. Existing iNiR
registrations and Noctalia preset packs need a reviewed update to add the new names.

| Profile | Opens with | Closes with | Look |
| --- | --- | --- | --- |
| `fragment-flow` | Balanced | Implosion | Textured assembly followed by an inward collapse |
| `burst-and-drift` | Explosion | Dust Drift | A strong arrival followed by drifting dust |
| `frost-and-fragments` | Frost Vanish | Pixel Dust | A frosted reveal that breaks into pixels |
| `spring-and-ember` | Spring Wobble | Ember Erosion | A playful spring with a monochrome fade |
| `ghost-and-shockwave` | Ghost Wisps | Shockwave | Soft wisps followed by a ripple |
| `pixel-shuffle` | Pixel Wipe | Pixelate | A pixel reveal and a chunky exit |
| `ribbon-exit` | Alternating Blinds | Ribbon Fold | Alternating strips that fold away |

These pairings reuse existing preset settings. All leave resize and experimental
movement unset. Their shader cost is the cost of the chosen action; profiles do
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
alone leaves the slot unset. Stock KDL and iRiS exports omit it;
movement requires the separate [compositor experiment](../experimental/README.md).
Profiles do not add application-specific rules or interactive dragging hooks.

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
`--movement-strength` are explicit demo overrides. An unset movement slot is
rejected rather than silently replaced. See [native movement](movement.md).
