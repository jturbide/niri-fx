# Changelog

User-visible changes are recorded here under Added, Changed, Fixed or Removed.
New work goes in **Unreleased**; dated entries are frozen when a release is made.
Versions follow `MAJOR.MINOR.PATCH`; while 0.x, minor versions may change the
prototype's interfaces. Migration notes accompany compatibility changes.

The 0.1.0–0.4.1 entries below reconstruct the private development history from
versioned commits on 2026-10-02. They were not published GitHub releases or tags.

## Unreleased

### Added

- Five varied Fragment presets: Tidal Fragments, Mosaic Burst, Chaotic Confetti,
  Crosswind and Orbital Ribbons. Shared controls add unequal cell sizes, seeded
  heading variation and travelling waves with strength/frequency/speed.
- Four more Slice presets: Split Curtain, Ribbon Wave, Shuffled Slats and Venetian
  Sweep. Add independent random directions, six release orders, unequal widths,
  travel/spin variation and transverse waves.
- Elastic family: Spring Wobble, Rubber Band and Jelly, with strength, frequency,
  damping and axis controls. Stock open/close and experimental native movement
  bend the whole window. Interactive drag physics and resize wobble are not included.
- Schema 3 presets, 12 importable examples, 12 preset GIFs, five comparisons and
  three native swap recordings. Regenerate Slide Apart and its count comparison;
  keep Fragments first in the README gallery.
- Reversible `export-pack` for the existing Noctalia Niri Animations picker and
  other KDL consumers. Preserve unrelated files, refuse edited/colliding paths,
  keep ownership metadata and restore snapshots. Noctalia UI acceptance is pending.
- Ruff lint/format, ESLint, Prettier, editor conventions and pinned development
  dependencies. Actions now includes lint and a real CLI/browser/HTTP/helper/save
  E2E flow for all families, alongside unit/integration/GLSL/docs/package checks.
- Compatibility alias tests, schema/pack ownership tests, visible and deterministic
  browser variation checks, and native wobble/interrupted-swap checks.

### Changed

- Slide Apart alternates adjacent horizontal strips instead of splitting halves.
  Split Curtain retains the old look; saved legacy JSON keeps its saved direction.
- Canonical implementation/resources move to `niri_fx`; `niri_fragments` modules
  alias the same objects. Existing commands, IDs, state paths, snapshots and
  launcher identities remain supported. Fresh launcher commands use `niri_fx`.
- Studio JavaScript and CSS become readable, separately linted source files,
  assembled into the same self-contained offline HTML export.
- All 14 original Fragment presets retain their exact shader sources. New varied
  Fragments use a separate, more expensive bounded renderer. Resize stays opt-in
  and uses its existing renderer without the new wave/variation controls.


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
supports opening/closing only. See [migration](docs/migration-0.6.md) before
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
