// SPDX-License-Identifier: MIT
// Stock Niri supplies the previous and next client textures in current geometry.
// Share the sample contract across continuous deformations; do not clamp texture
// edges, which would smear client-side decorations into transparent pixels.
@RESIZE_STATE@
vec4 resize_sample(vec2 geo, float blend) {
    vec2 prev = (niri_geo_to_tex_prev * vec3(geo, 1.0)).xy;
    vec2 next = (niri_geo_to_tex_next * vec3(geo, 1.0)).xy;
    vec4 a = vec4(0.0), b = vec4(0.0);
    if (all(greaterThanEqual(prev, vec2(0.0))) && all(lessThan(prev, vec2(1.0)))) a = texture2D(niri_tex_prev, prev);
    if (all(greaterThanEqual(next, vec2(0.0))) && all(lessThan(next, vec2(1.0)))) b = texture2D(niri_tex_next, next);
    return mix(a, b, blend);
}
vec2 resize_change() {
    vec2 ratio = vec2(niri_curr_geo_to_next_geo[0][0], niri_curr_geo_to_next_geo[1][1]);
    ratio = fx_resize_reference_ratio(ratio);
    return clamp(log(max(ratio, vec2(0.0001))) * 2.0, -1.0, 1.0);
}
vec2 resize_boundary(vec2 uv) {
    // Geometry edges stay sealed even though stock resize bounds do not expand.
    return sin(clamp(uv, 0.0, 1.0) * 3.14159265359);
}
