// SPDX-License-Identifier: MIT
// Original anisotropic flow erosion; highlights retain sampled texture alpha.
@NOISE@
@EDGE_COLOR@
vec4 @ENTRY@(vec3 coords_geo, vec3 size_geo) {
    float p = @PROGRESS@;
    vec2 uv = coords_geo.xy, size = max(size_geo.xy, vec2(1.0));
    if (p >= 1.0) return vec4(0.0);
    float angle = radians(@WISP_ANGLE@);
    vec2 wind = vec2(cos(angle), sin(angle)), side = vec2(-wind.y, wind.x);
    vec2 px = uv * size;
    // Project into the flow basis before stretching the noise into threads.
    // Longitudinal and transverse scales intentionally differ.
    vec2 q = vec2(dot(px, side), dot(px, wind)) / @WISP_SCALE@;
    float curl = sin(q.y * 1.9 + p * @WISP_SPEED@ * 6.2831853 + fx_noise(q * 0.4) * 4.0);
    // A bounded temporal envelope bends the texture most during transition.
    // Inverse sampling can move pixels; it does not alter compositor geometry.
    float envelope = p * p * (1.0 - p) * 4.0;
    vec2 flow = wind * @WISP_DRIFT@ * p * p + side * curl * @WISP_CURL@ * @WISP_SCALE@ * envelope;
    vec2 source = uv - flow / size;
    if (p <= 0.0) source = uv;
    if (any(lessThan(source, vec2(0.0))) || any(greaterThanEqual(source, vec2(1.0)))) return vec4(0.0);
    vec4 color = texture2D(niri_tex, (niri_geo_to_tex * vec3(source, 1.0)).xy);
    if (p <= 0.0) return color;
    q.x += curl * @WISP_CURL@;
    float threads = fx_noise(vec2(q.x * @WISP_STRANDS@, q.y * 0.22 - p * @WISP_SPEED@));
    float detail = fx_noise(q * vec2(@WISP_STRANDS@ * 2.1, 0.65) + p);
    float field = mix(threads, detail, 0.25);
    float threshold = mix(-@WISP_SOFTNESS@, 1.0 + @WISP_SOFTNESS@, p);
    float mask = smoothstep(threshold - @WISP_SOFTNESS@, threshold + @WISP_SOFTNESS@, field);
    // Tint existing premultiplied texture color, never add an opaque glow.
    float highlight = (1.0 - smoothstep(0.0, 0.14, field - threshold)) * @WISP_GLOW@ * sin(p * 3.14159265);
    color.rgb = mix(color.rgb, fx_edge_color() * color.a, highlight);
    return color * mask;
}
