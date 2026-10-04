# NiriFX documentation

Start with [Getting started](getting-started.md), or [choose your setup](scenarios.md)
for instructions tailored to your desktop. NiriFX works standalone on Niri;
iNiR/iRiS, DMS and Noctalia integrations are optional.

## Install and use

| I want to… | Guide |
| --- | --- |
| Preview effects and install NiriFX | [Getting started](getting-started.md) |
| Use plain Niri or Waybar | [Standalone setup](standalone.md) |
| Use iNiR or iRiS | [iNiR/iRiS setup](getting-started.md#inir-and-iris) |
| Use DankMaterialShell | [DMS launcher adapter](dms.md) |
| Use or embed the Quickshell picker | [Quickshell picker](quickshell.md) |
| Pick presets from one terminal command | [Terminal guide](terminal.md) |
| Use a GTK picker or embed it in AGS 3 | [GTK and AGS guide](gtk.md) |
| Use Noctalia's animation picker | [Noctalia preset pack](noctalia.md) |
| Use another shell or a generated config | [Choose your setup](scenarios.md), [custom shells](custom-shells.md) |
| Check requirements and supported features | [Compatibility](compatibility.md) |
| Diagnose setup or undo a change | [Setup and restore](setup.md), [troubleshooting](troubleshooting.md) |
| Update an installation | [Updating NiriFX](upgrading.md) |
| Choose a version or understand release downloads | [Releases](releases.md) |

## Choose and customize effects

| I want to… | Guide |
| --- | --- |
| Choose a first look | [Nine starter presets](https://jturbide.github.io/niri-fx/gallery/?collection=starter), [open/close pairings](https://jturbide.github.io/niri-fx/gallery/?collection=profiles) |
| Find exact preset IDs, timings and settings JSON | [Preset reference](presets.md) |
| Find a look or compare settings | [Click-to-play gallery](https://jturbide.github.io/niri-fx/gallery/), [scenario guide](showcases.md), [full catalog](catalog.md) |
| Try effects without installation or share settings | [Web Studio](web-studio.md) |
| Learn Studio's controls | [Studio and controls](usage.md) |
| Adjust waves, randomness, colors and motion | [Effect controls](effect-controls.md) |
| Enable a resize effect | [Resize styles and profiles](resize.md) |
| Combine different opening and closing effects | [Profiles](profiles.md) |
| Import a ready-made custom style | [Examples](../examples/README.md) |
| Browse presets by look | [Preset collections](collections.md) |
| Try experimental movement and swaps | [Experimental build](../experimental/README.md) |
| Understand performance and known limits | [GPU measurements](performance.md), [testing](validation.md) |
| See planned improvements | [Roadmap](../ROADMAP.md), [integration plans](roadmap.md) |

Opening and closing use stock Niri shaders. Resize is opt-in for Fragments, Elastic, Slices and Distortion. Native
movement requires the experimental compositor patch. Studio previews the actual
movement shader on a synthetic path; its older Move/Swap sketches are labelled
concepts. Previewing does not activate effects.

## Contribute and learn more

- [Contributing](../CONTRIBUTING.md) and [community](community/README.md)
- [Architecture](architecture.md), [adding effects](adding-effects.md) and [engineering plan](next-phases.md)
- [iNiR integration contract](integration.md) and [movement design](movement.md)
- [Testing details](validation.md) and [recording the gallery](gifs/README.md)
- [Release process](releasing.md), [changelog](../CHANGELOG.md) and [security policy](../SECURITY.md)
- [Brand assets](branding.md), [related projects](related-projects.md) and [license notices](../THIRD_PARTY.md)

[Desktop motion packs](desktop-motion.md) coordinate stock workspace, camera and overview springs.

[Fragment shapes](fragment-shapes.md) covers joined layouts, emerging silhouettes and ready-made looks.
