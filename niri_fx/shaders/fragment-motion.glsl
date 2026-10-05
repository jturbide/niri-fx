// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Julien Turbide
// nirifx-fragment-motion: 3
// nirifx-fragment-grid: @PARTICLES@ @TILE@
#ifdef NIRIFX_FRAGMENT_MESH
// Native code owns each cell's delayed target, pose and original source UVs.
// The material never searches nearby cells or recomputes physics per pixel.
vec4 fragment_motion_mesh_color(vec2 source_uv, vec2 local_px, vec2 half_extent, float edge_blend) {
    if (any(lessThan(source_uv, vec2(0.0))) || any(greaterThanEqual(source_uv, vec2(1.0))))
        return vec4(0.0);
    vec2 edge = half_extent - abs(local_px);
    float coverage = smoothstep(0.0, 0.8 / max(0.01, niri_scale), min(edge.x, edge.y));
    // Blend edge antialiasing from continuous pose velocity, not displacement:
    // a new target must not change a stationary piece's appearance.
    coverage = mix(1.0, coverage, clamp(edge_blend, 0.0, 1.0));
    return texture2D(niri_tex, source_uv) * coverage;
}
#endif
