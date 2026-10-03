# Related projects

Research checked on 2026-10-02. This is a comparison of the inspected source,
not a claim that no equivalent effect exists anywhere.

| Project | Existing capability | Relationship to this project |
| --- | --- | --- |
| [liixini/shaders](https://github.com/liixini/shaders) | `randomsquares`, `pixelfade-wave`, `voronoi-shatter`, and many other transitions | The inspected square/shard shaders reveal or fade cells; they do not translate textured square fragments. |
| [Xansidev/nirimation](https://github.com/Xansidev/nirimation) | Pixelation, an `explode` shader, and other effects | The inspected explosion is fire/smoke/debris with a simple opening fade, rather than reversible textured block assembly. |
| [jgarza9788/niri-animation-collection](https://github.com/jgarza9788/niri-animation-collection) | A larger collection including pixelation and pixel sorting | Useful examples and alternatives. |
| [pnbarbeito/niri-animation-rotate](https://github.com/pnbarbeito/niri-animation-rotate) | Rotates community effects on compositor events | An existing manager; a rotation daemon is unnecessary for a fixed external iNiR preset pack. |
| [snowarch/iNiR](https://github.com/snowarch/iNiR) | External user animation presets and shared settings services | Existing integration point, including iRiS's window movement gallery. |

The GLSL and adapter in this repository are original. No shader collection is
vendored. If an existing effect is imported later, retain its specific license
and attribution and document any changes.

The separate Niri-derived movement patch is GPL-3.0-or-later; see
[third-party notices](../THIRD_PARTY.md) for its source and license scope.

Official references:

- [Niri animations](https://niri-wm.github.io/niri/Configuration:-Animations.html)
- [Opening shader interface](https://niri-wm.github.io/niri/examples/open_custom_shader.frag)
- [Closing shader interface](https://niri-wm.github.io/niri/examples/close_custom_shader.frag)
- [Niri includes and merging](https://niri-wm.github.io/niri/Configuration:-Include.html)
