"""Settings and starting points for experimental native square-fragment motion.

These controls belong to the patched compositor's ``fragment-motion`` block.
They are not a portable profile document or part of Studio's parameter schema.
This module performs no configuration writes or activation.
"""

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
from types import MappingProxyType

from .presets import PRESETS as EFFECT_PRESETS


@dataclass(frozen=True)
class FragmentControl:
    """Native control metadata; ranges are inclusive unless stated otherwise."""

    kind: str
    default: int | float | str
    minimum: int | float | None = None
    maximum: int | float | None = None
    exclusive_min: bool = False
    choices: tuple[str, ...] = ()
    unit: str = ""


def _number(default, minimum, maximum, *, integer=False, exclusive_min=False, unit=""):
    return field(
        default=default,
        metadata={
            "control": FragmentControl(
                "integer" if integer else "number",
                default,
                minimum,
                maximum,
                exclusive_min,
                unit=unit,
            )
        },
    )


@dataclass(frozen=True)
class FragmentMotionSettings:
    """The native v3 controls, retaining its integer types, units and bounds.

    Delays postpone each piece's target history. Response times set how quickly
    it catches that target; rotation/tilt follow its continuous velocity. Tilt
    uses radians and an orthographic planar projection, not perspective 3D.
    """

    batches: int = _number(64, 1, 4096, integer=True)
    delay_near_ms: int = _number(0, 0, 600, integer=True, unit="ms")
    delay_far_ms: int = _number(360, 0, 600, integer=True, unit="ms")
    delay_jitter: float = _number(0.25, 0, 1)
    response_near_ms: int = _number(120, 20, 800, integer=True, unit="ms")
    response_far_ms: int = _number(360, 20, 800, integer=True, unit="ms")
    response_jitter: float = _number(0.3, 0, 1)
    distance_exponent: float = _number(1.2, 0, 4, exclusive_min=True)
    max_lag: int = _number(768, 1, 1024, integer=True, unit="logical px")
    pin_radius: float = _number(24, 0, 256, unit="logical px")
    press_spread: float = _number(20, 0, 128, unit="logical px")
    press_response_ms: int = _number(140, 20, 800, integer=True, unit="ms")
    rotation_mode: str = field(
        default="movement",
        metadata={
            "control": FragmentControl("choice", "movement", choices=("movement", "random", "none"))
        },
    )
    rotation_degrees: float = _number(20, 0, 60, unit="degrees")
    rotation_response_ms: int = _number(180, 20, 800, integer=True, unit="ms")
    rotation_speed: int = _number(1000, 1, 5000, integer=True, unit="logical px/s")
    tilt: float = _number(0.55, 0, 1.1, unit="radians")
    release_ms: int = _number(1800, 200, 2000, integer=True, unit="ms")

    def __post_init__(self):
        for name, control in CONTROLS.items():
            value = getattr(self, name)
            if control.kind == "choice":
                if type(value) is not str or value not in control.choices:
                    raise ValueError(f"{name} must be one of: {', '.join(control.choices)}")
                continue
            # Bool is an int subclass. Check type and bounds before isfinite so
            # booleans and arbitrarily large integers fail without coercion.
            numeric = type(value) in (int, float)
            if control.kind == "integer":
                numeric = type(value) is int
            if not numeric or not control.minimum <= value <= control.maximum:
                raise ValueError(
                    f"{name} must be a {control.kind} between "
                    f"{control.minimum} and {control.maximum}"
                )
            if not math.isfinite(value) or (control.exclusive_min and value == control.minimum):
                raise ValueError(f"{name} must be finite and greater than {control.minimum}")
        if self.delay_near_ms > self.delay_far_ms:
            raise ValueError("delay_near_ms must not exceed delay_far_ms")
        if self.response_near_ms > self.response_far_ms:
            raise ValueError("response_near_ms must not exceed response_far_ms")


CONTROLS = MappingProxyType(
    {item.name: item.metadata["control"] for item in fields(FragmentMotionSettings)}
)


