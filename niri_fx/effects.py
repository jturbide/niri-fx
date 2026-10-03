"""Validated effect families shared by Studio, Niri exports and shell adapters."""

import math
from dataclasses import asdict, dataclass
from importlib.resources import files

GRAVITIES = ("none", "down", "up", "left", "right", "center", "space")
ROTATIONS = ("none", "random", "gravity")
RELEASES = ("together", "left", "right", "up", "down")
RESIZE_MODES = ("full", "edge", "soft")
SLICE_DIRECTIONS = ("outward", "alternate", "positive", "negative", "random")
SLICE_ORDERS = ("forward", "reverse", "center", "edges", "random", "together")
ELASTIC_AXES = ("both", "horizontal", "vertical")
ELASTIC_FIELDS = ("elastic_strength", "elastic_frequency", "elastic_damping", "elastic_axis")
MOTION_FIELDS = (
    "size_variation",
    "direction_variation",
    "wave_strength",
    "wave_frequency",
    "wave_speed",
)
PRESET_SCHEMA = 3
FAMILIES = {
    "fragments": {
        "label": "Fragments",
        "open_close": True,
        "resize": True,
        "movement": True,
        "concept": True,
    },
    "slices": {
        "label": "Slices",
        "open_close": True,
        "resize": False,
        "movement": False,
        "concept": False,
    },
    "elastic": {
        "label": "Elastic",
        "open_close": True,
        "resize": False,
        "movement": True,
        "concept": False,
    },
}
FAMILY_FIELDS = (
    "family",
    "slice_count",
    "slice_angle",
    "slice_distance",
    "slice_stagger",
    "slice_rotation",
    "slice_direction",
    "slice_order",
    "slice_travel_variation",
    "slice_rotation_variation",
)
LIMITS = {
    "tile_size": (8, 128),
    "scatter": (0, 240),
    "open_ms": (100, 1500),
    "close_ms": (100, 1500),
    "gravity_strength": (0, 3),
    "particles": (0, 4096),
    "spin": (0, 720),
    "swirl": (-360, 360),
    "dispersion": (0, 1),
    "stagger": (0, 0.4),
    "resize_ms": (100, 1500),
    "resize_strength": (0, 1),
    "origin_x": (0, 1),
    "origin_y": (0, 1),
    "wave_span": (0, 0.7),
    "slice_count": (2, 48),
    "slice_angle": (-90, 90),
    "slice_distance": (0, 600),
    "slice_stagger": (0, 0.75),
    "slice_rotation": (-60, 60),
    "size_variation": (0, 1),
    "direction_variation": (0, 1),
    "wave_strength": (0, 1),
    "wave_frequency": (0.25, 4),
    "wave_speed": (0, 4),
    "slice_travel_variation": (0, 1),
    "slice_rotation_variation": (0, 1),
    "elastic_strength": (0, 1),
    "elastic_frequency": (1, 5),
    "elastic_damping": (0, 8),
}


