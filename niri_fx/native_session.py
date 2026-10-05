"""Immutable local desktop bundles and reviewed next-login selection.

Preparing a bundle does not select or run it. Selection transactions change only
one small pointer; retained binaries and configuration remain available even
when selecting a different version while a desktop session is still running.
"""

import json
import os
import re
import stat
from pathlib import Path

from . import native_build
from .setup import _kdl_nodes, _kdl_string, change
from .storage import digest

SCHEMA = 1
_ID = re.compile(r"[0-9a-f]{64}")
MAX_CONFIG_BYTES = 4 * 1024 * 1024
MAX_BINARY_BYTES = 512 * 1024 * 1024
MAX_METADATA_BYTES = 1024 * 1024


def default_root():
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "niri-fx/native"


def _path(value):
    path = Path(value).expanduser().absolute()
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError(f"Native session paths must not be symlinks: {component}")
    return path


def _read(path, limit, *, mode=None):
    path = _path(path)
    with native_build._regular_file(path) as stream:
        before = os.fstat(stream.fileno())
        data = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    if len(data) > limit:
        raise ValueError(f"Native session input exceeds its size limit: {path}")
    current = path.stat()

    def identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

    if identity(before) != identity(after) or identity(after) != identity(current):
        raise ValueError(f"Native session input changed while reading: {path}")
    if mode is not None and stat.S_IMODE(current.st_mode) != mode:
        raise ValueError(f"Unexpected native session file permissions: {path}")
    return data


def _json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _object(data, label):
    try:
        value = json.loads(data)
    except (ValueError, UnicodeError) as error:
        raise ValueError(f"Invalid {label}") from error
    if not isinstance(value, dict):
        raise ValueError(f"Invalid {label}")
    return value


def _self_contained(data):
    def walk(nodes):
        for name, _, children in nodes:
            # The lightweight node scanner does not decode KDL type annotations.
            # Niri accepts typed includes, so rejecting annotations closes that
            # ambiguity without pretending this scanner is a complete parser.
            if name.startswith("("):
                raise ValueError(
                    "Native session configs cannot use node type annotations; remove them before staging"
                )
            if _kdl_string(name) == "include":
                raise ValueError(
                    "Native session bundles require a self-contained config with no active include nodes"
                )
            walk(children)

    walk(_kdl_nodes(data))


def _bundle_path(root, bundle_id):
    if not isinstance(bundle_id, str) or not _ID.fullmatch(bundle_id):
        raise ValueError("Invalid native session bundle ID")
    return _path(_path(root) / "bundles" / bundle_id)


def _bundle_id(binary_sha256, config_sha256, metadata):
    return native_build.fingerprint(
        {"binary_sha256": binary_sha256, "config_sha256": config_sha256, "native_build": metadata}
    )


def _observed(path, data, mode):
    item = change(path, data, expected_before=data)
    if item["mode"] != mode:
        raise ValueError(f"Unexpected native session file permissions: {path}")
    item["expected_mode"] = mode
    item["regular_only"] = True
    return item


