// SPDX-License-Identifier: MIT
// Layered erosion with a charcoal band and a configurable narrow rim.
@NOISE@
@EDGE_COLOR@
vec4 @ENTRY@(vec3 coords_geo, vec3 size_geo) {
    vec2 uv = coords_geo.xy;
    if (any(lessThan(uv, vec2(0.0))) || any(greaterThanEqual(uv, vec2(1.0)))) return vec4(0.0);
    float p = @PROGRESS@;
    vec4 color = texture2D(niri_tex, (niri_geo_to_tex * coords_geo).xy);
    if (p <= 0.0) return color;
    if (p >= 1.0) return vec4(0.0);
    // Logical-pixel noise cells stay the same apparent size across window sizes.
    // Detail adds higher frequencies; flow moves the field without state/history.
    vec2 q = uv * size_geo.xy / @DISSOLVE_SCALE@;
    q += @DISSOLVE_FLOW@ * p * vec2(0.4, -1.0);
    float fine = (fx_noise(q * 2.13 + 17.0) + 0.5 * fx_noise(q * 4.31 - 9.0)) / 1.5;
    float field = mix(fx_noise(q), fine, @DISSOLVE_DETAIL@ * 0.65);
    float order = uv.x;
    if (@DISSOLVE_DIRECTION@ == 2) order = 1.0 - uv.x;
    if (@DISSOLVE_DIRECTION@ == 3) order = uv.y;
    if (@DISSOLVE_DIRECTION@ == 4) order = 1.0 - uv.y;
    if (@DISSOLVE_DIRECTION@ == 5) order = length((uv - 0.5) * 1.41421356237);
    if (@DISSOLVE_DIRECTION@ != 0) field = mix(field, order, @DISSOLVE_BIAS@);
    if (@DISSOLVE_MODE@ == 1) {
        // A spreading wet edge with layered turbulence. A fixed origin and
        // deterministic field make reconstruction a reverse ink reveal.
        vec2 origin = vec2(@DISSOLVE_X@, @DISSOLVE_Y@);
        vec2 size = max(size_geo.xy, vec2(1.0));
        float radius = max(length(max(origin, 1.0 - origin) * size), 1.0);
        float radial = length((uv - origin) * size) / radius;
        field = clamp(radial + (field - 0.5) * 0.5 * @DISSOLVE_TURBULENCE@, 0.0, 1.0);
    }
    // Sweep beyond both ends of the noise range so the soft band fully enters
    // and exits. Explicit endpoint branches above preserve the exact source.
    float threshold = mix(-@DISSOLVE_SOFTNESS@, 1.0 + @DISSOLVE_SOFTNESS@, p);
    float mask = smoothstep(threshold - @DISSOLVE_SOFTNESS@, threshold + @DISSOLVE_SOFTNESS@, field);
    float band = max(@EDGE_WIDTH@, 0.00001);
    float edge_activity = smoothstep(0.0, 0.12, p) * (1.0 - step(@EDGE_WIDTH@, 0.0));
    float charred = (1.0 - smoothstep(0.0, band * 2.0, field - threshold)) * edge_activity;
    float rim = (1.0 - smoothstep(0.0, band * 0.65, field - threshold)) * edge_activity;
    // Darken the wider band before adding a narrow rim. Multiply the rim by
    // source alpha so transparent client pixels never acquire opaque color.
    color.rgb = mix(color.rgb, color.rgb * 0.08, charred * @EDGE_CHAR@);
    color.rgb = mix(color.rgb, fx_edge_color() * color.a, rim);
    return color * mask;
}
