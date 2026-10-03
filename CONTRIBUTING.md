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
.venv/bin/python -m pip install build
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
python3 -m niri_fragments preview --output /tmp/fragments-review.html
node scripts/browser-smoke.mjs file:///tmp/fragments-review.html
```

Use a fresh output filename. `--save-test` is only for a Studio process explicitly
pointed at a temporary registry. Software WebGL validates rendering behavior and
export parity; it is not a compositor GPU benchmark. See
[validation](docs/validation.md) and [GIF reproduction](docs/gifs/README.md).

## Project layout

| Location | Responsibility |
| --- | --- |
| `niri_fragments/effects.py`, `shaders/` | Validated parameters, presets and shader generation |
| `niri_fragments/setup.py` | Setup plans, snapshots, conflict-aware restore and diagnostics |
| `niri_fragments/integration.py` | iNiR helper contract and safe registry updates |
| `niri_fragments/studio.py`, `preview.html`, `motion-preview.js` | Local editor, actual shader previews and labelled movement concepts |
| `tests/`, `scripts/validate.py`, `scripts/browser-smoke.mjs` | Behavioral, compilation and browser checks |
| `experimental/`, `scripts/build-niri-movement.py`, `scripts/nested-demo.py` | Pinned compositor patch and isolated native experiment |
| `docs/`, `CHANGELOG.md` | User guidance, evidence and release history |

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

Original Fragments contributions use [MIT](LICENSE). Changes derived from Niri
in the movement patch use [GPL-3.0-or-later](experimental/COPYING-NIRI).
Preserve attribution for any imported code; see [third-party notices](THIRD_PARTY.md).
There is no CLA. Follow the [release guide](docs/releasing.md) for maintainer tasks.
