"""Validated effect families shared by Studio, Niri exports and shell adapters."""

from dataclasses import dataclass

from .parameters import parameter, specifications, validate_parameters

GRAVITIES = ("none", "down", "up", "left", "right", "center", "space")
ROTATIONS = ("none", "random", "gravity")
RELEASES = (
    "together",
    "left",
    "right",
    "up",
    "down",
    "center",
    "edges",
    "diagonal",
    "checkerboard",
)
RESIZE_MODES = ("full", "edge", "soft")
SLICE_DIRECTIONS = ("outward", "alternate", "positive", "negative", "random")
SLICE_ORDERS = ("forward", "reverse", "center", "edges", "random", "together")
ELASTIC_AXES = ("both", "horizontal", "vertical")
ELASTIC_ANCHORS = {
    "center": (0.5, 0.5),
    "top": (0.5, 0.0),
    "bottom": (0.5, 1.0),
    "left": (0.0, 0.5),
    "right": (1.0, 0.5),
    "top-left": (0.0, 0.0),
    "top-right": (1.0, 0.0),
    "bottom-left": (0.0, 1.0),
    "bottom-right": (1.0, 1.0),
}
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
FAMILIES.update(
    {
        name: {
            "label": name.title(),
            "open_close": True,
            "resize": False,
            "movement": False,
            "concept": False,
        }
        for name in ("dissolve", "iris", "pixels", "wisps", "distortion")
    }
)


