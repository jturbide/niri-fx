// SPDX-License-Identifier: MIT
// Geometry in lattice units. Each cell owns a disjoint part of the original
// window; silhouettes contract inside that ownership region during flight.
const int FX_SHAPE = @FRAGMENT_SHAPE@;
const int FX_SECONDARY = @FRAGMENT_SECONDARY@;
const float FX_MIX = @FRAGMENT_MIX@;
const int FX_MIX_SEED = @FRAGMENT_SHAPE_SEED@;

// Document-seeded cell identity is independent of animation time and action.
// Mixed layouts keep one rectangular source grid; triangle cells partition into
// two pieces. Other silhouettes emerge inside their cell, with exact coverage
// at reconstruction. No cell changes shape during a flight or resize.
int shaped_kind(vec2 cell) {
    if (FX_MIX == 0.0) return FX_SHAPE;
    vec2 key = mod(floor(cell), 4096.0);
    float x = mod(dot(key, vec2(127.0, 311.0)) + float(FX_MIX_SEED) * 17.0, 4096.0);
    float y = mod(dot(key, vec2(269.0, 183.0)) + float(FX_MIX_SEED) * 137.0, 4096.0);
    for (int i = 0; i < 3; i++) {
        x = mod(x * x + y, 4096.0);
        y = mod(y * 109.0 + x * 241.0 + 17.0, 4096.0);
    }
    return (x + 0.5) / 4096.0 < FX_MIX ? FX_SECONDARY : FX_SHAPE;
}
float shaped_density() {
    if (FX_MIX == 0.0) return FX_SHAPE == 2 ? 1.41421356237 : (FX_SHAPE == 5 ? 0.620403239401 : 1.0);
    float triangles = FX_SHAPE == 2 ? 1.0 - FX_MIX : (FX_SECONDARY == 2 ? FX_MIX : 0.0);
    return sqrt(1.0 + triangles);
}
float shaped_radius(vec2 stretch) {
    float radius = 0.5 * length(stretch);
    if (FX_SHAPE == 2 || (FX_MIX > 0.0 && FX_SECONDARY == 2))
        radius = max(length(stretch * vec2(2.0, 1.0)), length(stretch * vec2(1.0, 2.0))) / 3.0;
    if (FX_SHAPE == 5 && FX_MIX == 0.0) radius = max(stretch.x, stretch.y);
    return radius;
}
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
    if (FX_SHAPE == 5 && FX_MIX == 0.0)
        return vec2(1.73205080757 * (cell.x + cell.y * 0.5), 1.5 * cell.y);
    if (shaped_kind(cell) == 2) return cell + vec2(part == 0 ? 1.0 / 3.0 : 2.0 / 3.0);
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
    if (FX_SHAPE == 5 && FX_MIX == 0.0) return all(lessThan(abs(shaped_hex_owner(point) - cell), vec2(0.1)));
    if (any(lessThan(point, cell)) || any(greaterThanEqual(point, cell + 1.0))) return false;
    if (shaped_kind(cell) == 2) {
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
float shaped_edge(vec2 local, vec2 cell, int part, float progress) {
    int kind = shaped_kind(cell);
    float box = min(0.5 - abs(local.x), 0.5 - abs(local.y));
    float edge = box, inradius = 0.5;
    if (kind == 2) {
        vec2 point = local + vec2(part == 0 ? 1.0 / 3.0 : 2.0 / 3.0);
        edge = part == 0
            ? min(min(point.x, point.y), (1.0 - point.x - point.y) / 1.41421356237)
            : min(min(1.0 - point.x, 1.0 - point.y), (point.x + point.y - 1.0) / 1.41421356237);
        inradius = 0.235702260396;
    } else if (kind == 5 && FX_MIX == 0.0) {
        vec2 a = abs(local);
        edge = 0.866025403784 - max(a.x, dot(a, vec2(0.5, 0.866025403784)));
        inradius = 0.866025403784;
    }
    float emergence = smoothstep(0.0, FX_TRANSITION, progress);
    float silhouette = edge;
    if (kind == 5 && FX_MIX > 0.0) {
        vec2 a = abs(local);
        silhouette = 0.433012701892 - max(a.x, dot(a, vec2(0.5, 0.866025403784)));
        inradius = mix(0.5, 0.433012701892, emergence);
    }
    if (kind == 3 || kind == 4) silhouette = 0.5 - length(local);
    if (kind == 6) silhouette = (0.5 - abs(local.x) - abs(local.y)) / 1.41421356237;
    if (kind == 7) silhouette = shaped_star(local);
    edge = mix(edge, silhouette, emergence);
    // Interpolate toward a contained circle to soften polygon corners without
    // expanding their source region. Circle/ellipse already have smooth edges.
    if (kind != 3 && kind != 4 && kind != 7) {
        if (kind == 6) inradius = mix(0.5, 0.353553390593, emergence);
        edge = mix(edge, inradius - length(local), FX_ROUNDNESS * emergence);
    }
    return edge;
}
