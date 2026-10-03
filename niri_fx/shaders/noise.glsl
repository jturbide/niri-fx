// SPDX-License-Identifier: MIT
// Original seeded lattice noise shared by NiriFX erosion and wisps.
// Deterministic value noise. Seed is fixed within an animation, which lets
// a reversed progress value reconstruct the same pattern without stored state.
float fx_hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7)) + niri_random_seed * 91.7) * 43758.5453);
}
float fx_noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(fx_hash(i), fx_hash(i + vec2(1.0, 0.0)), f.x),
               mix(fx_hash(i + vec2(0.0, 1.0)), fx_hash(i + vec2(1.0)), f.x), f.y);
}
