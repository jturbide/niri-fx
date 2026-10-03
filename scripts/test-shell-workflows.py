#!/usr/bin/env python3
"""Verify and optionally record real shell pickers in owned nested Niri sessions."""

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.nested import NestedSession, encode_gif, record, save_clips, source_hashes, stop, wait_for

from niri_fx.documents import load_document, parse_document
from niri_fx.effects import PRESETS, render_kdl
from niri_fx.integration import make_custom_preset, update_registry

BASE = """hotkey-overlay { skip-at-startup; }
layout { background-color "#111827"; }
animations { window-resize { duration-ms 170; curve "ease-out-cubic"; }; }
"""


def run(session, *command):
    return subprocess.check_output(
        [str(arg) for arg in command],
        env=session.env,
        text=True,
        stderr=subprocess.PIPE,
        timeout=15,
    )


def dms(session, args):
    source = args.source.resolve()
    if not (source / "Services/PluginService.qml").is_file():
        raise ValueError("DMS source must contain Services/PluginService.qml")
    qml_root = session.root / "qml"
    qml_root.mkdir()
    for folder in source.iterdir():
        if folder.is_dir():
            (qml_root / folder.name).symlink_to(folder, target_is_directory=True)
    shutil.copytree(
        ROOT / "integrations/dms/niriFX", session.root / "config/DankMaterialShell/plugins/niriFX"
    )
    qml = qml_root / "shell.qml"
    shutil.copyfile(ROOT / "scripts/fixtures/dms-host.qml", qml)
    bin_dir = session.root / "bin"
    bin_dir.mkdir()
    # The launcher starts Studio detached. Record that owned process group so
    # even the app window and HTTP server are stopped when acceptance finishes.
    pid_file = session.root / "studio-group.json"
    executable = bin_dir / "niri-fx"
    executable.write_text(
        f"#!{sys.executable}\nimport os,sys,json\n"
        f"os.chdir({str(ROOT)!r})\n"
        "if sys.argv[1:] == ['studio']:\n"
        " if os.getpgrp()!=os.getpid(): os.setsid()\n"
        f" with open({str(pid_file)!r},'w') as f: json.dump(os.getpgrp(),f)\n"
        f"os.execv({sys.executable!r},[{sys.executable!r},'-m','niri_fx',*sys.argv[1:]])\n"
    )
    executable.chmod(0o700)
    session.env["PATH"] = str(bin_dir) + ":" + os.environ["PATH"]
    session.launch(["qs", "-p", str(qml)], "dms", private_bus=True)

    def ipc(*command):
        return run(session, "qs", "ipc", "-p", qml, "call", "record", *command)

    def info():
        try:
            return json.loads(ipc("info"))
        except subprocess.CalledProcessError:
            return {}

    def present(query, selected):
        ipc("present", query)
        wait_for(lambda: info().get("selected") == selected, f"DMS result {selected}")
        time.sleep(0.8)

    wait_for(lambda: info().get("count") == len(PRESETS), "DMS catalog", 40)
    time.sleep(0.5)
    original = session.config.read_bytes()
    recorder = video = None
    try:
        if args.record:
            recorder, video = record(session, "workflow-dms")
        present("fx balanced", "Balanced")
        session.capture("dms-search")
        session.keys("-k", "Return")
        effect_file = session.config.parent / "nirifx/animations.kdl"
        wait_for(lambda: effect_file.exists() and not info().get("busy"), "DMS apply")
        assert session.config.read_bytes().startswith(original)
        assert "window-resize" not in effect_file.read_text()
        assert effect_file.read_text().endswith(render_kdl(PRESETS["balanced"]))
        present("fx undo", "Undo last NiriFX change")
        session.capture("dms-undo")
        session.keys("-k", "Return")
        wait_for(lambda: session.config.read_bytes() == original, "exact DMS restore")
        assert not effect_file.exists()
        present("fx studio", "Open NiriFX Studio")
        session.keys("-k", "Return")
        window = wait_for(
            lambda: next((w for w in session.windows() if "NiriFX Studio" in w["title"]), None),
            "Studio app window",
            30,
        )
        time.sleep(2)
        session.capture("dms-studio")
        session.msg("action", "close-window", "--id", str(window["id"]))
        time.sleep(0.8)
        if recorder:
            stop(recorder, signal.SIGINT)
        # Also prove Undo preserves an external edit. This refusal is a separate
        # acceptance check; the GIF shows the successful everyday workflow.
        present("fx balanced", "Balanced")
        session.keys("-k", "Return")
        wait_for(lambda: effect_file.exists() and not info().get("busy"), "second apply")
        edited = session.config.read_bytes() + b"// Independent user edit\n"
        session.config.write_bytes(edited)
        present("fx undo", "Undo last NiriFX change")
        session.keys("-k", "Return")
        wait_for(
            lambda: "File changed since" in info().get("status", "") and not info().get("busy"),
            "restore conflict",
        )
        assert session.config.read_bytes() == edited and effect_file.exists()
    finally:
        if pid_file.exists():
            pgid = json.loads(pid_file.read_text())
            if pgid in (os.getpgrp(), session.compositor.pid) or pgid <= 1:
                raise RuntimeError("Invalid Studio process group")
            try:
                os.killpg(pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass
    return video, [
        "real DMS launcher search",
        "keyboard selection",
        "apply",
        "exact undo",
        "Studio app launch",
        "undo refuses external edits",
        "resize preserved",
    ]


def noctalia(session, args):
    if not args.binary or not args.assets or not args.plugin:
        raise ValueError("Noctalia needs --binary, --assets and --plugin")
    # The picker displays this path. Keep personal checkout paths out of demos.
    presets = Path(session.runtime.name) / "presets"
    run(
        session,
        sys.executable,
        "-m",
        "niri_fx",
        "export-pack",
        "--output",
        presets,
        "--state",
        session.root / "pack-state",
        "--apply",
    )
    profile = parse_document(load_document(ROOT / "examples/profiles/burst-and-drift.json"))[2]
    (presets / "custom-burst-and-drift.kdl").write_text(render_kdl(profile))
    target = session.config.parent / "picker.kdl"
    target.write_text("animations {}\n")
    session.reload(BASE + 'include "picker.kdl"\n')
    shutil.copytree(args.plugin, session.root / "data/noctalia/plugins/niri-animations")
    config = session.root / "config/noctalia"
    config.mkdir()
    (config / "config.toml").write_text(
        '[plugins]\nenabled=["imjustdoingmypart/niri-animations"]\nauto_update="none"\nsource=[]\n'
        '[plugin_settings."imjustdoingmypart/niri-animations"]\npresets_dir='
        + json.dumps(str(presets))
        + "\ntarget_file="
        + json.dumps(str(target))
        + "\ninclude_prefix="
        + json.dumps(str(presets))
        + "\n"
    )
    binary = args.binary.resolve()
    session.env["NOCTALIA_ASSETS_DIR"] = str(args.assets.resolve())
    session.launch([str(binary)], "noctalia", private_bus=True)

    def ready():
        try:
            return "imjustdoingmypart/niri-animations" in run(
                session, binary, "msg", "plugins", "list"
            )
        except subprocess.CalledProcessError:
            return None

    wait_for(ready, "Noctalia plugin registration", 40)
    run(session, binary, "msg", "panel-toggle", "imjustdoingmypart/niri-animations:picker")
    time.sleep(0.8)
    recorder = video = None
    if args.record:
        recorder, video = record(session, "workflow-noctalia")
    time.sleep(0.8)
    # The real panel's tab order is Off, Random, Preset; wtype addresses only
    # this nested Wayland socket. No callback or target file is faked.
    session.keys("-k", "Tab", "-k", "Tab", "-k", "Tab", "-k", "space")
    time.sleep(0.8)
    session.capture("noctalia-dropdown")
    # Pointer hover may preselect a different row when the popup appears.
    # Reset navigation to the first row before choosing the custom profile.
    session.keys("-k", "Home", "-k", "Down", "-k", "Return")
    wait_for(lambda: "custom-burst-and-drift.kdl" in target.read_text(), "profile selection")
    assert "window-resize" not in (presets / "custom-burst-and-drift.kdl").read_text()
    run(session, "niri", "validate", "-c", session.config)
    time.sleep(1.5)
    session.capture("noctalia-profile")
    # Luau rebuilds the panel after applying; reopen to reset its tab focus.
    run(session, binary, "msg", "panel-toggle", "imjustdoingmypart/niri-animations:picker")
    time.sleep(0.3)
    run(session, binary, "msg", "panel-toggle", "imjustdoingmypart/niri-animations:picker")
    time.sleep(0.4)
    session.keys("-k", "Tab", "-k", "Tab", "-k", "Tab", "-k", "space")
    time.sleep(0.5)
    session.keys("-k", "Home", "-k", "Return")
    wait_for(lambda: "include " not in target.read_text(), "base selection")
    run(session, "niri", "validate", "-c", session.config)
    time.sleep(1)
    session.capture("noctalia-base")
    if recorder:
        stop(recorder, signal.SIGINT)
    return video, [
        "55 presets plus custom profile",
        "keyboard dropdown selection",
        "independent profile applied",
        "base restored",
        "resize preserved",
        "Niri validation",
    ]


def iris(session, args):
    source = args.source.resolve()
    helper = source / "scripts/niri-config.py"
    if not helper.is_file() or not args.pointer_protocol:
        raise ValueError("iRiS needs --source and --pointer-protocol (wlr virtual pointer XML)")
    # Compile the protocol client locally. No generated or third-party protocol
    # bindings are shipped, and input uses only this session's nested socket.
    build = session.root / "pointer"
    build.mkdir()
    for mode, target in (
        ("client-header", "virtual-pointer.h"),
        ("private-code", "virtual-pointer.c"),
    ):
        subprocess.run(
            ["wayland-scanner", mode, str(args.pointer_protocol.resolve()), str(build / target)],
            check=True,
            timeout=15,
        )
    flags = subprocess.check_output(
        ["pkg-config", "--cflags", "--libs", "wayland-client"], text=True
    ).split()
    pointer = build / "click"
    subprocess.run(
        [
            "cc",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-I",
            str(build),
            str(ROOT / "scripts/fixtures/click.c"),
            str(build / "virtual-pointer.c"),
            "-o",
            str(pointer),
            *flags,
        ],
        check=True,
        timeout=30,
    )
    # The shell helper selects this legacy directory when it exists, matching
    # the gallery service's watcher. Both paths are inside the temporary XDG tree.
    registry = session.root / "config/illogical-impulse/niri-animation-presets.json"
    registry.parent.mkdir()
    target = session.config.parent / "config.d/60-animations.kdl"
    target.parent.mkdir()
    target.write_text("animations {}\n")
    session.reload(
        "hotkey-overlay { skip-at-startup; }\nprefer-no-csd\n"
        'layout { background-color "#111827"; focus-ring { off; }; border { off; }; }\n'
        'window-rule { match title="NiriFX / iRiS gallery acceptance"; open-floating true; '
        'default-floating-position x=120 y=80 relative-to="top-left"; }\n'
        'include "config.d/60-animations.kdl"\n'
    )
    applied = json.loads(run(session, sys.executable, helper, "apply-animation-preset", "snappy"))
    assert applied["success"], applied
    original = target.read_bytes()
    catalog = json.loads(run(session, sys.executable, helper, "get-animation-presets"))
    profiles = [
        make_custom_preset(catalog, load_document(ROOT / "examples/profiles" / file), "snappy")
        for file in ("burst-and-drift.json", "frost-and-fragments.json")
    ]
    update_registry(registry, profiles)
    qml_root = session.root / "qml"
    qml_root.mkdir()
    for item in source.iterdir():
        if not item.name.startswith(".") and item.name != "shell.qml":
            (qml_root / item.name).symlink_to(item, target_is_directory=item.is_dir())
    qml = qml_root / "shell.qml"
    shutil.copyfile(ROOT / "scripts/fixtures/iris-host.qml", qml)
    session.launch(["qs", "-p", str(qml)], "iris", private_bus=True)

    def ipc(*command):
        return run(session, "qs", "ipc", "-p", qml, "call", "record", *command)

    def info():
        try:
            return json.loads(ipc("info"))
        except subprocess.CalledProcessError:
            return {}

    wait_for(lambda: info().get("ready"), "iRiS gallery", 40)
    assert info()["active"] == "snappy", info()
    time.sleep(1)
    recorder = video = None
    if args.record:
        recorder, video = record(session, "workflow-iris")
    for preset in [*profiles, {"id": "snappy"}]:
        session.focus()
        point = json.loads(ipc("locate", preset["id"]))
        assert point and 0 <= point["x"] < 1060 and 0 <= point["y"] < 740, point
        time.sleep(0.6)
        run(session, pointer, round(point["x"] + 120), round(point["y"] + 80), 1440, 900)
        wait_for(
            lambda identifier=preset["id"]: info().get("active") == identifier,
            f"iRiS selection {preset['id']}",
        )
        actual = json.loads(run(session, sys.executable, helper, "get-animation-presets"))
        assert actual["active"] == preset["id"], actual["active"]
        run(session, "niri", "validate", "-c", session.config)
        if "types" in preset:
            base = next(p for p in catalog["presets"] if p["id"] == "snappy")
            assert preset["types"]["window-resize"] == base["types"]["window-resize"]
        time.sleep(1.5)
        session.capture(preset["id"])
    assert target.read_bytes() == original
    if recorder:
        stop(recorder, signal.SIGINT)
    return video, [
        "actual iRiS gallery and service",
        "pointer selection",
        "two independent profiles",
        "resize preserved",
        "exact prior style restored",
        "Niri validation",
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shell", choices=("dms", "noctalia", "iris"))
    parser.add_argument("--source", type=Path, help="DMS or iNiR QML source directory")
    parser.add_argument(
        "--pointer-protocol", type=Path, help="wlr virtual pointer protocol XML for iRiS"
    )
    parser.add_argument("--binary", type=Path, help="Noctalia binary")
    parser.add_argument("--assets", type=Path, help="Noctalia release assets")
    parser.add_argument("--plugin", type=Path, help="Noctalia Niri Animations source")
    parser.add_argument("--version", required=True, help="Tested release label, stored in evidence")
    parser.add_argument("--record", action="store_true")
    args = parser.parse_args()
    if args.shell in ("dms", "iris") and not args.source:
        parser.error(f"{args.shell} requires --source")
    with NestedSession(BASE) as session:
        video, checks = {"dms": dms, "noctalia": noctalia, "iris": iris}[args.shell](session, args)
        session.check_render_log()
        result = {
            "name": "workflow-" + args.shell,
            "backend": f"actual {args.shell} picker UI in stock nested Niri",
            "version": args.version,
            "checks": checks,
        }
        source_files = {
            "dms": ["Services/PluginService.qml", "Modals/DankLauncherV2/DankLauncherV2Modal.qml"],
            "iris": [
                "services/NiriAnimationPresets.qml",
                "modules/iris/settings/IrisNiriMotionGallery.qml",
                "scripts/niri-config.py",
            ],
        }
        files = (
            [args.source / p for p in source_files[args.shell]]
            if args.source
            else [args.binary, args.plugin / "panel.luau"]
        )
        result["tested_sources"] = {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files
        }
        if args.shell != "dms":
            profiles = ["examples/profiles/burst-and-drift.json"]
            if args.shell == "iris":
                profiles.append("examples/profiles/frost-and-fragments.json")
            result["sources"] = source_hashes(*profiles)
        if video:
            dest = ROOT / "docs/gifs" / (result["name"] + ".gif")
            # Noctalia's surrounding bar can show host network information via
            # system D-Bus. Publish only its picker, excluding that entire bar.
            crop = {"noctalia": "640:500:400:220", "iris": "1060:740:120:80"}.get(args.shell)
            encode_gif(video, dest, width=1060 if args.shell == "iris" else 960, crop=crop)
            result.update(file=str(dest.relative_to(ROOT)), bytes=dest.stat().st_size)
            save_clips([result])
        (session.root / "checks.json").write_text(json.dumps(result, indent=2) + "\n")
        print(f"PASS {args.shell}: {', '.join(checks)}; evidence: {session.root}")


if __name__ == "__main__":
    main()
