vec4 @ENTRY@(vec3 coords_geo, vec3 size_geo) {
    return pixels_color(coords_geo, size_geo, @PROGRESS@);
}
