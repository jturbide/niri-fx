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


# Family names map directly to files. Fragments has three implementations with
# different bounded lookup costs; resize has its own two-texture interface.
TEMPLATE_FILES = {
    "classic": "fragments",
    "gravity": "gravity",
    "varied": "varied",
    "resize": "resize",
    **{name: name for name in FAMILIES if name != "fragments"},
}


def shader_templates():
    """Assemble readable GLSL parts, leaving only parameter/action tokens.

    Shared helpers and action entry points expand first. Python and the browser
    then substitute the same catalog constants into these exact template strings.
    Read fresh resources so a source-checkout Studio can pick up shader edits.
    """
    root = files("niri_fx").joinpath("shaders")
    snippets = {
        "NOISE": root.joinpath("noise.glsl").read_text().rstrip(),
        "EDGE_COLOR": root.joinpath("edge-color.glsl").read_text().rstrip(),
    }
    result = {}
    for name, filename in TEMPLATE_FILES.items():
        source = root.joinpath(f"{filename}.glsl").read_text()
        if "@ACTION_ENTRY@" in source:
            source = source.replace(
                "@ACTION_ENTRY@", root.joinpath(f"{filename}-entry.glsl").read_text().rstrip()
            )
        for token, snippet in snippets.items():
            source = source.replace(f"@{token}@", snippet)
        result[name] = source
    return result


def renderer_name(effect):
    """Select a renderer without changing an effect's saved parameters."""
    if effect.family != "fragments":
        return effect.family
    if effect.varied:
        return "varied"
    return "classic" if effect.classic else "gravity"


def shader(effect, opening):
    """Opening reverses the same breakup path; independent profiles choose separately."""
    return _expand(shader_templates()[renderer_name(effect)], effect, opening)


def resize_shader(effect):
    if not FAMILIES[effect.family]["resize"]:
        raise ValueError(f"The {effect.family} family does not support resize")
    return _expand(shader_templates()["resize"], effect, False)


def movement_shader(effect):
    """Experimental API: emit only for the pinned patched compositor."""
    if not FAMILIES[effect.family]["movement"]:
        raise ValueError(f"The {effect.family} family does not support experimental movement")
    renderer = TEMPLATE_FILES[renderer_name(effect)]
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
