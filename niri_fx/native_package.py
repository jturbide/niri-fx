"""Explicit package adoption into retained tools and compositor storage.

Review reads bytes only. Package replacement never selects a runtime; Apply
copies a pure-Python snapshot and promotes compatible tools before the compositor.
"""

import ast
import json
import os
import subprocess
from pathlib import Path

from . import (
    __version__,
    native_build,
    native_session,
    native_tools,
    native_tools_launcher,
    package_session,
    setup,
)
from .native_install import install_plan
from .storage import digest

REGISTERED_ENTRY = Path("/usr/share/wayland-sessions/niri-fx-packaged.desktop")
SESSION_LAUNCHER = Path("/usr/bin/niri-fx-session")
PACKAGE_DIRECTORY = Path(__file__).resolve().parent

_SOURCE_PROBE = r"""
import json, pathlib, sys
package, root, identifiers = json.loads(sys.argv[1])
sys.path.insert(0, str(pathlib.Path(package).parent))
import niri_fx
from niri_fx.cli import main as cli_main
from niri_fx.native_login import main as login_main
from niri_fx.native_session import inspect_bundle
assert callable(cli_main) and callable(login_main)
for identifier in identifiers:
    inspect_bundle(pathlib.Path(root), identifier)
print(json.dumps({"package": str(pathlib.Path(niri_fx.__file__).resolve().parent), "version": niri_fx.__version__}))
"""


def _source_files(package):
    files = {}
    observed = []
    total = 0
    for path in native_tools_launcher.package_files(package):
        data = native_session._read(path, 32 * 1024 * 1024)
        total += len(data)
        if total > 128 * 1024 * 1024:
            raise ValueError("Retained tools package exceeds its total size limit")
        files[str(path.relative_to(package))] = data
        observed.append(native_tools._observe(path, data))
    if not files or "__init__.py" not in files:
        raise ValueError("Incomplete tools package")
    if set(files) != {
        str(path.relative_to(package)) for path in native_tools_launcher.package_files(package)
    }:
        raise ValueError("Tools source inventory changed during review")
    return files, observed


def _snapshot(root):
    source = native_session._path(PACKAGE_DIRECTORY)
    files, observed = _source_files(source)
    # Do not execute a second installation during review or copy a version that
    # changed underneath the already-running adoption command.
    versions = [
        node.value.value
        for node in ast.parse(files["__init__.py"]).body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "__version__" for target in node.targets
        )
        and isinstance(node.value, ast.Constant)
    ]
    if versions != [__version__]:
        raise ValueError("Installed tools changed; restart the package adoption command")
    hashes = {name: digest(data) for name, data in files.items()}
    identifier = native_tools_launcher.fingerprint(hashes)
    package = root / "tools/packages" / identifier / "niri_fx"
    if package.exists():
        existing = {
            str(path.relative_to(package))
            for path in native_tools_launcher.package_files(package, allow_bytecode=False)
        }
        if existing - set(files):
            raise ValueError("Retained tools snapshot contains unexpected files")
    changes = [native_tools._owned_change(package / name, data) for name, data in files.items()]
    return package, files, changes, observed, {"path": str(source), "files": hashes}


def _asset_changes(root, selection, source_files):
    migration = {
        "launch.py": source_files["native_tools_launcher.py"],
        "niri-fx.desktop": package_session.DESKTOP_ENTRY,
    }
    assets, _, _ = native_tools._assets(root, selection, migration_assets=migration)
    result = []
    hashes = {}
    desktop = None
    for path, old_data, mode in assets:
        data = (
            source_files["native_tools_launcher.py"]
            if path.name == "launch.py"
            else package_session.DESKTOP_ENTRY
            if path.name == "niri-fx.desktop"
            else old_data
        )
        # Existing assets have already passed the retained selection's hash and
        # mode checks. Only the dispatcher and login entry need migration.
        if selection:
            item = setup.change(path, data, expected_before=old_data)
            item.update(regular_only=True, expected_mode=mode, mode=mode)
        else:
            # A terminated first adoption may already have written these exact
            # generated assets. Resume without overwriting any different bytes.
            item = native_tools._owned_change(path, data, mode=mode)
        result.append(item)
        hashes[path.name] = digest(data)
        if path.name == "studio.desktop":
            desktop = data
    return result, hashes, desktop


