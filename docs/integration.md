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
updates. It does not require a daemon. A shell preset selection remains the
only action that activates the registered effect.

## Next steps

1. Validate and tune the shader in a real Niri session, including scaling,
   transparency, screen edges, fullscreen windows and low refresh rates.
2. Add named custom presets to the adapter, backed by the same validated
   parameter model used by standalone rendering.
3. Propose optional effect metadata to iNiR for native tile-size, scatter and
   separate open/close duration controls, preserving unrelated timings.
4. Add a shader-accurate preview hook to the shell gallery. Its existing
   timing thumbnail cannot accurately display fragment motion.

An upstream contribution should be developed and reviewed separately from
the installed shell. No runtime fork or upstream pull request is required for
the initial external preset pack.
