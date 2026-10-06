"""One editable desktop source with owned stock and native effect projections.

Retained bundles contain a closed recovery configuration. The running wrapper
deliberately follows external settings; its identity never proves which external
bytes a compositor has loaded. Transactions are recoverable, not crash-atomic.
"""

import json
import os
import re
import shutil
from dataclasses import replace
from pathlib import Path

from . import native_config, native_session, setup
from .effects import render_kdl
from .profiles import Profile
from .storage import digest

FILES = {
    "runtime": "shared/runtime.kdl",
    "stock": "shared/stock.kdl",
    "native": "shared/native.kdl",
}
NATIVE_MARKER = b"// Managed by niri-fx shared settings.\n"


def _paths(root, config, binary_sha256):
    owner = digest(
        native_session._json_bytes(
            {
                "root": str(root),
                "source": str(config),
                "binary_sha256": binary_sha256,
            }
        )
    )
    directory = root / "shared" / owner
    return {
        "owner_id": owner,
        "source_config": str(config),
        "stock_include": str(config.parent / "nirifx/animations.kdl"),
        "runtime_config": str(directory / "config.kdl"),
        "native_include": str(directory / "native.kdl"),
    }


def _wrapper(shared):
    return (
        NATIVE_MARKER
        + (
            f"include {json.dumps(shared['source_config'])}\n"
            f"include {json.dumps(shared['native_include'])}\n"
        ).encode()
    )


def _owner_path(shared):
    return Path(shared["stock_include"]).with_name("shared.json")


def _read_optional(path, *, mode=None):
    return (
        native_session._read(path, native_session.MAX_CONFIG_BYTES, mode=mode)
        if path.exists()
        else None
    )


def _change(path, data, *, owned=False):
    path = native_session._path(path)
    item = setup.change(path, data)
    item["regular_only"] = True
    if item["before"] is not None:
        item["expected_mode"] = item["mode"]
        if owned and item["mode"] != 0o600:
            raise ValueError("Shared NiriFX files must remain private regular files")
    if owned:
        item["mode"] = 0o600
    return item


def _stock_binary(value):
    resolved = shutil.which(str(value))
    if resolved is None:
        raise ValueError("Choose an installed stock Niri executable")
    path = native_session._path(Path(resolved).resolve())
    data = native_session._read(path, native_session.MAX_BINARY_BYTES)
    if not os.access(path, os.X_OK):
        raise ValueError("The stock Niri validator must be executable")
    return str(path), _change(path, data)


def _common_root(config, stock):
    data = native_session._read(config, native_session.MAX_CONFIG_BYTES)
    text = data.decode()
    block = f"{setup.BEGIN}\ninclude {json.dumps(str(stock))}\n{setup.END}"
    base = setup.without_managed_block(text)
    if base != text:
        if block not in text:
            raise ValueError("The existing NiriFX include is not the expected owned stock include")
    elif re.search(r"(?mi)^\s*include\s+[^\n]*nirifx[^\n]*", text):
        raise ValueError("An unrecognized NiriFX include needs review before sharing settings")
    return (base.rstrip() + "\n\n" + block + "\n").encode()


def _projections(document, fragment_preset, variant):
    from .native_customization import _document, _overlay

    document, effect = _document(document)
    stock = (setup.OWNED + "\n" + render_kdl(effect, continuous_fragments=False)).encode()
    native_effect = (
        replace(effect, open=None, close=None, resize=None, motion=None)
        if isinstance(effect, Profile)
        else Profile()
    )
    native = NATIVE_MARKER + _overlay(native_effect, fragment_preset, variant)
    return document, stock, native


