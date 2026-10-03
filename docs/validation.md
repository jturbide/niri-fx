# Validation and known limits

Evidence recorded on **2026-10-02**, updated for the post-0.6 development checkout. This is a prototype validation record, not a GPU performance certification.
For version-by-version behavior changes, see the [changelog](../CHANGELOG.md).

## Stock effects and editor

| Check | Observed result |
| --- | --- |
| Python regression suite | 48 tests passed: validation, preset ownership/preservation, backups, atomic writes, symlinks and actual loopback saving/rejection |
| GLSL ES 1.00 compilation | All 181 shaders compiled: 138 fragment variants, 22 slice and 21 elastic variants |
| Stock Niri config parsing | All 41 default and 69 explicitly enabled fragment resize exports validated with Niri 26.04 (`8ed0da4`) |
| iNiR adapter | 0.6 verified all 17 presets through the installed helper in temporary config. Current E2E saves schema 3 Fragments, Slices and Elastic through a synthetic helper and actual CLI/browser/HTTP path, preserving base resize and other providers. |
| Noctalia file contract | All 41 exported files validated through picker-style relative includes with stock Niri; Noctalia UI not run. |
| Code conventions | Ruff, ESLint and Prettier pass; Actions runs them with pinned development dependencies. |
| Setup / restore | Real standalone setup, repeat apply and exact restoration passed with Niri, relative includes and a Unicode config path; conflict, failure and symlink cases covered in tests |
| JSON import | Current documents and rejected obsolete schemas, explicit resize, fractional values, malformed/oversized documents and unsupported fields checked in Chromium |
| Current API | One module/CLI and schema 3 for all families; obsolete schemas rejected; current registry ownership and resize preservation tested |
| Resize defaults | All built-ins and new editor sessions opt out; explicit custom choices preserved |
| Browser shader endpoints | Intact initial texture, fragmented midpoint and transparent final frame for open/close |
| Resize preview | All three modes have intact endpoints and correct texture replacement; Edge Rebuild retains the center and Soft Reflow reduces breakup |
| Browser / Python parity | Generated shader exports matched across built-ins; extreme controls rendered without WebGL errors |
| Gravity checks | Earth moved downward, Updraft upward and Black Hole contracted |
| Concept move / swap | Synthetic windows arrived intact in their correct columns; these are not compositor movement checks |
| Packaging | Clean wheel/source builds; installed current CLI, icon and offline Studio checked outside the checkout; obsolete namespace/entry point absent; all 41 exported presets restored exactly |
| Branding and local registration | Canonical Studio/demo launchers installed; iNiR recognizes renamed preset ownership/IDs while the selected shader and resize settings remain unchanged |

Current browser checks exercised all 41 presets, exact endpoints, extreme
parameters, all family controls/capability limits, schema 3 round trips and rejected schema 1/2 imports and three
fragment resize styles. Each new shape/hinge/elastic control independently changes
rendered pixels and survives an import round trip. Shrink, rounding and strip
collapse reduce occupied area. Four spatial release modes produce distinct
patterns. Extreme rounded/unequal Canvas pieces remain drawable at texture edges.
Browser parity and behavioral checks validate current effects.

The three original 0.6 slice effects also opened and closed a synthetic Alacritty client in
an isolated **stock Niri 26.04** session. Intermediate captures differed from the
intact window, the opening completed intact, and closing left no window-colored
pixels. No shader/render/config errors appeared. These are functional checks,
not performance certification across hardware.

## Native movement experiment

The pinned Niri patch built with Rust 1.99.0 and no default features. It applied
to a clean checkout of `8ed0da44d974c32c6877d2f4630c314da0717ecb` and reproduced
the expected source diff. Niri's 19 config tests, one config integration test and
12 existing layout animation regression tests passed.

A nested session rendered two synthetic Alacritty clients during a real column
swap. Both fragmented, exchanged columns and regained their original measured
colored areas. Native resize and shader-removal captures were inspected; no
shader compilation/render/config errors appeared in the observed smoke logs.
The 0.5.0 nested smoke also passed six swaps interrupted by subsequent moves,
confirmed both windows' final positions/colored areas, and closed a moving
window without leaving its fragments behind. This checks eventual settlement,
not seamless visual continuity; interrupted movements can restart their phase.
The TTY path compiled but was not activated. The normal login compositor was
not replaced. See [the experiment scope](../experimental/README.md).

Crosswind, Orbital Ribbons and Spring Wobble also passed the nested movement
smoke: real swaps, six interrupted swaps, intact settlement, close during movement
and shader-removal fallback. Elastic checks visibly bent edges rather than
fragment pixel loss. The shader change reuses the existing pinned compositor
binary; no additional compositor patch was required.

Bubble Burst, Core Detonation and Twist Snap also passed the native smoke:
real swap, six interrupted swaps, intact settlement, close during movement,
supported resize and shader-removal fallback. The new shape/twist recordings
use the same separately built compositor; the compositor patch is unchanged.

## Documentation recordings

The gallery contains 75 GIFs: all 41 presets, open/close and opt-in resize,
control/style comparisons, custom recipes, labelled Canvas movement concepts,
and seven actual nested Niri swaps. The latest addition is 12 preset loops,
five comparisons and three native recordings for piece shapes, spatial release,
slice hinges/collapse and elastic transforms. All current clips include exact
parameter metadata, apart from the separately documented original native swap.
Synthetic content only; see [reproduction details](gifs/README.md).

The comparison/custom recorder checks browser/Python shader parity for every
panel. The docs check verifies that preview commands, importable JSON, comparison
definitions and recorded parameter metadata still agree.

GIFs use 20 fps, scaled output and palette reduction. Browser checks use Chromium
software WebGL. Neither measures compositor GPU frame time or guarantees exact
appearance on every desktop. The experimental default build is unoptimized.

## Remaining acceptance work

- Real GPU frame time and responsiveness at different window/output sizes. The original fragment
  shader evaluates up to 27 candidate cells per pixel for simultaneous release,
  or 81 for directional release. New varied Fragments uses up to 147/441 candidates,
  independent of particle count. Expanded
  draw area adds cost; lower particle count alone does not guarantee faster rendering.
  Slices evaluates at most its configured 2–48 strips per pixel; strip count,
  window size and expanded draw bounds affect work.
- Fractional scaling, mixed monitors, transparency, decorations, fullscreen,
  output-edge clipping and different applications. Client-side shadows outside
  window geometry are omitted during breakup.
- Broader repeated/interrupted-animation coverage, simultaneous resize/close
  interactions and graphics reset behavior beyond the nested smoke cases.
- Direct dragging, seamless retargeting and per-particle ordering across windows
  are not implemented by the current movement hook.
- Noctalia picker UI and DMS runtime acceptance and native picker integration are pending; the documented
  include ordering was checked with an isolated Niri config, not a DMS session.

Reproduce checks through [Contributing](../CONTRIBUTING.md), report issues with
minimal synthetic examples, and distinguish successful automated checks from
visual preference or desktop performance claims.
