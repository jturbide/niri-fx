// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Julien Turbide
// Analytic fragment field: reversible directional acceleration, attraction,
// radial drift and orbit, with independent per-fragment orientation.
const float FRAGMENTS_TILE = @TILE@;
const float FRAGMENTS_SCATTER = @SCATTER@;
const float FRAGMENTS_PARTICLES = @PARTICLES@;
const int FRAGMENTS_GRAVITY = @GRAVITY@;
const float FRAGMENTS_STRENGTH = @STRENGTH@;
const int FRAGMENTS_ROTATION = @ROTATION@;
const float FRAGMENTS_SPIN = @SPIN@;
const float FRAGMENTS_SWIRL = @SWIRL@;
const float FRAGMENTS_PI = 3.14159265359;

vec2 fragments_hash(vec2 cell) {
    vec2 seed = cell + vec2(niri_random_seed * 71.0, niri_random_seed * 113.0);
    return fract(sin(vec2(dot(seed, vec2(127.1, 311.7)),
                          dot(seed, vec2(269.5, 183.3)))) * 43758.5453);
}

mat2 fragments_turn(float angle) {
    float c = cos(angle), s = sin(angle);
    return mat2(c, s, -s, c);
}

vec4 fragments_sample(vec2 geo) {
    vec2 uv = (niri_geo_to_tex * vec3(geo, 1.0)).xy;
    if (any(lessThan(uv, vec2(0.0))) || any(greaterThanEqual(uv, vec2(1.0))))
        return vec4(0.0);
    return texture2D(niri_tex, uv);
}

vec4 fragments_color(vec3 coords_geo, vec3 size_geo, float breakup) {
    if (breakup <= 0.0) return fragments_sample(coords_geo.xy);
    if (breakup >= 1.0) return vec4(0.0);
    vec2 size = max(size_geo.xy, vec2(1.0));
    vec2 center = size * 0.5;
    vec2 pixel = coords_geo.xy * size;
    // Target count is approximate because tiles remain square at every aspect
    // ratio; a 4-logical-pixel floor bounds density on very small windows.
    float tile = FRAGMENTS_TILE;
    if (FRAGMENTS_PARTICLES > 0.0)
        tile = max(4.0, sqrt(size.x * size.y / FRAGMENTS_PARTICLES));
    float travel = breakup * breakup * (3.0 - 2.0 * breakup);
    float scale = 1.0 + 2.0 * FRAGMENTS_SCATTER * travel / max(size.x, size.y);
    vec2 direction = vec2(0.0);
    if (FRAGMENTS_GRAVITY == 1) direction = vec2(0.0, 1.0);
    if (FRAGMENTS_GRAVITY == 2) direction = vec2(0.0, -1.0);
    if (FRAGMENTS_GRAVITY == 3) direction = vec2(-1.0, 0.0);
    if (FRAGMENTS_GRAVITY == 4) direction = vec2(1.0, 0.0);
    // Directional displacement accelerates over time, in logical pixels.
    vec2 drift = direction * 220.0 * FRAGMENTS_STRENGTH * breakup * breakup;
    if (FRAGMENTS_GRAVITY == 5)
        scale *= max(0.06, exp(-2.6 * FRAGMENTS_STRENGTH * travel));
    if (FRAGMENTS_GRAVITY == 6)
        scale += 2.0 * 180.0 * FRAGMENTS_STRENGTH * breakup / max(size.x, size.y);
    float orbit = FRAGMENTS_SWIRL * (FRAGMENTS_PI / 180.0) * travel;
    mat2 field = fragments_turn(orbit);
    mat2 inverse_field = fragments_turn(-orbit);
    vec2 field_center = center + drift;
    vec2 count = ceil(size / tile);
    vec2 grid_origin = (size - count * tile) * 0.5;
    vec2 source_guess = center + inverse_field * (pixel - field_center) / scale;
    vec2 candidate = floor((source_guess - grid_origin) / tile);
    // Collapse fragments with the field so attraction never requires searching
    // hundreds of overlapping cells at a singularity. The inverse stays finite.
    float field_shrink = min(1.0, scale);
    vec2 span = (count - 1.0) * tile * 0.5 * scale;
    float c = abs(cos(orbit)), s = abs(sin(orbit));
    vec2 extent = vec2(c * span.x + s * span.y, s * span.x + c * span.y)
                  + vec2(tile * field_shrink * 0.95);
    if (any(greaterThan(abs(pixel - field_center), extent))) return vec4(0.0);

    vec4 result = vec4(0.0);
    // Rotated half-diagonal <= 0.708 tiles, inverse-rotated jitter <= 0.340.
    // Total < 1.5 tiles: every contributor is in this 3x3 source neighborhood.
    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            vec2 cell = candidate + vec2(float(x), float(y));
            if (any(lessThan(cell, vec2(0.0))) || any(greaterThanEqual(cell, count))) continue;
            vec2 random = fragments_hash(cell);
            float delay = random.x * 0.16;
            float local_time = clamp((breakup - delay) / (1.0 - delay), 0.0, 1.0);
            float shrink = field_shrink * (1.0 - 0.82 * smoothstep(0.0, 1.0, local_time));
            float opacity = 1.0 - smoothstep(0.35, 1.0, local_time);
            vec2 source_center = grid_origin + (cell + 0.5) * tile;
            vec2 destination = field_center + field * ((source_center - center) * scale);
            vec2 motion = destination - source_center;
            vec2 jitter = (random - 0.5) * tile * 0.48 * travel * field_shrink;
            float angle = 0.0;
            if (FRAGMENTS_ROTATION == 1)
                angle = (random.y * 2.0 - 1.0) * FRAGMENTS_SPIN * (FRAGMENTS_PI / 180.0) * travel;
            if (FRAGMENTS_ROTATION == 2 && dot(motion, motion) > 0.0001) {
                // Turn the fragment's top toward its net travel direction.
                float heading = atan(motion.y, motion.x) + FRAGMENTS_PI * 0.5;
                heading = mod(heading + FRAGMENTS_PI, 2.0 * FRAGMENTS_PI) - FRAGMENTS_PI;
                float limit = FRAGMENTS_SPIN * (FRAGMENTS_PI / 180.0);
                angle = clamp(heading, -limit, limit) * travel;
            }
            vec2 local = fragments_turn(-angle) * (pixel - destination - jitter) / shrink;
            vec2 source = source_center + local;
            if (any(lessThan(local, vec2(-tile * 0.5))) || any(greaterThanEqual(local, vec2(tile * 0.5)))) continue;
            if (any(lessThan(source, vec2(0.0))) || any(greaterThanEqual(source, size))) continue;
            vec4 fragment = fragments_sample(source / size) * opacity;
            result = fragment + result * (1.0 - fragment.a);
        }
    }
    return result;
}

vec4 @ENTRY@(vec3 coords_geo, vec3 size_geo) {
    return fragments_color(coords_geo, size_geo, @PROGRESS@);
}
