// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Julien Turbide
// Shaped fragments reuse the reversible flight field with disjoint rectangular,
// triangular or hexagonal ownership. Existing square presets keep their compact paths.
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
const float FX_SHRINK = @FRAGMENT_SHRINK@;
const float FX_ROUNDNESS = @FRAGMENT_ROUNDNESS@;
const float FRAGMENTS_PI = 3.14159265359;

// Integer-valued arithmetic stays below 2^24, where highp floats represent
// every integer exactly. Power-of-two reduction avoids transcendental hash
// changes when drivers unroll different cell neighborhoods. Quantize the seed
// once; each source cell and triangle part keeps its identity throughout flight.
vec2 fragments_hash(vec2 cell) {
    vec2 key = mod(floor(cell), 4096.0);
    float seed = floor(clamp(niri_random_seed, 0.0, 1.0) * 65535.0);
    float part = floor(fract(cell.x) * 16.0);
    float x = mod(dot(key, vec2(127.0, 311.0)) + mod(seed, 4096.0) * 17.0 + part * 199.0, 4096.0);
    float y = mod(dot(key, vec2(269.0, 183.0)) + floor(seed / 4096.0) * 257.0 + part * 137.0, 4096.0);
    for (int i = 0; i < 3; i++) {
        x = mod(x * x + y, 4096.0);
        y = mod(y * 109.0 + x * 241.0 + 17.0, 4096.0);
    }
    return (vec2(x, y) + 0.5) / 4096.0;
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

@FRAGMENT_SHAPES@

vec4 fragments_phase(vec3 coords_geo, vec3 size_geo, float breakup, int phase) {
    if (breakup >= 1.0) return vec4(0.0);
    vec2 size = max(size_geo.xy, vec2(1.0));
    vec2 center = size * FRAGMENTS_ORIGIN, pixel = coords_geo.xy * size;
    // One rectangle has area tile²; a triangle occupies half a cell and a
    // regular hexagon has area 3sqrt(3)/2 * radius². Preserve target density.
    float tile = FRAGMENTS_PARTICLES > 0.0
        ? max(4.0, sqrt(size.x * size.y / FRAGMENTS_PARTICLES)) : FRAGMENTS_TILE;
    tile *= shaped_density();
    vec2 stretch = shaped_stretch();
    float orientation = radians(FX_ORIENTATION);
    mat2 layout = fragments_turn(orientation), inverse_layout = fragments_turn(-orientation);
    float radius = shaped_radius(stretch);
    radius *= tile;
    float metric = tile * min(stretch.x, stretch.y);
    float travel = breakup * breakup * (3.0 - 2.0 * breakup);
    vec2 direction = vec2(0.0);
    if (FRAGMENTS_GRAVITY == 1) direction = vec2(0.0, 1.0);
    if (FRAGMENTS_GRAVITY == 2) direction = vec2(0.0, -1.0);
    if (FRAGMENTS_GRAVITY == 3) direction = vec2(-1.0, 0.0);
    if (FRAGMENTS_GRAVITY == 4) direction = vec2(1.0, 0.0);
    vec4 result = vec4(0.0);
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
        float orbit = radians(FRAGMENTS_SWIRL) * travel * speed + bias * travel;
        mat2 field = fragments_turn(orbit), inverse_field = fragments_turn(-orbit);
        vec2 field_center = center + drift;
        float field_shrink = min(1.0, scale);
        float wave_extent = FX_WAVE * size.y * 0.45 / (2.0 * FRAGMENTS_PI * FX_FREQUENCY)
                          * abs(sin(FRAGMENTS_PI * breakup));
        // Border cells can have their centroid outside the window. Include a
        // complete source-piece radius before rotating the band's envelope.
        vec2 span = size * 0.5 + radius;
        span.x += wave_extent;
        span *= scale;
        float c = abs(cos(orbit)), s = abs(sin(orbit));
        vec2 extent = vec2(c * span.x + s * span.y, s * span.x + c * span.y)
                    + vec2(tile * 0.72 * FRAGMENTS_DISPERSION * scale + radius * field_shrink);
        vec2 bounds_center = field_center + field * ((size * 0.5 - center) * scale);
        if (any(greaterThan(abs(pixel - bounds_center), extent))) continue;
        vec2 source_guess = center + inverse_field * (pixel - field_center) / scale;
        source_guess.x -= fragments_wave(source_guess.y, size.y, breakup);
        vec2 grid_guess = (inverse_layout * (source_guess - size * 0.5)) / (tile * stretch);
        vec2 candidate = floor(FX_SHAPE == 5 && FX_MIX == 0.0 ? shaped_axial(grid_guess) : grid_guess);
        // In inverse-field space a rotated piece plus wander is within this
        // circle. Undoing the wave expands distances by at most 1 + .45*FX_WAVE.
        // Reject impossible cells before seeded hashes, phase and flight math.
        float lookup_reach = (radius + 0.72 * FRAGMENTS_DISPERSION * tile) * (1.0 + 0.45 * FX_WAVE);
        // Export-time bounds include maximum rotated radius, aspect, wander,
        // inverse-wave error and centroid offset (see shape_search_radius).
        // Loop count is independent of window area and target particle count.
        for (int y = -@SHAPED_RADIUS@; y <= @SHAPED_RADIUS@; y++) {
          for (int x = -@SHAPED_RADIUS@; x <= @SHAPED_RADIUS@; x++) {
            vec2 cell = candidate + vec2(float(x), float(y));
            for (int part = 0; part < @SHAPED_PARTS@; part++) {
                if (part > 0 && shaped_kind(cell) != 2) continue;
                vec2 lattice_center = shaped_center(cell, part);
                vec2 source_center = size * 0.5 + layout * (lattice_center * tile * stretch);
                if (any(lessThan(source_center + radius, vec2(0.0)))
                    || any(greaterThan(source_center - radius, size))) continue;
                vec2 lookup_delta = source_guess - source_center;
                if (dot(lookup_delta, lookup_delta) > lookup_reach * lookup_reach) continue;
                // Each triangle has its own stable identity, speed band and spin.
                vec2 random = fragments_hash(cell + vec2(float(part) * 0.371, float(part) * 0.619));
                if (int(floor(random.x * 3.0)) != band) continue;
                if (fragments_phase_index(source_center / size) != phase) continue;
                float wave = clamp(dot(source_center / size - 0.5, direction) + 0.5, 0.0, 1.0);
                float delay = FRAGMENTS_STAGGER * (0.65 * random.x + 0.35 * wave);
                float local_time = clamp((breakup - delay) / (1.0 - delay), 0.0, 1.0);
                float release = smoothstep(0.0, 0.72, local_time);
                float shrink = field_shrink * (1.0 - 0.28 * release)
                               * (1.0 - 0.92 * smoothstep(0.58, 1.0, local_time));
                shrink *= (1.0 - 0.85 * FX_SHRINK * release)
                        * (1.0 - 0.65 * FX_SIZE * random.y * release);
                float opacity = 1.0 - smoothstep(0.62, 1.0, local_time);
                vec2 waved_center = source_center + vec2(fragments_wave(source_center.y, size.y, breakup), 0.0);
                vec2 destination = field_center + field * ((waved_center - center) * scale);
                float wander_angle = random.y * 2.0 * FRAGMENTS_PI
                                   + (random.x - 0.5) * 2.0 * sin(local_time * FRAGMENTS_PI);
                vec2 wander = vec2(cos(wander_angle), sin(wander_angle))
                            * sqrt(fract(random.x * 3.0)) * 0.72 * FRAGMENTS_DISPERSION * tile * release * scale;
                destination += field * wander;
                vec2 motion = destination - source_center, relative = pixel - destination;
                if (dot(relative, relative) > radius * radius * shrink * shrink) continue;
                float angle = 0.0;
                if (FRAGMENTS_ROTATION == 1)
                    angle = (random.y * 2.0 - 1.0) * radians(FRAGMENTS_SPIN)
                          * (0.3 * local_time + 0.7 * local_time * local_time);
                if (FRAGMENTS_ROTATION == 2 && dot(motion, motion) > 0.0001) {
                    float heading = atan(motion.y, motion.x) + FRAGMENTS_PI * 0.5 - orientation;
                    heading = mod(heading + FRAGMENTS_PI, 2.0 * FRAGMENTS_PI) - FRAGMENTS_PI;
                    angle = clamp(heading, -radians(FRAGMENTS_SPIN), radians(FRAGMENTS_SPIN)) * release;
                }
                vec2 local = inverse_layout * (fragments_turn(-angle) * relative) / (shrink * tile * stretch);
                if (!shaped_owns(lattice_center + local, cell, part)) continue;
                vec2 source = source_center + layout * (local * tile * stretch);
                if (any(lessThan(source, vec2(0.0))) || any(greaterThanEqual(source, size))) continue;
                float edge = shaped_edge(local, cell, part, local_time) * metric;
                if (edge < -0.0001) continue;
                edge = min(edge, min(min(source.x, source.y), min(size.x - source.x, size.y - source.y)));
                float coverage = mix(1.0, smoothstep(0.0, 0.85, edge * shrink), smoothstep(0.0, 0.12, breakup));
                vec4 fragment = fragments_sample(source / size) * (opacity * coverage);
                result = fragment + result * (1.0 - fragment.a);
            }
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
    for (int phase = 0; phase < 3; phase++) {
        float delay = float(phase) * 0.5 * FRAGMENTS_WAVE_SPAN;
        float p = clamp((breakup - delay) / (1.0 - FRAGMENTS_WAVE_SPAN), 0.0, 1.0);
        vec4 layer = fragments_phase(coords_geo, size_geo, p, phase);
        result = layer + result * (1.0 - layer.a);
    }
    return result;
}

@ACTION_ENTRY@
