# NiriFX roadmap

NiriFX aims to make window effects expressive, easy to tune and comfortable for
everyday use. This roadmap describes work being considered next. Priorities can
change with feedback; items here do not imply a release date.

See the [README](README.md) for available features, the [changelog](CHANGELOG.md)
for completed work and [compatibility](docs/compatibility.md) for supported setups.
`main` may contain features newer than the latest release.

## Next: confidence across more desktops

- **More hardware results.** Compare large windows and simultaneous animations on
  integrated GPUs and several refresh rates. Publish repeatable measurements with
  their hardware and renderer details.
- **Mixed-monitor behavior.** Test fractional scaling, output changes, decorations,
  fullscreen transitions and effects near screen edges.
- **More interruption coverage.** Exercise rapid open/close sequences and overlapping
  resize, movement and close actions with real applications.
- **Clearer performance choices.** Explore quality options where measurements show
  a useful tradeoff, while retaining recognizable textures and smooth endpoints.

The [performance guide](docs/performance.md) and [validation record](docs/validation.md)
show what has already been measured and what remains untested.

## Next: reusable shell pickers

Standalone NiriFX already works with any bar or shell running on Niri. These
integrations would add convenient browsing and settings interfaces:

1. **Custom Quickshell:** a reusable picker with search, profiles and Undo.
2. **AGS/Astal:** an equivalent example for GTK-based shells.
3. **Caelestia:** assess a maintained Niri setup and a suitable extension point.
4. **ML4W:** document a separate Niri session, then assess an appropriate settings adapter.

The existing iNiR/iRiS, DMS and Noctalia paths remain the supported integrations.
Waybar uses [standalone setup](docs/standalone.md) and needs no separate effects
backend. See the [integration design notes](docs/roadmap.md).

## Exploring: interactive movement

The optional compositor patch demonstrates native swaps, retargeting and continued
animation during close interruptions. It remains an experiment with a pinned Niri
revision, separate from the standard installation.

Further research includes velocity continuity during rapid direction changes,
pointer-driven deformation, more efficient damage bounds and ordering particles
from different windows in one scene. A shared particle scene would need more
compositor work than the current independent window shaders.

See the [movement guide](docs/movement.md) and [nested demo](experimental/README.md).
New styles are welcome when they add a distinct look, with examples and measured
costs rather than a growing list of nearly identical presets.

## Contribute a result or an idea

[Open an issue](https://github.com/jturbide/niri-fx/issues) with your setup, the
behavior you want and a reproducible example. Reports from different GPUs and
monitor arrangements are especially useful. [Contributing](CONTRIBUTING.md) covers
development checks; the [design notes](docs/next-phases.md) explain the technical
questions behind this roadmap.
