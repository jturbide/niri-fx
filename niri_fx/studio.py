"""Local effect editor. Only validated named presets can be saved to iNiR."""

import base64
import json
import os
import secrets
import shutil
import subprocess
import time
import webbrowser
from dataclasses import asdict
from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .branding import APP_ID
from .effects import (
    ELASTIC_ANCHORS,
    ELASTIC_AXES,
    FAMILIES,
    GRAVITIES,
    LIMITS,
    PARAMETERS,
    PRESET_SCHEMA,
    PRESETS,
    RELEASES,
    RESIZE_MODES,
    ROTATIONS,
    SLICE_DIRECTIONS,
    SLICE_ORDERS,
    Effect,
    describe_presets,
    shader_templates,
)
from .integration import make_custom_preset, read_shell_presets, update_registry


def parameter_controls():
    groups = {}
    for key, spec in PARAMETERS.items():
        if key == "family":
            continue
        attrs = f'id="{key}"'
        if spec["type"] == "number":
            low, high = spec["limits"]
            control = f'<input {attrs} type="range" min="{16 if key == "particles" else low}" max="{high}" step="{1 if spec["integer"] else "any"}" />'
            output = f' <output id="{key}-value"></output>'
        elif spec["type"] == "boolean":
            control, output = f'<input {attrs} type="checkbox" />', ""
        else:
            options = "".join(
                f'<option value="{escape(value)}">{escape(value.replace("-", " ").title())}</option>'
                for value in spec["choices"]
            )
            control, output = f"<select {attrs}>{options}</select>", ""
        wrapper = (
            ' id="count-control"'
            if key == "particles"
            else ' id="tile-control"'
            if key == "tile_size"
            else ""
        )
        groups.setdefault(spec["group"], []).append(
            f'<div{wrapper} class="parameter" data-parameter="{key}"><label for="{key}">{escape(spec["label"])}{output}</label>{control}<button type="button" class="reset-parameter" data-reset="{key}" aria-label="Reset {escape(spec["label"])}">Reset</button></div>'
        )
    result = []
    for group, controls in groups.items():
        if group == "general":
            group = "resize"  # resize boolean uses the same opt-in group
        if group == "fragments":
            controls.insert(
                0,
                '<div><label for="density">Particle sizing</label><select id="density"><option value="count">Target particle count</option><option value="tile">Fixed square size</option></select></div>',
            )
        identifier = {"fragments": "fragment", "slices": "slice"}.get(group, group)
        # Basic family settings stay visible; detailed variation is collapsible.
        if group == "variation":
            result.append(
                '<details id="variation-controls" class="wide"><summary>Advanced waves and variation</summary>'
                + "".join(controls)
                + '<small id="variation-note"></small><span id="slice-variation"></span></details>'
            )
        else:
            result.append(
                f'<div id="{identifier}-controls" class="wide parameter-group">'
                + "".join(controls)
                + "</div>"
            )
    return "".join(result)


def preview_document(effect, name="balanced", connection=None, preferences=None):
    from .profiles import Profile

    profile = effect.document(name) if isinstance(effect, Profile) else None
    if profile:
        effect = effect.open

    payload = {
        "schema": PRESET_SCHEMA,
        "profile": profile,
        "preferences": preferences,
        "specifications": PARAMETERS,
        "parameters": asdict(effect),
        "name": name,
        "presets": describe_presets(),
        "templates": shader_templates(),
        "gravities": GRAVITIES,
        "rotations": ROTATIONS,
        "releases": RELEASES,
        "resize_modes": RESIZE_MODES,
        "limits": LIMITS,
        "defaults": asdict(Effect()),
        "families": FAMILIES,
        "slice_directions": SLICE_DIRECTIONS,
        "slice_orders": SLICE_ORDERS,
        "elastic_axes": ELASTIC_AXES,
        "elastic_anchors": ELASTIC_ANCHORS,
        "connection": connection,
    }
    data = json.dumps(payload).replace("</", "<\\/")
    root = files("niri_fx")
    return (
        root.joinpath("preview.html")
        .read_text()
        .replace("@EFFECT_JSON@", data)
        .replace("@PARAMETER_CONTROLS@", parameter_controls())
        .replace(
            "@APP_ICON@",
            base64.b64encode(root.joinpath("assets/niri-fx.svg").read_bytes()).decode(),
        )
        .replace(
            "<!--@MOTION_JS@-->",
            "<script>" + root.joinpath("motion-preview.js").read_text() + "</script>",
        )
        .replace(
            "<!--@STUDIO_CSS@-->", "<style>" + root.joinpath("studio.css").read_text() + "</style>"
        )
        .replace(
            "<!--@STUDIO_JS@-->", "<script>" + root.joinpath("studio.js").read_text() + "</script>"
        )
    )