@dataclass(frozen=True)
class Effect:
    family: str = "fragments"
    slice_count: int = 12
    slice_angle: float = 0
    slice_distance: float = 220
    slice_stagger: float = 0.25
    slice_rotation: float = 0
    slice_direction: str = "outward"
    slice_order: str = "forward"
    slice_travel_variation: float = 0.1
    slice_rotation_variation: float = 0
    size_variation: float = 0
    direction_variation: float = 0
    wave_strength: float = 0
    wave_frequency: float = 1
    wave_speed: float = 1
    elastic_strength: float = 0.7
    elastic_frequency: float = 2
    elastic_damping: float = 2
    elastic_axis: str = "both"
    tile_size: float = 28
    scatter: float = 125
    open_ms: int = 520
    close_ms: int = 480
    gravity: str = "space"
    gravity_strength: float = 0.7
    particles: int = 720
    rotation: str = "random"
    spin: float = 180
    swirl: float = 0
    dispersion: float = 0.7
    stagger: float = 0.18
    resize: bool = False
    resize_ms: int = 450
    resize_strength: float = 0.65
    release: str = "together"
    wave_span: float = 0.55
    origin_x: float = 0.5
    origin_y: float = 0.5
    resize_mode: str = "full"

    def __post_init__(self):
        for name, (low, high) in LIMITS.items():
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not low <= value <= high
            ):
                raise ValueError(f"{name} must be a finite number between {low} and {high}")
            if (name.endswith("_ms") or name in ("particles", "slice_count")) and int(
                value
            ) != value:
                raise ValueError(f"{name} must be a whole number")
        if not isinstance(self.resize, bool):
            raise ValueError("resize must be a boolean")
        if not isinstance(self.family, str) or self.family not in FAMILIES:
            raise ValueError(f"family must be one of {', '.join(FAMILIES)}")
        if self.slice_direction not in SLICE_DIRECTIONS:
            raise ValueError(f"slice_direction must be one of {', '.join(SLICE_DIRECTIONS)}")
        if self.slice_order not in SLICE_ORDERS:
            raise ValueError(f"slice_order must be one of {', '.join(SLICE_ORDERS)}")
        if self.elastic_axis not in ELASTIC_AXES:
            raise ValueError(f"elastic_axis must be one of {', '.join(ELASTIC_AXES)}")
        if self.resize and not FAMILIES[self.family]["resize"]:
            raise ValueError(f"The {self.family} family does not support resize; use --no-resize")
        if self.particles and self.particles < 16:
            raise ValueError("particles must be 0 (tile size mode) or between 16 and 4096")
        if self.gravity not in GRAVITIES:
            raise ValueError(f"gravity must be one of {', '.join(GRAVITIES)}")
        if self.rotation not in ROTATIONS:
            raise ValueError(f"rotation must be one of {', '.join(ROTATIONS)}")
        if self.release not in RELEASES:
            raise ValueError(f"release must be one of {', '.join(RELEASES)}")
        if self.resize_mode not in RESIZE_MODES:
            raise ValueError(f"resize_mode must be one of {', '.join(RESIZE_MODES)}")

    @property
    def varied(self):
        return bool(self.size_variation or self.direction_variation or self.wave_strength)

    @property
    def classic(self):
        return (
            self.gravity == "none"
            and not self.particles
            and self.rotation == "none"
            and self.swirl == 0
            and self.dispersion == 0
            and self.stagger == 0
            and self.release == "together"
            and self.origin_x == 0.5
            and self.origin_y == 0.5
        )


