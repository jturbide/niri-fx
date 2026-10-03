# Adding or changing an effect

Start with the existing family when the behavior fits its renderer. A preset is
just named parameter data; a new family is warranted when sampling, capabilities
or control semantics differ. See [architecture](architecture.md) before editing.

## Define the contract first

Record the intended appearance, supported actions, exact endpoints, coordinate
units, transparency behavior and worst-case lookup cost. A stock open/close shader
does not imply resize or movement support. New built-ins keep resize disabled.

Add parameters through `parameter()` in [model.py](../niri_fx/model.py). Supply a
label, range/choices, family applicability, editor group and optional GLSL token.
Use `glsl_type="int"` only when the GLSL expression requires integer syntax;
`integer=True` separately constrains user values. Avoid adding independent CLI
or browser validation lists.

For a new family, add its capability entry and its GLSL file with the same name.
[effects.py](../niri_fx/effects.py) loads family templates from that catalog;
Fragments retains its explicit classic/gravity/varied alternatives. Only add
special renderer selection when the mathematics actually require it.

## Implement and explain the math

Use the [shader contract](architecture.md#shader-contract). Share helpers only
when their semantics match: compact and varied fragments intentionally have
different neighborhoods and costs. Describe bounds and inverse transforms near
the code. Do not claim a physical simulation for an artistic field.

Parameter tokens use `@NAME@`; shared snippets expand before parameters. Separate
action entry files are useful when open/close and experimental movement share a
body. Unsupported action requests must fail rather than silently emit another
family's shader. Keep intermediate deformation separate from exact endpoints.

Add the built-in to [presets.py](../niri_fx/presets.py). Studio options and CLI
choices follow the catalog. Inspect applicable controls and any mode-specific
control disabling in `labels()`; metadata cannot express every dependency yet.
Studio's synthetic window must make both the midpoint and reconstruction legible.

## Validate the behavior, then record it

Run focused tests first, then the relevant gates from [Contributing](../CONTRIBUTING.md):

```sh
python3 -m unittest discover -s tests
npm test
python3 scripts/validate.py --require-glsl --require-niri
npm run test:browser
python3 scripts/studio-e2e.py
```

Extend shared document cases for new validation rules. Add behavioral checks for
new controls: visible change, valid extrema, intact/transparent endpoints and
source-alpha preservation. Keep Python/browser shader parity. Test installed
package resources as well as source-checkout imports. For motion-field changes,
exercise stock/nested Niri and describe exactly which backend was observed.

Add importable JSON and a matching preview command in [examples](../examples/README.md).
Create a preset loop and, when useful, a comparison that isolates one control:

```sh
node scripts/render-readme-gifs.mjs --only=preset-NAME
python3 scripts/check-docs.py
```

`NAME` is the new catalog ID. The recorder also accepts comparison names from
[showcases.json](gifs/showcases.json). Generated metadata must match the current
parameters. Use synthetic content only. A code move or comment change that leaves
rendering unchanged does not require replacing all existing GIFs.

## Finish the change

Update Unreleased, control documentation, examples and the relevant showcase.
Keep Fragments first in the README. Document performance as measured shader or
compositor cost, with hardware and method; GIFs and software WebGL are appearance
checks. Add a release note for changed defaults or document formats. Do not enable
resize, install a compositor patch or activate a user's new preset as a side effect
of registering the catalog.
