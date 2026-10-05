# Changelog

User-visible changes are recorded here under Added, Changed, Fixed or Removed.
New work goes in **Unreleased**; dated entries are frozen when a release is made.
Versions follow `MAJOR.MINOR.PATCH`; while 0.x, minor versions may change the
prototype's interfaces. Migration notes accompany compatibility changes.

## Unreleased

### Added

- Studio's NiriFX session target prepares reviewed effect changes for the next
  login. It retains the previous binary/configuration pair, reopens saved recipes
  and reviews rollback separately. Independent action choices and Gentle, Tear
  and Cascade continuous-fragment presets use the retained build. Session and
  file details are collapsed behind the main preset controls.
- `native install --candidate DIR --config FILE` prepares the full desktop build,
  configuration snapshot, NiriFX login entry and next-login selection in one
  reviewed transaction. Display-manager registration remains an administrator
  step until distribution packages provide it. Shell sources and the running
  session stay unchanged.
- `native configure` exposes the same immutable preset editing through the CLI
  and agent discovery, with exact review fingerprints and retained rollback.
- One `build-nirifx-session.py` command builds all compositor features with
  desktop support, release optimization and focused regressions. A pinned native
  compatibility matrix and isolated patch/build checks separate
  upstream port failures from desktop updates. The native release checklist
  covers dependency-aware packages, provenance, rollback and physical acceptance
  before compositor binaries are advertised as supported downloads.
- `native status` distinguishes the advertised running session from next-login
  and rollback selections, and reports each retained bundle's file and allocated
  storage sizes. Missing selections stay visible. `--offline` skips IPC; status
  never executes a candidate or changes desktop settings.
- `native stage --snapshot-includes` imports split Niri configurations into a
  closed, verified bundle while preserving include order and file boundaries.
  Review covers every source, including absent optional files. Login entries
  support custom names, and `doctor` reports continuous-fragment capability
  separately from timed movement.
- `native stage`, `status`, `select`, `rollback` and `session-entry`
  commands prepare retained desktop binary/configuration pairs and reviewed
  next-login selection. The per-user systemd launcher preserves the stock Niri
  service lifecycle, pins one pair per login and falls back to stock for expired
  leases. Display-manager registration remains an administrator step; physical
  desktop acceptance and distribution packages are still pending.
- Isolated native build candidates preserve earlier source trees, Cargo outputs
  and executables. Successful attempts publish their own manifest and copied
  binary; explicit per-variant selection lets native tests use a candidate
  without changing the login session or legacy demo selection.
- A reviewed migration removes the earlier compact iRiS source integration
  without discarding newer upstream changes. Customized or ambiguous files are
  preserved for manual review.
- Native build identity records the ordered patch stack, locked dependencies,
  toolchain, target and features. A read-only inspector checks artifact identity
  and desktop build prerequisites without starting or installing a compositor.
- Continuous square-fragment motion for pointer dragging, timed
  movement and column reordering. Distant pieces initially lag behind the grabbed
  region, then catch up with per-piece delay and response variation. Pressing can
  expand the material before moving; held pauses keep that spread, and release
  reconstructs the window. Native controls expose timing, variation, spread,
  pinning, rotation, tilt and release. Focused native acceptance verifies
  screen-position retention, independently delayed pieces, queued reversals,
  long floating and tiled drags, stable endpoints and client input. Physical
  desktop acceptance remains separate.
- Gentle, Tear and Cascade presets for continuous fragment motion, with
  a local comparison window, preset buttons and keyboard shortcuts. Validated
  native controls share one canonical definition. Settings and grid changes wait
  until the active motion has settled; Off takes effect immediately. Unsupported
  grids use protected fallback without repeated per-frame preparation.
- Native fragment checks cover shader failure and recovery, direct screenshot
  privacy, interrupted clients and measured CPU state costs.
- Continuous-fragment diagnostics cover simultaneous two- and four-window motion,
  dense input history and hardware GPU mesh workloads. CPU measurements expose
  remaining recovery spikes after short pauses; particle defaults and limits
  are unchanged.
- NiriFX session resize-to-close continuation retains the current material,
  deformation phase and size paths while fading out. Borders and shadows follow
  the changing geometry; each capture target owns a separate frozen material.
- Installed upgrade checks accept the published 0.19 package, including active
  Preserve/Off choices. CLI and Library Restore must retain their recovery history
  and refuse external edits before recovering the original files exactly.
- NiriFX session resize effects retain their deformation phase, piece layout and
  current material across repeated size changes. Client content updates on a
  separate clock; shader replacements take effect on the next resize episode.
  Output and capture targets keep separate material caches and respond to
  changes in capture restrictions.
- Native before/after comparisons for minimum-size width and height retargets
  and retained fragment and triangle resize effects.
- A versioned 0.19 compatibility corpus shared by Python and browser tests,
  covering document migration, action choices, rejected input, representative
  catalog IDs and CLI JSON consumers. This begins compatibility testing toward
  1.0; it does not freeze current 0.x interfaces.
- A clean-account first-use check for source and wheel installations, covering
  Library selection, all action modes, saved profiles, review/cancel, Apply,
  reopening Studio and exact Restore without connecting to a desktop session.
- An overlapping-pointer diagnostic covering idle-device removal, held-owner
  removal, ownership changes and shared-button releases. It reproduces the
  stale-grab failure in unmodified Niri and records the limits of global cleanup.

### Changed

- New installs use Library/Studio and external shell configuration. The optional
  iRiS source-patching installer is retired to avoid blocking shell updates;
  historical exact Restore remains available. The desktop update guide describes
  cleanup and the planned separate native package/session lifecycle.
