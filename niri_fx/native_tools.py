"""Reviewed upgrades for CLI, Studio and the NiriFX login launcher.

Runtime installation stays outside this module. A caller explicitly supplies an
existing bootstrap environment, then reviews promotion of the environment it is
running from. One retained selector keeps all stable entry points together.
"""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from . import native_session, native_tools_launcher, setup
from .branding import APP_ID, KEYWORDS
from .native_entry import _exec_argument
from .storage import digest

# This small probe runs only explicitly selected Python installations. Isolated
# mode excludes the checkout and PYTHONPATH; old releases need not implement a
# new command in order to demonstrate that they can read current bundle data.
_PROBE = r"""
import hashlib, json, pathlib, sys
root, identifiers, package_hint = json.loads(sys.argv[1])
if sys.version_info < (3, 10):
    raise ValueError("Tools require Python 3.10 or newer")
if package_hint is not None:
    sys.path.insert(0, str(pathlib.Path(package_hint).parent))
import niri_fx
from niri_fx.branding import desktop_entry
from niri_fx.native_session import inspect_bundle
prefix = pathlib.Path(sys.prefix).absolute()
package = pathlib.Path(niri_fx.__file__).resolve().parent
if sys.prefix == sys.base_prefix or not package.is_relative_to(prefix):
    raise ValueError("Use a persistent virtual environment with a normally installed NiriFX package, not an editable checkout")
for identifier in identifiers:
    inspect_bundle(pathlib.Path(root), identifier)
files = {}
paths = [prefix / "pyvenv.cfg"]
paths += sorted(p for p in package.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc")
if len(paths) > 2048:
    raise ValueError("Runtime inventory exceeds its file limit")
for path in paths:
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError("Runtime file exceeds its size limit")
    files[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
print(json.dumps({"schema": 1, "python": str(pathlib.Path(sys.executable).absolute()), "package": str(package), "version": niri_fx.__version__, "files": files, "desktop": desktop_entry().decode()}))
"""


