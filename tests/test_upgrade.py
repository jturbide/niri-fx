"""Keep installed-wheel acceptance isolated and tied to the official old asset."""

import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("upgrade", ROOT / "scripts/test-upgrade.py")
upgrade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upgrade)


class UpgradeBoundaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_official_checksum_rejects_replaced_or_renamed_wheel_and_duplicate_entries(self):
        wheel = self.root / "niri_fx-0.17.0-py3-none-any.whl"
        wheel.write_bytes(b"release wheel")
        checksum = self.root / "SHA256SUMS"
        line = hashlib.sha256(wheel.read_bytes()).hexdigest() + "  " + wheel.name + "\n"
        checksum.write_text(line)
        upgrade.verify_checksum(wheel, checksum)
        wheel.write_bytes(b"local replacement")
        with self.assertRaisesRegex(ValueError, "does not match"):
            upgrade.verify_checksum(wheel, checksum)
        checksum.write_text(line + line)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            upgrade.verify_checksum(wheel, checksum)
        checksum.write_text(line.replace(wheel.name, "another-wheel.whl"))
        with self.assertRaisesRegex(ValueError, "does not match"):
            upgrade.verify_checksum(wheel, checksum)

    def test_metadata_is_read_from_exactly_one_nirifx_distribution(self):
        for names in (("niri-fx",), ("different-package",), ("niri-fx", "other-package")):
            wheel = self.root / "fixture.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                for index, name in enumerate(names):
                    archive.writestr(
                        f"package{index}.dist-info/METADATA", f"Name: {name}\nVersion: 0.17.0\n"
                    )
            with self.subTest(names=names):
                if names == ("niri-fx",):
                    self.assertEqual(upgrade.wheel_version(wheel), "0.17.0")
                else:
                    with self.assertRaises(ValueError):
                        upgrade.wheel_version(wheel)

    def test_source_profile_requires_historical_schema_and_independent_swap(self):
        default = {
            "kind": "profile",
            "schema": 2,
            "actions": {"open": {}, "close": {}, "resize": None, "movement": None},
        }
        upgrade.verify_source_profile(default, "0.20.0")
        independent = dict(
            default, schema=3, actions=dict(default["actions"], swap={"kind": "glide"})
        )
        upgrade.verify_source_profile(independent, "0.20.0", swap=True)
        for document, swap in (
            (dict(default, schema=4), False),
            (dict(default, schema=True), False),
            (dict(default, fragment_motion={}), False),
            (dict(default, actions=dict(default["actions"], swap=None)), False),
            (dict(independent, schema=2), True),
            (dict(independent, actions=dict(independent["actions"], swap=None)), True),
        ):
            with self.subTest(document=document, swap=swap), self.assertRaises(AssertionError):
                upgrade.verify_source_profile(document, "0.20.0", swap=swap)
        with self.assertRaisesRegex(AssertionError, "does not support"):
            upgrade.verify_source_profile(independent, "0.19.0", swap=True)
        for version in ("0.17.0", "0.18.0"):
            upgrade.verify_source_profile(dict(default, schema=1), version)

    def test_disposable_installation_cannot_inherit_desktop_or_checkout_handles(self):
        handles = {
            key: "inherited-handle"
            for key in (
                "NIRI_SOCKET",
                "WAYLAND_DISPLAY",
                "DISPLAY",
                "DBUS_SESSION_BUS_ADDRESS",
                "XDG_RUNTIME_DIR",
                "PYTHONPATH",
                "PYTHONHOME",
                "VIRTUAL_ENV",
            )
        }
        with patch.dict(upgrade.os.environ, handles):
            environment = upgrade.isolated_environment(self.root)
        self.assertTrue(handles.keys().isdisjoint(environment))
        for key in ("HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
            self.assertTrue(Path(environment[key]).is_relative_to(self.root))
        self.assertEqual(environment["PYTHONNOUSERSITE"], "1")

    def test_preservation_oracle_detects_added_deleted_and_changed_state(self):
        original = self.root / "profile.json"
        original.write_text("original")
        baseline = upgrade.snapshot_files(self.root)
        added = self.root / "unexpected-migration.json"
        added.write_text("new")
        self.assertNotEqual(upgrade.snapshot_files(self.root), baseline)
        added.unlink()
        original.write_text("rewritten")
        self.assertNotEqual(upgrade.snapshot_files(self.root), baseline)
        original.unlink()
        self.assertNotEqual(upgrade.snapshot_files(self.root), baseline)

    def test_native_rejection_cannot_pass_on_success_or_an_unrelated_error(self):
        session = upgrade.Session("http://127.0.0.1:1234/?token=synthetic-test-token")
        for status, message in (
            (400, "verified running pointer"),
            (403, "denied"),
            (400, "invalid JSON"),
        ):
            error = HTTPError(
                "http://127.0.0.1:1234/review",
                status,
                "failed",
                {},
                io.BytesIO(json.dumps({"error": message}).encode()),
            )
            with (
                self.subTest(status=status, message=message),
                patch.object(session, "post", side_effect=error),
            ):
                if status == 400 and message == "verified running pointer":
                    session.rejected("/review", {}, "verified running pointer")
                else:
                    with self.assertRaises(AssertionError):
                        session.rejected("/review", {}, "verified running pointer")
        with patch.object(session, "post", return_value={"ok": True}):
            with self.assertRaisesRegex(AssertionError, "accepted"):
                session.rejected("/review", {}, "verified running pointer")


if __name__ == "__main__":
    unittest.main()
