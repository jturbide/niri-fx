# iNiR / iRiS integration contract

Niri renders application windows. iNiR provides shared shell services; iRiS is
one of its shell families. Fragments uses Niri GLSL and the existing external
preset registry, without modifying installed QML or running an animation daemon.

## Shell interfaces

Checked against the installed iNiR source during development on 2026-10-02:

- `services/NiriAnimationPresets.qml` loads and watches user presets.
- `scripts/niri-config.py get-animation-presets` returns available entries and
  the recognized active preset.
- `modules/iris/settings/IrisOptions.qml` exposes the `niriMotion` row under
  Windows / Movement / Style; `IrisNiriMotionGallery.qml` uses the shared service.
- A preset's `types` contains duration/curve/custom-shader or spring settings.
- Applying a preset replaces the shell-managed animations block while retaining
  global off/slowdown controls.

This is an integration contract to recheck after shell updates, not a stable
third-party plugin API. The native gallery thumbnail shows generic timing; it
cannot reproduce the fragment shader. Detailed controls remain in Studio.

## Registry ownership and activation

Built-in IDs use `niri-fragments-`; named custom IDs use
`niri-fragments-custom-`. Pack updates replace only incoming owned IDs and preserve
named custom styles and other providers. Malformed JSON, duplicate IDs and foreign
ownership collisions are rejected. Writes are atomic, back up the resolved target,
and preserve symlinks. Unregister removes all Fragments entries, including customs.

Each generated entry snapshots the recognized base preset's other animation
settings. An unknown active style requires an explicit `--base`; timings are not
approximated. Base changes are not inherited automatically. Since 0.4.1, resize
fragments default off, preserving base resize settings unless explicitly enabled.
Custom JSON without a resize field also opts out; existing custom choices survive.

Registration and Studio saving do not activate effects. A shell preset selection
performs activation. Re-registering does not replace the shader already embedded
in Niri's config: reselect it afterward. Named customs keep their saved shader
until explicitly saved again. Unregister also leaves the active config untouched;
select a non-Fragments style first. See [update and rollback](getting-started.md).

## Studio

Studio shares Python/GLSL templates with CLI exports. Its loopback save endpoint
accepts validated parameters rather than arbitrary shader text or destinations.
Requests require a per-session token and matching Origin/Host; request bodies are
limited to 16 KiB. See [security boundaries](../SECURITY.md).

Chromium app mode uses a dedicated profile under
`$XDG_STATE_HOME/niri-fragments/studio-profile`, defaulting to
`~/.local/state/niri-fragments/studio-profile`. Use `--browser` for a tab or
`--no-browser` to launch nothing. The server exits after 15 minutes without a
browser heartbeat, or immediately with Ctrl+C from its terminal.

Movement shaders are never written to this registry or stock KDL exports. Studio
Move/Swap tabs are design previews; the [native experiment](../experimental/README.md)
has its own isolated build and config.

## Future integrations

Possible iNiR contributions include a Studio launcher, optional effect metadata
for native controls, and a shader-accurate gallery preview. They should be developed
against upstream source and reviewed separately from installed shell files.
See [compatibility](compatibility.md) for the proposed DMS adapter and compositor
boundaries; none of these future integrations are implied by current registration.

## NiriFX compatibility

The public brand/CLI is NiriFX as of 0.6. Registry `generator` ownership and ID
prefixes remain `niri-fragments` so updates and removal recognize existing entries.
Display labels use NiriFX. `effect.family` selects the shader; missing family in
legacy JSON defaults to `fragments`. Fragment exports remain schema 1; slices
use schema 2. Never infer capabilities from the selected shell: Slices currently
supports only open/close, while Fragment movement still requires patched Niri.
See [migration](migration-0.6.md).