def validate_shared(root, descriptor, binary_sha256, assets, *, variant):
    """Validate retained ownership and recipe shape without consulting the source."""
    from .native_customization import _document, _validate_choices

    fields = {
        "schema",
        "owner_id",
        "source_config",
        "stock_include",
        "runtime_config",
        "native_include",
        "stock_binary",
        "source_fingerprint",
        "stock_sha256",
        "native_sha256",
        "runtime_sha256",
        "document",
        "fragment_preset",
        "baseline_bundle",
    }
    if (
        not isinstance(descriptor, dict)
        or set(descriptor) != fields
        or type(descriptor["schema"]) is not int
        or descriptor["schema"] != 1
    ):
        raise ValueError("Invalid shared-settings descriptor")
    root = native_session._path(root)
    if not isinstance(descriptor["source_config"], str):
        raise ValueError("Shared desktop configuration needs an absolute path")
    config = Path(descriptor["source_config"])
    if (
        not config.is_absolute()
        or str(config) != os.path.abspath(config)
        or config.is_relative_to(root)
    ):
        raise ValueError("Shared desktop configuration must be outside managed storage")
    if any(
        descriptor.get(key) != value for key, value in _paths(root, config, binary_sha256).items()
    ):
        raise ValueError("Shared settings paths do not match their owner")
    for key in (
        "source_fingerprint",
        "stock_sha256",
        "native_sha256",
        "runtime_sha256",
        "baseline_bundle",
    ):
        if not isinstance(descriptor[key], str) or not native_session._ID.fullmatch(
            descriptor[key]
        ):
            raise ValueError("Invalid shared settings fingerprint")
    if (
        not isinstance(descriptor["stock_binary"], str)
        or not Path(descriptor["stock_binary"]).is_absolute()
    ):
        raise ValueError("Shared settings need an explicit stock validator")
    if set(assets) != set(FILES):
        raise ValueError("Shared settings are missing retained projections")
    for key, data in assets.items():
        if not isinstance(data, bytes) or digest(data) != descriptor[key + "_sha256"]:
            raise ValueError("Retained shared settings contents changed")
    if (
        assets["runtime"] != _wrapper(descriptor)
        or not assets["stock"].startswith((setup.OWNED + "\n").encode())
        or not assets["native"].startswith(NATIVE_MARKER)
    ):
        raise ValueError("Shared projection ownership is invalid")
    document, effect = _document(descriptor["document"])
    if document != descriptor["document"]:
        raise ValueError("Shared recipe is not canonical")
    _validate_choices(effect, descriptor["fragment_preset"], variant, retained=True)
    return {
        "schema": 1,
        "baseline_bundle": descriptor["baseline_bundle"],
        "document": document,
        "fragment_preset": descriptor["fragment_preset"],
    }


def _assets(report):
    folder = Path(report.get("recovery_config", report["config"])).parent
    return {
        key: native_session._read(folder / name, native_session.MAX_CONFIG_BYTES, mode=0o600)
        for key, name in FILES.items()
    }


def _owner(root, shared):
    path = native_session._path(_owner_path(shared))
    raw = _read_optional(path, mode=0o600)
    if raw is None:
        return None, None
    value = native_session._object(raw, "shared projection owner")
    if (
        set(value) != {"schema", "root", "source_config", "bundle_id"}
        or type(value["schema"]) is not int
        or value["schema"] != 1
        or value["root"] != str(root)
        or value["source_config"] != shared["source_config"]
    ):
        raise ValueError("The stock NiriFX projection has another owner")
    report = native_session.inspect_bundle(root, value["bundle_id"])
    previous = report.get("shared")
    if previous is None or previous["source_config"] != shared["source_config"]:
        raise ValueError("The shared projection receipt is inconsistent")
    if (
        native_session._read(
            Path(shared["stock_include"]), native_session.MAX_CONFIG_BYTES, mode=0o600
        )
        != _assets(report)["stock"]
    ):
        raise ValueError("The owned stock projection changed outside NiriFX")
    return report, raw


def _mutable_changes(root, shared, assets, *, adopting=False):
    previous, owner_bytes = _owner(root, shared)
    observed = [_change(_owner_path(shared), owner_bytes, owned=True)]
    stock = Path(shared["stock_include"])
    existing = _read_optional(stock)
    if previous is None and existing is not None:
        if not adopting or not existing.startswith((setup.OWNED + "\n").encode()):
            raise ValueError("Refusing to replace an unowned stock effects file")
    native = Path(shared["native_include"])
    before_native = _read_optional(native, mode=0o600)
    owner_record = native.parent / "selection.json"
    if before_native is None and owner_record.exists():
        raise ValueError(
            "The native projection is missing but an owner record remains; preserving both for review"
        )
    if before_native is not None:
        # Another build has its own native projection. Only this owner's last
        # retained selection may authorize replacing its stable include.
        raw = _read_optional(owner_record, mode=0o600)
        record = native_session._object(raw, "native projection owner") if raw is not None else {}
        if set(record) != {"schema", "bundle_id"} or record.get("schema") != 1:
            raise ValueError("The native shared projection has no valid owner")
        old = native_session.inspect_bundle(root, record["bundle_id"])
        if (
            old.get("shared", {}).get("owner_id") != shared["owner_id"]
            or before_native != _assets(old)["native"]
        ):
            raise ValueError("The owned native projection changed outside NiriFX")
        observed.append(_change(owner_record, raw, owned=True))
    wrapper = Path(shared["runtime_config"])
    current_wrapper = _read_optional(wrapper, mode=0o600)
    if current_wrapper is not None and current_wrapper != assets["runtime"]:
        raise ValueError("The owned runtime wrapper changed outside NiriFX")
    result = [
        _change(wrapper, assets["runtime"], owned=True),
        _change(stock, assets["stock"], owned=True),
        _change(native, assets["native"], owned=True),
    ]
    # Receipts are filled after the immutable bundle identifier is known.
    return result, observed


