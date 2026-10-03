# Contributing

Small, focused contributions are welcome. For a larger feature or compositor
backend, open an issue describing the intended behavior before implementing it.
Check the [project roadmap](ROADMAP.md), [compatibility](docs/compatibility.md) and
[movement limits](experimental/README.md) first. Read the [architecture](docs/architecture.md),
[effect contribution guide](docs/adding-effects.md) and [next phases](docs/next-phases.md)
for implementation boundaries and acceptance criteria.

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
configuration checks. CI requires GLSL validation; local `--require-niri` also
checks stock Niri config parsing. Tests use temporary files and a loopback server,
so local socket access must be available. Do not point tests at your real registry.

For editor/rendering changes, use Node 22+ and Chromium/Chrome (or `CHROME_BIN`):

```sh
python3 -m niri_fx preview --output /tmp/fragments-review.html
node scripts/browser-smoke.mjs file:///tmp/fragments-review.html
# Full CLI/browser/save flow, using temporary config only:
npm run test:browser
python3 scripts/studio-e2e.py
```

Use a fresh output filename. `--save-test` is only for a Studio process explicitly
pointed at a temporary registry. Software WebGL validates rendering behavior and
export parity; it is not a compositor GPU benchmark. See
[validation](docs/validation.md) and [GIF reproduction](docs/gifs/README.md).

## Project layout

| Location | Responsibility |
| --- | --- |
| `niri_fx/` | Canonical implementation, module entry point and packaged assets |
| `niri_fx/model.py`, `parameters.py`, `presets.py` | Shared parameter catalog, validation and built-in styles |
| `niri_fx/documents.py`, `profiles.py` | Shell-independent document validation, serialization and action choices |
| `niri_fx/effects.py`, `shaders/` | Shader assembly and stock/experimental export boundaries |
| `niri_fx/setup.py`, `pack.py`, `storage.py` | Setup plans, preset folders, shared atomic writes, snapshots and conflict-aware restore |
| `niri_fx/integration.py` | iNiR helper contract and safe registry updates |
| `niri_fx/picker.py`, `qml/`, `gtk/`, `integrations/ags/` | Optional desktop pickers, reusable views/controllers and AGS example; writes stay in the CLI |
| `niri_fx/terminal.py` | Recommended preset presentation and a line-oriented guide using the shared setup/restore backend |
| `niri_fx/preview.py`, `effect-core.js` | Offline assembly and DOM-free browser validation/shader generation |
| `niri_fx/studio.py`, `preview.html`, `studio.js`, `studio.css`, `motion-preview.js` | HTTP/app lifetime, editor state, actual shader previews and labelled movement concepts |
| `tests/`, `tests/fixtures/`, `scripts/validate.py`, `scripts/browser-smoke.mjs` | Shared document cases, domain/storage tests, shader parity and real browser checks |
| `scripts/lib/browser.mjs` | Chromium startup, bounded protocol calls, readiness and cleanup shared by all browser tools |
| `experimental/`, `scripts/build-niri-movement.py`, `scripts/nested-demo.py` | Pinned compositor patch and isolated native experiment |
| `docs/`, `CHANGELOG.md` | User guidance, evidence and release history |

## Code conventions and checks

- Use `niri_fx` and `niri-fx` exclusively. The project is in active development;
  obsolete APIs and formats are removed instead of maintained as compatibility
  layers. Document breaking changes under Unreleased. Single-effect documents use schema 3; independent profiles use kind `profile`, schema 1.
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
  Python and compares all supported stock action shaders. `npm run test:browser`
  tests real Chromium launch/error/timeout/cleanup and gallery filtering/playback before the full editor E2E.
  Avoid duplicating these with a separate framework just to increase test counts.
- GitHub Actions classifies changes conservatively: an explicit docs/media allowlist skips unit, GLSL, package and browser work. Lint and docs checks still run. Unknown paths, missing history, manual runs and failed selection require full checks or fail the required jobs. Required job names remain unchanged.
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
Keep limitations explicit, especially stock Niri versus experimental movement.

Keep personal configurations, local workspace paths, session URLs, raw audit
reports, planning conversations and outreach drafts out of commits and PR bodies.
Use sample content in media. Inspect representative frames of each recording,
including menus and status messages; text inside images is not covered by a
source secret scan. Keep local investigations under ignored `artifacts/`.

After changing recordings or gallery metadata, run `python3 scripts/build-gallery.py` (Pillow required), then `python3 scripts/build-gallery.py --check`. GitHub Pages publishes the checked static gallery after changes reach main. Posters load first; playback is explicit and limited to one GIF.

Before submitting, inspect `git diff --cached`, check new files for private data
and run the documentation check. A clean scanner result complements manual review;
it does not replace it. Examples should use generic paths and names.

## Review expectations

- Explain the problem, resulting behavior, and checks run in the pull request.
- Add an **Unreleased** changelog entry for user-visible behavior, defaults,
  compatibility, packaging or substantial documentation changes.
- Keep resize fragments opt-in. Keep movement shaders out of stock Niri exports.
- Preserve unrelated presets and timings, backups, symlinks and explicit custom
  choices. Registration and saving must remain separate from activation.
- Keep Python and browser parameter validation and shader generation consistent.
- Test behavior that can regress; avoid tests that only repeat implementation.
- Use synthetic content in captures. Do not commit user configs, session tokens,
  raw recordings, binaries, toolchains or the `artifacts/` directory.

Changes to the Niri patch need the pinned build/tests and a nested-session check.
Do not replace a contributor's login compositor to run tests. Explain any new
capture, damage, rendering or interruption behavior and its validation limits.

Original NiriFX contributions use [MIT](LICENSE). Changes derived from Niri
in the movement patch use [GPL-3.0-or-later](experimental/COPYING-NIRI).
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