PRESETS = {
    "subtle": Effect(
        scatter=35,
        open_ms=360,
        close_ms=300,
        gravity="none",
        particles=360,
        spin=55,
        dispersion=0.3,
        stagger=0.1,
    ),
    "balanced": Effect(),
    "dramatic": Effect(
        scatter=180,
        open_ms=680,
        close_ms=600,
        gravity="space",
        gravity_strength=1.1,
        particles=1100,
        spin=260,
        dispersion=1,
        stagger=0.26,
    ),
    "explosion": Effect(
        scatter=240,
        open_ms=700,
        close_ms=680,
        gravity="space",
        gravity_strength=1.5,
        particles=1200,
        spin=300,
        dispersion=1,
        stagger=0.12,
    ),
    "implosion": Effect(
        scatter=30,
        open_ms=720,
        close_ms=680,
        gravity="center",
        gravity_strength=1.65,
        particles=1000,
        spin=260,
        dispersion=1,
        stagger=0.2,
    ),
    "earth": Effect(
        scatter=65,
        open_ms=600,
        close_ms=650,
        gravity="down",
        gravity_strength=1.0,
        particles=600,
        spin=190,
        dispersion=0.85,
        stagger=0.24,
    ),
    "black-hole": Effect(
        scatter=12,
        open_ms=680,
        close_ms=650,
        gravity="center",
        gravity_strength=1.3,
        particles=800,
        rotation="gravity",
        spin=200,
        swirl=30,
        dispersion=0.55,
        stagger=0.22,
    ),
    "space": Effect(
        scatter=100,
        open_ms=650,
        close_ms=650,
        gravity="space",
        gravity_strength=0.9,
        particles=650,
        spin=210,
        dispersion=0.95,
        stagger=0.28,
    ),
    "vortex": Effect(
        scatter=25,
        open_ms=720,
        close_ms=720,
        gravity="center",
        gravity_strength=1.15,
        particles=720,
        rotation="gravity",
        spin=240,
        swirl=160,
        dispersion=0.65,
        stagger=0.25,
    ),
    "confetti": Effect(
        scatter=115,
        open_ms=650,
        close_ms=720,
        gravity="down",
        gravity_strength=0.85,
        particles=1600,
        spin=480,
        dispersion=1,
        stagger=0.3,
    ),
    "updraft": Effect(
        scatter=60,
        open_ms=600,
        close_ms=640,
        gravity="up",
        gravity_strength=0.9,
        particles=600,
        rotation="gravity",
        spin=180,
        swirl=-25,
        dispersion=0.8,
        stagger=0.24,
    ),
    "directional-wave": Effect(
        scatter=90,
        open_ms=1000,
        close_ms=1000,
        gravity="up",
        gravity_strength=0.6,
        particles=900,
        spin=180,
        release="left",
        wave_span=0.6,
    ),
    "corner-burst": Effect(
        scatter=180,
        open_ms=780,
        close_ms=740,
        gravity="space",
        gravity_strength=1.1,
        particles=1200,
        spin=300,
        origin_x=0.15,
        origin_y=0.8,
        dispersion=0.8,
    ),
    "orbital-collapse": Effect(
        scatter=15,
        open_ms=1000,
        close_ms=1000,
        gravity="center",
        gravity_strength=1.5,
        particles=1400,
        rotation="gravity",
        spin=320,
        swirl=300,
        dispersion=0.8,
        stagger=0.25,
    ),
    "slide-apart": Effect(
        family="slices",
        slice_count=12,
        slice_direction="alternate",
        slice_distance=240,
        slice_stagger=0.22,
        open_ms=680,
        close_ms=640,
    ),
    "alternating-blinds": Effect(
        family="slices",
        slice_count=16,
        slice_angle=90,
        slice_direction="alternate",
        slice_rotation=16,
        slice_distance=180,
        slice_stagger=0.35,
        open_ms=820,
        close_ms=760,
    ),
    "diagonal-shear": Effect(
        family="slices",
        slice_count=10,
        slice_angle=-35,
        slice_direction="alternate",
        slice_rotation=5,
        slice_distance=280,
        slice_stagger=0.3,
        open_ms=760,
        close_ms=720,
    ),
    "split-curtain": Effect(
        family="slices",
        slice_count=12,
        slice_distance=240,
        slice_stagger=0.22,
        open_ms=680,
        close_ms=640,
    ),
    "ribbon-wave": Effect(
        family="slices",
        slice_count=18,
        slice_direction="alternate",
        slice_distance=150,
        slice_stagger=0.2,
        slice_rotation=4,
        wave_strength=1,
        wave_frequency=0.6,
        wave_speed=1.5,
        open_ms=1100,
        close_ms=1050,
    ),
    "shuffled-slats": Effect(
        family="slices",
        slice_count=22,
        slice_direction="random",
        slice_order="random",
        slice_distance=260,
        slice_stagger=0.45,
        slice_rotation=28,
        slice_rotation_variation=1,
        slice_travel_variation=0.7,
        size_variation=1,
        direction_variation=0.45,
        open_ms=1000,
        close_ms=950,
    ),
    "venetian-sweep": Effect(
        family="slices",
        slice_count=20,
        slice_angle=90,
        slice_direction="positive",
        slice_order="center",
        slice_distance=260,
        slice_stagger=0.6,
        slice_rotation=12,
        wave_strength=0.8,
        wave_frequency=0.75,
        wave_speed=1,
        open_ms=1050,
        close_ms=1000,
    ),
    "tidal-fragments": Effect(
        scatter=100,
        particles=550,
        gravity="up",
        gravity_strength=0.6,
        wave_strength=1,
        wave_frequency=0.5,
        wave_speed=1.5,
        size_variation=0.5,
        spin=100,
        open_ms=1050,
        close_ms=1000,
    ),
    "mosaic-burst": Effect(
        scatter=200,
        particles=480,
        gravity="space",
        gravity_strength=1.1,
        size_variation=1,
        direction_variation=0.35,
        spin=220,
        open_ms=820,
        close_ms=780,
    ),
    "chaotic-confetti": Effect(
        scatter=100,
        particles=1100,
        gravity="down",
        gravity_strength=1.1,
        size_variation=0.9,
        direction_variation=0.85,
        wave_strength=0.5,
        wave_frequency=1.5,
        wave_speed=2,
        spin=540,
        dispersion=1,
        open_ms=1000,
        close_ms=1050,
    ),
    "crosswind": Effect(
        scatter=145,
        particles=850,
        gravity="right",
        gravity_strength=0.8,
        direction_variation=0.35,
        wave_strength=0.7,
        wave_frequency=0.5,
        wave_speed=1,
        spin=240,
        open_ms=900,
        close_ms=850,
    ),
    "orbital-ribbons": Effect(
        scatter=90,
        particles=680,
        gravity="center",
        gravity_strength=0.6,
        swirl=240,
        wave_strength=1,
        wave_frequency=0.75,
        wave_speed=1,
        size_variation=0.65,
        rotation="gravity",
        spin=220,
        open_ms=1050,
        close_ms=1000,
    ),
    "spring-wobble": Effect(
        family="elastic",
        elastic_strength=0.85,
        elastic_frequency=2.5,
        elastic_damping=1.5,
        open_ms=1000,
        close_ms=900,
    ),
    "rubber-band": Effect(
        family="elastic",
        elastic_strength=1,
        elastic_frequency=1.25,
        elastic_damping=0.8,
        elastic_axis="horizontal",
        open_ms=850,
        close_ms=800,
    ),
    "jelly": Effect(
        family="elastic",
        elastic_strength=0.9,
        elastic_frequency=3.5,
        elastic_damping=0.6,
        open_ms=1200,
        close_ms=1100,
    ),
}


