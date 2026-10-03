"""Public effect catalog and action-specific shader generation."""

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
    "effect_document",
]


def shader_templates():
    root = files("niri_fx").joinpath("shaders")
    noise = root.joinpath("noise.glsl").read_text().rstrip()
    edge_color = root.joinpath("edge-color.glsl").read_text().rstrip()
    templates = {
        "dissolve": root.joinpath("dissolve.glsl").read_text(),
        "iris": root.joinpath("iris.glsl").read_text(),
        "pixels": root.joinpath("pixels.glsl").read_text(),
        "wisps": root.joinpath("wisps.glsl").read_text(),
        "distortion": root.joinpath("distortion.glsl").read_text(),
        "classic": root.joinpath("fragments.glsl")
        .read_text()
        .replace("@ACTION_ENTRY@", root.joinpath("fragments-entry.glsl").read_text().rstrip()),
        "gravity": root.joinpath("gravity.glsl")
        .read_text()
        .replace("@ACTION_ENTRY@", root.joinpath("gravity-entry.glsl").read_text().rstrip()),
        "resize": root.joinpath("resize.glsl").read_text(),
        "slices": root.joinpath("slices.glsl")
        .read_text()
        .replace("@ACTION_ENTRY@", root.joinpath("slices-entry.glsl").read_text().rstrip()),
        "elastic": root.joinpath("elastic.glsl")
        .read_text()
        .replace("@ACTION_ENTRY@", root.joinpath("elastic-entry.glsl").read_text().rstrip()),
        "varied": root.joinpath("varied.glsl")
        .read_text()
        .replace("@ACTION_ENTRY@", root.joinpath("varied-entry.glsl").read_text().rstrip()),
    }
    return {
        name: source.replace("@NOISE@", noise).replace("@EDGE_COLOR@", edge_color)
        for name, source in templates.items()
    }


def shader(effect, opening):
    template = shader_templates()[
        effect.family
        if effect.family != "fragments"
        else "varied"
        if effect.varied
        else "classic"
        if effect.classic
        else "gravity"
    ]
    return _expand(template, effect, opening)


def resize_shader(effect):
    if not FAMILIES[effect.family]["resize"]:
        raise ValueError(f"The {effect.family} family does not support resize")
    return _expand(shader_templates()["resize"], effect, False)


def movement_shader(effect):
    """Experimental API: emit only for the pinned patched compositor."""
    if not FAMILIES[effect.family]["movement"]:
        raise ValueError(f"The {effect.family} family does not support experimental movement")
    renderer = (
        "elastic"
        if effect.family == "elastic"
        else "varied"
        if effect.varied
        else "fragments"
        if effect.classic
        else "gravity"
    )
    source = _expand(
        files("niri_fx")
        .joinpath(f"shaders/{renderer}.glsl")
        .read_text()
        .replace("@ACTION_ENTRY@", ""),
        effect,
        False,
    )
    if effect.family == "elastic":
        return (
            source
            + """vec4 move_color(vec3 coords_geo, vec3 size_geo) {
    vec2 impulse = vec2(niri_move_delta.x < 0.0 ? -1.0 : 1.0,
                        niri_move_delta.y < 0.0 ? -1.0 : 1.0);
    return elastic_color(coords_geo, size_geo, niri_clamped_progress, 0.0, impulse);
}
"""
        )
    return (
        source
        + """vec4 move_color(vec3 coords_geo, vec3 size_geo) {
    float p = niri_clamped_progress;
    float breakup = 0.64 * pow(sin(3.14159265359 * p), 2.0);
    if (p <= 0.0 || p >= 1.0) breakup = 0.0;
    return fragments_color(coords_geo, size_geo, breakup);
}
"""
    )


def _expand(template, effect, opening):
    tokens = shader_tokens(effect, PARAMETERS)
    tokens.update(
        {
            "ELASTIC_ORIGIN_X": glsl_number(ELASTIC_ANCHORS[effect.elastic_anchor][0]),
            "ELASTIC_ORIGIN_Y": glsl_number(ELASTIC_ANCHORS[effect.elastic_anchor][1]),
            "ENTRY": "open_color" if opening else "close_color",
            "PROGRESS": "1.0 - niri_clamped_progress" if opening else "niri_clamped_progress",
        }
    )
    return re.sub(r"@([A-Z_]+)@", lambda match: tokens[match[1]], template)


def animation_types(effect):
    from .profiles import Profile

    if isinstance(effect, Profile):
        return effect.animation_types()
    types = {
        name: {"duration-ms": duration, "curve": "linear", "custom-shader": shader(effect, opening)}
        for name, duration, opening in (
            ("window-open", effect.open_ms, True),
            ("window-close", effect.close_ms, False),
        )
    }

    if effect.resize:
        types["window-resize"] = {
            "duration-ms": effect.resize_ms,
            "curve": "linear",
            "custom-shader": resize_shader(effect),
        }
    return types


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
    from .profiles import Profile

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


def effect_document(name, effect):
    """Serialize the current preset format; older formats are not supported."""
    from .profiles import Profile

    if isinstance(effect, Profile):
        return effect.document(name)
    return {"schema": PRESET_SCHEMA, "name": name, "effect": asdict(effect)}
