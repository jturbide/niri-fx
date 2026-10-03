// SPDX-License-Identifier: MIT
// NiriFX slices: inverse-map each rigid strip into its original window texture.
// Original shader, MIT licensed. Bounded by the validated 2–48 slice count.
const int SL_COUNT = @SLICE_COUNT@;
const float SL_ANGLE = @SLICE_ANGLE@;
const float SL_DISTANCE = @SLICE_DISTANCE@;
const float SL_STAGGER = @SLICE_STAGGER@;
const float SL_ROTATION = @SLICE_ROTATION@;
const int SL_DIRECTION = @SLICE_DIRECTION@;
const int SL_ORDER = @SLICE_ORDER@;
const float SL_SIZE_VARIATION = @SIZE_VARIATION@;
const float SL_DIRECTION_VARIATION = @DIRECTION_VARIATION@;
const float SL_TRAVEL_VARIATION = @SLICE_TRAVEL_VARIATION@;
const float SL_ROTATION_VARIATION = @SLICE_ROTATION_VARIATION@;
const float SL_WAVE = @WAVE_STRENGTH@;
const float SL_FREQUENCY = @WAVE_FREQUENCY@;
const float SL_SPEED = @WAVE_SPEED@;
const float SL_PIVOT = @SLICE_PIVOT@;
const float SL_COLLAPSE = @SLICE_COLLAPSE@;

float slices_hash(float index, float salt) {
    return fract(sin(index * 127.1 + niri_random_seed * 43.7 + salt) * 43758.5453);
}
// Shared boundaries partition the whole texture, even with unequal widths.
float slices_boundary(float index) {
    if (index <= 0.0 || index >= float(SL_COUNT)) return index / float(SL_COUNT);
    return (index + (slices_hash(index, 19.1) * 2.0 - 1.0) * 0.45 * SL_SIZE_VARIATION) / float(SL_COUNT);
}

vec4 slices_sample(vec2 geo) {
    if (any(lessThan(geo, vec2(0.0))) || any(greaterThanEqual(geo, vec2(1.0)))) return vec4(0.0);
    return texture2D(niri_tex, (niri_geo_to_tex * vec3(geo, 1.0)).xy);
}

vec4 slices_color(vec3 coords_geo, vec3 size_geo, float progress) {
    if (progress <= 0.0) return slices_sample(coords_geo.xy);
    if (progress >= 1.0) return vec4(0.0);
    vec2 size = max(size_geo.xy, vec2(1.0));
    vec2 pixel = (coords_geo.xy - 0.5) * size;
    float radians = SL_ANGLE * 0.01745329252;
    vec2 tangent = vec2(cos(radians), sin(radians));
    vec2 normal = vec2(-tangent.y, tangent.x);
    float span = dot(abs(normal), size);
    vec4 result = vec4(0.0);
    for (int index = 0; index < SL_COUNT; index++) {
        float ordinal = float(index);
        float low = slices_boundary(ordinal) * span, high = slices_boundary(ordinal + 1.0) * span;
        float position = (low + high) * 0.5 / span;
        float order = ordinal / float(SL_COUNT - 1);
        if (SL_ORDER == 1) order = 1.0 - order;
        if (SL_ORDER == 2) order = abs(order * 2.0 - 1.0);
        if (SL_ORDER == 3) order = 1.0 - abs(order * 2.0 - 1.0);
        if (SL_ORDER == 4) order = slices_hash(ordinal, 53.7);
        if (SL_ORDER == 5) order = 0.0;
        float stagger = SL_ORDER == 5 ? 0.0 : SL_STAGGER;
        float delay = stagger * order;
        float t = clamp((progress - delay) / (1.0 - stagger), 0.0, 1.0);
        float flight = t * t * (3.0 - 2.0 * t);
        float direction = position < 0.5 ? -1.0 : 1.0;
        if (SL_DIRECTION == 1) direction = mod(ordinal, 2.0) < 1.0 ? -1.0 : 1.0;
        if (SL_DIRECTION == 2) direction = 1.0;
        if (SL_DIRECTION == 3) direction = -1.0;
        if (SL_DIRECTION == 4) direction = slices_hash(ordinal, 81.3) < 0.5 ? -1.0 : 1.0;
        float random = slices_hash(ordinal, 0.0);
        vec2 pivot = normal * ((position - 0.5) * span)
                   + tangent * (SL_PIVOT * dot(abs(tangent), size) * 0.5);
        float heading = (slices_hash(ordinal, 37.9) * 2.0 - 1.0) * 3.14159265359 * SL_DIRECTION_VARIATION;
        vec2 heading_axis = tangent * cos(heading) + normal * sin(heading);
        vec2 travel = heading_axis * direction * SL_DISTANCE * flight * (1.0 + SL_TRAVEL_VARIATION * (2.0 * random - 1.0));
        float wave = sin(6.28318530718 * (SL_FREQUENCY * position - SL_SPEED * t)) * sin(3.14159265359 * t);
        travel += normal * (SL_WAVE * span * 0.45 / (6.28318530718 * SL_FREQUENCY)) * wave;
        float rotation = mix(direction, slices_hash(ordinal, 67.1) * 2.0 - 1.0, SL_ROTATION_VARIATION);
        float angle = rotation * SL_ROTATION * 0.01745329252 * flight;
        float c = cos(angle), s = sin(angle);
        // Inverse rotation and translation recover the stationary source point.
        vec2 relative = pixel - pivot - travel;
        vec2 unturned = vec2(c * relative.x + s * relative.y, -s * relative.x + c * relative.y);
        // Compress only the strip width, then invert it in the unrotated frame.
        // The positive scale floor prevents a singular lookup near disappearance.
        float width_scale = 1.0 - 0.94 * SL_COLLAPSE * flight;
        vec2 source = unturned + pivot;
        if (SL_COLLAPSE > 0.0)
            source += normal * dot(unturned, normal) * (1.0 / width_scale - 1.0);
        float stripe = dot(source, normal) + span * 0.5;
        if (stripe < low || stripe >= high) continue;
        vec2 geo = source / size + 0.5;
        float fade = 1.0 - smoothstep(0.35, 1.0, t);
        // Reveal a subpixel edge only as strips move, preserving the intact image.
        float edge = mix(1.0, smoothstep(0.0, 0.75, min(stripe - low, high - stripe) * width_scale), flight);
        vec4 color = slices_sample(geo) * fade * edge;
        result = color + result * (1.0 - color.a);
    }
    return result;
}

@ACTION_ENTRY@
