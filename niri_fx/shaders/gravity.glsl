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
const float FRAGMENTS_DISPERSION = @DISPERSION@;
const float FRAGMENTS_STAGGER = @STAGGER@;
const int FRAGMENTS_RELEASE = @RELEASE@;
const float FRAGMENTS_WAVE_SPAN = @WAVE_SPAN@;
const vec2 FRAGMENTS_ORIGIN = vec2(@ORIGIN_X@, @ORIGIN_Y@);
const float FX_SHRINK = @FRAGMENT_SHRINK@;
const float FX_ROUNDNESS = @FRAGMENT_ROUNDNESS@;
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

int fragments_phase_index(vec2 geo) {
    if (FRAGMENTS_RELEASE == 0) return 0;
    float axis = geo.x;
    if (FRAGMENTS_RELEASE == 2) axis = 1.0 - geo.x;
    if (FRAGMENTS_RELEASE == 3) axis = geo.y;
    if (FRAGMENTS_RELEASE == 4) axis = 1.0 - geo.y;
    if (FRAGMENTS_RELEASE == 5 || FRAGMENTS_RELEASE == 6) {
        vec2 radius = max(FRAGMENTS_ORIGIN, vec2(1.0) - FRAGMENTS_ORIGIN);
        axis = length((geo - FRAGMENTS_ORIGIN) / radius) / sqrt(2.0);
        if (FRAGMENTS_RELEASE == 6) axis = 1.0 - axis;
    }
    if (FRAGMENTS_RELEASE == 7) axis = (geo.x + geo.y) * 0.5;
    if (FRAGMENTS_RELEASE == 8)
        return int(mod(floor(geo.x * 6.0) + floor(geo.y * 6.0), 2.0)) * 2;
    return int(clamp(floor(axis * 3.0), 0.0, 2.0));
}

