# NiriFX roadmap

NiriFX focuses on finished effects and coherent motion for Niri. Choose a preset,
apply it, and customize when useful. Niri remains the primary compositor; other
backends are research candidates, not current compatibility claims.

Checklists describe concrete deliverables. Checked items have shipped or have
recorded validation; unchecked items are still planned or in development. Epic
order expresses priority, not a release date. See [available features](README.md),
[release history](CHANGELOG.md) and [validation limits](docs/validation.md).

## Coherent desktop motion milestone

- [x] Verify the running movement shader contract before live activation, with Apply and Restore.
- [x] Test rapid swaps, move/resize/close overlaps and floating/tiled changes; fix demonstrated jumps.
- [x] Ship Gentle, Balanced and Playful motion packs with coordinated stock desktop timing.
- [x] Add compositor output feedback and publish nested submission evidence separately from shader/capture timing.
- [ ] Collect physical DRM presentation and mixed-output evidence on an experimental login session.
- [x] Add deterministic mixtures of built-in fragment shapes with finished presets.
- [x] Publish portable settings, faithful showcases, support limits and regression coverage.

Resize and experimental movement remain explicit choices. Later, build
pointer-driven wobble on the validated motion foundation (Epic 4).

## Coordinated action sets milestone

- [x] Ship Fragments, Ribbons and Elastic sets with stock open/close and desktop timing.
- [x] Suggest matching resize and movement in the existing Studio and CLI, with separate opt-in.
- [x] Publish base, resize-only and experimental examples with faithful shader and native showcases.
- [x] Verify import, editing, Undo, shell exports and native endpoints; document action limits.

## Library and action combos milestone

- [x] Open on recommended looks, favorites and saved profiles, with Studio in the same app.
- [x] Choose one shared style or separate opening, closing and optional resize/movement styles.
- [x] Keep the same combo builder online, with portable JSON/config exports and browser-local profiles.
- [x] Share reviewed Apply/Restore across standalone, iNiR and connected Noctalia configurations.
- [x] Validate optional compact iRiS and Noctalia entries and accurate iRiS active-selection feedback.
- [x] Record the combo workflow and publish its guides and online interface.
- [x] Manage saved profiles with copy, rename and removal, explicit replacement
  choices, edit conflict detection and JSON transfer between local and online Studio.

## Polished combo previews and 0.17 release milestone

Goal: make finished combinations easy to compare, choose and install.

- [x] Preview a whole combo with one button: opening, a pause and closing,
      using each action's own style and duration.
- [x] Include selected resize and experimental movement previews, with accurate
      support labels, a stable variation and cancellation when settings change.
- [x] Respect reduced motion and keep playback separate from editing, Undo and Apply.
- [x] Refine five existing recommended combos: Fragment Flow, Soft Landing,
      Ribbon Current, Playful Motion and Geometric Flow, with fragments first.
- [x] Publish complete-cycle showcases and portable JSON for all five combos.
- [x] Test the actual 0.16-to-0.17 upgrade with saved JSON, favorites, shell entries
      and exact Restore in isolated configurations.
- [ ] Publish the signed 0.17 prerelease, its packages, checksums and upgrade guide.

Pointer-driven wobble is the next major FX milestone after this release (Epic 4).

## Released foundation

- [x] Stock Niri opening and closing effects, standalone setup and shell adapters.
- [x] Independent open/close pairings and explicitly enabled resize profiles.
- [x] Eight fragment shapes, four shape presets and their showcases in 0.12.0.
- [x] Experimental tile/column movement, swaps and velocity-preserving retargets.
- [x] Searchable gallery, Studio, terminal workflow and reversible setup snapshots.
- [x] Curated collections shared across browsing interfaces and ten finished pairings.

## Epic 1: general window movement

Goal: make movement a distinct, well-tested action with useful finished looks.

- [x] Add Fragment Wake, Ribbon Transfer and Momentum Glide presets.
- [x] Preview the actual movement shader in Studio with directional controls.
- [x] Edit an independent movement action and preserve it in portable profiles.
- [x] Keep movement out of stock exports; support profiles in the isolated demo.
- [x] Exercise horizontal and vertical rearrangement, consuming/expelling windows,
      insertion/removal and simultaneous resize/movement.
- [x] Record native movement and swap examples, including reversals.
- [x] Publish measured costs and explicit compositor/renderer requirements.
- [x] Detect movement configuration support and distinguish the tested executable
      from the running compositor in `doctor`.
- [x] Verify the running movement shader contract before offering live activation;
      parser acceptance alone is insufficient.

## Epic 2: shaped and expressive resize

Goal: extend the shape vocabulary to size changes while keeping borders and
endpoints reliable. Every built-in style keeps resize off unless a separate
resize profile is explicitly applied.

- [x] Reuse triangle, hexagon and silhouette geometry in the resize renderer.
- [x] Add finished Edge Rebuild and Soft Reflow profiles with shapes.
- [x] Expose only resize-relevant controls in Studio.
- [x] Verify growth/shrink, transparent source ownership, extreme proportions,
      stable identities and zero-strength behavior.
- [x] Check repeated resize, close-during-resize and fullscreen interruptions.
- [x] Publish comparisons, native recordings and GPU measurements.
- [ ] Investigate a physical resize-edge anchor where the compositor exposes it.

