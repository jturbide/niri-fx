"""Source-checkout imports for the shared native build evidence contract."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from niri_fx.native_build import (  # noqa: E402
    DESKTOP_FEATURES,
    PATCH_FIELDS,
    REVISION,
    SCHEMA,
    STACKS,
    _read_manifest,
    cargo_artifact,
    digest,
    fingerprint,
    inspect,
    metadata,
    native_host,
)

__all__ = [
    "DESKTOP_FEATURES",
    "PATCH_FIELDS",
    "REVISION",
    "SCHEMA",
    "STACKS",
    "_read_manifest",
    "cargo_artifact",
    "digest",
    "fingerprint",
    "inspect",
    "metadata",
    "native_host",
]
