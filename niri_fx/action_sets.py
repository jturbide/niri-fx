"""Coordinated looks with optional companions, using ordinary profile documents.

Choosing a set supplies only open/close effects and desktop timing. A separate,
explicit choice adds resize or experimental movement. Keeping recommendations
outside the portable profile prevents an imported document from enabling them.
"""

from dataclasses import asdict, dataclass, replace

from .model import Effect
from .motion import MOTION_PACKS
from .presets import PRESETS
from .profiles import Profile


@dataclass(frozen=True)
class ActionSet:
    opening: str
    closing: str
    desktop: str
    resize: Effect
    movement: Effect
    description: str

    def profile(self, *, include_resize=False, include_movement=False):
        """Build the exact requested actions; neither companion is a default."""
        return Profile(
            PRESETS[self.opening],
            PRESETS[self.closing],
            resize=self.resize if include_resize else None,
            movement=self.movement if include_movement else None,
            motion=MOTION_PACKS[self.desktop],
        )


ACTION_SETS = {
    "fragments-motion": ActionSet(
        "mixed-confetti",
        "orbiting-shapes",
        "balanced",
        replace(
            PRESETS["mixed-confetti"],
            resize_mode="edge",
            resize_strength=0.42,
            resize_ms=380,
            spin=110,
        ),
        replace(
            PRESETS["fragment-wake"],
            fragment_secondary="triangle",
            fragment_mix=0.5,
            particles=800,
            movement_strength=0.45,
            movement_ms=800,
        ),
        "Mixed pieces assemble, orbit away and share restrained desktop timing",
    ),
    "ribbons-motion": ActionSet(
        "ribbon-wave",
        "zipper",
        "gentle",
        replace(
            PRESETS["ribbon-wave"],
            resize_strength=0.4,
            resize_ms=380,
            slice_rotation=3,
        ),
        replace(PRESETS["ribbon-transfer"], movement_strength=0.45, movement_ms=800),
        "Flowing ribbons arrive, a zipper closes them and gentle desktop springs settle",
    ),
    "elastic-motion": ActionSet(
        "spring-wobble",
        "rubber-band",
        "playful",
        replace(
            PRESETS["spring-wobble"],
            elastic_strength=0.28,
            elastic_frequency=1.4,
            elastic_damping=3.5,
            resize_strength=0.42,
            resize_ms=360,
        ),
        replace(PRESETS["momentum-glide"], movement_strength=0.42, movement_ms=750),
        "Springy arrivals, a rubber-sheet exit and lightly bouncing desktop timing",
    ),
}


def companion_documents():
    """Fresh editor suggestions, never part of saved or imported settings."""
    return {
        name: {"resize": asdict(recipe.resize), "movement": asdict(recipe.movement)}
        for name, recipe in ACTION_SETS.items()
    }
