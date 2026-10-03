// SPDX-License-Identifier: MIT
// Pointy hexagons on an axial lattice. Inverse affine flight and a fixed 5x5
// lookup keep work independent of the number of cells in the window.
@NOISE@
vec4 hex_texture(vec2 uv) {
    if (any(lessThan(uv, vec2(0.0))) || any(greaterThanEqual(uv, vec2(1.0)))) return vec4(0.0);
    return texture2D(niri_tex, (niri_geo_to_tex * vec3(uv, 1.0)).xy);
}
vec4 @ENTRY@(vec3 coords_geo, vec3 size_geo) {
    float p = @PROGRESS@;
    if (p <= 0.0) return hex_texture(coords_geo.xy);
    if (p >= 1.0) return vec4(0.0);
    vec2 size = max(size_geo.xy, vec2(1.0));
    vec2 pixel = coords_geo.xy * size, origin = size * 0.5;
    float radius = @HEX_SIZE@;
    float flight = p * p * (3.0 - 2.0 * p);
    float scale = 1.0 + @HEX_SPREAD@ * flight;
    if (@HEX_DIRECTION@ == 1) scale = exp(-1.4 * @HEX_SPREAD@ * flight);
    vec2 guess = origin + (pixel - origin) / scale;
    vec2 axial = vec2((guess.x / 1.73205080757 - guess.y / 3.0) / radius,
                      guess.y * 2.0 / (3.0 * radius));
    vec2 candidate = floor(axial);
    vec4 result = vec4(0.0);
    // A circumradius plus <= .45 radius of drift maps to <1.68 axial units.
    // Center offset from floor adds <1; offsets -2..2 cover both directions.
    for (int y = -2; y <= 2; y++) {
      for (int x = -2; x <= 2; x++) {
        vec2 cell = candidate + vec2(float(x), float(y));
        vec2 center = radius * vec2(1.73205080757 * (cell.x + cell.y * 0.5), 1.5 * cell.y);
        if (any(lessThan(center, vec2(-radius))) || any(greaterThan(center, size + radius))) continue;
        float random = fx_hash(cell), angle = random * 6.2831853;
        float local_time = clamp((p - @HEX_STAGGER@ * random) / (1.0 - @HEX_STAGGER@), 0.0, 1.0);
        // Keep the hexagonal silhouettes readable through most of the journey.
        float shrink = min(1.0, scale) * (1.0 - 0.35 * smoothstep(0.0, 0.7, local_time))
                       * (1.0 - 0.95 * smoothstep(0.65, 1.0, local_time));
        vec2 drift = vec2(cos(angle), sin(angle)) * radius * 0.45 * flight * scale;
        vec2 delta = pixel - (origin + (center - origin) * scale + drift);
        if (dot(delta, delta) > radius * radius * shrink * shrink) continue;
        float spin = radians(@HEX_SPIN@) * (random * 2.0 - 1.0) * flight;
        float c = cos(spin), s = sin(spin);
        vec2 local = mat2(c, -s, s, c) * delta / shrink;
        vec2 a = abs(local);
        float edge = radius * 0.86602540378 - max(a.x, dot(a, vec2(0.5, 0.86602540378)));
        if (edge < 0.0) continue;
        float coverage = mix(1.0, smoothstep(0.0, 0.8, edge * shrink), smoothstep(0.0, 0.08, p));
        vec4 color = hex_texture((center + local) / size) * coverage * (1.0 - smoothstep(0.65, 1.0, local_time));
        result = color + result * (1.0 - color.a);
      }
    }
    return result;
}
