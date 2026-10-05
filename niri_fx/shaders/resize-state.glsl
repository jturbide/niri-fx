// SPDX-License-Identifier: MIT
// niri-fx resize-continuity: 1
// Stock Niri supplies two client snapshots. The experimental renderer can retain
// one undeformed material, its phase and its original geometry across retargets.
// Only that renderer defines this macro; stock exports keep their existing math.
vec2 fx_resize_reference_size(vec2 stock_size) {
#ifdef NIRIFX_RESIZE_CONTINUITY_V1
    if (niri_resize_retained > 0.5) return max(niri_resize_reference_size, vec2(1.0));
#endif
    return stock_size;
}
// Follow the original resize's virtual geometry as its phase advances. This
// matches uninterrupted stock motion, even when a retarget changes real geometry.
vec2 fx_resize_material_size(vec2 stock_size) {
#ifdef NIRIFX_RESIZE_CONTINUITY_V1
    if (niri_resize_retained > 0.5)
        return max(mix(niri_resize_reference_from_size, niri_resize_reference_to_size,
                       niri_clamped_progress), vec2(1.0));
#endif
    return stock_size;
}
vec2 fx_resize_reference_ratio(vec2 stock_ratio) {
#ifdef NIRIFX_RESIZE_CONTINUITY_V1
    if (niri_resize_retained > 0.5)
        return fx_resize_material_size(vec2(1.0))
             / max(niri_resize_reference_to_size, vec2(1.0));
#endif
    return stock_ratio;
}
