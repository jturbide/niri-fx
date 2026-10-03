# Validation and known limits

Evidence updated on **2026-10-03** for development after 0.7.0. These checks
establish behavior on the tested setups; they do not certify every GPU or desktop.
See the [changelog](../CHANGELOG.md) for user-visible changes.

## Stock effects and editor

| Check | Observed result |
| --- | --- |
| Python | 72 regression tests: validation, ownership, backup/restore, temporary HTTP saving, family capabilities and conservative CI scope selection |
| Portable JavaScript | 28 Node checks; all 64 presets' supported stock shaders match Python |
| Real Chromium | 64 rendered presets with intact/transparent endpoints, extreme controls, import/export, capabilities, independent profiles and actual HTTP saving for all nine families |
| New controls | Hex size/spread/spin/direction/stagger, ink origin/turbulence and glitch bands/chroma each change rendered pixels; transparent input stays transparent |
| Browser lifecycle and gallery | Three tests cover failed startup, bounded requests, disconnect/cleanup, gallery filtering, reduced-motion startup and single-GIF playback |
| GLSL and stock config | All supported open/close/movement/resize shader variants compile as GLSL ES 1.00; all 64 default exports, supported resize exports and 64 picker-style includes parse in stock Niri 26.04 |
| Native stock effects | All nine added presets open, render intermediate frames, settle intact and close to an empty scene in a nested stock compositor |
| Resize profiles | Elastic, Accordion and Ripple grow and shrink a synthetic client to 900 and 400 pixels, produce intermediate frames, settle correctly and close without leftovers |
| Resize defaults | Every built-in leaves resize off; viewing controls never enables it; explicit profile slots and custom choices round-trip |
| Packaging | Wheel and source distribution build; installed CLI, shader resources, icon, offline Studio and profile exports work outside the checkout |
| Documentation | Local links, example commands, preset/profile recordings, native source hashes and generated gallery/poster hashes are checked |

Browser rendering uses software WebGL for deterministic behavior checks. Native
checks use synthetic clients, fresh config directories and separate nested Niri
windows. They do not replace or alter the login compositor.

The earlier transparency, window-shape and fractional-scale cases below remain
useful regression evidence. Adapter UI recordings describe the versions and
catalog size actually exercised; new family support is checked through the current
file contract and Studio save flow, not assumed from those older recordings.

## Native movement and continuity

The experimental patch applies to Niri revision
`8ed0da44d974c32c6877d2f4630c314da0717ecb`. A release build passed 19 config tests,
one config integration test, 12 layout-animation tests and three new continuity
state tests for uninterrupted motion, reversal and repeated retargets/render passes.

Ten native swap recordings passed final-position and intact-color checks with
clean render logs. Interrupted swapping, closing during movement and closing
during opening also passed visible-transition and final-cleanup checks. Recording
commands must arrive within the bounded interruption window.

Retargets retain the deformation phase and seed, with smoothly blended direction
impulses. Close interruptions continue the original effect while fading. This is
visual-state continuity, not a claim of continuous physical velocity or acceleration
across every layout change. Windows remain separate render elements. Mixed-output
handoffs, capture/block-out combinations, shader removal during close continuation,
fullscreen and graphics-reset interactions need broader testing.

The older smoke checks covered resize and shader-removal fallback, repeated swaps
and closure of moving windows. The current recordings are described in
[the experiment guide](../experimental/README.md). The TTY path was not activated.

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
**134 GIFs**, including all **64 presets**, resize profiles and comparisons, custom
recipes, labelled Canvas concepts, ten native swaps and twelve workflow/compositor
scenarios. Fragments appear first. Static posters load initially, and only one
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
- Continuous physical velocity across retargets, direct dragging, simultaneous
  resize/close, shared per-particle ordering and graphics-reset behavior.
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

The installed desktop config and preset registry are outside the hygiene change.
No active effects, resize choices, shell integrations or compositor binaries are
changed by this maintenance work. See [architecture](architecture.md) and the
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
| DMS 1.6.2 / Quickshell 0.3.1 | Unmodified `DankLauncherV2Modal` and `PluginService` in a small host load the NiriFX adapter. Real keyboard search/selection applies Balanced, Undo restores exact config bytes, Studio opens as an app window. A separate check proves Undo refuses an externally edited config. This is launcher-component acceptance, not a full DMS daemon/session test. |
| Noctalia 5.2.1 / Niri Animations 0.2.0 | Full isolated shell, 55 exported styles plus Burst and Drift. Real keyboard dropdown selection applies the independent profile, returns to base and validates both configs; fragment resize remains absent. |
| Pinned native movement patch | Explosion at 1200 ms, release build, 50 fps recording: left/right/left interruption leaves both window IDs in the expected final columns and solid color populations within 2% of the original; closing one moving client removes it and leaves the survivor intact. The harness requires acknowledgements less than 600 ms apart and rejects IPC stalls of 150 ms or more. These checks do not assert seamless retargeting or measure GPU frame time. |

The shell workflow found a standalone preflight bug with an existing inline
`animations` block. Validation now uses a separate generated include, matching
installation. The regression test uses the real Niri parser for plan/apply/restore;
CI skips only that test where Niri is not installed.

[Scenario metadata](gifs/scenario-manifest.json) records parameters, scales, source
profile hashes, tested shell source fingerprints and native patch revision/hash.
The docs check detects stale source profiles, preset overrides, patch metadata,
file sizes and missing gallery links. Run recording commands sequentially because
they update the shared manifest. See the [recording guide](gifs/README.md#workflow-and-compositor-recordings).

**Remaining limits:** a single nested output at 1.5× is not true mixed-monitor
acceptance; these synthetic clients do not cover every decoration/application.
Native movement remains optional and experimental. See [ROADMAP.md](../ROADMAP.md).
