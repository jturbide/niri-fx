# Shell integration design notes

NiriFX already works with standalone Niri, iNiR/iRiS, DMS and Noctalia.
The next integrations aim to make browsing, applying and restoring styles
convenient in more desktop setups. See the [project roadmap](../ROADMAP.md)
for priorities. This page describes the integration contract.

Existing adapters cover iNiR/iRiS, DMS and Noctalia. Future examples should build
on the same standalone apply/restore API. The roadmap prioritizes a custom
Quickshell picker, then AGS/Astal, followed by Caelestia and ML4W assessments.
An adapter needs a maintained Niri-compatible target and a stable UI extension
point; installing a different shell cannot add compositor shader hooks.

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
