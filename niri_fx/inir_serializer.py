"""Inspect iNiR's supported serializer contract without writing its checkout.

The installed helper is trusted Python code, not a sandboxed input. Its known
writer is intercepted so ordinary compatible helpers only produce review bytes;
contract checks report upstream API drift before the transaction applies them.
"""

import contextlib
import importlib.util
import inspect
import io
from dataclasses import dataclass
from pathlib import Path

from .storage import digest, read_bytes

SECTION = "config.d/60-animations.kdl"


@dataclass(frozen=True)
class SerializedPreset:
    path: Path
    before: bytes | None
    content: bytes
    helper_sha256: str


def _callable(module, name, *arguments):
    function = getattr(module, name, None)
    if not callable(function):
        raise ValueError(f"missing callable {name}")
    try:
        inspect.signature(function).bind(*arguments)
    except (TypeError, ValueError):
        raise ValueError(f"unsupported arguments for {name}") from None
    return function


def serialize_preset(inir_root, config, preset):
    """Return one supported animation replacement and its exact source identity."""
    helper = Path(inir_root) / "scripts/niri-config.py"
    config = Path(config).expanduser().absolute()
    try:
        # Compile the same bytes used for review identity. Avoid import loaders
        # that can reuse stale bytecode or create __pycache__ in the shell tree.
        source = helper.read_bytes()
        spec = importlib.util.spec_from_file_location("_nirifx_inir_helper", helper)
        module = importlib.util.module_from_spec(spec)
        exec(compile(source, str(helper), "exec"), module.__dict__)
        resolver = _callable(module, "resolve_niri_section_file", SECTION)
        serializer = _callable(module, "cmd_apply_animation_preset", [preset["id"]])
        _callable(module, "_load_animation_presets")
        _callable(module, "_write_validated", config, "")
        animation = Path(resolver(SECTION))
        # iNiR supports a modular section and a monolithic root config. Compare
        # destinations but retain logical paths for the transaction's symlink checks.
        if not animation.is_absolute() or animation.resolve() not in {
            config.resolve(),
            (config.parent / SECTION).resolve(),
        }:
            raise ValueError("unsupported animation file path")
        before = read_bytes(animation.resolve())
        captured = []

        def capture(path, text):
            if Path(path) != animation:
                raise ValueError("serializer changed its animation file path")
            if captured:
                raise ValueError("serializer produced more than one animation file")
            if not isinstance(text, str) or not text.strip():
                raise ValueError("serializer returned empty or non-text animation content")
            captured.append(text.encode())
            return 0

        module._load_animation_presets = lambda: {"presets": [preset]}
        module._write_validated = capture
        with contextlib.redirect_stdout(io.StringIO()):
            result = serializer([preset["id"]])
        if type(result) is not int or result != 0 or len(captured) != 1:
            raise ValueError("serializer did not produce exactly one successful replacement")
        return SerializedPreset(animation, before, captured[0], digest(source))
    except Exception as error:
        # KeyboardInterrupt and other BaseException controls retain their normal
        # behavior. API/import/serialization failures become a usable UI response.
        detail = str(error).strip() or type(error).__name__
        raise ValueError(
            f"iNiR's animation helper is incompatible: {detail[:240]}. "
            "Update NiriFX and iNiR together, or open Studio with --target standalone. "
            "Existing NiriFX Restore remains available."
        ) from error
