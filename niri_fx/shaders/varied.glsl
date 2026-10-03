// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Julien Turbide
// Variation renderer: shared jittered grid boundaries and an invertible wave
// field. Legacy presets continue using gravity.glsl without changes.
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
const float FX_SIZE = @SIZE_VARIATION@;
const float FX_DIRECTION = @DIRECTION_VARIATION@;
const float FX_WAVE = @WAVE_STRENGTH@;
const float FX_FREQUENCY = @WAVE_FREQUENCY@;
const float FX_SPEED = @WAVE_SPEED@;
const float FRAGMENTS_PI = 3.14159265359;

vec2 fragments_hash(vec2 cell) {
    vec2 seed = cell + vec2(niri_random_seed * 71.0, niri_random_seed * 113.0);
    return fract(sin(vec2(dot(seed, vec2(127.1, 311.7)),
                          dot(seed, vec2(269.5, 183.3)))) * 43758.5453);
}

// Each axis reuses the same boundary from both adjacent cells. Minimum width
// is .6 tiles; changing the seed never changes during a single animation.
vec2 fragments_boundary(vec2 cell) {
    return cell + (vec2(fragments_hash(vec2(cell.x, 17.0)).x,
                         fragments_hash(vec2(29.0, cell.y)).y) * 2.0 - 1.0) * 0.2 * FX_SIZE;
}
float fragments_wave(float y, float height, float progress) {
    // |d displacement / dy| <= .45: the inverse lookup remains bounded.
    float phase = 2.0 * FRAGMENTS_PI * (FX_FREQUENCY * y / height - FX_SPEED * progress);
    return FX_WAVE * height * 0.45 / (2.0 * FRAGMENTS_PI * FX_FREQUENCY)
           * sin(phase) * sin(FRAGMENTS_PI * progress);
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
    return int(clamp(floor(axis * 3.0), 0.0, 2.0));
}

vec4 fragments_phase(vec3 coords_geo, vec3 size_geo, float breakup, int phase) {
    if (breakup >= 1.0) return vec4(0.0);
    vec2 size = max(size_geo.xy, vec2(1.0));
    vec2 center = size * FRAGMENTS_ORIGIN;
    vec2 pixel = coords_geo.xy * size;
    // Target count uses a nominal square grid; jittered boundaries make rectangles.
    // A 4-logical-pixel floor bounds density on very small windows.
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
        float bias = (fragments_hash(vec2(float(band), 91.0)).y * 2.0 - 1.0) * FRAGMENTS_PI * FX_DIRECTION;
        drift = fragments_turn(bias) * drift;
        float orbit = FRAGMENTS_SWIRL * (FRAGMENTS_PI / 180.0) * travel * speed + bias * travel;
        mat2 field = fragments_turn(orbit);
        mat2 inverse_field = fragments_turn(-orbit);
        vec2 field_center = center + drift;
        vec2 source_guess = center + inverse_field * (pixel - field_center) / scale;
        source_guess.x -= fragments_wave(source_guess.y, size.y, breakup);
        vec2 candidate = floor((source_guess - grid_origin) / tile);
        // Scale pieces with inward fields to bound overlap at the attractor.
        float field_shrink = min(1.0, scale);
        // Inverse lookup: variable centers <= .2 tiles, half-diagonal <= .99,
        // wander <= .72, wave inverse error <= .45 * (.99 + .72).
        // Including the cell-center offset gives < 3.2, covered by offsets ±3.
        for (int y = -3; y <= 3; y++) {
          for (int x = -3; x <= 3; x++) {
            vec2 cell = candidate + vec2(float(x), float(y));
            if (any(lessThan(cell, vec2(0.0))) || any(greaterThanEqual(cell, count))) continue;
            vec2 low = fragments_boundary(cell), high = fragments_boundary(cell + 1.0);
            low = mix(low, vec2(0.0), vec2(1.0) - step(vec2(0.5), cell));
            high = mix(high, count, step(count - 0.5, cell + 1.0));
            vec2 source_center = grid_origin + (low + high) * 0.5 * tile;
            vec2 half_size = (high - low) * 0.5 * tile;
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
            float opacity = 1.0 - smoothstep(0.62, 1.0, local_time);
            vec2 waved_center = source_center + vec2(fragments_wave(source_center.y, size.y, breakup), 0.0);
            vec2 destination = field_center + field * ((waved_center - center) * scale);
            float wander_angle = random.y * 2.0 * FRAGMENTS_PI
                               + (random.x - 0.5) * 2.0 * sin(local_time * FRAGMENTS_PI);
            vec2 wander = vec2(cos(wander_angle), sin(wander_angle))
                        * sqrt(fract(random.x * 3.0)) * 0.72 * FRAGMENTS_DISPERSION * tile * release * scale;
            destination += field * wander;
            vec2 motion = destination - source_center;
            vec2 relative = pixel - destination;
            // Cheap circular rejection before trigonometry and texture reads.
            if (dot(relative, relative) > dot(half_size, half_size) * shrink * shrink) continue;
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
            if (any(lessThan(local, -half_size)) || any(greaterThanEqual(local, half_size))) continue;
            if (any(lessThan(source, vec2(0.0))) || any(greaterThanEqual(source, size))) continue;
            vec2 edge = min(half_size - abs(local), min(source, size - source));
            float coverage = mix(1.0, smoothstep(0.0, 0.85, min(edge.x, edge.y) * shrink),
                                 smoothstep(0.0, 0.12, breakup));
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
    // Three staggered source strips retain invertible fields and bounded lookup.
    // Together uses 147 candidates; three release phases use up to 441.
    for (int phase = 0; phase < 3; phase++) {
        float delay = float(phase) * 0.5 * FRAGMENTS_WAVE_SPAN;
        float p = clamp((breakup - delay) / (1.0 - FRAGMENTS_WAVE_SPAN), 0.0, 1.0);
        vec4 layer = fragments_phase(coords_geo, size_geo, p, phase);
        result = layer + result * (1.0 - layer.a);
    }
    return result;
}

vec4 @ENTRY@(vec3 coords_geo, vec3 size_geo) {
    return fragments_color(coords_geo, size_geo, @PROGRESS@);
}
