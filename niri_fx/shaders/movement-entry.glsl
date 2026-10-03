// The compositor owns position and interruption state. This shader only
// deforms its current texture; no second translation or independent clock.
vec4 move_color(vec3 coords_geo, vec3 size_geo) {
    float p = niri_clamped_progress;
    float breakup = @MOVEMENT_STRENGTH@ * pow(sin(3.14159265359 * p), 2.0);
    if (p <= 0.0 || p >= 1.0) breakup = 0.0;
    vec4 effect = @FUNCTION@_color(coords_geo, size_geo, breakup);
    if (@MOVEMENT_FOCUS@ <= 0.0) return effect;
    // Smooth normalization also behaves continuously as a reversal passes
    // through zero impulse. Emphasis follows travel, including vertical moves.
    vec2 heading = niri_move_impulse / sqrt(dot(niri_move_impulse, niri_move_impulse) + 0.04);
    float trailing = 0.5 - dot(coords_geo.xy - 0.5, heading);
    float mask = mix(1.0, smoothstep(0.15, 0.8, trailing), @MOVEMENT_FOCUS@);
    vec4 intact = @FUNCTION@_color(coords_geo, size_geo, 0.0);
    // Convex premultiplied blending keeps the leading content readable.
    return mix(intact, effect, mask);
}
