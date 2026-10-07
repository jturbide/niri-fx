# Name, description and brand assets

**Name:** NiriFX

**Tagline:** Window effects for niri.

Use this short description in listings, articles or videos:

> Customizable window animations for niri, with a visual editor, CLI and optional
> shell integrations. Explore fragments, slices, wobble, pixels, wisps and more.

The repository and command are `niri-fx`; the Python package is `niri_fx`.
Use the upstream spellings **niri**, **iNiR**, **iRiS**, **DankMaterialShell (DMS)**,
**Noctalia** and **Quickshell**.

## Assets

- [Application icon](../niri_fx/assets/niri-fx.svg): mint and violet pixel artwork.
- [README banner](assets/nirifx-banner.svg): NiriFX wordmark and effect artwork.

Both are SVGs with no external fonts or resources and are covered by the
project's [MIT license](../LICENSE). Keep the artwork legible and provide an
accessible text label when it carries meaning.

## Describing features and integrations

NiriFX is built with **Python, GLSL and WebGL** for **niri**. Opening, closing and resize
shaders work on stock Niri. Native movement/swaps and pointer deformation require
the separate experimental compositor build.

| Integration | What it provides |
| --- | --- |
| iNiR/iRiS | Preset registration and saving from Studio to the shell's style picker |
| DankMaterialShell | An optional launcher adapter for preset search, Studio and Undo |
| Noctalia | KDL preset files for its existing Niri Animations picker |
| Other bars or shells on Niri | Standalone setup and optional CLI launchers |

Studio is a web editor that can open in a dedicated app-style window. Quickshell
is optional; desktop effects use Niri's rendering hooks.
See [compatibility](compatibility.md) for tested versions and limitations.

NiriFX is independent of these projects. Link to upstream projects when giving
credit; do not present their names or logos as endorsements. See
[related projects](related-projects.md) and [third-party notices](../THIRD_PARTY.md)
for references and attribution.