@dataclass(frozen=True)
class Effect:
    """Immutable, validated parameter data for every renderer.

    The flat schema keeps round trips stable when Studio switches families;
    irrelevant fields remain stored but never select unsupported capabilities.
    Add controls through parameter metadata, not parallel CLI/UI field lists.
    """

    family: str = parameter(
        "fragments", label="Effect family", families=(), group="general", choices=tuple(FAMILIES)
    )
    slice_count: int = parameter(
        12,
        label="Slice count",
        families=("slices",),
        group="slices",
        limits=(2, 48),
        token="SLICE_COUNT",
        glsl_type="int",
        integer=True,
    )
    slice_angle: float = parameter(
        0,
        label="Slice angle",
        families=("slices",),
        group="slices",
        limits=(-90, 90),
        token="SLICE_ANGLE",
        unit="°",
    )
    slice_distance: float = parameter(
        220,
        label="Travel distance",
        families=("slices",),
        group="slices",
        limits=(0, 600),
        token="SLICE_DISTANCE",
        unit=" px",
    )
    slice_stagger: float = parameter(
        0.25,
        label="Release stagger",
        families=("slices",),
        group="slices",
        limits=(0, 0.75),
        token="SLICE_STAGGER",
    )
    slice_rotation: float = parameter(
        0,
        label="Strip rotation",
        families=("slices",),
        group="slices",
        limits=(-60, 60),
        token="SLICE_ROTATION",
        unit="°",
    )
    slice_direction: str = parameter(
        "outward",
        label="Travel direction",
        families=("slices",),
        group="slices",
        choices=SLICE_DIRECTIONS,
        token="SLICE_DIRECTION",
    )
    slice_order: str = parameter(
        "forward",
        label="Release order",
        families=("slices",),
        group="slices",
        choices=SLICE_ORDERS,
        token="SLICE_ORDER",
    )
    slice_travel_variation: float = parameter(
        0.1,
        label="Travel variation",
        families=("slices",),
        group="variation",
        limits=(0, 1),
        token="SLICE_TRAVEL_VARIATION",
    )
    slice_rotation_variation: float = parameter(
        0,
        label="Rotation variation",
        families=("slices",),
        group="variation",
        limits=(0, 1),
        token="SLICE_ROTATION_VARIATION",
    )
    slice_pivot: float = parameter(
        0,
        label="Hinge position",
        families=("slices",),
        group="slices",
        limits=(-1, 1),
        token="SLICE_PIVOT",
    )
    slice_collapse: float = parameter(
        0,
        label="Width collapse",
        families=("slices",),
        group="slices",
        limits=(0, 1),
        token="SLICE_COLLAPSE",
    )
    fragment_shrink: float = parameter(
        0,
        label="Extra piece shrink",
        families=("fragments",),
        group="fragments",
        limits=(0, 1),
        token="FRAGMENT_SHRINK",
    )
    fragment_roundness: float = parameter(
        0,
        label="Rounded corners",
        families=("fragments",),
        group="fragments",
        limits=(0, 1),
        token="FRAGMENT_ROUNDNESS",
    )
    size_variation: float = parameter(
        0,
        label="Unequal piece sizes",
        families=("fragments", "slices"),
        group="variation",
        limits=(0, 1),
        token="SIZE_VARIATION",
    )
    direction_variation: float = parameter(
        0,
        label="Direction variation",
        families=("fragments", "slices"),
        group="variation",
        limits=(0, 1),
        token="DIRECTION_VARIATION",
    )
    wave_strength: float = parameter(
        0,
        label="Wave strength",
        families=("fragments", "slices"),
        group="variation",
        limits=(0, 1),
        token="WAVE_STRENGTH",
    )
    wave_frequency: float = parameter(
        1,
        label="Wave frequency",
        families=("fragments", "slices"),
        group="variation",
        limits=(0.25, 4),
        token="WAVE_FREQUENCY",
        unit=" cycles",
    )
    wave_speed: float = parameter(
        1,
        label="Wave speed",
        families=("fragments", "slices"),
        group="variation",
        limits=(0, 4),
        token="WAVE_SPEED",
        unit=" cycles",
    )
    elastic_strength: float = parameter(
        0.7,
        label="Wobble strength",
        families=("elastic",),
        group="elastic",
        limits=(0, 1),
        token="ELASTIC_STRENGTH",
    )
    elastic_frequency: float = parameter(
        2,
        label="Spring oscillations",
        families=("elastic",),
        group="elastic",
        limits=(1, 5),
        token="ELASTIC_FREQUENCY",
        unit=" cycles",
    )
    elastic_damping: float = parameter(
        2,
        label="Damping",
        families=("elastic",),
        group="elastic",
        limits=(0, 8),
        token="ELASTIC_DAMPING",
    )
    elastic_axis: str = parameter(
        "both",
        label="Wobble axis",
        families=("elastic",),
        group="elastic",
        choices=ELASTIC_AXES,
        token="ELASTIC_AXIS",
    )
    elastic_twist: float = parameter(
        0,
        label="Spring twist",
        families=("elastic",),
        group="elastic",
        limits=(-90, 90),
        token="ELASTIC_TWIST",
        unit="°",
    )
    elastic_stretch: float = parameter(
        0,
        label="Extra stretching",
        families=("elastic",),
        group="elastic",
        limits=(0, 1),
        token="ELASTIC_STRETCH",
    )
    elastic_ripple: float = parameter(
        1,
        label="Spatial bend frequency",
        families=("elastic",),
        group="elastic",
        limits=(0.5, 4),
        token="ELASTIC_RIPPLE",
        unit="×",
    )
    elastic_anchor: str = parameter(
        "center",
        label="Transform origin",
        families=("elastic",),
        group="elastic",
        choices=tuple(ELASTIC_ANCHORS),
    )
    tile_size: float = parameter(
        28,
        label="Square size",
        families=("fragments",),
        group="fragments",
        limits=(8, 128),
        token="TILE",
        unit=" px",
    )
    scatter: float = parameter(
        125,
        label="Initial spread",
        families=("fragments",),
        group="fragments",
        limits=(0, 240),
        token="SCATTER",
        unit=" px",
    )
    open_ms: int = parameter(
        520,
        label="Opening time",
        families=(),
        group="timing",
        limits=(100, 1500),
        unit=" ms",
        integer=True,
    )
    close_ms: int = parameter(
        480,
        label="Closing time",
        families=(),
        group="timing",
        limits=(100, 1500),
        unit=" ms",
        integer=True,
    )
    gravity: str = parameter(
        "space",
        label="Gravity direction",
        families=("fragments",),
        group="fragments",
        choices=GRAVITIES,
        token="GRAVITY",
    )
    gravity_strength: float = parameter(
        0.7,
        label="Gravity strength",
        families=("fragments",),
        group="fragments",
        limits=(0, 3),
        token="STRENGTH",
        unit="×",
    )
    particles: int = parameter(
        720,
        label="Particles, approximately",
        families=("fragments",),
        group="fragments",
        limits=(0, 4096),
        token="PARTICLES",
        integer=True,
    )
    rotation: str = parameter(
        "random",
        label="Particle rotation",
        families=("fragments",),
        group="fragments",
        choices=ROTATIONS,
        token="ROTATION",
    )
    spin: float = parameter(
        180,
        label="Spin / alignment limit",
        families=("fragments",),
        group="fragments",
        limits=(0, 720),
        token="SPIN",
        unit="°",
    )
    swirl: float = parameter(
        0,
        label="Orbit around center",
        families=("fragments",),
        group="fragments",
        limits=(-360, 360),
        token="SWIRL",
        unit="°",
    )
    dispersion: float = parameter(
        0.7,
        label="Path dispersion",
        families=("fragments",),
        group="fragments",
        limits=(0, 1),
        token="DISPERSION",
    )
    stagger: float = parameter(
        0.18,
        label="Release stagger",
        families=("fragments",),
        group="fragments",
        limits=(0, 0.4),
        token="STAGGER",
    )
    resize: bool = parameter(False, label="Resize", families=(), group="resize")
    resize_ms: int = parameter(
        450,
        label="Resize time",
        families=("fragments",),
        group="resize",
        limits=(100, 1500),
        unit=" ms",
        integer=True,
    )
    resize_strength: float = parameter(
        0.65,
        label="Resize breakup",
        families=("fragments",),
        group="resize",
        limits=(0, 1),
        token="RESIZE",
    )
    release: str = parameter(
        "together",
        label="Release pattern",
        families=("fragments",),
        group="fragments",
        choices=RELEASES,
        token="RELEASE",
    )
    wave_span: float = parameter(
        0.55,
        label="Wave separation",
        families=("fragments",),
        group="fragments",
        limits=(0, 0.7),
        token="WAVE_SPAN",
    )
    origin_x: float = parameter(
        0.5,
        label="Burst center · horizontal",
        families=("fragments",),
        group="fragments",
        limits=(0, 1),
        token="ORIGIN_X",
    )
    origin_y: float = parameter(
        0.5,
        label="Burst center · vertical",
        families=("fragments",),
        group="fragments",
        limits=(0, 1),
        token="ORIGIN_Y",
    )
    resize_mode: str = parameter(
        "full",
        label="Resize style",
        families=("fragments",),
        group="resize",
        choices=RESIZE_MODES,
        token="RESIZE_MODE",
    )

    dissolve_scale: float = parameter(
        24,
        label="Noise size",
        families=("dissolve",),
        group="dissolve",
        limits=(4, 160),
        unit=" px",
        token="DISSOLVE_SCALE",
    )
    dissolve_softness: float = parameter(
        0.06,
        label="Dissolve softness",
        families=("dissolve",),
        group="dissolve",
        limits=(0.005, 0.25),
        token="DISSOLVE_SOFTNESS",
    )
    dissolve_bias: float = parameter(
        0.5,
        label="Directional influence",
        families=("dissolve",),
        group="dissolve",
        limits=(0, 1),
        token="DISSOLVE_BIAS",
    )
    dissolve_direction: str = parameter(
        "none",
        label="Dissolve direction",
        families=("dissolve",),
        group="dissolve",
        choices=("none", "left", "right", "up", "down", "center"),
        token="DISSOLVE_DIRECTION",
    )
    edge_width: float = parameter(
        0.08,
        label="Edge band width",
        families=("dissolve",),
        group="dissolve",
        limits=(0, 0.3),
        token="EDGE_WIDTH",
    )
    edge_hue: float = parameter(
        30,
        label="Edge color hue",
        families=("dissolve", "wisps"),
        group="color",
        limits=(0, 360),
        unit="°",
        token="EDGE_HUE",
    )
    iris_shape: str = parameter(
        "circle",
        label="Reveal shape",
        families=("iris",),
        group="iris",
        choices=("circle", "diamond", "square"),
        token="IRIS_SHAPE",
    )
    iris_direction: str = parameter(
        "inward",
        label="Closing direction",
        families=("iris",),
        group="iris",
        choices=("inward", "outward"),
        token="IRIS_DIRECTION",
    )
    iris_softness: float = parameter(
        0.04,
        label="Reveal softness",
        families=("iris",),
        group="iris",
        limits=(0.005, 0.3),
        token="IRIS_SOFTNESS",
    )
    iris_twist: float = parameter(
        0,
        label="Mask rotation",
        families=("iris",),
        group="iris",
        limits=(-180, 180),
        unit="°",
        token="IRIS_TWIST",
    )
    iris_x: float = parameter(
        0.5,
        label="Reveal center · horizontal",
        families=("iris",),
        group="iris",
        limits=(0, 1),
        token="IRIS_X",
    )
    iris_y: float = parameter(
        0.5,
        label="Reveal center · vertical",
        families=("iris",),
        group="iris",
        limits=(0, 1),
        token="IRIS_Y",
    )

    dissolve_detail: float = parameter(
        0.55,
        label="Fine erosion detail",
        families=("dissolve",),
        group="dissolve",
        limits=(0, 1),
        token="DISSOLVE_DETAIL",
    )
    dissolve_flow: float = parameter(
        0.25,
        label="Noise flow",
        families=("dissolve",),
        group="dissolve",
        limits=(0, 2),
        token="DISSOLVE_FLOW",
    )
    edge_saturation: float = parameter(
        0,
        label="Edge saturation",
        families=("dissolve", "wisps"),
        group="color",
        limits=(0, 1),
        token="EDGE_SATURATION",
    )
    edge_brightness: float = parameter(
        1,
        label="Edge brightness",
        families=("dissolve", "wisps"),
        group="color",
        limits=(0, 1),
        token="EDGE_BRIGHTNESS",
    )
    edge_char: float = parameter(
        0.65,
        label="Charcoal band",
        families=("dissolve",),
        group="dissolve",
        limits=(0, 1),
        token="EDGE_CHAR",
    )
    pixel_mode: str = parameter(
        "wipe",
        label="Pixel motion",
        families=("pixels",),
        group="pixels",
        choices=("wipe", "pixelate", "dust"),
        token="PIXEL_MODE",
    )
    pixel_size: float = parameter(
        12,
        label="Pixel size",
        families=("pixels",),
        group="pixels",
        limits=(4, 64),
        token="PIXEL_SIZE",
        unit=" px",
    )
    pixel_direction: str = parameter(
        "center",
        label="Wipe direction",
        families=("pixels",),
        group="pixels",
        choices=("center", "edges", "left", "right", "up", "down"),
        token="PIXEL_DIRECTION",
    )
    pixel_randomness: float = parameter(
        0.22,
        label="Release randomness",
        families=("pixels",),
        group="pixels",
        limits=(0, 1),
        token="PIXEL_RANDOMNESS",
    )
    pixel_softness: float = parameter(
        0.12,
        label="Pixel fade softness",
        families=("pixels",),
        group="pixels",
        limits=(0.01, 0.4),
        token="PIXEL_SOFTNESS",
    )
    pixel_travel: float = parameter(
        6,
        label="Dust travel in cells",
        families=("pixels",),
        group="pixels",
        limits=(0, 8),
        token="PIXEL_TRAVEL",
    )
    pixel_wind: str = parameter(
        "right",
        label="Dust wind",
        families=("pixels",),
        group="pixels",
        choices=("right", "left", "up", "down"),
        token="PIXEL_WIND",
    )
    pixel_x: float = parameter(
        0.5,
        label="Pixel origin · horizontal",
        families=("pixels",),
        group="pixels",
        limits=(0, 1),
        token="PIXEL_X",
    )
    pixel_y: float = parameter(
        0.5,
        label="Pixel origin · vertical",
        families=("pixels",),
        group="pixels",
        limits=(0, 1),
        token="PIXEL_Y",
    )
    wisp_scale: float = parameter(
        48,
        label="Wisp size",
        families=("wisps",),
        group="wisps",
        limits=(12, 128),
        token="WISP_SCALE",
        unit=" px",
    )
    wisp_strands: float = parameter(
        3,
        label="Thread density",
        families=("wisps",),
        group="wisps",
        limits=(1, 10),
        token="WISP_STRANDS",
    )
    wisp_curl: float = parameter(
        0.65,
        label="Curl strength",
        families=("wisps",),
        group="wisps",
        limits=(0, 2),
        token="WISP_CURL",
    )
    wisp_drift: float = parameter(
        110,
        label="Drift distance",
        families=("wisps",),
        group="wisps",
        limits=(0, 240),
        token="WISP_DRIFT",
        unit=" px",
    )
    wisp_angle: float = parameter(
        -90,
        label="Drift direction",
        families=("wisps",),
        group="wisps",
        limits=(-180, 180),
        token="WISP_ANGLE",
        unit="°",
    )
    wisp_speed: float = parameter(
        1.2,
        label="Flow speed",
        families=("wisps",),
        group="wisps",
        limits=(0, 4),
        token="WISP_SPEED",
    )
    wisp_glow: float = parameter(
        0.55,
        label="Thread highlight",
        families=("wisps",),
        group="wisps",
        limits=(0, 1),
        token="WISP_GLOW",
    )
    wisp_softness: float = parameter(
        0.1,
        label="Thread softness",
        families=("wisps",),
        group="wisps",
        limits=(0.01, 0.3),
        token="WISP_SOFTNESS",
    )
    distortion_mode: str = parameter(
        "shockwave",
        label="Distortion pattern",
        families=("distortion",),
        group="distortion",
        choices=("shockwave", "ripple", "wave"),
        token="DISTORTION_MODE",
    )
    distortion_strength: float = parameter(
        28,
        label="Displacement",
        families=("distortion",),
        group="distortion",
        limits=(0, 80),
        token="DISTORTION_STRENGTH",
        unit=" px",
    )
    distortion_wavelength: float = parameter(
        70,
        label="Wavelength",
        families=("distortion",),
        group="distortion",
        limits=(12, 240),
        token="DISTORTION_WAVELENGTH",
        unit=" px",
    )
    distortion_width: float = parameter(
        100,
        label="Shock front width",
        families=("distortion",),
        group="distortion",
        limits=(10, 240),
        token="DISTORTION_WIDTH",
        unit=" px",
    )
    distortion_cycles: float = parameter(
        1.5,
        label="Wave travel cycles",
        families=("distortion",),
        group="distortion",
        limits=(0.25, 4),
        token="DISTORTION_CYCLES",
    )
    distortion_falloff: float = parameter(
        1,
        label="Distance falloff",
        families=("distortion",),
        group="distortion",
        limits=(0, 4),
        token="DISTORTION_FALLOFF",
    )
    distortion_angle: float = parameter(
        0,
        label="Planar wave angle",
        families=("distortion",),
        group="distortion",
        limits=(-180, 180),
        token="DISTORTION_ANGLE",
        unit="°",
    )
    distortion_fade: float = parameter(
        0.3,
        label="Fade starts at",
        families=("distortion",),
        group="distortion",
        limits=(0.15, 0.85),
        token="DISTORTION_FADE",
    )
    distortion_x: float = parameter(
        0.5,
        label="Wave origin · horizontal",
        families=("distortion",),
        group="distortion",
        limits=(0, 1),
        token="DISTORTION_X",
    )
    distortion_y: float = parameter(
        0.5,
        label="Wave origin · vertical",
        families=("distortion",),
        group="distortion",
        limits=(0, 1),
        token="DISTORTION_Y",
    )

    def __post_init__(self):
        validate_parameters(self, PARAMETERS)
        if self.resize and not FAMILIES[self.family]["resize"]:
            raise ValueError(f"The {self.family} family does not support resize; use --no-resize")
        if self.particles and self.particles < 16:
            raise ValueError("particles must be 0 (tile size mode) or between 16 and 4096")

    @property
    def varied(self):
        """Variation requires the wider inverse-search renderer."""
        return bool(self.size_variation or self.direction_variation or self.wave_strength)

    @property
    def classic(self):
        """Only this restricted field can use the smallest analytic lookup."""
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
            and not self.fragment_shrink
            and not self.fragment_roundness
        )


PARAMETERS = specifications(Effect)
LIMITS = {name: spec["limits"] for name, spec in PARAMETERS.items() if spec["limits"]}
