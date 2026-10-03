"""Small, dependency-free preset guide; setup owns every write and snapshot.

This is a line-oriented workflow, not a second settings application. Keep the
default path about finished presets; detailed customization belongs in Studio
and the existing render/setup options.
"""

import os
from copy import copy
from pathlib import Path

from .catalog import PROFILE_RECIPES, PROFILES, RECOMMENDED, STYLES, families
from .effects import FAMILIES, PRESETS
from .setup import apply_plan, plan_setup, restore, summarize


def catalog(query="", family=None, recommended=False, *, profiles=False, all_styles=False):
    query = query.casefold().replace("-", " ").strip()
    source = PROFILES if profiles else STYLES if all_styles else PRESETS
    return [
        key
        for key, style in source.items()
        if (not recommended or key in RECOMMENDED or key in PROFILES)
        and (not family or family in families(style))
        and query
        in f"{key.replace('-', ' ')} {' '.join(families(style))} {PROFILE_RECIPES[key][2] if key in PROFILES else RECOMMENDED.get(key, '')}".casefold()
    ]


def describe(key):
    if key in PROFILES:
        opening, closing, description = PROFILE_RECIPES[key]
        return f"{key:<21} {description} · {opening} → {closing}"
    effect = PRESETS[key]
    text = RECOMMENDED.get(key, FAMILIES[effect.family]["label"])
    return f"{key:<21} {text} ({effect.open_ms}/{effect.close_ms} ms)"


def print_catalog(keys, write=print, numbered=False):
    write(("    " if numbered else "") + "Style                  Look (open → close)")
    for index, key in enumerate(keys, 1):
        write(f"{index:2}. {describe(key)}" if numbered else describe(key))


def display_path(value):
    text = str(value)
    for label, prefix in (
        ("$XDG_CONFIG_HOME", os.environ.get("XDG_CONFIG_HOME")),
        ("$XDG_STATE_HOME", os.environ.get("XDG_STATE_HOME")),
        ("~", str(Path.home())),
    ):
        if prefix and text.startswith(prefix.rstrip("/") + "/"):
            return label + text[len(prefix.rstrip("/")) :]
    return text


def undo(state, read=input, write=print):
    review = restore(state)
    write("\nUndo the latest CLI setup change:")
    for path in review["paths"]:
        write(f"  Restore {display_path(path)}")
    if review["target"] == "inir":
        write(review["note"])
    if read("Type undo to restore these files, or Enter to cancel: ").strip().lower() != "undo":
        write("Cancelled. No settings changed.")
        return
    # Pin the reviewed transaction; a later CLI change must not redirect Undo.
    restore(state, review["transaction"], True)
    write("Previous files restored exactly.")


def choose(default, read=input, write=print):
    keys = catalog(recommended=True)
    while True:
        write("")
        print_catalog(keys, write, numbered=True)
        write("Use profiles for open/close pairings, all, /search, a name, undo, or q.")
        answer = read(f"Choose a style [{default}]: ").strip().lower()
        if answer in ("q", "quit", "undo"):
            return answer
        if not answer:
            return default
        if answer == "all":
            keys = catalog(all_styles=True)
        elif answer == "profiles":
            keys = catalog(profiles=True)
        elif answer.startswith("/"):
            keys = catalog(answer[1:], all_styles=True)
            if not keys:
                write("No matching styles. Try another search or all.")
        elif answer in STYLES:
            return answer
        elif answer.isdecimal() and 1 <= int(answer) <= len(keys):
            return keys[int(answer) - 1]
        else:
            write("Choose a listed number or preset name; /slices searches a family.")


def guide(arguments, read=input, write=print):
    """Review concrete files and require one deliberate apply/undo confirmation.

    The CLI enforces a real terminal. Injectable I/O lets tests exercise races
    and cancellation while keeping every config/state path in a temp directory.
    """
    args = copy(arguments)
    write("NiriFX — pick a finished style")
    write("No editor needed. Built-in presets leave resize effects off.")
    target = args.target
    if target == "auto":
        target = "inir" if (args.inir_root / "scripts/niri-config.py").is_file() else "standalone"
    if target == "inir":
        write("\niNiR: add the built-in collection, then choose a style in iRiS.")
        write("Registration does not activate an effect or change your current animation.")
        answer = (
            read("Enter to review the collection, undo to restore, or q to leave: ").strip().lower()
        )
        if answer == "undo":
            undo(args.state, read, write)
            return
        if answer != "":
            write("Cancelled. No settings changed.")
            return
        args.preset, args.profile = "balanced", None
    else:
        write("\nStandalone Niri — choose opening and closing effects.")
        choice = choose(args.profile or args.preset, read, write)
        if choice == "undo":
            undo(args.state, read, write)
            return
        if choice in ("q", "quit"):
            write("Cancelled. No settings changed.")
            return
        args.profile = choice if choice in PROFILES else None
        args.preset = choice if choice in PRESETS else "balanced"
    # Fix the selected backend before review; installing/removing a shell while
    # the prompt is open cannot silently switch the destination of this apply.
    args.target = target
    selection = args.profile or args.preset
    effect = STYLES[selection]
    review = summarize(plan_setup(args, effect))
    write(f"\n{'Built-in collection' if target == 'inir' else selection} — {target}")
    for item in review["changes"]:
        write(f"  {item['action'].capitalize()} {display_path(item['path'])}")
    for note in review["notes"]:
        write(note)
    if not review["changes"]:
        write("Already matches. No files need changing.")
        return
    if read("Type apply to write these changes, or Enter to cancel: ").strip().lower() != "apply":
        write("Cancelled. No settings changed.")
        return
    apply_plan(plan_setup(args, effect), args.state, expected=review["plan_sha256"])
    write(
        "Collection added. Choose a style in iRiS." if target == "inir" else f"Applied {selection}."
    )
    write(f"History: {display_path(args.state)}")
    write("Undo: open this guide again and choose undo.")


def print_diagnostics(report, write=print):
    for check in report["checks"]:
        status = "OK" if check["ok"] else "FAIL" if check["ok"] is False else "INFO"
        write(f"{status:4} {check['check']}: {check['detail']}")
    write(report["resize"])
    write(report["next"])