def shader_templates():
    root = files("niri_fx").joinpath("shaders")
    return {
        "classic": root.joinpath("fragments.glsl").read_text(),
        "gravity": root.joinpath("gravity.glsl").read_text(),
        "resize": root.joinpath("resize.glsl").read_text(),
        "slices": root.joinpath("slices.glsl").read_text(),
        "elastic": root.joinpath("elastic.glsl").read_text(),
        "varied": root.joinpath("varied.glsl").read_text(),
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
    source = shader(effect, False)
    source = source[: source.rfind("vec4 close_color")]
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
    return (
        template.replace("@TILE@", f"{effect.tile_size:.6f}")
        .replace("@SLICE_COUNT@", str(int(effect.slice_count)))
        .replace("@SLICE_ANGLE@", f"{effect.slice_angle:.6f}")
        .replace("@SLICE_DISTANCE@", f"{effect.slice_distance:.6f}")
        .replace("@SLICE_STAGGER@", f"{effect.slice_stagger:.6f}")
        .replace("@SLICE_ROTATION@", f"{effect.slice_rotation:.6f}")
        .replace("@SLICE_DIRECTION@", str(SLICE_DIRECTIONS.index(effect.slice_direction)))
        .replace("@SLICE_ORDER@", str(SLICE_ORDERS.index(effect.slice_order)))
        .replace("@SLICE_TRAVEL_VARIATION@", f"{effect.slice_travel_variation:.6f}")
        .replace("@SLICE_ROTATION_VARIATION@", f"{effect.slice_rotation_variation:.6f}")
        .replace("@SIZE_VARIATION@", f"{effect.size_variation:.6f}")
        .replace("@DIRECTION_VARIATION@", f"{effect.direction_variation:.6f}")
        .replace("@WAVE_STRENGTH@", f"{effect.wave_strength:.6f}")
        .replace("@WAVE_FREQUENCY@", f"{effect.wave_frequency:.6f}")
        .replace("@WAVE_SPEED@", f"{effect.wave_speed:.6f}")
        .replace("@ELASTIC_STRENGTH@", f"{effect.elastic_strength:.6f}")
        .replace("@ELASTIC_FREQUENCY@", f"{effect.elastic_frequency:.6f}")
        .replace("@ELASTIC_DAMPING@", f"{effect.elastic_damping:.6f}")
        .replace("@ELASTIC_AXIS@", str(ELASTIC_AXES.index(effect.elastic_axis)))
        .replace("@SCATTER@", f"{effect.scatter:.6f}")
        .replace("@PARTICLES@", f"{effect.particles:.6f}")
        .replace("@GRAVITY@", str(GRAVITIES.index(effect.gravity)))
        .replace("@STRENGTH@", f"{effect.gravity_strength:.6f}")
        .replace("@ROTATION@", str(ROTATIONS.index(effect.rotation)))
        .replace("@SPIN@", f"{effect.spin:.6f}")
        .replace("@SWIRL@", f"{effect.swirl:.6f}")
        .replace("@DISPERSION@", f"{effect.dispersion:.6f}")
        .replace("@RESIZE@", f"{effect.resize_strength:.6f}")
        .replace("@STAGGER@", f"{effect.stagger:.6f}")
        .replace("@RELEASE@", str(RELEASES.index(effect.release)))
        .replace("@WAVE_SPAN@", f"{effect.wave_span:.6f}")
        .replace("@ORIGIN_X@", f"{effect.origin_x:.6f}")
        .replace("@ORIGIN_Y@", f"{effect.origin_y:.6f}")
        .replace("@RESIZE_MODE@", str(RESIZE_MODES.index(effect.resize_mode)))
        .replace("@ENTRY@", "open_color" if opening else "close_color")
        .replace(
            "@PROGRESS@", "1.0 - niri_clamped_progress" if opening else "niri_clamped_progress"
        )
    )


def animation_types(effect):
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
    return {"schema": PRESET_SCHEMA, "name": name, "effect": asdict(effect)}