- Setup guides lead with Library for choosing a combo and reviewing independent
  action choices, Apply and Restore. Terminal and scriptable setup remain available.
- Generated resize shaders use retained material when the native extension is
  available. Build the experimental compositor from the same checkout to use it;
  stock Niri and older experimental builds keep their existing shader behavior.
- Update the pinned checkout, Python/Node setup and Pages publishing actions.

### Fixed

- Native bundle inspection now uses the same bounded configuration scanner as
  include snapshots, so a leading byte-order mark cannot hide an external include
  in an older single-file bundle.
- Library inspection loads the current iNiR serializer without creating or
  reusing bytecode in the shell checkout.
- Continuous fragments skip redundant simulation after long idle when every
  piece is exactly at rest and no delayed motion remains, preserving existing
  motion. The CPU benchmark records both recovery and ordinary update costs.
- A fragment shader that fails compilation keeps ordinary drag handling. The
  display renderer must verify the effect before enabling fragment-specific input.
- Pointer presses and consumed bindings are tracked per device in the experimental
  compositor. Removing a pointer releases only its presses and ends its owned grab;
  another device holding the same button keeps its press until it releases.
- iNiR/iRiS registration and Library Apply encode Off using the shell's supported
  timing format, allowing mixed action choices to serialize and remain recognizable
  by its active-style matcher. Portable profiles keep their explicit Off choices.
- Minimum-size resize paths now share constrained displacement with neighboring
  windows, preventing the overlap caused by independent curves. Regressions cover
  simultaneous resizes, source removal, swaps and focus changes.
- Turning resize or all animations off finishes the shared resize paths before
  removing their source, so neighboring windows settle with the resized window.

Resize-to-close continuation requires the matching development compositor and a
marked NiriFX resize shader. Fullscreen windows and transitions, output-scale
changes and unavailable frozen material use the existing protected closing snapshot. Physical
device unplug/replug and graphics-reset acceptance remain separate validation work.

## 0.19.0 — 2026-10-04

### Added

- Independent Preserve / NiriFX Style / Off controls for opening, closing,
  resizing, movement and pointer drag in Library and Studio, with matching CLI
  choices, portable JSON, previews, shared styles and Undo.
- A recorded action-selection workflow and native comparisons for resize
  reversals, orthogonal retargets and timing reloads, with reproducible checks.
- A path to 1.0 with proposed public-interface boundaries, backward compatibility
  throughout 1.x and concrete acceptance criteria. Current 0.x interfaces remain
  under development; this does not announce a stability freeze.
- Public Discussions, GitHub Sponsors links, README badges and star history.
  CodeQL scanning and grouped weekly dependency updates complement existing
  secret scanning and push protection.

### Changed

- Profiles export schema 2. Schema 1 imports retain their behavior. Preserve uses
  the desktop configuration underneath NiriFX; Off disables the selected action.
- Experimental movement and pointer contracts advance to version 2. Explicit
  merge flags preserve sibling settings; timed movement Off no longer disables
  pointer deformation. Rebuild the matching experimental compositor before native
  activation. Stock exports continue to omit native overrides.
- CI selects expensive checks by changed paths, caches dependency downloads and
  runs independent browser/rendering matrices in parallel. A required aggregate
  rejects missing or failed checks. The same local workload measured 127.8 seconds
  sequentially and 74.1 seconds in parallel; this is not a GitHub runner benchmark.
- User guides distinguish available features and support limits from future work;
  contributor and maintainer references are grouped separately.
- Refresh affected Studio, Library, picker and native showcases for the current
  controls and compositor patches.

### Fixed

- Interrupted resizes retain per-axis size velocity and timing alongside adjacent
  tiles and columns. Unchanged axes keep their existing deadlines; reloaded timing
  applies to new transitions. Extreme negative size samples are floored before
  constructing renderer geometry, preventing a debug-build panic. Neighbor alignment
  at that floor and retained resize shader state remain separate limitations.
- Browser tests pass imported documents and geometry through protocol arguments
  rather than interpolating fixture data into executable JavaScript.

### Upgrade

