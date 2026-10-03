# Validation and known limits

Evidence recorded on **2026-10-02**, for 0.4.1 and the accompanying documentation
update. This is a prototype validation record, not a GPU performance certification.
For version-by-version behavior changes, see the [changelog](../CHANGELOG.md).

## Stock effects and editor

| Check | Observed result |
| --- | --- |
| Python regression suite | 22 tests passed: validation, preset ownership/preservation, backups, atomic writes, symlinks and actual loopback saving/rejection |
| GLSL ES 1.00 compilation | All 44 shaders compiled: 11 presets × open/close/resize/experimental movement |
| Stock Niri config parsing | All 11 default exports validated with Niri 26.04 (`8ed0da4`) |
| iNiR adapter | All 11 presets applied and recognized in a temporary config; global off/slowdown retained |
| Resize defaults | All built-ins and new editor sessions opt out; explicit custom choices preserved |
| Browser shader endpoints | Intact initial texture, fragmented midpoint and transparent final frame for open/close |
| Resize preview | Intact endpoints, intermediate breakup and correct old/new texture replacement |
| Browser / Python parity | Generated shader exports matched across built-ins; extreme controls rendered without WebGL errors |
| Gravity checks | Earth moved downward, Updraft upward and Black Hole contracted |
| Concept move / swap | Synthetic windows arrived intact in their correct columns; these are not compositor movement checks |
| Packaging | Wheel/source builds and installed CLI resource checks; see the public preparation record for archive scope |

The adapter and browser rendering checks were run during 0.2–0.4 development;
0.4.1 changed resize defaults and reran the regression/compilation/config checks.
The docs update does not change shader code. The real installed desktop has been
used for open/close effects, but that observation does not cover other hardware,
all window types or performance under load.

## Native movement experiment

The pinned Niri patch built with Rust 1.99.0 and no default features. It applied
to a clean checkout of `8ed0da44d974c32c6877d2f4630c314da0717ecb` and reproduced
the expected source diff. Niri's 19 config tests, one config integration test and
12 existing layout animation regression tests passed.

A nested session rendered two synthetic Alacritty clients during a real column
swap. Both fragmented, exchanged columns and regained their original measured
colored areas. Native resize and shader-removal captures were inspected; no
shader compilation/render/config errors appeared in the observed smoke logs.
The TTY path compiled but was not activated. The normal login compositor was
not replaced. See [the experiment scope](../experimental/README.md).

## Documentation recordings

The gallery contains 17 GIFs: real Studio shader recordings for opening, closing,
optional resize and all 11 presets; two labelled Canvas movement concepts; and
one actual nested Niri swap recording. The clips use synthetic content. Frame
sequences, loop metadata and file references were checked, and representative
frames were inspected. See [reproduction details](gifs/README.md).

GIFs use 20 fps, scaled output and palette reduction. Browser checks use Chromium
software WebGL. Neither measures compositor GPU frame time or guarantees exact
appearance on every desktop. The experimental default build is unoptimized.

## Remaining acceptance work

- Real GPU frame time and responsiveness at different window/output sizes. The
  shader evaluates up to 27 candidate cells per pixel, independent of particle
  count; expanded draw area adds cost.
- Fractional scaling, mixed monitors, transparency, decorations, fullscreen,
  output-edge clipping and different applications. Client-side shadows outside
  window geometry are omitted during breakup.
- Rapid/repeated/interrupted animations, resize/close interactions and graphics
  reset behavior, especially in the movement patch.
- Direct dragging, seamless retargeting and per-particle ordering across windows
  are not implemented by the current movement hook.
- DMS runtime acceptance and native picker integration are pending; the documented
  include ordering was checked with an isolated Niri config, not a DMS session.

Reproduce checks through [Contributing](../CONTRIBUTING.md), report issues with
minimal synthetic examples, and distinguish successful automated checks from
visual preference or desktop performance claims.
