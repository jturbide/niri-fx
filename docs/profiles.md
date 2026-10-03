# Independent action profiles

A style describes one effect. A profile assigns separate styles to opening,
closing and optionally resizing. For example: open with Spring Wobble, close
with Ember Erosion, and leave your existing resize behavior unchanged.

![Spring opening and ember closing in one profile](gifs/profile-spring-and-ember.gif)

In Studio, enable **Independent action effects**, choose **Editing action**, and
pick/tune its style. Reconstruct previews the opening action; Deconstruct previews
the closing action. Viewing Resize never enables it: tick **Enable resize effect**
deliberately. Only Fragments currently supports resize. Turning independent
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
Studio does not edit or activate it yet. Stock KDL and iRiS exports omit it;
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
