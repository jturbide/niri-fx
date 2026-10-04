#!/usr/bin/env python3
"""Verify pointer profiles through the real CLI, HTTP app and owned native Niri.

Only the newly created nested compositor and its temporary configuration receive
changes. The login compositor supplies an outer window; it is never replaced.
"""

import json
import os
import subprocess
import sys
import threading
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lib.movement import experiment
from lib.nested import NestedSession, wait_for

from niri_fx.capabilities import pointer_capability
from niri_fx.effects import PRESETS
from niri_fx.pointer import PRESETS as POINTER_PRESETS
from niri_fx.profiles import Profile
from niri_fx.studio import make_server


def main():
    binary, _, _ = experiment(pointer_wobble=True)
    base = (
        "hotkey-overlay { skip-at-startup; }\nanimations { window-resize { duration-ms 170; }; }\n"
    )
    with NestedSession(base, binary=binary, width=1000, height=700) as session:
        original = session.config.read_bytes()
        args = SimpleNamespace(
            config=session.config,
            state=session.root / "state/niri-fx",
            registry=session.root / "registry.json",
            inir_root=session.root / "no-shell",
            movement_binary=binary,
            target="standalone",
            base="auto",
            port=0,
            preset="balanced",
        )
        profile = Profile(
            PRESETS["balanced"],
            PRESETS["frost-vanish"],
            pointer=POINTER_PRESETS["gentle"].wobble,
        )
        checks = []

        def capabilities():
            return json.loads(session.msg("-j", "niri-fx-pointer-capabilities"))[
                "NiriFxPointerCapabilities"
            ]

        def doctor():
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "niri_fx",
                    "doctor",
                    "--config",
                    str(session.config),
                    "--inir-root",
                    str(args.inir_root),
                    "--niri-binary",
                    str(binary),
                ],
                cwd=ROOT,
                env=session.env,
                text=True,
                capture_output=True,
                timeout=30,
            )
            report = json.loads(result.stdout)
            assert result.returncode == 0 and report["healthy"], report
            assert report["pointer_capability"]["activation_ready"], report

        with patch.dict(os.environ, session.env):
            support = pointer_capability(binary, socket_path=session.env["NIRI_SOCKET"])
            assert support["activation_ready"] and not capabilities()["configured"]
            assert not pointer_capability("/usr/bin/niri", socket_path=session.env["NIRI_SOCKET"])[
                "activation_ready"
            ]
            doctor()
            checks.append("native runtime verified before pointer is configured")
            with make_server(args, profile) as server:
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                token = parse_qs(urlsplit(server.session_url).query)["token"][0]

                def post(path, data, *, status=200):
                    request = Request(
                        server.origin + path,
                        json.dumps(data).encode(),
                        {
                            "Content-Type": "application/json",
                            "Origin": server.origin,
                            "X-NiriFX-Token": token,
                        },
                        method="POST",
                    )
                    try:
                        with urlopen(request, timeout=30) as response:
                            assert status == response.status
                            return json.load(response)
                    except HTTPError as error:
                        if error.code != status:
                            raise RuntimeError(error.read().decode()) from error
                        return json.load(error)

                try:
                    with urlopen(server.session_url, timeout=30) as response:
                        html = response.read().decode()
                        assert '"activation_ready": true' in html
                        assert '"target_supported": true' in html
                    for case, selected, move in (
                        ("pointer-only", profile, False),
                        (
                            "pointer-and-movement",
                            replace(profile, movement=PRESETS["momentum-glide"]),
                            True,
                        ),
                        (
                            "pointer-disabled",
                            replace(profile, pointer=replace(profile.pointer, strength=0)),
                            False,
                        ),
                    ):
                        selection = {
                            "document": selected.document(case),
                            "allow_resize": False,
                            "allow_movement": move,
                            "allow_pointer": True,
                        }
                        reviewed = post("/review", selection)
                        assert session.config.read_bytes() == original
                        request = {"selection": selection, "expected": reviewed["plan_sha256"]}
                        with patch.dict(os.environ, {"NIRI_SOCKET": ""}):
                            refused = post("/apply", request, status=400)
                            assert "verified running" in refused["error"]
                        assert session.config.read_bytes() == original
                        applied = post("/apply", request)
                        assert applied["changed"]
                        wait_for(lambda: capabilities()["configured"], "pointer config reload")
                        assert capabilities()["enabled"] is (selected.pointer.strength > 0)
                        exported = (session.config.parent / "nirifx/animations.kdl").read_text()
                        assert exported.count("window-movement {") == 1
                        assert "window-resize" not in exported
                        assert (
                            "custom-shader" in exported.split("window-movement {", 1)[1]
                        ) is move
                        doctor()
                        post("/restore", {})
                        wait_for(lambda: not capabilities()["configured"], "pointer restore reload")
                        assert session.config.read_bytes() == original
                        assert not (session.config.parent / "nirifx/animations.kdl").exists()
                        checks.append(
                            case
                            + ": HTTP review, capability loss refusal, apply, reload and exact restore"
                        )
                    # Undoing a stock selection can reactivate a previous native
                    # profile. It needs the same runtime proof as ordinary Apply.
                    include = session.config.parent / "nirifx/animations.kdl"
                    for selected in (profile, replace(profile, pointer=None)):
                        selection = {
                            "document": selected.document("restore-native"),
                            "allow_resize": False,
                            "allow_movement": False,
                            "allow_pointer": selected.pointer is not None,
                        }
                        reviewed = post("/review", selection)
                        post(
                            "/apply", {"selection": selection, "expected": reviewed["plan_sha256"]}
                        )
                        wait_for(
                            lambda enabled=selected.pointer is not None: (
                                capabilities()["configured"] is enabled
                            ),
                            "stacked profile reload",
                        )
                    stock_bytes = include.read_bytes()
                    with patch.dict(os.environ, {"NIRI_SOCKET": ""}):
                        refused = post("/restore", {}, status=400)
                        assert "reactivate experimental pointer" in refused["error"]
                    assert include.read_bytes() == stock_bytes
                    post("/restore", {})
                    wait_for(lambda: capabilities()["configured"], "native snapshot restored")
                    post("/restore", {})
                    wait_for(lambda: not capabilities()["configured"], "stock baseline restored")
                    assert session.config.read_bytes() == original and not include.exists()
                    checks.append(
                        "native snapshot Restore requires current runtime support; stock fallback remains available"
                    )
                finally:
                    server.shutdown()
                    thread.join(timeout=5)
                    assert not thread.is_alive()
            session.check_render_log()
        (session.root / "integration-checks.json").write_text(
            json.dumps({"checks": checks}, indent=2) + "\n"
        )
        print(f"PASS: native pointer profile and HTTP integration. Evidence: {session.root}")


if __name__ == "__main__":
    main()
