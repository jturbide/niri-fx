"""Session setup uses launch-owned paths, installed tools and a single reviewed transaction."""

import json
import os
import shutil
import sys
import tempfile
import unittest
import venv
from argparse import Namespace
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

import test_native_package

from niri_fx import native_package, native_session, setup, studio_session
from niri_fx.effects import PRESETS
from niri_fx.storage import digest
from niri_fx.studio import make_server
from niri_fx.studio_session import StudioSession

inspect_installed = studio_session._installed
run_installed = studio_session._command


class StudioSessionTests(unittest.TestCase):
    def setUp(self):
        fixture = test_native_package.NativePackageTests(methodName="runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.config = fixture.fixture.fixture.config
        self.root = fixture.root
        self.session = StudioSession(self.root, self.config)
        for setting in (
            patch.object(studio_session, "PACKAGE_CANDIDATE", fixture.fixture.candidate),
            patch.object(native_package, "REGISTERED_ENTRY", fixture.registered),
            patch.object(studio_session, "_installed", side_effect=self.installed),
            patch.object(studio_session, "_command", side_effect=self.command),
        ):
            setting.start()
            self.addCleanup(setting.stop)
        self.commands = []

    def installed(self):
        manifest = json.loads((self.fixture.fixture.candidate / "manifest.json").read_text())
        files, _ = native_package._source_files(self.fixture.source)
        return {
            "version": native_package.__version__,
            "build_id": manifest["native_build"]["build_id"],
            "binary_sha256": manifest["binary_sha256"],
            "files": {name: digest(data) for name, data in files.items()},
        }

    def command(self, arguments):
        self.commands.append(arguments)
        config = arguments[arguments.index("--config") + 1] if "--config" in arguments else None
        plan = native_package.adopt_plan(
            self.root,
            self.fixture.fixture.candidate,
            config,
            registered_entry=self.fixture.registered,
        )
        if "--apply" in arguments:
            return native_package.apply_adoption(
                plan, self.root, arguments[arguments.index("--expect-plan") + 1]
            ) | {"dry_run": False}
        return setup.summarize(plan) | {"dry_run": True}

    def adopt(self):
        review = self.session.review({})
        return self.session.apply({"expected": review["plan_sha256"]})

    def test_fresh_setup_reviews_and_copies_only_the_launch_config(self):
        original = self.config.read_bytes()
        with patch("subprocess.Popen", side_effect=AssertionError("status executed a program")):
            status = self.session.status({})
        self.assertEqual(status["state"], "ready")
        self.assertEqual(status["action"], "setup")
        self.assertEqual(status["config"]["path"], str(self.config))
        self.assertEqual(status["config"]["mode"], "copy")
        self.assertEqual(status["running"]["status"], "offline")
        review = self.session.review({})
        self.assertFalse(self.root.exists())
        self.assertEqual(review["intent"], "setup")
        self.assertIn(str(self.config), self.commands[-1])
        result = self.session.apply({"expected": review["plan_sha256"]})
        self.assertEqual(result["activation"], "next-login")
        self.assertTrue(result["reopen_required"])
        self.assertEqual(result["session"]["state"], "current")
        self.assertEqual(self.config.read_bytes(), original)

    def test_updates_preserve_recipe_and_detect_same_version_source_changes(self):
        self.adopt()
        selected = native_session.load_selection(self.root)["selected"]
        old = self.fixture.configure_recipe(selected)
        original = Path(old["config"]).read_bytes()
        self.fixture.upgrade_candidate()
        source = self.fixture.source / "__init__.py"
        source.write_bytes(source.read_bytes() + b"# same version package rebuild\n")
        status = self.session.status({})
        self.assertEqual(status["state"], "update")
        self.assertEqual(status["config"]["mode"], "preserve")
        review = self.session.review({})
        self.assertEqual(review["intent"], "update")
        self.assertNotIn("--config", self.commands[-1])
        result = self.session.apply({"expected": review["plan_sha256"]})
        self.assertEqual(result["session"]["state"], "current")
        new = native_session.inspect_bundle(self.root, result["session"]["next_login"]["bundle_id"])
        self.assertEqual(Path(new["config"]).read_bytes(), original)
        self.assertEqual(new["customization"]["document"], old["customization"]["document"])

    def test_same_version_tools_only_or_compositor_only_change_is_an_update(self):
        self.adopt()
        with patch.object(
            studio_session,
            "_installed",
            return_value=self.installed()
            | {
                "files": self.installed()["files"] | {"new.py": "0" * 64},
            },
        ):
            self.assertEqual(self.session.snapshot()["state"], "update")
        with patch.object(
            studio_session,
            "_installed",
            return_value=self.installed()
            | {
                "binary_sha256": "0" * 64,
            },
        ):
            self.assertEqual(self.session.snapshot()["state"], "update")

    def test_missing_package_keeps_retained_and_running_status(self):
        self.adopt()
        with patch.object(studio_session, "_installed", return_value=None):
            status = self.session.snapshot()
            self.assertEqual(status["state"], "missing")
            self.assertIsNotNone(status["next_login"])
            self.assertEqual(status["running"]["status"], "offline")
            with self.assertRaisesRegex(ValueError, "Install the complete"):
                self.session.review({})

    def test_shared_update_preserves_recipe_and_both_config_projections(self):
        _, old, _ = self.fixture.prepare_second_adoption(shared=True)
        paths = [
            Path(old["shared"][key]) for key in ("source_config", "native_include", "stock_include")
        ]
        before = {path: path.read_bytes() for path in paths}
        review = self.session.review({})
        self.assertNotIn("--config", self.commands[-1])
        result = self.session.apply({"expected": review["plan_sha256"]})
        new = native_session.inspect_bundle(self.root, result["session"]["next_login"]["bundle_id"])
        self.assertTrue(result["session"]["next_login"]["shared"])
        self.assertEqual(new["shared"]["document"], old["shared"]["document"])
        self.assertEqual({path: path.read_bytes() for path in paths}, before)

    def test_installed_metadata_inspection_reads_only_and_refuses_incomplete_candidates(self):
        # These fixtures are deliberately user-owned. The production ownership
        # guard has its own refusal test; no test creates files under /usr.
        with (
            patch.object(studio_session, "_system_package", return_value=self.fixture.source),
            patch.object(studio_session, "_trusted") as trusted,
            patch("subprocess.Popen", side_effect=AssertionError("metadata executed a program")),
        ):
            self.assertEqual(inspect_installed(), self.installed())
            self.assertGreater(trusted.call_count, 50)
            path = self.fixture.fixture.candidate / "manifest.json"
            original = path.read_text()
            manifest = json.loads(original)
            for build in (None, {}, {"inputs": None}, {"inputs": {"variant": "movement"}}):
                path.write_text(json.dumps(manifest | {"native_build": build}))
                with self.subTest(build=build), self.assertRaisesRegex(ValueError, "no complete"):
                    inspect_installed()
            path.write_text(original)
            binary = self.fixture.fixture.fixture.binary
            before = binary.read_bytes()
            binary.write_bytes(before + b"corrupt candidate\n")
            with self.assertRaisesRegex(ValueError, "contents changed"):
                inspect_installed()
            binary.write_bytes(before)
            self.fixture.source.joinpath("__init__.py").write_text(
                "__version__ = '/private/path'\n"
            )
            with self.assertRaisesRegex(ValueError, "version is unavailable"):
                inspect_installed()

    def test_isolated_child_adopts_installed_version_instead_of_running_studio_version(self):
        prefix = self.fixture.directory / "installed-tools"
        venv.EnvBuilder(with_pip=False).create(prefix)
        package = (
            prefix
            / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages/niri_fx"
        )
        shutil.copytree(self.fixture.source, package)
        self.fixture.source = package
        package.joinpath("__init__.py").write_text('__version__ = "0.88.0"\n')
        # The subprocess imports the actual installed CLI. Only its trusted
        # dispatcher path is relocated into this temporary package fixture.
        package.joinpath("__main__.py").write_text(
            "from pathlib import Path\nfrom niri_fx import native_package\n"
            f"native_package.SESSION_LAUNCHER = Path({str(self.fixture.launcher)!r})\n"
            "from niri_fx.cli import main\nraise SystemExit(main())\n"
        )
        native = self.fixture.fixture.fixture
        native.binary.write_text('#!/bin/sh\n[ "$1" = validate ] && [ "$2" = -c ]\n')
        native.record["binary_sha256"] = digest(native.binary.read_bytes())
        native.save_record()
        installed = self.installed() | {"version": "0.88.0"}
        original = self.config.read_bytes()
        with (
            patch.object(studio_session, "SYSTEM_PYTHON", prefix / "bin/python3"),
            patch.object(studio_session, "_command", side_effect=run_installed),
            patch.object(studio_session, "_installed", return_value=installed),
        ):
            review = self.session.review({})
            self.assertEqual(review["selection"]["tools_version"], "0.88.0")
            self.assertFalse(self.root.exists())
            result = self.session.apply({"expected": review["plan_sha256"]})
        self.assertEqual(result["session"]["state"], "current")
        self.assertEqual(result["session"]["next_login"]["tools_version"], "0.88.0")
        self.assertEqual(self.config.read_bytes(), original)

    def test_cancel_is_read_only_and_consumes_review(self):
        review = self.session.review({})
        token = {"expected": review["plan_sha256"]}
        self.assertEqual(self.session.cancel(token), {"cancelled": True})
        self.assertFalse(self.root.exists())
        with self.assertRaisesRegex(ValueError, "cancelled or stale"):
            self.session.apply(token)
        self.assertEqual(len(self.commands), 1)

    def test_changed_config_refuses_apply_and_requires_another_review(self):
        review = self.session.review({})
        token = {"expected": review["plan_sha256"]}
        self.config.write_bytes(self.config.read_bytes() + b"// changed after review\n")
        with self.assertRaisesRegex(ValueError, "unchanged reviewed plan"):
            self.session.apply(token)
        self.assertFalse(self.root.exists())
        with self.assertRaisesRegex(ValueError, "missing, cancelled or stale"):
            self.session.apply(token)

    def test_failed_review_invalidates_previous_review(self):
        old = self.session.review({})
        with patch.object(studio_session, "_command", side_effect=ValueError("package changed")):
            with self.assertRaisesRegex(ValueError, "package changed"):
                self.session.review({})
        with self.assertRaisesRegex(ValueError, "missing, cancelled or stale"):
            self.session.apply({"expected": old["plan_sha256"]})

    def test_unreadable_reply_after_real_apply_requires_reopen_and_status_check(self):
        review = self.session.review({})

        def interrupted_response(arguments):
            self.command(arguments)
            raise ValueError("unreadable reply after writes")

        with patch.object(studio_session, "_command", side_effect=interrupted_response):
            with self.assertRaisesRegex(ValueError, "unreadable reply"):
                self.session.apply({"expected": review["plan_sha256"]})
        status = self.session.status({})
        self.assertEqual(status["state"], "current")
        self.assertTrue(status["reopen_required"])
        self.assertTrue(status["apply_uncertain"])
        self.assertIsNone(self.session.pending)

    def test_refusal_before_starting_apply_does_not_require_reopen(self):
        review = self.session.review({})
        with patch.object(studio_session, "_installed", side_effect=ValueError("package removed")):
            with self.assertRaisesRegex(ValueError, "package removed"):
                self.session.apply({"expected": review["plan_sha256"]})
        self.assertFalse(self.session.reopen_required)
        self.assertFalse(self.root.exists())

    def test_browser_paths_commands_and_custom_root_are_rejected(self):
        for method in (self.session.status, self.session.review):
            for value in ([], {"config": "/foreign"}, {"candidate": "/foreign"}, {"apply": True}):
                with self.subTest(method=method, value=value), self.assertRaises(ValueError):
                    method(value)
        review = self.session.review({})
        for value in (
            {},
            {"expected": "wrong"},
            {"expected": review["plan_sha256"], "root": "/foreign"},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.session.apply(value)
        foreign = StudioSession(self.root / "foreign", self.config)
        self.assertEqual(foreign.snapshot()["state"], "blocked")
        with self.assertRaisesRegex(ValueError, "default XDG"):
            foreign.review({})
        self.assertFalse(self.root.exists())


class SessionServerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="studio-session-http-")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        config = self.directory / "config.kdl"
        config.write_text("animations {}\n")
        arguments = Namespace(
            target="standalone",
            port=0,
            preset="earth",
            base="auto",
            config=config,
            registry=self.directory / "registry.json",
            inir_root="unused",
        )
        session_patch = patch("niri_fx.studio.StudioSession")
        self.session = session_patch.start().return_value
        self.addCleanup(session_patch.stop)
        self.session.snapshot.return_value = {"state": "missing"}
        self.session.status.return_value = {"state": "missing"}
        self.session.review.return_value = {"plan_sha256": "a" * 64}
        self.session.apply.return_value = {"changed": True, "reopen_required": True}
        self.session.cancel.return_value = {"cancelled": True}
        self.session.reopen_required = False
        self.server = make_server(arguments, PRESETS["earth"])
        thread = Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.token = parse_qs(urlsplit(self.server.session_url).query)["token"][0]

    def post(self, route, data, **headers):
        request = Request(
            self.server.origin + route,
            json.dumps(data).encode(),
            {
                "Content-Type": "application/json",
                "Origin": self.server.origin,
                "X-NiriFX-Token": self.token,
            }
            | headers,
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_session_routes_share_csrf_guards_and_cancel_has_no_apply(self):
        for route in ("/session-status", "/session-review", "/session-apply", "/session-cancel"):
            with self.subTest(route=route), self.assertRaises(HTTPError) as error:
                self.post(route, {}, Origin="https://foreign.example")
            self.assertEqual(error.exception.code, 403)
            error.exception.close()
        self.session.status.assert_not_called()
        self.session.review.assert_not_called()
        self.session.apply.assert_not_called()
        self.assertEqual(self.post("/session-review", {}), {"plan_sha256": "a" * 64})
        self.assertEqual(self.post("/session-cancel", {"expected": "a" * 64}), {"cancelled": True})
        self.session.apply.assert_not_called()

    def test_adoption_blocks_old_desktop_reviews_and_mutations_but_allows_draft_storage(self):
        self.post("/session-apply", {"expected": "a" * 64})
        self.assertTrue(self.post("/session-status", {})["reopen_required"])
        for route in (
            "/review",
            "/apply",
            "/restore",
            "/rollback-review",
            "/rollback-apply",
            "/shared-review",
            "/shared-apply",
            "/recovery-review",
            "/recovery-apply",
            "/session-review",
            "/session-apply",
            "/save",
        ):
            with self.subTest(route=route), self.assertRaises(HTTPError) as error:
                self.post(route, {})
            self.assertEqual(error.exception.code, 400)
            self.assertIn("reopen Studio", error.exception.read().decode())
            error.exception.close()
        with patch("niri_fx.library.Library.store", return_value={"saved": True}) as store:
            self.assertEqual(self.post("/store", {"document": {}}), {"saved": True})
            store.assert_called_once()

    def test_uncertain_apply_response_fences_other_desktop_writers(self):
        def uncertain(_):
            self.session.reopen_required = True
            raise ValueError("The package response could not be read")

        self.session.apply.side_effect = uncertain
        with self.assertRaises(HTTPError) as error:
            self.post("/session-apply", {"expected": "a" * 64})
        response = json.loads(error.exception.read())
        error.exception.close()
        self.assertTrue(response["reopen_required"])
        self.assertTrue(response["apply_uncertain"])
        self.assertTrue(self.post("/session-status", {})["reopen_required"])
        with self.assertRaises(HTTPError) as error:
            self.post("/apply", {})
        self.assertIn("reopen Studio", error.exception.read().decode())
        error.exception.close()


class InstalledToolCommandTests(unittest.TestCase):
    def test_untrusted_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "package"
            path.write_text("not a trusted package")
            with self.assertRaisesRegex(ValueError, "untrusted or writable"):
                studio_session._trusted(path)

    def test_command_is_fixed_isolated_and_strips_desktop_and_python_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "python3"
            script.write_text(
                "#!" + sys.executable + "\nimport json, os, sys\n"
                "print(json.dumps({'argv':sys.argv[1:], 'cwd':os.getcwd(), 'env':dict(os.environ)}))\n"
            )
            script.chmod(0o755)
            with (
                patch.object(studio_session, "SYSTEM_PYTHON", script),
                patch.dict(
                    os.environ,
                    {
                        "PYTHONPATH": "/foreign",
                        "PYTHONHOME": "/foreign",
                        "NIRI_SOCKET": "/foreign",
                        "WAYLAND_DISPLAY": "foreign",
                        "DISPLAY": ":100",
                        "DBUS_SESSION_BUS_ADDRESS": "foreign",
                        "XDG_DATA_HOME": directory,
                    },
                ),
            ):
                result = studio_session._command(["--root", directory])
            self.assertEqual(
                result["argv"],
                ["-I", "-B", "-m", "niri_fx", "native", "adopt", "--root", directory],
            )
            self.assertEqual(result["cwd"], "/")
            self.assertEqual(result["env"]["XDG_DATA_HOME"], directory)
            for name in (
                "PYTHONPATH",
                "PYTHONHOME",
                "NIRI_SOCKET",
                "WAYLAND_DISPLAY",
                "DISPLAY",
                "DBUS_SESSION_BUS_ADDRESS",
            ):
                self.assertNotIn(name, result["env"])

    def test_command_output_and_duration_are_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            script = Path(directory) / "python3"
            for code, changes, message in (
                ("print('x' * 10000)", {"MAX_OUTPUT_BYTES": 1024}, "too much output"),
                ("import time; time.sleep(5)", {"COMMAND_TIMEOUT": 0.05}, "timed out"),
                ("print('not-json')", {"MAX_OUTPUT_BYTES": 1024}, "unreadable response"),
            ):
                script.write_text("#!" + sys.executable + "\n" + code + "\n")
                script.chmod(0o755)
                with (
                    self.subTest(message=message),
                    patch.object(studio_session, "SYSTEM_PYTHON", script),
                    patch.multiple(studio_session, **changes),
                    self.assertRaisesRegex(ValueError, message),
                ):
                    studio_session._command([])


if __name__ == "__main__":
    unittest.main()
