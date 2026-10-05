// SPDX-License-Identifier: MIT
// Joined source geometry is fixed in the destination window's logical space.
// The current rectangle stretches that space during resize, without changing
// piece identities or repartitioning at every frame. Stock resize supplies two
// textures, but no pointer anchor or persistent per-piece simulation state.
@RESIZE_STATE@
const float FR_TILE = @TILE@;
const float FR_COUNT = @PARTICLES@;
const float FR_STRENGTH = @RESIZE@;
const float FR_SPIN = @SPIN@;
const int FR_ROTATION = @ROTATION@;
const int FR_GRAVITY = @GRAVITY@;
const int FR_MODE = @RESIZE_MODE@;
const float FX_ROUNDNESS = @FRAGMENT_ROUNDNESS@;
const float FR_SIZE = @SIZE_VARIATION@;
const float FR_SHRINK = @FRAGMENT_SHRINK@;

@FRAGMENT_SHAPES@

mat2 fr_turn(float angle) {
    float c = cos(angle), s = sin(angle);
    return mat2(c, s, -s, c);
}
vec2 fr_hash(vec2 cell, int part) {
    vec2 key = mod(cell, 4096.0);
    float x = mod(dot(key, vec2(127.0, 311.0)) + float(part) * 199.0, 4096.0);
    float y = mod(dot(key, vec2(269.0, 183.0)) + float(part) * 137.0, 4096.0);
    for (int i = 0; i < 3; i++) {
        x = mod(x * x + y, 4096.0);
        y = mod(y * 109.0 + x * 241.0 + 17.0, 4096.0);
    }
    return (vec2(x, y) + 0.5) / 4096.0;
}
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
    vec4 intact = fr_sample(coords_curr_geo.xy, blend);
    if (p <= 0.0 || p >= 1.0 || FR_STRENGTH <= 0.0) return intact;
    float pulse = pow(sin(p * 3.14159265359), 2.0) * FR_STRENGTH;
    vec2 current_size = max(size_curr_geo.xy, vec2(1.0));
    vec2 next_scale = vec2(niri_curr_geo_to_next_geo[0][0], niri_curr_geo_to_next_geo[1][1]);
    vec2 size = fx_resize_reference_size(current_size / max(next_scale, vec2(0.0001)));
    vec2 pixel = coords_curr_geo.xy * size;
    // Border/shadow pixels keep their ordinary crossfade. Interior pieces never
    // need an expanded offscreen rectangle, which stock resize cannot promise.
    if (any(lessThan(pixel, vec2(0.0))) || any(greaterThanEqual(pixel, size))) return intact;
    float tile = FR_COUNT > 0.0 ? max(4.0, sqrt(size.x * size.y / FR_COUNT)) : FR_TILE;
    tile *= shaped_density();
    vec2 stretch = shaped_stretch();
    mat2 layout = fr_turn(radians(FX_ORIENTATION));
    mat2 inverse_layout = fr_turn(-radians(FX_ORIENTATION));
    float radius = shaped_radius(stretch);
    radius *= tile;
    vec2 grid = inverse_layout * (pixel - size * 0.5) / (tile * stretch);
    vec2 candidate = floor(FX_SHAPE == 5 && FX_MIX == 0.0 ? shaped_axial(grid) : grid);
    vec2 changing = step(vec2(0.0001), abs(fx_resize_reference_ratio(next_scale) - vec2(1.0)));
    // Metric for a conservative antialias width under anisotropic stretching.
    vec2 material_scale = next_scale;
#ifdef NIRIFX_RESIZE_CONTINUITY_V1
    if (niri_resize_retained > 0.5) material_scale = current_size / size;
#endif
    float metric = tile * min(stretch.x, stretch.y) * min(material_scale.x, material_scale.y);
    vec4 result = vec4(0.0);
    for (int y = -@SHAPED_RESIZE_RADIUS@; y <= @SHAPED_RESIZE_RADIUS@; y++) {
      for (int x = -@SHAPED_RESIZE_RADIUS@; x <= @SHAPED_RESIZE_RADIUS@; x++) {
        vec2 cell = candidate + vec2(float(x), float(y));
        for (int part = 0; part < @SHAPED_PARTS@; part++) {
                if (part > 0 && shaped_kind(cell) != 2) continue;
            vec2 center_grid = shaped_center(cell, part);
            vec2 center = size * 0.5 + layout * (center_grid * tile * stretch);
            vec2 offset = pixel - center;
            float reach = radius + tile * 0.4;
            if (dot(offset, offset) > reach * reach) continue;
            vec2 random = fr_hash(cell, part);
            float border = min(min(center.x, center.y), min(size.x - center.x, size.y - center.y));
            // Keep a full piece-radius band intact. This seals all borders even
            // for rotated triangles and strongly elongated hexagons.
            float local_pulse = pulse * smoothstep(radius, radius + tile, border);
            if (FR_MODE == 1) {
                vec2 edge = abs(center / size - 0.5) * 2.0 * changing;
                local_pulse *= smoothstep(0.35, 0.85, max(edge.x, edge.y));
            }
            if (FR_MODE == 2) local_pulse *= 0.28;
            vec2 direction = vec2(cos(random.x * 6.28318530718), sin(random.x * 6.28318530718));
            if (FR_GRAVITY == 1) direction = vec2(0.0, 1.0);
            if (FR_GRAVITY == 2) direction = vec2(0.0, -1.0);
            if (FR_GRAVITY == 3) direction = vec2(-1.0, 0.0);
            if (FR_GRAVITY == 4) direction = vec2(1.0, 0.0);
            if (FR_GRAVITY >= 5) {
                vec2 radial = center / size - 0.5;
                direction = radial / max(length(radial), 0.001) * (FR_GRAVITY == 5 ? -1.0 : 1.0);
            }
            vec2 drift = direction * tile * (0.2 + 0.2 * random.y) * local_pulse;
            float angle = (random.y * 2.0 - 1.0) * radians(FR_SPIN) * 0.35;
            if (FR_ROTATION == 0) angle = 0.0;
            if (FR_ROTATION == 2) {
                float heading = atan(direction.y, direction.x) - radians(FX_ORIENTATION);
                heading = mod(heading + 3.14159265359, 6.28318530718) - 3.14159265359;
                angle = clamp(heading, -radians(FR_SPIN), radians(FR_SPIN));
            }
            float shrink = (1.0 - 0.6 * local_pulse)
                         * (1.0 - 0.45 * FR_SIZE * random.y * local_pulse)
                         * (1.0 - 0.45 * FR_SHRINK * local_pulse);
            vec2 relative = offset - drift;
            if (dot(relative, relative) > radius * radius * shrink * shrink) continue;
            vec2 local = inverse_layout * (fr_turn(-angle * local_pulse) * relative)
                       / (shrink * tile * stretch);
            if (!shaped_owns(center_grid + local, cell, part)) continue;
            vec2 source = center + layout * (local * tile * stretch);
            if (any(lessThan(source, vec2(0.0))) || any(greaterThanEqual(source, size))) continue;
            float edge = shaped_edge(local, cell, part, local_pulse) * metric * shrink;
            if (edge < -0.0001) continue;
            float coverage = mix(1.0, smoothstep(0.0, 0.8, edge), local_pulse);
            vec4 color = fr_sample(source / size, blend) * coverage;
            result = color + result * (1.0 - color.a);
        }
      }
    }
    return FR_MODE == 2 ? mix(intact, result, 0.65) : result;
}
