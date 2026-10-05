# Contributing

Small, focused contributions are welcome. For a larger feature or compositor
backend, open an issue describing the intended behavior before implementing it.
Check the [project roadmap](ROADMAP.md), [compatibility](docs/compatibility.md) and
[movement limits](experimental/README.md) first. Read the [architecture](docs/architecture.md),
[effect contribution guide](docs/adding-effects.md) and [next phases](docs/next-phases.md)
for implementation boundaries and acceptance criteria. Agent-assisted contributions
also follow [AGENTS.md](AGENTS.md); using NiriFX as an agent is covered separately
in the [agent guide](docs/agents.md).

## Development setup

Use Python 3.10+ from the repository root. Runtime code has no external Python
dependencies. Install development tools in a virtual environment:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
npm ci --ignore-scripts
.venv/bin/ruff check .
.venv/bin/ruff format --check .
npm run lint
npm run format:check
npm test
python3 -m unittest discover -s tests -v
python3 scripts/check-docs.py
python3 scripts/validate.py --require-glsl --require-niri
.venv/bin/python -m build
```

Install `glslangValidator` and Niri through your distribution for the shader and
configuration checks. CI requires GLSL validation for rendering changes; local
`--require-niri` also checks stock Niri config parsing. Tests use temporary files and a loopback server,
so local socket access must be available. Do not point tests at your real registry.

For editor/rendering changes, use Node 22+ and Chromium/Chrome (or `CHROME_BIN`):

```sh
python3 -m niri_fx preview --output /tmp/fragments-review.html
node scripts/browser-smoke.mjs file:///tmp/fragments-review.html
# Full CLI/browser/save flow, using temporary config only:
npm run test:browser
python3 scripts/studio-e2e.py
```

For changes to installation or first-use guidance, exercise Library with an empty
temporary account and the candidate package:

```sh
node scripts/test-first-use.mjs
node scripts/test-first-use.mjs --wheel dist/niri_fx-X.Y.Z-py3-none-any.whl
# Also exercise the installed iNiR serializer with temporary configuration:
node scripts/test-first-use.mjs --inir-root /path/to/inir \
  --wheel dist/niri_fx-X.Y.Z-py3-none-any.whl
