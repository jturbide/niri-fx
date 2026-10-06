"""Session archive audit rejects unsafe ownership, partial stacks and stale pairs."""

import importlib.util
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "arch_session_check", ROOT / "scripts/check-arch-session-package.py"
)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
native = check.native_build
VERSION = "0.21.0.r75.g1234567-1"


class ArchSessionPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="session package tests ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.payload = self.root / "payload"
        self.site = self.root / "site"
        (self.site / "niri_fx").mkdir(parents=True)
        for name in check.PAYLOAD | check.METADATA:
            path = self.payload / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic package fixture\n" * 8)
        self.candidate = self.payload / check.PREFIX
        (self.payload / check.DESKTOP).write_bytes(check.DESKTOP_ENTRY)
        dispatcher = (ROOT / "niri_fx/package_session.py").read_bytes()
        (self.payload / check.DISPATCHER).write_bytes(dispatcher)
        (self.payload / check.DISPATCHER).chmod(0o755)
        (self.site / "niri_fx/package_session.py").write_bytes(dispatcher)
        for name in native.STACKS["fragment"]:
            shutil.copyfile(ROOT / "experimental" / name, self.candidate / "patches" / name)
        binary = self.candidate / "bin/niri"
        binary.write_bytes(b"\x7fELF\x02\x01" + b"\0" * 12 + b"\x3e\0" + b"synthetic fixture")
        binary.chmod(0o755)
        rustc = "rustc 1.99.0 (fixture 2026-01-01)"
        self.manifest = {
            "revision": native.REVISION,
            "binary": "bin/niri",
            "source": "source",
            "binary_sha256": native.digest(binary),
            "rustc": rustc,
            "build_profile": "release",
            "build_flags": ["--locked"],
            **{
                native.PATCH_FIELDS[name]: native.digest(self.candidate / "patches" / name)
                for name in native.STACKS["fragment"]
            },
        }
        self.manifest["native_build"] = native.metadata(
            self.manifest,
            variant="fragment",
            lock_sha256=native.digest(self.candidate / "source/Cargo.lock"),
            target="x86_64-unknown-linux-gnu",
            features=["default", *native.DESKTOP_FEATURES],
            rustc_verbose=f"{rustc}\nhost: x86_64-unknown-linux-gnu",
        )
        self.write_manifest()
        self.pkginfo = (
            "pkgname = niri-fx-compositor-git\n"
            f"pkgver = {VERSION}\narch = x86_64\n"
            + "".join(
                f"depend = {name}\n"
                for name in (
                    "niri",
                    "niri-fx-git",
                    "python",
                    "bash",
                    "systemd",
                    "dbus",
                    "wayland",
                    "libglvnd",
                )
            )
        )
        (self.payload / ".PKGINFO").write_text(self.pkginfo)

    def write_manifest(self):
        (self.candidate / "manifest.json").write_text(json.dumps(self.manifest))

    def archive(self, *, extra=None, missing=None):
        output = self.root / "package.tar"
        with tarfile.open(output, "w") as archive:
            for name in sorted(check.PAYLOAD | check.METADATA):
                if name == missing:
                    continue
                path = self.payload / name
                item = tarfile.TarInfo(name)
                item.mode = path.stat().st_mode & 0o777
                item.size = path.stat().st_size
                archive.addfile(item, io.BytesIO(path.read_bytes()))
            if extra is not None:
                archive.addfile(extra, io.BytesIO(b""))
        return output

    def test_complete_payload_is_checked_without_running_any_executable(self):
        output = self.root / "extracted"
        files = check.extract_tar(self.archive(), output)
        self.assertEqual(files, check.PAYLOAD | check.METADATA)
        with patch.object(check.subprocess, "Popen", side_effect=AssertionError("must not run")):
            report, digest = check.inventory(output, self.site)
        self.assertEqual(report["status"], "metadata-match")
        self.assertEqual(digest, self.manifest["binary_sha256"])
        self.assertEqual(check.package_version(output, VERSION), VERSION)

    def test_unsafe_members_are_rejected_before_any_extraction(self):
        for name, kind in (
            ("../escape", tarfile.REGTYPE),
            ("/etc/passwd", tarfile.REGTYPE),
            ("usr/bin/niri", tarfile.REGTYPE),
            (".INSTALL", tarfile.REGTYPE),
            ("usr/lib/niri-fx/link", tarfile.SYMTYPE),
            (check.DESKTOP, tarfile.REGTYPE),
        ):
            with self.subTest(name=name, kind=kind):
                entry = tarfile.TarInfo(name)
                entry.type = kind
                entry.linkname = "/etc/passwd" if kind == tarfile.SYMTYPE else ""
                destination = self.root / "not-created"
                with self.assertRaises(ValueError):
                    check.extract_tar(self.archive(extra=entry), destination)
                self.assertFalse(destination.exists())

    def test_missing_patch_file_is_rejected_before_extraction(self):
        with self.assertRaisesRegex(ValueError, "incomplete"):
            check.extract_tar(
                self.archive(missing=f"{check.PREFIX}/patches/niri-swap.patch"),
                self.root / "missing",
            )

    def test_private_producer_modes_cannot_leak_into_system_package(self):
        entry = tarfile.TarInfo(check.PREFIX)
        entry.type = tarfile.DIRTYPE
        entry.mode = 0o700
        with self.assertRaisesRegex(ValueError, "system-readable permissions"):
            check.extract_tar(self.archive(extra=entry), self.root / "private-directory")
        (self.candidate / "manifest.json").chmod(0o600)
        with self.assertRaisesRegex(ValueError, "system-readable permissions"):
            check.extract_tar(self.archive(), self.root / "private-file")

    def test_decompression_rejects_excess_bytes_and_stalled_decoders(self):
        popen = subprocess.Popen
        for code, limit, timeout, error in (
            ("import sys; sys.stdout.buffer.write(b'x' * 8192)", 100, 5, "size limit"),
            ("import time; time.sleep(60)", 8192, 0.1, "timed out"),
        ):
            with self.subTest(error=error):
                output = self.root / error
                with (
                    patch.object(
                        check.subprocess,
                        "Popen",
                        side_effect=lambda *a, code=code, **kw: popen(
                            [sys.executable, "-c", code], **kw
                        ),
                    ),
                    self.assertRaisesRegex(ValueError, error),
                ):
                    check.decompress(self.root / "unused", output, limit=limit, timeout=timeout)
                self.assertLessEqual(output.stat().st_size, limit)

    def test_partial_stack_and_minimal_features_are_rejected(self):
        inputs = self.manifest["native_build"]["inputs"]
        inputs["patches"].pop()
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "four current"):
            check.inventory(self.payload, self.site)
        inputs["patches"].append(
            {"file": "niri-swap.patch", "sha256": self.manifest["swap_patch_sha256"]}
        )
        inputs["enabled_features"].remove("systemd")
        self.manifest["native_build"]["build_id"] = native.fingerprint(inputs)
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "Desktop build"):
            check.inventory(self.payload, self.site)

    def test_binary_tampering_and_escaping_manifest_are_rejected(self):
        binary = self.candidate / "bin/niri"
        binary.write_bytes(binary.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "binary differs"):
            check.inventory(self.payload, self.site)
        self.manifest["binary"] = "/usr/bin/niri"
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "fixed relative"):
            check.inventory(self.payload, self.site)

    def test_dispatcher_must_match_paired_tools_and_checkout(self):
        (self.site / "niri_fx/package_session.py").write_text("print('unexpected')\n")
        with self.assertRaisesRegex(ValueError, "Dispatcher differs"):
            check.inventory(self.payload, self.site)

    def test_package_versions_match_source_but_allow_different_pkgrels(self):
        self.assertEqual(check.package_version(self.payload, VERSION[:-1] + "2"), VERSION)
        with self.assertRaisesRegex(ValueError, "different source"):
            check.package_version(self.payload, VERSION.replace("1234567", "2345678"))

    def test_stock_package_conflicts_and_missing_lifecycle_deps_are_rejected(self):
        path = self.payload / ".PKGINFO"
        path.write_text(self.pkginfo + "conflict = niri\n")
        with self.assertRaisesRegex(ValueError, "must not provide"):
            check.package_version(self.payload, VERSION)
        path.write_text(self.pkginfo.replace("depend = niri\n", ""))
        with self.assertRaisesRegex(ValueError, "lifecycle"):
            check.package_version(self.payload, VERSION)


if __name__ == "__main__":
    unittest.main()
