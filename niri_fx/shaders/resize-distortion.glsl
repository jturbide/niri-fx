// SPDX-License-Identifier: MIT
@RESIZE_COMMON@
// Recover the complete signed size change, independent of animation progress.
// Niri exposes dimensions here, not the screen-space edge being dragged.
vec2 resize_signed_change() {
    vec2 prev = vec2(niri_curr_geo_to_prev_geo[0][0], niri_curr_geo_to_prev_geo[1][1]);
    vec2 next = vec2(niri_curr_geo_to_next_geo[0][0], niri_curr_geo_to_next_geo[1][1]);
    return clamp(log(max(prev, vec2(0.0001)) / max(next, vec2(0.0001))), -1.0, 1.0);
}
vec2 resize_sealed_offset(vec2 uv, vec2 offset) {
    // A smooth component-wise limit keeps samples strictly inside the rectangle.
    // Both displacement and its limit vanish at the border. Unlike clamping UVs,
    // this does not smear decorations across transparent or out-of-bounds pixels.
    vec2 margin = max(min(uv, 1.0 - uv), 0.0);
    offset *= 16.0 * uv.x * (1.0 - uv.x) * uv.y * (1.0 - uv.y);
    return offset * (0.8 * margin) / (0.8 * margin + abs(offset) + 0.000001);
}
vec4 resize_color(vec3 coords_curr_geo, vec3 size_curr_geo) {
    float p = niri_clamped_progress, blend = smoothstep(0.2, 0.8, p);
    vec2 uv = coords_curr_geo.xy, size = max(size_curr_geo.xy, vec2(1.0));
    if (p <= 0.0 || p >= 1.0 || @RESIZE@ <= 0.0) return resize_sample(uv, blend);
    if (@DISTORTION_RESIZE_MODE@ != 0) {
        if (any(lessThan(uv, vec2(0.0))) || any(greaterThanEqual(uv, vec2(1.0)))) return resize_sample(uv, blend);
        vec2 change = resize_signed_change();
        float pulse = pow(sin(p * 3.14159265359), 2.0);
        vec2 offset;
        if (@DISTORTION_RESIZE_MODE@ == 1) {
            // Width changes drive the right-edge wave; height changes drive the
            // bottom-edge wave. Shrinking reverses displacement, not elapsed time.
            vec2 distance = (1.0 - uv) * size;
            vec2 wave = sin(distance / @DISTORTION_WAVELENGTH@ * 6.2831853 - p * @DISTORTION_CYCLES@ * 6.2831853);
            offset = wave * exp(-@DISTORTION_FALLOFF@ * (1.0 - uv));
            offset *= change * @DISTORTION_STRENGTH@ * @RESIZE@ * pulse / size;
        } else {
            // The dominant changing axis chooses the twist direction. Work in
            // logical pixels so wide and tall windows do not become elliptical.
            float amount = abs(change.x) >= abs(change.y) ? change.x : change.y;
            float angle = radians(@RESIZE_TWIST@) * amount * @RESIZE@ * pulse;
            vec2 q = (uv - 0.5) * size;
            vec2 rotated = vec2(cos(angle) * q.x - sin(angle) * q.y, sin(angle) * q.x + cos(angle) * q.y);
            offset = (rotated - q) / size;
        }
        return resize_sample(uv + resize_sealed_offset(uv, offset), blend);
    }
    vec2 delta = (uv - vec2(@DISTORTION_X@, @DISTORTION_Y@)) * size;
    float distance = length(delta), pulse = pow(sin(p * 3.14159265359), 2.0);
    float wave = sin(distance / @DISTORTION_WAVELENGTH@ * 6.2831853 - p * @DISTORTION_CYCLES@ * 6.2831853);
    float attenuation = exp(-@DISTORTION_FALLOFF@ * distance / max(length(size), 1.0));
    vec2 offset = delta / max(distance, 1.0) / size * wave * pulse * attenuation;
    offset *= @DISTORTION_STRENGTH@ * @RESIZE@ * length(resize_change());
    return resize_sample(uv + offset * resize_boundary(uv), blend);
}
