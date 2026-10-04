"""Explicit pointer-drag presets for the experimental Niri build.

These settings belong to the compositor extension, outside portable Studio
profiles. A missing ``pointer-wobble`` node keeps pointer deformation disabled.
"""

import math
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class PointerWobble:
    """Validated spring controls; damping is a percentage and frequency is in Hz."""

    strength: float = 0.7
    damping: int = 65
    frequency: int = 8

    def __post_init__(self):
        # Reject bool explicitly: Python otherwise treats it as a valid number.
        # Check bounds before isfinite so oversized integers also fail cleanly.
        if (
            type(self.strength) not in (int, float)
            or not 0 <= self.strength <= 2
            or not math.isfinite(self.strength)
        ):
            raise ValueError("strength must be a finite number between 0 and 2")
        if type(self.damping) is not int or not 10 <= self.damping <= 100:
            raise ValueError("damping must be an integer between 10 and 100 percent")
        if type(self.frequency) is not int or not 2 <= self.frequency <= 16:
            raise ValueError("frequency must be an integer between 2 and 16 Hz")


@dataclass(frozen=True)
class PointerPreset:
    """A named starting point for the isolated pointer-drag demonstration."""

    name: str
    description: str
    wobble: PointerWobble


PRESETS = MappingProxyType(
    {
        "gentle": PointerPreset(
            "Gentle",
            "A small, firm flex that settles quickly after a drag.",
            PointerWobble(strength=0.4, damping=85, frequency=10),
        ),
        "rubber-sheet": PointerPreset(
            "Rubber Sheet",
            "A deeper, slower bend with a soft rebound when the pointer changes direction.",
            PointerWobble(strength=0.9, damping=50, frequency=6),
        ),
        "release-settle": PointerPreset(
            "Release Settle",
            "A springy drag with a visible, damped settle after release.",
            PointerWobble(strength=0.7, damping=42, frequency=8),
        ),
    }
)


def render_node(wobble: PointerWobble, indent: str = "        ") -> str:
    """Render the opt-in node inside an existing ``window-movement`` block."""
    return (
        f"{indent}pointer-wobble {{\n"
        f"{indent}    strength {wobble.strength}\n"
        f"{indent}    damping {wobble.damping}\n"
        f"{indent}    frequency {wobble.frequency}\n"
        f"{indent}}}\n"
    )


def render_example(name: str) -> str:
    """Generate a complete, commented snippet for the patched compositor only."""
    preset = PRESETS[name]
    return (
        f"// NiriFX experimental pointer wobble: {preset.name}\n"
        f"// {preset.description}\n"
        "// Requires the pinned patched Niri build; stock Niri does not support this node.\n"
        "// Try it in the isolated nested demo described in experimental/README.md.\n"
        "// Merge the node into an existing animations/window-movement block if needed.\n"
        "// The built-in drag shader needs no custom-shader and leaves resize unchanged.\n"
        "// Omit pointer-wobble to disable it. Strength 0 also disables deformation.\n"
        "// Controls: strength 0..2; damping 10..100 percent; frequency 2..16 Hz.\n"
        "animations {\n"
        "    window-movement {\n"
        f"{render_node(preset.wobble)}"
        "    }\n"
        "}\n"
    )
