"""Explicit native candidate selection for owned test sessions.

Unsetting an override preserves a harness's fixed legacy default. A supplied
path must validate completely; a typo or stale candidate never selects a
replacement build. Validation reads evidence without running its executable.
"""

import os
from pathlib import Path

from .native_build import _read_manifest, inspect

OVERRIDES = {
    "movement": "NIRIFX_MOVEMENT_MANIFEST",
    "pointer": "NIRIFX_POINTER_MANIFEST",
    "fragment": "NIRIFX_FRAGMENT_MANIFEST",
    "unmodified": "NIRIFX_BASELINE_MANIFEST",
}


def explicit_manifest(variant, *, repository):
    """Return verified (binary, manifest, source), or None for a legacy default."""
    name = OVERRIDES[variant]
    if name not in os.environ:
        return None
    try:
        supplied = os.environ[name]
        if not supplied.strip():
            raise ValueError("Expected an explicit manifest path")
        path = Path(supplied).expanduser().resolve()
        manifest = _read_manifest(path)
        source_value = manifest.get("source")
        if not isinstance(source_value, str) or not source_value.strip():
            raise ValueError("Candidate manifest lacks its source checkout path")
        source = Path(source_value).expanduser()
        if not source.is_absolute():
            source = path.parent / source
        source = source.resolve()
        result = inspect(path, source=source, repository=repository)
        if result["status"] != "metadata-match":
            raise ValueError("; ".join(result["reasons"]))
        if result["variant"] != variant:
            raise ValueError(f"Expected {variant}, found {result['variant']}")
        # The inspector reads the file independently. Bind the returned paths
        # to those same inputs if another process replaces a candidate manifest.
        if _read_manifest(path) != manifest:
            raise ValueError("Candidate manifest changed during selection")
        binary = Path(manifest["binary"])
        if not binary.is_absolute():
            binary = path.parent / binary
        return binary.resolve(), manifest, source
    except (OSError, ValueError, UnicodeError) as error:
        raise RuntimeError(f"{name}: {error}. No fallback build was selected.") from error
