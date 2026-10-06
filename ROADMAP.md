# NiriFX roadmap

NiriFX focuses on finished effects and coherent motion for Niri. Choose a preset,
apply it, and customize when useful. Niri remains the primary compositor; other
backends are research candidates, not current compatibility claims.

Checklists describe concrete deliverables. Checked items have shipped or have
recorded validation; unchecked items are still planned or in development. The
priorities below guide sequencing; epics group related work without release dates.
See [available features](README.md),
[release history](CHANGELOG.md) and [validation limits](docs/validation.md).

## Next priorities

1. **Validate shared settings in daily use.** One normal Niri configuration and
   one saved recipe now feed stock and full-session effects. Verify shell-driven
   edits, normal updates and recovery on physical desktops before broadening
   support claims; keep frozen recovery available.
2. **Prove everyday session reliability.** Prioritize mixed monitors, capture
   privacy, suspend/resume and recovery. Resolve the remaining stale-output probe
   and verify real PipeWire capture before expanding desktop support claims.
3. **Deliver one supported installation and update path.** Package the app,
   full compositor and login entry for an initial declared distribution and
   architecture; verify clean install, upgrade, rollback and return to stock Niri.
4. **Keep delivering focused 0.x releases.** 0.20 brings the integrated session
   tools and shared settings together; 0.21 adds complete recipe portability.
   Follow with reliability and installation improvements in later 0.x releases.
   The 1.0 contract stays a separate milestone after its acceptance gates pass.

New presets should demonstrate a distinct useful look, with importable settings
and a faithful showcase. More shells, workspace shaders and compositor ports
follow the core controls and reliability work below.

## Release milestones

