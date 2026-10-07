# Share desktop settings between Niri and NiriFX

Shared settings let both sessions follow your normal Niri configuration for
outputs, input, shortcuts, layout and shell-generated settings. Studio writes
common effects such as Open, Close and Resize into a stock-compatible include.
Move, Swap, pointer wobble and continuous fragments stay in a separate NiriFX
include for the selected compositor build.

This workflow is included in NiriFX 0.20 and newer. First
[prepare a NiriFX session](native-session.md) and
update the persistent [CLI, Studio and login tools](tool-updates.md). The selected
bundle must have a saved effects recipe: choose a combo in local Studio, review
it, then **Apply to desktop** or **Select for next login**. Saving a profile file
alone does not configure that bundle.

## Start in Studio

Close other NiriFX editors and open the adopted **NiriFX Studio** app. The development
version shows a shared-settings card below the session controls. It offers the
normal Niri configuration selected when Studio opens; **Share normal Niri settings**
always requires its own review and does not use an unsaved draft.

To choose another normal configuration, launch Studio with:

```sh
niri-fx studio --target native --shared-config ~/.config/niri/config.kdl
```

For separate native storage, also pass `--native-root /path/to/native-storage`.
Adoption uses the current selected bundle's saved recipe. The configuration and
storage paths are fixed when Studio opens; imported profiles cannot change them.

1. Check the configuration path under **Using a saved copy of Niri settings**.
2. Choose **Share normal Niri settings**. This uses the bundle's saved recipe,
   leaving your unsaved Studio draft unchanged.
3. Review the listed configuration changes, then choose **Apply shared settings**.
4. Save or export any draft edits, close Studio, and reopen it with
   `niri-fx studio --target native` to edit the newly selected shared setup.
   Repeat the same `--native-root` argument if you use separate storage.

In released 0.22.1 and earlier tools, pass `--shared-config` as shown above and
expand **Session details and saved recipe** to find the sharing controls.
The development version also accepts that explicit override; otherwise `--config`
provides the source. Offering a source does not connect it until you apply the review.

First adoption requires your next NiriFX login to use the shared wrapper. Log
out when convenient and choose **NiriFX**. Once a session uses that wrapper,
Niri watches its included files and reloads their changes automatically. Choosing
a different compositor build also requires the next login for its native effects.
The common effects include can already affect a running stock Niri session.

## Choose effects and keep using your shell settings

Keep editing ordinary desktop settings through your shell or normal Niri files.
Choose effects per action in Studio, then **Review & apply** and **Apply shared
settings**. **Preserve** removes that action's NiriFX override and follows the
current normal configuration underneath it. **Off** explicitly disables the
action. Global animation Off and slowdown settings still apply.

The result reports `activation: "config-written"` and `live.status: "unverified"`.
That means the files were updated; Studio has not independently confirmed what
the compositor loaded. Shared mode does not use the separate `--live` IPC reload
workflow. Review the effect on your desktop and check Niri's configuration error
notification if a change does not appear.

Adoption adds one managed include to your normal config and retains a frozen
recovery copy. It does not move your configuration, patch a shell checkout or
install a synchronization daemon. Leave the managed include at the end and use
Studio to change its generated effects files. Unrecognized or externally edited
NiriFX files are refused rather than overwritten. Standalone setup and old
standalone Restore cannot overwrite these shared effects; use shared rollback or
frozen recovery instead.

## Updates and validation

Apply validates the normal configuration with stock Niri and the combined
configuration with the selected NiriFX executable. The stock validator defaults
to `niri` on PATH; pass `--stock-binary /usr/bin/niri` when opening Studio or
running `native share` to choose it explicitly.

A newer stock Niri or shell may introduce configuration syntax that the retained
NiriFX build cannot parse. Failed Apply restores files still owned by that
transaction; a later shared-source edit can also fail the next login's preflight.
Keep stock Niri available, update the NiriFX build, or select frozen recovery.
Normal source edits do not damage the retained recovery copy.

## Rollback and frozen recovery

**Review rollback** restores the previous saved effects recipe. When that recipe
uses shared settings, it restores its generated effects while keeping your
current desktop settings. It validates both configurations again and requires a
fresh review.

Use **Review frozen recovery** if the shared source is missing, incompatible or
you want the retained snapshot. Confirm **Select for next login**, then close and
reopen Studio. Recovery selects a closed configuration for your next NiriFX
login; it leaves the shared source and generated effects files unchanged. Stock
Niri therefore keeps using its current settings.

## Equivalent CLI workflow

Find the saved bundle with `niri-fx native status`, then review and apply:

```sh
niri-fx native share BUNDLE_ID --config ~/.config/niri/config.kdl
niri-fx native share BUNDLE_ID --config ~/.config/niri/config.kdl \
  --apply --expect-plan REVIEWED_SHA256
```

Use the new shared bundle ID with `native configure` to choose another prefab or
document. Do not add `--live`. Every shared change requires the `plan_sha256`
from a fresh review and the same arguments on Apply.

For the previous recipe, use `niri-fx native rollback`, then repeat with
`--apply --expect-plan REVIEWED_SHA256`. For a frozen snapshot:

```sh
niri-fx native recover SHARED_BUNDLE_ID
niri-fx native recover SHARED_BUNDLE_ID --apply --expect-plan REVIEWED_SHA256
```

Use the same `--root /path/to/native-storage` throughout if your installation has
nondefault storage. Recovery and shared rollback retain older bundles.
