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
        for name in ("dissolve", "iris")
    }
)


@dataclass(frozen=True)
class Effect:
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
        label="Glowing edge width",
        families=("dissolve",),
        group="dissolve",
        limits=(0, 0.3),
        token="EDGE_WIDTH",
    )
    edge_hue: float = parameter(
        30,
        label="Edge color hue",
        families=("dissolve",),
        group="dissolve",
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

    def __post_init__(self):
        validate_parameters(self, PARAMETERS)
        if self.resize and not FAMILIES[self.family]["resize"]:
            raise ValueError(f"The {self.family} family does not support resize; use --no-resize")
        if self.particles and self.particles < 16:
            raise ValueError("particles must be 0 (tile size mode) or between 16 and 4096")

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
            and not self.fragment_shrink
            and not self.fragment_roundness
        )


PARAMETERS = specifications(Effect)
LIMITS = {name: spec["limits"] for name, spec in PARAMETERS.items() if spec["limits"]}
