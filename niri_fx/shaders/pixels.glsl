// SPDX-License-Identifier: MIT
// Original NiriFX grid wipe, progressive pixelation and bounded drifting dust.
@NOISE@
// Cell order is seeded once per animation. Opening retraces the same field
// backwards; no particles or random values are advanced frame by frame.
float pixel_order(vec2 cell, vec2 uv, vec2 size) {
    vec2 origin = vec2(@PIXEL_X@, @PIXEL_Y@);
    float radius = max(length(max(origin, 1.0 - origin) * size), 1.0);
    float order = length((uv - origin) * size) / radius;
    if (@PIXEL_DIRECTION@ == 1) order = 1.0 - order;
    if (@PIXEL_DIRECTION@ == 2) order = uv.x;
    if (@PIXEL_DIRECTION@ == 3) order = 1.0 - uv.x;
    if (@PIXEL_DIRECTION@ == 4) order = uv.y;
    if (@PIXEL_DIRECTION@ == 5) order = 1.0 - uv.y;
    if (@PIXEL_MODE@ == 1) order = length((uv - origin) * size) / radius;
    return mix(clamp(order, 0.0, 1.0), fx_hash(cell), @PIXEL_RANDOMNESS@);
}
vec4 pixel_texture(vec2 uv) {
    if (any(lessThan(uv, vec2(0.0))) || any(greaterThanEqual(uv, vec2(1.0)))) return vec4(0.0);
    return texture2D(niri_tex, (niri_geo_to_tex * vec3(uv, 1.0)).xy);
}
vec4 @ENTRY@(vec3 coords_geo, vec3 size_geo) {
    float p = @PROGRESS@;
    if (p <= 0.0) return pixel_texture(coords_geo.xy);
    if (p >= 1.0) return vec4(0.0);
    vec2 size = max(size_geo.xy, vec2(1.0)), px = coords_geo.xy * size;
    float tile = @PIXEL_SIZE@;
    if (@PIXEL_MODE@ != 2) {
        if (any(lessThan(coords_geo.xy, vec2(0.0))) || any(greaterThanEqual(coords_geo.xy, vec2(1.0)))) return vec4(0.0);
        // Keep the release grid fixed while sample blocks grow. Otherwise a
        // changing cell identity would cause pieces to flicker between orders.
        vec2 cell = floor(px / tile), center = clamp((cell + 0.5) * tile, vec2(0.5), size - 0.5);
        float order = pixel_order(cell, center / size, size);
        float local = clamp((p - 0.65 * order) / 0.35, 0.0, 1.0);
        float grain = @PIXEL_MODE@ == 1 ? mix(1.0, tile, smoothstep(0.0, 0.55, p)) : tile;
        vec2 snapped = clamp((floor(px / grain) + 0.5) * grain, vec2(0.5), size - 0.5);
        float quantize = @PIXEL_MODE@ == 1 ? smoothstep(0.0, 0.12, p) : smoothstep(-0.25, 0.2, local) * smoothstep(0.0, 0.12, p);
        vec4 color = mix(pixel_texture(coords_geo.xy), pixel_texture(snapped / size), quantize);
        float mask = 1.0 - smoothstep(0.5 - @PIXEL_SOFTNESS@, 0.5 + @PIXEL_SOFTNESS@, local);
        return color * mask;
    }
    vec2 wind = vec2(1.0, 0.0);
    if (@PIXEL_WIND@ == 1) wind = vec2(-1.0, 0.0);
    if (@PIXEL_WIND@ == 2) wind = vec2(0.0, -1.0);
    if (@PIXEL_WIND@ == 3) wind = vec2(0.0, 1.0);
    // Work in a cardinal wind basis. All four directions then share one bounded
    // inverse lookup; travel is measured in cells rather than screen pixels.
    vec2 side = vec2(-wind.y, wind.x);
    vec2 dest = vec2(dot(px, wind), dot(px, side)), near_cell = floor(dest / tile);
    vec4 result = vec4(0.0);
    // Travel is at most eight cells along wind and less than one sideways.
    // 33 candidates suffice regardless of window dimensions or grain count.
    for (int x = -9; x <= 1; x++) {
        for (int y = -1; y <= 1; y++) {
            vec2 cell = near_cell + vec2(float(x), float(y));
            vec2 center = (cell + 0.5) * tile;
            vec2 source_center = wind * center.x + side * center.y;
            float order = pixel_order(cell, clamp(source_center / size, 0.0, 1.0), size);
            float local = clamp((p - 0.65 * order) / 0.35, 0.0, 1.0);
            // A positive scale floor keeps the inverse transform finite. Each
            // candidate is clipped in source space before texture sampling.
            float shrink = 1.0 - 0.92 * local;
            vec2 drift = tile * vec2(@PIXEL_TRAVEL@ * local * local,
                sin(fx_hash(cell + 4.7) * 6.2831853 + local * 4.0) * local * 0.75);
            vec2 delta = (dest - center - drift) / shrink;
            if (max(abs(delta.x), abs(delta.y)) >= tile * 0.5) continue;
            vec2 source_px = source_center + wind * delta.x + side * delta.y;
            if (any(lessThan(source_px, vec2(0.0))) || any(greaterThanEqual(source_px, size))) continue;
            vec2 sampled = mix(source_px, clamp(source_center, vec2(0.5), size - 0.5), smoothstep(0.0, 0.18, local));
            vec4 color = pixel_texture(sampled / size);
            color *= 1.0 - smoothstep(0.5 - @PIXEL_SOFTNESS@, 1.0, local);
            // Premultiplied source-over composes overlapping grains. This is a
            // deterministic per-window order, not cross-window particle depth.
            result = color + result * (1.0 - color.a);
        }
    }
    return result;
}
