# Integration priorities

The root [ROADMAP.md](../ROADMAP.md) tracks overall progress and milestones.
This page supplies the integration-specific order and rationale.

Reviewed on **2026-10-03**. The current scope is standalone Niri plus iNiR/iRiS,
DMS and Noctalia. This is a priority order, not a release-date promise.
The [development phases](next-phases.md) turn these priorities into scoped deliverables
and acceptance gates; [architecture](architecture.md) defines the implementation boundaries.

| Priority | Work | Why / acceptance gate |
| --- | --- | --- |
| 1 | Polish and validate existing paths | Maintain the versioned picker workflow checks; broaden acceptance beyond isolated component hosts and test more GPUs, display scales and interrupted effects. |
| 2 | Reusable custom Quickshell example | A small picker using the shared CLI, with search, custom profiles and reversible apply/undo. Test it in an isolated Niri session before calling it supported. |
| 3 | AGS / Astal example | Reuse the same CLI contract in a GTK-based shell; useful beyond Quickshell. Choose a maintained API/version and verify a real shell workflow first. |
| 4 | Caelestia integration assessment | Its current documented compositor is Hyprland. First establish a maintained Niri-capable setup and an appropriate extension point; then consider a picker. Do not label a Hyprland configuration as NiriFX-compatible. |
| 5 | ML4W workflow assessment | Its documented focus is Hyprland. Start with coexistence/documentation for separate Niri sessions. A native settings adapter needs a supported Niri target and clear config ownership. |
| Separate research | Another compositor renderer | Hyprland/KWin/GNOME need their own shader hooks and adapters, not just a shell plugin. Consider user demand and maintenance cost before a backend project. |

**Waybar needs no compatibility project.** Standalone NiriFX already supplies the
animation configuration. An optional Studio launcher button is a small convenience,
not a prerequisite or a new effects backend. The same applies to simple bars/widgets.

For every future adapter: reuse the parameter catalog and CLI, keep resize opt-in,
separate preview/registration from activation, preserve unrelated settings, and
prove exact restore against temporary configs. Include a scenario guide and record
the actual validation scope. Do not add a second shader renderer inside a shell UI.

Primary references: [Quickshell](https://quickshell.org/),
[AGS](https://aylur.github.io/ags/), [Astal](https://aylur.github.io/astal/),
[Caelestia's components](https://github.com/caelestia-dots/shell#components),
[ML4W](https://github.com/mylinuxforwork/dotfiles), [Waybar](https://github.com/Alexays/Waybar).
