"""Parameter metadata shared by validation, CLI, Studio and shader expansion."""

import math
from dataclasses import field, fields


def parameter(
    default,
    *,
    label,
    families=(),
    group="timing",
    unit="",
    limits=None,
    choices=None,
    token=None,
    integer=False,
    advanced=False,
):
    spec = {
        "label": label,
        "families": families,
        "group": group,
        "unit": unit,
        "limits": limits,
        "choices": choices,
        "token": token,
        "integer": integer,
        "advanced": advanced,
    }
    return field(default=default, metadata=spec)


def specifications(cls):
    return {
        item.name: {
            **item.metadata,
            "default": item.default,
            "type": "boolean" if item.type is bool else "choice" if item.type is str else "number",
        }
        for item in fields(cls)
    }


def validate_parameters(effect, specs):
    for name, spec in specs.items():
        value = getattr(effect, name)
        if spec["type"] == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a boolean")
        elif spec["type"] == "choice":
            if not isinstance(value, str) or value not in spec["choices"]:
                raise ValueError(f"{name} must be one of {', '.join(spec['choices'])}")
        else:
            low, high = spec["limits"]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or not low <= value <= high
            ):
                raise ValueError(f"{name} must be a finite number between {low} and {high}")
            if spec["integer"] and int(value) != value:
                raise ValueError(f"{name} must be a whole number")


def glsl_number(value):
    """Six decimals, identical rounding in Python and JavaScript, including ties."""
    scaled = math.floor(abs(value) * 1_000_000 + 0.5)
    sign = "-" if value < 0 and scaled else ""
    return f"{sign}{scaled // 1_000_000}.{scaled % 1_000_000:06d}"


def shader_tokens(effect, specs):
    tokens = {}
    for name, spec in specs.items():
        if not spec["token"]:
            continue
        value = getattr(effect, name)
        tokens[spec["token"]] = (
            str(list(spec["choices"]).index(value))
            if spec["type"] == "choice"
            else str(int(value))
            if name == "slice_count"
            else glsl_number(value)
        )
    return tokens
