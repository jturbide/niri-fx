"""Replace a selected compositor while retaining its exact saved settings.

Package upgrades must not regenerate shaders from newer preset defaults. Frozen
bundles keep their bytes; shared bundles keep their projections and take a new
recovery snapshot of the user's current desktop settings.
"""

from pathlib import Path

from . import native_build, native_session, native_shared
from .native_customization import BASELINE_ROOT, _owned_files
from .native_install import install_plan
from .storage import digest


def _prepared_source(root, plan):
    """Adapt reviewed candidate bytes for the existing shared-bundle composer.

    These in-memory observations describe proposed bytes, not filesystem reads.
    The caller removes them from the final plan and binds the real candidate
    observations instead. No temporary bundle is written during review.
    """
    identifier = plan["selection"]["bundle_id"]
    folder = native_session._bundle_path(root, identifier)
    files = {}
    for item in [*plan["observed"], *plan["changes"]]:
        path = Path(item["target"])
        if path.is_relative_to(folder):
            data = item.get("after", item["before"])
            if data is not None:
                files[path.relative_to(folder).as_posix()] = data
    receipt = native_session._object(files["bundle.json"], "prepared native bundle")
    inputs = receipt["native_build"]["inputs"]
    return {
        "bundle_id": identifier,
        "binary": str(folder / "bin/niri"),
        "config": str(folder / "config.kdl"),
        "binary_sha256": receipt["binary_sha256"],
        "variant": inputs["variant"],
        "swap_supported": "niri-swap.patch" in native_build.patch_sequence(inputs),
        "observed": [
            {"target": str(folder / name), "before": data} for name, data in files.items()
        ],
    }


def _frozen_plan(root, old, prepared, observations):
    contents, incoming = _owned_files(old), _owned_files(prepared)
    previous = native_session._object(contents["bundle.json"], "selected native bundle")
    candidate = native_session._object(incoming["bundle.json"], "prepared native bundle")
    names = previous.get("config_files", {"config.kdl": previous["config_sha256"]})
    hashes = {name: digest(contents[name]) for name in names}
    recipe = previous.get("customization")
    identifier = native_session._bundle_id(
        candidate["binary_sha256"], hashes["config.kdl"], candidate["native_build"], hashes, recipe
    )
    folder = native_session._bundle_path(root, identifier)
    receipt = {
        key: candidate[key]
        for key in ("binary", "binary_sha256", "native_build", "source_manifest_sha256")
    } | {
        "schema": 3 if recipe else 2,
        "bundle_id": identifier,
        "config": "config.kdl",
        "config_sha256": hashes["config.kdl"],
        "config_files": hashes,
    }
    if recipe:
        receipt["customization"] = recipe
    changes = []
    if (folder / "bundle.json").exists():
        observations.extend(native_session.inspect_bundle(root, identifier)["observed"])
    else:
        if folder.exists() and any(
            path.is_file() or path.is_symlink() for path in folder.rglob("*")
        ):
            raise ValueError("An incomplete upgrade bundle exists; preserving it for review")
        outputs = {
            "bin/niri": incoming["bin/niri"],
            **{name: contents[name] for name in names},
            **({BASELINE_ROOT: contents[BASELINE_ROOT]} if recipe else {}),
            **{name: data for name, data in incoming.items() if name.startswith("provenance/")},
            "bundle.json": native_session._json_bytes(receipt),
        }
        for name, data in outputs.items():
            item = native_shared._change(folder / name, data, owned=True)
            item["mode"] = 0o755 if name == "bin/niri" else 0o600
            changes.append(item)
        observations.extend(changes)
    selected, selector = native_shared._selector(root, identifier)
    observations.append(selector)
    if selector["before"] != selector["after"]:
        changes.append(selector)
    return native_session._plan(
        "native-session-upgrade",
        selected | {"bundle_id": identifier},
        changes,
        observations,
        config=str(folder / "config.kdl"),
        binary=str(folder / "bin/niri"),
    )


def upgrade_plan(root, candidate):
    """Review a new full-session build without resetting the selected recipe."""
    root = native_session._path(root)
    selected = native_session.load_selection(root)["selected"]
    if selected is None:
        raise ValueError("Choose a configuration when adopting the first packaged session")
    old = native_session.inspect_bundle(root, selected)
    stage = install_plan(
        root, candidate, old.get("recovery_config", old["config"]), include_entry=False
    )
    # install_plan captures selection independently; refuse a concurrent switch
    # rather than upgrading the recipe of an earlier selection.
    selector = next(
        item for item in stage["observed"] if item["target"] == str(root / "selection.json")
    )
    if native_session._parse_selection(selector["before"])["selected"] != selected:
        raise ValueError("Native selection changed during upgrade review")
    prepared = _prepared_source(root, stage)
    observations = [*old["observed"], *stage["observed"]]
    if shared := old.get("shared"):
        binary, stock_observation = native_shared._stock_binary(shared["stock_binary"])
        plan = native_shared._compose(
            root,
            prepared,
            Path(shared["source_config"]),
            shared["document"],
            shared["fragment_preset"],
            binary,
            shared["baseline_bundle"],
            extra_observations=[stock_observation],
            retained_assets=native_shared._assets(old),
        )
        proposed = {id(item) for item in prepared["observed"]}
        plan["observed"] = [
            item for item in plan["observed"] if id(item) not in proposed
        ] + observations
        # The prepared source is an in-memory adapter, not a retained baseline.
        # Expose the actual selection being upgraded in the public review.
        plan["selection"]["base_bundle"] = selected
        folder = native_session._bundle_path(root, plan["selection"]["bundle_id"])
        plan["validation_binary"] = str(folder / "bin/niri")
    else:
        plan = _frozen_plan(root, old, prepared, observations)
    plan["activation"] = "next-login"
    plan["notes"] += [
        "Retains the selected recipe and shader bytes without adopting newer preset defaults.",
        "Keeps the previous compositor and settings available for rollback.",
        "Selects the new compositor for the next login; the running desktop is unchanged.",
    ]
    return plan
