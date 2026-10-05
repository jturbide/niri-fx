"""Inspectable setup plans and conflict-aware restoration of project-owned changes."""

import fcntl
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from .branding import APP_ID, desktop_entry
from .documents import effect_document
from .effects import render_kdl
from .integration import (
    make_builtin_profile,
    make_custom_preset,
    make_presets,
    merge_registry,
    read_shell_presets,
)
from .storage import atomic_write, digest, read_bytes

BEGIN = "// BEGIN niri-fx managed include"
END = "// END niri-fx managed include"
OWNED = "// Managed by niri-fx setup."

# This scanner identifies native restore requirements, not configuration validity.
# Keep quoted shader source opaque and respect KDL comments so their contents
# cannot be mistaken for compositor nodes. The selected Niri still validates KDL.
_KDL_TOKEN = re.compile(
    r'//[^\r\n\f\v\x85\u2028\u2029]*|/\*|\*/|r(?P<hashes>\#*)".*?"(?P=hashes)|"(?:\\.|[^"\\])*"|[{};=]|[^\s{};="/\\]+|/[-]?|[^\s]',
    re.S,
)


def _kdl_nodes(data):
    """Read node boundaries only; values remain opaque tokens for comparison."""
    source = data.decode()
    tokens, comment, offset, continuation = [], 0, 0, False
    while offset < len(source):
        if comment:
            # Quotes inside a block comment are ordinary characters. Tokenizing
            # them as strings could swallow its terminator and hide real nodes.
            marker = re.search(r"/\*|\*/", source[offset:])
            if marker is None:
                break
            comment += 1 if marker.group() == "/*" else -1
            offset += marker.end()
            continue
        if source[offset] in "\r\n\f\v\x85\u2028\u2029":
            if not continuation:
                tokens.append("\n")
            continuation = False
            offset += 2 if source[offset : offset + 2] == "\r\n" else 1
            continue
        if source[offset].isspace():
            offset += 1
            continue
        match = _KDL_TOKEN.match(source, offset)
        if match is None:
            raise ValueError("Could not inspect a saved configuration for native Restore")
        token = match.group()
        offset = match.end()
        if token == "/*":
            comment += 1
        elif token == "\\":
            continuation = True
        elif not token.startswith("//"):
            tokens.append(token)
    remaining = deque(tokens)

    def nodes():
        result, header, children, ignored, skip_value = [], [], [], False, False

        def finish():
            if header and not ignored:
                result.append((header[0], header[1:], children.copy()))

        while remaining:
            token = remaining.popleft()
            if token == "{":
                nested = nodes()
                if not skip_value:
                    children = nested
                skip_value = False
            elif token in (";", "\n", "}"):
                finish()
                if token == "}":
                    return result
                header, children, ignored, skip_value = [], [], False, False
            elif token == "/-":
                if header:
                    skip_value = True
                else:
                    ignored = True
            elif skip_value:
                skip_value = False
                # Slash-dash can discard a property, including a separately
                # quoted key/value. Its value is not an include argument.
                if remaining and remaining[0] == "=":
                    remaining.popleft()
                    if remaining:
                        remaining.popleft()
            else:
                header.append(token)
        finish()
        return result

    return nodes()


def _kdl_string(token):
    if token.startswith("r") and '"' in token:
        hashes = token[1 : token.index('"')]
        return token[len(hashes) + 2 : -len(hashes) - 1]
    if token.startswith('"'):
        # KDL spells Unicode escapes with braces, unlike JSON. Other common
        # quoted path/node escapes use the same representation.
        token = re.sub(
            r"\\u\{([0-9a-fA-F]+)\}",
            lambda match: json.dumps(chr(int(match[1], 16)))[1:-1],
            token,
        )
        return json.loads(token)
    return token


