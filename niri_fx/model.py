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
FRAGMENT_SHAPES = (
    "square",
    "rectangle",
    "triangle",
    "circle",
    "ellipse",
    "hexagon",
    "diamond",
    "star",
)
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
# Capabilities describe renderer support, never activation. Resize requires an
# explicit flag or profile slot even when a family has a resize renderer.
FAMILIES = {
    name: {
        "label": name.title(),
        "open_close": True,
        "resize": name in {"fragments", "slices", "elastic", "distortion"},
        "movement": name in {"fragments", "slices", "elastic", "pixels", "distortion"},
        "concept": name == "fragments",
    }
    for name in (
        "fragments",
        "slices",
        "elastic",
        "dissolve",
        "iris",
        "pixels",
        "wisps",
        "distortion",
        "hexagons",
    )
}


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
        basic=True,
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
        basic=True,
        label="Slice angle",
        families=("slices",),
        group="slices",
        limits=(-90, 90),
        token="SLICE_ANGLE",
        unit="°",
    )
    slice_distance: float = parameter(
        220,
        basic=True,
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
        basic=True,
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
    fragment_shape: str = parameter(
        "square",
        label="Piece shape",
        families=("fragments",),
        group="fragments",
        choices=FRAGMENT_SHAPES,
        token="FRAGMENT_SHAPE",
        basic=True,
    )
    fragment_aspect: float = parameter(
        1,
        label="Shape width / height",
        families=("fragments",),
        group="fragments",
        limits=(0.25, 4),
        token="FRAGMENT_ASPECT",
    )
    fragment_orientation: float = parameter(
        0,
        label="Shape orientation",
        families=("fragments",),
        group="fragments",
        limits=(-180, 180),
        unit="°",
        token="FRAGMENT_ORIENTATION",
    )
    fragment_transition: float = parameter(
        0.28,
        label="Shape emergence",
        families=("fragments",),
        group="fragments",
        limits=(0.05, 0.6),
        token="FRAGMENT_TRANSITION",
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
        basic=True,
        label="Wobble strength",
        families=("elastic",),
        group="elastic",
        limits=(0, 1),
        token="ELASTIC_STRENGTH",
    )
    elastic_frequency: float = parameter(
        2,
        basic=True,
        label="Spring oscillations",
        families=("elastic",),
        group="elastic",
        limits=(1, 5),
        token="ELASTIC_FREQUENCY",
        unit=" cycles",
    )
    elastic_damping: float = parameter(
        2,
        basic=True,
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
        basic=True,
        label="Square size",
        families=("fragments",),
        group="fragments",
        limits=(8, 128),
        token="TILE",
        unit=" px",
    )
    scatter: float = parameter(
        125,
        basic=True,
        label="Initial spread",
        families=("fragments",),
        group="fragments",
        limits=(0, 240),
        token="SCATTER",
        unit=" px",
    )
    open_ms: int = parameter(
        520,
        basic=True,
        label="Opening time",
        families=(),
        group="timing",
        limits=(100, 1500),
        unit=" ms",
        integer=True,
    )
    close_ms: int = parameter(
        480,
        basic=True,
        label="Closing time",
        families=(),
        group="timing",
        limits=(100, 1500),
        unit=" ms",
        integer=True,
    )
    gravity: str = parameter(
        "space",
        basic=True,
        label="Gravity direction",
        families=("fragments",),
        group="fragments",
        choices=GRAVITIES,
        token="GRAVITY",
    )
    gravity_strength: float = parameter(
        0.7,
        basic=True,
        label="Gravity strength",
        families=("fragments",),
        group="fragments",
        limits=(0, 3),
        token="STRENGTH",
        unit="×",
    )
    particles: int = parameter(
        720,
        basic=True,
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
    resize: bool = parameter(False, basic=True, label="Resize", families=(), group="resize")
    resize_ms: int = parameter(
        450,
        basic=True,
        label="Resize time",
        families=("fragments", "slices", "elastic", "distortion"),
        group="resize",
        limits=(100, 1500),
        unit=" ms",
        integer=True,
    )
    resize_strength: float = parameter(
        0.65,
        basic=True,
        label="Resize strength",
        families=("fragments", "slices", "elastic", "distortion"),
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
        basic=True,
        label="Resize style",
        families=("fragments",),
        group="resize",
        choices=RESIZE_MODES,
        token="RESIZE_MODE",
    )

    dissolve_scale: float = parameter(
        24,
        basic=True,
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
        basic=True,
        label="Reveal shape",
        families=("iris",),
        group="iris",
        choices=("circle", "diamond", "square"),
        token="IRIS_SHAPE",
    )
    iris_direction: str = parameter(
        "inward",
        basic=True,
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
        basic=True,
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
        basic=True,
        label="Pixel motion",
        families=("pixels",),
        group="pixels",
        choices=("wipe", "pixelate", "dust"),
        token="PIXEL_MODE",
    )
    pixel_size: float = parameter(
        12,
        basic=True,
        label="Pixel size",
        families=("pixels",),
        group="pixels",
        limits=(4, 64),
        token="PIXEL_SIZE",
        unit=" px",
    )
    pixel_direction: str = parameter(
        "center",
        basic=True,
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
        basic=True,
        label="Curl strength",
        families=("wisps",),
        group="wisps",
        limits=(0, 2),
        token="WISP_CURL",
    )
    wisp_drift: float = parameter(
        110,
        basic=True,
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
        basic=True,
        label="Distortion pattern",
        families=("distortion",),
        group="distortion",
        choices=("shockwave", "ripple", "wave", "glitch", "vortex"),
        token="DISTORTION_MODE",
    )
    distortion_strength: float = parameter(
        28,
        basic=True,
        label="Displacement",
        families=("distortion",),
        group="distortion",
        limits=(0, 80),
        token="DISTORTION_STRENGTH",
        unit=" px",
    )
    distortion_resize_mode: str = parameter(
        "ripple",
        basic=True,
        label="Resize distortion",
        families=("distortion",),
        group="resize",
        choices=("ripple", "edge-ripple", "torsion"),
        token="DISTORTION_RESIZE_MODE",
    )
    resize_twist: float = parameter(
        18,
        basic=True,
        label="Resize twist",
        families=("distortion",),
        group="resize",
        limits=(-45, 45),
        token="RESIZE_TWIST",
        unit="°",
    )
    distortion_twist: float = parameter(
        270,
        basic=True,
        label="Vortex twist",
        families=("distortion",),
        group="distortion",
        limits=(-720, 720),
        token="DISTORTION_TWIST",
        unit="°",
    )
    distortion_contract: float = parameter(
        0.8,
        basic=True,
        label="Vortex contraction",
        families=("distortion",),
        group="distortion",
        limits=(0, 0.95),
        token="DISTORTION_CONTRACT",
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
        label="Distortion origin · horizontal",
        families=("distortion",),
        group="distortion",
        limits=(0, 1),
        token="DISTORTION_X",
    )
    distortion_y: float = parameter(
        0.5,
        label="Distortion origin · vertical",
        families=("distortion",),
        group="distortion",
        limits=(0, 1),
        token="DISTORTION_Y",
    )

    hex_size: float = parameter(
        24,
        basic=True,
        label="Hexagon radius",
        families=("hexagons",),
        group="hexagons",
        limits=(6, 80),
        unit=" px",
        token="HEX_SIZE",
    )
    hex_spread: float = parameter(
        0.9,
        basic=True,
        label="Hexagon spread",
        families=("hexagons",),
        group="hexagons",
        limits=(0, 2),
        token="HEX_SPREAD",
    )
    hex_spin: float = parameter(
        140,
        label="Hexagon spin",
        families=("hexagons",),
        group="hexagons",
        limits=(0, 360),
        unit="°",
        token="HEX_SPIN",
    )
    hex_direction: str = parameter(
        "outward",
        basic=True,
        label="Hexagon direction",
        families=("hexagons",),
        group="hexagons",
        choices=("outward", "inward"),
        token="HEX_DIRECTION",
    )
    hex_stagger: float = parameter(
        0.3,
        label="Hexagon stagger",
        families=("hexagons",),
        group="hexagons",
        limits=(0, 0.7),
        token="HEX_STAGGER",
    )
    dissolve_mode: str = parameter(
        "noise",
        basic=True,
        label="Dissolve pattern",
        families=("dissolve",),
        group="dissolve",
        choices=("noise", "ink"),
        token="DISSOLVE_MODE",
    )
    dissolve_turbulence: float = parameter(
        0.6,
        basic=True,
        label="Ink turbulence",
        families=("dissolve",),
        group="dissolve",
        limits=(0, 1),
        token="DISSOLVE_TURBULENCE",
    )
    dissolve_x: float = parameter(
        0.5,
        label="Ink origin · horizontal",
        families=("dissolve",),
        group="dissolve",
        limits=(0, 1),
        token="DISSOLVE_X",
    )
    dissolve_y: float = parameter(
        0.5,
        label="Ink origin · vertical",
        families=("dissolve",),
        group="dissolve",
        limits=(0, 1),
        token="DISSOLVE_Y",
    )
    glitch_bands: int = parameter(
        24,
        label="Signal bands",
        families=("distortion",),
        group="distortion",
        limits=(4, 96),
        integer=True,
        token="GLITCH_BANDS",
    )
    glitch_chroma: float = parameter(
        0,
        label="Color separation",
        families=("distortion",),
        group="distortion",
        limits=(0, 1),
        token="GLITCH_CHROMA",
    )
    movement_strength: float = parameter(
        0.64,
        label="Native movement strength",
        families=("fragments", "slices", "elastic", "pixels", "distortion"),
        group="movement",
        limits=(0, 1),
        token="MOVEMENT_STRENGTH",
        basic=True,
    )
    movement_focus: float = parameter(
        0,
        label="Trailing edge emphasis",
        families=("fragments", "slices", "pixels", "distortion"),
        group="movement",
        limits=(0, 1),
        token="MOVEMENT_FOCUS",
    )
    movement_ms: int = parameter(
        900,
        label="Movement time",
        families=("fragments", "slices", "elastic", "pixels", "distortion"),
        group="movement",
        limits=(100, 2000),
        integer=True,
        unit=" ms",
    )

    def __post_init__(self):
        validate_parameters(self, PARAMETERS)
        if self.resize and not FAMILIES[self.family]["resize"]:
            raise ValueError(f"The {self.family} family does not support resize; use --no-resize")
        if self.particles and self.particles < 16:
            raise ValueError("particles must be 0 (tile size mode) or between 16 and 4096")

    @property
    def shaped(self):
        """Keep existing square effects on their smaller, unchanged lookup paths."""
        return (
            self.fragment_shape != "square"
            or self.fragment_orientation != 0
            or (self.fragment_roundness > 0 and self.fragment_transition != 0.28)
        )

    @property
    def shaped_resize(self):
        """Use geometry when an explicitly enabled resize needs piece controls."""
        return self.shaped or bool(
            self.fragment_shrink or self.fragment_roundness or self.size_variation
        )

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
