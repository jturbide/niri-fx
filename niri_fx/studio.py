"""Local Library and Studio with launch-scoped targets and reviewed changes."""

import json
import os
import re
import secrets
import shutil
import subprocess
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .branding import APP_ID
from .capabilities import pointer_capability
from .catalog import STYLES
from .documents import MAX_DOCUMENT_BYTES
from .integration import make_custom_preset, read_shell_presets, update_registry
from .library import Library, studio_target
from .preview import preview_document
from .storage import atomic_write


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
    """Require the same loopback authority, browser origin and session capability.

    Loopback binding alone is insufficient: an unrelated website can send local
    requests. Host/Origin checks and the token keep writes tied to this editor.
    """
    return (
        headers.get("Host") == urlsplit(origin).netloc
        and headers.get("Origin") == origin
        and headers.get("Content-Type", "").split(";")[0].strip() == "application/json"
        and secrets.compare_digest(headers.get("X-NiriFX-Token", "").encode(), token.encode())
    )


def make_server(arguments, effect):
    """Create an on-demand editor server; the caller controls its lifetime.

    GET serves self-contained previews. POST accepts bounded parameter documents
    or favorites, never paths, commands or raw shader source supplied by clients.
    Launch arguments fix the configuration owner. Reviewed activation delegates
    to the shared Library backend.
    """
    token = secrets.token_urlsafe(32)
    target = studio_target(arguments)
    preferences_path = (
        Path(getattr(arguments, "state", Path(arguments.registry).parent)).expanduser()
        / "studio-preferences.json"
    )
    if not hasattr(arguments, "state"):
        arguments.state = preferences_path.parent
    library = Library(arguments, target)
    native_document = getattr(arguments, "native_document", False) or bool(
        getattr(arguments, "custom", None) or getattr(arguments, "profile", None)
    )

    def connection():
        value = {
            "origin": server.origin,
            "token": token,
            "target": target,
            "view": "editor" if getattr(arguments, "edit", False) else "library",
        }
        if target == "native":
            from .capabilities import swap_capability
            from .native_customization import fragment_choices

            value["native"] = {
                "base_bundle": library.native_base["bundle_id"],
                "variant": library.native_base["variant"],
                "recipe": library.native_base.get("customization") if not native_document else None,
                "fragment_choices": fragment_choices(),
                "swap_supported": library.native_base.get("swap_supported", False)
                and swap_capability(library.native_base["binary"])["status"] == "supported",
            }
        else:
            value["pointer"] = pointer_capability(
                getattr(arguments, "movement_binary", None),
                socket_path=os.environ.get("NIRI_SOCKET"),
            ) | {
                "target_supported": target == "standalone",
                "target_detail": "Pointer Apply is available after verifying this standalone session."
                if target == "standalone"
                else "Pointer settings can be saved and exported here. Apply currently requires a verified standalone session.",
            }
        return value

    def valid_favorite(name):
        return isinstance(name, str) and (
            name in STYLES or re.fullmatch(r"custom-[a-z0-9][a-z0-9-]{0,47}", name)
        )

    def read_preferences():
        try:
            value = json.loads(preferences_path.read_text())
            return {"favorites": [name for name in value["favorites"] if valid_favorite(name)]}
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
                or request.path not in ("/", "/ping", "/library")
                or not secrets.compare_digest(supplied.encode(), token.encode())
            ):
                self.respond(403, {"error": "Open the editor using its local session URL."})
                return
            self.server.last_seen = time.monotonic()
            if request.path == "/ping":
                self.respond(200, {"ok": True})
                return
            if request.path == "/library":
                try:
                    self.respond(200, library.listing())
                except (OSError, ValueError, subprocess.SubprocessError) as error:
                    self.respond(400, {"error": str(error)})
                return
            selected, name = effect, getattr(arguments, "custom_name", arguments.preset)
            page_connection = connection()
            if target == "native" and not native_document:
                from .documents import parse_document
                from .profiles import Profile

                recipe = page_connection["native"]["recipe"]
                if recipe:
                    name, _, selected = parse_document(recipe["document"])
                else:
                    selected, name = Profile(), "NiriFX session"
            elif getattr(arguments, "active", False):
                try:
                    document = library.listing()["active"]
                    if document:
                        from .documents import parse_document

                        name, _, selected = parse_document(document)
                except (OSError, ValueError, subprocess.SubprocessError):
                    pass  # The library reports the failure; preview remains usable.
            self.respond(
                200,
                preview_document(
                    selected,
                    name,
                    page_connection,
                    read_preferences(),
                ),
                "text/html",
            )

        def do_POST(self):
            if self.path not in (
                "/save",
                "/preferences",
                "/store",
                "/profiles",
                "/review",
                "/apply",
                "/restore",
                "/rollback-review",
                "/rollback-apply",
            ) or not valid_save_request(self.headers, self.server.origin, token):
                self.respond(403, {"error": "Save request must come from this editor session."})
                return
            try:
                self.server.last_seen = time.monotonic()
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_DOCUMENT_BYTES:
                    raise ValueError(
                        f"Preset request must be between 1 and {MAX_DOCUMENT_BYTES} bytes"
                    )
                data = json.loads(self.rfile.read(length))
                if self.path in (
                    "/store",
                    "/profiles",
                    "/review",
                    "/apply",
                    "/restore",
                    "/rollback-review",
                    "/rollback-apply",
                ):
                    if self.path == "/restore" and data != {}:
                        raise ValueError("Restore accepts no client-selected paths or transaction")
                    action = {
                        "/store": library.store,
                        "/profiles": library.manage,
                        "/review": library.review,
                        "/apply": library.apply,
                        "/restore": lambda _: library.undo(),
                        "/rollback-review": library.rollback_review,
                        "/rollback-apply": library.rollback_apply,
                    }[self.path]
                    self.respond(200, action(data))
                    return
                if self.path == "/preferences":
                    if (
                        not isinstance(data, dict)
                        or set(data) != {"favorites"}
                        or not isinstance(data["favorites"], list)
                        or len(data["favorites"]) > len(STYLES) + 100
                        or any(not valid_favorite(name) for name in data["favorites"])
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
                if target == "native":
                    raise ValueError(
                        "Use Save to My profiles or Select for next login for managed sessions"
                    )
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
    server.save_target = target
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
            "Choose effects for each action, preview, then review and apply. A verified matching NiriFX session supports live Apply; otherwise choices are saved for the next login. Ctrl+C stops the app."
            if server.save_target == "native"
            else "Choose a look in Library or customize it in Studio. Review & apply activates effects. Ctrl+C stops the app.",
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
