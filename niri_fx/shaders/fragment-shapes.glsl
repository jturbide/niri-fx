// SPDX-License-Identifier: MIT
// Geometry in lattice units. Each cell owns a disjoint part of the original
// window; silhouettes contract inside that ownership region during flight.
const int FX_SHAPE = @FRAGMENT_SHAPE@;
const float FX_ASPECT = @FRAGMENT_ASPECT@;
const float FX_ORIENTATION = @FRAGMENT_ORIENTATION@;
const float FX_TRANSITION = @FRAGMENT_TRANSITION@;

vec2 shaped_stretch() {
    float aspect = (FX_SHAPE == 0 || FX_SHAPE == 3) ? 1.0 : FX_ASPECT;
    return vec2(sqrt(aspect), inversesqrt(aspect));
}
vec2 shaped_axial(vec2 point) {
    return vec2(point.x / 1.73205080757 - point.y / 3.0, point.y * 2.0 / 3.0);
}
vec2 shaped_center(vec2 cell, int part) {
    if (FX_SHAPE == 5)
        return vec2(1.73205080757 * (cell.x + cell.y * 0.5), 1.5 * cell.y);
    if (FX_SHAPE == 2) return cell + vec2(part == 0 ? 1.0 / 3.0 : 2.0 / 3.0);
    return cell + 0.5;
}
vec2 shaped_hex_owner(vec2 point) {
    vec2 axial = shaped_axial(point);
    vec3 cube = vec3(axial.x, -axial.x - axial.y, axial.y);
    vec3 nearest = floor(cube + 0.5), error = abs(nearest - cube);
    // Repair the largest rounding error so x+y+z=0. Strict tie ordering gives
    // every shared edge exactly one owner, including translucent textures.
    if (error.x > error.y && error.x > error.z) nearest.x = -nearest.y - nearest.z;
    else if (error.y > error.z) nearest.y = -nearest.x - nearest.z;
    else nearest.z = -nearest.x - nearest.y;
    return nearest.xz;
}
bool shaped_owns(vec2 point, vec2 cell, int part) {
    if (FX_SHAPE == 5) return all(lessThan(abs(shaped_hex_owner(point) - cell), vec2(0.1)));
    if (any(lessThan(point, cell)) || any(greaterThanEqual(point, cell + 1.0))) return false;
    if (FX_SHAPE == 2) {
        float diagonal = (point.x - cell.x) + (point.y - cell.y);
        return part == 0 ? diagonal < 1.0 : diagonal >= 1.0;
    }
    return true;
}
float shaped_star(vec2 point) {
    float distance_squared = 4.0;
    bool inside = false;
    vec2 previous = vec2(0.0, -0.5);
    // Ten bounded line segments, no imported paths or per-frame parsing.
    for (int i = 1; i <= 10; i++) {
        float angle = float(i) * 0.628318530718 - 1.57079632679;
        float radius = mod(float(i), 2.0) == 0.0 ? 0.5 : 0.23;
        vec2 next = vec2(cos(angle), sin(angle)) * radius;
        vec2 edge = next - previous, relative = point - previous;
        vec2 nearest = relative - edge * clamp(dot(relative, edge) / dot(edge, edge), 0.0, 1.0);
        distance_squared = min(distance_squared, dot(nearest, nearest));
        if ((previous.y > point.y) != (next.y > point.y)) {
            if (point.x < previous.x + edge.x * (point.y - previous.y) / edge.y) inside = !inside;
        }
        previous = next;
    }
    return sqrt(distance_squared) * (inside ? 1.0 : -1.0);
}
float shaped_edge(vec2 local, int part, float progress) {
    float box = min(0.5 - abs(local.x), 0.5 - abs(local.y));
    float edge = box, inradius = 0.5;
    if (FX_SHAPE == 2) {
        vec2 point = local + vec2(part == 0 ? 1.0 / 3.0 : 2.0 / 3.0);
        edge = part == 0
            ? min(min(point.x, point.y), (1.0 - point.x - point.y) / 1.41421356237)
            : min(min(1.0 - point.x, 1.0 - point.y), (point.x + point.y - 1.0) / 1.41421356237);
        inradius = 0.235702260396;
    } else if (FX_SHAPE == 5) {
        vec2 a = abs(local);
        edge = 0.866025403784 - max(a.x, dot(a, vec2(0.5, 0.866025403784)));
        inradius = 0.866025403784;
    }
    float emergence = smoothstep(0.0, FX_TRANSITION, progress);
    float silhouette = edge;
    if (FX_SHAPE == 3 || FX_SHAPE == 4) silhouette = 0.5 - length(local);
    if (FX_SHAPE == 6) silhouette = (0.5 - abs(local.x) - abs(local.y)) / 1.41421356237;
    if (FX_SHAPE == 7) silhouette = shaped_star(local);
    edge = mix(edge, silhouette, emergence);
    // Interpolate toward a contained circle to soften polygon corners without
    // expanding their source region. Circle/ellipse already have smooth edges.
    if (FX_SHAPE != 3 && FX_SHAPE != 4 && FX_SHAPE != 7) {
        if (FX_SHAPE == 6) inradius = mix(0.5, 0.353553390593, emergence);
        edge = mix(edge, inradius - length(local), FX_ROUNDNESS * emergence);
    }
    return edge;
}
