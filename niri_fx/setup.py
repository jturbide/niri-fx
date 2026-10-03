"""Inspectable setup plans and conflict-aware restoration of project-owned changes."""

import fcntl
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .branding import APP_ID, desktop_entry
from .documents import effect_document
from .effects import render_kdl
from .integration import make_custom_preset, make_presets, merge_registry, read_shell_presets
from .storage import atomic_write, digest, read_bytes

BEGIN = "// BEGIN niri-fx managed include"
END = "// END niri-fx managed include"
OWNED = "// Managed by niri-fx setup."


def default_config():
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "niri/config.kdl"


def default_state():
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / APP_ID / "setup"


def validate_config(path):
    if not shutil.which("niri"):
        raise ValueError("Niri is missing; install it before setup. Offline preview still works.")
    result = subprocess.run(
        ["niri", "validate", "-c", str(path)], text=True, capture_output=True, timeout=30
    )
    if result.returncode:
        raise ValueError("Niri configuration validation failed:\n" + result.stderr.strip())


def without_managed_block(text):
    if BEGIN not in text and END not in text:
        return text
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise ValueError("Ambiguous NiriFX include markers; inspect the config before setup")
    pattern = re.compile(
        r"(?m)^" + re.escape(BEGIN) + r"\ninclude [^\n]+\n" + re.escape(END) + r"\n?"
    )
    match = pattern.search(text)
    if not match:
        raise ValueError("The managed include block was edited; restore or review it manually")
    return text[: match.start()] + text[match.end() :]


def change(path, data, expected_before=...):
    """Capture bytes plus logical/resolved paths for later conflict detection.

    Dotfile symlinks stay intact: apply writes the captured target, and refuses
    if a later symlink retarget or file edit invalidates this plan.
    """
    logical = Path(path).expanduser().absolute()
    target = logical.resolve()
    if logical.is_symlink() and not target.exists():
        raise ValueError(f"Refusing a dangling symlink: {logical}")
    before = read_bytes(target)
    if expected_before is not ... and before != expected_before:
        raise ValueError(f"File changed while preparing the plan; leaving it untouched: {logical}")
    return {
        "logical": str(logical),
        "target": str(target),
        "before": before,
        "after": data,
        "mode": target.stat().st_mode & 0o777 if before is not None else 0o600,
    }


def launcher_change():
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    target = data / "applications" / f"{APP_ID}-studio.desktop"
    if target.exists() or target.is_symlink():
        return None
    return change(target, desktop_entry())


def plan_setup(args, effect, custom=None):
    config = Path(args.config).expanduser().absolute()
    target = args.target
    if target == "auto":
        target = (
            "inir" if (Path(args.inir_root) / "scripts/niri-config.py").is_file() else "standalone"
        )
    changes, notes = [], []
    if target == "inir":
        if config.exists() and BEGIN in config.read_text():
            raise ValueError(
                "A managed standalone override is active. Restore that setup before using iNiR."
            )
        shell = read_shell_presets(args.inir_root)
        if custom:
            generated = [make_custom_preset(shell, custom, args.base)]
        elif args.name:
            generated = [make_custom_preset(shell, effect_document(args.name, effect), args.base)]
        else:
            generated = make_presets(shell, args.base)
        registry = Path(args.registry).expanduser().resolve()
        old = read_bytes(registry)
        current = json.loads(old) if old is not None else {}
        updated = merge_registry(current, generated)
        if current != updated:
            changes.append(
                change(
                    args.registry,
                    (json.dumps(updated, indent=2, ensure_ascii=False) + "\n").encode(),
                    old,
                )
            )
        notes.append(
            "Select the saved style in iRiS Settings → Windows → Movement → Style to activate it."
        )
        notes.append(
            "Built-in resize stays off; custom resize is included only when explicitly enabled in its document/options."
        )
    else:
        if not config.is_file():
            raise ValueError(f"Niri config is missing: {config}. Create it first or pass --config.")
        if (Path(args.inir_root) / "scripts/niri-config.py").is_file():
            notes.append(
                "iNiR is also installed. This explicitly selected standalone override will take precedence over its animation picker."
            )
        original_bytes = config.read_bytes()
        original = original_bytes.decode()
        base = without_managed_block(original)
        # Avoid silently stacking over the documented manual install path.
        if re.search(r"(?m)^\s*include\s+[^\n]*nirifx[^\n]*", base, re.I):
            raise ValueError(
                "An unmanaged NiriFX include already exists; remove/review it before setup."
            )
        generated = render_kdl(effect)
        # Preserve the actual include boundary: Niri permits animation overrides
        # across files but rejects duplicate animations nodes in a single file.
        # Sibling probes also keep the user's relative includes valid. Neither
        # probe is referenced by the active config, and both disappear on failure.
        with (
            tempfile.NamedTemporaryFile(
                mode="w", suffix=".kdl", prefix=".nirifx-effect-", dir=config.parent
            ) as effect_probe,
            tempfile.NamedTemporaryFile(
                mode="w", suffix=".kdl", prefix=".nirifx-check-", dir=config.parent
            ) as probe,
        ):
            effect_probe.write(generated)
            effect_probe.flush()
            probe.write(
                base.rstrip() + "\ninclude " + json.dumps(Path(effect_probe.name).name) + "\n"
            )
            probe.flush()
            validate_config(probe.name)
        include = config.parent / "nirifx/animations.kdl"
        existing = read_bytes(include)
        if existing is not None and not existing.startswith((OWNED + "\n").encode()):
            raise ValueError(f"Refusing to replace an unowned file: {include}")
        changes.append(change(include, (OWNED + "\n" + generated).encode(), existing))
        block = f"{BEGIN}\ninclude {json.dumps(str(include), ensure_ascii=False)}\n{END}\n"
        changes.append(change(config, (base.rstrip() + "\n\n" + block).encode(), original_bytes))
        notes.append(
            "Applying this standalone include activates the effect through Niri's normal config reload."
        )
        notes.append(
            "The include comes last and overrides earlier open/close animations; keep one animation manager."
        )
    if args.launcher:
        launcher = launcher_change()
        if launcher:
            changes.append(launcher)
        else:
            notes.append("The existing Studio launcher is preserved.")
    observed = changes
    changes = [c for c in changes if c["before"] != c["after"]]
    from dataclasses import asdict

    return {
        "target": target,
        "notes": notes,
        "changes": changes,
        "observed": observed,
        "selection": [p["name"] for p in generated]
        if target == "inir"
        else (custom["name"] if custom else args.preset),
        "effect": asdict(effect) if target == "standalone" or custom or args.name else None,
        "activation": "select in iRiS" if target == "inir" else "Niri config reload",
        "validation_config": str(config) if target == "standalone" else None,
    }