```

This checks selection, per-action choices, save/review/cancel, Apply, reopening
Studio and exact Restore through the real UI. `--inir-root` additionally checks
the real shell helper's serialization and active-style recognition while reading
its installed source without modifying it. It needs Node 22+, Chromium and
stock Niri for config validation; it does not connect to a desktop session.

Use a fresh output filename. `--save-test` is only for a Studio process explicitly
pointed at a temporary registry. Software WebGL validates rendering behavior and
export parity; it is not a compositor GPU benchmark. See
[validation](docs/validation.md) and [GIF reproduction](docs/gifs/README.md).

## Project layout

| Location | Responsibility |
| --- | --- |
| `niri_fx/` | Canonical implementation, module entry point and packaged assets |
| `niri_fx/model.py`, `parameters.py`, `presets.py` | Shared parameter catalog, validation and built-in styles |
| `niri_fx/catalog.py` | Shared starter selection, curated collections and open/close pairings, normalized picker documents and shared family labels |
| `niri_fx/documents.py`, `profiles.py`, `pointer.py`, `motion.py` | Shell-independent documents, action choices, pointer controls and desktop springs |
| `niri_fx/agent.py`, `agent_data/nirifx/SKILL.md` | Canonical agent operation map, parameter metadata and packaged CLI skill |
| `niri_fx/effects.py`, `shaders/` | Shader assembly and stock/experimental export boundaries |
| `niri_fx/setup.py`, `pack.py`, `storage.py` | Setup plans, preset folders, shared atomic writes, snapshots and conflict-aware restore |
| `niri_fx/library.py`, `library.js` | Shared ready-made selection, action combos, saved documents and reviewed activation adapters |
| `niri_fx/integration.py` | iNiR helper contract and safe registry updates |
| `niri_fx/picker.py`, `qml/`, `gtk/`, `integrations/ags/` | Optional desktop pickers, reusable views/controllers and AGS example; writes stay in the CLI |
| `niri_fx/terminal.py` | Recommended preset presentation and a line-oriented guide using the shared setup/restore backend |
| `niri_fx/preview.py`, `effect-core.js` | Offline assembly and DOM-free browser validation/shader generation |
| `niri_fx/studio.py`, `preview.html`, `studio.js`, `studio.css`, `motion-preview.js` | HTTP/app lifetime, editor state, actual shader previews and labelled movement concepts |
| `tests/`, `tests/fixtures/`, `scripts/validate.py`, `scripts/browser-smoke.mjs` | Shared document cases, domain/storage tests, shader parity and real browser checks |
| `scripts/lib/browser.mjs` | Chromium startup, bounded protocol calls, readiness and cleanup shared by all browser tools |
| `experimental/`, `scripts/build-niri-movement.py`, `scripts/nested-demo.py` | Pinned movement patch, optional pointer extension and isolated native demos |
| `docs/`, `CHANGELOG.md` | User guidance, evidence and release history |

## Code conventions and checks

- Use `niri_fx` and `niri-fx` exclusively. During 0.x, obsolete APIs and formats
  may be replaced as the design improves. Document breaking changes under
  Unreleased and provide practical migration guidance. The future 1.0 release
  will define a public contract that remains backward compatible throughout 1.x;
  see the [stability policy](docs/stability.md) before changing public interfaces.
  Single-effect documents use schema 3; independent profiles use kind `profile`, schema 2 without a swap override and schema 3 with one (schema 1 imports retain their behavior).
- Python targets 3.10+, uses four spaces and Ruff lint/format (100 columns).
  Run `.venv/bin/ruff check --fix .` and `.venv/bin/ruff format .` before review.
- JavaScript, CSS, HTML and workflow YAML use Prettier; JavaScript also uses ESLint.
- QML components use Qt's `qmlformat` and `qmllint`. With Quickshell and Niri
  installed, run `python3 scripts/test-quickshell-picker.py` for real controller/view
  acceptance against temporary files. CI checks the portable backend and packaged
  QML resources; the Quickshell runtime test is a local gate for picker changes.
- GTK modules are ES modules for GJS; `controller.mjs` is toolkit-independent and
  covered by `npm test`. Run `python3 scripts/test-gtk-picker.py` inside Niri with
  GJS, GTK 4.10+ and wtype; `--ags /path/to/ags` also checks the AGS 3 example.
  These isolated runtime tests are local gates for GTK/AGS changes. CI checks
  the portable controller and installed resources without desktop dependencies.
  Run `npm run format`. The lockfile pins development tools; npm is not a runtime
  dependency. Studio sources are readable files assembled into one offline HTML page.
- Comments should explain units, bounds, ordering, ownership and design choices.
  For terminal workflow changes, run `python3 scripts/test-terminal.py` with Niri
  and util-linux `script` installed; `--record` uses an isolated Alacritty/Niri
  output for the showcase. Core tests also cover cancellation and stale reviews.
  Avoid line-by-line narration, commented-out experiments and undocumented magic
  numbers. Keep mathematical rationale beside the GLSL and architecture in its guide.
- Put behavior in small shared functions; keep family-specific rendering in GLSL
  templates and capabilities in the family catalog. Check rendered behavior when
  changing shaders. The compact and varied renderers have different costs.
- Add focused unit tests for validation/math/contracts and temporary-file integration
  tests for ownership, restore and migrations. Browser E2E checks render actual
  pixels, compare Python exports and save all families through the real Studio CLI.
  `npm test` also runs the DOM-free browser core with the same document cases as
  Python and compares supported stock/native shaders and combined pointer KDL. `npm run test:browser`
  tests real Chromium launch/error/timeout/cleanup and gallery filtering/playback before the full editor E2E.
  Avoid duplicating these with a separate framework just to increase test counts.
  Library save and desktop Apply workflows emulate reduced motion before loading
  Studio, including after reloads, to avoid queuing unrelated software-GPU playback.
  Their real WebGL previews and transaction assertions remain enabled; dedicated
  animation tests and rendering matrices cover intermediate frames.
- GitHub Actions classifies changes conservatively. Documentation/media changes
  keep lint, Node tests, docs checks and site construction. An exact allowlist of
  native compositor tools/patches and agent discovery files also keeps both Python
  test matrices and installed-package checks, while skipping unchanged portable
  GLSL and browser/Studio rendering suites. Native changes still need the local
  compositor checks below. Renderer, editor, shared contracts, examples and unknown
  paths require the complete suite; so do manual runs, release branches/tags,
  version changes and unavailable history. Mixed changes take the broader scope.
  Required job names stay unchanged, and failed or malformed selection fails them.
- Native pointer spring and shader math share a contract with the browser preview.
  The always-on Node tests verify native source hashes, recorded Rust traces and
  GLSL adaptation. After reviewing native math changes, regenerate the traces with
  `python3 scripts/pointer-preview-reference.py`, verify them with the same command
  plus `--check`, and update the browser adapter when needed. Changes to the trace
  fixture, generator or adapter require the full rendering suite. Native harness
  changes alone do not alter the browser's runtime inputs.
- CI caches pip and npm downloads using the dependency-file hashes. Each run still
  installs its dependencies and tests fresh outputs; virtual environments, shader
  results, browser profiles and generated packages are not reused as test evidence.
- Software WebGL probes reuse up to eight compiled programs for replay and reversal
  checks. CI runs browser workflows, three shape-aspect matrices, motion and Studio
  rendering as six independent jobs. The required `browser` aggregate checks every
  result; failures do not cancel other shards. Stage timings appear in job summaries.
  `python3 scripts/studio-e2e.py` still runs the complete rendering/save suite locally.
  Use `--suite studio|shapes|motion` for a focused run; shape shards accept
  `--shape-aspect 0.25|1|4`. These controls select tests, not effect quality.
  The full local suite has a 15-minute deadline; each CI rendering job has a
  20-minute limit. Individual browser requests keep bounded deadlines.
- Full GitHub Actions runs lint, Python 3.10/3.14 tests, GLSL compilation, docs/media
  checks, wheel installation and browser E2E. The optional DMS adapter test requires Quickshell; the [GPU harness](docs/performance.md) requires hardware timer queries. Stock Niri parsing and patched native
  smoke checks also run locally where the compositor is available. CI is not GPU
  performance certification or a desktop deployment pipeline.
- Reproduce [picker and compositor workflows](docs/gifs/README.md#workflow-and-compositor-recordings)
  in owned nested sessions. Keep the [roadmap](ROADMAP.md) status and
  [validation record](docs/validation.md) aligned with actual evidence.

Tool configurations: [Ruff](https://docs.astral.sh/ruff/configuration/),
[ESLint](https://eslint.org/docs/latest/use/configure/configuration-files),
[Prettier](https://prettier.io/docs/configuration).

## Public documentation and media

Write user guides for someone discovering NiriFX for the first time: explain
what a feature does, how to use it and which setups it supports. Use the changelog
for release history and the engineering/testing guides for implementation details.
Keep limitations explicit, especially stock Niri versus experimental movement and
pointer drag. Describe source-checkout additions as Unreleased until they ship in
a versioned package.

Keep personal configurations, local workspace paths, session URLs, raw audit
reports, planning conversations and outreach drafts out of commits and PR bodies.
A tracked directory named `internal` is still public; use an ignored location or
separate private workspace for that material. Keep the roadmap focused on future
outcomes, the changelog on delivered changes, and public design/testing guides on
constraints, reproducible evidence and known limits.

Use sample content in media. Inspect representative frames of each recording,
including menus and status messages; text inside images is not covered by a
source secret scan. Keep local investigations under ignored `artifacts/`.

After changing recordings or gallery metadata, run `python3 scripts/build-gallery.py` (Pillow required), then `python3 scripts/build-gallery.py --check`. GitHub Pages publishes the checked static gallery after changes reach main. Posters load first; playback is explicit and limited to one GIF.

The [preset reference](docs/presets.md) is generated from the same canonical
catalog and recording documents as the gallery. Do not edit its tables by hand.
Run `python3 scripts/build-gallery.py` after catalog or recording changes; check
mode rejects missing or duplicate recordings, mismatched parameters and a stale
reference. Keep every preset and pairing visible in the [visual catalog](docs/catalog.md).

A finished preset should have a clear visual purpose, a recognizable name and a
faithful preview at its actual configured timing. Prefer useful variations over
near-identical entries. Document the effect's supported actions and a simple way
to try it. Add focused parameter comparisons when they explain a meaningful choice.

Before submitting, inspect `git diff --cached`, check new files for private data
and run the documentation check. A clean scanner result complements manual review;
it does not replace it. Examples should use generic paths and names.

## Review expectations

- Explain the problem, resulting behavior, and checks run in the pull request.
- Add an **Unreleased** changelog entry for user-visible behavior, defaults,
  compatibility, packaging or substantial documentation changes.
- Preserve existing resize settings unless a resize style is selected. Keep
  movement shaders and pointer nodes out of stock Niri exports, including explicit
  zero-strength pointer settings.
- Preserve unrelated presets and timings, backups, symlinks and explicit custom
  choices. Registration and saving must remain separate from activation.
- Keep Python and browser parameter validation, pointer documents and shader
  generation consistent. Optional pointer settings are profile metadata, not a
  fifth shader action. All built-in profiles leave pointer settings unset.
- Test behavior that can regress; avoid tests that only repeat implementation.
- Use synthetic content in captures. Do not commit user configs, session tokens,
  raw recordings, binaries, toolchains or the `artifacts/` directory.

Changes to either Niri patch need the pinned build/tests and a nested-session check.
Do not replace a contributor's login compositor to run tests. Explain any new
capture, damage, rendering or interruption behavior and its validation limits.
Run native captures one at a time and keep their owned compositor window visible.
Concurrent browser automation or an obscured window can delay frame callbacks;
a late sample cannot establish that a short animation is absent.

Original NiriFX contributions use [MIT](LICENSE). Changes derived from Niri
in the movement/pointer patches and their browser pointer-preview adapter use
[GPL-3.0-or-later](experimental/COPYING-NIRI).
Preserve attribution for any imported code; see [third-party notices](THIRD_PARTY.md).
There is no CLA. Follow the [release guide](docs/releasing.md) for maintainer tasks.

For hosted Studio, `python3 scripts/build-site.py --output /tmp/nirifx-site` stages
both pages and their downloadable settings in a fresh directory. The browser suite
covers gallery-to-Studio links, edited share round trips, profile actions, malformed
input and exclusion of local session tokens.

For overlapping compositor actions, run `python3 scripts/test-interruptions.py`
and, after building the pinned experiment, add `--experimental`. These tests use
owned nested sessions with transparent fixtures. Sequential output scales are not
a substitute for physical mixed-monitor acceptance.

## Native pointer and agent acceptance

For changes to pointer profiles, capability verification or reviewed native
activation, build the optional extension and run the owned-session integration
check from a working graphical session:

```sh
python3 scripts/build-niri-movement.py --pointer-wobble --test
NIRIFX_POINTER_MANIFEST=/path/to/candidate/manifest.json \
  python3 scripts/test-pointer-integration.py
