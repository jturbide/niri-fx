"""Independent effects for each action; movement remains an experimental export."""

from dataclasses import asdict, dataclass

from .effects import FAMILIES, Effect, resize_shader, shader

PROFILE_SCHEMA = 1


@dataclass(frozen=True)
class Profile:
    open: Effect
    close: Effect
    resize: Effect | None = None
    movement: Effect | None = None

    def __post_init__(self):
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

    def animation_types(self):
        result = {}
        for action in ("open", "close", "resize"):
            effect = getattr(self, action)
            if effect is None:
                continue
            result[f"window-{action}"] = {
                "duration-ms": getattr(effect, f"{action}_ms"),
                "curve": "linear",
                "custom-shader": resize_shader(effect)
                if action == "resize"
                else shader(effect, action == "open"),
            }
        return result

    def document(self, name):
        return {"kind": "profile", "schema": PROFILE_SCHEMA, "name": name, "actions": asdict(self)}


def parse_profile(data):
    if type(data.get("schema")) is not int or data["schema"] != PROFILE_SCHEMA:
        raise ValueError(f"Profile requires schema: {PROFILE_SCHEMA}")
    if set(data) != {"kind", "schema", "name", "actions"}:
        raise ValueError("Profile requires kind, schema, name and actions only")
    actions = data.get("actions")
    if not isinstance(actions, dict) or set(actions) != {"open", "close", "resize", "movement"}:
        raise ValueError("Profile actions must contain open, close, resize and movement")
    try:
        return Profile(
            **{
                key: Effect(**value) if isinstance(value, dict) else value
                for key, value in actions.items()
            }
        )
    except TypeError as error:
        raise ValueError(f"Unsupported profile parameters: {error}") from error
