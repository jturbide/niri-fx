# Next development phases

This plan follows the maintenance refactor after 0.7.0. It prepares concrete work;
it does not announce implemented integrations, release dates or a new release.
The product scope remains standalone Niri and the existing iNiR/iRiS, DMS and
Noctalia paths. Keep the [integration priority order](roadmap.md).

## Phase 1 — stabilize the current surface

Deliver a repeatable acceptance run for the current 55 styles and existing setup
paths before expanding the catalog again.

- Complete full DMS launcher visual acceptance, including search, selecting a
  style, launching Studio, and Undo after an external config edit.
- Exercise independent profiles through the existing Noctalia picker and iRiS,
  including disabled resize and return to a prior style. Record versions and
  temporary config ownership, rather than implying every shell revision passed.
- Turn the stock Niri open/close smoke into a maintained script with synthetic
  clients, bounded waits, child cleanup and readable evidence. Keep it separate
  from the patched movement harness.
- Add a small transparent-window fixture and mixed/fractional-scale cases to
  compositor acceptance. Test interrupted open/close and output-edge clipping.
- Build a candidate from a clean source archive, verify installed resources and
  restore behavior, update validation evidence, then follow the release guide.

Exit: reproducible scripts and evidence, no regression in active config ownership,
all required CI checks green, and documented remaining hardware/UI limits. A
release is a separate decision after these gates, not part of repo cleanup.

## Phase 2 — measure and improve responsiveness

Separate synthetic shader draw cost from real compositor presentation behavior.
Use a release-built nested Niri, representative window sizes, concurrent effects
and 60/120/144 Hz outputs where available. Include integrated and discrete GPUs
when testers can supply them; retain raw samples and driver/version metadata.

Use the evidence to choose optimizations. Candidate-search reductions must retain
coverage bounds and visual parity. Do not expose particle count as a misleading
universal performance setting. Add a named quality preset only after its cost and
visual tradeoff are understood.

Exit: comparable measurements and targeted improvements with checked endpoints,
transparency and interrupted-animation behavior. Keep performance assertions
scoped to the measured hardware and renderer.

## Phase 3 — reusable shell integration examples

First build one custom Quickshell picker using the existing CLI. Then adapt the
same contract to an AGS/Astal example. Each must support catalog search, custom
profiles, explicit activation, a dedicated restore state and visible failures.
Use argument arrays and catalog IDs; do not interpolate names into shell commands
or duplicate shader math in QML/JavaScript.

Exit for each example: a maintained shell/API version, isolated Niri visual
acceptance, exact restore, a scenario guide, and clear ownership when another
animation manager is present. Caelestia and ML4W remain assessments after those
examples, subject to their Niri/compositor prerequisites. Waybar already uses the
standalone path and needs no effects backend.

## Phase 4 — movement research, separately gated

Keep the pinned Niri patch optional. Before broadening native movement, investigate
continuous retargeting, pointer-driven deformation, resize/close interruption,
damage bounds and cross-window ordering. Record why each required hook belongs
in the compositor rather than inferring it from a shell event stream.

Exit for a proposed hook: a small reviewed patch, pinned build/config/layout tests,
a nested compositor demo, interruption/fallback checks and an explicit support
matrix. A Canvas concept is not native acceptance. Do not replace the login
compositor or enable resize by default.

## Maintenance rules for every phase

Keep domain, rendering, UI, transport and persistence boundaries described in
[architecture](architecture.md). Follow the [effect contribution guide](adding-effects.md)
for new styles. Use shared document fixtures for Python/browser agreement and
keep browser lifecycle handling in one helper. Write comments about invariants
and non-obvious mathematics; keep temporary investigations under ignored
`artifacts/` and preserve recovery snapshots. Each phase should land in reviewable
changes with Unreleased notes and evidence, without unrelated cleanup churn.