def inspect_bundle(root, bundle_id):
    """Check owned bytes and frozen desktop build evidence without execution."""
    folder = _bundle_path(root, bundle_id)
    receipt_data = _read(folder / "bundle.json", MAX_METADATA_BYTES, mode=0o600)
    receipt = _object(receipt_data, "native session bundle")
    fields = {
        "schema",
        "bundle_id",
        "binary",
        "config",
        "binary_sha256",
        "config_sha256",
        "native_build",
        "source_manifest_sha256",
    }
    if (
        set(receipt) != fields
        or type(receipt["schema"]) is not int
        or receipt["schema"] != SCHEMA
        or receipt["bundle_id"] != bundle_id
        or receipt["binary"] != "bin/niri"
        or receipt["config"] != "config.kdl"
        or any(
            not isinstance(receipt[key], str) or not _ID.fullmatch(receipt[key])
            for key in ("binary_sha256", "config_sha256", "source_manifest_sha256")
        )
        or _bundle_id(receipt["binary_sha256"], receipt["config_sha256"], receipt["native_build"])
        != bundle_id
    ):
        raise ValueError("Native session bundle identity is invalid")
    binary, config = folder / "bin/niri", folder / "config.kdl"
    binary_data = _read(binary, MAX_BINARY_BYTES, mode=0o755)
    config_data = _read(config, MAX_CONFIG_BYTES, mode=0o600)
    if (
        digest(binary_data) != receipt["binary_sha256"]
        or digest(config_data) != receipt["config_sha256"]
    ):
        raise ValueError("Native session bundle contents changed")
    _self_contained(config_data)
    provenance = folder / "provenance"
    manifest_data = _read(provenance / "manifest.json", MAX_METADATA_BYTES, mode=0o600)
    manifest = _object(manifest_data, "frozen native build manifest")
    if (
        manifest.get("binary") != "../bin/niri"
        or manifest.get("source") != "."
        or manifest.get("binary_sha256") != receipt["binary_sha256"]
        or manifest.get("native_build") != receipt["native_build"]
    ):
        raise ValueError("Native session build evidence changed")
    metadata = receipt["native_build"]
    if not isinstance(metadata, dict) or not isinstance(metadata.get("inputs"), dict):
        raise ValueError("Invalid native session build metadata")
    variant = metadata["inputs"].get("variant")
    if not isinstance(variant, str) or variant not in native_build.STACKS:
        raise ValueError("Invalid native session build variant")
    evidence = [(provenance / "manifest.json", manifest_data)]
    evidence.append(
        (
            provenance / "Cargo.lock",
            _read(provenance / "Cargo.lock", MAX_METADATA_BYTES, mode=0o600),
        )
    )
    for name in native_build.STACKS[variant]:
        path = provenance / "experimental" / name
        evidence.append((path, _read(path, MAX_CONFIG_BYTES, mode=0o600)))
    report = native_build.inspect(
        provenance / "manifest.json",
        source=provenance,
        repository=provenance,
        desktop=True,
        pinned_revision=False,
    )
    if report["status"] != "metadata-match":
        raise ValueError("Native session bundle failed inspection: " + "; ".join(report["reasons"]))
    # Bind the second reader used by the shared inspector to the same evidence.
    observed = [_observed(binary, binary_data, 0o755), _observed(config, config_data, 0o600)]
    observed.extend(_observed(path, data, 0o600) for path, data in evidence)
    observed.append(_observed(folder / "bundle.json", receipt_data, 0o600))
    return {
        "bundle_id": bundle_id,
        "binary": str(binary),
        "config": str(config),
        "binary_sha256": receipt["binary_sha256"],
        "config_sha256": receipt["config_sha256"],
        "build_id": report["build_id"],
        "variant": report["variant"],
        "desktop_prerequisites": report["desktop_prerequisites"],
        "runtime_acceptance": "not_assessed",
        "physical_desktop_acceptance": "not_assessed",
        "observed": observed,
    }


def _plan(target, selection, changes, observed, *, config=None, binary=None, notes=()):
    for item in [*changes, *observed]:
        item["regular_only"] = True
    return {
        "target": target,
        "selection": selection,
        "notes": list(notes),
        "changes": changes,
        "observed": observed,
        "validation_config": config,
        "validation_binary": binary,
    }


def stage_plan(manifest, source, repository, config, root):
    """Review a full desktop build and copy its self-contained config on Apply."""
    manifest, source, repository, config, root = map(
        _path, (manifest, source, repository, config, root)
    )
    raw_manifest = _read(manifest, MAX_METADATA_BYTES)
    record = _object(raw_manifest, "native build manifest")
    binary_value = record.get("binary")
    if not isinstance(binary_value, str) or not binary_value:
        raise ValueError("Native build manifest has no binary path")
    binary = _path(manifest.parent / binary_value)
    binary_data = _read(binary, MAX_BINARY_BYTES)
    if not binary.stat().st_mode & 0o111:
        raise ValueError("Native candidate binary is not executable")
    config_data = _read(config, MAX_CONFIG_BYTES)
    _self_contained(config_data)
    provenance = [
        (source / "Cargo.lock", _read(source / "Cargo.lock", MAX_METADATA_BYTES), "Cargo.lock")
    ]
    inputs = (
        record.get("native_build", {}).get("inputs", {})
        if isinstance(record.get("native_build"), dict)
        else {}
    )
    variant = inputs.get("variant") if isinstance(inputs, dict) else None
    if not isinstance(variant, str) or variant not in native_build.STACKS:
        raise ValueError("Native candidate has no supported versioned build metadata")
    for name in native_build.STACKS[variant]:
        path = repository / "experimental" / name
        provenance.append((path, _read(path, MAX_CONFIG_BYTES), "experimental/" + name))
    report = native_build.inspect(manifest, source=source, repository=repository, desktop=True)
    if report["status"] != "metadata-match":
        raise ValueError("Candidate cannot be staged: " + "; ".join(report["reasons"]))
    if digest(binary_data) != record["binary_sha256"]:
        raise ValueError("Candidate binary changed during review")
    config_sha = digest(config_data)
    bundle_id = _bundle_id(record["binary_sha256"], config_sha, record["native_build"])
    folder = _bundle_path(root, bundle_id)
    source_observed = [
        _observed(path, data, stat.S_IMODE(path.stat().st_mode))
        for path, data in [(manifest, raw_manifest), (binary, binary_data), (config, config_data)]
        + [(path, data) for path, data, _ in provenance]
    ]
    selection = {"bundle_id": bundle_id, "build_id": report["build_id"], "variant": variant}
    notes = [
        "Stages a separate desktop bundle; does not change the next-login selection.",
        "Apply validates the copied config with this trusted candidate executable.",
    ]
    if (folder / "bundle.json").exists():
        existing = inspect_bundle(root, bundle_id)
        return _plan(
            "native-session-stage",
            selection,
            [],
            source_observed + existing["observed"],
            notes=notes,
        )
    if folder.exists():
        for existing in folder.rglob("*"):
            _path(existing)
            if not existing.is_dir():
                raise ValueError(
                    "Incomplete native session bundle exists; refusing to overwrite it"
                )
    receipt = {
        "schema": SCHEMA,
        "bundle_id": bundle_id,
        "binary": "bin/niri",
        "config": "config.kdl",
        "binary_sha256": record["binary_sha256"],
        "config_sha256": config_sha,
        "native_build": record["native_build"],
        "source_manifest_sha256": digest(raw_manifest),
    }
    outputs = [
        (folder / "bin/niri", binary_data, 0o755),
        (folder / "config.kdl", config_data, 0o600),
    ]
    outputs.extend(
        (folder / "provenance" / relative, data, 0o600) for _, data, relative in provenance
    )
    outputs.append(
        (
            folder / "provenance/manifest.json",
            _json_bytes(record | {"binary": "../bin/niri", "source": "."}),
            0o600,
        )
    )
    # The completion marker is written last; only complete bundles can be selected.
    outputs.append((folder / "bundle.json", _json_bytes(receipt), 0o600))
    changes = []
    for path, data, mode in outputs:
        _path(path)
        item = change(path, data, expected_before=None)
        item["mode"] = mode
        changes.append(item)
    return _plan(
        "native-session-stage",
        selection,
        changes,
        source_observed + changes,
        config=str(folder / "config.kdl"),
        binary=str(folder / "bin/niri"),
        notes=notes,
    )


