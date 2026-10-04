"""Independent effects for each action; movement remains an experimental export."""

from dataclasses import asdict, dataclass

from .model import FAMILIES, Effect
from .motion import DesktopMotion, parse_motion
from .pointer import PointerWobble, parse_pointer

PROFILE_SCHEMA = 1


@dataclass(frozen=True)
class Profile:
    """Action choices, independent of shader generation or shell persistence.

    None means inherit the compositor's existing behavior. Nested resize flags
    stay false because the resize slot is the only opt-in for a profile.
    Movement and pointer data can round-trip here without appearing in stock
    Niri exports. Pointer strength zero is an explicit disable, unlike None.
    """

    open: Effect
    close: Effect
    resize: Effect | None = None
    movement: Effect | None = None
    motion: DesktopMotion | None = None
    pointer: PointerWobble | None = None

    def __post_init__(self):
        if self.pointer is not None and not isinstance(self.pointer, PointerWobble):
            raise ValueError("Profile pointer must contain pointer wobble settings")
        if self.motion is not None and not isinstance(self.motion, DesktopMotion):
            raise ValueError("Profile motion must contain desktop spring settings")
        for action in ("open", "close", "resize", "movement"):
            effect = getattr(self, action)
            if effect is None and action in ("resize", "movement"):
                continue
            if not isinstance(effect, Effect):
                raise ValueError(f"{action} must contain an effect")
            if effect.resize:
                raise ValueError(
                    "Profile actions use a separate resize slot; leave effect.resize off"
                )
            if action in ("resize", "movement") and not FAMILIES[effect.family][action]:
                raise ValueError(f"The {effect.family} family does not support {action}")

    def document(self, name):
        document = {
            "kind": "profile",
            "schema": PROFILE_SCHEMA,
            "name": name,
            "actions": {
                key: asdict(getattr(self, key)) if getattr(self, key) is not None else None
                for key in ("open", "close", "resize", "movement")
            },
        }
        if self.motion is not None:
            document["motion"] = asdict(self.motion)
        if self.pointer is not None:
            document["pointer"] = asdict(self.pointer)
        return document


def parse_profile(data):
    if type(data.get("schema")) is not int or data["schema"] != PROFILE_SCHEMA:
        raise ValueError(f"Profile requires schema: {PROFILE_SCHEMA}")
    required = {"kind", "schema", "name", "actions"}
    if not required <= set(data) or set(data) - required - {"motion", "pointer"}:
        raise ValueError(
            "Profile requires kind, schema, name, actions and optional motion or pointer only"
        )
    actions = data.get("actions")
    if not isinstance(actions, dict) or set(actions) != {"open", "close", "resize", "movement"}:
        raise ValueError("Profile actions must contain open, close, resize and movement")
    try:
        return Profile(
            motion=parse_motion(data["motion"]) if "motion" in data else None,
            pointer=parse_pointer(data.get("pointer")),
            **{
                key: Effect(**value) if isinstance(value, dict) else value
                for key, value in actions.items()
            },
        )
    except TypeError as error:
        raise ValueError(f"Unsupported profile parameters: {error}") from error
