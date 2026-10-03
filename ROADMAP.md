# NiriFX roadmap

This is the current plan for NiriFX. Priorities can change with user feedback and
test results; these milestones have no promised release dates. Completed work may
be on `main` ahead of a tagged release: see [Unreleased](CHANGELOG.md).

**Next priority: finish acceptance of the existing effects and integrations, then
measure their cost before adding more styles or shell adapters.**

## Available today

- **55 presets across eight families:** Fragments, Slices, Elastic, Dissolve,
  Iris, Pixels, Wisps and Distortion, with a [visual gallery](docs/showcases.md).
- Stock Niri opening and closing, independent action profiles and explicitly
  enabled fragment resize. **Resize stays off by default.**
- Standalone Studio with app-style launch, import/export, Undo/Redo, search,
  favorites and pinned A/B comparisons.
- Reversible standalone setup, iNiR/iRiS preset registration, a DMS launcher
  adapter and export for Noctalia's existing animation picker.
- Lint, unit/integration/browser checks, shader validation, package checks and
  documentation/GIF consistency checks in required GitHub Actions.
- An **optional, pinned Niri patch** for native movement and swaps. Stock Niri
  does not gain movement shaders merely by installing a shell adapter.

See [compatibility](docs/compatibility.md) and [validation](docs/validation.md) for
the tested versions and limits of these claims.

## 1. Everyday workflows and visual acceptance — in progress

- [x] Record every built-in preset and importable profile; compare tuning controls.
- [x] Record Studio import, independent editing, A/B comparison, Undo/Redo and export.
- [x] Exercise stock Niri with transparent synthetic clients, tall/wide windows
  and a single output at fractional scale.
- [x] Record interrupted movement and close-during-movement in the patched compositor.
- [x] Record versioned iRiS, DMS and Noctalia picker walkthroughs, including prior-style
  restoration and preservation of base resize behavior.
- [ ] Extend acceptance to interrupted opening/closing, decorations, fullscreen
  and output-edge clipping.
- [ ] Test real mixed-scale monitors and multiple applications; one nested output
  at 1.5× is not mixed-monitor acceptance.

**Done when:** maintained scripts reproduce the workflow checks, every published
clip identifies its renderer and settings, and the remaining hardware limitations
are explicit. [Scenario index](docs/showcases.md) · [Recording guide](docs/gifs/README.md)

## 2. Performance and visual quality — planned

- Measure release-built compositor behavior across representative window sizes,
  simultaneous effects and available 60/120/144 Hz displays.
- Collect integrated/discrete GPU results with driver versions and raw samples.
- Use the results to improve expensive shader paths, clipping, alpha handling
  and perceived motion. Add quality settings only with measured visual/cost tradeoffs.
- Revisit new styles and variants after these checks. Prioritize distinct visual
  behavior over adding near-duplicate presets.

**Done when:** before/after measurements are comparable, intact/transparent endpoints
and interruption checks pass, and performance claims name the tested hardware.
The existing [GPU harness](docs/performance.md) measures shader draw cost; it does
not certify desktop responsiveness.

## 3. Reusable shell integrations — planned, in this order

1. **Custom Quickshell example:** a small maintained picker using the shared CLI.
2. **AGS/Astal example:** reuse the same catalog, profile and apply/restore contract.
3. **Caelestia assessment:** establish a maintained Niri-capable target and extension
   point before implementing or claiming support.
4. **ML4W assessment:** begin with separate Niri-session coexistence and ownership;
   a settings adapter depends on an appropriate Niri target.

**Done for each adapter when:** search, custom profiles, explicit activation,
visible errors and exact restore pass in a real isolated shell workflow, with a
versioned guide. [Integration priorities](docs/roadmap.md) · [Custom shell contract](docs/custom-shells.md)

**Waybar already works through standalone NiriFX.** An optional Studio button needs
no separate shader backend. Other compositor backends remain exploratory, outside
the committed integration milestones.

## 4. Native movement research — experimental, separately gated

- Investigate continuous retargeting and direct pointer-driven deformation.
- Expand move/resize/close interruption, fallback and damage-bound coverage.
- Explore cross-window particle ordering for swaps only after compositor hooks
  can support it correctly; event notifications alone are insufficient.
- Keep patches small, pinned and reviewable, with build/config/layout tests and
  actual nested-compositor captures for every claimed capability.

**Done for a proposed feature when:** a reviewed patch passes its reproducible
acceptance cases and has a clear fallback/support matrix. Canvas concepts do not
count as native implementation. [Movement design](docs/movement.md) · [Experiment](experimental/README.md)

## Release gate — after acceptance

- [ ] Choose the release scope from verified work and remaining known limits.
- [ ] Build from a clean source archive, check installed resources, setup and restore.
- [ ] Pass required CI, check gallery/docs metadata and finalize release notes.
- [ ] Follow the signed [release procedure](docs/releasing.md), then publish the
  chosen version. This roadmap does not itself schedule a release.

## Keeping this useful

Update this file when a milestone changes status; record implementation details in
[CHANGELOG.md](CHANGELOG.md) and actual acceptance results in
[docs/validation.md](docs/validation.md). The [development phases](docs/next-phases.md)
provide detailed engineering gates, and [architecture](docs/architecture.md) describes
the boundaries to preserve. Keep speculative ideas unchecked until they have an
implementation and evidence, rather than treating a GIF or an experiment as support.
