# Changelog

User-visible changes are recorded here under Added, Changed, Fixed or Removed.
New work goes in **Unreleased**; dated entries are frozen when a release is made.
Versions follow `MAJOR.MINOR.PATCH`; while 0.x, minor versions may change the
prototype's interfaces. Migration notes accompany compatibility changes.

The 0.1.0–0.4.1 entries below reconstruct the private development history from
versioned commits on 2026-10-02. They were not published GitHub releases or tags.

## Unreleased

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
