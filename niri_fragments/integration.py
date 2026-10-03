"""iNiR's external preset registry; never edits or activates Niri settings."""

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile

from .effects import Effect, PRESETS, animation_types, preset_description

OWNER = "niri-fragments"


def default_registry():
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    # Match iNiR's own legacy-directory selection, including its common symlink.
    legacy = config / "illogical-impulse"
    return (legacy if legacy.exists() else config / "inir") / "niri-animation-presets.json"


def default_inir_root():
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return data / "inir"


def read_shell_presets(inir_root):
    helper = Path(inir_root) / "scripts/niri-config.py"
    if not helper.is_file():
        raise ValueError(f"iNiR helper not found at {helper}; use --inir-root or standalone render")
    response = subprocess.run([sys.executable, str(helper), "get-animation-presets"],
                              check=True, text=True, capture_output=True, timeout=15)
    registry = json.loads(response.stdout)
    if not isinstance(registry, dict) or not isinstance(registry.get("presets"), list):
        raise ValueError("iNiR returned an unsupported preset registry")
    return registry


def resolve_base(shell_registry, base_id="auto"):
    presets = {p["id"]: p for p in shell_registry["presets"] if isinstance(p, dict) and "id" in p}
    chosen = shell_registry.get("active", "") if base_id == "auto" else base_id
    if not chosen:
        raise ValueError("Current animations are custom. Choose an explicit --base from iNiR's presets; custom timings cannot be captured losslessly.")
    seen = set()
    while chosen in presets and presets[chosen].get("generator") == OWNER:
        if chosen in seen:
            raise ValueError("Fragment preset base reference contains a cycle")
        seen.add(chosen)
        chosen = presets[chosen].get("base-preset", "")
    if chosen not in presets or not isinstance(presets[chosen].get("types"), dict) or not presets[chosen]["types"]:
        raise ValueError(f"Base preset {chosen!r} is unavailable; select another --base")
    return chosen, presets[chosen]["types"]


def make_preset(identifier, label, effect, chosen, base_types):
    types = deepcopy(base_types)
    types.update(animation_types(effect))
    return {"id": identifier, "name": f"NiriFX · {label}",
            "description": preset_description(effect),
            "keywords": ["nirifx", effect.family, "animation", "reconstruct", "slices" if effect.family == "slices" else "particles"],
            "generator": OWNER, "schema-version": 2, "base-preset": chosen,
            "effect": asdict(effect), "types": types}


def make_presets(shell_registry, base_id="auto"):
    chosen, base_types = resolve_base(shell_registry, base_id)
    generated = []
    for name, effect in PRESETS.items():
        generated.append(make_preset(f"{OWNER}-{name}", name.replace("-", " ").title(), effect, chosen, base_types))
    return generated


def custom_document(data):
    if not isinstance(data, dict) or type(data.get("schema")) is not int or data["schema"] not in (1, 2) or not isinstance(data.get("effect"), dict):
        raise ValueError("Custom preset must contain schema: 1 or 2, name, and an effect object")
    if data["schema"] == 1 and data["effect"].get("family", "fragments") != "fragments":
        raise ValueError("Non-fragment families require preset schema: 2")
    name = data.get("name")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,47}", name):
        raise ValueError("Preset name must be 1–48 letters, numbers, spaces, hyphens or underscores")
    slug = re.sub(r"[ _-]+", "-", name.lower()).rstrip("-")
    try:
        effect = Effect(**data["effect"])
    except TypeError as error:
        raise ValueError(f"Unsupported effect parameters: {error}") from error
    return name, slug, effect


def make_custom_preset(shell_registry, data, base_id="auto"):
    name, slug, effect = custom_document(data)
    chosen, base_types = resolve_base(shell_registry, base_id)
    return make_preset(f"{OWNER}-custom-{slug}", name, effect, chosen, base_types)


def merge_registry(data, generated, remove=False):
    if not isinstance(data, dict) or not isinstance(data.get("presets", []), list):
        raise ValueError("Existing user preset file must be an object with a presets array")
    current = data.get("presets", [])
    if any(not isinstance(p, dict) or not isinstance(p.get("id"), str) for p in current):
        raise ValueError("Existing user preset entries must be objects with string IDs")
    ids = [p["id"] for p in current]
    if len(ids) != len(set(ids)):
        raise ValueError("Existing user preset IDs are duplicated; refusing to rewrite them")
    generated_ids = {p["id"] for p in generated}
    for preset in current:
        if preset["id"] in generated_ids and preset.get("generator") != OWNER:
            raise ValueError(f"Preset ID {preset['id']} already belongs to another provider")
    result = deepcopy(data)
    # Updating the built-in pack must preserve independently saved custom
    # presets (and saving a custom preset must preserve the built-in pack).
    result["presets"] = [p for p in current if not (
        p.get("generator") == OWNER and (remove or p["id"] in generated_ids))]
    if not remove:
        result["presets"].extend(deepcopy(generated))
    if remove and result.get("default") in {p["id"] for p in current if p.get("generator") == OWNER}:
        result.pop("default")
    return result


def update_registry(registry_path, generated=(), *, remove=False, dry_run=False):
    target = Path(registry_path).expanduser().resolve()
    if dry_run:
        data = json.loads(target.read_text()) if target.exists() else {}
        return {"path": str(target), "dry_run": True,
                "registry": merge_registry(data, generated, remove)}
    if remove and not target.exists():
        return {"path": str(target), "changed": False, "backup": None}
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.with_name(target.name + ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        original = target.read_bytes() if target.exists() else None
        data = json.loads(original) if original is not None else {}
        updated = merge_registry(data, generated, remove)
        if updated == data:
            return {"path": str(target), "changed": False, "backup": None}
        mode = (target.stat().st_mode & 0o777) if original is not None else 0o600
        backup = None
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".niri-fragments-", delete=False) as output:
                temporary = Path(output.name)
                os.fchmod(output.fileno(), mode)
                output.write((json.dumps(updated, indent=2, ensure_ascii=False) + "\n").encode())
                output.flush()
                os.fsync(output.fileno())
            current = target.read_bytes() if target.exists() else None
            if current != original:
                raise ValueError("Preset registry changed during registration; retry after the other writer finishes")
            if original is not None:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
                backup = target.with_name(target.name + f".bak.{stamp}")
                with backup.open("xb") as saved:
                    os.fchmod(saved.fileno(), mode)
                    saved.write(original)
                    saved.flush()
                    os.fsync(saved.fileno())
            os.replace(temporary, target)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        return {"path": str(target), "changed": True,
                "backup": str(backup) if backup else None,
                "ids": [p["id"] for p in generated] if not remove else []}
