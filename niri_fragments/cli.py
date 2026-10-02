"""Dependency-free command line interface."""

import argparse
from dataclasses import replace
from importlib.resources import files
import json
from pathlib import Path
import subprocess
import sys

from . import __version__
from .effects import PRESETS, describe_presets, render_kdl, shader
from .integration import default_inir_root, default_registry, make_presets, read_shell_presets, update_registry


def parser():
    root = argparse.ArgumentParser(description="Window fragment animations and native iNiR/iRiS presets.")
    root.add_argument("--version", action="version", version=__version__)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="Print built-in effect parameters as JSON")
    for name, help_text in (("render", "Print a standalone Niri KDL animation override"),
                            ("preview", "Write a self-contained WebGL preview; does not touch Niri")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--preset", choices=PRESETS, default="balanced")
        command.add_argument("--tile-size", type=float, help="Square size in logical pixels (8–128)")
        command.add_argument("--scatter", type=float, help="Radial scatter in logical pixels (0–240)")
        command.add_argument("--open-ms", type=int)
        command.add_argument("--close-ms", type=int)
        if name == "preview":
            command.add_argument("--output", type=Path, required=True)
    register = commands.add_parser("register", help="Add presets to iNiR/iRiS settings without activating them")
    register.add_argument("--inir-root", type=Path, default=default_inir_root())
    register.add_argument("--base", default="auto", help="Base movement preset; defaults to the active recognized preset")
    unregister = commands.add_parser("unregister", help="Remove only niri-fragments entries from the user preset registry")
    for command in (register, unregister):
        command.add_argument("--registry", type=Path, default=default_registry())
        command.add_argument("--dry-run", action="store_true", help="Print the proposed registry; write nothing")
    return root


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "list":
            print(json.dumps(describe_presets(), indent=2))
        elif arguments.command in ("render", "preview"):
            overrides = {k: getattr(arguments, k) for k in ("tile_size", "scatter", "open_ms", "close_ms")
                         if getattr(arguments, k) is not None}
            effect = replace(PRESETS[arguments.preset], **overrides)
            if arguments.command == "render":
                print(render_kdl(effect), end="")
            else:
                document = files("niri_fragments").joinpath("preview.html").read_text()
                payload = {"shader": shader(effect, False), "openMs": effect.open_ms,
                           "closeMs": effect.close_ms, "name": arguments.preset}
                document = document.replace("@EFFECT_JSON@", json.dumps(payload).replace("</", "<\\/"))
                # Exclusive creation protects an existing preview or unrelated file.
                with arguments.output.open("x") as output:
                    output.write(document)
                print(arguments.output.resolve())
        else:
            generated = make_presets(read_shell_presets(arguments.inir_root), arguments.base) if arguments.command == "register" else []
            result = update_registry(arguments.registry, generated,
                                     remove=arguments.command == "unregister", dry_run=arguments.dry_run)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"niri-fragments: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
