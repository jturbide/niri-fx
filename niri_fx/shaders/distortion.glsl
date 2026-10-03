// SPDX-License-Identifier: MIT
// Original NiriFX travelling shock front, radial ripples and planar wave folds.
vec4 @ENTRY@(vec3 coords_geo, vec3 size_geo) {
    float p = @PROGRESS@;
    if (p >= 1.0) return vec4(0.0);
    vec2 uv = coords_geo.xy, size = max(size_geo.xy, vec2(1.0));
    vec2 origin = vec2(@DISTORTION_X@, @DISTORTION_Y@);
    // Radial distances use logical pixels, keeping circular fronts circular
    // on wide windows. The farthest corner bounds the complete sweep.
    vec2 delta = (uv - origin) * size;
    float radius = max(length(max(origin, 1.0 - origin) * size), 1.0);
    float distance = length(delta), phase = p * @DISTORTION_CYCLES@ * 6.2831853;
    vec2 direction = delta / max(distance, 0.001);
    float attenuation = exp(-@DISTORTION_FALLOFF@ * distance / radius);
    float wave = sin(distance / @DISTORTION_WAVELENGTH@ * 6.2831853 - phase);
    float envelope = sin(p * 3.14159265);
    float mask = 1.0 - smoothstep(@DISTORTION_FADE@, 1.0, p);
    // Shockwave concentrates displacement around a travelling front; the
    // other modes distort the whole texture and use the independent fade.
    if (@DISTORTION_MODE@ == 0) {
        float front = mix(-@DISTORTION_WIDTH@, radius + @DISTORTION_WIDTH@, p);
        float offset = distance - front;
        envelope *= exp(-pow(offset / @DISTORTION_WIDTH@, 2.0) * 3.0);
        wave = sin(offset / @DISTORTION_WAVELENGTH@ * 6.2831853 - phase);
        mask = smoothstep(front - @DISTORTION_WIDTH@ * 0.5, front + @DISTORTION_WIDTH@ * 0.5, distance);
    }
    if (@DISTORTION_MODE@ == 2) {
        float angle = radians(@DISTORTION_ANGLE@);
        vec2 axis = vec2(cos(angle), sin(angle));
        direction = vec2(-axis.y, axis.x);
        wave = sin(dot(delta, axis) / @DISTORTION_WAVELENGTH@ * 6.2831853 - phase);
    }
    // Pull from source coordinates rather than pushing pixels forward. Samples
    // outside geometry return transparent instead of stretching edge texels.
    vec2 source = uv - direction * wave * @DISTORTION_STRENGTH@ * envelope * attenuation / size;
    if (p <= 0.0) { source = uv; mask = 1.0; }
    if (any(lessThan(source, vec2(0.0))) || any(greaterThanEqual(source, vec2(1.0)))) return vec4(0.0);
    return texture2D(niri_tex, (niri_geo_to_tex * vec3(source, 1.0)).xy) * mask;
}
