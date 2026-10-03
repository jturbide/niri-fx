# Changelog

User-visible changes are recorded here under Added, Changed, Fixed or Removed.
New work goes in **Unreleased**; dated entries are frozen when a release is made.
Versions follow `MAJOR.MINOR.PATCH`; while 0.x, minor versions may change the
prototype's interfaces. Migration notes accompany compatibility changes.

The 0.1.0–0.4.1 entries below reconstruct the private development history from
versioned commits on 2026-10-02. They were not published GitHub releases or tags.

## Unreleased

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

- Nine presets: Hexagon Burst, Hive Collapse, Signal Glitch, Chromatic Glitch,
  Ink Spread, Ink Bloom, Slice Exchange, Pixel Transfer and Soft Phase. The
  catalog now contains 64 styles across nine families.
- Explicit Elastic Stretch, Accordion and Ripple resize profiles, with adjustable
  strength and family controls. Every built-in still leaves resize disabled.
- Native slice, pixel and distortion movement in the optional compositor patch,
  plus movement intensity. Interrupted swaps retain deformation and seed;
  direction changes blend instead of snapping. Closing during an opening or move
  continues that effect while fading, taking precedence over the normal close
  style. This preserves visual state, not physical velocity across every retarget.
- Searchable click-to-play gallery on GitHub Pages with 134 recordings, lightweight
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
- Refresh all ten native swap recordings and three interruption scenarios with
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
- Full Breakup, Edge Rebuild and Soft Reflow resize styles, all strictly opt-in.
- Seven new GIFs with matching JSON and visible README showcases: three presets,
  one origin comparison and three resize styles. The gallery now has 31 clips.
- Setup/restore failure and conflict tests, three-mode resize validation, browser
  import checks in CI, and repeated/interrupted native movement smoke checks.
- GIF gallery for open, close, opt-in resize, all 14 presets, Studio movement
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
**0.4.1 supersedes that default with explicit opt-in.** Native movement remained
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