- [x] Publish [0.20.0 tools](https://github.com/jturbide/niri-fx/releases/tag/v0.20.0)
      with shared settings, integrated session management, independent Swap choices,
      current guides and verified upgrade/recovery. Native binary and physical
      desktop acceptance remain separate gates.
- [x] Deliver [complete portable recipes in 0.21](#021-target-complete-portable-recipes),
      with action styles and continuous-fragment response preserved together,
      installed upgrade checks and [migration guidance](docs/upgrading.md#from-020-to-021).
- [ ] Use subsequent 0.x releases for physical reliability and supported packaging;
      publish tested environments and remaining limits with each release.
- [ ] Complete the [1.0 acceptance criteria](docs/stability.md#acceptance-criteria-for-10)
      before freezing the supported API. There is no scheduled jump to 1.0.

### 0.21 target: complete portable recipes

- [x] Define one versioned recipe for action modes, desktop springs, pointer wobble
      and explicit continuous-fragment values; built-in preset updates must not change saved values.
- [x] Preserve existing document meanings and migrate retained 0.20 recipes with
      matching Python/browser validation, units, bounds and rejected-input fixtures.
- [x] Keep the complete recipe through JSON download/import, share links, My profiles,
      copying, reopening and Undo/Redo in local and online Studio.
- [x] Offer Gentle, Tear and Cascade first, with detailed response controls secondary
      and a clear explanation that the canvas does not simulate continuous response.
- [x] Define Move Preserve/Style/Off, material edits and Pointer wobble interactions
      without silently losing response settings or enabling another action.
- [x] Use existing shared/frozen review, Apply and recovery paths; refuse unsupported
      native activation and keep stock exports compatible without losing portable data.
- [x] Verify an installed 0.20 upgrade, complete browser/local round trips, stale-review
      refusal and exact recovery. Publish importable examples and a faithful showcase.

## Available foundation

Stock open/close/resize effects, standalone setup, shell adapters, the shared
Library and online Studio are available. Profiles support independent Preserve / NiriFX Style / Off choices,
curated combinations, favorites, saved JSON and reviewed Apply/Restore.
Movement, swaps and pointer deformation use the full NiriFX session, currently
available through the source installation workflow. See [current support](docs/compatibility.md), [the catalog](docs/catalog.md)
and [release history](CHANGELOG.md) for delivered features and version details.

## Next release and motion continuity

Interrupted resize geometry retains size velocity independently per axis. The
development renderer also coordinates minimum-size limits with neighbors and
retains NiriFX deformation across retargets. Closing has a separate handoff and
acceptance boundary.

- [x] Retain active resize timing across reloads; apply new timing to new axes.
- [x] Publish native orthogonal-retarget and timing-reload comparisons.
- [x] Share constrained resize displacement with affected neighbors at the minimum
      size, including simultaneous resizes and source removal.
- [x] Retain resize material, deformation phase and shader identity through
      retargeting and reloads, with independent content updates and capture targets.
- [x] Continue resize through closing with separate decoration and privacy
      snapshots; compare the first closing frame within the documented
      [rasterization bounds](docs/validation.md#resize-to-close-acceptance-020).
- [x] Fix virtual-device disconnection and overlapping button ownership, retaining
      the unmodified pinned-Niri baseline comparison (Epic 4).
- [ ] Resolve the remaining stale-output failure and verify physical device removal.
- [ ] Collect physical capture/presentation and another GPU result before adding
      performance-driven quality choices (Epic 6).
- [x] Verify the 0.18-to-0.19 installed upgrade, preserved user data and exact
      Restore, including partial and all-Off profiles.
- [x] Verify upgrades from published 0.19 with active Preserve/Off choices,
      conflict-aware Restore and first-use Library flows through iNiR/iRiS.

## Updates and native build lifecycle

Goal: use NiriFX without blocking normal Niri or shell updates. Stock effects
use external configuration. Native features need a separately maintained
compositor build with an explicit upgrade path.

### One integrated product

NiriFX is one product. The full session includes every supported compositor
feature; users choose effects and action modes, not patch variants. Stock-Niri
configuration remains a lightweight compatibility path. Reduced-feature builds
are developer regression controls, not separate consumer editions.

- [x] Provide one full-feature desktop build command with required regressions.
- [x] Review and install a finished full build, configuration snapshot and
      next-login selection together; retain administrator login-entry registration
      until packages provide it.
- [ ] Install the NiriFX app, full compositor and login entry through one supported
      package workflow, keeping stock Niri available.
- [x] Detect a verified managed session before shell adapters and present direct
      per-action preset choices with immediate previews.
- [x] Apply reviewed effects and same-build rollback directly to the running
      managed session, with configuration-load confirmation and next-login storage.
- [x] Share normal user/shell settings beneath generated stock/native effect
      projections, preserving one saved combo and continuous-fragment response.
      Studio and CLI review source ownership, both validators and all affected
      files; stale review and handled validation failures preserve prior settings.
- [x] Keep independent frozen recovery for missing or invalid shared settings.
      Shared rollback restores an earlier recipe over current desktop settings;
      frozen recovery selects retained settings for next login without changing
      the shared source. Distinguish file updates from verified live activation.
- [ ] Verify shared configuration with shell-driven edits and updates on physical
      desktops, including cross-version parser conflicts and return to stock Niri.
- [x] Present recommended combos and per-action presets first; keep configuration
      paths, compositor build identities and technical controls in advanced details.
- [x] Identify the loaded Studio version and UI build in local, web and offline
      modes, with update guidance separate from compositor identity.
- [x] Offer the same preset/action choices through CLI and agent discovery.
- [x] Share verified live Apply and rollback between Studio, CLI and agents,
      binding each desktop reload to its reviewed session and configuration.
- [x] Version a portable session recipe carrying continuous-fragment controls,
      with import/export in local and online Studio. Schema 4 retains response
      values and action modes; older documents keep their meaning and unsupported
      builds refuse activation. Included in 0.21.
- [x] Make Download JSON, Share settings and My profiles retain the same complete
      recipe, including dormant response values while Move is preserved or Off.
- [x] Verify independent Move and Swap choices through explicit compositor action
      routing, portable profiles, Studio previews, reviewed Apply and old-build refusal.
- [ ] Extend independent Swap to additional exchange gestures only when their
      action boundaries can be identified reliably; keep ordinary dragging and
      column reordering on Move in the meantime.
- [ ] Verify physical login, shell startup, capture, input, suspend and rollback
      for the declared package targets before advertising desktop support.
- [ ] Publish the installation/support matrix with exact known limits, without
      presenting every integrated feature as a separate experiment.

### Shell integration

- [x] Retire new installation of the source-patched iRiS entry; keep the app and
      external registry as the supported access path.
- [x] Provide reviewed removal of the earlier entry, preserving upstream and
      unrelated edits and refusing ambiguous or customized files.
- [x] Load the iNiR serializer without writing bytecode into its checkout;
      verify read-only inspection against complete temporary-tree snapshots.
- [ ] Test supported shell upgrades with active profiles, changed helper
      contracts and exact Restore while keeping their checkouts unchanged.
- [ ] Add an external iNiR widget or upstream settings extension for one NiriFX
      entry; avoid maintaining a local settings-page patch.

### Native build identity and compatibility

- [x] Record versioned build identity, ordered patch hashes, locked dependencies,
      toolchain, target, profile and enabled features; inspect artifacts read-only.
- [x] Build changed patch stacks into fresh candidate directories without
      overwriting the working or previous build.
- [x] Pin an upstream compatibility matrix and check clean application of all
      patch stacks in CI, with compilation and native regressions for the full build.
- [ ] Separate upstream compatibility failures from user updates; offer only
      candidates that pass the declared release gates.
- [ ] Evaluate narrow upstream contributions for rendering hooks and shell
      extension points, with no dependency on their acceptance.

### Installation, selection and rollback

- [x] Present retained-bundle status, review and next-login rollback through the
      existing CLI without a background configuration manager.
- [x] Add the same native-session review and rollback controls to Studio.
- [x] Prepare a per-user systemd login launcher that pins a selected pair,
      preserves the stock service lifecycle and handles stale leases.
- [ ] Package a distinctly named compositor and NiriFX login session alongside
      stock Niri, including desktop features, portals and service lifecycle.
- [x] Review self-contained candidate configuration separately, keeping unsupported
      native nodes out of the stock-session configuration.
- [x] Select updates for the next login; retain the previous binary/config pair
      and never restart a running compositor from a background updater.
- [x] Import literal include trees into isolated candidate configuration with
      per-file review, preserved ordering and retained missing-optional state.
- [x] Connect Studio settings to a reviewed candidate-editing workflow without
      changing stock config ownership or editing retained bundles.
- [ ] Let supported shell extensions open that same Studio workflow without
      introducing another settings writer.
- [x] Show retained-bundle storage sizes and distinguish the advertised running
      session from next-login and rollback selections, with explicit unknown states.
- [ ] Provide reviewed cleanup that preserves all running, selected and rollback
      versions; a single advertised IPC session is insufficient to authorize removal.
- [ ] Verify failed install, interrupted update, changed shared dependencies,
      rollback and return to stock on supported physical desktops.
- [ ] Publish signed artifacts and source/patch provenance for declared
      distributions and architectures without holding normal system updates.

### Coherent tool upgrades

Goal: update CLI, Studio and the login launcher together, retaining a working
version for recovery. The [managed tool workflow](docs/tool-updates.md) migrates
existing entries once, then switches their shared runtime selection.

- [x] Review installed tool versions, launcher ownership and supported bundle
      formats in one update plan.
- [x] Review an installed persistent replacement runtime and validate selected,
      rollback and baseline bundles before changing launcher references.
- [x] Update owned CLI, Studio and login references through one recoverable
      transaction; refuse stale plans and externally changed entries.
- [x] Retain the previous runtime and provide reviewed rollback, including
      recovery from interrupted display-manager registration.
- [x] Verify temporary-account adoption, installed runtime upgrades, incompatible
      receipts, interrupted registration and rollback without desktop activation.
- [x] Show local Studio installation status and a save-and-reopen notice after
      shared tool selection changes; cover same-version updates, rollback,
      prepared migration, source installs and unavailable metadata without losing edits.
- [ ] Include environment creation, shared tool setup and login registration in
      supported distribution packages and an accessible update UI.
- [ ] Verify the migrated login entry on supported physical desktops, including
      system Python upgrades and return to stock Niri.

The [desktop update guide](docs/desktop-updates.md) separates current tools
from this planned package/session workflow. Build identity is not runtime or
physical acceptance; the native capture and input gates remain required.
Native release candidates follow the [distribution checklist](docs/releasing.md#native-release-candidates)
before being advertised as supported downloads.

## Consistent action selection

Goal: choose Preserve, a style or Off independently for each supported action.
Updated builds distinguish explicit left/right swaps from normal movement. Preserve inherits the
configuration underneath NiriFX, including existing user or shell customizations.

- [x] Define Preserve / Style / Off for opening, closing, resize, movement and
      pointer drag, including migration of existing profiles without changing behavior.
- [x] Represent the same choices in portable JSON, the CLI and Studio, including
      previews, shared styles, per-action controls and Undo.
- [x] Carry the choices through stock/native exports and supported shell adapters,
      preserving unrelated settings and reporting unavailable compositor features.
- [x] Verify reviewed Apply and exact Restore for partial profiles and all-off
      profiles, with examples and complete workflow coverage.
- [x] Verify a clean installation through Library selection, per-action choices,
      reviewed Apply and Restore, and make this path consistent across setup guides.
- [x] Clarify pointer controls in Studio: Off disables whole-window wobble, while
      continuous fragments follow Move. Explain this relationship beside the
      controls and show how to disable the currently active drag effect.

## Faster feedback for contributors

CI already selects expensive checks using reviewed file groups and caches pip/npm
downloads. Documentation-only changes skip rendering; renderer, shared-contract,
release and unknown changes retain the full suite. Full renderer runs still have
expensive software-WebGL matrices.

- [x] Record rendering-matrix and editor/save-stage timings.
- [x] Split independent rendering matrices across isolated CI jobs, with one
      required aggregate check that rejects missing or failed results.
- [x] Compare the same workload locally, retaining endpoint, intermediate-frame,
      export-parity and save-flow coverage.
- [x] Measure hosted runner elapsed time with separate timings for each rendering job.
- [ ] Inspect failed-shard diagnostics on a hosted rendering failure.
- [x] Harden browser startup diagnostics and cleanup: terminate owned helper
      processes, distinguish process exit from open pipes, and retain the original
      startup error when cleanup also fails.
- [x] Keep Library save and Apply workflow checks free of unnecessary preview
      playback, while retaining full animation coverage in rendering checks.
- [x] Bind Studio workflow, combo and pointer recordings to their original loaded
      preview; reject changed inputs and retain existing media when verification fails.
- [ ] Extend loaded-preview provenance binding to the generic shader-gallery
      recorder while retaining current-source checks.

## Stable 1.0 acceptance

NiriFX remains in 0.x development. The future 1.0 release will define a supported
public contract with backward compatibility throughout 1.x; incompatible changes
to that contract require a new major version. Features and internal implementation
can continue evolving. There is no release date or interface freeze yet.

The [stability policy](docs/stability.md) defines the proposed scope and detailed
acceptance criteria. The release checklist is:

- [ ] Publish exact stable interfaces, experimental boundaries and support policies.
- [ ] Complete versioned document and CLI/JSON fixtures for the declared public interface.
- [ ] Prove upgrades preserve user data, configuration and Restore history.
- [ ] Verify review, ownership, failure recovery and compositor capability checks.
- [ ] Pass the declared environment/adapter matrix and publish its tested limits.
- [ ] Release matching signed sources, packages, documentation and migration guidance.

Research epics need not all be complete for a stable stock-Niri core. Any native
feature advertised as stable must meet its own input, capture and runtime gates.

The initial [0.19 compatibility corpus](docs/stability.md#starting-compatibility-corpus-019)
records document migration, action semantics and representative CLI JSON responses.
It is a tested starting point; completing the supported interface inventory and
upgrade matrix remains part of the unchecked gates above.

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
endpoints reliable. Built-in styles preserve existing resize behavior; applying
a profile that selects resize changes it.

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
      the NiriFX compositor.
- [x] Continue an interrupted opening or movement while fading a closing window.
- [x] Expand coverage to move/resize/close combinations and vertical layout changes.
- [ ] Fix discontinuities demonstrated by those scenarios and add regressions.
- [x] Preserve per-axis size velocity during tested interrupted resize transitions.
- [x] Retain active-axis timing through configuration reloads and reject invalid sizes.
- [x] Coordinate minimum-size constraints across neighboring windows.
- [x] Retain resize material, deformation phase and capture-target state through
      retargets, with a separate content-update clock.
- [x] Carry retained resize material and geometry through closing without applying
      deformation twice or stretching decorations; test opening/movement overlap.
- [x] Test floating/tiled changes with resize/open/close overlap fixtures.
- [ ] Test physical mixed outputs and output removal.
- [ ] Investigate acceleration continuity and shared swap transactions.
- [ ] Evaluate particle-level ordering across windows and conservative damage bounds.

Current guarantees and their limits are in [native movement](docs/movement.md).
A clean endpoint test is not evidence of uninterrupted velocity.

## Epic 4: pointer-driven wobble

Goal: responsive, Compiz-inspired deformation tied to actual dragging.

### First native prototype

- [x] Add a grab-point anchor and bounded spring state driven by actual pointer motion.
- [x] Keep deformation separate from input hit testing and layout ownership.
- [x] Carry spring state through release and repeated grabs; verify tiled/floating transitions.
- [x] Offer Gentle, Rubber Sheet and Release Settle in the isolated demo, with example configurations.
- [x] Exercise real drag, reversal, release, close and disabled-effect paths with synthetic clients.
- [x] Record native showcases and publish the tested compositor/renderer requirements.
- [x] Respect disabled animations and retain the ordinary-renderer fallback.

Try the [pointer controls](docs/pointer-wobble.md). Native checks and their scope
are recorded in the [validation guide](docs/validation.md#pointer-driven-wobble).

### Integration and broader acceptance

- [x] Add pointer settings to portable profiles and Studio, with preset-first controls.
- [x] Add capability-verified standalone Apply/Restore and NiriFX session exports.
- [x] Test pointer-only, combined movement and disabled profiles against the running renderer.
- [x] Add native-math pointer playback to combo previews, with clear native support limits.
- [x] Add interactive dragging, keyboard demo playback and reduced-motion behavior in Studio.
- [x] Publish portable pointer combos and browser showcases with reproducible input traces.
- [x] Test destination-output loss, last-output loss and restoration during tiled/floating
      grabs in the native layout suite, including release and spring cleanup.
- [x] Check direct ScreenCapture privacy during rule changes, dragging and closing, with visible controls.
- [x] Test abrupt exit of grabbed tiled/floating clients and subsequent survivor input.
- [x] Compare held-button virtual-pointer disconnection and stale output with unmodified pinned Niri.
- [x] Compare overlapping virtual-pointer devices, ownership changes and same-button
      releases against unmodified Niri; distinguish surviving grabs from stale state.
- [x] Track button ownership per device so disconnect cleanup retains another
      device's valid presses and grabs, including overlapping button codes.
- [x] Verify virtual-device destruction, consumed bindings and reused device
      identities through the native input path.
- [ ] Verify physical device removal and reconnection during grabs.
- [ ] Resolve stale parent output in the strict two-compositor capture probe, including the effects-disabled baseline.
- [ ] Validate Output/Screencast privacy and actual PipeWire capture, including popups and blurred backgrounds.
- [ ] Verify physical output hotplug, mixed monitors and graphics-reset recovery.
- [x] Report input acknowledgements and nested output submissions separately.
- [ ] Measure physical input-to-photon latency and presentation across mixed outputs.

Timed Elastic effects remain available on stock Niri. Pointer-driven deformation
requires additional compositor support and starts in the isolated experiment.

### Continuous fragment motion

- [x] Drive eligible square fragments from persistent window motion during dragging
      and timed movement, retaining state through pause, reversal, release and regrab.
- [x] Verify long drags beyond the placement timer, interior breakup, stable
      reconstruction, timed moves and column reordering in an owned native session.
- [x] Verify that distant pieces initially retain their screen positions while
      the grabbed piece follows the pointer, then catch up and reconstruct.
- [x] Expand pieces on press without requiring pointer movement; keep the held
      pose stable and reconstruct after a press that never becomes a drag.
- [x] Verify per-piece delay and response with distinct nearby and far trajectories,
      a measurable waiting interval, queued reversals and bounded release.
- [x] Expose bounded native controls for delay, response, variation, press spread,
      pinning, rotation, tilt and release.
- [x] Add Gentle, Tear and Cascade presets and an isolated comparison window.
- [x] Verify preset reloads during holding and release, immediate Off, and bounded
      fallback for grids that exceed the renderer budget.
- [x] Measure release-mode CPU state costs through 4096 cells and recovery after
      simulated long idle; preserve motion when skipping redundant settled updates.
- [x] Verify ordinary input fallback after shader compilation failure and recovery
      after a valid reload, with display-renderer verification before fragment input.
- [x] Verify direct ScreenCapture restrictions during motion, release and closing,
      including live rule changes, interrupted clients and removed pointer owners.
- [x] Measure dense-history CPU recovery separately from synthetic history-capacity stress.
- [x] Verify independent materials, reconstruction and input during two- and
      four-window motion, including reversal and a subsequent single-window move.
- [x] Measure hardware GPU drawing for one, two and four continuous fragment
      meshes at 1080p and 4K, with visible contribution checks and explicit scope.
- [ ] Measure native buffer preparation, uploads and presentation, and collect
      additional GPU results before raising the particle limit.
- [ ] Reduce dense-history recovery spikes after 2–4 second pauses while preserving
      queued motion and release continuity; repeat CPU and native acceptance checks.
- [ ] Verify fragment recovery after renderer recreation and physical suspend/resume.
- [ ] Verify Output/Screencast privacy and actual PipeWire capture.
- [ ] Test the fragment path on a physical desktop, including capture restrictions,
      mixed outputs and input behavior before expanding its supported configurations.
- [x] Select Gentle, Tear and Cascade in local Studio's native target and retain
      the choice in managed bundles, with reviewed Apply and rollback.
- [ ] Carry continuous response in portable recipes and expose its bounded controls
      in Studio, with independent action choices and faithful drag previews.
- [ ] Tune per-piece motion through manual testing, including grab distance,
      travel direction, variation, tilt and acceleration toward the released
      window's resting position.
- [ ] Evaluate additional shapes and interactive resize after the square prototype.

The [continuous fragment prototype](docs/fragment-drag.md) defines the initial
scope, fallback behavior and focused checks. Physical desktop acceptance remains open.

## Epic 5: workspace, camera and overview motion

Goal: a coherent sense of motion across the desktop.

- [x] Curate stock timing/spring profiles for workspace switching,
      horizontal camera scrolling and overview zoom.
- [x] Keep camera motion separate from individual window movement effects.
- [ ] Design an experimental workspace rendering hook with gesture reversal.
- [ ] Prototype a restrained depth slide, wave sweep and slice transition.
- [ ] Explore directional window parallax: vary visual depth and follow-through
      with window or camera movement, allowing brief visual overlap, delayed
      motion and a wobble as windows settle into place.
- [ ] Test parallax reversals and interruptions without jumps, preserving focus,
      input, capture restrictions and final layout; provide bounded strength,
      delay and settling presets.
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

## Epic 9: agent and automation integration

Goal: let agents choose, customize and apply effects through the same validated
contracts as the app, with clear ownership and reversible changes.

- [x] Publish machine-readable command discovery, compact catalog summaries and canonical parameter bounds.
- [x] Bundle a reusable agent skill and document example prompts, review fingerprints and conflict-aware Restore.
- [x] Add contributor guidelines and test discovery, composition, installed resources and temporary-config Apply/Restore.
- [ ] Assess a thin MCP adapter when a client needs access without terminal tools.
- [ ] For any MCP adapter, fix configuration paths at startup and reuse capability checks, reviewed plans and Restore.
- [ ] Add client interoperability checks before advertising support for a specific agent integration.

Start with the [agent guide](docs/agents.md). There is no separate MCP service to
install for terminal-capable agents.

## Contribute a result or an idea

[Open an issue](https://github.com/jturbide/niri-fx/issues) with the setup, desired
behavior and a reproducible example. Reports from different GPUs and monitor
arrangements are useful. [Contributing](CONTRIBUTING.md) covers checks; the
[design notes](docs/next-phases.md) explain the engineering questions.
