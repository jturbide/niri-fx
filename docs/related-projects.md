# Related projects and foundations

Research refreshed on **2026-10-02**. These projects provide useful alternatives,
interfaces or inspiration. Inclusion is a reference, not an endorsement or a
claim that NiriFX originated every visual idea.

## Foundation and shell ecosystem

| Project | Relationship |
| --- | --- |
| [niri](https://github.com/niri-wm/niri) | The Wayland compositor whose animation shader interfaces render NiriFX effects. |
| [iNiR / iRiS](https://github.com/snowarch/iNiR) | Desktop shell and settings interface; NiriFX uses its external animation-preset registry. |
| [Quickshell](https://quickshell.org/) | QtQuick toolkit used by shells including iNiR and DMS. NiriFX's own Studio uses WebGL. |
| [DankMaterialShell](https://github.com/AvengeMedia/DankMaterialShell) | Quickshell/Go shell. NiriFX exports can be included in niri config; an optional launcher adapter provides preset selection and undo. |
| [Noctalia](https://noctalia.dev/) and [Niri Animations](https://github.com/noctalia-dev/community-plugins/tree/main/niri-animations) | The existing picker reads KDL preset folders. NiriFX exports one; current Noctalia uses a Luau plugin API. |
| [awesome-niri](https://github.com/niri-wm/awesome-niri) | Curated ecosystem directory with a Custom Shaders category; a suitable discovery venue. |

## Similar effects and tools

| Project | What to explore |
| --- | --- |
| [liixini/shaders](https://github.com/liixini/shaders) | Experimental GLSL transitions for niri. |
| [Nirimation](https://github.com/XansiVA/nirimation) | Shareable niri animation configurations and shader showcases. |
| [niri-animation-collection](https://github.com/jgarza9788/niri-animation-collection) | Animation presets, a showcase and a documented template/GIF contribution workflow. |
| [niri-animation-rotate](https://github.com/pnbarbeito/niri-animation-rotate) | Rotates KDL animations through compositor events or manual actions. A complementary manager, not a NiriFX dependency. |
| [Burn-My-Windows](https://github.com/Schneegans/Burn-My-Windows) | Configurable effects for GNOME Shell and KWin, including pixel and disintegration styles. Visual reference for NiriFX Pixels and Wisps; no shader code or preview assets are imported. |
| [Compiz plugins](https://github.com/compiz-reloaded/compiz-plugins-main) | The classic desktop-effects tradition behind the request for springy windows. NiriFX Elastic is a timed shader warp, not the original interactive physics. |

NiriFX combines parameterized GLSL with an offline visual editor, CLI, explicit
family capabilities and optional shell adapters. That is its current scope;
these references are not an exhaustive feature comparison or a uniqueness claim.

The shader collection is original and does not vendor those collections. Imported
code would require license/attribution review. The separate Niri-derived movement
patch is GPL-3.0-or-later; see [third-party notices](../THIRD_PARTY.md).

Official interfaces: [niri animations](https://niri-wm.github.io/niri/Configuration:-Animations.html),
[opening shader](https://niri-wm.github.io/niri/examples/open_custom_shader.frag),
[closing shader](https://niri-wm.github.io/niri/examples/close_custom_shader.frag),
[include semantics](https://niri-wm.github.io/niri/Configuration:-Include.html).

See [the community contribution plan](community/README.md) for suitable listing
and showcase proposals, and [branding](branding.md) for accurate credit wording.
