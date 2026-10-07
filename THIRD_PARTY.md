# Licensing and third-party notices

## Original NiriFX work

The original Python application, GLSL effects, browser editor, scripts,
documentation and synthetic demonstration assets are copyright 2026 Julien
Turbide and licensed under [MIT](LICENSE), except for the Niri-derived components
and separately licensed packaging sources below.
No community shader collection is vendored. Related projects are credited as
references in [the research notes](docs/related-projects.md).

## Experimental Niri patches

`experimental/niri-movement.patch` and its optional
`experimental/niri-pointer-wobble.patch` and `experimental/niri-fragment-drag.patch`
extensions contain modifications and context derived
from [Niri](https://github.com/niri-wm/niri) at commit
[`8ed0da44d974c32c6877d2f4630c314da0717ecb`](https://github.com/niri-wm/niri/tree/8ed0da44d974c32c6877d2f4630c314da0717ecb).
These patches are **GPL-3.0-or-later**, matching the pinned upstream project's license.
The full license text is included in [experimental/COPYING-NIRI](experimental/COPYING-NIRI).
Upstream copyright notices remain in the source fetched by the build helper.
The patches add an optional movement shader hook, pointer-driven deformation, continuous fragments,
rendering integration and associated configuration/testing changes; see
[the experiment](experimental/README.md).

The browser spring and deformation adapter in `niri_fx/pointer-preview.js` and
continuous fragment model and mesh in `niri_fx/fragment-preview.js` are derived
from their corresponding Niri patches and also use **GPL-3.0-or-later**. Their headers link
to the corresponding source and license. Studio includes these components in its
offline HTML and hosted page; the installed package includes the same readable
JavaScript and license text.

The source distribution includes the patches and both license texts, so project
distribution metadata lists `MIT AND GPL-3.0-or-later`. The installed Python
package does not contain or install a patched compositor. Its original Python
code remains MIT licensed; the embedded motion previews have the license described
above. This combined metadata does not relicense the MIT files.

The build helper fetches Niri and Cargo dependencies separately into ignored
build directories. Those projects retain their own licenses. No Niri binary,
Rust toolchain, browser or third-party Python dependency is distributed here.
If distributing a modified Niri binary separately, review its upstream notices
and source-distribution requirements for that artifact.

## Arch packaging sources

The recipes, desktop entries and package instructions in
`packaging/arch/niri-fx/` and `packaging/arch/niri-fx-git/` use **0BSD**. Each
directory includes its packaging license and file-level scope in `REUSE.toml`.
This applies to those packaging sources; the application and Niri-derived
components retain the licenses described above.

## External integrations and tooling

iNiR/iRiS and DankMaterialShell are separate projects; their code is not vendored.
Integration references do not imply affiliation or endorsement. Chromium,
FFmpeg, Alacritty and capture tools used for validation/recording are separately
installed tools. Demo recordings show synthetic content created for this project.

## Visual references

[Burn My Windows](https://github.com/Schneegans/Burn-My-Windows) by Simon Schneegans
and contributors inspired the requested pixel wipe, disintegration and wisp
behaviors. NiriFX implements its own GLSL for Niri; no Burn My Windows shader
source, textures or preview recordings are included.