def _native_requirements(path, overrides, seen=None):
    """Find native nodes in a prospective config, including restored includes.

    Signatures distinguish a native override being restored from an unchanged
    one already present in both configurations. Includes are read only; snapshot
    bytes take precedence over the current files for the prospective tree.
    """
    seen = set() if seen is None else seen
    path = Path(path).resolve()
    if path in seen:
        return set()
    if len(seen) >= 128:
        raise ValueError("Too many config includes to review experimental Restore safely")
    seen.add(path)
    raw = overrides[path] if path in overrides else read_bytes(path)
    if raw is None:
        return set()
    requirements = set()

    def walk(nodes, parents=()):
        for raw_name, arguments, children in nodes:
            name = _kdl_string(raw_name)
            if parents[-2:] == ("animations", "window-movement"):
                if name in (
                    "pointer-wobble",
                    "custom-shader",
                    "preserve-movement",
                    "preserve-pointer",
                ):
                    kind = (
                        "pointer" if name in ("pointer-wobble", "preserve-movement") else "movement"
                    )
                    signature = digest(json.dumps((arguments, children)).encode())
                    requirements.add((kind, signature))
            if not parents and name == "include" and arguments:
                included = Path(_kdl_string(arguments[0])).expanduser()
                requirements.update(_native_requirements(path.parent / included, overrides, seen))
            walk(children, (*parents, name))

    walk(_kdl_nodes(raw))
    return requirements


def _restore_native_requirements(work, config):
    """Compare complete before/after trees, or changed KDL for older snapshots."""
    before = {Path(item["target"]).resolve(): old for item, old, _ in work}
    after = {Path(item["target"]).resolve(): new for item, _, new in work}
    roots = ([Path(config)] if config else []) + [
        Path(item["target"]) for item, _, _ in work if Path(item["target"]).suffix == ".kdl"
    ]
    introduced = set()
    for root in roots:
        prior = _native_requirements(root, before)
        current = _native_requirements(root, after)
        for kind in ("pointer", "movement"):
            prior_signatures = {value for feature, value in prior if feature == kind}
            current_signatures = {value for feature, value in current if feature == kind}
            if prior_signatures and prior_signatures != current_signatures:
                introduced.add(kind)
    return sorted(introduced)


def default_config():
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "niri/config.kdl"


def default_state():
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / APP_ID / "setup"


def validate_config(path, binary="niri"):
    if not shutil.which(binary):
        raise ValueError("Niri is missing; install it before setup. Offline preview still works.")
    result = subprocess.run(
        [binary, "validate", "-c", str(path)], text=True, capture_output=True, timeout=30
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


def _link_bytes(path):
    """Read the link itself, refusing redirected ancestors and file collisions."""
    for parent in path.parents:
        try:
            info = parent.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError(f"Symlink change requires directory ancestors: {parent}")
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISLNK(info.st_mode):
        raise ValueError(f"Refusing to replace a non-symlink path: {path}")
    return os.readlink(os.fsencode(path))


def link_change(path, target):
    """Capture a link replacement without reading or rewriting its destination.

    Relative and dangling targets retain their exact spelling. Unlike ordinary
    dotfile changes, launcher links own their final path, never the linked file.
    """
    logical = Path(path).expanduser().absolute()
    before = _link_bytes(logical)
    after = os.fsencode(target) if target is not None else None
    if after is not None and (not after or b"\0" in after):
        raise ValueError("A symlink target must be nonempty and contain no null bytes")
    return {
        "kind": "symlink",
        "logical": str(logical),
        "target": str(logical),
        "before": before,
        "after": after,
        "mode": None,
    }


def _write_change(item, data, expected):
    if item.get("kind") != "symlink":
        atomic_write(Path(item["target"]), data, item["mode"])
        return
    path = Path(item["target"])
    check_unchanged(item, expected)
    if data is None:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".nirifx-link-" + uuid.uuid4().hex)
    created = False
    try:
        os.symlink(data, os.fsencode(temporary))
        created = True
        # Staging must not turn a concurrent retarget into permission to replace
        # a different launcher. Rename replaces this link, never its target.
        check_unchanged(item, expected)
        os.replace(temporary, path)
    finally:
        if created:
            temporary.unlink(missing_ok=True)


