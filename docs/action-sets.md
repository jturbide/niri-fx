# Coordinated action sets

Choose a complete look with **Fragments Motion**, **Ribbons Motion** or
**Elastic Motion**. Each supplies opening, closing and stock desktop springs.
Resize and experimental movement have matching suggestions, enabled separately.
These sets require NiriFX 0.16 or newer and use ordinary portable profile documents.

| Set | Opening | Closing | Desktop timing |
| --- | --- | --- | --- |
| `fragments-motion` | Mixed Confetti | Orbiting Shapes | Balanced |
| `ribbons-motion` | Ribbon Wave | Zipper | Gentle |
| `elastic-motion` | Spring Wobble | Rubber Band | Playful |

| Fragments | Ribbons | Elastic |
| --- | --- | --- |
| ![Mixed fragments arrive and orbit away](gifs/profile-fragments-motion.gif) | ![Waving ribbons arrive and zipper shut](gifs/profile-ribbons-motion.gif) | ![A springy arrival and rubber-sheet exit](gifs/profile-elastic-motion.gif) |

These shader loops show opening and closing with synthetic content. For native
workspace, camera and overview recordings, see [desktop motion packs](desktop-motion.md).
Desktop timing changes those three stock springs; it does not add workspace shaders.

## Try a set

Use the existing Studio or terminal workflow:

```sh
niri-fx list --collection action-sets --text
niri-fx studio --profile fragments-motion
niri-fx setup --target standalone --profile fragments-motion --no-launcher
```

The setup command previews the files. Append `--apply` to activate the reviewed
profile with a restore snapshot. From the checkout, replace `niri-fx` with
`python3 -m niri_fx`. Shell pickers use the same profile names after refreshing
their preset pack. See [setup and restore](setup.md) and [collections](collections.md).

In Studio, choose **Ready-made profile**, then view Resize or Movement under
**Editing action**. The matching suggestion appears in the controls without
changing the action. Choose **NiriFX Style** to include it in saved JSON.
Undo restores the prior choice. Imported or renamed sets retain suggestions when
both opening and closing still match the original set; editing either action
removes the match. A saved resize or movement choice always takes precedence.

## Add matching resize

Built-in profiles preserve existing resize settings. These separate examples
add a resize effect on stock Niri; each keeps the same opening, closing and desktop timing.

| Fragments: edge rebuild | Ribbons: restrained wave | Elastic: gentle spring |
| --- | --- | --- |
| ![Mixed pieces rebuild a resized edge](gifs/fragments-motion-resize.gif) | ![Ribbons wave during growth and shrink](gifs/ribbons-motion-resize.gif) | ![A resized window gently springs into place](gifs/elastic-motion-resize.gif) |
| [Resize JSON](../examples/profiles/fragments-motion-resize.json) | [Resize JSON](../examples/profiles/ribbons-motion-resize.json) | [Resize JSON](../examples/profiles/elastic-motion-resize.json) |

These are the actual resize shaders on synthetic textures and a controlled size
path. Real clients and interrupted resizing can behave differently. See
[resize requirements and limits](resize.md).

Create the same explicit selection without editing JSON:

```sh
niri-fx profile --action-set fragments-motion --include-resize > /tmp/fragments-resize.json
niri-fx studio --custom /tmp/fragments-resize.json
```

Without `--include-resize`, this command leaves resize unset. Both include flags
require `--action-set`; arbitrary per-action overrides use the existing preset
flags or Studio instead.

## Add experimental movement

Native movement requires the separately built [experimental compositor](../experimental/README.md).
The following recordings show real column swaps with synthetic mint and violet
clients in a nested compositor. Each returns to the initial window positions.

| Fragment wake | Ribbon transfer | Momentum glide |
| --- | --- | --- |
| ![Two windows exchange positions as mixed fragments](gifs/native-swap-fragments-motion.gif) | ![Two windows exchange positions as waving ribbons](gifs/native-swap-ribbons-motion.gif) | ![Two windows glide and settle into exchanged positions](gifs/native-swap-elastic-motion.gif) |
| [Resize and movement JSON](../examples/profiles/fragments-motion-native.json) | [Resize and movement JSON](../examples/profiles/ribbons-motion-native.json) | [Resize and movement JSON](../examples/profiles/elastic-motion-native.json) |

Those three downloads include **both resize and movement**. To include
movement alone, use only `--include-movement`:

```sh
niri-fx profile --action-set fragments-motion --include-movement > /tmp/fragments-movement.json
# Run from the checkout after building the pinned experimental compositor:
python3 scripts/nested-demo.py --custom /tmp/fragments-movement.json
```

Adding movement to JSON does not activate it. Stock exports omit movement;
[live activation](setup.md#activate-experimental-movement) requires explicit
standalone review and a verified running compositor contract. Native motion
follows compositor trajectories; Studio's shader preview uses a synthetic path.
These sets do not add interactive drag wobble or particle sharing between windows.

[All nine examples and preview commands](../examples/profiles/README.md#coordinated-action-sets)
provide base, resize-only and experimental versions. The
[recording manifests](gifs/README.md) retain exact settings and source hashes.
