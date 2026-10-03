vec4 @ENTRY@(vec3 coords_geo, vec3 size_geo) {
    return elastic_color(coords_geo, size_geo, @PROGRESS@, 1.0, vec2(1.0));
}
