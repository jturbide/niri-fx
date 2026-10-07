# Shell integration design notes

This page is for contributors building or embedding a shell adapter. See
[Choose your setup](scenarios.md) for installation, the
[project roadmap](../ROADMAP.md) for priorities, and the
[stability and compatibility policy](stability.md) for public-interface commitments.

## Available integrations

Existing adapters cover iNiR/iRiS, DMS and Noctalia. The [Quickshell](quickshell.md)
and [GTK/AGS](gtk.md) pickers add reviewed Apply, profiles and Undo using the same
standalone commands. Their tested versions and workflow scope are recorded in
[Validation](validation.md#workflow-and-compositor-scenarios).

**Waybar works with standalone NiriFX.** Standalone NiriFX already supplies the
animation configuration. An optional Studio launcher button is a small convenience,
not a prerequisite or a new effects backend. The same applies to simple bars/widgets.

## Adapter requirements

Reuse the parameter catalog and CLI. Preserve existing resize behavior unless the
profile selects resize, separate preview and registration from activation, and
preserve unrelated settings. Verify exact Restore against temporary configurations.
Include a scenario guide and document the supported shell versions and tested
workflows. Shader generation remains in NiriFX so each picker exports the same
effects and settings.

An adapter needs a maintained Niri-compatible target and a supported UI extension
point. Compositor shader support determines which effects can run; shell integration
provides the controls for choosing and applying them.

Keep adapter data and launchers outside the shell's source checkout. Do not patch
tracked settings pages or require stashing NiriFX edits before a shell update.
An embedded entry needs a supported external extension point or an accepted
upstream hook. Include an update regression that preserves user settings and
leaves the shell checkout unchanged. See [Desktop updates](desktop-updates.md).

## Further integration work

Focus on embedding the existing pickers in maintained Niri-compatible shells.
Each integration needs a supported UI extension point and a reproducible
Apply/Restore workflow before advertising support.

Primary references: [Quickshell](https://quickshell.org/),
[AGS](https://aylur.github.io/ags/), [Astal](https://aylur.github.io/astal/),
[Waybar](https://github.com/Alexays/Waybar).
