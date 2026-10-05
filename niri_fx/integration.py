"""iNiR's external preset registry; never edits or activates Niri settings."""

import fcntl
import json
import os
import subprocess
import sys
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .branding import APP_ID
from .catalog import PROFILES, STYLES, collection_names, families, title
from .documents import parse_document
from .effects import animation_types, preset_description
from .profiles import Profile
from .storage import staged_write

OWNER = APP_ID


def default_registry():
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    # Follow iNiR's config-root selection, including its common symlink.
    legacy = config / "illogical-impulse"
    return (legacy if legacy.exists() else config / "inir") / "niri-animation-presets.json"


def default_inir_root():
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return data / "inir"


def read_shell_presets(inir_root):
    helper = Path(inir_root) / "scripts/niri-config.py"
    if not helper.is_file():
        raise ValueError(f"iNiR helper not found at {helper}; use --inir-root or standalone render")
    response = subprocess.run(
        [sys.executable, str(helper), "get-animation-presets"],
        check=True,
        text=True,
        capture_output=True,
        timeout=15,
    )
    registry = json.loads(response.stdout)
    if not isinstance(registry, dict) or not isinstance(registry.get("presets"), list):
        raise ValueError("iNiR returned an unsupported preset registry")
    return registry


def resolve_base(shell_registry, base_id="auto"):
    """Follow NiriFX ancestry to real shell timings, rejecting cycles/custom state."""
    presets = {p["id"]: p for p in shell_registry["presets"] if isinstance(p, dict) and "id" in p}
    chosen = shell_registry.get("active", "") if base_id == "auto" else base_id
    if not chosen:
        raise ValueError(
            "Current animations are custom. Choose an explicit --base from iNiR's presets; custom timings cannot be captured losslessly."
        )
    seen = set()
    while chosen in presets and presets[chosen].get("generator") == OWNER:
        if chosen in seen:
            raise ValueError("NiriFX preset base reference contains a cycle")
        seen.add(chosen)
        chosen = presets[chosen].get("base-preset", "")
    if (
        chosen not in presets
        or not isinstance(presets[chosen].get("types"), dict)
        or not presets[chosen]["types"]
    ):
        raise ValueError(f"Base preset {chosen!r} is unavailable; select another --base")
    return chosen, presets[chosen]["types"]


def make_preset(identifier, label, effect, chosen, base_types):
    """Overlay only requested actions onto a copy of the user's base settings."""
    family = "profile" if isinstance(effect, Profile) else effect.family
    types = deepcopy(base_types)
    # iNiR's registry serializer and active-preset matcher accept timing/spring
    # specs, not Niri's `off` node. Zero duration has no animation under slowdown
    # either; replacing the whole spec also removes any inherited shader. Keep
    # the portable profile's explicit Off choice unchanged below.
    types.update(
        {
            action: {"duration-ms": 0, "curve": "linear"} if spec == {"off": True} else spec
            for action, spec in animation_types(effect).items()
        }
    )
    return {
        "id": identifier,
        "name": f"NiriFX · {label}",
        "description": preset_description(effect),
        "keywords": [
            "nirifx",
            *dict.fromkeys((family, *families(effect))),
            *collection_names(identifier.removeprefix(f"{OWNER}-")),
            "animation",
            "reconstruct",
            {"fragments": "particles", "slices": "strips", "elastic": "wobble"}.get(family, family),
        ],
        "generator": OWNER,
        "schema-version": 2,
        "base-preset": chosen,
        **(
            {"profile": effect.document(label)}
            if isinstance(effect, Profile)
            else {"effect": asdict(effect)}
        ),
        "types": types,
    }


def make_presets(shell_registry, base_id="auto"):
    chosen, base_types = resolve_base(shell_registry, base_id)
    generated = []
    for name, effect in STYLES.items():
        generated.append(
            make_preset(
                f"{OWNER}-{name}", name.replace("-", " ").title(), effect, chosen, base_types
            )
        )
    return generated


def make_builtin_profile(shell_registry, name, base_id="auto"):
    chosen, base_types = resolve_base(shell_registry, base_id)
    return make_preset(f"{OWNER}-{name}", title(name), PROFILES[name], chosen, base_types)


def make_custom_preset(shell_registry, data, base_id="auto"):
    name, slug, effect = parse_document(data)
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
    result["presets"] = [
        p
        for p in current
        if not (p.get("generator") == OWNER and (remove or p["id"] in generated_ids))
    ]
    if not remove:
        result["presets"].extend(deepcopy(generated))
    if remove and result.get("default") in {
        p["id"] for p in current if p.get("generator") == OWNER
    }:
        result.pop("default")
    return result


def update_registry(registry_path, generated=(), *, remove=False, dry_run=False):
    """Register without activation; preserve unrelated providers and recovery bytes.

    Lock cooperating writers, stage and fsync the replacement, compare against
    the read snapshot, then back up before rename. A failure before rename leaves
    the original registry intact. This does not edit the active Niri shader.
    """
    target = Path(registry_path).expanduser().resolve()
    if dry_run:
        data = json.loads(target.read_text()) if target.exists() else {}
        return {
            "path": str(target),
            "dry_run": True,
            "registry": merge_registry(data, generated, remove),
        }
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
        content = (json.dumps(updated, indent=2, ensure_ascii=False) + "\n").encode()
        with staged_write(target, content, mode) as temporary:
            current = target.read_bytes() if target.exists() else None
            if current != original:
                raise ValueError(
                    "Preset registry changed during registration; retry after the other writer finishes"
                )
            if original is not None:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
                backup = target.with_name(target.name + f".bak.{stamp}")
                with backup.open("xb") as saved:
                    os.fchmod(saved.fileno(), mode)
                    saved.write(original)
                    saved.flush()
                    os.fsync(saved.fileno())
            os.replace(temporary, target)
        return {
            "path": str(target),
            "changed": True,
            "backup": str(backup) if backup else None,
            "ids": [p["id"] for p in generated] if not remove else [],
        }