def summarize(plan):
    return {
        "plan_sha256": plan_fingerprint(plan),
        "target": plan["target"],
        "notes": plan["notes"],
        "selection": plan.get("selection"),
        "effect": plan.get("effect"),
        "activation": plan.get("activation"),
        "changes": [
            {
                "path": c["logical"],
                "action": "update" if c["before"] is not None else "create",
                "before_sha256": digest(c["before"]),
                "after_sha256": digest(c["after"]),
            }
            for c in plan["changes"]
        ],
    }


def plan_fingerprint(plan):
    """Bind a UI's review to its exact selection, paths, bytes and permissions.

    The plan is rebuilt before applying, not loaded from an editable cache.
    Existing per-write checks still protect changes during the apply operation.
    """
    value = {
        "target": plan["target"],
        "selection": plan.get("selection"),
        "effect": plan.get("effect"),
        "changes": [
            {k: item[k] for k in ("logical", "target", "mode")}
            | {side: digest(item[side]) for side in ("before", "after")}
            for item in plan.get("observed", plan["changes"])
        ],
    }
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def check_unchanged(item, expected):
    logical, target = Path(item["logical"]), Path(item["target"])
    if logical.resolve() != target or read_bytes(target) != expected:
        raise ValueError(f"File changed since the plan/snapshot; leaving it untouched: {logical}")


