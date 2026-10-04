"""Portable stock desktop timing, independent of window shader activation."""

import math
from dataclasses import asdict, dataclass

SPRING_LIMITS = {"damping_ratio": (0.1, 1), "stiffness": (1, 10000), "epsilon": (0.00001, 0.01)}


@dataclass(frozen=True)
class Spring:
    damping_ratio: float = 1
    stiffness: float = 800
    epsilon: float = 0.0001

    def __post_init__(self):
        # Niri currently cautions against overdamped springs. Keep finished
        # profiles in the stable range, with enough precision to settle cleanly.
        for field, (low, high) in SPRING_LIMITS.items():
            value = getattr(self, field)
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not low <= value <= high
            ):
                raise ValueError(f"Motion {field} must be a finite number from {low} to {high}")

        if int(self.stiffness) != self.stiffness:
            raise ValueError("Motion stiffness must be a whole number")

    def specification(self):
        return {
            "damping-ratio": self.damping_ratio,
            "stiffness": int(self.stiffness),
            "epsilon": self.epsilon,
        }


@dataclass(frozen=True)
class DesktopMotion:
    workspace: Spring
    camera: Spring
    overview: Spring

    def __post_init__(self):
        if any(
            not isinstance(getattr(self, key), Spring)
            for key in ("workspace", "camera", "overview")
        ):
            raise ValueError("Desktop motion requires workspace, camera and overview springs")

    def animation_types(self):
        return {
            # iNiR's animation registry uses the same ordered triple as its
            # built-in springs. Keep the portable document named and explicit.
            name: {"spring": list(getattr(self, key).specification().values())}
            for key, name in (
                ("workspace", "workspace-switch"),
                ("camera", "horizontal-view-movement"),
                ("overview", "overview-open-close"),
            )
        }


MOTION_PACKS = {
    "gentle": DesktopMotion(Spring(1, 500), Spring(1, 450), Spring(1, 550)),
    "balanced": DesktopMotion(Spring(1, 1000), Spring(1, 800), Spring(1, 800)),
    "playful": DesktopMotion(Spring(0.85, 650), Spring(0.85, 550), Spring(0.8, 700)),
}


def motion_documents():
    return {key: asdict(value) for key, value in MOTION_PACKS.items()}


def parse_motion(data):
    if not isinstance(data, dict) or set(data) != {"workspace", "camera", "overview"}:
        raise ValueError("Desktop motion requires workspace, camera and overview only")
    try:
        return DesktopMotion(**{key: Spring(**value) for key, value in data.items()})
    except TypeError as error:
        raise ValueError(
            "Desktop motion requires spring objects with supported parameters"
        ) from error