def _probe(python, root, identifiers, *, package_path=None):
    python = Path(python).expanduser().absolute()
    _exec_argument(str(python))
    result = subprocess.run(
        [str(python), "-I", "-B", "-c", _PROBE, json.dumps([str(root), identifiers, package_path])],
        cwd="/",
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        detail = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "probe failed"
        raise ValueError(f"Tools runtime cannot read the selected and rollback bundles: {detail}")
    if len(result.stdout) > native_tools_launcher.MAX_BYTES:
        raise ValueError("Tools runtime probe exceeded its output limit")
    record = json.loads(result.stdout)
    native_tools_launcher.verify_runtime(record)
    if Path(record["python"]) != python:
        raise ValueError("Tools runtime reported a different interpreter")
    return record


def _observe(path, data=None, *, mode=None):
    if data is None:
        data = native_session._read(path, native_tools_launcher.MAX_BYTES)
    item = setup.change(path, data, expected_before=data)
    item["regular_only"] = True
    item["expected_mode"] = item["mode"] if mode is None else mode
    return item


def _owned_change(path, data, *, mode=0o600):
    path = native_session._path(path)
    item = setup.change(path, data)
    if item["before"] is not None and item["mode"] != mode:
        raise ValueError(f"Unexpected tools file permissions; preserving it: {path}")
    if item["before"] is not None and item["before"] != data:
        raise ValueError(f"Existing tools file differs; preserving it: {path}")
    item["regular_only"] = True
    item["expected_mode"] = item["mode"] if item["before"] is not None else None
    item["mode"] = mode
    return item


def _read_selection(root):
    path = root / "tools/selection.json"
    if not path.exists():
        return None, None
    raw = native_tools_launcher.read_owned(path)
    selection = json.loads(raw)
    if (
        not isinstance(selection, dict)
        or set(selection)
        != {
            "schema",
            "phase",
            "current",
            "previous",
            "bootstrap",
            "legacy",
            "cli",
            "desktop",
            "registered_entry",
            "entry",
            "assets",
        }
        or selection["schema"] != 1
        or selection["phase"] not in {"prepared", "active"}
    ):
        raise ValueError("Unsupported tools selection")
    for key in ("current", "bootstrap", "legacy"):
        if not isinstance(selection[key], str) or not native_session._ID.fullmatch(selection[key]):
            raise ValueError("Invalid tools runtime selection")
    previous = selection["previous"]
    if previous is not None and (
        not isinstance(previous, str) or not native_session._ID.fullmatch(previous)
    ):
        raise ValueError("Invalid previous tools runtime selection")
    for key in ("cli", "desktop", "registered_entry", "entry"):
        if not isinstance(selection[key], str) or not Path(selection[key]).is_absolute():
            raise ValueError("Tools entry paths must be absolute")
    if selection["entry"] != str(root / "tools/niri-fx.desktop"):
        raise ValueError("Tools entry location changed")
    _assets(root, selection)
    return selection, raw


def _bundle_observations(root):
    selector = root / "selection.json"
    raw = native_session._read(selector, native_session.MAX_METADATA_BYTES, mode=0o600)
    selection = native_session._parse_selection(raw)
    identifiers = list(
        dict.fromkeys(value for key, value in selection.items() if key != "schema" and value)
    )
    if not selection.get("selected"):
        raise ValueError("Select a native bundle before preparing its tools")
    observed = [_observe(selector, raw, mode=0o600)]
    done = []
    while identifiers:
        identifier = identifiers.pop(0)
        if identifier in done:
            continue
        if len(done) >= 8:
            raise ValueError("Native baseline references exceed the supported limit")
        report = native_session.inspect_bundle(root, identifier)
        observed.extend(report["observed"])
        done.append(identifier)
        if recipe := report.get("customization"):
            identifiers.append(recipe["baseline_bundle"])
    return done, observed


def _runtime_observations(record):
    native_tools_launcher.verify_runtime(record)
    result = []
    for name, expected in record["files"].items():
        item = setup.change(name, Path(name).read_bytes())
        if digest(item["before"]) != expected:
            raise ValueError("Runtime changed while preparing the tools review")
        item["expected_mode"] = item["mode"]
        result.append(item)
    return result


def _record(root, identifier, identifiers=None):
    path = root / "tools/runtimes" / f"{identifier}.json"
    record = native_tools_launcher.runtime_record(root / "tools", identifier)
    current = (
        _probe(record["python"], root, identifiers, package_path=record["package"])
        if identifiers is not None
        else record
    )
    if current != record:
        raise ValueError("Retained tools runtime changed; keep it installed unchanged")
    return record, [_observe(path, mode=0o600), *_runtime_observations(record)]


def _assets(root, selection=None):
    directory = root / "tools"
    if selection is not None:
        expected = {
            "launch.py": 0o600,
            "niri-fx": 0o755,
            "niri-fx.desktop": 0o600,
            "studio.desktop": 0o600,
            "niri-fx.svg": 0o600,
        }
        if not isinstance(selection.get("assets"), dict) or set(selection["assets"]) != set(
            expected
        ):
            raise ValueError("Unsupported stable tools layout")
        files = []
        for name, mode in expected.items():
            data = native_session._read(
                directory / name, native_tools_launcher.MAX_BYTES, mode=mode
            )
            if digest(data) != selection["assets"][name]:
                raise ValueError("Stable tools launcher changed; preserving it for review")
            files.append((directory / name, data, mode))
        by_name = {path.name: data for path, data, _ in files}
        return files, by_name["niri-fx.desktop"], by_name["studio.desktop"]
    launcher = _exec_argument(str(directory / "launch.py"))
    session = (
        "[Desktop Entry]\nName=NiriFX\nComment=Niri with configurable NiriFX window effects\n"
        f"Exec=/usr/bin/python3 {launcher} session\nType=Application\nDesktopNames=niri\n"
    ).encode()
    cli = f'#!/bin/sh\nexec /usr/bin/python3 {shlex.quote(launcher)} cli "$@"\n'.encode()
    icon = str(directory / "niri-fx.svg")
    desktop = (
        "[Desktop Entry]\nType=Application\nName=NiriFX Studio\n"
        "Comment=Choose and customize Niri window effects\n"
        f"Exec=/usr/bin/python3 {launcher} studio\nIcon={icon}\n"
        "Terminal=false\nCategories=Settings;DesktopSettings;\n"
        f"Keywords={';'.join(KEYWORDS)};\nStartupWMClass={APP_ID}-studio\nStartupNotify=false\n"
    ).encode()
    files = [
        (directory / "launch.py", Path(native_tools_launcher.__file__).read_bytes(), 0o600),
        (directory / "niri-fx", cli, 0o755),
        (directory / "niri-fx.desktop", session, 0o600),
        (directory / "studio.desktop", desktop, 0o600),
        (
            directory / "niri-fx.svg",
            Path(__file__).with_name("assets").joinpath("niri-fx.svg").read_bytes(),
            0o600,
        ),
    ]
    return files, session, desktop


def _registration(path, stable, bootstrap=None, root=None):
    path = native_session._path(path)
    if not path.exists():
        return False, [_owned_change(path, None)]
    raw = native_session._read(path, native_session.MAX_METADATA_BYTES)
    observed = [_observe(path, raw)]
    if raw == stable:
        return True, observed
    if bootstrap is None:
        raise ValueError("Registered session entry differs; preserve it and review registration")
    # Recognize the complete former generator, not just a friendly desktop name.
    lines = raw.decode().splitlines()
    names = [line[5:] for line in lines if line.startswith("Name=")]
    if len(names) != 1:
        raise ValueError("Registered session entry is not owned by this installation")
    name = names[0]
    python = _exec_argument(bootstrap["python"])
    legacy = (
        f"[Desktop Entry]\nName={name}\nComment=Niri with configurable NiriFX window effects\n"
        f"Exec={python} {_exec_argument(str(root / 'session/launch.py'))}\nType=Application\nDesktopNames=niri\n"
    ).encode()
    script = (
        '"""NiriFX generated per-user login launcher."""\nimport sys\n'
        f"sys.path.insert(0, {str(Path(bootstrap['package']).parent)!r})\n"
        "from niri_fx.native_login import main\n"
        f"raise SystemExit(main(['--root', {str(root)!r}, 'launch']))\n"
    ).encode()
    if (
        raw != legacy
        or native_session._read(root / "session/launch.py", native_session.MAX_METADATA_BYTES)
        != script
    ):
        raise ValueError(
            "Registered session entry is not the bootstrap runtime's generated launcher"
        )
    observed.append(_observe(root / "session/launch.py", script))
    return False, observed


def _external_changes(root, selection, bootstrap, desktop):
    cli = Path(selection["cli"])
    expected_cli = Path(bootstrap["python"]).parent / "niri-fx"
    stable_cli = root / "tools/niri-fx"
    if cli.is_symlink() and cli.readlink() not in {expected_cli, stable_cli}:
        raise ValueError("CLI launcher differs from its owned bootstrap or stable link")
    link = setup.link_change(cli, stable_cli)
    path = native_session._path(selection["desktop"])
    app = setup.change(path, desktop)
    legacy = bootstrap["desktop"].encode()
    isolated = legacy.replace(b" -m niri_fx studio", b" -I -m niri_fx studio")
    if app["before"] not in (None, desktop, legacy, isolated):
        raise ValueError("Studio launcher differs from its generated bootstrap entry")
    app["regular_only"] = True
    app["expected_mode"] = app["mode"] if app["before"] is not None else None
    return [link, app]


def _plan(root, selection, before, items, observed, notes):
    selector = setup.change(
        root / "tools/selection.json", native_session._json_bytes(selection), expected_before=before
    )
    selector["regular_only"] = True
    selector["mode"] = 0o600
    if before is not None:
        selector["expected_mode"] = 0o600
    items.append(selector)
    items = list({item["logical"]: item for item in items}.values())
    observed.extend(items)
    return {
        "target": "native-tools-update",
        "selection": selection,
        "activation": "tools-only",
        "notes": notes,
        "changes": [item for item in items if item["before"] != item["after"]],
        "observed": observed,
        "validation_config": None,
        "validation_binary": None,
    }


def update_plan(
    root,
    *,
    bootstrap_runtime=None,
    legacy_tools_runtime=None,
    registered_entry,
    cli_path=None,
    desktop_path=None,
):
    root = native_session._path(root)
    registered_entry = native_session._path(registered_entry)
    identifiers, observed = _bundle_observations(root)
    candidate = _probe(
        sys.executable, root, identifiers, package_path=str(Path(__file__).resolve().parent)
    )
    candidate_id = native_tools_launcher.fingerprint(candidate)
    observed.extend(_runtime_observations(candidate))
    selection, before = _read_selection(root)
    assets, session, desktop = _assets(root, selection)
    items = [_owned_change(path, data, mode=mode) for path, data, mode in assets]
    items.append(
        _owned_change(
            root / "tools/runtimes" / f"{candidate_id}.json", native_session._json_bytes(candidate)
        )
    )
    if selection is None:
        if bootstrap_runtime is None:
            raise ValueError(
                "First tools preparation requires --bootstrap-runtime with the existing persistent virtual environment"
            )
        bootstrap = _probe(
            Path(bootstrap_runtime).expanduser().absolute() / "bin/python", root, identifiers
        )
        bootstrap_id = native_tools_launcher.fingerprint(bootstrap)
        observed.extend(_runtime_observations(bootstrap))
        legacy = (
            _probe(
                Path(legacy_tools_runtime).expanduser().absolute() / "bin/python", root, identifiers
            )
            if legacy_tools_runtime
            else bootstrap
        )
        legacy_id = native_tools_launcher.fingerprint(legacy)
        observed.extend(_runtime_observations(legacy))
        items.append(
            _owned_change(
                root / "tools/runtimes" / f"{legacy_id}.json", native_session._json_bytes(legacy)
            )
        )
        items.append(
            _owned_change(
                root / "tools/runtimes" / f"{bootstrap_id}.json",
                native_session._json_bytes(bootstrap),
            )
        )
        data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        selection = {
            "schema": 1,
            "phase": "prepared",
            "current": bootstrap_id,
            "previous": None,
            "bootstrap": bootstrap_id,
            "legacy": legacy_id,
            "entry": str(root / "tools/niri-fx.desktop"),
            "assets": {path.name: digest(data) for path, data, _ in assets},
            "cli": str(
                Path(cli_path or Path.home() / ".local/bin/niri-fx").expanduser().absolute()
            ),
            "desktop": str(
                Path(desktop_path or data_home / "applications/niri-fx-studio.desktop")
                .expanduser()
                .absolute()
            ),
            "registered_entry": str(registered_entry),
        }
    else:
        if str(registered_entry) != selection["registered_entry"]:
            raise ValueError("Registered entry path differs from the reviewed tools installation")
        for key, value in (("cli", cli_path), ("desktop", desktop_path)):
            if value is not None and str(Path(value).expanduser().absolute()) != selection[key]:
                raise ValueError("Launcher paths differ from the reviewed tools installation")
        bootstrap, evidence = _record(
            root, selection["bootstrap"], identifiers if selection["phase"] == "prepared" else None
        )
        observed.extend(evidence)
        legacy, evidence = _record(root, selection["legacy"])
        observed.extend(evidence)
        _, evidence = _record(root, selection["current"], identifiers)
        observed.extend(evidence)
        if legacy_tools_runtime is not None and Path(
            legacy_tools_runtime
        ).expanduser().absolute() / "bin/python" != Path(legacy["python"]):
            raise ValueError("Legacy tools runtime differs from the retained receipt")
        if bootstrap_runtime is not None and Path(
            bootstrap_runtime
        ).expanduser().absolute() / "bin/python" != Path(bootstrap["python"]):
            raise ValueError("Bootstrap runtime differs from the retained tools receipt")
    registered, evidence = _registration(registered_entry, session, bootstrap, root)
    observed.extend(evidence)
    external = _external_changes(root, selection, legacy, desktop)
    # Existing launchers are observed during preparation, but are only promoted
    # after the administrator-installed entry uses the stable dispatcher.
    observed.extend(external)
    if before is None or not registered:
        if selection["phase"] == "active":
            raise ValueError("Stable login registration changed after activation")
        return _plan(
            root,
            selection,
            before,
            items,
            observed,
            [
                "Prepares retained tool runtimes without changing existing CLI, Studio or login launchers.",
                "The bootstrap runtime remains selected; the compositor and its configuration are unchanged.",
                f"Register {root / 'tools/niri-fx.desktop'} as {registered_entry} with mode 0644, then review tools-update again.",
            ],
        )
    if selection["current"] != candidate_id:
        selection = selection | {"previous": selection["current"], "current": candidate_id}
    selection = selection | {"phase": "active"}
    items.extend(external)
    return _plan(
        root,
        selection,
        before,
        items,
        observed,
        [
            "Updates owned CLI, Studio and login dispatch through one retained tools selection.",
            "Retains earlier runtimes and checks selected, rollback and baseline bundles; no compositor restart occurs.",
            "New CLI, Studio and login launches use the selected runtime. Existing processes keep their current runtime.",
        ],
    )


def rollback_plan(root, *, registered_entry):
    root = native_session._path(root)
    selection, before = _read_selection(root)
    if selection is None or selection["phase"] != "active" or not selection["previous"]:
        raise ValueError("No previous active tools runtime is available")
    if str(native_session._path(registered_entry)) != selection["registered_entry"]:
        raise ValueError("Registered entry path differs from this tools installation")
    identifiers, observed = _bundle_observations(root)
    assets, session, desktop = _assets(root, selection)
    items = [_owned_change(path, data, mode=mode) for path, data, mode in assets]
    for key in ("current", "previous"):
        _, evidence = _record(root, selection[key], identifiers)
        observed.extend(evidence)
    registered, evidence = _registration(Path(registered_entry), session)
    if not registered:
        raise ValueError("Register the stable session entry before rolling back tools")
    observed.extend(evidence)
    legacy = native_tools_launcher.runtime_record(root / "tools", selection["legacy"])
    external = _external_changes(root, selection, legacy, desktop)
    if any(item["before"] != item["after"] for item in external):
        raise ValueError("Owned tool launchers changed; review tools-update before rollback")
    observed.extend(external)
    after = selection | {"current": selection["previous"], "previous": selection["current"]}
    plan = _plan(
        root,
        after,
        before,
        items,
        observed,
        [
            "Restores the previous compatible tools runtime; retains both installations and every compositor bundle.",
            "New CLI, Studio and login launches use the restored runtime. Existing processes and desktop settings are unchanged.",
        ],
    )
    plan["target"] = "native-tools-rollback"
    return plan


def apply_tools(plan, root, expected):
    if not expected:
        raise ValueError("Tools Apply requires --expect-plan from a reviewed plan")
    if plan["target"] not in {"native-tools-update", "native-tools-rollback"}:
        raise ValueError("Unsupported tools transaction")
    if expected != setup.plan_fingerprint(plan):
        raise ValueError(
            "The setup plan changed. Review the tools selection again before applying."
        )
    root = native_session._path(root)
    for item in plan["observed"]:
        setup.check_unchanged(item, item["before"])
        # File observations bind existing bytes; also reject new package files
        # added after review, which can change Python import resolution.
        path = Path(item["logical"])
        if path.parent == root / "tools/runtimes" and path.suffix == ".json":
            native_tools_launcher.verify_runtime(json.loads(item["after"]))
    return setup.apply_plan(plan, root / "state/selection", expected)


def status(root, *, registered_entry=None):
    root = native_session._path(root)
    selection, _ = _read_selection(root)
    if selection is None:
        return {
            "installed": False,
            "phase": "unmanaged",
            "detail": "No shared tools installation is prepared.",
        }
    result = {"installed": True, **selection, "runtimes": []}
    for identifier in dict.fromkeys(
        (selection["current"], selection["previous"], selection["bootstrap"], selection["legacy"])
    ):
        if identifier is None:
            continue
        try:
            record = native_tools_launcher.runtime_record(root / "tools", identifier)
            native_tools_launcher.verify_runtime(record)
            report = {
                "id": identifier,
                "version": record["version"],
                "python": record["python"],
                "status": "intact",
            }
        except (OSError, ValueError, KeyError, TypeError) as error:
            report = {"id": identifier, "status": "unavailable", "detail": str(error)}
        result["runtimes"].append(report)
    path = native_session._path(registered_entry or selection["registered_entry"])
    stable = _assets(root, selection)[1]
    result["registered"] = (
        path.exists() and native_session._read(path, native_session.MAX_METADATA_BYTES) == stable
    )
    return result


def entry_files(root):
    """Reuse the managed login entry without reintroducing a runtime pin."""
    root = native_session._path(root)
    selection, raw = _read_selection(root)
    if selection is None or selection["phase"] != "active":
        raise ValueError(
            "Complete tools registration and activation before installing another native bundle"
        )
    identifiers, observed = _bundle_observations(root)
    runtime, evidence = _record(root, selection["current"], identifiers)
    if (
        _probe(sys.executable, root, identifiers, package_path=str(Path(__file__).resolve().parent))
        != runtime
    ):
        raise ValueError(
            "Run native installation from the selected tools runtime, or review tools-update first"
        )
    observed.extend(evidence)
    observed.append(_observe(root / "tools/selection.json", raw, mode=0o600))
    assets, session, _ = _assets(root, selection)
    observed.extend(_owned_change(path, data, mode=mode) for path, data, mode in assets)
    registered, evidence = _registration(Path(selection["registered_entry"]), session)
    if not registered:
        raise ValueError("The managed login entry is not registered")
    observed.extend(evidence)
    return {
        "target": "native-session-entry",
        "selection": {
            "entry": str(root / "tools/niri-fx.desktop"),
            "assets": {path.name: digest(data) for path, data, _ in assets},
            "launcher": str(root / "tools/launch.py"),
            "name": "NiriFX",
        },
        "activation": "Next login",
        "notes": ["Reuses the registered shared tools launcher; no launcher runtime is repinned."],
        "changes": [],
        "observed": observed,
        "validation_config": None,
        "validation_binary": None,
    }
