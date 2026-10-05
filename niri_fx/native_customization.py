"""Review portable settings against a retained baseline for the next login.

Each edit copies a complete binary/configuration pair. Saved recipes retain the
original baseline root and reuse its include graph, so Preserve removes the
previous override and repeated editing never adds nested include layers.
"""

import json
from dataclasses import asdict, replace
from pathlib import Path

from . import native_session
from .documents import MAX_DOCUMENT_BYTES, effect_document, parse_document
from .effects import render_kdl
from .fragment_motion import PRESETS as FRAGMENT_PRESETS
from .fragment_motion import render_node as fragment_node
from .native_config import inspect_snapshot
from .profiles import Profile
from .setup import apply_plan, change
from .storage import digest

RECIPE_SCHEMA = 1
BASELINE_ROOT = "customization/base-config.kdl"


def fragment_choices():
    """Canonical material and response choices; browser requests carry only an ID."""
    return {
        key: {
            "name": preset.name,
            "description": preset.description,
            "effect": asdict(preset.effect),
        }
        for key, preset in FRAGMENT_PRESETS.items()
    }


def _document(document):
    try:
        raw = json.dumps(document, allow_nan=False).encode()
    except (TypeError, ValueError) as error:
        raise ValueError("Native settings require a portable JSON document") from error
    if len(raw) > MAX_DOCUMENT_BYTES:
        raise ValueError("Native settings document must be at most 16 KiB")
    name, _, effect = parse_document(document)
    canonical = effect_document(name, effect)
    if len(json.dumps(canonical, allow_nan=False).encode()) > MAX_DOCUMENT_BYTES:
        raise ValueError("Expanded native settings document must be at most 16 KiB")
    return canonical, effect


def configuration_document(*, document=None, profile=None, preset=None, fragment_preset=None):
    """Resolve one explicit CLI choice, optionally adding canonical drag motion.

    Browser and library requests already carry their complete movement material
    and use configure_plan directly. This convenience layer expands only an
    explicitly requested continuous preset before that strict validation path.
    """
    from .catalog import PROFILES, title
    from .presets import PRESETS

    if sum(value is not None for value in (document, profile, preset)) != 1:
        raise ValueError("Choose exactly one document, profile or preset")
    if profile is not None:
        if not isinstance(profile, str) or profile not in PROFILES:
            raise ValueError("Choose a known built-in profile")
        document = effect_document(title(profile), PROFILES[profile])
    elif preset is not None:
        if not isinstance(preset, str) or preset not in PRESETS:
            raise ValueError("Choose a known built-in preset")
        document = effect_document(title(preset), PRESETS[preset])
    document, effect = _document(document)
    if fragment_preset is None:
        return document
    if not isinstance(fragment_preset, str) or fragment_preset not in FRAGMENT_PRESETS:
        raise ValueError("Choose a known continuous fragment preset")
    if not isinstance(effect, Profile):
        style = replace(effect, resize=False)
        effect = Profile(open=style, close=style, resize=style if effect.resize else None)
    effect = replace(effect, movement=FRAGMENT_PRESETS[fragment_preset].effect)
    return _document(effect_document(document["name"], effect))[0]


def _validate_choices(effect, fragment_preset, variant):
    movement = isinstance(effect, Profile) and effect.movement is not None
    pointer = isinstance(effect, Profile) and effect.pointer is not None
    if movement and variant not in ("movement", "pointer", "fragment"):
        raise ValueError("Movement settings require a retained movement-capable build")
    if pointer and variant not in ("pointer", "fragment"):
        raise ValueError("Pointer settings require a retained pointer-capable build")
    if fragment_preset is not None:
        if not isinstance(fragment_preset, str) or fragment_preset not in FRAGMENT_PRESETS:
            raise ValueError("Choose a known continuous fragment preset")
        if variant != "fragment":
            raise ValueError("Continuous fragments require a retained fragment build")
        if (
            not isinstance(effect, Profile)
            or effect.movement != FRAGMENT_PRESETS[fragment_preset].effect
        ):
            raise ValueError(
                "The continuous fragment preset requires its matching canonical movement material"
            )
    return movement, pointer


def _overlay(effect, fragment_preset, variant):
    movement, pointer = _validate_choices(effect, fragment_preset, variant)
    # The shader marker also enables the compositor's default continuous
    # response. Omitting a native settings node alone would not disable it.
    generated = render_kdl(
        effect,
        movement=movement,
        pointer=pointer,
        swap=isinstance(effect, Profile) and effect.swap is not None,
        continuous_fragments=fragment_preset is not None,
    )
    if fragment_preset is not None:
        marker = "    window-movement {\n"
        if generated.count(marker) != 1:
            raise ValueError("Expected exactly one generated movement node")
        generated = generated.replace(
            marker, marker + fragment_node(FRAGMENT_PRESETS[fragment_preset].settings), 1
        )
    return generated.encode()


