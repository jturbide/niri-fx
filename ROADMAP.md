# NiriFX roadmap

NiriFX's next priority is making its effects feel good in everyday use across
more applications and display setups. Performance improvements and reusable
shell integrations follow. Priorities may change with feedback; no release dates
are set for the work below.

For features you can use today, see the [README](README.md) and
[compatibility guide](docs/compatibility.md). The [changelog](CHANGELOG.md) records
completed changes; `main` can include features newer than the latest release.

## Everyday use — in progress

Make effects behave consistently when windows open, close, change size or are
interrupted, and make choosing and restoring a style straightforward.

- [x] A recorded example for every built-in preset and importable profile.
- [x] Walkthroughs for Studio editing/export and iRiS, DMS and Noctalia selection.
- [x] Tests with transparent, tall and wide windows, plus a single output at 1.5× scale.
- [ ] Broader testing with application decorations, fullscreen windows and effects
  near output edges.
- [ ] Mixed-scale monitors and windows moving between outputs.
- [ ] More coverage of interrupted opening/closing and overlapping resize/close effects.

The [gallery](docs/showcases.md) shows current behavior. [Testing and known limits](docs/validation.md)
identify the applications, versions and display setups checked so far.

## Performance and visual quality — planned

Help users choose effects that suit their hardware without losing the look they want.

- Measure responsiveness with large windows, concurrent animations and different
  refresh rates on integrated and discrete GPUs.
- Improve expensive shader paths, transparency and clipping using those results.
- Explore quality options with documented performance and appearance tradeoffs.
- Add styles and variants with distinct visual behavior, alongside improvements
  to the existing collection.

The [GPU measurements](docs/performance.md) provide initial shader timings.
Measurements of complete compositor behavior are the next step.

## More shell integrations — planned

Standalone NiriFX already works with any bar or shell on Niri. These projects
would add convenient ways to browse and apply effects:

1. **Custom Quickshell picker:** a reusable example with search, custom profiles
   and Undo.
2. **AGS/Astal example:** the same workflow in a GTK-based shell.
3. **Caelestia:** assess a Niri-compatible setup and suitable integration point.
4. **ML4W:** document use in a separate Niri session, then assess a settings integration.

Caelestia and ML4W adapters are exploratory. Waybar works through the
[standalone setup](docs/standalone.md); it needs no separate effects backend.
See [integration plans](docs/roadmap.md) for details.

## Movement and swaps — experimental

An optional Niri patch already demonstrates native fragment and elastic column
swaps. Further work aims to make movement feel continuous during interaction:

- Smoother redirection when another move starts before the previous one finishes.
- Pointer-driven deformation while dragging a window.
- Better handling of overlapping movement, resize and close actions.
- Exploration of particle ordering between swapping windows.

These are research goals, not features of the standard installation. The
[experimental build](experimental/README.md) runs in a separate nested session;
Studio's Move/Swap tabs remain concept previews. Fragment resize stays opt-in.

## Help shape the roadmap

[Open an issue](https://github.com/jturbide/niri-fx/issues) with the behavior you
want, your setup and a reproducible example where possible. Reports from different
GPUs and monitor arrangements are especially useful. See [Contributing](CONTRIBUTING.md)
for implementation guidance and the [engineering plan](docs/next-phases.md) for
detailed test requirements. Releases follow the [release process](docs/releasing.md)
after their changes are tested and documented.
