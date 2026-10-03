// SPDX-License-Identifier: MIT
// Original NiriFX value-noise erosion, preserving premultiplied window alpha.
float fx_hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7)) + niri_random_seed * 91.7) * 43758.5453);
}
float fx_noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(fx_hash(i), fx_hash(i + vec2(1.0, 0.0)), f.x),
               mix(fx_hash(i + vec2(0.0, 1.0)), fx_hash(i + vec2(1.0)), f.x), f.y);
}
vec4 @ENTRY@(vec3 coords_geo, vec3 size_geo) {
    vec2 uv = coords_geo.xy;
    if (any(lessThan(uv, vec2(0.0))) || any(greaterThanEqual(uv, vec2(1.0)))) return vec4(0.0);
    float p = @PROGRESS@;
    vec4 color = texture2D(niri_tex, (niri_geo_to_tex * coords_geo).xy);
    if (p <= 0.0) return color;
    if (p >= 1.0) return vec4(0.0);
    float field = fx_noise(uv * size_geo.xy / @DISSOLVE_SCALE@);
    float order = uv.x;
    if (@DISSOLVE_DIRECTION@ == 2) order = 1.0 - uv.x;
    if (@DISSOLVE_DIRECTION@ == 3) order = uv.y;
    if (@DISSOLVE_DIRECTION@ == 4) order = 1.0 - uv.y;
    if (@DISSOLVE_DIRECTION@ == 5) order = length((uv - 0.5) * 1.41421356237);
    if (@DISSOLVE_DIRECTION@ != 0) field = mix(field, order, @DISSOLVE_BIAS@);
    float threshold = mix(-@DISSOLVE_SOFTNESS@, 1.0 + @DISSOLVE_SOFTNESS@, p);
    float mask = smoothstep(threshold - @DISSOLVE_SOFTNESS@, threshold + @DISSOLVE_SOFTNESS@, field);
    float edge = (1.0 - smoothstep(0.0, max(@EDGE_WIDTH@, 0.00001), field - threshold))
                 * smoothstep(0.0, 0.08, p) * (1.0 - step(@EDGE_WIDTH@, 0.0));
    vec3 hue = clamp(abs(fract(@EDGE_HUE@ / 360.0 + vec3(0.0, 0.6666667, 0.3333333)) * 6.0 - 3.0) - 1.0, 0.0, 1.0);
    color.rgb = mix(color.rgb, mix(vec3(0.15), hue, 0.85) * color.a, edge);
    return color * mask;
}
