"""Local effect editor. Only validated named presets can be saved to iNiR."""

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, HTTPServer
from importlib.resources import files
import json
import secrets
import subprocess
import time
from urllib.parse import parse_qs, urlsplit
import webbrowser

from .effects import GRAVITIES, ROTATIONS, describe_presets, shader_templates
from .integration import make_custom_preset, read_shell_presets, update_registry


def preview_document(effect, name="balanced", connection=None):
    payload = {"parameters": asdict(effect), "name": name, "presets": describe_presets(),
               "templates": shader_templates(), "gravities": GRAVITIES, "rotations": ROTATIONS,
               "connection": connection}
    data = json.dumps(payload).replace("</", "<\\/")
    return files("niri_fragments").joinpath("preview.html").read_text().replace("@EFFECT_JSON@", data)


def valid_save_request(headers, origin, token):
    return (headers.get("Host") == urlsplit(origin).netloc
            and headers.get("Origin") == origin
            and headers.get("Content-Type", "").split(";")[0].strip() == "application/json"
            and secrets.compare_digest(headers.get("X-Fragments-Token", "").encode(), token.encode()))


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
            if (self.headers.get("Host") != urlsplit(self.server.origin).netloc
                    or request.path not in ("/", "/ping") or not secrets.compare_digest(supplied.encode(), token.encode())):
                self.respond(403, {"error": "Open the editor using its local session URL."})
                return
            self.server.last_seen = time.monotonic()
            if request.path == "/ping":
                self.respond(200, {"ok": True})
                return
            self.respond(200, preview_document(effect, arguments.preset,
                         {"origin": self.server.origin, "token": token}), "text/html")

        def do_POST(self):
            if self.path != "/save" or not valid_save_request(self.headers, self.server.origin, token):
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
                self.respond(200, {"id": preset["id"], "name": preset["name"],
                                  "changed": result["changed"], "backup": result["backup"]})
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
        print(f"Niri Fragments Studio: {server.session_url}", flush=True)
        print("Save adds a preset to iRiS; select it there to activate. Ctrl+C stops the editor.", flush=True)
        if not arguments.no_browser:
            webbrowser.open(server.session_url)
        try:
            server.timeout = 1
            # The open editor pings periodically. A launcher-started process
            # exits after the tab closes instead of becoming a permanent daemon.
            while time.monotonic() - server.last_seen < 900:
                server.handle_request()
        except KeyboardInterrupt:
            pass