def _selector(root, identifier):
    path = root / "selection.json"
    raw = _read_optional(path, mode=0o600)
    before = native_session._parse_selection(raw)
    after = (
        before
        if before["selected"] == identifier
        else {
            "schema": native_session.SCHEMA,
            "selected": identifier,
            "previous": before["selected"],
        }
    )
    return after, _change(path, native_session._json_bytes(after), owned=True)


def _bundle_changes(root, source, files, shared, assets):
    from .native_customization import _owned_files

    old_files = _owned_files(source)
    original = native_session._object(old_files["bundle.json"], "native session bundle")
    hashes = {name: digest(data) for name, data in files.items()}
    identifier = native_session._bundle_id(
        original["binary_sha256"],
        hashes["config.kdl"],
        original["native_build"],
        hashes,
        shared=shared,
    )
    folder = native_session._bundle_path(root, identifier)
    if (folder / "bundle.json").exists():
        return identifier, [], native_session.inspect_bundle(root, identifier)["observed"]
    receipt = {
        "schema": 4,
        "bundle_id": identifier,
        "binary": "bin/niri",
        "config": "config.kdl",
        "binary_sha256": original["binary_sha256"],
        "config_sha256": hashes["config.kdl"],
        "native_build": original["native_build"],
        "source_manifest_sha256": original["source_manifest_sha256"],
        "config_files": hashes,
        "shared": shared,
    }
    outputs = {
        "bin/niri": old_files["bin/niri"],
        **files,
        **{FILES[key]: value for key, value in assets.items()},
        **{name: data for name, data in old_files.items() if name.startswith("provenance/")},
        "bundle.json": native_session._json_bytes(receipt),
    }
    changes, observed = native_session._bundle_outputs(folder, outputs)
    return identifier, changes, observed


def _finish_plan(
    root, source, shared, assets, files, observations, *, adopting=False, root_bytes=None
):
    mutable, ownership_observations = _mutable_changes(root, shared, assets, adopting=adopting)
    identifier, writes, bundle_observations = _bundle_changes(root, source, files, shared, assets)
    owner = {
        "schema": 1,
        "root": str(root),
        "source_config": shared["source_config"],
        "bundle_id": identifier,
    }
    mutable += [
        _change(_owner_path(shared), native_session._json_bytes(owner), owned=True),
        _change(
            Path(shared["native_include"]).parent / "selection.json",
            native_session._json_bytes({"schema": 1, "bundle_id": identifier}),
            owned=True,
        ),
    ]
    if root_bytes is not None:
        mutable.append(_change(Path(shared["source_config"]), root_bytes))
    selected, selector = _selector(root, identifier)
    all_changes = [*writes, *mutable, selector]
    observed = [
        *source["observed"],
        *observations,
        *ownership_observations,
        *bundle_observations,
        *mutable,
        selector,
    ]
    plan = native_session._plan(
        "native-session-shared",
        selected
        | {
            "bundle_id": identifier,
            "base_bundle": source["bundle_id"],
            "document": shared["document"],
            "fragment_preset": shared["fragment_preset"],
        },
        [item for item in all_changes if item["before"] != item["after"]],
        observed,
        config=shared["runtime_config"],
        binary=source["binary"],
        notes=[
            "Normal Niri and NiriFX use the same editable desktop configuration and saved effects recipe.",
            "Common effects apply in both sessions; native effects remain in a separate include for this compositor build.",
            "Niri watches included files. Written settings are not proof that the running desktop loaded them.",
            "Updates use recoverable sequential file writes, not a crash-atomic multi-file switch.",
            "The retained configuration is a frozen recovery copy; recovery never rewrites later desktop edits.",
        ],
    )
    plan.update(
        shared=shared,
        activation="config-written",
        selection_document=shared["document"],
        validation_checks=[{"config": shared["source_config"], "binary": shared["stock_binary"]}],
    )
    return plan


