// SPDX-License-Identifier: MIT
// Aspect-correct geometric reveal with explicit intact and transparent endpoints.
vec4 @ENTRY@(vec3 coords_geo, vec3 size_geo) {
    vec2 uv = coords_geo.xy;
    if (any(lessThan(uv, vec2(0.0))) || any(greaterThanEqual(uv, vec2(1.0)))) return vec4(0.0);
    float p = @PROGRESS@;
    vec4 color = texture2D(niri_tex, (niri_geo_to_tex * coords_geo).xy);
    if (p <= 0.0) return color;
    if (p >= 1.0) return vec4(0.0);
    vec2 origin = vec2(@IRIS_X@, @IRIS_Y@);
    vec2 size = max(size_geo.xy, vec2(1.0));
    vec2 delta = (uv - origin) * size;
    // Rotate only the distance field. Texture UVs stay fixed, so the contents
    // are revealed rather than rotated with the mask.
    float angle = radians(@IRIS_TWIST@) * p;
    delta = mat2(cos(angle), -sin(angle), sin(angle), cos(angle)) * delta;
    // A circumscribing radius keeps all corner/origin combinations intact at p=0.
    float radius = length(max(origin, 1.0 - origin) * size);
    float distance = length(delta) / radius;
    if (@IRIS_SHAPE@ == 1) distance = (abs(delta.x) + abs(delta.y)) / (1.41421356237 * radius);
    if (@IRIS_SHAPE@ == 2) distance = max(abs(delta.x), abs(delta.y)) / radius;
    float threshold = mix(1.0 + @IRIS_SOFTNESS@, -@IRIS_SOFTNESS@, p);
    float mask = 1.0 - smoothstep(threshold - @IRIS_SOFTNESS@, threshold + @IRIS_SOFTNESS@, distance);
    if (@IRIS_DIRECTION@ == 1) {
        threshold = mix(-@IRIS_SOFTNESS@, 1.0 + @IRIS_SOFTNESS@, p);
        mask = smoothstep(threshold - @IRIS_SOFTNESS@, threshold + @IRIS_SOFTNESS@, distance);
    }
    return color * mask;
}