def adopt_plan(root, candidate, config=None, *, registered_entry=REGISTERED_ENTRY):
    root = native_session._path(root)
    if root != native_session._path(package_session.default_root()):
        raise ValueError(
            "The packaged session uses this user's default XDG native storage; "
            "keep a custom-root installation on its existing per-user login entry"
        )
    registered_entry = native_session._path(registered_entry)
    registered = native_session._read(
        registered_entry, native_session.MAX_METADATA_BYTES, mode=0o644
    )
    if registered != package_session.DESKTOP_ENTRY:
        raise ValueError("Install the package's unchanged generic login entry before adoption")
    launcher_path = native_session._path(SESSION_LAUNCHER)
    launcher_bytes = native_session._read(launcher_path, native_session.MAX_METADATA_BYTES)
    if not os.access(launcher_path, os.X_OK):
        raise ValueError("The installed packaged-session dispatcher is not executable")
    candidate = native_session._path(candidate)
    manifest_path = candidate / "manifest.json"
    manifest_bytes = native_session._read(manifest_path, native_session.MAX_METADATA_BYTES)
    manifest = native_session._object(manifest_bytes, "packaged session candidate")
    metadata = manifest.get("native_build")
    inputs = metadata.get("inputs") if isinstance(metadata, dict) else None
    if (
        not isinstance(inputs, dict)
        or inputs.get("variant") != "fragment"
        or native_build.patch_sequence(inputs) != native_build.STACKS["fragment"]
    ):
        raise ValueError(
            "Package adoption requires the complete four-patch NiriFX session candidate"
        )
    current = native_session.load_selection(root)
    if current["selected"]:
        if config is not None:
            raise ValueError(
                "Existing adoption preserves current settings; omit --config for updates"
            )
        from .native_upgrade import upgrade_plan

        base = upgrade_plan(root, candidate)
        compatible_bundles, bundle_observed = native_tools._bundle_observations(root)
    else:
        if config is None:
            raise ValueError("Fresh package adoption requires --config")
        base = install_plan(root, candidate, config, include_entry=False)
        compatible_bundles = []
        bundle_observed = []
    if any(
        item["before"] != manifest_bytes
        for item in base["observed"]
        if item["logical"] == str(manifest_path)
    ):
        raise ValueError("Session candidate changed during package adoption review")

    package, source_files, runtime_changes, source_observed, source = _snapshot(root)
    # Only adoption may recognize an interrupted migration's exact replacement
    # dispatcher/entry. All other assets still require their recorded hashes.
    selection, before = native_tools._read_selection(
        root,
        migration_assets={
            "launch.py": source_files["native_tools_launcher.py"],
            "niri-fx.desktop": package_session.DESKTOP_ENTRY,
        },
    )
    if selection is not None and selection["phase"] != "active":
        raise ValueError("Complete the existing tools migration before adopting the package")
    if selection is None and (root / "session/launch.py").exists():
        raise ValueError(
            "Migrate the existing per-user launcher with native tools-update first; "
            "package adoption preserves unrecognized launchers"
        )
    assets, asset_hashes, desktop = _asset_changes(root, selection, source_files)
    record = {
        "schema": 2,
        "python": "/usr/bin/python3",
        "package": str(package),
        "version": __version__,
        "files": {str(package / name): digest(data) for name, data in source_files.items()},
        "desktop": desktop.decode(),
    }
    identifier = native_tools_launcher.fingerprint(record)
    receipt = native_tools._owned_change(
        root / "tools/runtimes" / f"{identifier}.json", native_session._json_bytes(record)
    )
    runtime_observed = []
    if selection is None:
        data_home = package_session.default_root().parents[1]
        selection = {
            "schema": 1,
            "phase": "active",
            "current": identifier,
            "previous": None,
            "bootstrap": identifier,
            "legacy": identifier,
            "entry": str(root / "tools/niri-fx.desktop"),
            "assets": asset_hashes,
            "cli": str(Path.home() / ".local/bin/niri-fx"),
            "desktop": str(data_home / "applications/niri-fx-studio.desktop"),
            "registered_entry": str(registered_entry),
        }
        legacy = record
    else:
        for old_id in dict.fromkeys(
            selection[key] for key in ("current", "previous", "bootstrap", "legacy")
        ):
            if old_id:
                _, evidence = native_tools._record(root, old_id)
                runtime_observed.extend(evidence)
        legacy = native_tools_launcher.runtime_record(root / "tools", selection["legacy"])
        selection = selection | {
            "assets": asset_hashes,
            "registered_entry": str(registered_entry),
            "previous": selection["current"]
            if selection["current"] != identifier
            else selection["previous"],
            "current": identifier,
        }
    external = native_tools._external_changes(root, selection, legacy, desktop)
    tools_selector = setup.change(
        root / "tools/selection.json", native_session._json_bytes(selection), expected_before=before
    )
    tools_selector.update(regular_only=True, mode=0o600, expected_mode=0o600 if before else None)
    compositor_selector = str(root / "selection.json")
    # A crash after the tools selector but before compositor selection leaves
    # the new tools reading the previous, already-inspected compositor bundle.
    ordered = [
        *runtime_changes,
        receipt,
        *(item for item in base["changes"] if item["logical"] != compositor_selector),
        *assets,
        *external,
        tools_selector,
        *(item for item in base["changes"] if item["logical"] == compositor_selector),
    ]
    observations = [
        *base["observed"],
        *bundle_observed,
        *source_observed,
        *runtime_observed,
        native_tools._observe(registered_entry, registered),
        native_tools._observe(launcher_path, launcher_bytes),
        native_tools._observe(manifest_path, manifest_bytes),
        *ordered,
    ]
    return base | {
        "target": "native-session-adopt",
        "selection": base["selection"]
        | {
            "native_root": str(root),
            "tools_runtime": identifier,
            "tools_version": __version__,
            "runtime_source": source,
            "compatible_bundles": compatible_bundles,
            "registered_entry": str(registered_entry),
        },
        "activation": "Next packaged NiriFX login",
        "changes": [item for item in ordered if item["before"] != item["after"]],
        "observed": observations,
        "notes": [
            *base["notes"],
            "Copies this package's pure-Python tools into retained user storage before selecting them.",
            "Apply probes the trusted source tools against retained bundles; review executes no programs.",
            "Package updates and removals do not rewrite retained tools or compositor bundles.",
            "The generic login entry performs no adoption; use NiriFX (package) at the next login.",
            "The system Python and compositor shared libraries remain distribution dependencies.",
        ],
    }


