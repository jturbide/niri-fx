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
    glsl_type="float",
    integer=False,
    basic=False,
):
    """Describe one field once for validation, CLI, Studio and GLSL generation.

    `integer` constrains user values; `glsl_type` controls emitted syntax. They
    differ: particle counts are whole numbers but multiply GLSL float vectors.
    Empty families means shared controls; group only describes editor layout.
    """
    spec = {
        "label": label,
        "families": families,
        "group": group,
        "unit": unit,
        "limits": limits,
        "choices": choices,
        "token": token,
        "glsl_type": glsl_type,
        "integer": integer,
        "basic": basic,
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
    """Reject non-finite values and bool-as-int before they reach generated GLSL."""
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
            if spec["glsl_type"] == "int"
            else glsl_number(value)
        )
    return tokens
