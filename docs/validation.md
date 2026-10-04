# Validation and known limits

Evidence updated on **2026-10-04**, including 0.18.0 pointer previews, integration
and agent support, plus the subsequent experimental resize geometry fix. These checks
establish behavior on the tested setups; they do not certify every GPU or desktop.
See the [changelog](../CHANGELOG.md) for user-visible changes.
For setup instructions, use the [documentation index](README.md); check
[Compatibility](compatibility.md) for supported features and requirements.

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
| Python | Regression coverage for validation, ownership, backup/restore, temporary HTTP saving, family capabilities, curated profiles, terminal workflows, movement diagnostics, isolated patch stacks and conservative CI scope selection |
| Portable JavaScript | All 75 presets' supported stock shaders match Python, with picker transactions, profile checks and complete combo playback |
| Real Chromium | 75 rendered presets with intact/transparent endpoints, extreme controls, import/export, capabilities, independent profiles and actual HTTP saving for all nine families |
| New controls | Hex size/spread/spin/direction/stagger, ink origin/turbulence and glitch bands/chroma each change rendered pixels; transparent input stays transparent |
| Browser lifecycle and gallery | Coverage includes failed startup, bounded requests, disconnect/cleanup, shared starter selection, pairing/search filters, direct anchors, collection URLs, all nine cross-family Studio filters, unchanged effect documents while browsing, narrow layouts, reduced-motion startup, single-GIF playback, hosted Studio share/download flows and explicit companion selection through import and Undo |
| GLSL and stock config | All supported open/close/movement/resize shader variants compile as GLSL ES 1.00; all 75 default exports, supported resize exports and 91 style/profile picker includes parse in stock Niri 26.04 |
| Native stock effects | All nine added presets open, render intermediate frames, settle intact and close to an empty scene in a nested stock compositor |
| Curated pairings | Geometric Flow, Ribbon Current and Soft Landing render partial opening/closing frames, settle intact and close to an empty scene in stock Niri. Sampling uses an 8× slower isolated animation clock to avoid missing short phases during screencopy; this does not measure real-time presentation smoothness. |
| Fragment optimization | 1,050 reference-frame pairs across software WebGL and hardware ANGLE match byte-for-byte, including extreme settings and transparent input. Core Detonation, Mosaic Burst and Orbital Ribbons pass stock open/close checks; Core Detonation also passes native swaps, interruptions and fallback. See [measurements and reproduction](performance.md#varied-fragment-flight-bounds). |
| Fragment shapes | Eight shapes restore translucent source coverage without an endpoint shortcut, including aspect 0.25 and 4, with stable replay and reversed opening/closing paths. Forward-transformed vertices exercise the inverse lookup bound. 240 reference-frame comparisons across software and hardware match frame hashes and alpha totals. At the 0.12.0 release, all 66 pre-existing presets kept byte-identical stock and movement shaders. |
| Shaped native actions | All four new presets pass transparent stock open/close and the patched movement smoke test (swaps, six interruptions, close during movement, supported resize and fallback). Triangle Shatter and Hex Swarm also pass sequential 1×/1.5×/2× interruption cases and eight rapid reversals; both have native swap recordings. |
| Vortex distortion | Existing distortion presets match 126 reference-frame pairs against 0.10.0 byte-for-byte. Signed twist, contraction, origin, extreme geometry and transparent source pass browser checks. Both presets pass stock open/close and cleanup. Vortex Fold passes native swaps, six interrupted swaps, close during movement, resize and fallback. |
| Resize profiles | All ten curated profiles (Elastic, Accordion, Ripple, Subtle/Expressive Edge Ripple and Torsion, plus Fragments/Ribbons/Elastic Motion) grow and shrink a transparent synthetic client to 900 and 400 pixels, produce intermediate frames, settle correctly and close without leftovers |
| Resize rendering | Edge Ripple and Torsion pass forward-time grow/shrink, exact texture endpoints, signed and zero controls, filled bounds at extreme aspect ratios and Python/JavaScript shader parity checks |
| Resize defaults | Built-ins preserve existing resize settings; viewing controls never adds a resize override; explicit profile slots and custom choices round-trip |
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
one config integration test, 19 layout-animation tests, seven shader-continuity tests,
seven position-continuity tests and five size-animation tests. These check repeated
reversals, first derivatives, monotone phase handoffs, zero-distance momentum,
spring input, slow/frozen clocks,
disabled animation semantics and closing along the actual layout path.

Eighteen native swap presets and three coordinated action-set swaps passed
final-position and intact-color checks with clean render logs. Interrupted swapping, eight rapid wobble reversals, closing
during movement and closing during opening also passed transition and cleanup checks. Recording
commands must arrive within the bounded interruption window.

All 30 existing native clips were refreshed for the updated patches: 21 swaps,
four interruption scenarios, two overlap/floating scenarios and three pointer
styles. The original settings and durations were retained; each GIF uses 20 ms
frame delays. Two additional resize comparisons document the geometry change below.

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

## Resize geometry continuity

When an animated resize reverses, the experimental renderer now retains the
displayed width and height and their sampled velocities. Adjacent columns and
stacked windows follow matching paths. Retargeting one axis leaves the other
axis's curve and finish time intact. This applies when a custom movement shader
is configured and resize animation is enabled; stock rendering and explicitly
disabled resize keep their existing behavior. No preset enables resize by default.

The original regression reproduced a 12-pixel edge separation 100 ms after a
resize reversal: the resized window restarted its size curve while its neighbor
retained movement velocity. The current movement build passes 19 layout-animation
tests and five size-animation tests; the pointer build passes 23 and five,
respectively. Coverage includes repeated reversals, orthogonal retargets, small
size changes, client-driven size changes, disabled resize, original easing and
slow or frozen clocks.

The [native comparison report](benchmarks/resize-continuity.json) records two
sequential captures of each case: the verified v0.18.0 movement build and the
updated build at the same pinned Niri revision. Identical passthrough shaders
expose the geometry. Both use synthetic cards, a 1200 ms linear resize, a reversal
after approximately 600 ms, and a nominal 16-pixel gap.

| Case | Baseline gap range | Updated gap range | Recording |
| --- | --- | --- | --- |
| Width reversal beside another column | 7 to 83 px | 17 to 18 px | [Side-by-side width comparison](gifs/native-resize-width-comparison.gif) |
| Height reversal above another window | 10 to 56 px | 16 to 18 px | [Side-by-side height comparison](gifs/native-resize-height-comparison.gif) |

Each range covers 142 decoded native video frames. Edge detection allows four
pixels for video conversion; measurements precede GIF scaling and palette
reduction. The report verifies executable, patch, fixture and recorder hashes,
unchanged window IDs, settled dimensions and bounded IPC timing. Historical
build metadata absent from the v0.18.0 manifest is listed as unavailable rather
than inferred. These are geometry checks, not frame-time or physical-display
measurements.

To reproduce, keep a v0.18.0 movement build in a separate checkout, with its
executable and build manifest intact. Build the updated experiment, then run:

```sh
python3 scripts/build-niri-movement.py --release --test
python3 scripts/record-resize-comparison.py \
  --baseline-manifest /path/to/niri-fx-0.18/artifacts/niri-movement-build.json \
  --baseline-tag v0.18.0
```

The recorder writes under `artifacts/resize-comparison/`. See the
[recording guide](gifs/README.md#native-resize-geometry-comparisons) for dependencies,
baseline verification and deliberate publication with `--publish`.

The resize shader's deformation phase can still restart, and closing during
resize still uses a snapshot. Extreme retargets can reach the one-pixel size
clamp while a neighbor's movement curve continues past it. Changing animation
timing during an active resize can also desynchronize neighboring paths. Those
cases, acceleration continuity, camera movement and physical mixed-output
behavior remain outside this fix.

## Pointer-driven wobble

The separate pointer build passed 20 configuration tests, the wiki parse check,
23 layout-animation tests, seven position-continuity tests, five size-animation
tests, seven movement-shader state tests and seven analytical spring tests. The
base movement patch and binary remain separately usable.

The native layout suite covers pointer-state grab/release and animation-disable
behavior, plus three output-lifecycle regressions for both tiled and floating
windows: destination-output removal during drag, last-output removal before
release, and output restoration with new input before release. They verify
continuous deformation, retained grab ownership, recovery without lost or
duplicated windows, and spring cleanup after settling. These are deterministic
layout tests, not physical monitor hotplug or mixed-monitor acceptance.

All three pointer presets passed real Wayland input checks in an owned nested
compositor: floating reversals and visible release settling, a real return drag
with matching settled geometry and pixels, convergence while held still,
regrab/input, a genuinely detached tiled drag, four disable paths
during a grab, and close cancellation with input reaching the surviving client.
The four disable paths are node removal, zero strength, movement off and all
animations off. Render logs were clean, and the three public recordings retain
50 fps playback with synthetic content.

The additional [hardening checks](benchmarks/pointer-hardening.json) use direct
`grim` ScreenCapture and two synthetic opaque cards. With `block-out-from
"screen-capture"`, protected content stays hidden during real dragging, rule
changes and the closing snapshot; a public card remains visible as a control.
The harness requires a nonempty redacted closing snapshot followed by an empty
endpoint for that window. With `block-out-from "screencast"`, protected content
remains visible in ScreenCapture as the negative control. This does not test the
Screencast render target, a portal or PipeWire transport.

Abrupt termination with SIGKILL is covered for grabbed floating and detached
tiled clients. A surviving client accepts actual clicks and a subsequent drag.
Disconnecting a virtual pointer while its button is held exposes a known limit:
unpressed motion from a replacement pointer still moves the grabbed window.
A replacement press/release recovers input. This occurs with deformation enabled
and omitted in the patched executable, and in an unmodified build at the same
pinned revision. Device-owned grab cleanup remains open.

The optional `--output-targets` probe uses a second owned compositor and retains
strict assertions. It currently fails on the tested GPU: the child's direct
capture clears after closing while the parent's image stays stale, even with
pointer deformation and privacy rules omitted. Both compositors continue
submitting frames. Output/Screencast privacy remains unverified. Actual PipeWire capture,
popup and blurred-background combinations also remain untested.

The [unmodified comparison](benchmarks/native-baseline.json) reproduces both
failures at the identical pinned revision, release flags and Rust compiler on
the same RTX 4070 Ti/NVIDIA renderer. In all three variants (unmodified, patched
with pointer omitted, patched with pointer enabled), Output and debug Screencast
retain pixel-identical closing frames in six independent samples about 2.7–5.3
seconds after a 1.6-second close. Direct captures are clear, with the public
control visible in every sample. Clicking the surviving client clears the stale
parent image. The FX patches are therefore not necessary to reproduce either
failure; compositor, driver and nested-harness causation remains unisolated.

Reproduce without replacing the login compositor:

```sh
python3 scripts/build-niri-movement.py --unmodified --release --test
python3 scripts/build-niri-movement.py --pointer-wobble --release --test
python3 scripts/test-native-baseline.py
```

The diagnostic writes sanitized evidence under `artifacts/` and exits **1** when
either failure reproduces. A completed baseline comparison is not a passing
acceptance test. `--probe disconnect` or `--probe output` selects one investigation.

`test-pointer-integration.py` also passed against the owned pointer session.
It served Studio through its actual HTTP backend, reviewed and applied a
pointer-only profile, combined movement/pointer settings and a zero-strength
override, then verified runtime state and exact Restore after each. It rejected
a stock-binary mismatch and loss of runtime capability before writes. The
selected executable validated configs throughout. No login-session configuration
was changed.

Stacked-profile checks also cover restoring native settings after a stock
selection: missing runtime support refuses reactivation, while a verified session
can restore the native profile and then return exactly to the stock baseline.

Browser checks cover preset/custom pointer controls, preservation through shared
style changes and Undo, portable JSON and experimental downloads matching Python.
The native download combines selected movement and pointer settings in one block.
Pointer-enabled combos now include a repeatable drag/reverse/release phase.
Interactive Studio dragging uses the same native spring and shader math with
synthetic input. Nine Rust-generated reference traces cover 134 sampled states;
Node checks compare the browser spring and shader against the unchanged native
implementation. Real Chromium checks cover corner anchors, regrabbing during
settling, CSS letterboxing, pointer capture loss, keyboard playback and Escape,
reduced motion, view changes and unchanged profile/Undo state. These checks do
not validate compositor input, capture, damage or presentation latency.

[Reproduce the checks](pointer-wobble.md#reproduce-validation-and-showcases) or
inspect the [pointer lifecycle results](benchmarks/pointer-wobble.json) and
[hardening results](benchmarks/pointer-hardening.json). These checks do not certify
physical input latency, Output/Screencast or PipeWire privacy, mixed outputs,
popups, blurred backgrounds or graphics-reset behavior. GPU-program failure uses the ordinary-renderer path
in the implementation; injected GPU failure was not part of this run. Closing
retains a snapshot of pointer deformation, not its ongoing spring simulation.

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
**205 GIFs**, including all **75 presets**, resize profiles and comparisons, custom
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
exports, explicit resize selection, preservation of base iRiS resize, malformed action rejection,
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

This historical check covered the then-current catalog of 55 presets. The refactor
preserved all 163 default action shaders after stripping comments and whitespace
(opening, closing, supported resize and movement). Comments documented coordinate
spaces, alpha handling and bounded inverse searches. Python/browser validators
shared 24 accepted/rejected document fixtures; the standalone JavaScript core had
no DOM or network dependency. These counts describe that refactor's evidence.

Full Studio E2E separately checked rendering, UI state and actual saving with
temporary configuration and registry files. The tests did not activate effects
or replace the installed compositor. See [Architecture](architecture.md) and the
[development design notes](next-phases.md) for implementation guidance.

## Workflow and compositor scenarios

Recorded on 2026-10-03 in a separate nested Niri window with synthetic clients,
temporary configuration and a private session bus. Only the nested output was
captured; the installed desktop configuration was unchanged. A private session
bus does not hide system D-Bus information, so the published Noctalia clip crops
out its bar and uses a generic temporary preset path.
[Reproduce the workflow recordings](gifs/README.md#workflow-and-compositor-recordings).

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
of resize and movement selection, portable round trips, stock movement omission and
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

## Agent workflow

Agent discovery and parameter metadata are tested without subprocess or socket
access. Compact catalog IDs match full documents; a chosen preset can become a
validated portable combo while stock exports omit optional native actions.
The published skill was also followed as a CLI consumer to create an offline
preview and review, apply and restore an owned temporary configuration using
real stock Niri validation. Installed-package checks cover the bundled skill.
These checks establish the terminal workflow, not MCP or specific agent-client
interoperability.

```sh
python3 -m unittest discover -s tests -p 'test_agent.py' -v
```

## Shared Library and combo builder

Browser regressions verify script-error reporting across reloads, delayed readiness,
invalid startup responses, timeouts and bounded process cleanup. Failure reports retain
diagnostics without exposing session URLs. Library transaction checks verify
completed profile operations separately from shader rendering; the rendering suite
checks intermediate pixels, endpoints and export parity.

Complete combo preview checks cover per-action styles and durations, stable seeds,
omission of unselected actions, grow/shrink texture exchange and movement position
continuity. The controller freezes a validated document and invalidates old frame
callbacks when stopped. An actual offline Studio browser test verifies selected
shader uniforms, the transparent closing endpoint, reduced motion, cancellation,
shared prefab styles and Undo without changing the edited document. Preview does
not validate a live compositor or activate an effect.

```sh
node --test tests/combo-preview.test.mjs
node --test tests/combo-preview-browser.test.mjs
node scripts/record-combo-showcases.mjs
```

The [release acceptance check](releases.md#verify-an-upgrade) installs the
checksum-verified official 0.16 wheel, preserves old exported JSON, favorites,
iNiR registry entries and an existing CLI Restore snapshot over an upgrade, then
exercises installed Library Save/Review/Apply/Restore in disposable configurations.
It also checks installed combo playback against an unchanged imported document.
This synthetic registry test does not cover every downstream shell customization.

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

A native dialog lifecycle regression closes and reopens the profile dialog in
one task, then verifies collision handling and a successful rename. Delayed close
events from an earlier operation cannot clear the current operation's state.

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
