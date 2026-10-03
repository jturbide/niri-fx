# NiriFX identity

**Name:** NiriFX. **Tagline:** Window effects for niri.
**Short description:** Configurable fragment, slice and elastic window animations
for niri, with a visual Studio, CLI and optional shell integrations.

Use `niri-fx` for the repository, executable and application ID, and `niri_fx` for
the Python package. Fragments, Slices and Elastic are effect families. Use the
upstream spellings **niri**, **iNiR**, **iRiS**, **DankMaterialShell (DMS)**,
**Noctalia** and **Quickshell**.

## Assets

- [Application mark](../niri_fx/assets/niri-fx.svg): original mint pixel N with
  violet fragments; suitable for the Studio launcher and small icons.
- [README banner](assets/nirifx-banner.svg): wordmark and the three effect families.

The assets are SVG, use no external fonts or resources, and are covered by this
project's MIT license. Keep the artwork legible against dark backgrounds and
provide an accessible text label when it carries meaning. The glyph depicts
fragments; it is not an upstream project's logo.

## Credits and support claims

| Wording | Appropriate use |
| --- | --- |
| Built with Python, GLSL and WebGL | Actual implementation: generator/server, compositor shaders and browser preview. |
| Built for niri | The compositor target; stock open/close, optional fragment resize. |
| Integrates with iNiR/iRiS | External preset registration and Studio save. |
| Exports presets for Noctalia | Its existing Niri Animations picker consumes the KDL folder. File contract and Noctalia 5.2.1 picker selection/return to base checked in isolation. |
| Works at the niri config layer with DMS | Standalone KDL include. No DMS-native settings plugin or runtime acceptance claim. |
| Quickshell ecosystem | iNiR and DMS use Quickshell. NiriFX itself is Python/WebGL, not a QML shell or Quickshell plugin. |
| Compiz-inspired elastic motion | Timed spring-like warping. Pointer-driven spring physics is not implemented. |

Use plain credit links, not upstream logos or “official partner” badges. Native
move/swap shaders require the separate patched compositor. The project has no
Hyprland, KWin or GNOME backend. See [related projects](related-projects.md) and
[third-party notices](../THIRD_PARTY.md).

## Discovery vocabulary

Package metadata and desktop search include animation, window effects, shaders,
GLSL, WebGL, fragments, pixels, particles, slices, wobble, niri, Wayland, iNiR,
iRiS, Quickshell, DankMaterialShell/DMS and Noctalia. GitHub topics use lowercase,
searchable names. Shell keywords describe integration targets, not dependencies
or endorsements. Keep descriptions readable; do not repeat keyword lists in
unrelated prose or use misspellings as project names.
