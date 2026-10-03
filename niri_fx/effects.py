"""Public effect catalog and action-specific shader generation."""

import math
import re
from dataclasses import asdict
from importlib.resources import files

from .model import (
    ELASTIC_ANCHORS,
    ELASTIC_AXES,
    FAMILIES,
    GRAVITIES,
    LIMITS,
    PARAMETERS,
    PRESET_SCHEMA,
    RELEASES,
    RESIZE_MODES,
    ROTATIONS,
    SLICE_DIRECTIONS,
    SLICE_ORDERS,
    Effect,
)
from .parameters import glsl_number, shader_tokens
from .presets import PRESETS
from .profiles import Profile

__all__ = [
    "ELASTIC_ANCHORS",
    "ELASTIC_AXES",
    "FAMILIES",
    "GRAVITIES",
    "LIMITS",
    "PARAMETERS",
    "PRESET_SCHEMA",
    "RELEASES",
    "RESIZE_MODES",
    "ROTATIONS",
    "SLICE_DIRECTIONS",
    "SLICE_ORDERS",
    "Effect",
    "PRESETS",
    "shader_templates",
    "shader",
    "resize_shader",
    "movement_shader",
    "animation_types",
    "render_kdl",
    "preset_description",
    "describe_presets",
]


# Family names map directly to files. Fragments has four implementations with
# different bounded lookup costs; resize has its own two-texture interface.
RESIZE_TEMPLATES = {
    "fragments": "resize",
    **{name: f"resize-{name}" for name in ("elastic", "slices", "distortion")},
}

TEMPLATE_FILES = {
    "classic": "fragments",
    "gravity": "gravity",
    "varied": "varied",
    "shaped": "shaped",
    **{name: name for name in RESIZE_TEMPLATES.values()},
    **{name: name for name in FAMILIES if name != "fragments"},
}


def _template(filename, entry=None):
    """Resolve shared GLSL first, then substitute action and parameter tokens."""
    root = files("niri_fx").joinpath("shaders")
    source = root.joinpath(f"{filename}.glsl").read_text()
    if "@ACTION_ENTRY@" in source:
        source = source.replace(
            "@ACTION_ENTRY@",
            root.joinpath(f"{filename}-entry.glsl").read_text().rstrip()
            if entry is None
            else entry,
        )
    for token, snippet in {
        "NOISE": "noise",
        "EDGE_COLOR": "edge-color",
        "RESIZE_COMMON": "resize-common",
        "FRAGMENT_SHAPES": "fragment-shapes",
    }.items():
        if f"@{token}@" in source:
            source = source.replace(
                f"@{token}@", root.joinpath(f"{snippet}.glsl").read_text().rstrip()
            )
    return source


def shader_templates():
    """Python and offline Studio expand the same assembled template strings."""
    return {name: _template(filename) for name, filename in TEMPLATE_FILES.items()}


def renderer_name(effect):
    """Select a renderer without changing an effect's saved parameters."""
    if effect.family != "fragments":
        return effect.family
    if effect.shaped:
        return "shaped"
    if effect.varied:
        return "varied"
    return "classic" if effect.classic else "gravity"


def shader(effect, opening):
    """Opening reverses the same breakup path; independent profiles choose separately."""
    return _expand(shader_templates()[renderer_name(effect)], effect, opening)


def resize_shader(effect):
    if not FAMILIES[effect.family]["resize"]:
        raise ValueError(f"The {effect.family} family does not support resize")
    return _expand(shader_templates()[RESIZE_TEMPLATES[effect.family]], effect, False)


def movement_shader(effect):
    """Experimental API: emit only for the pinned patched compositor."""
    if not FAMILIES[effect.family]["movement"]:
        raise ValueError(f"The {effect.family} family does not support experimental movement")
    renderer = TEMPLATE_FILES[renderer_name(effect)]
    if effect.family == "elastic":
        entry = """vec4 move_color(vec3 coords_geo, vec3 size_geo) {
    vec2 impulse = niri_move_impulse * (@MOVEMENT_STRENGTH@ / 0.64);
    return elastic_color(coords_geo, size_geo, niri_clamped_progress, 0.0, impulse);
}
"""
    else:
        function = {
            "fragments": "fragments",
            "slices": "slices",
            "pixels": "pixels",
            "distortion": "distortion",
        }[effect.family]
        entry = """vec4 move_color(vec3 coords_geo, vec3 size_geo) {
    float p = niri_clamped_progress;
    float breakup = @MOVEMENT_STRENGTH@ * pow(sin(3.14159265359 * p), 2.0);
    if (p <= 0.0 || p >= 1.0) breakup = 0.0;
    return FUNCTION_color(coords_geo, size_geo, breakup);
}
""".replace("FUNCTION", function)
    return _expand(_template(renderer, entry), effect, False)


