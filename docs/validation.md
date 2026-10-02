# Prototype validation

## Version 0.2 — gravity and Studio

Checked on 2026-10-02:

- The user reported the original effect working well in Niri; Subtle was
  active. All three original shader/timing pairs remain byte-for-byte equal
  to their installed 0.1 presets.
- 19 tests passed, including named preset preservation, parameter validation,
  the real loopback save endpoint, and rejection of foreign-origin requests.
- All 18 built-in open/close shaders compiled as GLSL ES 1.00; all nine KDL
  outputs passed Niri 26.04 configuration validation.
- All nine presets were applied and correctly recognized by the installed
  iNiR helper in an isolated temporary configuration. Global off/slowdown
  settings survived every application.
- Browser rendering checked every preset's intact start, nonempty fragmented
  midpoint and fully transparent end. Measured fragment positions confirmed
  Earth moving downward, Updraft upward, and Black Hole contracting.
- Browser-generated GLSL matched Python-generated GLSL for every built-in
  preset. Extreme count, gravity, rotation and orbit controls rendered without
  WebGL errors. The Save button wrote a named preset to an isolated registry.
- The wheel installed and rendered KDL and the editor outside the checkout;
  the desktop launcher passed `desktop-file-validate`.

Browser checks use Chromium software WebGL. They do not establish real Niri
GPU performance. Native visual acceptance of the new gravity modes, clipping
at large displacements, scaling and application-specific behavior remains open.

## Version 0.1 — original effect

Checked on 2026-10-02:

- 13 Python unit tests passed: preservation of unrelated presets and base
  timings, malformed/duplicate registry rejection, ownership collisions,
  idempotence, backups, symlinks, dry-run behavior, and input validation.
- All six shaders (open and close across three presets) compiled with
  `glslangValidator` as GLSL ES 1.00.
- All three generated KDL configurations passed `niri validate` with
  Niri 26.04 (`8ed0da4`).
- The installed iNiR helper applied each generated preset inside an isolated
  temporary XDG configuration, recognized the active preset correctly, and
  retained global `off` and `slowdown` controls.
- A wheel and source distribution built; installing the wheel into an isolated
  virtual environment preserved the shader and preview resources. The installed
  CLI rendered valid KDL and generated its standalone preview outside the checkout.
- Chromium's WebGL renderer compiled the actual effect and rendered an intact
  sample window and intermediate fragment motion. The included image is a
  synthetic preview, not a desktop screenshot. Software rendering was used;
  this is not a benchmark of the compositor or the user's GPU.

Still to validate in a real Niri session: visual preference, startup/closing
behavior with real applications, shader compilation in Niri's own renderer,
frame time, client-side decoration behavior, output-edge clipping, transparency,
fractional scaling, and multiple monitors. The project deliberately remains
labeled a prototype until those checks are complete.