def _overlay_name(files):
    for index in range(1, 10000):
        name = f"config/{index:04d}.kdl"
        if name not in files:
            return name
    raise ValueError("No owned configuration filename is available")


def _configured_root(baseline, overlay_file):
    return (
        baseline
        + b"\n// NiriFX native settings override the retained baseline below.\n"
        + f"include {json.dumps(overlay_file)}\n".encode()
    )


def validate_customization(recipe, files, baseline_root, *, variant):
    """Validate saved ownership and recipe data without regenerating old shaders."""
    fields = {
        "schema",
        "baseline_bundle",
        "baseline_files",
        "overlay_file",
        "document",
        "fragment_preset",
    }
    if (
        not isinstance(recipe, dict)
        or set(recipe) != fields
        or type(recipe["schema"]) is not int
        or recipe["schema"] != RECIPE_SCHEMA
        or not isinstance(recipe["baseline_bundle"], str)
        or not native_session._ID.fullmatch(recipe["baseline_bundle"])
        or not isinstance(recipe["baseline_files"], dict)
    ):
        raise ValueError("Invalid native customization recipe")
    baseline_hashes = recipe["baseline_files"]
    if (
        not baseline_hashes
        or set(baseline_hashes) - set(files)
        or baseline_hashes.get("config.kdl") != digest(baseline_root)
        or recipe["overlay_file"] != _overlay_name(baseline_hashes)
        or set(files) != set(baseline_hashes) | {recipe["overlay_file"]}
    ):
        raise ValueError("Native customization baseline ownership changed")
    baseline_files = {
        name: baseline_root if name == "config.kdl" else files[name] for name in baseline_hashes
    }
    if any(digest(data) != baseline_hashes[name] for name, data in baseline_files.items()):
        raise ValueError("Native customization baseline contents changed")
    inspect_snapshot("config.kdl", baseline_files)
    if files["config.kdl"] != _configured_root(baseline_root, recipe["overlay_file"]):
        raise ValueError("Native customization root no longer matches its retained baseline")
    document, effect = _document(recipe["document"])
    if document != recipe["document"]:
        raise ValueError("Native customization document is not canonical")
    _validate_choices(effect, recipe["fragment_preset"], variant)
    return {
        "schema": RECIPE_SCHEMA,
        "baseline_bundle": recipe["baseline_bundle"],
        "document": document,
        "fragment_preset": recipe["fragment_preset"],
    }


def read_recipe(root, bundle_id):
    """Return a validated saved recipe, or None for a plain staged baseline."""
    return native_session.inspect_bundle(root, bundle_id).get("customization")


def _owned_files(report):
    folder = Path(report["config"]).parent.resolve()
    return {
        Path(item["target"]).relative_to(folder).as_posix(): item["before"]
        for item in report["observed"]
    }


