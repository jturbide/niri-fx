"""Generate the same fragment effect for standalone Niri and shell presets."""

from dataclasses import asdict, dataclass
from importlib.resources import files
import math

GRAVITIES = ("none", "down", "up", "left", "right", "center", "space")
ROTATIONS = ("none", "random", "gravity")


@dataclass(frozen=True)
class Effect:
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

    def __post_init__(self):
        for name, low, high in (("tile_size", 8, 128), ("scatter", 0, 240),
                                ("open_ms", 100, 1500), ("close_ms", 100, 1500),
                                ("gravity_strength", 0, 3), ("particles", 0, 4096),
                                ("spin", 0, 720), ("swirl", -360, 360),
                                ("dispersion", 0, 1), ("stagger", 0, 0.4),
                                ("resize_ms", 100, 1500), ("resize_strength", 0, 1)):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError(f"{name} must be a finite number between {low} and {high}")
            if (name.endswith("_ms") or name == "particles") and int(value) != value:
                raise ValueError(f"{name} must be a whole number")
        if not isinstance(self.resize, bool):
            raise ValueError("resize must be a boolean")
        if self.particles and self.particles < 16:
            raise ValueError("particles must be 0 (tile size mode) or between 16 and 4096")
        if self.gravity not in GRAVITIES:
            raise ValueError(f"gravity must be one of {', '.join(GRAVITIES)}")
        if self.rotation not in ROTATIONS:
            raise ValueError(f"rotation must be one of {', '.join(ROTATIONS)}")

    @property
    def classic(self):
        return (self.gravity == "none" and not self.particles and self.rotation == "none"
                and self.swirl == 0 and self.dispersion == 0 and self.stagger == 0)


PRESETS = {
    "subtle": Effect(scatter=35, open_ms=360, close_ms=300, gravity="none", particles=360, spin=55, dispersion=0.3, stagger=0.1),
    "balanced": Effect(),
    "dramatic": Effect(scatter=180, open_ms=680, close_ms=600, gravity="space", gravity_strength=1.1, particles=1100, spin=260, dispersion=1, stagger=0.26),
    "explosion": Effect(scatter=240, open_ms=700, close_ms=680, gravity="space", gravity_strength=1.5, particles=1200, spin=300, dispersion=1, stagger=0.12),
    "implosion": Effect(scatter=30, open_ms=720, close_ms=680, gravity="center", gravity_strength=1.65, particles=1000, spin=260, dispersion=1, stagger=0.2),
    "earth": Effect(scatter=65, open_ms=600, close_ms=650, gravity="down", gravity_strength=1.0, particles=600, spin=190, dispersion=0.85, stagger=0.24),
    "black-hole": Effect(scatter=12, open_ms=680, close_ms=650, gravity="center", gravity_strength=1.3, particles=800, rotation="gravity", spin=200, swirl=30, dispersion=0.55, stagger=0.22),
    "space": Effect(scatter=100, open_ms=650, close_ms=650, gravity="space", gravity_strength=0.9, particles=650, spin=210, dispersion=0.95, stagger=0.28),
    "vortex": Effect(scatter=25, open_ms=720, close_ms=720, gravity="center", gravity_strength=1.15, particles=720, rotation="gravity", spin=240, swirl=160, dispersion=0.65, stagger=0.25),
    "confetti": Effect(scatter=115, open_ms=650, close_ms=720, gravity="down", gravity_strength=0.85, particles=1600, spin=480, dispersion=1, stagger=0.3),
    "updraft": Effect(scatter=60, open_ms=600, close_ms=640, gravity="up", gravity_strength=0.9, particles=600, rotation="gravity", spin=180, swirl=-25, dispersion=0.8, stagger=0.24),
}

def shader_templates():
    root = files("niri_fragments").joinpath("shaders")
    return {"classic": root.joinpath("fragments.glsl").read_text(),
            "gravity": root.joinpath("gravity.glsl").read_text(),
            "resize": root.joinpath("resize.glsl").read_text()}


def shader(effect, opening):
    template = shader_templates()["classic" if effect.classic else "gravity"]
    return _expand(template, effect, opening)


def resize_shader(effect):
    return _expand(shader_templates()["resize"], effect, False)


def movement_shader(effect):
    """Experimental API: emit only for the pinned patched compositor."""
    source = shader(effect, False)
    source = source[:source.rfind("vec4 close_color")]
    return source + """vec4 move_color(vec3 coords_geo, vec3 size_geo) {
    float p = niri_clamped_progress;
    float breakup = 0.64 * pow(sin(3.14159265359 * p), 2.0);
    if (p <= 0.0 || p >= 1.0) breakup = 0.0;
    return fragments_color(coords_geo, size_geo, breakup);
}
"""


def _expand(template, effect, opening):
    return (template.replace("@TILE@", f"{effect.tile_size:.6f}")
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
            .replace("@ENTRY@", "open_color" if opening else "close_color")
            .replace("@PROGRESS@", "1.0 - niri_clamped_progress" if opening else "niri_clamped_progress"))


def animation_types(effect):
    types = {
        name: {"duration-ms": duration, "curve": "linear", "custom-shader": shader(effect, opening)}
        for name, duration, opening in (("window-open", effect.open_ms, True),
                                        ("window-close", effect.close_ms, False))
    }

    if effect.resize:
        types["window-resize"] = {"duration-ms": effect.resize_ms, "curve": "linear",
                                  "custom-shader": resize_shader(effect)}
    return types


def render_kdl(effect):
    parts = ["// Generated by niri-fragments. Include after your base animation settings.", "animations {"]
    for name, spec in animation_types(effect).items():
        parts.extend([f"    {name} {{", f"        duration-ms {int(spec['duration-ms'])}",
                      '        curve "linear"', '        custom-shader r"',
                      spec["custom-shader"].rstrip(), '        "', "    }"])
    return "\n".join([*parts, "}", ""])


def preset_description(effect):
    density = f"~{effect.particles} pieces" if effect.particles else f"{effect.tile_size:g}px pieces"
    motion = f"{effect.gravity} {effect.gravity_strength:g}×, {effect.rotation} spin" if not effect.classic else f"{effect.scatter:g}px scatter"
    return f"{density}, {motion}; {effect.open_ms}/{effect.close_ms}ms open/close." + (f" Resize {effect.resize_ms}ms." if effect.resize else "")


def describe_presets():
    return {name: asdict(effect) for name, effect in PRESETS.items()}
