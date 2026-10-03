// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Julien Turbide
// Original shader for Niri's open_color / close_color interface.
// Generated constants are logical pixels, independent of output scale.
const float FRAGMENTS_TILE = @TILE@;
const float FRAGMENTS_SCATTER = @SCATTER@;

vec2 fragments_hash(vec2 cell) {
    vec2 seed = cell + vec2(niri_random_seed * 71.0, niri_random_seed * 113.0);
    return fract(sin(vec2(dot(seed, vec2(127.1, 311.7)),
                          dot(seed, vec2(269.5, 183.3)))) * 43758.5453);
}

vec4 fragments_sample(vec2 geo) {
    vec2 uv = (niri_geo_to_tex * vec3(geo, 1.0)).xy;
    if (any(lessThan(uv, vec2(0.0))) || any(greaterThanEqual(uv, vec2(1.0))))
        return vec4(0.0);
    return texture2D(niri_tex, uv);
}

vec4 fragments_color(vec3 coords_geo, vec3 size_geo, float breakup) {
    // Exact endpoints: preserve the original texture (including CSD shadows)
    // at rest, and leave no remnants when the animation finishes.
    if (breakup <= 0.0) return fragments_sample(coords_geo.xy);
    if (breakup >= 1.0) return vec4(0.0);

    vec2 size = max(size_geo.xy, vec2(1.0));
    vec2 center = size * 0.5;
    vec2 pixel = coords_geo.xy * size;
    float travel = breakup * breakup * (3.0 - 2.0 * breakup);
    float expansion = 1.0 + 2.0 * FRAGMENTS_SCATTER * travel / max(size.x, size.y);
    vec2 source_guess = (pixel - center) / expansion + center;
    vec2 count = ceil(size / FRAGMENTS_TILE);
    // Center the grid so clipped edge tiles are symmetric. Even a window
    // smaller than one tile then has a fragment centered on the window.
    vec2 grid_origin = (size - count * FRAGMENTS_TILE) * 0.5;
    vec2 candidate = floor((source_guess - grid_origin) / FRAGMENTS_TILE);
    vec2 first = grid_origin + vec2(FRAGMENTS_TILE * 0.5);
    vec2 last = grid_origin + (count - 0.5) * FRAGMENTS_TILE;
    vec2 padding = vec2(FRAGMENTS_TILE * 0.74);
    vec2 lower = center + (first - center) * expansion - padding;
    vec2 upper = center + (last - center) * expansion + padding;
    if (any(lessThan(pixel, lower)) || any(greaterThan(pixel, upper)))
        return vec4(0.0);
    vec4 result = vec4(0.0);

    // A uniform radial expansion has an analytic inverse. Jitter is bounded
    // to 0.24 of a tile per axis, so a 3x3 source neighborhood covers every
    // possible contributor, regardless of window size or scatter distance.
    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            vec2 cell = candidate + vec2(float(x), float(y));
            if (any(lessThan(cell, vec2(0.0))) || any(greaterThanEqual(cell, count)))
                continue;
            vec2 random = fragments_hash(cell);
            float delay = random.x * 0.16;
            float local_time = clamp((breakup - delay) / (1.0 - delay), 0.0, 1.0);
            float shrink = 1.0 - 0.82 * smoothstep(0.0, 1.0, local_time);
            float opacity = 1.0 - smoothstep(0.20, 1.0, local_time);
            vec2 source_center = grid_origin + (cell + 0.5) * FRAGMENTS_TILE;
            vec2 jitter = (random - 0.5) * (FRAGMENTS_TILE * 0.48) * travel;
            vec2 destination = center + (source_center - center) * expansion + jitter;
            vec2 local = (pixel - destination) / shrink;
            vec2 source = source_center + local;

            // Half-open intervals avoid double drawing shared cell edges.
            float half_tile = FRAGMENTS_TILE * 0.5;
            if (any(lessThan(local, vec2(-half_tile))) || any(greaterThanEqual(local, vec2(half_tile))))
                continue;
            if (any(lessThan(source, vec2(0.0))) || any(greaterThanEqual(source, size)))
                continue;

            // Niri textures use premultiplied alpha: fade RGB and alpha together.
            vec4 fragment = fragments_sample(source / size) * opacity;
            result = fragment + result * (1.0 - fragment.a);
        }
    }
    return result;
}

@ACTION_ENTRY@
