# Settings integration

Niri owns application-window rendering. iNiR provides shared services; iRiS is
one of its shell families. The fragment effect consequently belongs in Niri
GLSL, while preset selection belongs in the existing shell settings.

The first adapter uses the existing external registry contract:

- `services/NiriAnimationPresets.qml` loads and watches user presets.
- `scripts/niri-config.py get-animation-presets` exposes the current registry
  and recognized active preset.
- `modules/iris/settings/IrisOptions.qml` exposes a `niriMotion` row under
  Windows / Movement / Style.
- `IrisNiriMotionGallery.qml` uses the shared preset service.
- Each preset's `types` contains duration/curve/custom-shader or spring entries.
- Applying a preset replaces the shell-managed animations block, retaining
  the global off/slowdown controls.

These observations were checked against the installed iNiR source during
initial development. They are an integration contract to recheck after shell
updates, not a stable third-party plugin API.

Native registration avoids modifying shell QML and survives runtime source
updates. The animations do not require a daemon. A shell preset selection
remains the only action that activates the registered effect.

Version 0.2 adds named custom presets and a local Studio editor. The editor
and CLI share GLSL templates and the same validated effect parameter model.
Studio saves through a session-bound loopback endpoint; it accepts parameter
documents rather than arbitrary shader strings or filesystem destinations.
Its process is on-demand and expires after its browser tab stops pinging.

Built-in IDs retain the `niri-fragments-` prefix; custom IDs use
`niri-fragments-custom-`. Updating the built-in pack replaces only incoming
IDs, preserving named custom styles and other providers. Unregister explicitly
removes all entries owned by this project. Saving a named style snapshots the
recognized base preset's non-open/close settings, just like built-in registration.

## Next steps

1. Validate and tune the shader in a real Niri session, including scaling,
   transparency, screen edges, fullscreen windows and low refresh rates.
2. Propose optional effect metadata to iNiR for embedding Studio's controls
   directly in native settings, preserving unrelated timings.
3. Add a shader-accurate preview hook to the shell gallery. Its existing
   timing thumbnail cannot accurately display fragment motion.

An upstream contribution should be developed and reviewed separately from
the installed shell. No runtime fork or upstream pull request is required for
the initial external preset pack.
