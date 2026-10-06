"""Independent effects for each action; movement remains an experimental export."""

from dataclasses import asdict, dataclass
from typing import Literal

from .fragment_motion import FragmentMotionSettings, parse_fragment_motion
from .model import FAMILIES, Effect
from .motion import DesktopMotion, parse_motion
from .pointer import PointerWobble, parse_pointer

PROFILE_SCHEMA = 4
BASE_ACTIONS = ("open", "close", "resize", "movement")
ACTIONS = (*BASE_ACTIONS, "swap")
Action = Effect | Literal["off"] | None


def action_mode(action: Action) -> str:
    """Preserve inherits the underlying config; Off is an explicit override."""
    return "preserve" if action is None else "off" if action == "off" else "style"


@dataclass(frozen=True)
class Profile:
    """Action choices, independent of shader generation or shell persistence.

    None preserves the underlying desktop configuration, "off" disables an
    action, and Effect selects a NiriFX style. Resize flags stay false inside
    effects because the dedicated slot owns that choice. Native actions can
    round-trip without stock activation; pointer strength zero is explicit Off.
    Fragment response remains stored when movement is preserved, disabled or
    selects a material that cannot use the continuous native mesh.
    """

    open: Action = None
    close: Action = None
    resize: Action = None
    movement: Action = None
    swap: Action = None
    motion: DesktopMotion | None = None
    pointer: PointerWobble | None = None
    fragment_motion: FragmentMotionSettings | None = None

    def __post_init__(self):
        if self.fragment_motion is not None and not isinstance(
            self.fragment_motion, FragmentMotionSettings
        ):
            raise ValueError("Profile fragment_motion must contain fragment response settings")
        if self.pointer is not None and not isinstance(self.pointer, PointerWobble):
            raise ValueError("Profile pointer must contain pointer wobble settings")
        if self.motion is not None and not isinstance(self.motion, DesktopMotion):
            raise ValueError("Profile motion must contain desktop spring settings")
        for action in ACTIONS:
            effect = getattr(self, action)
            if effect is None or effect == "off":
                continue
            if not isinstance(effect, Effect):
                raise ValueError(f"{action} must contain an effect, null (Preserve), or 'off'")
            if effect.resize:
                raise ValueError(
                    "Profile actions use a separate resize slot; leave effect.resize off"
                )
            capability = "movement" if action == "swap" else action
            if capability in ("resize", "movement") and not FAMILIES[effect.family][capability]:
                raise ValueError(f"The {effect.family} family does not support {action}")

    def document(self, name):
        schema = (
            PROFILE_SCHEMA
            if self.fragment_motion is not None
            else 3
            if self.swap is not None
            else 2
        )
        document = {
            "kind": "profile",
            # Keep existing recipes byte-stable until explicit response controls
            # are saved. Schema 4 always retains all five action choices.
            "schema": schema,
            "name": name,
            "actions": {
                key: asdict(value) if isinstance(value := getattr(self, key), Effect) else value
                for key in (ACTIONS if schema >= 3 else BASE_ACTIONS)
            },
        }
        if self.motion is not None:
            document["motion"] = asdict(self.motion)
        if self.pointer is not None:
            document["pointer"] = asdict(self.pointer)
        if self.fragment_motion is not None:
            document["fragment_motion"] = asdict(self.fragment_motion)
        return document


def parse_profile(data):
    if type(data.get("schema")) is not int or data["schema"] not in (1, 2, 3, PROFILE_SCHEMA):
        raise ValueError(f"Profile requires schema: 1, 2, 3 or {PROFILE_SCHEMA}")
    required = {"kind", "schema", "name", "actions"}
    optional = {"motion", "pointer"}
    if data["schema"] == PROFILE_SCHEMA:
        required.add("fragment_motion")
        if data.get("fragment_motion") is None:
            raise ValueError("Schema 4 requires explicit fragment motion response settings")
    if not required <= set(data) or set(data) - required - optional:
        raise ValueError(
            "Profile requires kind, schema, name, actions and supported optional settings only"
        )
    actions = data.get("actions")
    expected = ACTIONS if data["schema"] >= 3 else BASE_ACTIONS
    if not isinstance(actions, dict) or set(actions) != set(expected):
        raise ValueError("Profile actions must contain " + ", ".join(expected))
    # Legacy profiles require open/close styles. Do not reinterpret malformed
    # old documents as new Preserve/Off choices during migration.
    if data["schema"] == 1 and any(
        not isinstance(actions[action], dict)
        and not (value is None and action in ("resize", "movement"))
        for action, value in actions.items()
    ):
        raise ValueError("Schema 1 requires opening/closing effects and optional resize/movement")
    try:
        return Profile(
            motion=parse_motion(data["motion"]) if "motion" in data else None,
            pointer=parse_pointer(data.get("pointer")),
            fragment_motion=parse_fragment_motion(data.get("fragment_motion")),
            **{
                key: Effect(**value) if isinstance(value, dict) else value
                for key, value in actions.items()
            },
        )
    except TypeError as error:
        raise ValueError(f"Unsupported profile parameters: {error}") from error