def parse_settings(data: Mapping) -> FragmentMotionSettings:
    """Validate snake_case overrides against native defaults.

    Omitted keys inherit defaults. Unknown keys, including hyphenated KDL names,
    fail explicitly. This mapping API does not define a new JSON document kind.
    Integer native controls require Python ints, including when called with JSON.
    """
    if not isinstance(data, Mapping):
        raise ValueError("Fragment motion settings must be a mapping of snake_case controls")
    unknown = set(data) - CONTROLS.keys()
    if unknown:
        raise ValueError(
            f"Unknown fragment motion controls: {', '.join(sorted(map(str, unknown)))}"
        )
    return FragmentMotionSettings(**data)


def render_node(settings: FragmentMotionSettings, indent: int = 8) -> str:
    """Render a block inside an experimental ``window-movement`` configuration."""
    if not isinstance(settings, FragmentMotionSettings):
        raise ValueError("render_node requires validated FragmentMotionSettings")
    if type(indent) is not int or indent < 0:
        raise ValueError("indent must be a nonnegative integer")
    prefix = " " * indent
    lines = [f"{prefix}fragment-motion {{"]
    for name, control in CONTROLS.items():
        value = getattr(settings, name)
        if control.kind == "number":
            # Preserve small positive exponents and full native f64 precision.
            # GLSL's six-decimal formatter would turn valid values into zero.
            value = 0.0 if value == 0 else float(value)
        lines.append(f"{prefix}    {name.replace('_', '-')} {json.dumps(value, allow_nan=False)}")
    return "\n".join((*lines, f"{prefix}}}", ""))


@dataclass(frozen=True)
class FragmentPreset:
    """A square material and native motion settings for an explicit local trial."""

    name: str
    description: str
    particles: int
    settings: FragmentMotionSettings

    def __post_init__(self):
        if type(self.particles) is not int or not 1 <= self.particles <= 4096:
            raise ValueError("particles must be an integer between 1 and 4096")
        if not isinstance(self.settings, FragmentMotionSettings):
            raise ValueError("settings must be validated FragmentMotionSettings")

    @property
    def effect(self):
        """Match the accepted square material; native settings own its motion."""
        return replace(
            EFFECT_PRESETS["balanced"],
            fragment_shape="square",
            particles=self.particles,
            spin=100,
            stagger=0.08,
            dispersion=0.65,
            movement_ms=350,
            movement_strength=0.48,
            movement_focus=0.65,
            scatter=100,
            gravity_strength=0.35,
        )


PRESETS = MappingProxyType(
    {
        "gentle": FragmentPreset(
            "Gentle",
            "A restrained separation with short delays and a quick return.",
            600,
            FragmentMotionSettings(
                batches=32,
                delay_far_ms=180,
                delay_jitter=0.15,
                response_near_ms=100,
                response_far_ms=220,
                response_jitter=0.15,
                max_lag=384,
                pin_radius=28,
                press_spread=8,
                press_response_ms=120,
                rotation_degrees=8,
                rotation_response_ms=140,
                tilt=0.2,
                release_ms=1100,
            ),
        ),
        "tear": FragmentPreset(
            "Tear",
            "Pieces spread around the grab point, then follow in a delayed, uneven wave.",
            800,
            FragmentMotionSettings(),
        ),
        "cascade": FragmentPreset(
            "Cascade",
            "More pieces, longer delays and wider separation with a pronounced turning motion.",
            1200,
            FragmentMotionSettings(
                batches=128,
                delay_far_ms=460,
                delay_jitter=0.35,
                response_near_ms=140,
                response_far_ms=460,
                response_jitter=0.35,
                distance_exponent=1.1,
                max_lag=1024,
                pin_radius=20,
                press_spread=32,
                press_response_ms=160,
                rotation_degrees=30,
                rotation_response_ms=210,
                tilt=0.75,
                release_ms=2000,
            ),
        ),
    }
)
