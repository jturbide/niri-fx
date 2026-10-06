# iNiR / iRiS integration contract

Niri renders application windows. iNiR provides shared shell services; iRiS is
one of its shell families. NiriFX uses Niri GLSL and the existing external
preset registry, without modifying installed QML or running an animation daemon.
For choosing and applying effects, start with [Library](library.md). This page
describes the adapter boundaries for contributors and shell integrators.

## Shell interfaces

The adapter uses these iNiR interfaces:

- `services/NiriAnimationPresets.qml` loads and watches user presets.
- `scripts/niri-config.py get-animation-presets` returns available entries and
  the recognized active preset.
- `modules/iris/settings/IrisOptions.qml` exposes the `niriMotion` row under
  Windows / Movement / Style; `IrisNiriMotionGallery.qml` uses the shared service.
- A preset's `types` contains duration/curve/custom-shader or spring settings.
- Applying a preset replaces the shell-managed animations block while retaining
  global off/slowdown controls.

Recheck these interfaces after shell updates; iNiR does not provide a stable
third-party plugin API for this adapter. The native gallery thumbnail shows generic timing; it
cannot reproduce the fragment shader. Detailed controls remain in Studio.
The [validation guide](validation.md#independent-action-choices-and-upgrades)
records the tested helper and service workflows.

## Registry ownership and activation

Built-in IDs use `niri-fx-`; named custom IDs use
`niri-fx-custom-`. Pack updates replace only incoming owned IDs and preserve
named custom styles and other providers. Malformed JSON, duplicate IDs and foreign
ownership collisions are rejected. Writes are atomic, back up the resolved target,
and preserve symlinks. Unregister removes all NiriFX entries, including customs.

Each generated entry snapshots the recognized base preset's other animation
settings. An unknown active style requires an explicit `--base`; timings are not
approximated. Base changes are not inherited automatically. Each stock action
can Preserve its base settings, use a NiriFX Style or be Off. Preserve follows the
underlying shell preset, including a disabled action; it does not copy a previous
NiriFX override.

The shell's serializer and active-style matcher represent Off as `duration-ms 0`
with a linear curve and no custom shader. The adapter uses that representation
in registry `types`; the portable profile still stores `"off"`. Standalone KDL
exports continue to emit Niri's `off` node. Global Off and slowdown controls and
unselected animation types retain their existing values.

Registration and saving a profile leave the active config unchanged. Selecting a
registered style in the shell activates it. Library's **Review & apply** uses the
installed serializer to prepare the registry and animation file together; its
reviewed transaction validates the Niri config and saves a Restore snapshot.
The shell service watches those files and recognizes the applied style.

Re-registering alone does not replace a shader already embedded in Niri's config:
reselect it afterward, or use Library Apply. Unregister also leaves active effects
unchanged. Restore a Library transaction with **Restore previous**, or select a
shell style before unregistering. See [update and rollback](getting-started.md).

## Studio

Studio shares Python/GLSL templates with CLI exports. Its loopback save endpoint
accepts validated parameters rather than arbitrary shader text or destinations.
Requests require a per-session token and matching Origin/Host; request bodies are
limited to 32 KiB in NiriFX 0.21 (16 KiB in 0.20). See [security boundaries](../SECURITY.md).

Chromium app mode uses a dedicated profile under
`$XDG_STATE_HOME/niri-fx/studio-profile`, defaulting to
`~/.local/state/niri-fx/studio-profile`. Use `--browser` for a tab or
`--no-browser` to launch nothing. The server exits after 15 minutes without a
browser heartbeat, or immediately with Ctrl+C from its terminal.

Movement shaders and pointer deformation are excluded from this registry's
animation types. Portable profiles retain those choices, and Studio can preview
them. Live native activation uses the standalone target and a verified
[experimental compositor](../experimental/README.md).

## Other shells

The [DMS adapter](dms.md), [Noctalia guide](noctalia.md) and standalone Library
share the same effect model and transaction backend. They have different
configuration owners; they do not use iNiR's registry. See
[compatibility](compatibility.md) before adding an adapter or extending a shell UI.

## NiriFX identity

The CLI, registry generator and ID prefix are `niri-fx`; the Python package is
`niri_fx`. Single-effect documents use schema 3; independent action profiles use
kind `profile`, schema 2 without a Swap override or schema 3 with one, with schema 1 import support.
NiriFX 0.21 adds schema 4 for complete continuous-fragment responses. Stock
shell adapters omit native movement, Swap and response nodes while portable
JSON retains their settings. Registry paths remain
those defined by iNiR's external-preset API, including its config-root selection.