def _validate_source(root, source, identifiers):
    """Apply-only compatibility check; the installed package is trusted code."""
    result = subprocess.run(
        [
            "/usr/bin/python3",
            "-I",
            "-B",
            "-c",
            _SOURCE_PROBE,
            json.dumps([source["path"], str(root), identifiers]),
        ],
        cwd="/",
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "probe failed"
        raise ValueError(
            f"Package tools cannot read retained bundles or load session entry points: {detail}"
        )
    if len(result.stdout) > native_tools_launcher.MAX_BYTES or json.loads(result.stdout) != {
        "package": source["path"],
        "version": __version__,
    }:
        raise ValueError("Package tools reported a different source or version")


def apply_adoption(plan, root, expected):
    if not expected or expected != setup.plan_fingerprint(plan):
        raise ValueError("Package adoption requires --expect-plan from the unchanged reviewed plan")
    if plan["target"] != "native-session-adopt":
        raise ValueError("Unsupported package adoption transaction")
    root = native_session._path(root)
    if str(root) != plan["selection"]["native_root"] or root != native_session._path(
        package_session.default_root()
    ):
        raise ValueError("Package adoption storage changed after review")
    source = plan["selection"]["runtime_source"]
    files, _ = _source_files(Path(source["path"]))
    if {name: digest(data) for name, data in files.items()} != source["files"]:
        raise ValueError("Tools source inventory changed after review")
    # Even an idempotent Apply must observe package updates, altered launchers
    # and new files inside earlier retained runtimes.
    for item in plan["observed"]:
        setup.check_unchanged(item, item["before"])
        path = Path(item["logical"])
        if path.parent == root / "tools/runtimes":
            if item["before"] is not None:
                native_tools_launcher.verify_runtime(json.loads(item["before"]))
            elif item["after"] is not None:
                record = json.loads(item["after"])
                package = Path(record["package"])
                if record["schema"] == 2 and package.exists():
                    actual = {
                        str(path)
                        for path in native_tools_launcher.package_files(
                            package, allow_bytecode=False
                        )
                    }
                    if actual - set(record["files"]):
                        raise ValueError("Retained tools snapshot inventory changed after review")
    _validate_source(root, source, plan["selection"]["compatible_bundles"])
    # The probe imports trusted source, but must not change the reviewed package
    # inventory before its files are copied into immutable storage.
    files, _ = _source_files(Path(source["path"]))
    if {name: digest(data) for name, data in files.items()} != source["files"]:
        raise ValueError("Tools source inventory changed during compatibility validation")
    result = setup.apply_plan(plan, root / "state/selection", expected)
    result.pop("restore", None)
    return result