def _still_owned(item, expected):
    if item.get("kind") == "symlink":
        try:
            check_unchanged(item, expected)
        except (OSError, ValueError):
            return False
        return True
    return (
        Path(item["logical"]).resolve() == Path(item["target"])
        and read_bytes(Path(item["target"])) == expected
    )


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
    movement = None
    pointer = None
    validation_binary = None
    if getattr(args, "enable_movement", False):
        if args.target != "standalone":
            raise ValueError("Experimental movement requires an explicit --target standalone")
        from .capabilities import movement_capability

        movement = movement_capability(
            getattr(args, "movement_binary", None), socket_path=os.environ.get("NIRI_SOCKET")
        )
        if not movement["activation_ready"]:
            raise ValueError(
                "Movement activation requires a matching binary and verified running shader contract. Run doctor --movement-binary PATH first."
            )
        notes.append(
            "Experimental movement is explicitly enabled and the running renderer contract is verified."
        )
    pointer_settings = getattr(effect, "pointer", None)
    if getattr(args, "enable_pointer", False):
        if args.target != "standalone":
            raise ValueError("Experimental pointer wobble requires an explicit --target standalone")
        if pointer_settings is None:
            raise ValueError("This profile has no pointer settings; select a pointer preset first")
        from .capabilities import pointer_capability

        pointer = pointer_capability(
            getattr(args, "movement_binary", None), socket_path=os.environ.get("NIRI_SOCKET")
        )
        if not pointer["activation_ready"]:
            raise ValueError(
                "Pointer activation requires a matching binary and verified running pointer contract. Run doctor --niri-binary PATH first."
            )
        notes.append(
            "Pointer settings are explicitly enabled for Apply and the running renderer contract is verified."
        )
    elif pointer_settings is not None:
        notes.append("Pointer settings are kept in the profile but omitted from this activation.")
    if target == "inir":
        if config.exists() and BEGIN in config.read_text():
            raise ValueError(
                "A managed standalone override is active. Restore that setup before using iNiR."
            )
        shell = read_shell_presets(args.inir_root)
        if custom:
            generated = [make_custom_preset(shell, custom, args.base)]
        elif getattr(args, "profile", None):
            generated = [make_builtin_profile(shell, args.profile, args.base)]
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
        notes.append("Existing resize settings are preserved unless you choose a resize style.")
    else:
        if not config.is_file():
            raise ValueError(f"Niri config is missing: {config}. Create it first or pass --config.")
        if (Path(args.inir_root) / "scripts/niri-config.py").is_file():
            notes.append(
                "iNiR is also installed. This standalone override takes precedence over its animation picker when Niri loads this configuration."
            )
        original_bytes = config.read_bytes()
        original = original_bytes.decode()
        base = without_managed_block(original)
        # Avoid silently stacking over the documented manual install path.
        if re.search(r"(?m)^\s*include\s+[^\n]*nirifx[^\n]*", base, re.I):
            raise ValueError(
                "An unmanaged NiriFX include already exists; remove/review it before setup."
            )
        generated = render_kdl(effect, movement=movement is not None, pointer=pointer is not None)
        if native := pointer or movement:
            validation_binary = native["binary"]
        elif selected := getattr(args, "movement_binary", None):
            validation_binary = str(Path(selected).expanduser().absolute())
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
            if validation_binary:
                validate_config(probe.name, validation_binary)
            else:
                validate_config(probe.name)
        include = config.parent / "nirifx/animations.kdl"
        existing = read_bytes(include)
        if existing is not None and not existing.startswith((OWNED + "\n").encode()):
            raise ValueError(f"Refusing to replace an unowned file: {include}")
        changes.append(change(include, (OWNED + "\n" + generated).encode(), existing))
        block = f"{BEGIN}\ninclude {json.dumps(str(include), ensure_ascii=False)}\n{END}\n"
        changes.append(change(config, (base.rstrip() + "\n\n" + block).encode(), original_bytes))
        notes.append(
            "The standalone include takes effect when Niri loads this configuration, including through its normal config reload when already active."
        )
        notes.append(
            "The include comes last. Preserve inherits the underlying desktop settings; selected styles and Off override only their actions."
        )
    if args.launcher:
        launcher = launcher_change()
        if launcher:
            changes.append(launcher)
        else:
            notes.append("The existing Studio launcher is preserved.")
    observed = changes
    changes = [c for c in changes if c["before"] != c["after"]]
    # Plans expose actions and desktop timing separately, just like portable
    # profiles. Serializing every dataclass field as an action would silently
    # change the picker review contract when profile metadata grows.
    document = effect_document("Selection", effect)

    return {
        "target": target,
        "notes": notes,
        "changes": changes,
        "observed": observed,
        "selection": [p["name"] for p in generated]
        if target == "inir"
        else (custom["name"] if custom else getattr(args, "profile", None) or args.preset),
        "effect": document.get("actions", document.get("effect"))
        if target == "standalone" or custom or args.name or getattr(args, "profile", None)
        else None,
        "desktop_motion": document.get("motion"),
        "pointer": document.get("pointer"),
        "activation": "select in iRiS" if target == "inir" else "Niri config reload",
        "validation_config": str(config) if target == "standalone" else None,
        "validation_binary": validation_binary,
        "movement": {"binary": movement["binary"], "socket": os.environ.get("NIRI_SOCKET")}
        if movement
        else None,
        "pointer_activation": {"binary": pointer["binary"], "socket": os.environ.get("NIRI_SOCKET")}
        if pointer
        else None,
    }