```

Use the candidate manifest printed by the builder. Each attempt has its own
source, target and published executable; it never replaces an earlier build.
See [candidate selection](experimental/README.md#isolated-build-candidates) for
movement, fragment and baseline checks.

The integration check starts a separate nested compositor and temporary Studio
server. It verifies the selected executable, live pointer contract, authenticated
review/Apply, capability-loss refusal, config reload and exact Restore. It covers
pointer-only settings, pointer plus timed movement and an explicit zero-strength
override without enabling resize. Evidence remains under ignored `artifacts/`.
It never replaces the login compositor or writes its configuration.

For renderer or spring changes, also run `python3 scripts/test-pointer-wobble.py --all`.
Use `--record` only when regenerating the native showcases, then rebuild the gallery
and check the recording source hashes. The timed browser preview cannot validate
actual pointer drag or release behavior. Physical mixed-monitor acceptance remains
separate from these nested checks.

Run `python3 scripts/test-pointer-hardening.py` for direct ScreenCapture privacy,
dynamic rules, closing snapshots, abrupt client exit and held-button device
disconnection. For the device-ownership fix, run
`python3 scripts/test-pointer-ownership.py` and repeat with `--pointer-wobble`.
Both builds must retain surviving presses/grabs and end removed-owner grabs;
same-button overlap and binding suppression must also pass. Physical unplug/replug
remains a separate hardware gate. The optional `--output-targets`
probe remains strict and currently fails on stale parent output in the tested
GPU setup. `scripts/test-native-baseline.py` preserves the earlier comparison of both failures on
unmodified pinned Niri with identical build settings; its exit status remains
nonzero while defects reproduce. Do not report Output,
Screencast or PipeWire privacy as validated from the default run. See the
[recorded scope and remaining work](docs/validation.md#pointer-driven-wobble).

For resize-to-close changes, use
`python3 scripts/test-resize-close.py --suite all --output-targets` with the
matching base build. It checks material/geometry continuation, first-frame
appearance, capture policies, transparent margins, a popup, native decorations,
Off and output-scale fallback in owned nested sessions. The
[recording guide](docs/gifs/README.md#native-resize-to-close-comparison) describes
the separate comparison recording and its required acceptance report.

For agent support, exercise the packaged `agent-info`, `--parameters` and `--skill`
commands as a consumer. Discover a real preset, build and inspect its JSON, and
produce an offline preview. Run reviewed Apply and Restore only against newly
created temporary config and state directories. Check the exact reviewed paths,
`plan_sha256`, transaction ID and restored bytes. Keep the canonical operation map
in `niri_fx/agent.py` and the packaged skill consistent with the CLI; an agent
adapter must reuse setup transactions rather than add a configuration writer.
