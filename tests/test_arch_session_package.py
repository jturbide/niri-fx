"""Complete Arch archive contract: tools and native session are inseparable."""

import base64
import csv
import importlib.util
import io
import json
import os
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
    "arch_package_check", ROOT / "scripts/check-arch-package.py"
)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)
session = check.session
native = session.native_build
VERSION = "0.21.0"


class ArchSessionPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="complete package tests ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.payload = self.root / "payload"
        self.site = self.payload / "usr/lib/python3.14/site-packages"
        self.distribution = self.site / f"niri_fx-{VERSION}.dist-info"
        self.candidate = self.payload / session.PREFIX
        self.licenses = self.payload / "usr/share/licenses/niri-fx"
        files = (
            check.METADATA
            | session.PAYLOAD
            | {"usr/bin/niri-fx", check.DESKTOP, check.ICON, "usr/share/doc/niri-fx/README.Arch"}
            | {
                f"usr/share/licenses/niri-fx/{name}"
                for name in (
                    "LICENSE",
                    "COPYING-NIRI",
                    "LICENSE.niri",
                    "LICENSE.packaging",
                    "THIRD_PARTY.md",
                )
            }
            | {f"usr/lib/python3.14/site-packages/niri_fx/{name}" for name in check.RESOURCES}
        )
        for name in files:
            path = self.payload / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic package fixture\n" * 8)
            path.chmod(0o644)
        self.distribution.mkdir()
        (self.distribution / "METADATA").write_text(f"Name: niri-fx\nVersion: {VERSION}\n")
        (self.payload / check.DESKTOP).write_text(
            "[Desktop Entry]\nType=Application\nExec=/usr/bin/niri-fx studio --active\n"
            "Icon=niri-fx\nTerminal=false\n"
        )
        (self.payload / session.DESKTOP).write_bytes(session.DESKTOP_ENTRY)
        dispatcher = (ROOT / "niri_fx/package_session.py").read_bytes()
        (self.payload / session.DISPATCHER).write_bytes(dispatcher)
        (self.payload / session.DISPATCHER).chmod(0o755)
        (self.site / "niri_fx/package_session.py").write_bytes(dispatcher)
        cli = self.payload / "usr/bin/niri-fx"
        cli.write_bytes(b"#!/usr/bin/python3\n# synthetic entry point\n")
        cli.chmod(0o755)
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
        self.pkginfo = f"pkgname = niri-fx\npkgver = {VERSION}-1\narch = x86_64\n" + "".join(
            f"depend = {name}\n"
            for name in (
                "niri",
                "python",
                "bash",
                "systemd",
                "dbus",
                "wayland",
                "libglvnd",
                "hicolor-icon-theme",
            )
        )
        (self.payload / ".PKGINFO").write_text(self.pkginfo)
        self.write_record()

    def write_manifest(self):
        (self.candidate / "manifest.json").write_text(json.dumps(self.manifest))

    def write_record(self):
        record = self.distribution / "RECORD"
        rows = []
        for path in sorted(self.site.rglob("*")) + [self.payload / "usr/bin/niri-fx"]:
            if not path.is_file() or path == record:
                continue
            digest = (
                base64.urlsafe_b64encode(bytes.fromhex(native.digest(path))).decode().rstrip("=")
            )
            rows.append((os.path.relpath(path, self.site), f"sha256={digest}", path.stat().st_size))
        rows.append((os.path.relpath(record, self.site), "", ""))
        with record.open("w", newline="") as stream:
            csv.writer(stream).writerows(rows)

    def files(self):
        return {
            str(path.relative_to(self.payload))
            for path in self.payload.rglob("*")
            if path.is_file()
        }

    def archive(self, *, extra=None, missing=None):
        output = self.root / "package.tar"
        with tarfile.open(output, "w") as archive:
            for name in sorted(self.files()):
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

    def test_complete_payload_and_exact_hashes_without_running_native_executables(self):
        output = self.root / "extracted"
        files = check.extract_tar(self.archive(), output)
        self.assertEqual(files, self.files())
        with patch.object(check.subprocess, "Popen", side_effect=AssertionError("must not run")):
            name, pkgver, version = check.package_version(output)
            site = check.inventory(output, files, name, version)
            evidence = session.inventory(output, site, name)
        self.assertEqual((name, pkgver, version), ("niri-fx", f"{VERSION}-1", VERSION))
        self.assertEqual(evidence["binary_sha256"], self.manifest["binary_sha256"])
        self.assertEqual(
            evidence["manifest_sha256"], native.digest(self.candidate / "manifest.json")
        )
        self.assertEqual(set(evidence["patch_sha256"]), set(native.STACKS["fragment"]))
        self.assertEqual(evidence["runtime_acceptance"], "not_assessed")

    def test_real_packaged_cli_schema4_render_and_preview_outside_checkout(self):
        from niri_fx import __version__

        shutil.copytree(
            ROOT / "niri_fx",
            self.site / "niri_fx",
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
        (self.payload / "usr/bin/niri-fx").write_text(
            "#!/usr/bin/python3\nfrom niri_fx.cli import main\nmain()\n"
        )
        isolated = self.root / "isolated"
        isolated.mkdir()
        self.assertGreater(check.smoke(self.payload, self.site, isolated, __version__), 50)

    def test_vcs_package_is_self_contained_and_uses_its_own_license_directory(self):
        pkgver = f"{VERSION}.r75.g1234567-2"
        (self.payload / ".PKGINFO").write_text(
            self.pkginfo.replace("pkgname = niri-fx\n", "pkgname = niri-fx-git\n").replace(
                f"pkgver = {VERSION}-1", f"pkgver = {pkgver}"
            )
            + f"provides = niri-fx={VERSION}\nconflict = niri-fx\n"
        )
        self.licenses.rename(self.licenses.with_name("niri-fx-git"))
        name, actual, version = check.package_version(self.payload)
        self.assertEqual((name, actual, version), ("niri-fx-git", pkgver, VERSION))
        site = check.inventory(self.payload, self.files(), name, version)
        self.assertEqual(
            session.inventory(self.payload, site, name)["binary_sha256"],
            self.manifest["binary_sha256"],
        )
        self.licenses.with_name("niri-fx-git").rename(self.licenses)
        with self.assertRaisesRegex(ValueError, "License directory"):
            check.inventory(self.payload, self.files(), name, version)

    def test_unsafe_members_are_rejected_before_any_extraction(self):
        for name, kind in (
            ("../escape", tarfile.REGTYPE),
            ("/etc/passwd", tarfile.REGTYPE),
            ("usr/bin/niri", tarfile.REGTYPE),
            ("usr/bin/niri-session", tarfile.REGTYPE),
            ("etc/niri/config.kdl", tarfile.REGTYPE),
            ("home/example/config.kdl", tarfile.REGTYPE),
            ("usr/lib/systemd/user/niri.service", tarfile.REGTYPE),
            (".INSTALL", tarfile.REGTYPE),
            ("usr/share/libalpm/hooks/niri-fx.hook", tarfile.REGTYPE),
            ("usr/share/wayland-sessions/niri.desktop", tarfile.REGTYPE),
            ("usr/lib/niri-fx/link", tarfile.SYMTYPE),
            ("usr/lib/niri-fx/link", tarfile.LNKTYPE),
            (check.DESKTOP, tarfile.REGTYPE),
        ):
            with self.subTest(name=name, kind=kind):
                entry = tarfile.TarInfo(name)
                entry.mode = 0o644
                entry.type = kind
                entry.linkname = "/etc/passwd" if kind in {tarfile.SYMTYPE, tarfile.LNKTYPE} else ""
                destination = self.root / "not-created"
                with self.assertRaises(ValueError):
                    check.extract_tar(self.archive(extra=entry), destination)
                self.assertFalse(destination.exists())

    def test_neither_tools_only_nor_native_only_archive_is_accepted(self):
        for name in (
            "usr/bin/niri-fx",
            check.DESKTOP,
            session.DISPATCHER,
            f"{session.PREFIX}/bin/niri",
            f"{session.PREFIX}/patches/niri-swap.patch",
        ):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "incomplete"):
                check.extract_tar(self.archive(missing=name), self.root / "missing")
            self.assertFalse((self.root / "missing").exists())

    def test_missing_wheel_resource_and_unrecorded_runtime_are_rejected(self):
        (self.site / "niri_fx/studio.js").unlink()
        self.write_record()
        with self.assertRaisesRegex(ValueError, "Missing packaged resource: studio.js"):
            check.inventory(self.payload, self.files(), "niri-fx", VERSION)
        (self.site / "niri_fx/unrecorded.py").write_text("# not inventoried\n")
        with self.assertRaisesRegex(ValueError, "Incomplete installed RECORD"):
            check.inventory(self.payload, self.files(), "niri-fx", VERSION)

    def test_missing_shader_and_session_resource_are_rejected(self):
        for name in ("shaders/hexagons.glsl", "native_package.py"):
            with self.subTest(name=name):
                path = self.site / "niri_fx" / name
                original = path.read_bytes()
                path.unlink()
                self.write_record()
                with self.assertRaisesRegex(ValueError, "Missing packaged resource"):
                    check.inventory(self.payload, self.files(), "niri-fx", VERSION)
                path.write_bytes(original)
                self.write_record()

    def test_wheel_record_and_version_must_match_package(self):
        with self.assertRaisesRegex(ValueError, "metadata differs"):
            check.inventory(self.payload, self.files(), "niri-fx", "0.99.0")
        (self.site / "niri_fx/studio.js").write_text("tampered\n")
        with self.assertRaisesRegex(ValueError, "RECORD mismatch"):
            check.inventory(self.payload, self.files(), "niri-fx", VERSION)

    def test_private_modes_or_nonroot_owner_cannot_leak_into_package(self):
        for mode, uid, error in ((0o700, 0, "permissions"), (0o755, 1000, "ownership")):
            entry = tarfile.TarInfo(session.PREFIX)
            entry.type, entry.mode, entry.uid = tarfile.DIRTYPE, mode, uid
            with self.assertRaisesRegex(ValueError, error):
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
                        session.subprocess,
                        "Popen",
                        side_effect=lambda *a, code=code, **kw: popen(
                            [sys.executable, "-c", code], **kw
                        ),
                    ),
                    self.assertRaisesRegex(ValueError, error),
                ):
                    session.decompress(self.root / "unused", output, limit=limit, timeout=timeout)
                self.assertLessEqual(output.stat().st_size, limit)

    def test_partial_stack_and_minimal_features_are_rejected(self):
        inputs = self.manifest["native_build"]["inputs"]
        inputs["patches"].pop()
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "four current"):
            session.inventory(self.payload, self.site, "niri-fx")
        inputs["patches"].append(
            {"file": "niri-swap.patch", "sha256": self.manifest["swap_patch_sha256"]}
        )
        inputs["enabled_features"].remove("systemd")
        self.manifest["native_build"]["build_id"] = native.fingerprint(inputs)
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "Desktop build"):
            session.inventory(self.payload, self.site, "niri-fx")

    def test_wrong_build_target_or_license_identity_is_rejected(self):
        inputs = self.manifest["native_build"]["inputs"]
        target = inputs["target"]
        inputs["target"] = "aarch64-unknown-linux-gnu"
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "build target"):
            session.inventory(self.payload, self.site, "niri-fx")
        inputs["target"] = target
        self.write_manifest()
        (self.licenses / "LICENSE.niri").write_text("different upstream license\n" * 8)
        with self.assertRaisesRegex(ValueError, "Upstream license differs"):
            session.inventory(self.payload, self.site, "niri-fx")

    def test_binary_lock_and_patch_hash_tampering_is_rejected(self):
        for name in ("bin/niri", "source/Cargo.lock", "patches/niri-swap.patch"):
            with self.subTest(name=name):
                path = self.candidate / name
                original = path.read_bytes()
                path.write_bytes(original + b"changed")
                with self.assertRaisesRegex(ValueError, "differs from the recorded SHA"):
                    session.inventory(self.payload, self.site, "niri-fx")
                path.write_bytes(original)

    def test_escaping_manifest_and_wrong_dispatcher_are_rejected(self):
        self.manifest["binary"] = "/usr/bin/niri"
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, "fixed relative"):
            session.inventory(self.payload, self.site, "niri-fx")
        self.manifest["binary"] = "bin/niri"
        self.write_manifest()
        (self.site / "niri_fx/package_session.py").write_text("print('unexpected')\n")
        with self.assertRaisesRegex(ValueError, "Dispatcher differs"):
            session.inventory(self.payload, self.site, "niri-fx")

    def test_vcs_requires_version_suffix_and_replacement_relationships(self):
        vcs = self.pkginfo.replace("pkgname = niri-fx\n", "pkgname = niri-fx-git\n")
        path = self.payload / ".PKGINFO"
        path.write_text(vcs + "provides = niri-fx\nconflict = niri-fx\n")
        with self.assertRaisesRegex(ValueError, "VCS pkgver"):
            check.package_version(self.payload)
        vcs = vcs.replace(f"pkgver = {VERSION}-1", f"pkgver = {VERSION}.r75.g1234567-1")
        for relationship in ("provides = niri-fx\n", "conflict = niri-fx\n"):
            path.write_text(vcs + relationship)
            with self.assertRaisesRegex(ValueError, "must provide and conflict"):
                check.package_version(self.payload)

    def test_unsupported_names_split_dependencies_and_stock_conflicts_are_rejected(self):
        invalid = (
            self.pkginfo.replace("pkgname = niri-fx\n", "pkgname = niri-fx-compositor-git\n"),
            self.pkginfo.replace("pkgname = niri-fx\n", "pkgname = niri-fx-tools\n"),
            self.pkginfo.replace("arch = x86_64", "arch = any"),
            self.pkginfo + "depend = niri-fx-git\n",
            self.pkginfo + "depend = niri-fx-compositor-git\n",
            self.pkginfo + "conflict = niri\n",
            self.pkginfo + "provides = niri\n",
            self.pkginfo + "replaces = niri-fx\n",
            self.pkginfo.replace("depend = niri\n", ""),
        )
        for pkginfo in invalid:
            with self.subTest(pkginfo=pkginfo), self.assertRaises(ValueError):
                (self.payload / ".PKGINFO").write_text(pkginfo)
                check.package_version(self.payload)


if __name__ == "__main__":
    unittest.main()
