# NiriFX documentation

Start with [Getting started](getting-started.md), or [choose your setup](scenarios.md)
for instructions tailored to your desktop. NiriFX works standalone on Niri;
iNiR/iRiS, DMS and Noctalia integrations are optional.

These guides cover version 0.20. Later changes on `main` are recorded under
[Unreleased](../CHANGELOG.md). Use [Releases](releases.md) to choose a versioned
package and its matching documentation.

## Install and use

| I want to… | Guide |
| --- | --- |
| Preview effects and install NiriFX | [Getting started](getting-started.md) |
| Use plain Niri or Waybar | [Standalone setup](standalone.md) |
| Use iNiR or iRiS | [iNiR/iRiS setup](getting-started.md#inir-and-iris) |
| Use DankMaterialShell | [DMS launcher adapter](dms.md) |
| Use or embed the Quickshell picker | [Quickshell picker](quickshell.md) |
| Pick presets from one terminal command | [Terminal guide](terminal.md) |
| Choose or customize effects with an AI agent | [Agent workflow and bundled skill](agents.md) |
| Use a GTK picker or embed it in AGS 3 | [GTK and AGS guide](gtk.md) |
| Use Noctalia's animation picker | [Noctalia preset pack](noctalia.md) |
| Use another shell or a generated config | [Choose your setup](scenarios.md), [custom shells](custom-shells.md) |
| Check requirements and supported features | [Compatibility](compatibility.md) |
| Diagnose setup or undo a change | [Setup and restore](setup.md), [troubleshooting](troubleshooting.md) |
| Update an installation | [Updating NiriFX](upgrading.md) |
| Keep CLI, Studio and the login launcher together | [Managed tool updates](tool-updates.md) |
| Update Niri or a desktop shell | [Desktop updates and native build lifecycle](desktop-updates.md) |
| Keep normal desktop settings and effects shared between sessions | [Shared settings](shared-settings.md) |
| Install the complete NiriFX compositor session | [Session setup and rollback](native-session.md) |
| Choose a version or understand release downloads | [Releases](releases.md) |

## Choose and customize effects

| I want to… | Guide |
| --- | --- |
| Choose a first look | [Nine starter presets](https://jturbide.github.io/niri-fx/gallery/?collection=starter), [open/close pairings](https://jturbide.github.io/niri-fx/gallery/?collection=profiles) |
| Find exact preset IDs, timings and settings JSON | [Preset reference](presets.md) |
| Find a look or compare settings | [Click-to-play gallery](https://jturbide.github.io/niri-fx/gallery/), [scenario guide](showcases.md), [full catalog](catalog.md) |
| Try effects without installation or share settings | [Web Studio](web-studio.md) |
| Learn Studio's controls | [Studio and controls](usage.md) |
| Choose one look or mix styles for each action | [Library and combo builder](library.md) |
| Adjust waves, randomness, colors and motion | [Effect controls](effect-controls.md) |
| Choose coordinated actions with optional companions | [Action sets](action-sets.md) |
| Coordinate workspace, camera and overview timing | [Desktop motion packs](desktop-motion.md) |
| Choose or mix fragment shapes | [Fragment shapes](fragment-shapes.md) |
| Enable a resize effect | [Resize styles and profiles](resize.md) |
| Combine different opening and closing effects | [Profiles](profiles.md) |
| Import a ready-made custom style | [Examples](../examples/README.md) |
| Browse presets by look | [Preset collections](collections.md) |
| Use movement and swaps | [NiriFX session](native-session.md) |
| Make a window bend while dragging | [Pointer wobble](pointer-wobble.md) |
| Make pieces spread on press and follow a drag with individual delays | [Continuous fragments](fragment-drag.md) |
| Check support, performance and known limits | [Compatibility](compatibility.md), [performance measurements](performance.md), [validation and known limits](validation.md) |
| See planned improvements and the path to 1.0 | [Project roadmap](../ROADMAP.md), [stability and compatibility policy](stability.md) |

Opening and closing use stock Niri shaders. Fragments, Elastic, Slices and
Distortion also provide resize effects. Movement, pointer wobble and continuous
fragments are included in the NiriFX session. Studio previews the actual
movement shader on a synthetic path; its older Move/Swap sketches are labelled
concepts. Previewing does not activate effects.

## Contribute and learn more

The references below explain implementation, reproducible checks and project
maintenance. Start with [Contributing](../CONTRIBUTING.md) when proposing a change.

| I want to… | Reference |
| --- | --- |
| Understand implementation boundaries | [Architecture](architecture.md), [development design notes](next-phases.md) |
| Add an effect or control | [Adding effects](adding-effects.md) |
| Build or embed a shell adapter | [Shell integration design](roadmap.md), [iNiR integration contract](integration.md) |
| Work on compositor behavior | [Movement design](movement.md), [developer builds](../experimental/README.md) |
| Check upstream builds and prepare native packages | [Native compatibility and distribution gates](native-compatibility.md) |
| Understand future compatibility commitments | [Stability and compatibility policy](stability.md) |
| Reproduce results or contribute hardware evidence | [Validation record](validation.md), [performance methodology](performance.md), [recording guide](gifs/README.md) |
| Maintain a release | [Maintainer release process](releasing.md), [changelog](../CHANGELOG.md) |
| Report a vulnerability | [Security policy](../SECURITY.md) |
| Discuss the project or reuse its assets | [Community](community/README.md), [brand assets](branding.md), [related projects](related-projects.md), [license notices](../THIRD_PARTY.md) |