def shape_search_radius(effect):
    """Bound inverse cell lookup despite spin, aspect, wandering and waves.

    A source piece fits inside `radius * tile`. Inverse flight adds at most .72
    tiles of wander; undoing the wave expands distances by at most 1.45. Rotating
    the lattice preserves lengths and undoing its aspect adds `stretch`. Hex
    axial coordinate rows have norm 2/3. Floor the extreme possible coordinates
    relative to each cell's centroid. Match this bound in effect-core.js;
    shader parity tests enforce it.
    """
    aspect = 1 if effect.fragment_shape in {"square", "circle"} else effect.fragment_aspect
    stretch = math.sqrt(max(aspect, 1 / aspect))
    radius = 0.5 * math.sqrt(aspect + 1 / aspect)
    low = high = 0.5
    if effect.fragment_shape == "triangle":
        radius = math.sqrt(max(4 * aspect + 1 / aspect, aspect + 4 / aspect)) / 3
        low, high = 1 / 3, 2 / 3
    axial = 1
    if effect.fragment_shape == "hexagon":
        radius, axial = stretch, 2 / 3
        low = high = 0
    reach = (radius + 0.72 * effect.dispersion) * (1.45 if effect.wave_strength else 1)
    reach = reach * stretch * axial + 0.00001
    return max(math.floor(reach + high), math.ceil(reach - low))


def _expand(template, effect, opening):
    tokens = shader_tokens(effect, PARAMETERS)
    tokens.update(
        {
            "VARIED_RADIUS": "2" if effect.wave_strength == 0 else "3",
            "SHAPED_RADIUS": str(shape_search_radius(effect)),
            "SHAPED_PARTS": "2" if effect.fragment_shape == "triangle" else "1",
            "ELASTIC_ORIGIN_X": glsl_number(ELASTIC_ANCHORS[effect.elastic_anchor][0]),
            "ELASTIC_ORIGIN_Y": glsl_number(ELASTIC_ANCHORS[effect.elastic_anchor][1]),
            "ENTRY": "open_color" if opening else "close_color",
            "PROGRESS": "1.0 - niri_clamped_progress" if opening else "niri_clamped_progress",
        }
    )

    def substitute(match):
        try:
            return tokens[match[1]]
        except KeyError as error:
            raise ValueError(f"Unknown shader token: {match[1]}") from error

    return re.sub(r"@([A-Z_]+)@", substitute, template)


def animation_types(effect):
    """Emit only stock actions; preserving a movement slot never activates it.

    Profiles opt into resize with a separate slot. Single styles use their
    explicit resize flag. Omitting the key lets the base Niri config keep control.
    """
    selected = (
        {action: getattr(effect, action) for action in ("open", "close", "resize")}
        if isinstance(effect, Profile)
        else {"open": effect, "close": effect, "resize": effect if effect.resize else None}
    )
    return {
        f"window-{action}": {
            "duration-ms": getattr(style, f"{action}_ms"),
            "curve": "linear",
            "custom-shader": resize_shader(style)
            if action == "resize"
            else shader(style, action == "open"),
        }
        for action, style in selected.items()
        if style is not None
    }


def render_kdl(effect):
    parts = ["// Generated by NiriFX. Include after your base animation settings.", "animations {"]
    for name, spec in animation_types(effect).items():
        parts.extend(
            [
                f"    {name} {{",
                f"        duration-ms {int(spec['duration-ms'])}",
                '        curve "linear"',
                '        custom-shader r"',
                spec["custom-shader"].rstrip(),
                '        "',
                "    }",
            ]
        )
    return "\n".join([*parts, "}", ""])


def preset_description(effect):
    if isinstance(effect, Profile):
        return f"Open: {effect.open.family}; close: {effect.close.family}; resize: {effect.resize.family if effect.resize else 'unchanged'}."
    if effect.family not in ("fragments", "slices", "elastic"):
        return f"{FAMILIES[effect.family]['label']} effect; {effect.open_ms}/{effect.close_ms}ms open/close."
    if effect.family == "elastic":
        return f"Spring wobble {effect.elastic_strength:g}×, {effect.elastic_frequency:g} cycles, {effect.elastic_axis}; {effect.open_ms}/{effect.close_ms}ms open/close."
    if effect.family == "slices":
        return f"{int(effect.slice_count)} slices at {effect.slice_angle:g}°, {effect.slice_direction}; {effect.open_ms}/{effect.close_ms}ms open/close."
    density = (
        f"~{effect.particles} pieces" if effect.particles else f"{effect.tile_size:g}px pieces"
    )
    motion = (
        f"{effect.gravity} {effect.gravity_strength:g}×, {effect.rotation} spin"
        if not effect.classic
        else f"{effect.scatter:g}px scatter"
    )
    return f"{density}, {motion}; {effect.open_ms}/{effect.close_ms}ms open/close." + (
        f" Resize {effect.resize_ms}ms." if effect.resize else ""
    )


def describe_presets():
    return {name: asdict(effect) for name, effect in PRESETS.items()}
