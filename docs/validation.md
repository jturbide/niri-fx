# Initial prototype validation

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
