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
    PRESET_SCHEMA,
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


def preview_document(effect, name="balanced", connection=None):
    payload = {
        "schema": PRESET_SCHEMA,
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
                ),
                "text/html",
            )

        def do_POST(self):
            if self.path != "/save" or not valid_save_request(
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
