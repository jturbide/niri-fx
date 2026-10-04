# Try, customize and share online

Open [Web Studio](https://jturbide.github.io/niri-fx/studio/) in a WebGL-capable
browser. No Niri installation is needed to preview effects. The hosted editor
uses the same shader templates and controls as local Studio, with synthetic
window content. It cannot change desktop settings or capture your windows.

## Start from a showcase

Opening [Web Studio](https://jturbide.github.io/niri-fx/studio/) directly starts in
Library. Choose a recommended look, mix styles per action, or use a shared style.
The first five recommendations are complete combos: Fragment Flow, Soft Landing,
Ribbon Current, Playful Motion and Geometric Flow. Fragments appear first;
single styles and coordinated action sets remain available below them.
**Customize in Studio** opens detailed controls. **Save to My profiles** uses
this browser's local storage; **Export JSON** keeps a portable copy. Local Apply
and Restore controls are absent from the hosted page. See [Library](library.md).

Press **Preview combo** to try the selected opening and closing effects as one
sequence, with an intact hold between them. Each action uses its own style and
timing. Explicitly selected resize or experimental movement effects are included;
an unset optional action is skipped. This works online and in the installed app
without applying settings or enabling an optional action.

Movement previews use a synthetic shader path. Actual move/swap effects need the
verified experimental Niri compositor; Web Studio cannot provide compositor
hooks. Stock desktop springs are described and recorded separately in the
[desktop motion guide](desktop-motion.md).

Library also stores experimental **Pointer drag** presets and custom strength,
damping and frequency. Online Studio can edit, share and download these settings;
combo playback includes a scripted drag when strength is above zero. **Try pointer
drag** lets you drag the synthetic window with native spring and shader math.
These previews do not verify compositor support. **Export stock Niri config** omits
experimental nodes. **Export experimental config** includes selected pointer and
movement settings for the matching native build. Read the
[pointer guide](pointer-wobble.md) before using that configuration.

1. Open the [gallery](https://jturbide.github.io/niri-fx/gallery/) and start with
   nine recommended looks. **Open/close pairings** shows sixteen finished combinations;
   **All examples** opens the full collection. Searching from Start here explores
   the full catalog. Filter by family, scenario or renderer, then press **Play**.
   Only one animation plays at a time.
2. Choose **Try in Studio** to load that example's recorded settings. Comparisons
   offer a separate link and JSON file for each style. Experimental movement and
   concept cards say **Edit open/close style**: Web Studio does not run a compositor.
3. Adjust the controls. Use **Basic** for the main look or **Advanced** for detailed
   tuning. **Pause** and the timeline let you inspect a single frame.
4. **Export JSON** keeps editable settings; **Export stock Niri config** exports stock shaders.
   Neither download activates an effect. The config preserves existing resize
   settings unless the document selects a resize effect, as the labelled resize profiles do.

Workflow recordings demonstrate shell interactions and may not have downloadable
style settings. Their setup guides describe the corresponding integration.

## Use the result locally

For an unchanged built-in look, use its name in the terminal guide or your shell's
picker. You do not need to download JSON or open an editor. The gallery's **Use on
Niri** section links to setup instructions for plain Niri/Waybar, iNiR/iRiS, DMS
and Noctalia.

For customized settings, install NiriFX using [Getting started](getting-started.md). Download a gallery
style's JSON, then use **Copy local command** from that card. Run it from the folder
containing the downloaded file, in the environment where NiriFX is installed.

For a file exported by Studio, run this from the source checkout, using the actual
path to your download:

```sh
python3 -m niri_fx studio --custom /path/to/nirifx-preset.json --target standalone
```

You can also choose **Import preset** inside local Studio. To activate an effect,
follow [standalone setup](standalone.md), [iNiR/iRiS](getting-started.md#inir-and-iris),
[DMS](dms.md) or [Noctalia](noctalia.md). Those guides cover reviewing changes and
restoring the prior configuration.

## Share settings or a gallery view

**Share settings** creates a public Studio link containing the style/profile,
selected action, preview mode, resize direction, random seed and timeline position. It never copies
local save tokens. The link preserves values, not playback, history or favorites.
If clipboard access is unavailable, select and copy the displayed URL.

The document is encoded in the URL fragment and decoded in the browser. There is
no preset-upload service, but anyone who receives the complete link can read its
name and settings. Treat it as shared content. Links accept validated parameter
data only, with the same 16 KiB document limit as JSON imports. Malformed links
show an error without replacing the current settings. Keep a JSON export as your
editable copy; development versions may change the format or defaults.

**Share this view** in the gallery keeps its collection, filters and current example
anchor. Direct links to examples outside the starter selection still reveal the
requested card.
Previews start paused when someone opens the link.

## Hosted, local and offline

| Mode | Preview and JSON/config export | Reviewed desktop Apply |
| --- | --- | --- |
| Web Studio | Yes | No |
| Local `studio` command | Yes | Standalone, installed iNiR or connected Noctalia target |
| Exported `preview` HTML | Yes, without a server | No |

The hosted page is a static GitHub Pages site. It has no analytics or preset
backend. For use without hosting, generate the self-contained editor:

```sh
python3 -m niri_fx preview --preset explosion --output /tmp/nirifx-studio.html
```

Open that HTML file in a browser. See [Studio controls](usage.md),
[independent profiles](profiles.md) and [movement limits](movement.md).
