// SPDX-License-Identifier: MIT
@RESIZE_COMMON@
vec4 resize_color(vec3 coords_curr_geo, vec3 size_curr_geo) {
    float p = niri_clamped_progress, blend = smoothstep(0.2, 0.8, p);
    vec2 uv = coords_curr_geo.xy, size = max(size_curr_geo.xy, vec2(1.0));
    if (p <= 0.0 || p >= 1.0 || @RESIZE@ <= 0.0) return resize_sample(uv, blend);
    vec2 delta = (uv - vec2(@DISTORTION_X@, @DISTORTION_Y@)) * size;
    float distance = length(delta), pulse = pow(sin(p * 3.14159265359), 2.0);
    float wave = sin(distance / @DISTORTION_WAVELENGTH@ * 6.2831853 - p * @DISTORTION_CYCLES@ * 6.2831853);
    float attenuation = exp(-@DISTORTION_FALLOFF@ * distance / max(length(size), 1.0));
    vec2 offset = delta / max(distance, 1.0) / size * wave * pulse * attenuation;
    offset *= @DISTORTION_STRENGTH@ * @RESIZE@ * length(resize_change());
    return resize_sample(uv + offset * resize_boundary(uv), blend);
}