def share_plan(root, base_bundle, config, *, stock_binary="niri"):
    """Review first adoption without moving the source or changing shell code."""
    from .native_customization import portable_recipe

    root, config = map(native_session._path, (root, config))
    if config.is_relative_to(root):
        raise ValueError("Shared desktop configuration must be outside managed storage")
    source = native_session.inspect_bundle(root, base_bundle)
    if source.get("shared") is not None:
        raise ValueError("This bundle already uses shared settings; configure its saved recipe")
    recipe = portable_recipe(root, base_bundle, report=source)
    if recipe is None:
        raise ValueError("Choose and save a NiriFX recipe before sharing desktop settings")
    binary, binary_observation = _stock_binary(stock_binary)
    return _compose(
        root,
        source,
        config,
        recipe["document"],
        recipe["fragment_preset"],
        binary,
        recipe["baseline_bundle"],
        adopting=True,
        extra_observations=[binary_observation],
    )


def _compose(
    root,
    source,
    config,
    document,
    fragment_preset,
    stock_binary,
    baseline,
    *,
    adopting=False,
    extra_observations=(),
    retained_assets=None,
):
    if retained_assets is None:
        document, stock, native = _projections(document, fragment_preset, source["variant"])
    else:
        stock, native = retained_assets["stock"], retained_assets["native"]
    from .native_customization import _document

    _, effect = _document(document)
    if isinstance(effect, Profile) and effect.swap is not None and not source.get("swap_supported"):
        raise ValueError("This retained compositor does not support independent Swap settings")
    paths = _paths(root, config, source["binary_sha256"])
    common = _common_root(config, Path(paths["stock_include"]))
    if not adopting and native_session._read(config, native_session.MAX_CONFIG_BYTES) != common:
        raise ValueError("The managed stock include changed; review shared settings adoption again")
    wrapper = _wrapper(paths)
    overrides = {
        config: common,
        Path(paths["stock_include"]): stock,
        Path(paths["runtime_config"]): wrapper,
        Path(paths["native_include"]): native,
    }
    common_snapshot = native_config.snapshot(config, overrides=overrides)
    stock_edges = []
    for item in common_snapshot["observed"]:
        path = Path(item["logical"])
        if path.is_relative_to(root):
            raise ValueError("The shared include tree cannot refer to managed native storage")
        data = overrides.get(path, item["before"])
        if data is None:
            continue
        if path != Path(paths["stock_include"]) and data.startswith((setup.OWNED + "\n").encode()):
            raise ValueError("Another managed NiriFX projection is already included")
        for include in native_config._includes(data):
            if native_config._source_include(path.parent, include.path) == Path(
                paths["stock_include"]
            ):
                stock_edges.append(path)
    if stock_edges != [config]:
        raise ValueError("The shared stock projection must be included exactly once from the root")
    recovery = native_config.snapshot(Path(paths["runtime_config"]), overrides=overrides)
    shared = {
        "schema": 1,
        **paths,
        "stock_binary": stock_binary,
        "source_fingerprint": common_snapshot["fingerprint"],
        "stock_sha256": digest(stock),
        "native_sha256": digest(native),
        "runtime_sha256": digest(wrapper),
        "document": document,
        "fragment_preset": fragment_preset,
        "baseline_bundle": baseline,
    }
    assets = {"stock": stock, "native": native, "runtime": wrapper}
    validate_shared(root, shared, source["binary_sha256"], assets, variant=source["variant"])
    return _finish_plan(
        root,
        source,
        shared,
        assets,
        recovery["files"],
        [*recovery["observed"], *extra_observations],
        adopting=adopting,
        root_bytes=common if adopting else None,
    )


def configure_shared_plan(root, base_bundle, document, *, fragment_preset=None):
    root = native_session._path(root)
    source = native_session.inspect_bundle(root, base_bundle)
    shared = source.get("shared")
    if shared is None:
        raise ValueError("Choose a shared-settings bundle")
    binary, observation = _stock_binary(shared["stock_binary"])
    return _compose(
        root,
        source,
        Path(shared["source_config"]),
        document,
        fragment_preset,
        binary,
        shared["baseline_bundle"],
        extra_observations=[observation],
    )


def selection_plan(root, bundle_id):
    """Restore a retained shared recipe, preserving current external settings."""
    root = native_session._path(root)
    report = native_session.inspect_bundle(root, bundle_id)
    shared = report["shared"]
    # Build a fresh recovery snapshot rather than claiming old external bytes
    # were restored. The requested recipe and build are kept exactly.
    binary, observation = _stock_binary(shared["stock_binary"])
    return _compose(
        root,
        report,
        Path(shared["source_config"]),
        shared["document"],
        shared["fragment_preset"],
        binary,
        shared["baseline_bundle"],
        extra_observations=[observation],
        retained_assets=_assets(report),
    )