def configure_plan(root, base_bundle, document, *, fragment_preset=None):
    """Review a new immutable pair and a selector change; never query the desktop."""
    root = native_session._path(root)
    selector = native_session._path(root / "selection.json")
    selected_bytes = (
        native_session._read(selector, native_session.MAX_METADATA_BYTES, mode=0o600)
        if selector.exists()
        else None
    )
    selected = native_session._parse_selection(selected_bytes)
    source = native_session.inspect_bundle(root, base_bundle)
    source_files = _owned_files(source)
    original = native_session._object(source_files["bundle.json"], "native session bundle")
    document, effect = _document(document)
    if isinstance(effect, Profile) and effect.swap is not None and not source.get("swap_supported"):
        raise ValueError(
            "This retained compositor shares Move and Swap. Build an updated NiriFX session "
            "with independent swap support, or choose Preserve for Swap."
        )
    generated = _overlay(effect, fragment_preset, source["variant"])
    prior = original.get("customization")
    if prior is not None:
        baseline_bundle = prior["baseline_bundle"]
        baseline_files = {
            name: source_files[BASELINE_ROOT] if name == "config.kdl" else source_files[name]
            for name in prior["baseline_files"]
        }
    else:
        baseline_bundle = base_bundle
        baseline_files = {
            name: source_files[name]
            for name in original.get("config_files", {"config.kdl": original["config_sha256"]})
        }
    inspect_snapshot("config.kdl", baseline_files)
    overlay_file = _overlay_name(baseline_files)
    baseline_root = baseline_files["config.kdl"]
    files = baseline_files | {
        "config.kdl": _configured_root(baseline_root, overlay_file),
        overlay_file: generated,
    }
    inspect_snapshot("config.kdl", files)
    customization = {
        "schema": RECIPE_SCHEMA,
        "baseline_bundle": baseline_bundle,
        "baseline_files": {name: digest(data) for name, data in baseline_files.items()},
        "overlay_file": overlay_file,
        "document": document,
        "fragment_preset": fragment_preset,
    }
    validate_customization(customization, files, baseline_root, variant=source["variant"])
    config_hashes = {name: digest(data) for name, data in files.items()}
    identifier = native_session._bundle_id(
        original["binary_sha256"],
        config_hashes["config.kdl"],
        original["native_build"],
        config_hashes,
        customization,
    )
    folder = native_session._bundle_path(root, identifier)
    observed = list(source["observed"])
    changes = []
    if (folder / "bundle.json").exists():
        observed.extend(native_session.inspect_bundle(root, identifier)["observed"])
    else:
        if folder.exists():
            for existing in folder.rglob("*"):
                native_session._path(existing)
                if not existing.is_dir():
                    raise ValueError(
                        "Incomplete native customization exists; refusing to overwrite it"
                    )
        receipt = {
            "schema": 3,
            "bundle_id": identifier,
            "binary": "bin/niri",
            "config": "config.kdl",
            "binary_sha256": original["binary_sha256"],
            "config_sha256": config_hashes["config.kdl"],
            "native_build": original["native_build"],
            "source_manifest_sha256": original["source_manifest_sha256"],
            "config_files": config_hashes,
            "customization": customization,
        }
        outputs = {"bin/niri": source_files["bin/niri"], **files, BASELINE_ROOT: baseline_root}
        outputs.update(
            {name: data for name, data in source_files.items() if name.startswith("provenance/")}
        )
        # Publish complete owned bytes before the next-login selector. Apply's
        # validation failure rolls both back; a killed process still faces the
        # launcher's independent config preflight at the next login.
        outputs["bundle.json"] = native_session._json_bytes(receipt)
        for name, data in outputs.items():
            path = native_session._path(folder / name)
            item = change(path, data, expected_before=None)
            item["mode"] = 0o755 if name == "bin/niri" else 0o600
            changes.append(item)
        observed.extend(changes)
    next_selection = (
        selected
        if selected["selected"] == identifier
        else {
            "schema": native_session.SCHEMA,
            "selected": identifier,
            "previous": selected["selected"],
        }
    )
    selector_change = change(
        selector, native_session._json_bytes(next_selection), expected_before=selected_bytes
    )
    selector_change["mode"] = 0o600
    if selected_bytes is not None:
        selector_change["expected_mode"] = 0o600
    observed.append(selector_change)
    if next_selection != selected:
        changes.append(selector_change)
    selection = next_selection | {
        "bundle_id": identifier,
        "base_bundle": base_bundle,
        "baseline_bundle": baseline_bundle,
        "document": document,
        "fragment_preset": fragment_preset,
    }
    plan = native_session._plan(
        "native-session-configure",
        selection,
        changes,
        observed,
        config=str(folder / "config.kdl"),
        binary=str(folder / "bin/niri"),
        notes=[
            "Creates a retained binary/configuration pair and selects it for the next login.",
            "Preserve inherits the original saved baseline, including its existing styles.",
            "Global animations off or slowdown in the baseline stays in effect and can suppress "
            "or slow chosen styles.",
            "Existing bundles and stock configuration remain unchanged.",
            "The login launcher's NiriFX runtime must support bundle schema 3 before the next login.",
            "A retained build's variant does not certify the current shader interface or renderer.",
            "Apply validates this trusted executable's copied config; this is not renderer acceptance.",
        ],
    )
    plan["activation"] = "next-login"
    plan["selection_document"] = document
    plan["effect"] = document.get("actions", document.get("effect"))
    plan["desktop_motion"] = document.get("motion")
    plan["pointer"] = document.get("pointer")
    return plan


def apply_native(plan, root, *, expected=None):
    """Use the selector's shared transaction lock and retain every older bundle."""
    root = native_session._path(root)
    result = apply_plan(plan, root / "state/selection", expected)
    result.pop("restore", None)
    return result | {"activation": "next-login", "dry_run": False}
