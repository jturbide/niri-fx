#!/usr/bin/env python3
"""Exercise the shared app's adapters against stock Niri and an installed iNiR helper.

All XDG paths and configs belong to the nested session. This verifies the real
iNiR serializer and active-preset recognition, not a mock or the login desktop.
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.nested import NestedSession, wait_for

from niri_fx.documents import effect_document
from niri_fx.integration import default_inir_root
from niri_fx.library import Library
from niri_fx.presets import PRESETS
from niri_fx.profiles import Profile


def exercise(source):
    import subprocess

    base = 'hotkey-overlay { skip-at-startup; }\ninclude "config.d/60-animations.kdl"\n'
    with NestedSession("hotkey-overlay { skip-at-startup; }\n") as session:
        animation = session.config.parent / "config.d/60-animations.kdl"
        animation.parent.mkdir()
        animation.write_text("animations { slowdown 1.25; }\n")
        session.reload(base)
        registry = session.root / "config/illogical-impulse/niri-animation-presets.json"
        registry.parent.mkdir()
        helper = source / "scripts/niri-config.py"

        def shell(*args):
            return json.loads(
                subprocess.check_output(
                    [sys.executable, str(helper), *args], env=session.env, text=True, timeout=30
                )
            )

        assert shell("apply-animation-preset", "snappy")["success"]
        args = SimpleNamespace(
            config=session.config,
            registry=registry,
            inir_root=source,
            state=session.root / "state/niri-fx",
            base="auto",
        )
        original = animation.read_bytes()
        root_before = session.config.read_bytes()
        selection = {
            "document": effect_document(
                "Night Motion", Profile(PRESETS["zipper"], PRESETS["frost-vanish"])
            ),
            "allow_resize": False,
            "allow_movement": False,
        }
        with patch.dict(os.environ, session.env):
            library = Library(args, "inir")
            plan = library.review(selection)
            assert animation.read_bytes() == original and not registry.exists()
            library.apply({"selection": selection, "expected": plan["plan_sha256"]})
            assert shell("get-animation-presets")["active"] == "niri-fx-custom-night-motion"
            assert "slowdown 1.25" in animation.read_text()
            active_shell = shell("get-animation-presets")
            active = next(p for p in active_shell["presets"] if p["id"] == active_shell["active"])
            base_preset = next(p for p in active_shell["presets"] if p["id"] == "snappy")
            assert active["types"].get("window-movement") == base_preset["types"].get(
                "window-movement"
            )
            library.store({"document": selection["document"], "expected": None})
            assert library.listing()["active"]["name"] == "Night Motion"
            test_iris_entry(session, source)
            assert animation.read_bytes() == original and not registry.exists()
            assert shell("get-animation-presets")["active"] == "snappy"
            assert session.config.read_bytes() == root_before
            for target in ("standalone", "noctalia"):
                if target == "noctalia":
                    args.picker_file = session.config.parent / "picker.kdl"
                    args.picker_file.write_text("animations {\n slowdown 1.25\n}\n")
                    args.preset_dir = session.config.parent / "presets"
                    session.reload(base + 'include "picker.kdl"\n')
                before = session.config.read_bytes()
                library = Library(args, target)
                plan = library.review(selection)
                library.apply({"selection": selection, "expected": plan["plan_sha256"]})
                subprocess.run(
                    ["niri", "validate", "-c", str(session.config)],
                    env=session.env,
                    check=True,
                    capture_output=True,
                )
                library.undo()
                assert session.config.read_bytes() == before
        print(
            f"PASS: iNiR active recognition, globals, stock movement omission; standalone and Noctalia Apply/Restore. Evidence: {session.root}"
        )


def test_iris_entry(session, source):
    import importlib.util
    import subprocess

    # Only the settings directory is copied for the prototype; all other shell
    # modules are read through symlinks. The installed iNiR tree is never edited.
    (session.root / "data/inir").symlink_to(source, target_is_directory=True)
    qml = session.root / "qml"
    qml.mkdir()
    for item in source.iterdir():
        if item.name not in ("modules", "shell.qml") and not item.name.startswith("."):
            (qml / item.name).symlink_to(item, target_is_directory=item.is_dir())
    modules = qml / "modules"
    modules.mkdir()
    for item in (source / "modules").iterdir():
        if item.name != "iris":
            (modules / item.name).symlink_to(item, target_is_directory=item.is_dir())
    iris = modules / "iris"
    iris.mkdir()
    for item in (source / "modules/iris").iterdir():
        if item.name != "settings":
            (iris / item.name).symlink_to(item, target_is_directory=item.is_dir())
    shutil.copytree(source / "modules/iris/settings", iris / "settings")
    spec = importlib.util.spec_from_file_location(
        "iris_installer", ROOT / "scripts/install-iris-integration.py"
    )
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    from niri_fx.setup import apply_plan

    apply_plan(installer.plan(qml), session.root / "ui-state")
    host = qml / "shell.qml"
    shutil.copyfile(ROOT / "scripts/fixtures/iris-host.qml", host)
    bin_dir = session.root / "bin"
    bin_dir.mkdir()
    dispatch = session.root / "studio-dispatch.json"
    executable = bin_dir / "niri-fx"
    executable.write_text(
        f"#!{sys.executable}\nimport os,sys,json\nos.chdir({str(ROOT)!r})\n"
        "if sys.argv[1] == 'studio' and '--restore' not in sys.argv and '--status' not in sys.argv:\n"
        f" with open({str(dispatch)!r},'w') as f: json.dump(sys.argv[1:],f)\n"
        "else:\n"
        f" os.execv({sys.executable!r},[{sys.executable!r},'-m','niri_fx',*sys.argv[1:]])\n"
    )
    executable.chmod(0o700)
    session.env["PATH"] = str(bin_dir) + ":" + session.env["PATH"]
    session.launch(["qs", "-p", str(host)], "iris-entry", private_bus=True)

    def ipc(*args):
        return subprocess.check_output(
            ["qs", "ipc", "-p", str(host), "call", "record", *args],
            env=session.env,
            text=True,
            stderr=subprocess.PIPE,
            timeout=15,
        )

    def state():
        try:
            return json.loads(ipc("fxInfo"))
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return {}

    wait_for(lambda: state().get("available") and state().get("selected"), "compact iRiS entry", 40)
    assert state()["restore"]
    assert state()["active"] == "NiriFX · Night Motion"
    session.capture("iris-compact-entry")
    assert "true" in ipc("clickFX", "Choose effects")
    wait_for(dispatch.exists, "library dispatch")
    assert json.loads(dispatch.read_text()) == ["studio", "--target", "inir", "--active"]
    dispatch.unlink()
    assert "true" in ipc("clickFX", "Customize")
    wait_for(dispatch.exists, "editor dispatch")
    assert json.loads(dispatch.read_text())[-1] == "--edit"
    assert "true" in ipc("clickFX", "Restore previous")
    wait_for(
        lambda: not state().get("selected") and not state().get("restore"),
        "iRiS restore and watcher refresh",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inir-root", type=Path, default=default_inir_root())
    exercise(parser.parse_args().inir_root.resolve())
