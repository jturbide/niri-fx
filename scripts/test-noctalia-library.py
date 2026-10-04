#!/usr/bin/env python3
"""Verify the Noctalia 5 shortcut's actual Luau launch using private XDG paths."""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.nested import NestedSession, wait_for


def exercise(binary, assets, protocol):
    with NestedSession("hotkey-overlay { skip-at-startup; }\n") as session:
        plugin = session.root / "data/noctalia/plugins/niri-fx"
        shutil.copytree(ROOT / "integrations/noctalia/niriFX", plugin)
        config = session.root / "config/noctalia"
        config.mkdir()
        # Spaces, quotes and shell metacharacters must reach argv unchanged.
        directory = str(session.config.parent / "looks ' $(never-run)")
        target = str(session.config.parent / "animation file.kdl")
        (config / "config.toml").write_text(
            '[plugins]\nenabled=["jturbide/niri-fx"]\nauto_update="none"\nsource=[]\n'
            '[[control_center.shortcuts]]\ntype="jturbide/niri-fx:library"\n'
            '[plugin_settings."jturbide/niri-fx"]\npresets_dir='
            + json.dumps(directory)
            + "\ntarget_file="
            + json.dumps(target)
            + "\n"
        )
        capture = session.root / "launch.json"
        bin_dir = session.root / "bin"
        bin_dir.mkdir()
        executable = bin_dir / "niri-fx"
        executable.write_text(
            f"#!{sys.executable}\nimport json,sys\nwith open({str(capture)!r},'w') as f: json.dump(sys.argv[1:],f)\n"
        )
        executable.chmod(0o700)
        session.env["PATH"] = str(bin_dir) + ":" + session.env["PATH"]
        session.env["NOCTALIA_ASSETS_DIR"] = str(assets.resolve())
        session.launch([str(binary.resolve())], "noctalia-library", private_bus=True)

        def ipc(*args):
            return subprocess.check_output(
                [str(binary.resolve()), "msg", *args],
                env=session.env,
                text=True,
                stderr=subprocess.PIPE,
                timeout=15,
            )

        def ready():
            try:
                return "jturbide/niri-fx" in ipc("plugins", "list")
            except subprocess.CalledProcessError:
                return False

        wait_for(ready, "Noctalia NiriFX plugin registration", 40)
        ipc("panel-toggle", "control-center")

        import time

        time.sleep(1)
        session.capture("noctalia-shortcut")

        build = session.root / "pointer"
        build.mkdir()
        for mode, name in (
            ("client-header", "virtual-pointer.h"),
            ("private-code", "virtual-pointer.c"),
        ):
            subprocess.run(
                ["wayland-scanner", mode, str(protocol.resolve()), str(build / name)],
                check=True,
                timeout=15,
            )
        flags = subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "wayland-client"], text=True
        ).split()
        client = build / "click"
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
                str(client),
                *flags,
            ],
            check=True,
            timeout=30,
        )
        # The owned output is fixed at 1440 x 900. Click the only configured
        # shortcut in Control Center Home; input cannot reach the login socket.
        subprocess.run(
            [str(client), "960", "448", "1440", "900"], env=session.env, check=True, timeout=15
        )
        wait_for(capture.exists, "Noctalia Library launch")
        assert json.loads(capture.read_text()) == [
            "studio",
            "--target",
            "noctalia",
            "--active",
            "--preset-dir",
            directory,
            "--picker-file",
            target,
        ]
        print(
            f"PASS: registered Noctalia shortcut and literal argv dispatch. Evidence: {session.root}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--pointer-protocol", type=Path, required=True)
    args = parser.parse_args()
    exercise(args.binary, args.assets, args.pointer_protocol)
