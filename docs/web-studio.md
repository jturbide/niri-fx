# Try, customize and share online

Open [Web Studio](https://jturbide.github.io/niri-fx/studio/) in a WebGL-capable
browser. No Niri installation is needed to preview effects. The hosted editor
uses the same portable shader templates and controls as local Studio, with synthetic
window content. It cannot change desktop settings or capture your windows.

## Start from a showcase

Opening [Web Studio](https://jturbide.github.io/niri-fx/studio/) directly starts in
Library. Choose Open, Close, Resize, Move or Swap, then click a style to preview
and assign it. **Combos** offers complete looks: Fragment Flow, Soft Landing,
Ribbon Current, Playful Motion and Geometric Flow. **Customize your combo** lets
you share a style across selected actions; **Advanced editor** opens detailed
controls. **Save to My profiles** uses
this browser's local storage; **Download JSON** keeps a portable copy. Local Apply
and Restore controls are absent from the hosted page. See [Library](library.md).

Press **Preview combo** to try the selected opening and closing effects as one
sequence, with an intact hold between them. Each action uses its own style and
timing. Selected Resize, Move and Swap effects are included;
an unset optional action is skipped. This works online and in the installed app
without applying settings or enabling an optional action.

Movement previews use a synthetic shader path; Swap shows two sample windows.
Actual Move/Swap effects need a matching NiriFX compositor; Web Studio cannot provide compositor
hooks. Stock desktop springs are described and recorded separately in the
[desktop motion guide](desktop-motion.md).

Library also stores **Pointer wobble** presets and custom strength,
damping and frequency. Online Studio can edit, share and download these settings;
combo playback includes a scripted drag when strength is above zero. **Try pointer
wobble** lets you drag the synthetic window with native spring and shader math.
These previews do not verify compositor support. **Export stock Niri config** omits
NiriFX session nodes. **Export NiriFX session config** includes selected pointer,
Move and Swap settings for the matching native build. Read the
[pointer guide](pointer-wobble.md) before using that configuration.

**Current source, Unreleased:** **Gentle / Tear / Cascade** fragment responses
and their custom controls can be saved to My profiles, downloaded and shared
online. Values travel with the profile, even while Move is Off, preserved or
using an incompatible material. **Timed movement** removes the response.
Stock config exports omit it; native exports need an eligible material and a
compatible NiriFX compositor. The browser previews the movement material, not
continuous gesture behavior. See [portable fragment recipes](profiles.md#portable-fragment-response).

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
4. **Download JSON** keeps editable settings; **Export stock Niri config** exports stock shaders.
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
python3 -m niri_fx studio --custom /path/to/nirifx-preset.json
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
data only, with the same 32 KiB document limit as JSON imports in current source
(16 KiB in 0.20). Malformed links
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
| Local `studio` command | Yes | Standalone, installed iNiR, connected Noctalia or a matching managed NiriFX session |
| Exported `preview` HTML | Yes, without a server | No |

The hosted page is a static GitHub Pages site. It has no analytics or preset
backend. Its footer shows the version and **UI build**, which identifies the
editor and built-in catalog independently of your settings. Compare it with
local Studio when checking whether both use the same UI. Reload the web page
after an update; an exported HTML file needs to be regenerated. This identity
does not describe or verify a running compositor.

For use without hosting, generate the self-contained editor:

```sh
python3 -m niri_fx preview --preset explosion --output /tmp/nirifx-studio.html
```

Open that HTML file in a browser. See [Studio controls](usage.md),
[independent profiles](profiles.md) and [movement limits](movement.md).
