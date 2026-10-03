// NiriFX slices: inverse-map each rigid strip into its original window texture.
// Original shader, MIT licensed. Bounded by the validated 2–48 slice count.
const int SL_COUNT = @SLICE_COUNT@;
const float SL_ANGLE = @SLICE_ANGLE@;
const float SL_DISTANCE = @SLICE_DISTANCE@;
const float SL_STAGGER = @SLICE_STAGGER@;
const float SL_ROTATION = @SLICE_ROTATION@;
const int SL_DIRECTION = @SLICE_DIRECTION@;

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
    float width = span / float(SL_COUNT);
    vec4 result = vec4(0.0);
    for (int index = 0; index < SL_COUNT; index++) {
        float ordinal = float(index);
        float position = (ordinal + 0.5) / float(SL_COUNT);
        float delay = SL_STAGGER * ordinal / float(SL_COUNT - 1);
        float t = clamp((progress - delay) / (1.0 - SL_STAGGER), 0.0, 1.0);
        float flight = t * t * (3.0 - 2.0 * t);
        float direction = position < 0.5 ? -1.0 : 1.0;
        if (SL_DIRECTION == 1) direction = mod(ordinal, 2.0) < 1.0 ? -1.0 : 1.0;
        if (SL_DIRECTION == 2) direction = 1.0;
        if (SL_DIRECTION == 3) direction = -1.0;
        float random = fract(sin(ordinal * 127.1 + niri_random_seed * 43.7) * 43758.5453);
        vec2 pivot = normal * ((position - 0.5) * span);
        vec2 travel = tangent * direction * SL_DISTANCE * flight * (0.9 + 0.2 * random);
        float angle = direction * SL_ROTATION * 0.01745329252 * flight;
        float c = cos(angle), s = sin(angle);
        // Inverse rotation and translation recover the stationary source point.
        vec2 relative = pixel - pivot - travel;
        vec2 source = vec2(c * relative.x + s * relative.y, -s * relative.x + c * relative.y) + pivot;
        float stripe = dot(source, normal) + span * 0.5;
        float low = ordinal * width, high = low + width;
        if (stripe < low || stripe >= high) continue;
        vec2 geo = source / size + 0.5;
        float fade = 1.0 - smoothstep(0.35, 1.0, t);
        // Reveal a subpixel edge only as strips move, preserving the intact image.
        float edge = mix(1.0, smoothstep(0.0, 0.75, min(stripe - low, high - stripe)), flight);
        vec4 color = slices_sample(geo) * fade * edge;
        result = color + result * (1.0 - color.a);
    }
    return result;
}

vec4 @ENTRY@(vec3 coords_geo, vec3 size_geo) {
    return slices_color(coords_geo, size_geo, @PROGRESS@);
}
