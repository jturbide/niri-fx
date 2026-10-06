"""Public effect catalog and action-specific shader generation."""

import math
import re
from dataclasses import asdict
from functools import lru_cache
from importlib.resources import files

from .fragment_motion import FragmentMotionSettings
from .fragment_motion import render_node as fragment_node
from .model import (
    ELASTIC_ANCHORS,
    ELASTIC_AXES,
    FAMILIES,
    FRAGMENT_SHAPES,
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
from .pointer import PointerWobble, render_node
from .presets import PRESETS
from .profiles import Profile, action_mode

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
    "fragment_motion_eligible",
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
    "resize-shaped": "resize-shaped",
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
        "RESIZE_STATE": "resize-state",
        "FRAGMENT_SHAPES": "fragment-shapes",
    }.items():
        if f"@{token}@" in source:
            source = source.replace(
                f"@{token}@", root.joinpath(f"{snippet}.glsl").read_text().rstrip()
            )
    return source


@lru_cache(maxsize=1)
def shader_templates():
    """Python and offline Studio expand the same assembled template strings."""
    templates = {name: _template(filename) for name, filename in TEMPLATE_FILES.items()}
    root = files("niri_fx").joinpath("shaders")
    for renderer in (
        "classic",
        "gravity",
        "varied",
        "shaped",
        "slices",
        "elastic",
        "pixels",
        "distortion",
    ):
        family = "fragments" if renderer in {"classic", "gravity", "varied", "shaped"} else renderer
        entry = (
            root.joinpath(
                "movement-elastic-entry.glsl" if family == "elastic" else "movement-entry.glsl"
            )
            .read_text()
            .replace("@FUNCTION@", family)
        )
        templates[f"move-{renderer}"] = _template(TEMPLATE_FILES[renderer], entry)
        if renderer in {"classic", "gravity"}:
            # The native extension owns its forward mesh and per-cell state.
            # Older compositors and Studio use the exact timed entry below.
            continuous = root.joinpath("fragment-motion.glsl").read_text()
            templates[f"move-{renderer}-continuous"] = _template(
                TEMPLATE_FILES[renderer], continuous + "\n" + entry
            )
    return templates


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
    renderer = (
        "resize-shaped"
        if effect.family == "fragments" and effect.shaped_resize
        else RESIZE_TEMPLATES[effect.family]
    )
    return _expand(shader_templates()[renderer], effect, False)


def movement_shader(effect, *, continuous_fragments=True):
    """Experimental API: emit only for the pinned patched compositor."""
    if not FAMILIES[effect.family]["movement"]:
        raise ValueError(f"The {effect.family} family does not support experimental movement")
    suffix = "-continuous" if continuous_fragments and fragment_motion_eligible(effect) else ""
    return _expand(shader_templates()[f"move-{renderer_name(effect)}{suffix}"], effect, False)


def fragment_motion_eligible(effect):
    """Limit the native mesh prototype to an unmodified square lattice.

    Unsupported materials keep their existing timed renderer. Shape mixtures,
    waves and variable cell sizes need a matching mesh material before they can
    advertise this contract. The native block owns its motion controls; a zero
    portable movement strength still means no continuous deformation.
    """
    return (
        effect.family == "fragments"
        and effect.movement_strength > 0
        and effect.particles <= 4096
        and effect.effective_shape == "square"
        and not effect.mixed_shapes
        and not effect.fragment_orientation
        and not effect.fragment_roundness
        and not effect.fragment_shrink
        and not effect.size_variation
        and not effect.direction_variation
        and not effect.wave_strength
        and effect.rotation in {"none", "random"}
        and effect.release == "together"
    )


def shape_search_radius(effect, *, resizing=False):
    """Bound inverse cell lookup despite spin, aspect, wandering and waves.

    Resize allows .4 tiles of local drift and no waves. Open/close and movement
    use the flight bound below; both branches search in their source lattice.

    A source piece fits inside `radius * tile`. Inverse flight adds at most .72
    tiles of wander; undoing the wave expands distances by at most 1.45. Rotating
    the lattice preserves lengths and undoing its aspect adds `stretch`. Hex
    axial coordinate rows have norm 2/3. Floor the extreme possible coordinates
    relative to each cell's centroid. Match this bound in effect-core.js;
    shader parity tests enforce it.
    """
    shape = effect.effective_shape
    aspect = 1 if shape in {"square", "circle"} else effect.fragment_aspect
    stretch = math.sqrt(max(aspect, 1 / aspect))
    radius = 0.5 * math.sqrt(aspect + 1 / aspect)
    low = high = 0.5
    if shape == "triangle" or (effect.mixed_shapes and effect.fragment_secondary == "triangle"):
        radius = math.sqrt(max(4 * aspect + 1 / aspect, aspect + 4 / aspect)) / 3
        low, high = 1 / 3, 2 / 3
    axial = 1
    if shape == "hexagon" and not effect.mixed_shapes:
        radius, axial = stretch, 2 / 3
        low = high = 0
    reach = radius + (0.4 if resizing else 0.72 * effect.dispersion)
    if not resizing and effect.wave_strength:
        reach *= 1.45
    reach = reach * stretch * axial + 0.00001
    return max(math.floor(reach + high), math.ceil(reach - low))