def summarize(plan):
    return {
        "plan_sha256": plan_fingerprint(plan),
        "target": plan["target"],
        "notes": plan["notes"],
        "selection": plan.get("selection"),
        "effect": plan.get("effect"),
        "desktop_motion": plan.get("desktop_motion"),
        "pointer": plan.get("pointer"),
        "activation": plan.get("activation"),
        "movement": plan.get("movement"),
        "pointer_activation": plan.get("pointer_activation"),
        "native_live": plan.get("native_live"),
        "validation_binary": plan.get("validation_binary"),
        "changes": [
            {
                "path": c["logical"],
                "action": "delete"
                if c["after"] is None
                else "update"
                if c["before"] is not None
                else "create",
                "before_sha256": digest(c["before"]),
                "after_sha256": digest(c["after"]),
            }
            | ({"kind": c["kind"]} if "kind" in c else {})
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
        "desktop_motion": plan.get("desktop_motion"),
        "pointer": plan.get("pointer"),
        "movement": plan.get("movement"),
        "pointer_activation": plan.get("pointer_activation"),
        "native_live": plan.get("native_live"),
        "activation": plan.get("activation"),
        "validation_binary": plan.get("validation_binary"),
        "changes": [
            {k: item[k] for k in ("logical", "target", "mode")}
            | {side: digest(item[side]) for side in ("before", "after")}
            | ({"expected_mode": item["expected_mode"]} if "expected_mode" in item else {})
            | ({"regular_only": True} if item.get("regular_only") else {})
            | ({"kind": item["kind"]} if "kind" in item else {})
            for item in plan.get("observed", plan["changes"])
        ],
    }
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def check_unchanged(item, expected):
    logical, target = Path(item["logical"]), Path(item["target"])
    if item.get("kind") == "symlink":
        if logical != target or _link_bytes(logical) != expected:
            raise ValueError(
                f"Link changed since the plan/snapshot; leaving it untouched: {logical}"
            )
        return
    if "kind" in item:
        raise ValueError(f"Unsupported setup change kind: {item['kind']}")
    if item.get("regular_only"):
        if any(path.is_symlink() for path in (logical, *logical.parents)):
            raise ValueError(f"Native session path changed to a symlink: {logical}")
        try:
            info = target.lstat()
        except FileNotFoundError:
            info = None
        if info is not None and not stat.S_ISREG(info.st_mode):
            raise ValueError(f"Native session path is no longer a regular file: {logical}")
    if (
        item.get("expected_mode") is not None
        and target.exists()
        and stat.S_IMODE(target.stat().st_mode) != item["expected_mode"]
    ):
        raise ValueError(f"File permissions changed since the plan: {logical}")
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
    from .capabilities import movement_capability, pointer_capability

    # Review binds the selected executable and session. Re-query the renderer
    # immediately before the transaction, even for an otherwise idempotent plan.
    for key, label, capability in (
        ("movement", "movement", movement_capability),
        ("pointer_activation", "pointer", pointer_capability),
    ):
        if selected := plan.get(key):
            if (
                os.environ.get("NIRI_SOCKET") != selected["socket"]
                or not capability(selected["binary"], socket_path=selected["socket"])[
                    "activation_ready"
                ]
            ):
                raise ValueError(
                    f"Running {label} support changed after review; leaving the configuration untouched"
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
            "validation_config": plan.get("validation_config"),
            "validation_binary": plan.get("validation_binary"),
            "files": [],
        }
        if plan.get("selection_document") is not None:
            manifest["selection_document"] = plan["selection_document"]
        if plan.get("library_scope") is not None:
            manifest["library_scope"] = plan["library_scope"]
        for i, item in enumerate(plan["changes"]):
            for side in ("before", "after"):
                if item[side] is not None:
                    atomic_write(folder / f"{i}.{side}", item[side])
            manifest["files"].append(
                {k: item[k] for k in ("logical", "target", "mode")}
                | {"before_sha256": digest(item["before"]), "after_sha256": digest(item["after"])}
                | ({"kind": item["kind"]} if "kind" in item else {})
            )

        def save():
            atomic_write(folder / "manifest.json", (json.dumps(manifest, indent=2) + "\n").encode())

        save()
        applied = []
        try:
            for item in plan["changes"]:
                check_unchanged(item, item["before"])
                _write_change(item, item["after"], item["before"])
                applied.append(item)
            if plan["validation_config"]:
                if plan.get("validation_binary"):
                    validate_config(plan["validation_config"], plan["validation_binary"])
                else:
                    validate_config(plan["validation_config"])
            manifest["status"] = "applied"
            save()
        except BaseException:
            manifest["status"] = "failed"
            for item in reversed(applied):
                if _still_owned(item, item["after"]):
                    _write_change(item, item["before"], item["after"])
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


def restore(state, identifier=None, apply=False, *, binary=None, verify_native=True):
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
        if data["target"].startswith("native-session-"):
            raise ValueError(
                "Native bundles are retained for running sessions and recovery. "
                "Use native rollback to change the next-login selection; automatic bundle removal is unavailable."
            )
        if data["target"].startswith("native-tools-"):
            raise ValueError(
                "Native tools require a compatibility-checked runtime rollback. "
                "Use native tools rollback; generic Restore cannot change tool runtimes."
            )
        work = []
        for i, item in enumerate(data["files"]):
            before = read_bytes(path.parent / f"{i}.before")
            after = read_bytes(path.parent / f"{i}.after")
            if digest(before) != item["before_sha256"] or digest(after) != item["after_sha256"]:
                raise ValueError("Setup snapshot contents failed their hash check")
            check_unchanged(item, after)
            work.append((item, before, after))
        # Restoring a previous experimental selection is an activation too.
        # Inspect the actual saved bytes, not just the selection metadata: an
        # older snapshot or a shell adapter may contain native user settings.
        # Stock restoration remains available without Niri or a live session.
        native = _restore_native_requirements(
            [entry for entry in work if entry[0].get("kind") != "symlink"],
            data.get("validation_config"),
        )
        validator = binary if binary is not None else data.get("validation_binary")
        if native and (apply or verify_native):
            from .capabilities import movement_capability, pointer_capability

            for feature in native:
                capability = pointer_capability if feature == "pointer" else movement_capability
                report = capability(validator, socket_path=os.environ.get("NIRI_SOCKET"))
                if not report["activation_ready"]:
                    raise ValueError(
                        f"Restore would reactivate experimental {feature} settings. A matching binary and verified running renderer are required; use --niri-binary PATH. Configuration and snapshots were left untouched."
                    )
                validator = report["binary"]
        result = {
            "transaction": data["id"],
            "target": data["target"],
            "dry_run": not apply,
            "paths": [item["logical"] for item, _, _ in work],
            "experimental": native,
            "note": (
                "For iNiR, select your previous non-NiriFX style first; restoring the registry does not rewrite the active shader."
                if data["target"] == "inir"
                else "Restores the exact files from this snapshot."
            ),
        }
        if apply:
            restored = []
            try:
                for item, before, after in reversed(work):
                    check_unchanged(item, after)
                    _write_change(item, before, after)
                    restored.append((item, before, after))
                if native:
                    config = data.get("validation_config")
                    # Old snapshots have no root config metadata. Validate the
                    # restored KDL files in place so their relative includes
                    # resolve as they will when the compositor loads them.
                    paths = (
                        [config]
                        if config
                        else [
                            item["logical"]
                            for item, before, _ in work
                            if before is not None and Path(item["logical"]).suffix == ".kdl"
                        ]
                    )
                    for restored_config in paths:
                        validate_config(restored_config, validator)
            except BaseException:
                for item, before, after in reversed(restored):
                    if _still_owned(item, before):
                        _write_change(item, after, before)
                raise
            data["status"] = "restored"
            atomic_write(path, (json.dumps(data, indent=2) + "\n").encode())
        return result


def doctor(args):
    from .capabilities import fragment_capability, movement_capability, pointer_capability

    checks = []
    selected = getattr(args, "movement_binary", None)
    requested = str(Path(selected).expanduser().absolute()) if selected is not None else "niri"
    niri = shutil.which(requested)
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
        if selected is not None:
            validate_config(config, requested)
        else:
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
    movement = movement_capability(
        getattr(args, "movement_binary", None), socket_path=os.environ.get("NIRI_SOCKET")
    )
    pointer = pointer_capability(
        getattr(args, "movement_binary", None), socket_path=os.environ.get("NIRI_SOCKET")
    )
    fragment = fragment_capability(
        getattr(args, "movement_binary", None), socket_path=os.environ.get("NIRI_SOCKET")
    )
    checks.extend(
        [
            {
                "check": "movement-binary",
                "ok": None,
                "detail": f"{movement['binary'] or 'Unavailable'}: {movement['detail']}",
            },
            {"check": "session", "ok": None, "detail": movement["session"]["detail"]},
            {
                "check": "movement-renderer",
                "ok": None,
                "detail": movement["session"]["contract"]["detail"],
            },
            {
                "check": "pointer-binary",
                "ok": None,
                "detail": f"{pointer['binary'] or 'Unavailable'}: {pointer['detail']}",
            },
            {
                "check": "pointer-renderer",
                "ok": None,
                "detail": pointer["session"]["contract"]["detail"],
            },
            {
                "check": "fragment-renderer",
                "ok": None,
                "detail": fragment["session"]["contract"]["detail"],
            },
        ]
    )
    from .picker import picker_checks

    checks.extend(picker_checks())
    return {
        "checks": checks,
        "healthy": all(c["ok"] is not False for c in checks),
        "resize": "Choose resize separately; built-in presets preserve existing resize behavior.",
        "movement": "Experimental movement requires a matching binary and verified running renderer contract.",
        "movement_capability": movement,
        "pointer": "Experimental pointer deformation requires standalone mode, a matching binary and a verified running renderer contract.",
        "pointer_capability": pointer,
        "fragment_capability": fragment,
        "next": "Run niri-fx for guided preset selection, or setup for a scriptable JSON plan.",
    }
