# Troubleshooting

## The effect does not appear

Confirm Niri animations are enabled. `register` and Studio **Save to iRiS** only
update the registry: select the resulting style in Settings to activate it.
After updating the pack, reselect it to replace the old embedded shader.

Run `niri validate`. A late standalone animation include can override the shell's
selected preset. Use the [installation guide](getting-started.md) to choose one
configuration owner. The stock iRiS gallery thumbnail shows generic timing,
not an accurate shader preview; use Studio to inspect the effect.

## Registration cannot recognize my active preset

Unknown custom timings are not approximated. Choose a known shell style as your
base with `--base`, for example `--base bouncy`, and review the `--dry-run` output
before registering. Saved styles snapshot that base's other animation settings.
Missing helper or registry errors may mean iNiR lacks external preset support,
or needs explicit `--inir-root` / `--registry` paths.

Malformed JSON, duplicate IDs and foreign preset ownership collisions are
rejected without replacing the registry. Keep the file and its backup for
diagnosis; do not delete unrelated presets to force registration.

## Studio opens in a tab, is blank, or cannot save

Chromium app mode is optional. `studio --browser` uses the default browser;
`studio --no-browser` prints the local URL without launching one. WebGL must be
available. A restrictive browser configuration or failed GPU context can prevent
preview rendering; try a current WebGL-capable browser.

Offline previews export files but cannot save to iRiS. Use `studio` for saving,
with iNiR installed, and open its printed loopback URL directly. The save endpoint
checks the session token and Origin; embedding the page in another site is not
supported. The server expires after 15 minutes without a browser heartbeat;
relaunch it if the session expired.

`preview --output` refuses to overwrite an existing file. Choose a new filename.
If a launcher stopped working after moving the checkout, recreate it with
`python3 scripts/install-desktop.py`.

## Resize or movement does nothing

Resize fragments are disabled by default. Enable them explicitly in Studio or
with `--resize`, save/export, and apply the result. Changing resize strength alone
does not enable the effect.

Stock Niri does not accept a custom movement shader. Studio's Move and Swap tabs
are concepts. The [nested experimental demo](../experimental/README.md) is the
supplied path for real move/swap effects; do not paste its config into stock Niri.
Direct pointer dragging does not gain a particle timeline even in the prototype.

## Pieces clip, performance drops, or transparent windows look different

Large excursions can clip at output edges and Niri's animation draw bounds.
Client-side shadows outside window geometry are omitted during breakup. Try less
scatter, gravity or orbit, and compare Subtle with a heavier preset. Particle
count alone is not a reliable GPU cost estimate: the shader performs up to 27
candidate-cell checks per output pixel regardless of count, and expanded draw
area also costs work. Reduce display area/effect spread when comparing frame time.

Software WebGL checks and GIFs do not establish desktop GPU performance. Report
the preset, compositor version, GPU/driver, scale factor, window size and minimal
reproduction. Include whether the issue occurs in stock Niri or only the patch.
Use synthetic content for captures and remove private data from logs/configs.

## Reporting a problem

Use the repository's bug template with `python3 -m niri_fragments --version`,
`niri --version`, your shell version/commit and the relevant effect parameters.
Do not attach your whole desktop configuration or a Studio URL containing its
session token. For security issues, follow [SECURITY.md](../SECURITY.md).
