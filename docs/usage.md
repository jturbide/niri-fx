# Studio and controls

![Gravity and rotation controls in Niri Fragments Studio](studio.png)

```sh
python3 -m niri_fragments studio
```

This opens a dedicated Chromium app window, with no tabs or address bar and a
separate profile. The optional application launcher opens the same window.
The renderer is still web technology, not a native QML page. If Chromium is
unavailable, it falls back to your browser; `studio --browser` explicitly opens
a browser tab. Live controls include:

- **Gravity direction:** none, down, up, left, right, center, or outward.
- **Gravity strength:** 0–3×. Downward gravity accelerates; outward space motion
  drifts at a constant radial rate. Strength is artistic, not an SI unit.
- **Particles:** a target of 16–4096 pieces, or a fixed square size of 8–128
  logical pixels. Target counts are approximate so fragments remain square;
  very small windows also have a four-pixel minimum tile size.
- **Rotation:** none, random spin, or orientation toward the travel direction.
- **Spin:** 0–720 degrees; the random spin range or the alignment limit.
- **Orbit:** −360 to +360 degrees around the window center.
- **Spread:** 0–240 logical pixels of initial radial scatter.
- **Path dispersion:** 0–1; separates fragment speeds and curves their paths.
- **Release stagger:** 0–0.4; varies when fragments separate and dissolve.
- **Timing:** independent opening, closing and resizing durations, 100–1500 ms.
- **Resize (off by default):** enable switch and breakup strength (0–1); bounded fragments
  reconstruct the window at its new size. Resize shares particle count, gravity
  direction and rotation; its strength is separate from open/close gravity.

The editor uses the same shader templates as the CLI. Click **Reconstruct** or
**Deconstruct**, or scrub the timeline. Set a name and choose **Save to iRiS**;
then select that named style in iRiS's existing picker. Saving does not activate
it. Saving the same name updates that custom preset, with a backup.

The **Move** and **Swap** tabs are visual concepts: textured particles cross
between columns and reconstruct at their destinations. They are not installed
movement effects. Saving/exporting changes open/close and enabled resize behavior.
Run `python3 scripts/nested-demo.py` after building the isolated experiment
to try actual native movement. See [the compositor work](movement.md).

The controls live in Fragments Studio. iRiS's native page lists the resulting
presets; its stock thumbnail still shows generic timing rather than this shader.

The editor binds only to loopback and uses a per-session save token and origin
checks. It reads the installed iNiR helper and writes only the preset registry.
The editor page makes no external network requests. It exits within 15 minutes of the app window or tab
closing (or immediately with Ctrl+C when launched from a terminal).

For an app-launcher entry tied to this checkout:

```sh
python3 scripts/install-desktop.py
```

Search for **Niri Fragments Studio** in your application launcher. This is
on-demand; nothing is added to session startup. Keep the checkout at its current
path, or recreate the launcher after moving it.

An offline editor is also available:

```sh
python3 -m niri_fragments preview --preset earth --output /tmp/fragments.html
xdg-open /tmp/fragments.html
```

Offline mode can export a preset JSON file or standalone KDL. Import JSON with:

```sh
python3 -m niri_fragments register --custom ~/Downloads/niri-fragments-preset.json
```

## Command-line options

```sh
# Save a custom option alongside the built-in pack.
python3 -m niri_fragments register --name "Heavy Meteor" --preset earth \
  --gravity-strength 1.8 --particles 400 --rotation random --spin 360

# Render a standalone override; includes no shell integration or activation.
python3 -m niri_fragments render --preset black-hole --gravity-strength 0.8 \
  --swirl 120 --rotation gravity --particles 300 > fragments.kdl
niri validate -c fragments.kdl
```

`--tile-size` switches off target-count mode. `--particles 0` also selects fixed
sizing. `list` prints the built-in parameters as JSON. `--preset` chooses the
starting values for `render`, `preview`, `studio`, or a named `register`.

## Presets

| Preset | Motion |
| --- | --- |
| Subtle / Balanced / Dramatic | Increasingly dense bursts: 360 / 720 / 1,100 pieces |
| Explosion | 1,200 tumbling pieces burst outward; opening implodes them into place |
| Implosion | 1,000 pieces collapse toward the center; opening reverses the collapse |
| Earth | Accelerates downward with randomized spin |
| Black Hole | Draws pieces inward and turns them toward the center |
| Space | Drifts outward in every direction with free spin |
| Vortex | Spirals inward while pieces follow their travel direction |
| Confetti | Small tumbling pieces with downward gravity |
| Updraft | Rises with a slight orbit and direction-following rotation |

Particle targets are approximate and depend on window geometry. Opening reverses
the closing trajectory with its own duration; the effect is artistic rather than
a physical simulation. There are no particle collisions.

## Resize is opt-in

New presets, built-in presets and Studio sessions all start with fragment resize
disabled. Enable **Fragment windows when resizing**, or pass `--resize`:

```sh
python3 -m niri_fragments register --name "Resize experiment" --preset balanced --resize
python3 -m niri_fragments render --preset balanced --resize > /tmp/fragments-resize.kdl
```

`--no-resize` suppresses the override. With the iNiR adapter, the base preset's
resize behavior is preserved when fragments are disabled. Standalone exports
omit `window-resize`, leaving your existing Niri settings in charge. Saved custom
presets keep their explicit choices; legacy JSON without `resize` opts out.

See [installation, updating and rollback](getting-started.md) before applying
exports. The CLI's `--help` and subcommand `--help` list every available option.
