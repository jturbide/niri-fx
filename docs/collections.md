# Choose a preset collection

Collections group finished looks across effect families. A family describes how
an effect is rendered; a collection helps you choose its character. Styles can
belong to more than one collection. The full catalog remains available.

| Collection ID | Look | Start with |
| --- | --- | --- |
| `action-sets` | Coordinated effects with separately enabled resize/movement companions | Fragments Motion |
| `desktop` | Window effects with workspace, camera and overview timing | Balanced Motion |
| `everyday` | Compact movement and readable arrivals | Balanced or Soft Landing |
| `bursts` | Explosions, inward collapse and gravity | Explosion or Burst and Drift |
| `shapes` | Geometric pieces and joined layouts | Triangle Shatter or Geometric Flow |
| `ribbons` | Slices, folds, hinges and waves | Alternating Blinds or Ribbon Current |
| `playful` | Wobble, bounce and elastic settling | Spring Wobble or Jelly |
| `atmospheric` | Frost, wisps, ink and gentle distortion | Frost Vanish or Soft Landing |
| `pixels` | Pixel wipes, chunky breakup and glitches | Pixel Wipe or Pixel Shuffle |

## Browse and choose

```sh
niri-fx list --collections --text
niri-fx list --collection shapes --text
niri-fx list --collection atmospheric --profiles --text
niri-fx studio --profile geometric-flow
```

From the checkout, replace `niri-fx` with `python3 -m niri_fx`. In the terminal
guide, type **groups** to see the collection IDs, then **@shapes** or another ID.
Pick a name or number to review its configuration before applying it.

Studio's **Collection** chooser filters starting styles and finished pairings
across families. Filtering keeps the current effect intact. Choosing an effect
family returns to that family's full list. The
[gallery](https://jturbide.github.io/niri-fx/gallery/?collection=shapes) has the same
collection names, shareable filters and click-to-play examples. Its collections
contain finished styles and pairings; **All examples** also includes comparisons,
resize demonstrations and native movement scenarios.

The Quickshell and GTK pickers retain their family and name filters. iNiR
registrations include collection IDs and all profile action families as search
keywords. Re-register the collection or refresh an exported shell preset pack to
add new names; updating registration does not select a new effect.

## Use the settings

```sh
# Review standalone activation; append --apply after reviewing the files:
niri-fx setup --target standalone --profile geometric-flow --no-launcher
# Portable JSON for every member, including independent profile actions:
niri-fx list --collection shapes > shapes.json
```

The last command produces a catalog keyed by style ID. Use
`niri-fx inspect --profile geometric-flow > geometric-flow.json` for a single
importable document. Collection labels and membership stay outside style/profile
schemas, so sharing or customizing a look does not change its effect parameters.

Built-in styles and pairings preserve existing resize settings. Pairings also
leave experimental movement unset. See [action profiles](profiles.md),
[setup and restore](setup.md), and the [complete visual catalog](catalog.md).

The three [desktop motion packs](desktop-motion.md) and three [coordinated action sets](action-sets.md) intentionally replace the stock workspace, camera and overview springs. Other profiles preserve them.
