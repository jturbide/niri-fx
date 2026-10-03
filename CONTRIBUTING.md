# Contributing

Small, focused contributions are welcome. For a larger feature or compositor
backend, open an issue describing the intended behavior before implementing it.
Check the [compatibility roadmap](docs/compatibility.md) and
[movement limits](experimental/README.md) first.

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
| `niri_fx/effects.py`, `shaders/` | Validated parameters, presets and shader generation |
| `niri_fx/setup.py` | Setup plans, snapshots, conflict-aware restore and diagnostics |
| `niri_fx/integration.py` | iNiR helper contract and safe registry updates |
| `niri_fx/studio.py`, `preview.html`, `studio.js`, `studio.css`, `motion-preview.js` | Local editor, actual shader previews and labelled movement concepts |
| `tests/`, `scripts/validate.py`, `scripts/browser-smoke.mjs` | Behavioral, compilation and browser checks |
| `experimental/`, `scripts/build-niri-movement.py`, `scripts/nested-demo.py` | Pinned compositor patch and isolated native experiment |
| `docs/`, `CHANGELOG.md` | User guidance, evidence and release history |

## Code conventions and checks

- Use `niri_fx` and `niri-fx` exclusively. The project is in active development;
  obsolete APIs and formats are removed instead of maintained as compatibility
  layers. Document breaking changes under Unreleased. Preset documents use schema 3.
- Python targets 3.10+, uses four spaces and Ruff lint/format (100 columns).
  Run `.venv/bin/ruff check --fix .` and `.venv/bin/ruff format .` before review.
- JavaScript, CSS, HTML and workflow YAML use Prettier; JavaScript also uses ESLint.
  Run `npm run format`. The lockfile pins development tools; npm is not a runtime
  dependency. Studio sources are readable files assembled into one offline HTML page.
- Put behavior in small shared functions; keep family-specific rendering in GLSL
  templates and capabilities in the family catalog. Check rendered behavior when
  changing shaders. The compact and varied renderers have different costs.
- Add focused unit tests for validation/math/contracts and temporary-file integration
  tests for ownership, restore and migrations. Browser E2E checks render actual
  pixels, compare Python exports and save all families through the real Studio CLI.
  Avoid duplicating these with a separate framework just to increase test counts.
- GitHub Actions runs lint, Python 3.10/3.14 tests, GLSL compilation, docs/media
  checks, wheel installation and browser E2E. Stock Niri parsing and patched native
  smoke checks also run locally where the compositor is available. CI is not GPU
  performance certification or a desktop deployment pipeline.

Tool configurations: [Ruff](https://docs.astral.sh/ruff/configuration/),
[ESLint](https://eslint.org/docs/latest/use/configure/configuration-files),
[Prettier](https://prettier.io/docs/configuration).

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