Install the new wheel in the same environment and reopen Studio. Installation
preserves configuration, saved profiles, favorites, registrations and Restore
history. Saving a profile writes schema 2, which older versions cannot read.
Keep original exports for downgrades. Native activation requires a rebuilt
contract-2 compositor; installing NiriFX does not replace it.
See [upgrading from 0.18](docs/upgrading.md#from-018-to-019).

## 0.18.0 — 2026-10-04

### Added

- Interactive pointer dragging in Studio and a deterministic drag/reverse/release
  phase in complete combo previews. Both use the experimental compositor's spring
  and deformation math, with a keyboard demo and reduced-motion behavior.
- Three portable pointer example combos and browser showcases with JSON downloads.
  Browser playback previews synthetic input; live dragging still requires the
  experimental compositor.
- A pointer-wobble prototype for the pinned experimental compositor.
  Windows bend around the grab point, respond to direction changes and settle
  after release, with bounded spring motion and ordinary input/layout behavior.
- Gentle, Rubber Sheet and Release Settle drag presets, native KDL examples and
  an isolated demo with draggable synthetic cards. This optional native feature
  responds to dragging separately from Studio's timed Elastic effects.
- An optional compositor patch and separate build directory, with a dedicated
  runtime capability query and real Wayland pointer lifecycle checks.
- Three looping native pointer showcases with real return drags, exact
  configuration downloads, input acceptance results and separately labelled
  nested submission diagnostics.
- Portable pointer settings and Library controls for preset choice, strength,
  damping and frequency. JSON, saved profiles, sharing and Undo retain them;
  stock exports omit experimental nodes.
- Explicit experimental config downloads and capability-verified standalone
  pointer Apply/Restore, including combined movement and zero-strength profiles.
  `--niri-binary` selects the executable used for diagnostics and validation.
- Agent command discovery, canonical parameter metadata, compact catalog
  summaries, a packaged reusable skill and public automation/contributor guides.
- Isolated native checks for profile activation, runtime capability loss,
  stock-binary mismatch and exact Restore through the Studio backend.
- Native layout regressions for output removal and restoration during tiled and
  floating pointer drags, checking spring continuity, window ownership and settle
  cleanup. Physical monitor hotplug remains separate acceptance work.
- Isolated pointer hardening checks for direct ScreenCapture privacy during
  dragging and closing, changing privacy rules, and abrupt grabbed-client exit
  followed by clicks and dragging in a surviving client.
- An isolated unmodified Niri build and reproducible comparison of held-pointer
  disconnection and stale nested output. Both failures reproduce without FX
  patches; diagnostic results keep the remaining input/capture limits explicit.
- An installed 0.17-to-0.18 upgrade check preserving existing Library profiles,
  favorites, shell registrations and exact CLI/Library Restore histories.

### Changed

- Expand the roadmap into native-pointer acceptance, Studio/profile integration
  and physical presentation milestones, each with a concrete checklist.
- Distinguish native KDL downloads from Studio JSON in the showcase gallery.
- Refresh Library, Studio, combo and pointer recordings for the current controls.
- Verify browser pointer math against traces generated from the native Rust
  spring and retain GPL attribution for the derived browser adapter.
- Allow pointer-only portable profiles in the isolated native demo.
- Document retained grabs after held-button virtual-pointer disconnection and a
  failing optional two-compositor output probe. Keep Output/Screencast and
  PipeWire privacy separate from the tested direct ScreenCapture path.

### Fixed

- Verify current compositor support before Restore reactivates a previous native
  pointer or movement selection. Returning to stock settings remains available.
- Preserve the current profile operation when an earlier dialog's queued close
  event arrives after a new dialog has opened, including rename conflict recovery.

### Upgrade

Existing saved profiles, favorites, shell registrations and Restore history remain
supported. Pointer settings are optional profile metadata; existing profiles keep
pointer drag unset. The browser preview and agent commands are included in the
package. Live pointer deformation requires a separately built, verified native
extension and explicit activation. The compositor is not installed by the wheel.
See the [upgrade guide](docs/upgrading.md#from-017-to-018) and
[pointer validation limits](docs/pointer-wobble.md#reproduce-validation-and-showcases).

## 0.17.0 — 2026-10-04

### Added

- One-click complete combo previews with per-action styles and durations, selected
  resize/movement loops, stable variations and reduced-motion endpoints. Playback
  leaves editing, Undo and saved documents unchanged.
- Five refined recommended combos and complete opening/pause/closing showcases:
  Fragment Flow, Soft Landing, Ribbon Current, Playful Motion and Geometric Flow.
- An isolated upgrade check using the official 0.16 wheel and saved settings,
  favorites, shell registration and exact Restore, including installed Studio.
- A Library view in the existing NiriFX app, with recommended looks, collections,
  profile favorites, My profiles and a simple shared-style/per-action combo builder.
- Reviewed Apply and Restore in the local app through standalone, iNiR and
  connected Noctalia configurations. Paths remain fixed at launch, stale reviews
  are rejected and external edits are preserved.
- The same combo builder in Web Studio, with browser-local profiles and portable
  JSON/config exports. Detailed Studio controls remain in the same app.
- An optional compact iRiS entry with the NiriFX logo, active look, Choose effects,
  Customize and Restore, plus a Noctalia 5 launcher shortcut.
- Saved-profile copying, renaming and removal in the local and online Library,
  with explicit replacement confirmation and preserved favorites on rename.

### Changed

- DMS explicitly opens the standalone target. Quickshell/GTK preview dispatch
  opens detailed Studio controls and carries the selected Niri config path.

### Fixed

- Correct the validation guide's gallery total and reject stale GIF/preset
  counts in the three public showcase guides during documentation checks.
- Preserve other sessions' saved-profile edits and reject rename collisions.
  Skip damaged saved documents individually and report invalid names in the UI.
- Wait for Chrome's debugging-port file to finish writing within the bounded
  startup deadline, with regression coverage for incomplete and invalid ports.
- Enable browser lifecycle domains before startup hooks and navigation, with
  regression coverage for error capture during repeated reloads and page-target
  discovery during startup. Library checks
  wait for completed operations and use an intact preview frame while separate
  rendering checks retain intermediate-frame coverage.

### Upgrade

Install the new package to use Library and combo previews. Existing exported JSON,
favorites, shell entries and CLI Restore snapshots remain valid. Named Library
profiles and Library Apply history are new in this version. Five built-in combos
have refined settings; re-export or re-register a shell pack to refresh them.
Updating a pack does not select an active style. Resize and movement remain unset
in every built-in profile. See the [upgrade guide](docs/upgrading.md#from-016-to-017).

## 0.16.0 — 2026-10-03

### Added

- Fragments Motion, Ribbons Motion and Elastic Motion coordinated profiles, with
  opening, closing and stock desktop springs in the existing browsing flows.
- Matching resize and experimental movement suggestions in Studio, and explicit
  `profile --action-set` include flags for portable settings. Both actions remain
  unset in every built-in profile.
- An Action Sets collection, nine complete example documents and nine showcases,
  including actual nested-compositor swaps with hashed source settings.

### Fixed

- Update the Studio suggestion label immediately when its action is enabled.
- Sample both sides of native swap crossings instead of requiring unchanged
  solid colors at an occluded or blended midpoint.

### Upgrade

Update NiriFX, then re-register or re-export shell packs to add the three profiles.
Existing presets, document schemas and the experimental compositor patch are
unchanged. Built-in sets leave resize and movement unset; optional example files
state which actions they include. Updating registration does not activate a style.


## 0.15.0 — 2026-10-03

### Added

- Gentle, Balanced and Playful desktop motion profiles with stock workspace,
  camera and overview springs; select them in existing browsing and setup flows.
- Deterministic built-in fragment shape mixtures, a secondary shape, mixture
  amount and layout seed, with Mixed Confetti and Orbiting Shapes presets.
- A versioned runtime movement handshake and explicit standalone activation,
  verified again before Apply; Restore retains exact previous configuration.
- Bounded compositor frame-feedback history and native timing reports that
  distinguish Winit submission, DRM presentation and encoder delivery.
- Native floating/tiled and resize/open/close overlap coverage, new showcases,
  complete settings examples and documented support limits.
- A generated preset reference with all built-in IDs, action timings, family
  capabilities, shader previews and portable settings downloads. Gallery checks
  reject missing or duplicate recordings and mismatched catalog settings.

### Fixed

- Keep picker review actions separate from desktop timing and verify both before Apply.
- Reject incorrect native capture dimensions, including ignored host actions while locked.
- Complete the visual catalog with three missing preset previews and six missing
  pairing previews. Use stable family headings instead of outdated counts.
- Describe actual movement shader preview and explicit resize choices consistently
  across the documentation and standalone setup guides.

### Upgrade

Update NiriFX before importing mixed-shape or desktop-motion settings. Re-register
or re-export shell packs to add the new styles. Existing preset defaults are
unchanged. Rebuild the experimental compositor for runtime verification and frame
feedback; older patched builds cannot pass live activation checks. Built-in profiles
leave resize and movement settings unchanged.

## 0.14.0 — 2026-10-03

### Added

- Seven curated preset collections shared by the CLI, Studio and gallery:
  Everyday, Explosions and Gravity, Geometric Pieces, Slices and Ribbons,
  Wobble and Bounce, Soft and Atmospheric, and Pixels and Glitches.
- Geometric Flow, Ribbon Current and Soft Landing open/close pairings, with
  portable settings, dedicated showcases and preset-picker registration.
- `list --collections`, `list --collection NAME`, and group browsing in the
  terminal guide. Collection filtering does not activate or edit an effect.

### Fixed

- Profile family metadata now includes explicit resize and movement actions,
  matching the desktop pickers. iNiR keywords include every action family and
  curated collection, so mixed-family profiles can be found by either effect.
- Isolated native test startup no longer depends on the desktop's logging level;
  socket announcements remain available when `RUST_LOG=warn` is set. Warning
  module names no longer cause false compositor-error reports.

### Changed

- Simplify preset filtering and keep collection metadata separate from portable
  effect documents. Built-in profiles continue to leave resize and movement unset.

### Upgrade

Re-register or re-export shell packs to add the three pairings and updated search
keywords. Existing effect values, schemas and the experimental compositor patch
are unchanged. Package updates do not select a style or enable resize.

## 0.13.1 — 2026-10-03

### Added

- Movement diagnostics distinguish configuration support in a chosen Niri binary
  from the compositor currently running. `doctor --movement-binary PATH` checks
  a trusted experimental build without installing it. JSON and readable reports
  describe parser support separately from rendering and activation.

### Fixed

- Studio's shape hint now covers selected resize effects. Setup and native demo guides
  reflect the current preset registry and Quickshell fixtures.

## 0.13.0 — 2026-10-03

### Added

- Fragment Wake, Ribbon Transfer and Momentum Glide: three movement-oriented
  presets with duration, intensity and directional trailing emphasis controls.
- Actual movement shader preview in Studio, four preview directions, and an
  independent movement action preserved in portable JSON profiles.
- Eight fragment shapes during explicit resize, with Triangle Edge Rebuild,
  Hexagon Edge Rebuild and Circle Soft Reflow profiles.
- Native consume/expel, vertical reorder, move/resize and insertion/removal checks;
  new swap, rearrangement, resize and shader showcases.
- Public roadmap epics with acceptance checklists and Niri-first portability notes.

### Changed

- The isolated demo accepts portable movement profiles and uses the chosen
  movement time. Synthetic Quickshell cards replace terminal clients, with private
  configuration, state and D-Bus directories.
- Resize exposes applicable shape controls and keeps a stable border. Square
  styles with rounding, shrink or size variation use the shaped resize renderer.
- Python and Studio share assembled movement shader templates. Stock exports
  continue to omit experimental movement; all built-in styles leave resize off.

### Upgrade

Update NiriFX before importing documents containing the new movement controls.
Re-register or re-export the collection to add the three styles to shell pickers.
Updating does not select an effect or enable resize. Existing explicit fragment
resize configurations with shape, rounding, shrink or size variation now honor
those controls. The experimental compositor patch remains unchanged.

## 0.12.0 — 2026-10-03

### Added

- Eight fragment shapes with shared gravity, spin, wave and release controls:
  square, rectangle, triangle, circle, ellipse, hexagon, diamond and star.
- Shape proportions, starting orientation and silhouette emergence timing in
  Studio and the CLI. Triangles move independently; hexagons form a joined lattice.
- Triangle Shatter, Circle Burst, Rectangle Confetti and Hex Swarm presets,
  importable examples, control comparisons and native swap showcases.
- Transparent layout, extreme aspect, reconstruction and lookup-bound checks.

### Changed

- Skip unreachable shaped cells before motion calculations. Existing square
  presets retain their original shaders and appearance. All built-ins keep resize off.
- Shaped layouts vary piece sizes during flight to preserve a joined initial
  partition. Shape controls do not affect the separate resize renderer.
- Studio keeps the older Canvas movement sketches limited to unrotated square
  fragments. Native shaped movement remains available through the experimental build.

### Upgrade

Update the CLI before importing shape settings. Existing documents receive square
defaults, and existing built-in shaders are unchanged. Re-register or re-export
to expose the new presets in shell pickers. Updating alone does not rewrite active
effects. The experimental compositor patch is unchanged from 0.11.0.

## 0.11.0 — 2026-10-03

### Added

- Vortex Fold and Soft Swirl, with signed twist, contraction, falloff and origin
  controls. Both support stock Niri opening/closing and experimental movement.
- Edge Ripple and Torsion Resize, each with separate Subtle and Expressive profiles.
  All built-in styles and open/close pairings still leave resize disabled.
- Dedicated recordings, comparisons, importable settings and hardware shader
  measurements for the new effects. The gallery contains 151 showcases.
- Gallery collections for nine starter looks, seven open/close pairings and all
  examples, with shareable links and setup instructions for each supported shell.
- Community forms for sharing styles and reporting compatibility across GPUs,
  displays and shells. No automatic telemetry or report upload is added.

### Changed

- Share the starter selection between the gallery and terminal guide, keeping
  Fragments first. Shorter mobile pages and expandable filters put previews closer
  to the top. Search from Start here explores the complete collection.
- Studio disables controls that do not affect the selected action, preserving
  their values. Torsion has its own signed resize twist control.
- Standardize GitHub release titles as `NiriFX X.Y.Z`.

### Fixed

- Preview shrinking as a new forward-time transition, exchanging old/new textures
  and geometry. Share links preserve resize direction; all resize showcase clips
  use the corrected flow.
- Preserve access to filtered gallery views and direct example links outside the
  starter collection. Update the terminal guide's preset count and walkthrough.

### Upgrade

Update the CLI before importing Vortex, Edge Ripple or Torsion documents. Older
settings receive defaults for the new controls; existing built-in effect values
and resize choices are preserved. Updating the package does not rewrite active
shaders. Re-register or re-export to expose new styles in shell pickers. The
experimental compositor patch is unchanged from 0.10.0.

## 0.10.0 — 2026-10-03

### Added

- Seven selectable open/close profiles: Fragment Flow, Burst and Drift, Frost and
  Fragments, Spring and Ember, Ghost and Shockwave, Pixel Shuffle and Ribbon Exit.
  They reuse existing presets and leave resize and movement unset.
- `--profile` selection for setup, render, preview, Studio and iNiR registration;
  `inspect --profile` exports editable JSON. The terminal guide adds a `profiles`
  menu, while `list --profiles` and `list --documents` support browsing and pickers.
- Built-in profile selection in Studio, Quickshell, GTK, DMS and exported preset
  packs. Refresh all seven profile showcases and the affected workflow recordings.
  The updated DMS adapter requires the matching CLI; see the upgrade guide.

### Fixed

- Normalize both actions when recording older profile JSON files that omit newer
  defaults; opening shader parity now checks the same fully resolved settings.
- Add content versions to gallery GIF/poster URLs so regenerated examples replace
  browser-cached recordings while unchanged examples remain cacheable.

### Changed

- Reduce varied-fragment shader work with conservative flight bounds and earlier
  velocity-group rejection. Preset settings, trajectories and particle density
  are unchanged; hardware results and reference-frame checks are documented in
  the performance guide.
- Experimental movement now carries tile and column position velocity through
  interrupted swaps, with a cubic path that settles at the new destination.
  Initial moves retain their configured easing/spring, and the change requires
  the pinned compositor patch with a movement shader configured. Close continuations
  follow the actual remaining layout distance and speed independently of shader phase.
- Refresh all ten native swap GIFs and four interruption scenarios from the revised
  release build. Add deterministic position/close handoff regressions.
- Extend the hardware GPU benchmark with batches of 1–8 independent window draws.
  Publish 1080p/4K results for five presets at 1, 2 and 4 draws; these are synthetic
  shader costs, not compositor frame times or physical presentation measurements.

## 0.9.0 — 2026-10-03

### Added

- Guided preset selection through `niri-fx` in a terminal or `setup --interactive`:
  nine recommended starting points, the full searchable catalog, concrete file
  review, guarded Apply and exact Undo. iNiR users register the collection for
  their existing picker; standalone users apply a chosen preset. No extra UI
  toolkit or default launcher is added by the guide.
- Readable `list --text` with recommendation/family/search filters, and
  `doctor --text` with optional Quickshell/GJS/GTK dependency checks. Existing
  JSON output remains available; missing optional interfaces do not fail core health.
- Optional GTK 4/GJS picker (`niri-fx picker --toolkit gtk`) with reusable widgets
  and an AGS 3 example. Includes search, JSON profiles, Studio dispatch, reviewed
  Apply, explicit resize consent and separate Undo history; closing the window
  waits for active CLI operations. Neither Quickshell nor AGS is required for the
  standalone GTK window.
- GTK/AGS setup and embedding guide, keyboard workflow GIF, portable controller
  tests and isolated runtime checks for conflicts, restoration and close-during-Apply.
- Optional Quickshell picker with style/family search, JSON profile loading,
  Studio launch, reviewed Apply and dedicated Undo history. Reusable controller
  and view components ship in the Python package; `niri-fx picker` opens them.
- Read-only `inspect --custom` for normalized style/profile JSON and
  `setup --expect-plan` to bind Apply to a previously reviewed plan. The picker
  rejects stale selections and requires explicit consent for custom resize effects.
- Quickshell integration guide and keyboard workflow showcase, with isolated
  controller/view tests for exact restore, changed files and process failures.

## 0.8.0 — 2026-10-03

### Maintenance

- Separate portable document validation, action profiles, offline preview assembly,
  HTTP transport and shared file staging into focused modules. Remove circular
  profile/rendering imports and adapter dependencies from the domain layer.
- Extract Studio's document/shader/KDL operations into a DOM-free core. Share
  acceptance fixtures with Python and compare all 64 presets' supported stock
  action shaders directly in Node, in addition to real browser E2E.
- Unify Chromium startup, readiness, request deadlines, disconnect handling and
  cleanup across browser tests, GIF recording and GPU benchmarks. All tools now
  honor `CHROME_BIN`; use URL-safe source paths and isolated browser profiles.
- Reject unknown single-style document fields consistently with profile documents;
  reject trailing-newline names in the browser as Python already does. Fail on
  unknown shader tokens and derive GLSL numeric syntax from parameter metadata.
- Add storage rollback/cleanup and browser lifecycle regression checks, extend CI
  and source packaging to include them, and separate shared test fixtures from
  individual test modules.
- Document architecture, shader invariants, ownership/restore behavior, effect
  contribution steps and concrete next-phase acceptance gates. Add focused source
  comments without changing preset values or shader math. Shader-preserving refactors retain existing recording metadata.
- Refresh fourteen early preset loops to record their exact parameters. Every
  built-in preset now has metadata checked against its current values in CI.

### Added

- Hosted Web Studio on GitHub Pages. Gallery styles open their recorded settings,
  offer JSON downloads and local commands, and support shareable filter links.
  Studio shares validated documents, action selection, seed and preview position
  without forwarding local save tokens. Hosted Studio never activates effects.
- Native deformation retargets carry sampled phase and direction speed through
  cubic transitions. Closing a moving window retains those clocks and begins
  translation with its sampled velocity. Layout easing remains owned by Niri.
- Rapid-reversal wobble showcase, refreshed native recordings and stock/patched
  stress checks for transparent clients, rapid open/close, resize interruptions,
  fullscreen and sequential 1×/1.5×/2× output scales.

- Nine presets: Hexagon Burst, Hive Collapse, Signal Glitch, Chromatic Glitch,
  Ink Spread, Ink Bloom, Slice Exchange, Pixel Transfer and Soft Phase. The
  catalog now contains 64 styles across nine families.
- Explicit Elastic Stretch, Accordion and Ripple resize profiles, with adjustable
  strength and family controls. Every built-in still leaves resize disabled.
- Native slice, pixel and distortion movement in the optional compositor patch,
  plus movement intensity. Interrupted swaps retain deformation and seed;
  direction changes blend instead of snapping. Closing during an opening or move
  continues that effect while fading, taking precedence over the normal close
  style. Shader deformation carries sampled velocity; this does not change every
  layout trajectory or create shared particle physics.
- Searchable click-to-play gallery on GitHub Pages with 135 recordings, lightweight
  posters, family/scenario/renderer filters and single-animation playback.
  New clips cover all added presets, three resize profiles, a resize comparison,
  three native swap styles and closing during opening.
- Basic/Advanced Studio controls, Pause and a reduced-motion preview preference
  that follows the system setting. Preview preferences do not change exported effects.
- Fragment reference-image comparison and native capture-delivery diagnostics;
  expanded browser, stock compositor, interruption and gallery checks.
- Root roadmap with current work, planned improvements and contribution paths;
  detailed integration and engineering plans link back to it.
- Eleven workflow/scenario GIFs: Studio editing/export, iRiS/DMS/Noctalia pickers,
  transparent stock-Niri clients, tall/wide windows, fractional scale and two
  interrupted native movement cases. The workflow recordings complement the effect catalog.
- Reproducible nested-session acceptance tools with private settings, owned
  process cleanup, synthetic content, versioned evidence and checked GIF metadata.
- Eight presets across three new stock open/close families: Pixels (Pixel Wipe,
  Pixelate, Dust Drift), Wisps (Ghost Wisps, Ink Current), and Distortion
  (Shockwave, Ripple Collapse, Wave Fold). All are usable for opening and closing on stock Niri.
- Thirty-two controls for layered erosion, edge palettes, pixel release/drift,
  curling wisps and wave distortion, shared by CLI, Studio and JSON presets.
- Twenty-two new showcase GIFs: eight preset loops, eleven tuning comparisons
  and three mixed-action profiles. Five existing clips were regenerated for
  the revised Dissolve effects. A visual scenario
  index links practical choices, exact settings and importable profiles; docs CI
  requires a recording for every preset/profile example and links for all GIFs.
- README TL;DR before the gallery, a scenario selector, a complete standalone
  guide and custom-shell/bar guidance. Prioritized integration roadmap for
  custom Quickshell, AGS/Astal, Caelestia and ML4W; Waybar needs no shader adapter.
- Browser checks for transparent input, downloadable standalone/Noctalia files
  and every new control; stock Niri open/close smoke of all new/revised styles.

### Changed

- Tighten the bounded lookup for varied fragments without waves from 7×7 to 5×5.
  All 231 reference frame pairs matched exactly; measured Core Detonation and
  Mosaic Burst shader time fell roughly 45–47% on the documented GPU sample.
- Refresh all ten native swap recordings and four interruption scenarios with
  mint/violet synthetic cards, 50 fps capture and the release-built experiment.
- Curate the README with Fragments first and move the full catalog to its own
  page. Rewrite roadmap priorities and document resize, continuity and measured
  performance limits for public use.
- Skip expensive CI steps for known documentation/media-only changes while
  retaining required check names, lint/docs validation and conservative fallback.
- Rewrite the README, roadmap and setup guides around user workflows and supported
  features. Add release/download guidance, refresh issue forms and correct stale
  DMS/Noctalia descriptions. Remove historical launch notes and unsubmitted
  outreach drafts from the current documentation.
- Refresh interrupted-movement recordings with mint/violet sample app cards,
  50 fps capture and an optimized compositor build. Raise the nested recording
  window and reject delayed interruption commands; keep verification outside the
  recorded timeline. Refresh shell demos with neutral labels and paths, and make
  gallery pointer input use monotonic timestamps and bounded scroll positions.
- Ember Erosion defaults to a white rim and charcoal band. Hue, saturation and
  brightness are configurable; Frost retains its cool palette. Dissolve gains
  layered detail and flowing noise.
- Studio accepts `--target auto|inir|noctalia|standalone`. Auto selects iNiR when
  its helper is installed, otherwise standalone; offline previews default to
  file downloads. Save instructions follow the selected target.
- Effect-family choices come from the shared catalog rather than a separate
  hardcoded HTML list.

### Fixed

- Standalone setup preflight now validates generated animations through the same
  include boundary used by installation. Configs with an existing inline
  `animations` block no longer fail with a duplicate-node error. A real Niri
  regression test covers planning, apply, preservation of resize and exact restore.
- Browser automation tolerates the brief absence of a document during navigation
  instead of failing before Studio is ready.

## 0.7.0 — 2026-10-02

### Added

- Thirty new presets since 0.6: varied Fragments, additional Slices, Elastic
  wobble, Dissolve and Iris reveals. The catalog now has 47 styles across five
  families, all with resize off by default.
- Fragment rounding, shrink, unequal sizes, seeded directions and travelling
  waves; spatial release patterns; slice release order, hinge and collapse;
  elastic twist, stretch, bend frequency and transform origins; twelve controls
  for noise erosion, colored edges and geometric iris masks.
- Independent action profiles: separate opening and closing styles, optional
  fragment resize, CLI generation, Studio editing, import/export and iRiS saving.
- Studio search, persistent favorites, 100-state undo/redo, individual reset,
  pinned A/B comparison and iNiR/Noctalia/standalone save targets.
- Importable examples, controlled comparisons and actual native swap recordings.
  The gallery now contains 84 GIFs, with Fragments first and an independent-profile
  showcase. Targeted regeneration supports `--only=clip-name,clip-name`.
- Reversible `export-pack` for Noctalia's existing Niri Animations picker and other
  KDL consumers, with ownership checks and restore snapshots. Noctalia 5.2.1 /
  Niri Animations 0.2.0 passed style selection and return to base in nested Niri.
- Optional DMS launcher adapter for search, Studio, reversible apply and undo;
  tested through real offscreen Quickshell and DMS 1.6.2 PluginService. Full
  launcher visual acceptance remains pending.
- Hardware GPU timing harness with raw samples, percentiles, frame-budget
  comparisons and explicit rejection of software/disjoint timing results.
- Ruff, ESLint, Prettier and pinned development dependencies. Actions includes
  lint, Python 3.10/3.14, GLSL/docs/package checks and actual CLI/browser/HTTP/save
  E2E coverage of all families and independent profiles.

### Changed

- One current NiriFX identity: `niri_fx` package, `niri-fx` CLI/registry IDs/state
  and launcher names. Remove the legacy package, executable and schema 1/2 style
  support. Single-style documents use schema 3; independent profiles use kind
  `profile`, schema 1. Historical snapshots remain recovery records; the
  application does not migrate old formats. See [upgrading](docs/upgrading.md).
- One parameter catalog drives Python validation, CLI options, Studio controls,
  shader tokens and labels. Model, built-in preset data and renderers are separate.
- Studio JavaScript and CSS are readable, separately linted source files,
  assembled into the same self-contained offline HTML export.
- Shared shader bodies have explicit action entry points. Movement generation no
  longer cuts a function out of generated source text.
- Python/JavaScript shader numbers use identical rounding, including halfway values.
- Slide Apart alternates adjacent horizontal strips. Split Curtain supplies the
  former split direction.
- Compact and varied Fragments use separate bounded renderers with different
  costs. Resize retains its existing renderer without wave/variation controls.
- Run branch checks on pull requests and main pushes, avoiding duplicate feature
  branch push/PR runs.

### Branding and discoverability

- Original pixel-N application icon, README banner, searchable desktop metadata,
  expanded package/GitHub keywords and accurate Built with / Integrations credits.
- Related-project research and a community contribution plan, including a focused
  awesome-niri listing proposal and Noctalia documentation suggestion.
- Fix issue-template links that still pointed at the old repository name.

## 0.6.0 — 2026-10-02

Niri Fragments becomes **NiriFX**, a window effects studio with multiple families.

### Added

- Slices family with Slide Apart, Alternating Blinds and Diagonal Shear presets.
  Configure strip count, angle, distance, direction, stagger and rotation.
- Family-specific Studio controls and a `families` capability command. Unsupported
  slice resize/movement requests fail explicitly; Studio disables those previews.
- Schema 2 slice documents, three importable examples, three preset GIFs and a
  synchronized 4/12/32-slice comparison. The README gallery now has 35 GIFs.
- Historical shader fingerprint tests, slice validation/round trips, family UI
  checks and new/legacy command compatibility coverage.
- Migration guidance for the repository/package rename and preserved user state.

### Changed

- Repository/distribution/primary CLI become `niri-fx`; app name is NiriFX Studio.
  `niri-fragments`, `python3 -m niri_fragments` and existing Python imports remain
  supported, alongside `python3 -m niri_fx`.
- iNiR display labels use NiriFX while IDs/ownership remain `niri-fragments`.
  Existing presets, snapshots, managed includes and launcher identities are retained.
- Studio filters controls/presets by family. Irrelevant CLI overrides are rejected.

### Fixed

- Browser checks wait for Chrome startup and report launch errors/diagnostics
  instead of an unhelpful missing debug-port file error on slower CI runners.

Compatibility: all 14 existing fragment shaders remain byte-for-byte identical
in generated source to 0.5. Fragment exports retain schema 1, and legacy JSON
still imports. New slice JSON needs 0.6+. Resize stays off by default; Slices
supports opening/closing only. See [migration](https://github.com/jturbide/niri-fx/blob/v0.6.0/docs/migration-0.6.md) before
replacing an installed Python distribution. DMS integration remains future work.

## 0.5.0 — 2026-10-02

First public prerelease. Earlier versions were private development milestones.

### Added

- `doctor` diagnostics, preview-first `setup`, managed standalone includes,
  optional launcher creation and hash-checked restore snapshots.
- Studio JSON import with shared parameter validation, legacy defaults and exact
  numeric preservation. CLI `--custom` support for render, preview, Studio and setup.
- Directional Wave, Corner Burst and Orbital Collapse, bringing the pack to 14;
  three-stage release waves, wave span and adjustable burst/orbit origin.
- Full Breakup, Edge Rebuild and Soft Reflow resize styles, disabled in built-in presets.
- Seven new GIFs with matching JSON and visible README showcases: three presets,
  one origin comparison and three resize styles. The gallery now has 31 clips.
- Setup/restore failure and conflict tests, three-mode resize validation, browser
  import checks in CI, and repeated/interrupted native movement smoke checks.
- GIF gallery for open, close, resize, all 14 presets, Studio movement
  concepts and an actual nested-compositor column swap; reproducible recorders.
- Four synchronized control comparisons for particle count, gravity direction,
  gravity strength and rotation, plus Meteor Shower, Orbit Burst and Reverse
  Gravity examples with importable JSON and matching preview commands.
- Installation, update, removal, troubleshooting, contributor, security and
  release guides, with issue/PR templates and a documentation check in CI.
- Compatibility guide for standalone Niri and DankMaterialShell, with an explicit
  roadmap for a future DMS adapter.
- This changelog and public-release preparation notes.

### Changed

- Reorganized the README around previews, onboarding and supported capabilities.
- Expanded the main README with visible preset, control and movement showcases;
  the gallery no longer requires opening collapsed sections.
- Added package project links and made the source archive include its demo assets,
  experimental patch and corresponding license notices.

### Fixed

- Retry temporary Chromium profile removal while helper processes finish writing,
  preventing successful browser checks from failing during cleanup.
- Printed restore commands use the running Python interpreter, including when
  running directly from a checkout without an installed CLI executable.

Migration: re-register the built-in pack and reselect a style in iRiS, or
regenerate your standalone include. Existing JSON remains compatible; absent
new fields use centered origins, simultaneous release and Full Breakup. Resize
remains off unless an imported/saved custom preset explicitly enables it.
Setup snapshots cover setup changes only; earlier manual registrations use
`unregister` and their printed backups. Native move/swap remains experimental.

## 0.4.1 — 2026-10-02

### Fixed

- Disabled fragment resize by default in all built-in presets, new Studio sessions
  and the nested demo. Existing custom presets retain explicit resize choices.
- Preserve the base preset's resize behavior unless `--resize` or the Studio
  checkbox explicitly enables fragments. Legacy JSON without `resize` opts out.

Migration: re-register and reselect a built-in style to replace its active 0.4.0
shader/settings. Re-export standalone configurations. Custom styles are unchanged.

## 0.4.0 — 2026-10-02

### Added

- Stock Niri resize shader, old/new texture preview, duration and breakup controls.
- Isolated, pinned Niri movement patch with a native column-swap demo, build
  verification and compositor regression checks.

Historical default: this version enabled fragment resize in built-in presets.
**Since 0.4.1, built-in presets leave fragment resize disabled.** Native movement remained
experimental and separate from stock exports and iNiR registration.

## 0.3.0 — 2026-10-02

### Added

- Explosion and Implosion presets, bringing the pack to 11 styles.
- Path dispersion and stagger controls; Studio Move/Swap design concepts.
- Chromium app-style Studio with a separate profile and browser fallback.

### Changed

- Denser presets, varied trajectories, staggered release, softer fragment edges
  and later dissolution. Balanced now targets 720 fragments.

## 0.2.0 — 2026-10-02

### Added

- Earth, Black Hole, Space, Vortex, Confetti and Updraft presets.
- Gravity direction/strength, target particle count, rotation, spin and orbit.
- Interactive Studio, named custom presets, JSON import/export and KDL export.
- Session-bound loopback save endpoint with token and Origin validation.

### Changed

- Built-in pack updates preserve named custom styles and other providers.

## 0.1.0 — 2026-10-02

### Added

- Textured pixel open/close shaders with Subtle, Balanced and Dramatic presets.
- CLI rendering, offline preview and native iNiR/iRiS preset registration.
- Scoped registry backups, atomic writes, dry-run, symlink preservation and
  unregister support, plus shader/config validation and CI.
