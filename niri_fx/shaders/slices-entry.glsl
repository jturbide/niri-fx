vec4 @ENTRY@(vec3 coords_geo, vec3 size_geo) {
    return slices_color(coords_geo, size_geo, @PROGRESS@);
}
