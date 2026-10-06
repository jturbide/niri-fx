"""Portable preset documents: validation and serialization without shell dependencies.

The file/HTTP/browser paths accept named parameter data, never arbitrary GLSL.
Schemas describe the outer document shape; each Effect validates its own fields.
"""

import json
import re
from dataclasses import asdict
from pathlib import Path

from .model import PRESET_SCHEMA, Effect
from .profiles import Profile, parse_profile

# Five independent styles plus explicit response controls fit when pretty-printed.
MAX_DOCUMENT_BYTES = 32 * 1024


def parse_document(data):
    """Validate a style/profile and derive its stable registry slug. No I/O."""
    profile = isinstance(data, dict) and data.get("kind") == "profile"
    if not profile and (
        not isinstance(data, dict)
        or type(data.get("schema")) is not int
        or data["schema"] != PRESET_SCHEMA
        or not isinstance(data.get("effect"), dict)
    ):
        raise ValueError(
            f"Custom preset must contain schema: {PRESET_SCHEMA}, name, and an effect object"
        )
    if not profile and set(data) != {"schema", "name", "effect"}:
        raise ValueError("Preset requires schema, name and effect only")
    name = data.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,47}", name):
        raise ValueError(
            "Preset name must be 1–48 letters, numbers, spaces, hyphens or underscores"
        )
    slug = re.sub(r"[ _-]+", "-", name.lower()).rstrip("-")
    try:
        effect = parse_profile(data) if profile else Effect(**data["effect"])
    except TypeError as error:
        raise ValueError(f"Unsupported effect parameters: {error}") from error
    return name, slug, effect


def load_document(path):
    """Read at most the same byte limit used by Studio, then validate atomically."""
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_DOCUMENT_BYTES + 1)
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise ValueError("Custom preset must be at most 32 KiB")
    data = json.loads(raw)
    parse_document(data)
    return data


def effect_document(name, effect):
    """Serialize the current preset format; older formats are not supported."""
    if isinstance(effect, Profile):
        return effect.document(name)
    return {"schema": PRESET_SCHEMA, "name": name, "effect": asdict(effect)}
