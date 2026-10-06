"""Prepare the complete NiriFX login session through one reviewed transaction."""

from . import native_session
from .native_entry import entry_files
from .setup import change


def install_plan(root, candidate, config, *, name="NiriFX", include_entry=True):
    """Review a full candidate, owned config snapshot, launcher and next login.

    Candidate layout is fixed by the source builder. Frozen patch evidence is
    read from that attempt, never from today's mutable repository checkout.
    The plan creates no directories and executes no candidate during review.
    """
    root, candidate, config = map(native_session._path, (root, candidate, config))
    manifest_path = candidate / "manifest.json"
    manifest_data = native_session._read(manifest_path, native_session.MAX_METADATA_BYTES)
    manifest = native_session._object(manifest_data, "NiriFX session candidate")
    binary = manifest.get("binary")
    if (
        not isinstance(binary, str)
        or not binary
        or manifest.get("source") != "source"
        or native_session._path(candidate / binary).resolve() != (candidate / "bin/niri").resolve()
    ):
        raise ValueError(
            "NiriFX installation requires the candidate's own bin/niri and source layout"
        )
    metadata = manifest.get("native_build")
    if (
        not isinstance(metadata, dict)
        or not isinstance(metadata.get("inputs"), dict)
        or metadata["inputs"].get("variant") != "fragment"
    ):
        raise ValueError("NiriFX installation requires the complete session feature stack")
    # Capture selection before inspecting large files. The reviewed fingerprint
    # and Apply's observations refuse another selection made during that work.
    selector = native_session._path(root / "selection.json")
    previous_bytes = (
        native_session._read(selector, native_session.MAX_METADATA_BYTES, mode=0o600)
        if selector.exists()
        else None
    )
    previous = native_session._parse_selection(previous_bytes)
    stage = native_session.stage_plan(
        manifest_path,
        candidate / "source",
        candidate,
        config,
        root,
        snapshot_includes=True,
        patch_directory=candidate / "patches",
    )
    # The initial layout/variant checks must describe the same manifest that
    # stage inspected, even if a producer replaced it between the two reads.
    manifest_observation = next(
        item for item in stage["observed"] if item["target"] == str(manifest_path.resolve())
    )
    if manifest_observation["before"] != manifest_data:
        raise ValueError("NiriFX session candidate changed during installation review")
    identifier = stage["selection"]["bundle_id"]
    after = (
        previous
        if previous["selected"] == identifier
        else {
            "schema": native_session.SCHEMA,
            "selected": identifier,
            "previous": previous["selected"],
        }
    )
    selection_change = change(
        selector, native_session._json_bytes(after), expected_before=previous_bytes
    )
    selection_change["mode"] = 0o600
    if previous_bytes is not None:
        selection_change["expected_mode"] = 0o600
    entry = (
        entry_files(root, name)
        if include_entry
        else {"selection": {}, "changes": [], "observed": [], "notes": []}
    )
    changes = [*stage["changes"], *entry["changes"]]
    if after != previous:
        changes.append(selection_change)
    folder = native_session._bundle_path(root, identifier)
    plan = native_session._plan(
        "native-session-install",
        stage["selection"] | entry["selection"] | after,
        changes,
        [*stage["observed"], *entry["observed"], selection_change],
        config=str(folder / "config.kdl"),
        binary=str(folder / "bin/niri"),
        notes=[
            "Prepares the complete NiriFX session and selects its pair for the next login.",
            "Copies the supplied config and its include tree; source and stock settings stay unchanged.",
            "Uses the candidate's frozen build evidence; review executes no programs.",
            "Apply writes the selector last, then validates the copied config; handled failure restores owned bytes.",
            "Existing bundles remain available for native rollback; the running desktop is unchanged.",
            *entry["notes"],
            "Metadata and configuration validation do not establish renderer or physical desktop acceptance.",
        ],
    )
    plan["activation"] = "Administrator registration, then next login"
    return plan
