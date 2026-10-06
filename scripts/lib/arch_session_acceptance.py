"""Receipt-based assertions for disposable Arch package adoption checks.

This helper reads synthetic homes and test reports. It imports neither the
installed package nor a retained runtime; archive identity, native executable
identity and retained tools identity are deliberately assessed separately.
"""

import argparse
import hashlib
import json
import re
import sysconfig
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(files):
    return hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def capture():
    home = Path.home()
    root = home / ".local/share/niri-fx/native"

    def inventory(folder):
        return {
            str(path.relative_to(home)): sha(path)
            for path in sorted(folder.rglob("*"))
            if path.is_file()
        }

    def source_files(folder):
        return {
            str(path.relative_to(folder)): sha(path)
            for path in sorted(folder.rglob("*"))
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        }

    native = read(root / "selection.json")
    tools = read(root / "tools/selection.json")
    folder = root / "bundles" / native["selected"]
    bundle = read(folder / "bundle.json")
    receipt = read(root / "tools/runtimes" / (tools["current"] + ".json"))
    assert sha(folder / "bin/niri") == bundle["binary_sha256"]
    assert all(sha(Path(path)) == value for path, value in receipt["files"].items())
    configs = bundle.get("config_files", {"config.kdl": bundle["config_sha256"]})
    assert all(sha(folder / name) == value for name, value in configs.items())
    immutable = {}
    for part in (root / "bundles", root / "tools/packages", root / "tools/runtimes"):
        immutable.update(inventory(part))
    return {
        "native_selection": native,
        "tools_selection": tools,
        "native_sha256": bundle["binary_sha256"],
        "native_build_id": bundle["native_build"]["build_id"],
        "tools_content_id": identity(source_files(Path(receipt["package"]))),
        "tools_version": receipt["version"],
        "config_files": configs,
        "customization": bundle.get("customization"),
        "external_settings": inventory(home / ".config")
        | {"saved_profile": sha(home / ".local/share/niri-fx/saved.json")},
        "immutable_files": immutable,
        "installed_native_sha256": sha(Path("/usr/lib/niri-fx/session-candidate/bin/niri")),
        "installed_tools_content_id": identity(
            source_files(Path(sysconfig.get_path("purelib")) / "niri_fx")
        ),
    }


def plan(path, home):
    result = read(path)
    assert result["dry_run"] is True
    assert re.fullmatch(r"[0-9a-f]{64}", result["plan_sha256"])
    assert all(Path(item["path"]).is_relative_to(home) for item in result["changes"])
    return result["plan_sha256"]


def assess(output):
    def load(name):
        return read(output / name)

    before, after = load("state-a-ready.json"), load("state-a-readopted.json")
    for key in ("config_files", "customization", "external_settings"):
        assert before[key] == after[key], f"Re-adoption changed {key}"
    assert all(
        after["immutable_files"].get(path) == digest
        for path, digest in before["immutable_files"].items()
    )
    assert after["native_sha256"] == after["installed_native_sha256"]
    assert after["tools_content_id"] == after["installed_tools_content_id"]
    binary = before["native_sha256"] != after["native_sha256"]
    build = before["native_build_id"] != after["native_build_id"]
    native = binary or build
    tools = before["tools_content_id"] != after["tools_content_id"]
    assert (before["tools_selection"]["current"] != after["tools_selection"]["current"]) == tools
    for key, changed in (("native_selection", native), ("tools_selection", tools)):
        old, new = before[key], after[key]
        current = "selected" if key == "native_selection" else "current"
        if changed:
            assert new[current] != old[current]
            assert new["previous"] == old[current]
        else:
            assert new == old, f"Unchanged identity unexpectedly altered {key}"
    if not native and not tools:
        assert load("readopt-a-plan.json")["changes"] == []
        assert (output / "user-a-ready.json").read_bytes() == (
            output / "user-a-readopted.json"
        ).read_bytes()
    first, replacement = load("package-check.json"), load("replacement-check.json")
    summary = {
        "archive_changed": first["sha256"] != replacement["sha256"],
        "package_version_changed": first["pkgver"] != replacement["pkgver"],
        "native_identity_changed": native,
        "native_binary_changed": binary,
        "native_build_inputs_changed": build,
        "tools_content_changed": tools,
        "tools_version_changed": before["tools_version"] != after["tools_version"],
        "read_only_review": "passed",
        "saved_recipe_preserved": "passed",
        "readoption": "passed" if native or tools else "idempotent",
        "compositor_rollback": "pending" if native else "not_assessed_identical_native_identity",
        "tools_rollback": "pending" if tools else "not_assessed_identical_tools",
        "second_user": "unchanged",
        "physical_session_acceptance": "not_assessed",
    }
    if binary and not build:
        summary["native_scope"] = (
            "Different executable bytes with the same recorded build inputs; no feature-change claim."
        )
    (output / "upgrade-assessment.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def check_rollbacks(output):
    def load(name):
        return read(output / name)

    before, adopted, final = (
        load("state-a-" + name + ".json") for name in ("ready", "readopted", "final")
    )
    summary = load("upgrade-assessment.json")
    for kind, changed, selector, current in (
        ("compositor", summary["native_identity_changed"], "native_selection", "selected"),
        ("tools", summary["tools_content_changed"], "tools_selection", "current"),
    ):
        if not changed:
            continue
        other = "tools_selection" if kind == "compositor" else "native_selection"
        rollback = load("state-a-" + kind + "-rollback.json")
        forward = load("state-a-" + kind + "-rollforward.json")
        assert rollback[selector][current] == before[selector][current]
        assert forward[selector] == adopted[selector]
        assert rollback[other] == forward[other] == adopted[other]
        for state in (rollback, forward):
            for key in ("config_files", "customization", "external_settings"):
                assert state[key] == before[key], f"{kind} rollback changed {key}"
            assert all(
                state["immutable_files"].get(path) == digest
                for path, digest in adopted["immutable_files"].items()
            )
        summary[kind + "_rollback"] = "passed"
    for key in ("native_selection", "tools_selection", "native_sha256", "tools_content_id"):
        assert final[key] == adopted[key]
    (output / "upgrade-assessment.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capture")
    plan_parser = sub.add_parser("plan")
    plan_parser.add_argument("path", type=Path)
    plan_parser.add_argument("home", type=Path)
    for name in ("assess", "rollback"):
        sub.add_parser(name).add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "capture":
        result = capture()
    elif args.command == "plan":
        result = plan(args.path, args.home)
    elif args.command == "assess":
        result = assess(args.output)
    else:
        result = check_rollbacks(args.output)
    print(result if isinstance(result, str) else json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
