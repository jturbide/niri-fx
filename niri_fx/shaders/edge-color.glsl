// SPDX-License-Identifier: MIT
// Return straight RGB in [0, 1]. Callers multiply by sampled alpha before
// compositing; saturation zero spans black-to-white independently of hue.
vec3 fx_edge_color() {
    vec3 hue = clamp(abs(fract(@EDGE_HUE@ / 360.0 + vec3(0.0, 0.6666667, 0.3333333)) * 6.0 - 3.0) - 1.0, 0.0, 1.0);
    return mix(vec3(1.0), hue, @EDGE_SATURATION@) * @EDGE_BRIGHTNESS@;
}