def inspect_settings(report):
    """Observe mutable disk state; this is never a renderer-loaded receipt."""
    result = {
        "status": "unavailable",
        "source_fingerprint": None,
        "projections_match": False,
        "observed": [],
    }
    try:
        shared = report["shared"]
        source = Path(shared["source_config"])
        if native_session._read(source, native_session.MAX_CONFIG_BYTES) != _common_root(
            source, Path(shared["stock_include"])
        ):
            raise ValueError("The owned stock include boundary changed")
        snapshot = native_config.snapshot(source)
        observed = list(snapshot["observed"])
        match = True
        for key, field in (
            ("stock", "stock_include"),
            ("native", "native_include"),
            ("runtime", "runtime_config"),
        ):
            path = Path(shared[field])
            data = native_session._read(path, native_session.MAX_CONFIG_BYTES, mode=0o600)
            observed.append(_change(path, data, owned=True))
            match = match and digest(data) == shared[key + "_sha256"]
        return {
            "status": "current"
            if match and snapshot["fingerprint"] == shared["source_fingerprint"]
            else "changed",
            "source_fingerprint": snapshot["fingerprint"],
            "projections_match": match,
            "observed": observed,
        }
    except (OSError, ValueError, KeyError, TypeError):
        return result


def preflight(report):
    """Validate selected shared settings without changing or adopting any file."""
    state = inspect_settings(report)
    if state["status"] == "unavailable" or not state["projections_match"]:
        raise ValueError(
            "Shared settings are missing or changed outside their reviewed recipe; use frozen recovery or review again"
        )
    shared = report["shared"]
    setup.validate_config(shared["source_config"], shared["stock_binary"])
    setup.validate_config(shared["runtime_config"], report["binary"])
    for item in state["observed"]:
        setup.check_unchanged(item, item["before"])
    return state["observed"]


def apply_shared(plan, root, *, expected=None):
    if not isinstance(expected, str) or not expected:
        raise ValueError("Shared settings require the fingerprint from a fresh review")
    result = setup.apply_plan(plan, native_session._path(root) / "state/selection", expected)
    result.pop("restore", None)
    return result | {
        "activation": "config-written",
        "dry_run": False,
        "live": {
            "status": "unverified",
            "detail": "Settings were written. Sessions already using this wrapper watch its includes; "
            "adoption or a different compositor build needs the next login. "
            "The active configuration was not verified.",
        },
    }


def recovery_plan(root, base_bundle):
    """Select the retained closed configuration without reading external settings."""
    from .native_customization import _owned_files

    root = native_session._path(root)
    source = native_session.inspect_bundle(root, base_bundle)
    if source.get("shared") is None:
        raise ValueError("Frozen recovery requires a shared-settings bundle")
    contents = _owned_files(source)
    old = native_session._object(contents["bundle.json"], "shared bundle")
    identifier = native_session._bundle_id(
        old["binary_sha256"], old["config_sha256"], old["native_build"], old["config_files"]
    )
    folder = native_session._bundle_path(root, identifier)
    receipt = {key: value for key, value in old.items() if key != "shared"} | {
        "schema": 2,
        "bundle_id": identifier,
    }
    changes, observed = [], list(source["observed"])
    if (folder / "bundle.json").exists():
        observed.extend(native_session.inspect_bundle(root, identifier)["observed"])
    else:
        if folder.exists() and any(folder.iterdir()):
            raise ValueError("An incomplete recovery bundle exists")
        outputs = {
            name: data
            for name, data in contents.items()
            if name == "bin/niri" or name in old["config_files"] or name.startswith("provenance/")
        }
        outputs["bundle.json"] = native_session._json_bytes(receipt)
        for name, data in outputs.items():
            item = _change(folder / name, data, owned=True)
            item["mode"] = 0o755 if name == "bin/niri" else 0o600
            changes.append(item)
        observed.extend(changes)
    selection, selector = _selector(root, identifier)
    observed.append(selector)
    if selector["before"] != selector["after"]:
        changes.append(selector)
    plan = native_session._plan(
        "native-session-recovery",
        selection | {"bundle_id": identifier, "recovery_from": base_bundle},
        changes,
        observed,
        config=str(folder / "config.kdl"),
        binary=str(folder / "bin/niri"),
        notes=[
            "Selects the closed recovery configuration for the next login.",
            "The shared source and its effects files are not read or overwritten.",
        ],
    )
    plan["activation"] = "next-login"
    return plan
