# Shell integration plans

NiriFX already works with standalone Niri, iNiR/iRiS, DMS and Noctalia.
The next integrations aim to make browsing, applying and restoring styles
convenient in more desktop setups. See the [project roadmap](../ROADMAP.md)
for overall priorities.

The order below reflects current priorities; release dates are not set.

| Priority | Integration | Planned experience |
| --- | --- | --- |
| 1 | Existing integrations | More testing across shell versions, complete desktop sessions, GPUs and display setups. |
| 2 | Reusable custom Quickshell example | A reusable picker with search, custom profiles and reversible apply/undo. |
| 3 | AGS / Astal example | A GTK-based picker with the same search, profile and restore workflow. |
| 4 | Caelestia integration assessment | Explore a picker once a maintained Niri-compatible setup and suitable extension point are established. |
| 5 | ML4W workflow assessment | Start with guidance for a separate Niri session, then assess a settings adapter for an appropriate Niri target. |
| Separate research | Another compositor renderer | Hyprland/KWin/GNOME need their own shader hooks and adapters, not just a shell plugin. Consider user demand and maintenance cost before a backend project. |

**Waybar works with standalone NiriFX.** Standalone NiriFX already supplies the
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
