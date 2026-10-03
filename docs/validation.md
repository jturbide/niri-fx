# Validation and known limits

Evidence recorded on **2026-10-02**, for 0.5.0. This is a prototype validation record, not a GPU performance certification.
For version-by-version behavior changes, see the [changelog](../CHANGELOG.md).

## Stock effects and editor

| Check | Observed result |
| --- | --- |
| Python regression suite | 36 tests passed: validation, preset ownership/preservation, backups, atomic writes, symlinks and actual loopback saving/rejection |
| GLSL ES 1.00 compilation | All 84 shaders compiled: 14 presets × open/close/movement + three resize modes |
| Stock Niri config parsing | All 14 default and 42 explicitly enabled resize exports validated with Niri 26.04 (`8ed0da4`) |
| iNiR adapter | 14 presets registered/restored with the installed helper in a temporary registry; prior 11-preset apply/recognition checks retained |
| Setup / restore | Real standalone setup, repeat apply and exact restoration passed with Niri, relative includes and a Unicode config path; conflict, failure and symlink cases covered in tests |
| JSON import | Valid/legacy documents, explicit resize, fractional values, malformed/oversized documents and unsupported fields checked in Chromium |
| Resize defaults | All built-ins and new editor sessions opt out; explicit custom choices preserved |
| Browser shader endpoints | Intact initial texture, fragmented midpoint and transparent final frame for open/close |
| Resize preview | All three modes have intact endpoints and correct texture replacement; Edge Rebuild retains the center and Soft Reflow reduces breakup |
| Browser / Python parity | Generated shader exports matched across built-ins; extreme controls rendered without WebGL errors |
| Gravity checks | Earth moved downward, Updraft upward and Black Hole contracted |
| Concept move / swap | Synthetic windows arrived intact in their correct columns; these are not compositor movement checks |
| Packaging | Wheel/source builds and installed CLI resource checks; see the public preparation record for archive scope |

The 0.5.0 browser checks exercised all 14 presets, exact endpoints, extreme
parameters and three resize styles. The real installed desktop has been used
for earlier open/close effects; the new variants have compilation/browser
validation but not broad hardware acceptance.

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

## Documentation recordings

The gallery contains 31 GIFs: real Studio shader recordings for opening, closing,
optional resize and all 14 presets; five synchronized control comparisons; three
custom recipes and three opt-in resize styles; two labelled Canvas movement concepts; and one actual nested
Niri swap recording. The custom examples ship with their recorded JSON settings.
The clips use synthetic content. Frame
sequences, loop metadata and file references were checked, and representative
frames were inspected. See [reproduction details](gifs/README.md).

The comparison/custom recorder checks browser/Python shader parity for every
panel. The docs check verifies that preview commands, importable JSON, comparison
definitions and recorded parameter metadata still agree.

GIFs use 20 fps, scaled output and palette reduction. Browser checks use Chromium
software WebGL. Neither measures compositor GPU frame time or guarantees exact
appearance on every desktop. The experimental default build is unoptimized.

## Remaining acceptance work

- Real GPU frame time and responsiveness at different window/output sizes. The
  shader evaluates up to 27 candidate cells per pixel for simultaneous release,
  or 81 for three directional waves, independent of particle count. Expanded
  draw area adds cost; lower particle count alone does not guarantee faster rendering.
- Fractional scaling, mixed monitors, transparency, decorations, fullscreen,
  output-edge clipping and different applications. Client-side shadows outside
  window geometry are omitted during breakup.
- Broader repeated/interrupted-animation coverage, simultaneous resize/close
  interactions and graphics reset behavior beyond the nested smoke cases.
- Direct dragging, seamless retargeting and per-particle ordering across windows
  are not implemented by the current movement hook.
- DMS runtime acceptance and native picker integration are pending; the documented
  include ordering was checked with an isolated Niri config, not a DMS session.

Reproduce checks through [Contributing](../CONTRIBUTING.md), report issues with
minimal synthetic examples, and distinguish successful automated checks from
visual preference or desktop performance claims.
