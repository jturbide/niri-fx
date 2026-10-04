# Shell integration design notes

NiriFX already works with standalone Niri, iNiR/iRiS, DMS and Noctalia.
The next integrations aim to make browsing, applying and restoring styles
convenient in more desktop setups. See the [project roadmap](../ROADMAP.md)
for priorities. This page describes the integration contract.

Existing adapters cover iNiR/iRiS, DMS and Noctalia. The [Quickshell](quickshell.md)
and [GTK/AGS](gtk.md) pickers add reviewed Apply, profiles and Undo using the same
standalone API. Full-shell embedding and Caelestia/ML4W assessments remain next steps.
An adapter needs a maintained Niri-compatible target and a stable UI extension
point; installing a different shell cannot add compositor shader hooks.

**Waybar works with standalone NiriFX.** Standalone NiriFX already supplies the
animation configuration. An optional Studio launcher button is a small convenience,
not a prerequisite or a new effects backend. The same applies to simple bars/widgets.

For every future adapter: reuse the parameter catalog and CLI, preserve existing resize behavior
unless the profile selects resize, separate preview/registration from activation, preserve unrelated settings, and
prove exact restore against temporary configs. Include a scenario guide and record
the actual validation scope. Do not add a second shader renderer inside a shell UI.

Primary references: [Quickshell](https://quickshell.org/),
[AGS](https://aylur.github.io/ags/), [Astal](https://aylur.github.io/astal/),
[Caelestia's components](https://github.com/caelestia-dots/shell#components),
[ML4W](https://github.com/mylinuxforwork/dotfiles), [Waybar](https://github.com/Alexays/Waybar).