vec4 fragments_phase(vec3 coords_geo, vec3 size_geo, float breakup, int phase) {
    if (breakup >= 1.0) return vec4(0.0);
    vec2 size = max(size_geo.xy, vec2(1.0));
    vec2 center = size * FRAGMENTS_ORIGIN;
    vec2 pixel = coords_geo.xy * size;
    // Target count is approximate because tiles remain square at every aspect
    // ratio; a 4-logical-pixel floor bounds density on very small windows.
    float tile = FRAGMENTS_TILE;
    if (FRAGMENTS_PARTICLES > 0.0)
        tile = max(4.0, sqrt(size.x * size.y / FRAGMENTS_PARTICLES));
    float travel = breakup * breakup * (3.0 - 2.0 * breakup);
    vec2 direction = vec2(0.0);
    if (FRAGMENTS_GRAVITY == 1) direction = vec2(0.0, 1.0);
    if (FRAGMENTS_GRAVITY == 2) direction = vec2(0.0, -1.0);
    if (FRAGMENTS_GRAVITY == 3) direction = vec2(-1.0, 0.0);
    if (FRAGMENTS_GRAVITY == 4) direction = vec2(1.0, 0.0);
    vec2 count = ceil(size / tile);
    vec2 grid_origin = (size - count * tile) * 0.5;
    if (breakup <= 0.0) {
        vec2 source_center = grid_origin + (floor((pixel - grid_origin) / tile) + 0.5) * tile;
        return fragments_phase_index(source_center / size) == phase ? fragments_sample(coords_geo.xy) : vec4(0.0);
    }
    vec4 result = vec4(0.0);
    // Three interleaved velocity bands break up the expanding-sheet look.
    // Each piece belongs to one band, with its own invertible flight field.
    for (int band = 0; band < 3; band++) {
        float speed = 1.0 + (float(band) - 1.0) * 0.48 * FRAGMENTS_DISPERSION;
        float scale = 1.0 + 2.0 * FRAGMENTS_SCATTER * travel * speed / max(size.x, size.y);
        vec2 drift = direction * 220.0 * FRAGMENTS_STRENGTH * breakup * breakup * speed;
        if (FRAGMENTS_GRAVITY == 5)
            scale *= max(0.06, exp(-2.8 * FRAGMENTS_STRENGTH * breakup * breakup * speed));
        if (FRAGMENTS_GRAVITY == 6)
            scale += 2.0 * 180.0 * FRAGMENTS_STRENGTH * breakup * speed / max(size.x, size.y);
        float orbit = FRAGMENTS_SWIRL * (FRAGMENTS_PI / 180.0) * travel * speed;
        mat2 field = fragments_turn(orbit);
        mat2 inverse_field = fragments_turn(-orbit);
        vec2 field_center = center + drift;
        vec2 source_guess = center + inverse_field * (pixel - field_center) / scale;
        vec2 candidate = floor((source_guess - grid_origin) / tile);
        // Scale pieces with inward fields to bound overlap at the attractor.
        float field_shrink = min(1.0, scale);
        vec2 span = (count - 1.0) * tile * 0.5 * scale;
        float c = abs(cos(orbit)), s = abs(sin(orbit));
        vec2 extent = vec2(c * span.x + s * span.y, s * span.x + c * span.y)
                    + vec2(tile * (0.72 * FRAGMENTS_DISPERSION * scale + 0.71 * field_shrink));
        vec2 bounds_center = field_center + field * ((size * 0.5 - center) * scale);
        if (any(greaterThan(abs(pixel - bounds_center), extent))) continue;
        // Inverse wander <= .72 tiles, half-diagonal <= .708. Total < 1.5:
        // a 3x3 neighborhood per band covers all contributors (27 candidates).
        for (int y = -1; y <= 1; y++) {
          for (int x = -1; x <= 1; x++) {
            vec2 cell = candidate + vec2(float(x), float(y));
            if (any(lessThan(cell, vec2(0.0))) || any(greaterThanEqual(cell, count))) continue;
            vec2 source_center = grid_origin + (cell + 0.5) * tile;
            if (fragments_phase_index(source_center / size) != phase) continue;
            vec2 random = fragments_hash(cell);
            if (int(floor(random.x * 3.0)) != band) continue;
            float wave = dot(source_center / size - 0.5, direction) + 0.5;
            float delay = FRAGMENTS_STAGGER * (0.65 * random.x + 0.35 * wave);
            float local_time = clamp((breakup - delay) / (1.0 - delay), 0.0, 1.0);
            float release = smoothstep(0.0, 0.72, local_time);
            // Keep recognizable pieces through the middle of the flight, then
            // dissolve. Opening runs the same trajectory backwards to a seal.
            float shrink = field_shrink * (1.0 - 0.28 * release)
                           * (1.0 - 0.92 * smoothstep(0.58, 1.0, local_time));
            shrink *= 1.0 - 0.85 * FX_SHRINK * release;
            float opacity = 1.0 - smoothstep(0.62, 1.0, local_time);
            vec2 destination = field_center + field * ((source_center - center) * scale);
            float wander_angle = random.y * 2.0 * FRAGMENTS_PI
                               + (random.x - 0.5) * 2.0 * sin(local_time * FRAGMENTS_PI);
            vec2 wander = vec2(cos(wander_angle), sin(wander_angle))
                        * sqrt(fract(random.x * 3.0)) * 0.72 * FRAGMENTS_DISPERSION * tile * release * scale;
            destination += field * wander;
            vec2 motion = destination - source_center;
            vec2 relative = pixel - destination;
            // Cheap circular rejection before trigonometry and texture reads.
            if (dot(relative, relative) > 0.501 * tile * tile * shrink * shrink) continue;
            float angle = 0.0;
            if (FRAGMENTS_ROTATION == 1)
                angle = (random.y * 2.0 - 1.0) * FRAGMENTS_SPIN * (FRAGMENTS_PI / 180.0)
                      * (0.3 * local_time + 0.7 * local_time * local_time);
            if (FRAGMENTS_ROTATION == 2 && dot(motion, motion) > 0.0001) {
                // Turn the fragment's top toward its net travel direction.
                float heading = atan(motion.y, motion.x) + FRAGMENTS_PI * 0.5;
                heading = mod(heading + FRAGMENTS_PI, 2.0 * FRAGMENTS_PI) - FRAGMENTS_PI;
                float limit = FRAGMENTS_SPIN * (FRAGMENTS_PI / 180.0);
                angle = clamp(heading, -limit, limit) * release;
            }
            vec2 local = fragments_turn(-angle) * relative / shrink;
            vec2 source = source_center + local;
            if (any(lessThan(local, vec2(-tile * 0.5))) || any(greaterThanEqual(local, vec2(tile * 0.5)))) continue;
            if (any(lessThan(source, vec2(0.0))) || any(greaterThanEqual(source, size))) continue;
            vec2 edge = min(vec2(tile * 0.5) - abs(local), min(source, size - source));
            float coverage = mix(1.0, smoothstep(0.0, 0.85, min(edge.x, edge.y) * shrink),
                                 smoothstep(0.0, 0.12, breakup));
            // Rounded corners emerge after release; no gaps at the intact endpoint.
            vec2 shape_half = vec2(tile * 0.5);
            float radius = min(shape_half.x, shape_half.y) * FX_ROUNDNESS
                         * smoothstep(0.0, 0.28, local_time);
            if (radius > 0.0) {
                vec2 corner = abs(local) - shape_half + radius;
                float inside = radius - length(max(corner, vec2(0.0)))
                             - min(max(corner.x, corner.y), 0.0);
                coverage *= smoothstep(0.0, 0.85, inside * shrink);
            }
            vec4 fragment = fragments_sample(source / size) * (opacity * coverage);
            result = fragment + result * (1.0 - fragment.a);
          }
        }
    }
    return result;
}

vec4 fragments_color(vec3 coords_geo, vec3 size_geo, float breakup) {
    if (breakup <= 0.0) return fragments_sample(coords_geo.xy);
    if (breakup >= 1.0) return vec4(0.0);
    if (FRAGMENTS_RELEASE == 0) return fragments_phase(coords_geo, size_geo, breakup, 0);
    vec4 result = vec4(0.0);
    // Three staggered source groups retain invertible fields and bounded lookup.
    // Together mode still uses one field (27 candidates); waves use up to 81.
    for (int phase = 0; phase < 3; phase++) {
        float delay = float(phase) * 0.5 * FRAGMENTS_WAVE_SPAN;
        float p = clamp((breakup - delay) / (1.0 - FRAGMENTS_WAVE_SPAN), 0.0, 1.0);
        vec4 layer = fragments_phase(coords_geo, size_geo, p, phase);
        result = layer + result * (1.0 - layer.a);
    }
    return result;
}

@ACTION_ENTRY@