def _expand(template, effect, opening):
    tokens = shader_tokens(effect, PARAMETERS)
    tokens.update(
        {
            "VARIED_RADIUS": "2" if effect.wave_strength == 0 else "3",
            "SHAPED_RADIUS": str(shape_search_radius(effect)),
            "SHAPED_RESIZE_RADIUS": str(shape_search_radius(effect, resizing=True)),
            "SHAPED_PARTS": "2"
            if effect.effective_shape == "triangle"
            or (effect.mixed_shapes and effect.fragment_secondary == "triangle")
            else "1",
            "FRAGMENT_SHAPE": str(FRAGMENT_SHAPES.index(effect.effective_shape)),
            "FRAGMENT_MIX": glsl_number(effect.fragment_mix if effect.mixed_shapes else 0),
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


def animation_types(
    effect, *, movement=False, pointer=False, swap=False, continuous_fragments=True
):
    """Emit requested overrides; native movement and pointer use separate opt-ins.

    Profiles opt into resize with a separate slot. Single styles use their
    explicit resize flag. Omitting the key lets the base Niri config keep control.
    """
    selected = (
        {action: getattr(effect, action) for action in ("open", "close", "resize")}
        if isinstance(effect, Profile)
        else {"open": effect, "close": effect, "resize": effect if effect.resize else None}
    )
    result = {}
    for action, style in selected.items():
        if style is None:
            continue
        if style == "off":
            result[f"window-{action}"] = {"off": True}
        else:
            result[f"window-{action}"] = {
                "duration-ms": getattr(style, f"{action}_ms"),
                "curve": "linear",
                "custom-shader": resize_shader(style)
                if action == "resize"
                else shader(style, action == "open"),
            }
    if movement:
        style = effect.movement if isinstance(effect, Profile) else effect
        if style is None:
            raise ValueError("The profile must explicitly choose a movement action")
        result["window-movement"] = (
            {"off": True}
            if style == "off"
            else {
                "duration-ms": style.movement_ms,
                "curve": "linear",
                "custom-shader": movement_shader(style, continuous_fragments=continuous_fragments),
            }
        )
        if not pointer:
            result["window-movement"]["preserve-pointer"] = True
        if (
            continuous_fragments
            and isinstance(effect, Profile)
            and effect.fragment_motion is not None
            and isinstance(style, Effect)
            and fragment_motion_eligible(style)
        ):
            result["window-movement"]["fragment-motion"] = asdict(effect.fragment_motion)
    if pointer:
        if not isinstance(effect, Profile) or effect.pointer is None:
            raise ValueError("The profile must explicitly choose pointer settings")
        # Native contract 2 merges these siblings explicitly. Niri otherwise
        # replaces the entire animation node when a later include supplies it.
        native = result.setdefault("window-movement", {"preserve-movement": True})
        native["pointer-wobble"] = asdict(effect.pointer)
    if swap:
        if not isinstance(effect, Profile) or effect.swap is None:
            raise ValueError("The profile must explicitly choose a swap action")
        style = effect.swap
        result["window-swap"] = (
            {"off": True}
            if style == "off"
            else {
                "duration-ms": style.movement_ms,
                "curve": "linear",
                # Swap overrides use the timed material ABI. Pointer fragments
                # retain their independent movement response and source mesh.
                "custom-shader": movement_shader(style, continuous_fragments=False),
            }
        )
    if isinstance(effect, Profile) and effect.motion:
        for name, settings in effect.motion.animation_types().items():
            result.setdefault(name, {}).update(settings)
    return result


def render_kdl(effect, *, movement=False, pointer=False, swap=False, continuous_fragments=True):
    parts = ["// Generated by NiriFX. Include after your base animation settings.", "animations {"]
    for name, spec in animation_types(
        effect,
        movement=movement,
        pointer=pointer,
        swap=swap,
        continuous_fragments=continuous_fragments,
    ).items():
        parts.append(f"    {name} {{")
        for flag in ("off", "preserve-movement", "preserve-pointer"):
            if spec.get(flag):
                parts.append(f"        {flag}")
        if "spring" in spec:
            settings = " ".join(
                f"{key}={int(value) if key == 'stiffness' else glsl_number(value)}"
                for key, value in zip(
                    ("damping-ratio", "stiffness", "epsilon"), spec["spring"], strict=True
                )
            )
            parts.append(f"        spring {settings}")
        if "custom-shader" in spec:
            parts.extend(
                [
                    f"        duration-ms {int(spec['duration-ms'])}",
                    '        curve "linear"',
                    '        custom-shader r"',
                    spec["custom-shader"].rstrip(),
                    '        "',
                ]
            )
        if "pointer-wobble" in spec:
            parts.append(render_node(PointerWobble(**spec["pointer-wobble"])).rstrip())
        if "fragment-motion" in spec:
            parts.append(fragment_node(FragmentMotionSettings(**spec["fragment-motion"])).rstrip())
        parts.append("    }")
    return "\n".join([*parts, "}", ""])


def preset_description(effect):
    if isinstance(effect, Profile):
        return (
            "; ".join(
                f"{action.title()}: {style.family if isinstance(style, Effect) else action_mode(style)}"
                for action in ("open", "close", "resize", "movement", "swap")
                for style in (getattr(effect, action),)
            )
            + "."
            + (" Coordinated desktop springs." if effect.motion else "")
        )
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