## Epic 3: continuous transitions

Goal: retain visual direction and state when actions overlap.

- [x] Preserve movement phase, seed, direction and sampled position velocity in
      the pinned experimental build.
- [x] Continue an interrupted opening or movement while fading a closing window.
- [x] Expand coverage to move/resize/close combinations and vertical layout changes.
- [ ] Fix discontinuities demonstrated by those scenarios and add regressions.
- [ ] Investigate velocity continuity across interrupted resize transitions.
- [x] Test floating/tiled changes with resize/open/close overlap fixtures.
- [ ] Test physical mixed outputs and output removal.
- [ ] Investigate acceleration continuity and shared swap transactions.
- [ ] Evaluate particle-level ordering across windows and conservative damage bounds.

Current guarantees and their limits are in [native movement](docs/movement.md).
A clean endpoint test is not evidence of uninterrupted velocity.

## Epic 4: pointer-driven wobble

Goal: responsive, Compiz-inspired deformation tied to actual dragging.

- [ ] Design a grab-point anchor and a pointer-driven deformation state.
- [ ] Keep visual deformation separate from input hit testing and layout ownership.
- [ ] Preserve state through drag cancellation, release and tiling transitions.
- [ ] Add gentle wobble, rubber-sheet and release-settle presets.
- [ ] Measure input latency and frame times in a nested compositor.
- [ ] Add reduced-motion behavior and ordinary-renderer fallback.

This requires further compositor work. Existing timed Elastic effects do not
simulate dragging.

## Epic 5: workspace, camera and overview motion

Goal: a coherent sense of motion across the desktop.

- [x] Curate opt-in stock timing/spring profiles for workspace switching,
      horizontal camera scrolling and overview zoom.
- [x] Keep camera motion separate from individual window movement effects.
- [ ] Design an experimental workspace rendering hook with gesture reversal.
- [ ] Prototype a restrained depth slide, wave sweep and slice transition.
- [ ] Preserve clipping, capture restrictions, multiple outputs and input behavior.
- [ ] Evaluate fullscreen and overview entry/exit as separate transition paths.
- [x] Record native stock workspace, camera and overview demonstrations.
- [ ] Establish physical compositor presentation budgets for these transitions.

Stock Niri exposes timing for these actions, not the same custom shader interface
as opening, closing and resizing. See [Niri's animation documentation](https://niri-wm.github.io/niri/Configuration:-Animations.html).

## Epic 6: performance and broader desktop validation

- [ ] Collect integrated-GPU results and several output sizes/refresh rates.
- [x] Collect native submission/presentation feedback separately from WebGL shader cost.
- [ ] Validate physical DRM feedback and report the workload and presentation flags.
- [ ] Test simultaneous effects, fractional scaling and physical mixed monitors.
- [ ] Add quality choices only where measurements demonstrate a useful tradeoff.
- [ ] Expand capture, popup, decoration and graphics-reset acceptance.

Published results and reproducible commands remain in the
[performance guide](docs/performance.md) and [validation record](docs/validation.md).

## Epic 7: custom silhouettes and curated profiles

- [x] Add deterministic mixtures of selected built-in shapes.
- [ ] Prototype one closed SVG outline, simplified at import time with bounded
      shader complexity. Filters, strokes and compound artwork remain out of scope.
- [x] Curate coordinated Fragments, Ribbons and Elastic motion profiles as actions
      become supported; preserve explicit resize and movement choices.
- [x] Give each new visual behavior an importable example and faithful showcase.

See [fragment shapes](docs/fragment-shapes.md) and [action profiles](docs/profiles.md).

## Epic 8: shell integration and future compositor ports

Shells and compositors are different integration targets. iNiR/iRiS, DMS,
Noctalia, Quickshell and GTK pickers use NiriFX's Niri backend today. Waybar needs
only the standalone path.

- [ ] Validate full shell embedding of reusable Quickshell and GTK/Astal components.
- [ ] Assess Caelestia on a maintained Niri setup, then an ML4W Niri-session adapter.
- [x] Document the reusable effect/preset model and compositor-specific rendering
      inputs without introducing an unused generic backend framework.
- [ ] After the Niri motion milestones, assess one Hyprland effect as a small port
      experiment: textures, coordinates, progress, transparency and damage first.
- [ ] Evaluate plugin/version maintenance and capture/input behavior before any
      broader Hyprland support commitment.
- [ ] Add another backend only when a working prototype justifies its abstractions.

Shader math and preset descriptions can be reused. Window textures, animation
lifecycle, interruption state, damage and configuration belong to each compositor;
Wayland is not a portable window-effects plugin API. Hyprland's
[C++ plugin interface](https://wiki.hypr.land/Plugins/Development/Getting-Started/)
is a possible research path, not a drop-in Niri shader loader. No Hyprland backend
is being implemented in the current release. See [portability boundaries](docs/architecture.md#compositor-portability).

## Contribute a result or an idea

[Open an issue](https://github.com/jturbide/niri-fx/issues) with the setup, desired
behavior and a reproducible example. Reports from different GPUs and monitor
arrangements are useful. [Contributing](CONTRIBUTING.md) covers checks; the
[design notes](docs/next-phases.md) explain the engineering questions.
