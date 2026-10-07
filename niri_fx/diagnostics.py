"""Choose the configuration doctor inspects without executing discovered programs."""

from pathlib import Path

from . import native_session

_READ_ERRORS = (OSError, ValueError, KeyError, TypeError, StopIteration)


def session_context(*, socket_path=None):
    """Keep the advertised running bundle separate from the next-login selection.

    Only an inspected retained bundle can supply executable/configuration paths.
    Paths reported by an external or unknown IPC peer are never returned as a
    diagnostic pair, even when that peer advertises a familiar version string.
    """
    result = {
        "running": {
            "status": "unknown" if socket_path else "offline",
            "bundle_id": None,
            "detail": "The running NiriFX session could not be inspected.",
        },
        "next_login": {
            "status": "unknown",
            "bundle_id": None,
            "detail": "The next-login selection could not be inspected.",
        },
    }
    try:
        root = native_session.default_root()
        report = native_session.status(root, socket_path=socket_path)
        result["running"] = {
            key: report["running"].get(key) for key in ("status", "bundle_id", "detail")
        }
        selected = report["selection"]["selected"]
        next_login = next(
            (bundle for bundle in report["bundles"] if bundle["bundle_id"] == selected), None
        )
        result["next_login"] = {
            "status": next_login["status"] if next_login else "unavailable" if selected else "none",
            "bundle_id": selected,
            "detail": (
                "A retained NiriFX bundle is selected for the next login."
                if next_login and next_login["status"] == "metadata-match"
                else "The selected next-login bundle is unavailable. Its executable was not run."
                if selected
                else "No managed NiriFX bundle is selected for the next login."
            ),
        }
        if result["running"]["status"] != "matched":
            return result, None
        # Reinspect this exact retained bundle, not the IPC peer's binary path
        # or the newer selection. Its startup config can differ from files
        # reloaded later; diagnostics must not claim to observe loaded effects.
        bundle = native_session.inspect_bundle(root, result["running"]["bundle_id"])
        return result, bundle
    except _READ_ERRORS as error:
        result["running"] = {
            "status": "unknown" if socket_path else "offline",
            "bundle_id": None,
            "detail": f"Retained NiriFX session inspection was unavailable: {error}",
        }
        return result, None


def resolve_context(args, default_config, *, socket_path=None):
    """Explicit binary or config choices keep their pair; only defaults adapt."""
    native, running = session_context(socket_path=socket_path)
    explicit_binary = getattr(args, "movement_binary", None)
    explicit_config = getattr(args, "config", None)
    binary = Path(explicit_binary).expanduser().absolute() if explicit_binary is not None else None
    config = Path(default_config if explicit_config is None else explicit_config).expanduser()
    if explicit_binary is not None or explicit_config is not None:
        mode = "explicit"
        detail = (
            "Explicit diagnostic selection. Unspecified values use Niri on PATH or the normal "
            "Niri configuration; the running session does not replace either choice."
        )
    elif running is not None:
        mode = "managed-running"
        binary, config = Path(running["binary"]), Path(running["config"])
        detail = (
            "Inspecting the verified running NiriFX bundle and its startup configuration path. "
            "This checks current files, not the configuration contents already loaded by Niri."
        )
    else:
        mode = "stock-default"
        detail = (
            "Inspecting Niri on PATH and the normal Niri configuration. No running managed "
            "NiriFX bundle was verified; retained next-login executables were not selected."
        )
    return {
        "binary": binary,
        "config": config,
        "native_session": native,
        "scope": {
            "mode": mode,
            "binary": str(binary) if binary is not None else "niri",
            "config": str(config),
            "detail": detail,
        },
    }
