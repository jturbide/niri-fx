// SPDX-License-Identifier: MIT
@RESIZE_COMMON@
vec4 resize_color(vec3 coords_curr_geo, vec3 size_curr_geo) {
    float p = niri_clamped_progress, blend = smoothstep(0.2, 0.8, p);
    vec2 uv = coords_curr_geo.xy;
    if (p <= 0.0 || p >= 1.0 || @RESIZE@ <= 0.0) return resize_sample(uv, blend);
    vec2 axis = vec2(cos(radians(@SLICE_ANGLE@)), sin(radians(@SLICE_ANGLE@)));
    vec2 size = fx_resize_material_size(max(size_curr_geo.xy, vec2(1.0)));
    float span = max(dot(abs(axis), size), 1.0);
    float strip = dot(uv * size, axis) / span * float(@SLICE_COUNT@);
    float fold = sin(strip * 3.14159265359 + p * @SLICE_STAGGER@ * 6.2831853);
    float pulse = pow(sin(p * 3.14159265359), 2.0);
    float amount = clamp(length(resize_change()) * 2.5, 0.0, 1.0) * @RESIZE@ * pulse;
    // Fold amplitude stays below a quarter strip: no inverse-search loop and
    // no fold-over singularities, even at maximum count/strength.
    vec2 offset = axis * fold * span / max(float(@SLICE_COUNT@), 2.0) / size * 0.22 * amount;
    return resize_sample(uv + offset * resize_boundary(uv), blend);
}
