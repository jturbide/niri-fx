// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Julien Turbide
// Bounded fragmentation during resize. No per-frame simulation or random seed.
const float FR_TILE = @TILE@;
const float FR_COUNT = @PARTICLES@;
const float FR_STRENGTH = @RESIZE@;
const float FR_SPIN = @SPIN@;
const int FR_ROTATION = @ROTATION@;
const int FR_GRAVITY = @GRAVITY@;
const int FR_MODE = @RESIZE_MODE@;

vec2 fr_hash(vec2 cell) {
    return fract(sin(vec2(dot(cell, vec2(127.1, 311.7)),
                          dot(cell, vec2(269.5, 183.3)))) * 43758.5453);
}
mat2 fr_turn(float a) { float c = cos(a), s = sin(a); return mat2(c, s, -s, c); }
vec4 fr_sample(vec2 geo, float blend) {
    vec2 prev = (niri_geo_to_tex_prev * vec3(geo, 1.0)).xy;
    vec2 next = (niri_geo_to_tex_next * vec3(geo, 1.0)).xy;
    vec4 a = vec4(0.0), b = vec4(0.0);
    if (all(greaterThanEqual(prev, vec2(0.0))) && all(lessThan(prev, vec2(1.0))))
        a = texture2D(niri_tex_prev, prev);
    if (all(greaterThanEqual(next, vec2(0.0))) && all(lessThan(next, vec2(1.0))))
        b = texture2D(niri_tex_next, next);
    return mix(a, b, blend);
}
vec4 resize_color(vec3 coords_curr_geo, vec3 size_curr_geo) {
    float p = niri_clamped_progress;
    float blend = smoothstep(0.2, 0.8, p);
    // Exact endpoint samples also preserve client-side decoration shadows.
    if (p <= 0.0 || p >= 1.0 || FR_STRENGTH <= 0.0)
        return fr_sample(coords_curr_geo.xy, blend);
    float pulse = pow(sin(p * 3.14159265359), 2.0) * FR_STRENGTH;
    vec2 size = max(size_curr_geo.xy, vec2(1.0));
    vec2 pixel = coords_curr_geo.xy * size;
    if (any(lessThan(pixel, vec2(0.0))) || any(greaterThanEqual(pixel, size)))
        return fr_sample(coords_curr_geo.xy, blend) * (1.0 - pulse);
    // Use final geometry for a stable grid count while the current size changes.
    vec2 next_scale = vec2(niri_curr_geo_to_next_geo[0][0], niri_curr_geo_to_next_geo[1][1]);
    vec2 final_size = size / max(next_scale, vec2(0.0001));
    float tile = FR_COUNT > 0.0 ? max(4.0, sqrt(final_size.x * final_size.y / FR_COUNT)) : FR_TILE;
    vec2 count = ceil(final_size / tile);
    vec2 cell_size = size / count;
    vec2 candidate = floor(pixel / cell_size);
    vec4 result = vec4(0.0);
    // Displacement <= .4 cells plus half-diagonal <= .708: 3x3 covers rotation.
    for (int y = -1; y <= 1; y++) {
      for (int x = -1; x <= 1; x++) {
        vec2 cell = candidate + vec2(float(x), float(y));
        if (any(lessThan(cell, vec2(0.0))) || any(greaterThanEqual(cell, count))) continue;
        vec2 random = fr_hash(cell);
        vec2 center = (cell + 0.5) * cell_size;
        vec2 direction = vec2(cos(random.x * 6.2831853), sin(random.x * 6.2831853));
        if (FR_GRAVITY == 1) direction = vec2(0.0, 1.0);
        if (FR_GRAVITY == 2) direction = vec2(0.0, -1.0);
        if (FR_GRAVITY == 3) direction = vec2(-1.0, 0.0);
        if (FR_GRAVITY == 4) direction = vec2(1.0, 0.0);
        if (FR_GRAVITY >= 5) {
            vec2 radial = center / size - 0.5;
            direction = radial / max(length(radial), 0.001) * (FR_GRAVITY == 5 ? -1.0 : 1.0);
        }
        // Keep boundary cells inside the resize geometry; expanded bounds are
        // not guaranteed by stock Niri's resize interface.
        vec2 edge_cells = min(cell, count - 1.0 - cell);
        float edge_factor = smoothstep(0.0, 1.0, min(edge_cells.x, edge_cells.y));
        float local_pulse = pulse;
        if (FR_MODE == 1) {
            // Concentrate breakup near the outer bands of changing dimensions.
            // This leaves the central content intact while the boundary rebuilds.
            vec2 changing = step(vec2(0.0001), abs(next_scale - vec2(1.0)));
            vec2 edge_distance = abs(center / size - 0.5) * 2.0 * changing;
            local_pulse *= smoothstep(0.5, 0.95, max(edge_distance.x, edge_distance.y));
        }
        if (FR_MODE == 2) local_pulse *= 0.28;
        vec2 drift = direction * (0.2 + 0.2 * random.y) * local_pulse * edge_factor;
        float angle = (random.y * 2.0 - 1.0) * FR_SPIN * 0.01745329252 * 0.35;
        if (FR_ROTATION == 0) angle = 0.0;
        if (FR_ROTATION == 2)
            angle = dot(direction, direction) > 0.0001
                ? clamp(atan(direction.y, direction.x), -FR_SPIN * 0.01745329252, FR_SPIN * 0.01745329252) : 0.0;
        float shrink = 1.0 - 0.6 * local_pulse;
        vec2 local = fr_turn(-angle * local_pulse * edge_factor) * ((pixel - center) / cell_size - drift) / shrink;
        if (any(lessThan(local, vec2(-0.5))) || any(greaterThanEqual(local, vec2(0.5)))) continue;
        vec2 source = center + local * cell_size;
        vec2 edge = (0.5 - abs(local)) * cell_size * shrink;
        float coverage = mix(1.0, smoothstep(0.0, 0.8, min(edge.x, edge.y)), local_pulse);
        vec4 color = fr_sample(source / size, blend) * coverage;
        result = color + result * (1.0 - color.a);
      }
    }
    if (FR_MODE == 2) return mix(fr_sample(coords_curr_geo.xy, blend), result, 0.65);
    return result;
}
