# Validation and known limits

Evidence updated on **2026-10-04** for 0.16.0 and the Unreleased Library changes. These checks
establish behavior on the tested setups; they do not certify every GPU or desktop.
See the [changelog](../CHANGELOG.md) for user-visible changes.

## Public catalog checks

Automated checks enforce catalog completeness. The generated
[preset reference](presets.md) covers every named preset and pairing with its
actual action timings and portable settings. Missing or duplicate recording IDs,
mismatched effect parameters, stale reference tables, missing visual-catalog
previews and outdated README counts fail validation. Three regressions exercise
completeness, independent pairing timing and rejected recording/settings errors.
These checks complement the rendering and native evidence below.

## Stock effects and editor

| Check | Observed result |
| --- | --- |
| Python | 166 regression tests: validation, ownership, backup/restore, temporary HTTP saving, family capabilities, curated profiles, terminal workflows, movement parser/session diagnostics and conservative CI scope selection |
| Portable JavaScript | 69 Node checks; all 75 presets' supported stock shaders match Python, with picker transaction and profile checks |
| Real Chromium | 75 rendered presets with intact/transparent endpoints, extreme controls, import/export, capabilities, independent profiles and actual HTTP saving for all nine families |
| New controls | Hex size/spread/spin/direction/stagger, ink origin/turbulence and glitch bands/chroma each change rendered pixels; transparent input stays transparent |
| Browser lifecycle and gallery | Ten tests cover failed startup, bounded requests, disconnect/cleanup, shared starter selection, pairing/search filters, direct anchors, collection URLs, all nine cross-family Studio filters, unchanged effect documents while browsing, narrow layouts, reduced-motion startup, single-GIF playback hosted Studio share/download flows and explicit companion opt-in through import and Undo |
| GLSL and stock config | All supported open/close/movement/resize shader variants compile as GLSL ES 1.00; all 75 default exports, supported resize exports and 91 style/profile picker includes parse in stock Niri 26.04 |
| Native stock effects | All nine added presets open, render intermediate frames, settle intact and close to an empty scene in a nested stock compositor |
| Curated pairings | Geometric Flow, Ribbon Current and Soft Landing render partial opening/closing frames, settle intact and close to an empty scene in stock Niri. Sampling uses an 8× slower isolated animation clock to avoid missing short phases during screencopy; this does not measure real-time presentation smoothness. |
| Fragment optimization | 1,050 reference-frame pairs across software WebGL and hardware ANGLE match byte-for-byte, including extreme settings and transparent input. Core Detonation, Mosaic Burst and Orbital Ribbons pass stock open/close checks; Core Detonation also passes native swaps, interruptions and fallback. See [measurements and reproduction](performance.md#varied-fragment-flight-bounds). |
| Fragment shapes | Eight shapes restore translucent source coverage without an endpoint shortcut, including aspect 0.25 and 4, with stable replay and reversed opening/closing paths. Forward-transformed vertices exercise the inverse lookup bound. 240 reference-frame comparisons across software and hardware match frame hashes and alpha totals. At the 0.12.0 release, all 66 pre-existing presets kept byte-identical stock and movement shaders. |
| Shaped native actions | All four new presets pass transparent stock open/close and the patched movement smoke test (swaps, six interruptions, close during movement, supported resize and fallback). Triangle Shatter and Hex Swarm also pass sequential 1×/1.5×/2× interruption cases and eight rapid reversals; both have native swap recordings. |
| Vortex distortion | Existing distortion presets match 126 reference-frame pairs against 0.10.0 byte-for-byte. Signed twist, contraction, origin, extreme geometry and transparent source pass browser checks. Both presets pass stock open/close and cleanup. Vortex Fold passes native swaps, six interrupted swaps, close during movement, resize and fallback. |
| Resize profiles | All ten curated profiles (Elastic, Accordion, Ripple, Subtle/Expressive Edge Ripple and Torsion, plus Fragments/Ribbons/Elastic Motion) grow and shrink a transparent synthetic client to 900 and 400 pixels, produce intermediate frames, settle correctly and close without leftovers |
| Resize rendering | Edge Ripple and Torsion pass forward-time grow/shrink, exact texture endpoints, signed and zero controls, filled bounds at extreme aspect ratios and Python/JavaScript shader parity checks |
| Resize defaults | Every built-in leaves resize off; viewing controls never enables it; explicit profile slots and custom choices round-trip |
| Packaging | Wheel and source distribution build; installed CLI, shader resources, icon, offline Studio and profile exports work outside the checkout |
| Documentation | Local links, example commands, preset/profile recordings, native source hashes and generated gallery/poster hashes are checked |

Editor acceptance uses software WebGL for deterministic behavior checks. Native
checks use synthetic clients, fresh config directories and separate nested Niri
windows. They do not replace or alter the login compositor.

The earlier transparency, window-shape and fractional-scale cases below remain
useful regression evidence. Adapter UI recordings describe the versions and
catalog size actually exercised; new family support is checked through the current
file contract and Studio save flow, not assumed from those older recordings.

## Movement diagnostics

The parser probe was checked against stock Niri 26.04 and the pinned experimental
build, which report the same upstream version. IPC executable identification
correctly distinguished the running stock session from that separate binary,
then identified the matching binary in an owned nested experimental session.
These checks made no changes to desktop settings.

Regression coverage includes missing and replaced binaries, parser errors,
timeouts, malformed/oversized IPC replies, another user's socket and unavailable
process identity. These results certify configuration parsing and identity only;
they do not certify the movement shader contract or rendering.

## Native movement and continuity

The experimental patch applies to Niri revision
`8ed0da44d974c32c6877d2f4630c314da0717ecb`. A release build passed 19 config tests,
one config integration test, 12 layout-animation tests, seven shader-continuity tests
and seven position-continuity tests. These check repeated reversals, first derivatives,
monotone phase handoffs, zero-distance momentum, spring input, slow/frozen clocks,
disabled animation semantics and closing along the actual layout path.

Ten native swap recordings passed final-position and intact-color checks with
clean render logs. Interrupted swapping, eight rapid wobble reversals, closing
during movement and closing during opening also passed transition and cleanup checks. Recording
commands must arrive within the bounded interruption window.

Retargets retain deformation phase, seed and sampled phase/direction speed. Cubic
phase curves shorten when needed to stay monotone. Close movement retains those
clocks and starts translation at the sampled layout speed while fading separately.
Interrupted tile/column offsets now use cubic paths that retain their sampled
velocity when a movement shader is configured. Initial moves keep upstream easing.
This is not a guarantee of physical velocity or acceleration continuity across
every event, camera motion or pointer dragging. Windows remain separate
render elements. Mixed-output handoffs, capture/block-out combinations, shader
removal during close continuation and graphics-reset interactions need broader testing.

The older smoke checks covered resize and shader-removal fallback, repeated swaps
and closure of moving windows. The current recordings are described in
[the experiment guide](../experimental/README.md). The TTY path was not activated.

## Interruption stress coverage

`test-interruptions.py` passed against stock Niri 26.04 and the pinned release-built
experiment. Each run checked three rapid open/close cycles, close during a reversed
resize, four rapid width changes and a fullscreen round trip, at each of 1×, 1.5×
and 2×. All 15 cases per compositor ended with no surviving window or changed pixels
against the empty scene. Fullscreen dimensions and the restored floating width
matched expectations; render logs were clean.

The experimental run additionally passed eight column reversals with unchanged
window IDs and final columns, and removing the movement shader during transit.
These checks use transparent synthetic Quickshell clients in one nested output.
They establish state and cleanup, not perceptual seamlessness or physical mixed-output
behavior. Timing and shader-state tests complement the recordings.

The Expressive Edge Ripple and Torsion profiles each passed the same 15 stock
interruption cases across 1×, 1.5× and 2×. All endpoints were empty after close,
restored widths matched and render logs were clean. Their size-dependent shader
phase restarts with Niri's resize animation; this does not establish continuous
velocity across interrupted resizes.

```sh
python3 scripts/test-stock-scenarios.py --presets balanced --resize-profiles
python3 scripts/test-interruptions.py --resize-profile examples/profiles/edge-ripple-expressive.json
python3 scripts/test-interruptions.py --resize-profile examples/profiles/torsion-expressive.json
```

## Performance evidence

A tighter candidate search for varied fragments without waves produced byte-identical
results in **231 software-WebGL frame pairs** against the previous shader: seven
varied presets and four maximum-size/randomness uniform-grid cases, each at three
seeds and seven animation positions. Waved presets keep the previous search bounds.

Hardware shader measurements and a release-built nested capture diagnostic are
reported in [Performance](performance.md). Neither measures physical presentation
latency. The varied renderer searches 75–147 candidates for together release, up
to 441 for staged release; particle count alone does not predict cost.

## Documentation recordings

The [click-to-play gallery](https://jturbide.github.io/niri-fx/gallery/) contains
**197 GIFs**, including all **75 presets**, resize profiles and comparisons, custom
recipes, labelled Canvas concepts, native swaps and workflow/compositor scenarios.
Fragments appear first. Static posters load initially, and only one
animation plays after an explicit click.

Shader previews use 20 fps, the Studio workflow 10 fps, and current native swaps
and interruption scenarios 50 fps from an optimized release build. GIF timing and
palette reduction affect appearance; recordings are not performance measurements.
All content is synthetic. See [recording commands](gifs/README.md).

## Remaining acceptance work

- Physical presentation timing and responsiveness on integrated GPUs, larger windows,
  multiple outputs and mixed scaling; capture/encoder timing cannot substitute for it.
- Broader transparency, decorations, fullscreen and output-edge clipping. Client-side
  shadows outside the window geometry are omitted during breakup.
- Acceleration continuity, camera transitions, direct dragging, broader application
  resize/close coverage, shared per-particle ordering and graphics-reset behavior.
- Full iRiS, DMS and Noctalia desktop sessions across versions beyond the controlled
  component/picker workflows documented below.

Reproduce checks through [Contributing](../CONTRIBUTING.md). Distinguish successful
automation, visual preference and hardware performance when reporting results.

## Earlier 0.7.0 acceptance: profiles and integrations

Independent action profiles passed CLI JSON round trips, separate shader/timing
exports, opt-in resize, preservation of base iRiS resize, malformed action rejection,
and actual CLI/browser/HTTP registration. Browser checks exercise independent edits,
action switching, undo/redo, individual reset, profile import/export, viewing resize
without activation, pinned A/B comparison without changing saved B, and search.
Favorites persist across Studio ports through the authenticated preferences endpoint;
unknown favorite IDs are rejected without changing the file.

All twelve Dissolve/Iris controls independently changed rendered pixels. All six
new presets had exact intact/transparent endpoints, and halfway numeric values
matched Python and JavaScript shader exports. Software WebGL was explicitly rejected
as a GPU benchmark result. A real RTX 4070 Ti run measured five styles at three
resolutions; see [methodology and results](performance.md). It does not certify
compositor performance. The explicit shader-entry refactor also passed the nested
Spring Wobble swap/interruption/close/fallback smoke test.

The DMS QML component passed offscreen Quickshell catalog/search, apply and exact
restore against temporary Niri files. The actual DMS 1.6.2 PluginService also
discovered the plugin and instantiated its launcher provider, then passed search,
apply and restore. These checks do not replace visual testing of the full launcher.

Noctalia 5.2.1 was built from its official release source and run inside stock
Niri in a separate nested window with temporary XDG directories and a private
D-Bus session. The unmodified Niri Animations 0.2.0 picker displayed all 47 styles.
Virtual keyboard dropdown selection applied Iris Bloom then Ember Erosion, and
selecting the base pack removed the include. Stock Niri validated the resulting
configs; the isolated shell and compositor were stopped after the test.

## Maintenance refactor

The refactor preserved all 163 default action shaders across 55 presets after
stripping comments and whitespace (opening, closing, supported resize and movement).
New comments explain coordinate spaces, alpha handling and bounded inverse searches.
The Python/browser validators share 24 accepted/rejected document fixtures; the
standalone JavaScript core has no DOM or network dependency. Full Studio E2E remains
a separate check of rendering, UI state and actual temporary-registry saving.

Tests use temporary configuration and registry files. Running these checks does
not activate effects or replace the installed compositor. See [architecture](architecture.md) and the
[next-phase gates](next-phases.md).

## Workflow and compositor scenarios

Recorded on 2026-10-03. The workflow harness owns a nested Niri window, synthetic
clients, fresh HOME/XDG directories and a private session bus. It sends input and
captures only the nested output, stops its process groups and retains logs,
PNGs, source video and JSON evidence under ignored `artifacts/scenario-*`.
The installed desktop configuration is not edited. A private session bus does
not hide system D-Bus information; the published Noctalia clip crops out its bar
and uses a generic temporary preset path.

| Check | Result and scope |
| --- | --- |
| Stock Niri 26.04 | Explosion/Ghost Wisps with transparent margins and gutter; wide Shockwave (900×280), tall Pixel Wipe (300×660), Frost Vanish at 1.5× (600×400). Five cases show partial open/close, intact surfaces and zero changed pixels after closing. Recorded actions use 1400 ms; preset defaults are unchanged. |
| Studio | Actual profile import, independent closing-wind edit, pinned A/B, Undo/Redo, JSON/KDL download equality, stock Niri validation and absent resize. Chromium software WebGL; 10 fps UI recording. |
| iNiR/iRiS c08bb92 / Quickshell 0.3.1 | Unmodified `IrisNiriMotionGallery` and `NiriAnimationPresets` in a small host. Real virtual-pointer selection of Burst and Drift, Frost and Fragments, then Snappy; helper reports each active profile, resulting configs validate, base resize is preserved and prior animation file is restored exactly. The card previews are iRiS timing illustrations. |
| DMS 1.6.2 / Quickshell 0.3.1 | Unmodified `DankLauncherV2Modal` and `PluginService` in a small host load all 71 NiriFX choices. Real keyboard selection applies Fragment Flow, Undo restores exact config bytes, Studio opens as an app window. A separate check proves Undo refuses an externally edited config. This is launcher-component acceptance, not a full DMS daemon/session test. |
| NiriFX picker / Quickshell 0.3.1 | Packaged controller/view in an isolated host. Real keyboard search, Review, Apply and exact Undo; base resize stays intact. Offscreen checks also cover profiles, explicit resize consent, repeated Undo, stale files, external-edit refusal and missing commands. Studio dispatch arguments are verified; this harness does not launch Studio or test every embedding shell. |
| NiriFX picker / GJS 1.88.1, GTK 4.22.5 | Packaged GTK widget in an isolated host. Keyboard search, Review, Apply, exact Undo and close-during-Apply pass. Real CLI checks cover profiles, consent, repeated Undo, stale files, external edits and missing commands; Node tests cover overlapping requests. Studio dispatch is checked without a browser. |
| NiriFX terminal guide | Real CLI in a PTY and Alacritty on stock nested Niri. Fragment Flow selection, read-only review, confirmed Apply and exact Undo pass; base resize is preserved. Unit checks cover search, cancellation, stale files, external edits, iNiR registration without activation and refusing piped interactive input. |
| AGS source v3.1.2 (`bbee2f1`; embedded CLI label 3.1.0) | Supplied entry point with the packaged GTK widget passes real keyboard Review/Apply/Undo and clean exit. This validates the AGS application example, not a full Astal shell or GTK 3 embedding. |
| Noctalia 5.2.1 / Niri Animations 0.2.0 | Full isolated shell, 55 exported styles plus Burst and Drift. Real keyboard dropdown selection applies the independent profile, returns to base and validates both configs; fragment resize remains absent. |
| Pinned native movement patch | Explosion at 1200 ms, release build, 50 fps recording: left/right/left interruption leaves both window IDs in the expected final columns and solid color populations within 2% of the original; closing one moving client removes it and leaves the survivor intact. The harness requires acknowledgements less than 600 ms apart and rejects IPC stalls of 150 ms or more. These checks do not assert seamless retargeting or measure GPU frame time. |

The shell workflow found a standalone preflight bug with an existing inline
`animations` block. Validation now uses a separate generated include, matching
installation. The regression test uses the real Niri parser for plan/apply/restore;
CI skips only that test where Niri is not installed.

The curated-profile update adds seven pairings to the 64 single effects. Quickshell,
GTK, AGS and terminal recordings select Fragment Flow; controller checks also cover
the mixed-family Burst and Drift profile. Tests verify both action settings through
review, Apply and exact Undo. An installed wheel tested outside the checkout exports
all seven profiles through the stock Niri parser and applies/restores a 71-file
picker pack. Every pairing has a matching JSON example and shader-parity recording;
the browser checks cover Studio selection, Undo/Redo and shared-link round trips.

[Scenario metadata](gifs/scenario-manifest.json) records parameters, scales, source
profile hashes, tested shell source fingerprints and native patch revision/hash.
The docs check detects stale source profiles, preset overrides, patch metadata,
file sizes and missing gallery links. Run recording commands sequentially because
they update the shared manifest. See the [recording guide](gifs/README.md#workflow-and-compositor-recordings).

**Remaining limits:** a single nested output at 1.5× is not true mixed-monitor
acceptance; these synthetic clients do not cover every decoration/application.
Native movement remains optional and experimental. See [ROADMAP.md](../ROADMAP.md).

## General movement and shaped resize (0.13)

Three movement presets pass native column swaps and the broader rearrangement
harness: consume into a column, vertical reorder, expel, six reversals,
simultaneous move/resize, inserting then closing a client during opening, and
closing during movement. Window IDs and final layout are checked; closed windows
leave an empty scene. An exported independent movement profile also passes the
isolated demo's smoke test. The compositor patch itself is unchanged.

The browser checks eight resize shapes at aspect 0.25, 1 and 4 and a rotated
lattice. Near-zero progress retains every source pixel with one translucent owner;
zero strength and endpoints are intact. Full, Edge and Soft modes match a wider
candidate search across 72 cases per renderer: software matches exactly; hardware
retains occupancy/ownership and differs by at most one 8-bit channel step. Replays
are deterministic. Studio additionally exercises separate
old/new textures through growth and shrink, hides inapplicable controls, and
round-trips an independently edited movement slot while excluding it from stock
KDL. Forward-transformed piece vertices test the resize lookup bound.

Triangle Edge Rebuild, Hexagon Edge Rebuild and Circle Soft Reflow pass transparent
close-during-open, repeated resize, close-during-resize and fullscreen/restore
checks at sequential 1×, 1.5× and 2× scales. This is one nested output, not a mixed
physical-monitor test. Native checks establish endpoints and cleanup; they do not
prove velocity continuity across interrupted resize.

Recordings reject movement IPC calls of 150 ms or more while capture drives
regular frames. Idle nested winit scheduling is recorded separately and is not a
frame-time measurement. Synthetic test clients and their outer window are owned
by the harness; the installed compositor and active desktop effect are preserved.

## Coherent desktop motion validation

- 147 Python tests cover portable spring validation, unchanged ordinary timing,
  registry spring triples, separate window/desktop picker review, strict runtime capability parsing, refused activation
  and Apply rechecks, alongside existing snapshot/Restore protections.
- All 75 presets and 13 profiles have faithful shader previews and settings.
  The three desktop packs additionally have stock workspace/camera/overview
  recordings. Canvas previews show their window effects only.
- Mixed-shape checks cover every primary/secondary pair in documents, mixture
  endpoints and zero-mixture compatibility. Browser readbacks cover representative
  mixtures at aspect 0.25, 1 and 4, joined translucent ownership, stable replay,
  reversed opening/closing and a wider reference lookup.
- The pinned release compositor built and passed config/layout, movement-state
  and close-continuation tests. An owned nested session verified the runtime
  handshake, explicit movement Apply and exact Restore with a clean render log.
- Fragment Wake, Ribbon Transfer and Momentum Glide passed consume/expel, vertical
  reordering, six reversals, floating/tiled changes, move+resize, insertion plus
  resize/close and complete cleanup. Stock interruption tests and experimental
  Mixed Confetti tests passed at sequential scales 1, 1.5 and 2.
- All native patch recordings were refreshed. The harness now rejects unexpected
  output dimensions; recording actions retain bounded acknowledgement checks.
- Native timing tests keep outputs/workloads separate and require all three
  presentation flags for hardware claims. The published nested run contains
  estimated Winit submissions. Physical DRM acceptance remains open.

This matrix demonstrated no additional visual discontinuity requiring a new
continuation algorithm. Floating/tiled and resize endpoint checks do not prove
velocity continuity. Physical mixed monitors, pointer dragging and shared particle
state remain separate tasks in the [roadmap](../ROADMAP.md).

## Coordinated action sets

The 0.16.0 Fragments, Ribbons and Elastic sets pass all independent combinations
of resize and movement opt-in, portable round trips, stock movement omission and
shell preservation of unset resize. Browser checks exercise renamed imports,
editing away from a match, suggested controls, exact Undo/Redo and JSON-only
movement selection. All 91 stock style/profile includes parse in Niri 26.04.

Each experimental companion passes native swaps, seven interrupted reversals,
ordinary-renderer fallback and close cleanup in the pinned release build. Swap
visibility is sampled on either side of the crossing; midpoint blending can
change solid source colors without losing a window. Exact final positions and
both settled color populations are checked. The three new resize companions
also pass native stock growth/shrink to 900/400 pixels, intermediate-frame checks
and empty close endpoints.

Quickshell and GJS/GTK controllers review, apply and exactly undo each base set
with its desktop springs and both optional shader actions absent. Six shader GIFs
and three native swap GIFs use the published example settings. The native clips
retain the full source profile and its hash. [Measured resize shader costs](performance.md#coordinated-resize-companions)
remain separate from compositor presentation evidence.

## Shared Library and combo builder

The browser test files run sequentially so concurrent software WebGL contexts
do not compete for a shared CI runner. Shader checks remain enabled; readiness
timeouts report the observed state without exposing session URLs.
The harness enables its Page and Runtime domains before navigation. A real-process
regression verifies that startup hooks capture script errors on repeated reloads.
Another regression covers a briefly empty page-target list after the debugging
port becomes available, without extending the existing startup deadline.
Library transaction checks use an intact preview frame and wait for profile
operations to finish. This keeps queued software GPU draws out of UI timing;
the full rendering suite still checks intermediate pixels, endpoints and parity.

The Library uses the existing Studio document and history. Browser checks cover
independent actions, supported optional selectors, shared styles, Undo, edited
settings and browser-local profile persistence. Profile checks cover
copying, renaming, removal, replacement confirmation and preserved data after a
conflict or damaged document. The installed Library browser test uses a real
temporary Studio server and verifies its JSON files without changing Niri config.
Authenticated HTTP checks cover Save, read-only Review, Apply, exact Restore and
rejected origins/path injection.
Backend checks cover stale plans, external edits, validation rollback and Restore
isolation across configuration paths and adapters.

A stock nested Niri session exercises the installed iNiR serializer, active-profile
recognition, retained slowdown/base movement and exact Restore. The optional
compact iRiS component loads in its real module tree, shows the applied profile,
dispatches Library/Customize arguments and updates after Restore. Separate real
Niri parsing checks cover standalone and connected Noctalia Apply/Restore.

Noctalia 5.2.1 loads the API 24 shortcut in a private shell. A virtual-pointer click
on its Control Center button dispatches the expected argument array, including
paths containing spaces, quotes and shell metacharacters. DMS 1.6.2 opens the shared
app with its explicit standalone config. These checks validate the supplied
entries; other shell families use the standalone launcher and are not claimed as
native settings integrations.
