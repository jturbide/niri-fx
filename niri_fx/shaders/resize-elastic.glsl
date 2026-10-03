// SPDX-License-Identifier: MIT
@RESIZE_COMMON@
vec4 resize_color(vec3 coords_curr_geo, vec3 size_curr_geo) {
    float p = niri_clamped_progress, blend = smoothstep(0.2, 0.8, p);
    vec2 uv = coords_curr_geo.xy;
    if (p <= 0.0 || p >= 1.0 || @RESIZE@ <= 0.0) return resize_sample(uv, blend);
    float spring = sin(p * 3.14159265359) * cos(p * @ELASTIC_FREQUENCY@ * 6.2831853) * exp(-p * @ELASTIC_DAMPING@);
    vec2 change = resize_change();
    if (@ELASTIC_AXIS@ == 1) change.y = 0.0;
    if (@ELASTIC_AXIS@ == 2) change.x = 0.0;
    vec2 origin = vec2(@ELASTIC_ORIGIN_X@, @ELASTIC_ORIGIN_Y@);
    vec2 offset = (uv - origin) * change * spring * @RESIZE@ * @ELASTIC_STRENGTH@ * 0.35;
    offset *= resize_boundary(uv);
    return resize_sample(uv + offset, blend);
}
