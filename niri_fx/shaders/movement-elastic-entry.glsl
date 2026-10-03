vec4 move_color(vec3 coords_geo, vec3 size_geo) {
    vec2 impulse = niri_move_impulse * (@MOVEMENT_STRENGTH@ / 0.64);
    return elastic_color(coords_geo, size_geo, niri_clamped_progress, 0.0, impulse);
}