def open_studio(url, browser=False):
    """Use a separate Chromium app profile; do not borrow personal browser state."""
    if not browser:
        for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
            executable = shutil.which(name)
            if not executable:
                continue
            state = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
            profile = state / APP_ID / "studio-profile"
            profile.mkdir(parents=True, exist_ok=True)
            try:
                subprocess.Popen(
                    [
                        executable,
                        "--app=" + url,
                        "--user-data-dir=" + str(profile),
                        f"--class={APP_ID}-studio",
                        f"--name={APP_ID}-studio",
                        "--window-size=1320,960",
                        "--no-first-run",
                        "--no-default-browser-check",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return "app"
            except OSError:
                continue
    webbrowser.open(url)
    return "browser"


def valid_save_request(headers, origin, token):
    return (
        headers.get("Host") == urlsplit(origin).netloc
        and headers.get("Origin") == origin
        and headers.get("Content-Type", "").split(";")[0].strip() == "application/json"
        and secrets.compare_digest(headers.get("X-NiriFX-Token", "").encode(), token.encode())
    )


def make_server(arguments, effect):
    token = secrets.token_urlsafe(32)
    preferences_path = (
        Path(getattr(arguments, "state", Path(arguments.registry).parent))
        / "studio-preferences.json"
    )

    def read_preferences():
        try:
            value = json.loads(preferences_path.read_text())
            return {
                "favorites": [
                    name for name in value["favorites"] if isinstance(name, str) and name in PRESETS
                ]
            }
        except (OSError, ValueError, KeyError, TypeError):
            return {"favorites": []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Keep the per-session token out of request logs.

        def respond(self, status, content, content_type="application/json"):
            payload = content.encode() if isinstance(content, str) else json.dumps(content).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type + "; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            request = urlsplit(self.path)
            supplied = parse_qs(request.query).get("token", [""])[0]
            if (
                self.headers.get("Host") != urlsplit(self.server.origin).netloc
                or request.path not in ("/", "/ping")
                or not secrets.compare_digest(supplied.encode(), token.encode())
            ):
                self.respond(403, {"error": "Open the editor using its local session URL."})
                return
            self.server.last_seen = time.monotonic()
            if request.path == "/ping":
                self.respond(200, {"ok": True})
                return
            self.respond(
                200,
                preview_document(
                    effect,
                    getattr(arguments, "custom_name", arguments.preset),
                    {"origin": self.server.origin, "token": token},
                    read_preferences(),
                ),
                "text/html",
            )

        def do_POST(self):
            if self.path not in ("/save", "/preferences") or not valid_save_request(
                self.headers, self.server.origin, token
            ):
                self.respond(403, {"error": "Save request must come from this editor session."})
                return
            try:
                self.server.last_seen = time.monotonic()
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 16384:
                    raise ValueError("Preset request must be between 1 and 16384 bytes")
                data = json.loads(self.rfile.read(length))
                if self.path == "/preferences":
                    from .setup import atomic_write

                    if (
                        not isinstance(data, dict)
                        or set(data) != {"favorites"}
                        or not isinstance(data["favorites"], list)
                        or len(data["favorites"]) > len(PRESETS)
                        or any(
                            not isinstance(name, str) or name not in PRESETS
                            for name in data["favorites"]
                        )
                    ):
                        raise ValueError("Preferences must contain a list of built-in favorites")
                    if preferences_path.is_symlink():
                        raise ValueError("Studio preferences cannot be a symlink")
                    atomic_write(
                        preferences_path,
                        (json.dumps({"favorites": sorted(set(data["favorites"]))}) + "\n").encode(),
                    )
                    self.respond(200, {"ok": True})
                    return
                registry = read_shell_presets(arguments.inir_root)
                preset = make_custom_preset(registry, data, arguments.base)
                result = update_registry(arguments.registry, [preset])
                self.respond(
                    200,
                    {
                        "id": preset["id"],
                        "name": preset["name"],
                        "changed": result["changed"],
                        "backup": result["backup"],
                    },
                )
            except (OSError, ValueError, subprocess.SubprocessError) as error:
                self.respond(400, {"error": str(error)})

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

    server = HTTPServer(("127.0.0.1", arguments.port), Handler)
    server.origin = f"http://127.0.0.1:{server.server_port}"
    server.session_url = server.origin + "/?token=" + token
    server.last_seen = time.monotonic()
    return server


def serve(arguments, effect):
    if not 0 <= arguments.port <= 65535:
        raise ValueError("port must be between 0 and 65535")
    with make_server(arguments, effect) as server:
        print(f"NiriFX Studio: {server.session_url}", flush=True)
        print(
            "Save adds a preset to iRiS; select it there to activate. Ctrl+C stops the editor.",
            flush=True,
        )
        if not arguments.no_browser:
            mode = open_studio(server.session_url, browser=arguments.browser)
            print(f"Opened {mode} window.", flush=True)
        try:
            server.timeout = 1
            # The open editor pings periodically. A launcher-started process
            # exits after the tab closes instead of becoming a permanent daemon.
            while time.monotonic() - server.last_seen < 900:
                server.handle_request()
        except KeyboardInterrupt:
            pass
