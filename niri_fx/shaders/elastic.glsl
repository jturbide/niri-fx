// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Julien Turbide
// Two reversible shears give a continuous, springy whole-window deformation.
// This is a timed animation, not a simulation of interactive pointer dragging.
const float EL_STRENGTH = @ELASTIC_STRENGTH@;
const float EL_FREQUENCY = @ELASTIC_FREQUENCY@;
const float EL_DAMPING = @ELASTIC_DAMPING@;
const int EL_AXIS = @ELASTIC_AXIS@;
const float EL_TWIST = @ELASTIC_TWIST@;
const float EL_STRETCH = @ELASTIC_STRETCH@;
const float EL_RIPPLE = @ELASTIC_RIPPLE@;
const vec2 EL_ORIGIN = vec2(@ELASTIC_ORIGIN_X@, @ELASTIC_ORIGIN_Y@);
const float EL_PI = 3.14159265359;

vec4 elastic_sample(vec2 geo) {
    if (any(lessThan(geo, vec2(0.0))) || any(greaterThanEqual(geo, vec2(1.0)))) return vec4(0.0);
    return texture2D(niri_tex, (niri_geo_to_tex * vec3(geo, 1.0)).xy);
}

vec4 elastic_color(vec3 coords_geo, vec3 size_geo, float p, float collapse, vec2 impulse) {
    if (p <= 0.0) return elastic_sample(coords_geo.xy);
    if (p >= 1.0) return collapse > 0.0 ? vec4(0.0) : elastic_sample(coords_geo.xy);
    float envelope = sin(EL_PI * p) * exp(-EL_DAMPING * p);
    float spring = sin(2.0 * EL_PI * EL_FREQUENCY * p);
    vec2 bend = impulse * EL_STRENGTH * envelope * vec2(0.22 * spring, 0.15 * cos(2.0 * EL_PI * EL_FREQUENCY * p));
    if (EL_AXIS == 1) bend.y = 0.0;
    if (EL_AXIS == 2) bend.x = 0.0;
    float scale = 1.0 - collapse * 0.28 * smoothstep(0.0, 1.0, p);
    // Mild breathing adds spring tension without folding the texture.
    vec2 stretch = vec2(1.0 + (0.08 + 0.3 * EL_STRETCH) * spring * envelope * EL_STRENGTH,
                        1.0 - (0.06 + 0.3 * EL_STRETCH) * spring * envelope * EL_STRENGTH);
    // Rotate in logical pixels so a wide window rotates without aspect distortion.
    vec2 unturned = coords_geo.xy - EL_ORIGIN;
    if (EL_TWIST != 0.0) {
        vec2 size = max(size_geo.xy, vec2(1.0));
        float angle = EL_TWIST * (EL_PI / 180.0) * spring * envelope * impulse.x;
        float c = cos(angle), s = sin(angle);
        vec2 relative = unturned * size;
        unturned = vec2(c * relative.x + s * relative.y, -s * relative.x + c * relative.y) / size;
    }
    vec2 source = unturned / (scale * stretch) + EL_ORIGIN;
    // Invert y(x') first, then x(y): unlike a simultaneous displacement this
    // is an exact inverse and stays continuous at every frequency/strength.
    source.y -= bend.y * sin(EL_PI * EL_RIPPLE * source.x);
    source.x -= bend.x * sin(EL_PI * EL_RIPPLE * source.y);
    float opacity = 1.0 - collapse * smoothstep(0.45, 1.0, p);
    return elastic_sample(source) * opacity;
}

@ACTION_ENTRY@