def apply_plan(plan, state, expected=None):
    """Snapshot, compare, write and validate; roll back only bytes still owned.

    The lock coordinates NiriFX writers sharing this state directory. Editors
    and other tools do not honor it, so every write also checks current bytes.
    Multi-file writes are sequential, not crash-atomic; snapshots aid recovery.
    """
    if expected is not None and expected != plan_fingerprint(plan):
        raise ValueError(
            "The setup plan changed. Review the selection and files again before applying."
        )
    if not plan["changes"]:
        return {**summarize(plan), "changed": False, "transaction": None}
    state = Path(state).expanduser().resolve()
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (state / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        for item in plan.get("observed", plan["changes"]):
            check_unchanged(item, item["before"])
        identifier = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ-") + uuid.uuid4().hex[:8]
        folder = state / identifier
        folder.mkdir(mode=0o700)
        manifest = {
            "schema": 1,
            "id": identifier,
            "status": "preparing",
            "target": plan["target"],
            "files": [],
        }
        for i, item in enumerate(plan["changes"]):
            for side in ("before", "after"):
                if item[side] is not None:
                    atomic_write(folder / f"{i}.{side}", item[side])
            manifest["files"].append(
                {k: item[k] for k in ("logical", "target", "mode")}
                | {"before_sha256": digest(item["before"]), "after_sha256": digest(item["after"])}
            )

        def save():
            atomic_write(folder / "manifest.json", (json.dumps(manifest, indent=2) + "\n").encode())

        save()
        applied = []
        try:
            for item in plan["changes"]:
                check_unchanged(item, item["before"])
                atomic_write(Path(item["target"]), item["after"], item["mode"])
                applied.append(item)
            if plan["validation_config"]:
                validate_config(plan["validation_config"])
            manifest["status"] = "applied"
            save()
        except BaseException:
            manifest["status"] = "failed"
            for item in reversed(applied):
                if (
                    Path(item["logical"]).resolve() == Path(item["target"])
                    and read_bytes(Path(item["target"])) == item["after"]
                ):
                    atomic_write(Path(item["target"]), item["before"], item["mode"])
            save()
            raise
        return {
            **summarize(plan),
            "changed": True,
            "transaction": identifier,
            "restore": shlex.join(
                [
                    sys.executable,
                    "-m",
                    "niri_fx",
                    "restore",
                    "--state",
                    str(state),
                    "--transaction",
                    identifier,
                    "--apply",
                ]
            ),
        }


def restore(state, identifier=None, apply=False):
    """Undo a selected/latest applied snapshot after verifying hashes and paths.

    Later user edits are conflicts, never an invitation to force an old backup
    over current data. Reverse write order unwinds dependent includes safely.
    """
    state = Path(state).expanduser().resolve()
    if not state.is_dir():
        raise ValueError(
            "No setup snapshots exist. Use unregister for older manually registered presets."
        )
    with (state / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if identifier and not re.fullmatch(r"\d{8}T\d{12}Z-[a-f0-9]{8}", identifier):
            raise ValueError("Invalid transaction ID")
        candidates = (
            [state / identifier / "manifest.json"]
            if identifier
            else sorted(state.glob("*/manifest.json"), reverse=True)
        )
        selected = None
        for candidate in candidates:
            data = json.loads(candidate.read_text())
            if data.get("schema") != 1:
                raise ValueError("Unsupported setup snapshot schema")
            if data["status"] == "applied":
                selected = candidate, data
                break
        if selected is None:
            raise ValueError("No applied setup snapshot remains to restore")
        path, data = selected
        work = []
        for i, item in enumerate(data["files"]):
            before = read_bytes(path.parent / f"{i}.before")
            after = read_bytes(path.parent / f"{i}.after")
            if digest(before) != item["before_sha256"] or digest(after) != item["after_sha256"]:
                raise ValueError("Setup snapshot contents failed their hash check")
            check_unchanged(item, after)
            work.append((item, before, after))
        result = {
            "transaction": data["id"],
            "target": data["target"],
            "dry_run": not apply,
            "paths": [item["logical"] for item, _, _ in work],
            "note": "For iNiR, select your previous non-NiriFX style first; restoring the registry does not rewrite the active shader.",
        }
        if apply:
            restored = []
            try:
                for item, before, after in reversed(work):
                    check_unchanged(item, after)
                    atomic_write(Path(item["target"]), before, item["mode"])
                    restored.append((item, before, after))
            except BaseException:
                for item, before, after in reversed(restored):
                    if read_bytes(Path(item["target"])) == before:
                        atomic_write(Path(item["target"]), after, item["mode"])
                raise
            data["status"] = "restored"
            atomic_write(path, (json.dumps(data, indent=2) + "\n").encode())
        return result


def doctor(args):
    checks = []
    niri = shutil.which("niri")
    try:
        version = (
            subprocess.check_output(
                [niri, "--version"], text=True, stderr=subprocess.PIPE, timeout=10
            ).strip()
            if niri
            else "Not installed; offline preview is available."
        )
        checks.append({"check": "niri", "ok": bool(niri), "detail": version})
    except (OSError, subprocess.SubprocessError) as error:
        checks.append({"check": "niri", "ok": False, "detail": f"Could not query Niri: {error}"})
    config = Path(args.config).expanduser()
    try:
        validate_config(config)
        checks.append({"check": "config", "ok": True, "detail": str(config)})
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        checks.append({"check": "config", "ok": False, "detail": str(error)})
    helper = Path(args.inir_root) / "scripts/niri-config.py"
    if helper.is_file():
        try:
            shell = read_shell_presets(args.inir_root)
            checks.append(
                {
                    "check": "inir",
                    "ok": True,
                    "detail": f"External presets available; active: {shell.get('active') or 'custom/unrecognized'}",
                }
            )
        except (ValueError, OSError, subprocess.SubprocessError) as error:
            checks.append({"check": "inir", "ok": False, "detail": str(error)})
    else:
        checks.append(
            {
                "check": "inir",
                "ok": None,
                "detail": "Not installed; use standalone setup (including DMS on Niri).",
            }
        )
    browser = next(
        (
            name
            for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
            if shutil.which(name)
        ),
        None,
    )
    checks.append(
        {
            "check": "studio",
            "ok": None,
            "detail": f"App window: {browser}"
            if browser
            else "Studio will use the default browser; WebGL is required.",
        }
    )
    checks.append(
        {
            "check": "session",
            "ok": None,
            "detail": "Niri socket advertised"
            if os.environ.get("NIRI_SOCKET")
            else "No Niri socket advertised; this may be an offline/SSH session.",
        }
    )
    from .picker import picker_checks

    checks.extend(picker_checks())
    return {
        "checks": checks,
        "healthy": all(c["ok"] is not False for c in checks),
        "resize": "Opt-in; all built-in presets default off.",
        "movement": "Requires the separate experimental compositor; setup never installs it.",
        "next": "Run niri-fx for guided preset selection, or setup for a scriptable JSON plan.",
    }
