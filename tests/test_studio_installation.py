"""Installation notices inspect retained receipts without running their Python."""

import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

from niri_fx import native_tools, native_tools_launcher, studio_installation
from niri_fx.effects import PRESETS
from niri_fx.storage import digest
from niri_fx.studio import make_server
from niri_fx.studio_installation import RuntimeIdentity, StudioInstallation


class StudioInstallationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="studio-installation-")
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.root = self.home / "native"
        self.receipts = self.root / "tools/runtimes"
        self.receipts.mkdir(parents=True)
        self.old = self.runtime("old")
        self.new = self.runtime("new")
        assets, session, _ = native_tools._assets(self.root)
        for path, data, mode in assets:
            path.write_bytes(data)
            path.chmod(mode)
        self.registered = self.home / "niri-fx.desktop"
        self.registered.write_bytes(session)
        self.selection = {
            "schema": 1,
            "phase": "active",
            "current": self.identifier(self.old),
            "previous": None,
            "bootstrap": self.identifier(self.old),
            "legacy": self.identifier(self.old),
            "cli": str(self.home / "bin/niri-fx"),
            "desktop": str(self.home / "applications/niri-fx.desktop"),
            "registered_entry": str(self.registered),
            "entry": str(self.root / "tools/niri-fx.desktop"),
            "assets": {path.name: digest(data) for path, data, _ in assets},
        }
        self.select()

    def runtime(self, name, version="0.19.0", *, retain=True):
        prefix = self.home / name
        package = prefix / "lib/niri_fx"
        package.mkdir(parents=True)
        init = package / "__init__.py"
        init.write_text(f"__version__ = {version!r}\n")
        config = prefix / "pyvenv.cfg"
        config.write_text("synthetic environment\n")
        python = prefix / "bin/python"
        python.parent.mkdir()
        python.write_text("synthetic interpreter: never execute\n")
        python.chmod(0o755)
        record = {
            "schema": 1,
            "python": str(python),
            "package": str(package),
            "version": version,
            "files": {str(path): digest(path.read_bytes()) for path in (init, config)},
            "desktop": "synthetic desktop entry\n",
        }
        if retain:
            receipt = self.receipts / (self.identifier(record) + ".json")
            receipt.write_text(json.dumps(record))
            receipt.chmod(0o600)
        return record

    @staticmethod
    def identifier(record):
        return native_tools_launcher.fingerprint(record)

    @staticmethod
    def identity(record):
        return RuntimeIdentity(Path(record["python"]), Path(record["package"]), record["version"])

    def select(self, **values):
        self.selection.update(values)
        path = self.root / "tools/selection.json"
        path.write_text(json.dumps(self.selection))
        path.chmod(0o600)

    def installation(self, record=None):
        with patch.object(
            RuntimeIdentity, "capture", return_value=self.identity(record or self.old)
        ):
            return StudioInstallation(self.root)

    def test_current_and_same_version_changed_use_startup_receipt(self):
        installation = self.installation()
        self.assertEqual(
            installation.snapshot(), {"state": "current", "selected_version": "0.19.0"}
        )
        self.select(current=self.identifier(self.new), previous=self.identifier(self.old))
        self.assertEqual(
            installation.snapshot(), {"state": "changed", "selected_version": "0.19.0"}
        )
        with patch.object(RuntimeIdentity, "capture", side_effect=AssertionError("recaptured")):
            self.assertEqual(installation.snapshot()["state"], "changed")
        self.assertEqual(self.installation(self.new).snapshot()["state"], "current")

    def test_prepared_remains_prepared_after_registration_until_activation(self):
        self.select(phase="prepared")
        self.assertTrue(native_tools.status(self.root)["registered"])
        installation = self.installation(self.new)
        self.assertEqual(
            installation.snapshot(), {"state": "prepared", "selected_version": "0.19.0"}
        )
        self.select(phase="active", current=self.identifier(self.new))
        self.assertEqual(installation.snapshot()["state"], "current")

    def test_archived_running_receipt_stays_changed_after_multiple_updates(self):
        third = self.runtime("third", "0.20.0")
        self.select(
            current=self.identifier(third),
            previous=self.identifier(self.new),
            bootstrap=self.identifier(self.new),
            legacy=self.identifier(self.new),
        )
        installation = self.installation(self.old)
        self.assertEqual(
            installation.snapshot(), {"state": "changed", "selected_version": "0.20.0"}
        )
        (self.receipts / (self.identifier(self.old) + ".json")).unlink()
        self.assertEqual(installation.snapshot()["state"], "changed")

    def test_matching_referenced_receipt_does_not_scan_large_archive(self):
        for index in range(studio_installation._MAX_ARCHIVED_RECEIPTS + 1):
            (self.receipts / f"{index:064x}.json").write_text("{}")
        self.assertEqual(self.installation().snapshot()["state"], "current")

    def test_unresolved_archive_lookup_is_bounded(self):
        other = self.runtime("unregistered", retain=False)
        for index in range(studio_installation._MAX_ARCHIVED_RECEIPTS):
            (self.receipts / f"{index:064x}.json").write_text("{}")
        self.assertEqual(
            self.installation(other).snapshot(), {"state": "unavailable", "selected_version": None}
        )

    def test_unmanaged_source_does_not_read_unrelated_installed_tools(self):
        source = RuntimeIdentity(
            self.home / "system/bin/python", self.home / "checkout/niri_fx", "0.19.0"
        )
        with (
            patch.object(RuntimeIdentity, "capture", return_value=source),
            patch.object(
                native_tools, "status", side_effect=AssertionError("unrelated installation")
            ),
        ):
            self.assertEqual(
                StudioInstallation(self.root).snapshot(),
                {"state": "unmanaged", "selected_version": None},
            )

    def test_unregistered_venv_and_absent_installation_are_unmanaged(self):
        other = self.runtime("unregistered", retain=False)
        self.assertEqual(self.installation(other).snapshot()["state"], "unmanaged")
        with patch.object(RuntimeIdentity, "capture", return_value=self.identity(self.old)):
            self.assertEqual(
                StudioInstallation(self.home / "absent").snapshot()["state"], "unmanaged"
            )

    def test_running_unregistered_venv_notices_later_preparation_and_activation(self):
        record = self.runtime("later-adopted", retain=False)
        installation = self.installation(record)
        self.assertEqual(installation.snapshot()["state"], "unmanaged")
        receipt = self.receipts / (self.identifier(record) + ".json")
        receipt.write_text(json.dumps(record))
        receipt.chmod(0o600)
        self.select(phase="prepared")
        with patch.object(RuntimeIdentity, "capture", side_effect=AssertionError("recaptured")):
            self.assertEqual(installation.snapshot()["state"], "prepared")
            self.select(phase="active", current=self.identifier(record))
            self.assertEqual(installation.snapshot()["state"], "current")
            (self.root / "tools/selection.json").unlink()
            self.assertEqual(installation.snapshot()["state"], "unavailable")

    def test_running_venv_notices_first_installation_after_studio_start(self):
        tools = self.root / "tools"
        saved = self.home / "saved-tools"
        tools.rename(saved)
        installation = self.installation()
        self.assertEqual(installation.snapshot()["state"], "unmanaged")
        saved.rename(tools)
        self.select(phase="prepared")
        self.assertEqual(installation.snapshot()["state"], "prepared")
        self.select(phase="active")
        self.assertEqual(installation.snapshot()["state"], "current")

    def test_current_health_ignores_damaged_unused_previous_runtime(self):
        self.select(current=self.identifier(self.new), previous=self.identifier(self.old))
        Path(self.old["package"]).joinpath("__init__.py").write_text("changed unused runtime\n")
        self.assertEqual(self.installation(self.new).snapshot()["state"], "current")

    def test_damaged_recognized_running_runtime_is_not_unmanaged(self):
        self.select(current=self.identifier(self.new), previous=self.identifier(self.old))
        Path(self.old["package"]).joinpath("__init__.py").write_text("changed running runtime\n")
        self.assertEqual(
            self.installation(self.old).snapshot(),
            {"state": "unavailable", "selected_version": None},
        )

    def test_invalid_current_metadata_is_unavailable_without_detail(self):
        installation = self.installation()
        Path(self.old["package"]).joinpath("__init__.py").write_text("changed selected runtime\n")
        self.assertEqual(
            installation.snapshot(), {"state": "unavailable", "selected_version": None}
        )
        self.select(current=self.identifier(self.new))
        self.assertEqual(installation.snapshot()["state"], "changed")
        (self.root / "tools/selection.json").unlink()
        self.assertEqual(
            installation.snapshot(), {"state": "unavailable", "selected_version": None}
        )

    def test_versions_are_bounded_plain_text_and_receipts_are_verified(self):
        for index, version in enumerate(("/private/path", "hello\nworld", "x" * 65, None)):
            with self.subTest(version=version):
                record = self.runtime(f"invalid-{index}", version)
                self.select(current=self.identifier(record))
                self.assertEqual(
                    self.installation().snapshot(),
                    {"state": "unavailable", "selected_version": None},
                )
        self.select(current=self.identifier(self.old))
        receipt = self.receipts / (self.identifier(self.old) + ".json")
        receipt.write_text(json.dumps(self.old | {"version": "forged"}))
        self.assertEqual(self.installation().snapshot()["state"], "unavailable")

    def test_identity_preserves_venv_interpreter_spelling_at_capture(self):
        python = Path(self.old["python"])
        python.unlink()
        python.symlink_to(self.new["python"])
        with (
            patch.object(studio_installation.sys, "executable", str(python)),
            patch.object(
                studio_installation,
                "__file__",
                str(Path(self.old["package"]) / "studio_installation.py"),
            ),
            patch.object(studio_installation, "__version__", "0.19.0"),
        ):
            identity = RuntimeIdentity.capture()
        self.assertEqual(identity.python, python)
        self.assertNotEqual(identity.python, python.resolve())
        self.assertEqual(identity.package, Path(self.old["package"]))

    def test_authenticated_ping_and_initial_catalog_are_scoped_read_only(self):
        config = self.home / "config.kdl"
        config.write_text("animations {}\n")
        arguments = Namespace(
            target="standalone",
            port=0,
            preset="earth",
            base="auto",
            registry=self.home / "presets.json",
            inir_root="unused",
            config=config,
        )
        with (
            patch.object(RuntimeIdentity, "capture", return_value=self.identity(self.old)),
            patch("niri_fx.native_session.default_root", return_value=self.root),
        ):
            server = make_server(arguments, PRESETS["earth"])
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        token = parse_qs(urlsplit(server.session_url).query)["token"][0]
        endpoint = server.origin + "/ping?token=" + token
        before = {str(p): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        with (
            patch("niri_fx.native_tools._probe", side_effect=AssertionError("runtime executed")),
            patch("subprocess.run", side_effect=AssertionError("process executed")),
            patch("subprocess.Popen", side_effect=AssertionError("process launched")),
            patch(
                "niri_fx.native_session.default_root", side_effect=AssertionError("root recaptured")
            ),
            patch("niri_fx.studio.pointer_capability", return_value={"status": "unknown"}),
        ):
            with urlopen(
                endpoint + "&native_root=/untrusted&runtime=/untrusted", timeout=5
            ) as response:
                self.assertEqual(
                    json.load(response),
                    {
                        "ok": True,
                        "installation": {"state": "current", "selected_version": "0.19.0"},
                    },
                )
            with urlopen(server.session_url, timeout=5) as response:
                self.assertIn(
                    '"installation": {"state": "current", "selected_version": "0.19.0"}',
                    response.read().decode(),
                )
            for request in (
                server.origin + "/ping",
                server.origin + "/ping?token=wrong",
                Request(endpoint, headers={"Host": "foreign.example"}),
            ):
                with (
                    self.subTest(request=request),
                    patch.object(
                        native_tools,
                        "status",
                        side_effect=AssertionError("unauthenticated metadata read"),
                    ),
                ):
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(request, timeout=5)
                    self.assertEqual(caught.exception.code, 403)
                    caught.exception.close()
        after = {str(p): p.read_bytes() for p in self.home.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.select(current=self.identifier(self.new))
        with patch.object(
            RuntimeIdentity, "capture", side_effect=AssertionError("identity recaptured")
        ):
            with urlopen(endpoint, timeout=5) as response:
                self.assertEqual(json.load(response)["installation"]["state"], "changed")

    def test_explicit_native_root_is_used_instead_of_desktop_default(self):
        arguments = Namespace(
            target="native",
            native_root=self.root,
            port=0,
            preset="earth",
            registry=self.home / "presets.json",
        )
        with (
            patch.object(RuntimeIdentity, "capture", return_value=self.identity(self.old)),
            patch("niri_fx.studio.Library"),
            patch(
                "niri_fx.native_session.default_root", side_effect=AssertionError("default root")
            ),
            patch("niri_fx.studio.StudioInstallation", wraps=StudioInstallation) as installation,
        ):
            server = make_server(arguments, PRESETS["earth"])
        self.addCleanup(server.server_close)
        installation.assert_called_once_with(self.root)


if __name__ == "__main__":
    unittest.main()
