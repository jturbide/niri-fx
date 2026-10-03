#!/usr/bin/env python3
"""Run two synthetic clients in a separate Niri window, never a login session."""
import argparse
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from niri_fragments.effects import FAMILIES, PRESETS, movement_shader, render_kdl

BASE = '''layout {
    gaps 24
    default-column-width { proportion 0.42; }
    center-focused-column "never"
    focus-ring { off; }
    border { off; }
    background-color "#111827"
}
prefer-no-csd
hotkey-overlay { skip-at-startup; }
binds {
    Alt+Left { move-column-left; }
    Alt+Right { move-column-right; }
    Alt+R { switch-preset-column-width; }
    Alt+Q { quit skip-confirmation=true; }
}
'''


def config(effect, duration, source):
    # One animations node per file. Stock exports never include this extension.
    common = render_kdl(effect).rstrip()
    assert common.endswith("}")
    return BASE + common[:-1] + f'''    window-movement {{
        duration-ms {duration}
        curve "linear"
''' + (f'        custom-shader r"\n{source}\n"\n' if source is not None else '') + '    }\n}\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preset", choices=[name for name, effect in PRESETS.items() if FAMILIES[effect.family]["movement"]], default="explosion")
    parser.add_argument("--duration-ms", type=int, default=1100)
    parser.add_argument("--resize", action="store_true", help="Opt into fragment resize effects in the demo")
    parser.add_argument("--smoke", action="store_true", help="Capture movement, resize and fallback, then exit; needs grim and Pillow")
    args = parser.parse_args()
    if not 100 <= args.duration_ms <= 3000:
        parser.error("duration must be 100–3000 ms")
    if not os.environ.get("WAYLAND_DISPLAY"):
        parser.error("Run inside the existing Wayland desktop; this launcher will not start a TTY session")
    if not shutil.which("alacritty"):
        parser.error("alacritty is required for the synthetic demo clients")
    if args.smoke:
        if not shutil.which("grim"):
            parser.error("grim is required for --smoke")
        from PIL import Image  # Optional test dependency, not required by the demo.
    manifest_file = ROOT / "artifacts/niri-movement-build.json"
    if not manifest_file.exists():
        parser.error("Build first: python3 scripts/build-niri-movement.py")
    manifest = json.loads(manifest_file.read_text())
    binary = Path(manifest["binary"])
    if (hashlib.sha256((ROOT / "experimental/niri-movement.patch").read_bytes()).hexdigest() != manifest["patch_sha256"]
            or hashlib.sha256(binary.read_bytes()).hexdigest() != manifest["binary_sha256"]):
        parser.error("The patch or binary changed; rebuild before launching the demo")
    root = Path(tempfile.mkdtemp(prefix="nested-demo-", dir=ROOT / "artifacts"))
    cfg = root / "config.kdl"
    effect = replace(PRESETS[args.preset], resize=args.resize or args.smoke,
                     resize_ms=900 if args.smoke else 550)
    source = movement_shader(effect)
    cfg.write_text(config(effect, args.duration_ms, source))
    subprocess.run([str(binary), "validate", "-c", str(cfg)], check=True)
    env = os.environ.copy()
    env.pop("NIRI_SOCKET", None)
    env.pop("DISPLAY", None)  # Force nesting on the existing Wayland display.
    clients = []
    with (root / "niri.log").open("w") as log:
        # Deliberately no --session, no user config and no startup shell/bar.
        process = subprocess.Popen([str(binary), "-c", str(cfg)], env=env, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                text = (root / "niri.log").read_text()
                ipc = re.search(r"IPC listening on: (\S+)", text)
                display = re.search(r"listening on Wayland socket: (\S+)", text)
                if ipc and display:
                    break
                if process.poll() is not None:
                    raise RuntimeError(f"Nested compositor exited; inspect {root / 'niri.log'}")
                time.sleep(0.1)
            else:
                raise RuntimeError("Nested compositor did not become ready")
            env.update(NIRI_SOCKET=ipc[1], WAYLAND_DISPLAY=display[1])
            (root / "session.json").write_text(json.dumps({"pid": process.pid, "socket": ipc[1], "display": display[1]}))
            def msg(*arguments):
                return subprocess.check_output([str(binary), "msg", *arguments], env=env, text=True)
            for name, color in (("blue", "#245d8a"), ("orange", "#985235")):
                terminal = root / f"{name}.toml"
                terminal.write_text(f'''[window]
decorations = "None"
[colors.primary]
background = "{color}"
foreground = "#ffffff"
[font]
size = 16
[cursor.style]
blinking = "Never"
''')
                content = f"\033[2J\033[H\033[?25l\n  FRAGMENTS / {name.upper()}\n\n  Alt + Left / Right: move\n  Alt + R: resize\n  Alt + Q: exit demo\n\n" + (f"\n  {name.upper()} WINDOW\n" * 6)
                code = f"print({content!r}, flush=True); input()"
                clients.append(subprocess.Popen(["alacritty", "--config-file", str(terminal),
                    "--title", f"Fragments demo / {name}", "-e", "python3", "-c", code],
                    env=env, stdout=log, stderr=log))
            print(f"Nested demo: Alt+Left/Right to swap columns, Alt+R to resize, Alt+Q to close.\nLogs: {root}", flush=True)
            if args.smoke:
                time.sleep(2.5)
                def capture(name):
                    dest = root / f"{name}.png"
                    subprocess.run(["grim", str(dest)], env=env, check=True)
                    return dest
                def colors(filename):
                    with Image.open(filename) as image:
                        counts = image.convert("RGB").getcolors(image.width * image.height)
                        blue = sum(n for n, (r, g, b) in counts if b > r * 1.6 and g > r * 1.3 and b > 80)
                        orange = sum(n for n, (r, g, b) in counts if r > b * 1.8 and r > g * 1.4 and r > 100)
                        return blue, orange
                before = colors(capture("before"))
                windows_before = json.loads(msg("-j", "windows"))
                assert len(windows_before) == 2, "Both demo clients must be mapped"
                # Ensure the right column is active regardless of client startup order.
                right = max(windows_before, key=lambda w: w["layout"]["pos_in_scrolling_layout"][0])
                msg("action", "focus-window", "--id", str(right["id"]))
                msg("action", "move-column-left")
                time.sleep(args.duration_ms / 2000)
                middle = colors(capture("movement"))
                time.sleep(args.duration_ms / 1000 + 0.3)
                after = colors(capture("after"))
                windows_after = json.loads(msg("-j", "windows"))
                for old in windows_before:
                    new = next(w for w in windows_after if w["id"] == old["id"])
                    assert new["layout"]["pos_in_scrolling_layout"][0] != old["layout"]["pos_in_scrolling_layout"][0]
                for initial, fragmented, final in zip(before, middle, after):
                    assert initial > 1000 and 0 < fragmented < initial * 0.85, (before, middle, after)
                    assert abs(final - initial) < initial * 0.02, (before, after)
                # Retarget while movement is still running. An even number of
                # swaps must return both windows intact to their starting slots.
                for index in range(6):
                    msg("action", "move-column-right" if index % 2 == 0 else "move-column-left")
                    time.sleep(0.12)
                time.sleep(args.duration_ms / 1000 + 0.3)
                repeated = colors(capture("repeated"))
                repeated_windows = json.loads(msg("-j", "windows"))
                assert {w["id"]: w["layout"]["pos_in_scrolling_layout"] for w in repeated_windows} == {
                    w["id"]: w["layout"]["pos_in_scrolling_layout"] for w in windows_after}
                for initial, final in zip(after, repeated):
                    assert abs(final - initial) < initial * 0.02, (after, repeated)
                msg("action", "set-column-width", "60%")
                time.sleep(0.43)
                capture("resize")
                time.sleep(1)
                capture("resized")
                # Removing the shader must recover ordinary movement on hot reload.
                cfg.write_text(config(effect, args.duration_ms, None))
                time.sleep(0.6)
                msg("action", "move-column-right")
                time.sleep(args.duration_ms / 2000)
                capture("fallback")
                time.sleep(args.duration_ms / 1000)
                # Re-enable, swap, then close the moving client. After closing
                # and layout settlement, no fragments from it may remain.
                cfg.write_text(config(effect, args.duration_ms, source))
                time.sleep(0.6)
                msg("action", "move-column-left")
                time.sleep(0.15)
                msg("action", "close-window", "--id", str(right["id"]))
                time.sleep(max(effect.close_ms, args.duration_ms) / 1000 + 1)
                closed = colors(capture("close-during-movement"))
                remaining = json.loads(msg("-j", "windows"))
                assert len(remaining) == 1 and remaining[0]["id"] != right["id"]
                victim_index = 0 if "blue" in right["title"] else 1
                assert closed[victim_index] == 0 and closed[1 - victim_index] > 1000, closed
                assert process.poll() is None
                errors = re.findall(r".*(?:error compiling|error rendering|panicked|error loading config).*", (root / "niri.log").read_text())
                assert not errors, errors
                (root / "checks.json").write_text(json.dumps({"before": before, "movement": middle, "after": after,
                    "repeated": repeated, "close_during_movement": closed, "errors": errors}, indent=2))
                print("PASS: real swap, six interrupted swaps, close during movement, resize and shader-removal fallback.")
            else:
                process.wait()
        finally:
            for client in clients:
                if client.poll() is None:
                    client.terminate()
                try:
                    client.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    client.kill()
                    client.wait()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == "__main__":
    main()
