# Importable action profiles

Each profile assigns independent opening and closing effects. All four leave
resize and experimental movement unset, preserving the user's existing behavior.
Import a JSON file in Studio, or preview it using the commands below. Previewing
and exporting do not activate animations.

| Profile | Opening | Closing | Showcase |
| --- | --- | --- | --- |
| [Burst and Drift](burst-and-drift.json) | Explosion | Dust Drift | [GIF](../../docs/gifs/profile-burst-and-drift.gif) |
| [Frost and Fragments](frost-and-fragments.json) | Frost Vanish | Pixel Dust | [GIF](../../docs/gifs/profile-frost-and-fragments.gif) |
| [Spring and Ember](spring-and-ember.json) | Spring Wobble | Ember Erosion | [GIF](../../docs/gifs/profile-spring-and-ember.gif) |
| [Ghost and Shockwave](ghost-and-shockwave.json) | Ghost Wisps | Shockwave | [GIF](../../docs/gifs/profile-ghost-and-shockwave.gif) |

Run from the checkout:

```sh
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

To make a new combination, use Studio's **Independent action effects** or
`python3 -m niri_fx profile --help`. See the [profile guide](../../docs/profiles.md)
for editing, saving and explicit resize opt-in; follow [setup and restore](../../docs/setup.md)
when ready to apply a profile.
