// SPDX-License-Identifier: MIT
vec3 fx_edge_color() {
    vec3 hue = clamp(abs(fract(@EDGE_HUE@ / 360.0 + vec3(0.0, 0.6666667, 0.3333333)) * 6.0 - 3.0) - 1.0, 0.0, 1.0);
    return mix(vec3(1.0), hue, @EDGE_SATURATION@) * @EDGE_BRIGHTNESS@;
}