def _parse_selection(raw):
    if raw is None:
        return {"schema": SCHEMA, "selected": None}
    value = _object(raw, "native session selection")
    if (
        set(value) not in ({"schema", "selected"}, {"schema", "selected", "previous"})
        or type(value["schema"]) is not int
        or value["schema"] != SCHEMA
        or any(
            item is not None and (not isinstance(item, str) or not _ID.fullmatch(item))
            for key, item in value.items()
            if key != "schema"
        )
    ):
        raise ValueError("Invalid native session selection")
    return value


def load_selection(root):
    """Missing history differs from a recorded previous no-selection state."""
    path = _path(_path(root) / "selection.json")
    raw = _read(path, MAX_METADATA_BYTES, mode=0o600) if path.exists() else None
    return _parse_selection(raw)


def _selection_plan(root, bundle_id, *, rollback=False):
    root = _path(root)
    path = _path(root / "selection.json")
    raw_before = _read(path, MAX_METADATA_BYTES, mode=0o600) if path.exists() else None
    before = _parse_selection(raw_before)
    if rollback:
        if "previous" not in before:
            raise ValueError("No previous native session selection is available")
        bundle_id = before["previous"]
    selected = inspect_bundle(root, bundle_id) if bundle_id is not None else None
    after = (
        before
        if before["selected"] == bundle_id
        else {"schema": SCHEMA, "selected": bundle_id, "previous": before["selected"]}
    )
    item = change(path, _json_bytes(after), expected_before=raw_before)
    item["mode"] = 0o600
    if raw_before is not None:
        item["expected_mode"] = 0o600
    observed = ([*selected["observed"]] if selected else []) + [item]
    changes = [item] if before != after else []
    return _plan(
        "native-session-selection",
        after,
        changes,
        observed,
        config=selected["config"] if selected else None,
        binary=selected["binary"] if selected else None,
        notes=[
            "Changes the next-login selection only; running sessions are unchanged.",
            "Previously staged bundles remain available for rollback.",
        ],
    )


def select_plan(root, bundle_id):
    return _selection_plan(root, bundle_id)


def rollback_plan(root):
    return _selection_plan(root, None, rollback=True)


def status(root):
    root = _path(root)
    selection = load_selection(root)
    bundles = []
    parent = _path(root / "bundles")
    if parent.exists():
        for folder in sorted(parent.iterdir()):
            if not _ID.fullmatch(folder.name):
                continue
            try:
                report = inspect_bundle(root, folder.name)
                report.pop("observed")
                bundles.append(report | {"status": "metadata-match"})
            except (OSError, ValueError, UnicodeError) as error:
                bundles.append(
                    {"bundle_id": folder.name, "status": "unavailable", "reason": str(error)}
                )
    return {
        "schema": SCHEMA,
        "root": str(root),
        "selection": selection,
        "bundles": bundles,
        "note": "Selection applies at the next NiriFX login; stock Niri is unchanged.",
    }
