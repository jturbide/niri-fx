"""Native login ownership tests use temporary paths and mocked user services."""

import json
import os
import signal
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from niri_fx import native_login as login

BUNDLE = "a" * 64
OTHER_BUNDLE = "b" * 64
TOKEN = "c" * 32


class NativeLoginTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "bundles"
        self.root.mkdir()
        self.runtime = Path(self.temporary.name) / "runtime"
        self.runtime.mkdir(mode=0o700)
        environment = patch.dict(
            os.environ, {"XDG_RUNTIME_DIR": str(self.runtime), "XDG_SESSION_ID": "test"}
        )
        environment.start()
        self.addCleanup(environment.stop)
        _, self.directory, self.dropin = login.runtime_paths()
        self.report = {
            "binary": str(self.root / "bin/niri"),
            "config": str(self.root / "config.kdl"),
            "binary_sha256": "d" * 64,
        }

    def lease(self, **changes):
        return {
            "schema": 1,
            "uid": os.getuid(),
            **login.process_identity(os.getpid()),
            "token": TOKEN,
            "bundle_id": BUNDLE,
            "binary": self.report["binary"],
            "root": str(self.root),
            "session_id": "test",
            **changes,
        }

    def write_lease(self, **changes):
        lease = self.lease(**changes)
        self.directory.mkdir(mode=0o700, exist_ok=True)
        (self.directory / "lease.json").write_text(json.dumps(lease))
        return lease

    def record_acceptance(self, lease):
        login._receipt_path(self.directory, lease["token"]).write_text(
            json.dumps(
                {
                    "token": lease["token"],
                    "bundle_id": lease["bundle_id"],
                    "pid": 4242,
                    "start_ticks": 10,
                    "binary": lease["binary"],
                }
            )
        )
        (self.directory / f"verified-{lease['token']}.json").write_text(
            json.dumps(
                {
                    "schema": 1,
                    "token": lease["token"],
                    "bundle_id": lease["bundle_id"],
                    "main_pid": 4242,
                    "version": "26.04",
                    "scope": "process-and-ipc",
                }
            )
        )

    def write_dropin(self):
        self.dropin.parent.mkdir(parents=True)
        self.dropin.write_text(login.dropin_text(self.root, TOKEN))

    def test_running_desktop_refused_before_any_runtime_write(self):
        with (
            patch.object(login, "service_state", return_value=("active", 4242)),
            patch.object(login, "_bundle") as bundle,
        ):
            with self.assertRaisesRegex(RuntimeError, "running desktop has not been changed"):
                login.launch(self.root)
        bundle.assert_not_called()
        self.assertFalse(self.directory.exists())
        self.assertFalse(self.dropin.exists())

    def test_missing_selection_does_not_fall_back_to_another_bundle(self):
        with (
            patch.object(login, "require_stopped"),
            patch.object(login, "_require_tools"),
            patch.object(login, "require_unmodified_start"),
            patch.object(login, "load_selection", return_value={"schema": 1, "selected": None}),
            patch.object(login, "_bundle") as bundle,
        ):
            with self.assertRaisesRegex(RuntimeError, "No native bundle"):
                login.launch(self.root)
        bundle.assert_not_called()
        self.assertFalse(self.directory.exists())

    def test_runtime_directory_refuses_symlinks_and_other_writable_paths(self):
        link = Path(self.temporary.name) / "linked-runtime"
        link.symlink_to(self.runtime, target_is_directory=True)
        for value in (str(link), "relative"):
            with (
                self.subTest(value=value),
                patch.dict(os.environ, {"XDG_RUNTIME_DIR": value}),
                self.assertRaises(RuntimeError),
            ):
                login.runtime_paths()
        self.runtime.chmod(0o777)
        with self.assertRaises(RuntimeError):
            login.runtime_paths()

    def test_lease_requires_process_start_time_root_and_session(self):
        lease = self.write_lease()
        self.assertEqual(login.load_lease(self.directory), lease)
        self.assertTrue(login.lease_alive(lease, TOKEN, self.root))
        self.assertFalse(login.lease_alive(lease | {"start_ticks": -1}, TOKEN, self.root))
        self.assertFalse(login.lease_alive(lease, "d" * 32, self.root))
        self.assertFalse(login.lease_alive(lease, TOKEN, self.root / "other"))
        with patch.dict(os.environ, {"XDG_SESSION_ID": "another"}):
            self.assertFalse(login.lease_alive(lease, TOKEN, self.root))

    def test_malformed_and_symlinked_leases_are_not_authority(self):
        lease = self.write_lease()
        path = self.directory / "lease.json"
        for value in (
            [],
            lease | {"schema": True},
            lease | {"bundle_id": "../elsewhere"},
            lease | {"pid": True},
            lease | {"root": "."},
        ):
            with self.subTest(value=value):
                path.write_text(json.dumps(value))
                self.assertIsNone(login.load_lease(self.directory))
        target = self.directory / "other.json"
        path.rename(target)
        path.symlink_to(target)
        self.assertIsNone(login.load_lease(self.directory))

    def test_unit_arguments_escape_systemd_expansion_without_shell(self):
        value = login.dropin_text(Path('/tmp/a space/%x/$HOME/"quote'), TOKEN)
        self.assertIn('%%x/$$HOME/\\"quote', value)
        self.assertIn("from niri_fx.native_login import main", value)
        self.assertIn("sys.path.insert(0,", value)
        self.assertNotIn("PYTHONPATH", value)
        self.assertNotIn("sh -c", value)
        with self.assertRaises(ValueError):
            login.dropin_text(Path("/tmp/line\nbreak"), TOKEN)

    def test_cleanup_removes_only_matching_lease_and_dropin(self):
        lease = self.write_lease()
        self.write_dropin()
        with patch.object(login, "systemctl") as service:
            self.assertTrue(login.owned_cleanup(self.directory, self.dropin, lease))
        service.assert_called_once_with("daemon-reload")
        self.assertFalse(self.dropin.exists())
        self.assertFalse((self.directory / "lease.json").exists())

    def test_cleanup_preserves_external_edits(self):
        lease = self.write_lease()
        self.write_dropin()
        self.dropin.write_text("[Service]\nExecStart=external\n")
        with patch.object(login, "systemctl") as service:
            self.assertFalse(login.owned_cleanup(self.directory, self.dropin, lease))
        service.assert_not_called()
        self.assertTrue(self.dropin.exists())
        self.assertTrue((self.directory / "lease.json").exists())

    def test_stale_override_executes_stock_without_inspecting_bundle(self):
        self.write_lease(start_ticks=-1)
        with patch.object(login, "_bundle") as bundle, patch.object(login.os, "execv") as execute:
            login.compositor(self.root, TOKEN)
        bundle.assert_not_called()
        execute.assert_called_once_with(str(login.STOCK), [str(login.STOCK), "--session"])

    def test_missing_runtime_executes_stock_without_inspecting_bundle(self):
        with (
            patch.dict(os.environ, {"XDG_RUNTIME_DIR": ""}),
            patch.object(login, "_bundle") as bundle,
            patch.object(login.os, "execv") as execute,
        ):
            login.compositor(self.root, TOKEN)
        bundle.assert_not_called()
        execute.assert_called_once_with(str(login.STOCK), [str(login.STOCK), "--session"])

    def test_compositor_uses_leased_bundle_despite_changed_selection(self):
        self.write_lease()
        (self.root / "selection.json").write_text(
            json.dumps({"schema": 1, "selected": OTHER_BUNDLE})
        )
        with (
            patch.object(login, "_bundle", return_value=self.report) as bundle,
            patch.object(login, "load_selection") as selected,
            patch.object(login.os, "execv") as execute,
        ):
            login.compositor(self.root, TOKEN)
        selected.assert_not_called()
        bundle.assert_called_once_with(self.root, BUNDLE)
        execute.assert_called_once_with(
            self.report["binary"],
            [self.report["binary"], "--session", "--config", self.report["config"]],
        )
        receipt = json.loads(login._receipt_path(self.directory, TOKEN).read_text())
        self.assertEqual(receipt["bundle_id"], BUNDLE)
        self.assertEqual(receipt["pid"], os.getpid())

    def test_invalid_bundle_prevents_native_execution(self):
        self.write_lease()
        with (
            patch.object(login, "_bundle", side_effect=ValueError("changed bundle")),
            patch.object(login.os, "execv") as execute,
        ):
            with self.assertRaisesRegex(ValueError, "changed bundle"):
                login.compositor(self.root, TOKEN)
        execute.assert_not_called()
        self.assertFalse(login._receipt_path(self.directory, TOKEN).exists())

    def test_lease_expiring_during_validation_prevents_execution(self):
        self.write_lease()

        def validate(*_):
            (self.directory / "lease.json").unlink()
            return self.report

        with (
            patch.object(login, "_bundle", side_effect=validate),
            patch.object(login.os, "execv") as execute,
        ):
            with self.assertRaisesRegex(RuntimeError, "lost its launcher"):
                login.compositor(self.root, TOKEN)
        execute.assert_not_called()

    def test_changed_receipt_cannot_authorize_another_executable(self):
        lease = self.write_lease()
        identity = {"pid": 4242, "start_ticks": 10}
        login._receipt_path(self.directory, TOKEN).write_text(
            json.dumps(
                {
                    **identity,
                    "token": TOKEN,
                    "bundle_id": BUNDLE,
                    "binary": "/tmp/another-executable",
                }
            )
        )
        with (
            patch.object(login, "process_identity", return_value=identity),
            patch.object(login, "same_executable", return_value=True),
        ):
            self.assertFalse(login._owned_compositor(self.directory, lease, 4242))

    def test_configuration_validation_rechecks_bundle_integrity(self):
        success = subprocess.CompletedProcess([], 0, "", "")
        with (
            patch.object(
                login,
                "inspect_bundle",
                side_effect=[self.report, self.report | {"binary_sha256": "e" * 64}],
            ),
            patch.object(login.subprocess, "run", return_value=success) as run,
        ):
            with self.assertRaisesRegex(RuntimeError, "changed during"):
                login._bundle(self.root, BUNDLE)
        self.assertEqual(
            run.call_args.args[0], [self.report["binary"], "validate", "-c", self.report["config"]]
        )

    def test_failed_configuration_validation_prevents_login(self):
        failure = subprocess.CompletedProcess([], 1, "", "bad configuration")
        with (
            patch.object(login, "inspect_bundle", return_value=self.report),
            patch.object(login.subprocess, "run", return_value=failure),
        ):
            with self.assertRaisesRegex(RuntimeError, "bad configuration"):
                login._bundle(self.root, BUNDLE)

    def test_launch_captures_selection_once_and_cleans_runtime(self):
        captured = []
        child = Mock()
        child.poll.return_value = 0
        child.returncode = 0

        def start(command):
            captured.append(login.load_lease(self.directory))
            self.record_acceptance(captured[-1])
            self.assertEqual(command, [str(login.UPSTREAM_SESSION)])
            (self.root / "selection.json").write_text(
                json.dumps({"schema": 1, "selected": OTHER_BUNDLE})
            )
            return child

        with (
            patch.object(login, "require_stopped"),
            patch.object(login, "_require_tools"),
            patch.object(login, "require_unmodified_start"),
            patch.object(
                login, "load_selection", return_value={"schema": 1, "selected": BUNDLE}
            ) as selected,
            patch.object(login, "_bundle", return_value=self.report),
            patch.object(login, "systemctl"),
            patch.object(login, "_stop_owned", return_value=False),
            patch.object(login.subprocess, "Popen", side_effect=start),
        ):
            self.assertEqual(login.launch(self.root), 0)
        selected.assert_called_once_with(self.root)
        self.assertEqual(captured[0]["bundle_id"], BUNDLE)
        self.assertFalse(self.dropin.exists())
        self.assertFalse((self.directory / "lease.json").exists())

    def test_launch_failure_after_runtime_write_still_cleans_owned_files(self):
        with (
            patch.object(login, "require_stopped"),
            patch.object(login, "_require_tools"),
            patch.object(login, "require_unmodified_start"),
            patch.object(login, "load_selection", return_value={"schema": 1, "selected": BUNDLE}),
            patch.object(login, "_bundle", return_value=self.report),
            patch.object(login, "systemctl"),
            patch.object(login, "_stop_owned", return_value=False),
            patch.object(login.subprocess, "Popen", side_effect=OSError("could not start")),
        ):
            with self.assertRaisesRegex(OSError, "could not start"):
                login.launch(self.root)
        self.assertFalse(self.dropin.exists())
        self.assertFalse((self.directory / "lease.json").exists())

    def test_live_lease_cannot_be_replaced(self):
        self.write_lease()
        with (
            patch.object(login, "require_stopped"),
            patch.object(login, "_require_tools"),
            patch.object(login, "require_unmodified_start"),
            patch.object(login, "load_selection", return_value={"schema": 1, "selected": BUNDLE}),
            patch.object(login, "_bundle", return_value=self.report),
            patch.object(login.subprocess, "Popen") as start,
        ):
            with self.assertRaisesRegex(RuntimeError, "Another live launcher"):
                login.launch(self.root)
        start.assert_not_called()

    def test_service_stop_requires_exact_compositor_start_time(self):
        lease = self.write_lease()
        receipt = {
            "token": TOKEN,
            "bundle_id": BUNDLE,
            "pid": 4242,
            "start_ticks": 10,
            "binary": self.report["binary"],
        }
        login._receipt_path(self.directory, TOKEN).write_text(json.dumps(receipt))
        with (
            patch.object(login, "process_identity", return_value={"pid": 4242, "start_ticks": 11}),
            patch.object(login, "same_executable", return_value=True),
        ):
            self.assertFalse(login._owned_compositor(self.directory, lease, 4242))
        with (
            patch.object(login, "process_identity", return_value={"pid": 4242, "start_ticks": 10}),
            patch.object(login, "same_executable", return_value=True),
        ):
            self.assertTrue(login._owned_compositor(self.directory, lease, 4242))

    def test_stop_never_targets_an_unowned_replacement_service(self):
        lease = self.write_lease()
        with (
            patch.object(login, "service_state", return_value=("active", 4242)),
            patch.object(login, "_owned_compositor", return_value=False),
            patch.object(login, "systemctl") as service,
        ):
            self.assertFalse(login._stop_owned(self.directory, lease, self.root))
        service.assert_not_called()

    def test_verify_stock_fallback_does_not_inspect_absent_bundle(self):
        self.write_lease(start_ticks=-1)
        with (
            patch.object(login, "service_state", return_value=("active", 4242)),
            patch.object(login, "same_executable", return_value=True),
            patch.object(login, "_bundle") as bundle,
        ):
            login.verify(self.root, TOKEN)
        bundle.assert_not_called()

    def test_verify_native_process_and_ipc_does_not_require_enabled_effects(self):
        self.write_lease()
        (self.runtime / "niri.wayland-1.4242.sock").touch()
        with (
            patch.object(login, "service_state", return_value=("active", 4242)),
            patch.object(login, "_bundle", return_value=self.report),
            patch.object(login, "_owned_compositor", return_value=True),
            patch.object(login, "same_executable", return_value=True),
            patch.object(Path, "is_socket", return_value=True),
            patch.object(login, "_socket_version", return_value="26.04"),
        ):
            login.verify(self.root, TOKEN)
        report = json.loads((self.directory / f"verified-{TOKEN}.json").read_text())
        self.assertEqual(report["scope"], "process-and-ipc")
        self.assertEqual(report["bundle_id"], BUNDLE)
        self.assertNotIn("renderer_verified", report)

    def test_verification_timeout_does_not_report_success(self):
        self.write_lease()
        with (
            patch.object(login, "_bundle", return_value=self.report),
            patch.object(login, "VERIFY_TIMEOUT", 0),
        ):
            with self.assertRaisesRegex(RuntimeError, "did not expose"):
                login.verify(self.root, TOKEN)
        self.assertFalse((self.directory / f"verified-{TOKEN}.json").exists())

    def test_competing_runtime_start_hook_is_refused_without_mutation(self):
        self.dropin.parent.mkdir(parents=True)
        old = self.dropin.with_name("90-niri-fx-desktop-test.conf")
        original = "[Service]\nExecStartPost=/tmp/older-launcher verify\n"
        old.write_text(original)
        result = subprocess.CompletedProcess(
            [], 0, "# /usr/lib/systemd/user/niri.service\n[Service]\nExecStart=niri --session\n", ""
        )
        with patch.object(login, "systemctl", return_value=result):
            with self.assertRaisesRegex(RuntimeError, "Another niri.service start override"):
                login.require_unmodified_start(self.directory, self.dropin)
        self.assertEqual(old.read_text(), original)
        self.assertFalse(self.directory.exists())
        self.assertFalse(self.dropin.exists())

    def test_persistent_start_override_is_refused_but_environment_is_allowed(self):
        for hook in ("ExecStart=", "ExecStartPre=/tmp/hook", "ExecStartPost=/tmp/hook"):
            text = (
                "# /usr/lib/systemd/user/niri.service\n[Service]\nExecStart=niri --session\n# /tmp/user/niri.service.d/local.conf\n[Service]\n"
                + hook
                + "\n"
            )
            with (
                self.subTest(hook=hook),
                patch.object(
                    login, "systemctl", return_value=subprocess.CompletedProcess([], 0, text, "")
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "start override"):
                    login.require_unmodified_start(self.directory, self.dropin)
        text = "# /usr/lib/systemd/user/niri.service\n[Service]\nExecStart=niri --session\n# /tmp/user/niri.service.d/env.conf\n[Service]\nEnvironment=TEST=1\n"
        with patch.object(
            login, "systemctl", return_value=subprocess.CompletedProcess([], 0, text, "")
        ):
            login.require_unmodified_start(self.directory, self.dropin)

    def test_exact_owned_stale_override_can_be_cleaned(self):
        self.write_lease(start_ticks=-1)
        self.write_dropin()
        with patch.object(
            login, "systemctl", return_value=subprocess.CompletedProcess([], 0, "", "")
        ):
            login.require_unmodified_start(self.directory, self.dropin)
        self.assertTrue(self.dropin.exists())

    def test_upstream_zero_exit_without_verified_login_is_failure(self):
        child = Mock()
        child.poll.return_value = 0
        child.returncode = 0
        with (
            patch.object(login, "require_stopped"),
            patch.object(login, "_require_tools"),
            patch.object(login, "require_unmodified_start"),
            patch.object(login, "load_selection", return_value={"schema": 1, "selected": BUNDLE}),
            patch.object(login, "_bundle", return_value=self.report),
            patch.object(login, "systemctl"),
            patch.object(login, "_stop_owned", return_value=False),
            patch.object(login.subprocess, "Popen", return_value=child),
        ):
            with self.assertRaisesRegex(RuntimeError, "ended before compositor"):
                login.launch(self.root)
        self.assertFalse(self.dropin.exists())
        self.assertFalse((self.directory / "lease.json").exists())

    def test_start_override_refusal_precedes_runtime_creation(self):
        with (
            patch.object(login, "require_stopped"),
            patch.object(login, "_require_tools"),
            patch.object(login, "load_selection", return_value={"schema": 1, "selected": BUNDLE}),
            patch.object(login, "_bundle", return_value=self.report),
            patch.object(
                login, "require_unmodified_start", side_effect=RuntimeError("competing hook")
            ),
            patch.object(login.subprocess, "Popen") as start,
        ):
            with self.assertRaisesRegex(RuntimeError, "competing hook"):
                login.launch(self.root)
        start.assert_not_called()
        self.assertFalse(self.directory.exists())
        self.assertFalse(self.dropin.exists())

    def test_interrupted_start_without_acceptance_returns_signal_status(self):
        handlers = {}
        child = Mock()
        child.poll.return_value = 0
        child.returncode = 0

        def register(signum, handler):
            handlers[signum] = handler
            return signal.SIG_DFL

        def start(_):
            handlers[signal.SIGTERM](signal.SIGTERM, None)
            return child

        with (
            patch.object(login, "require_stopped"),
            patch.object(login, "_require_tools"),
            patch.object(login, "require_unmodified_start"),
            patch.object(login, "load_selection", return_value={"schema": 1, "selected": BUNDLE}),
            patch.object(login, "_bundle", return_value=self.report),
            patch.object(login, "systemctl"),
            patch.object(login, "_stop_owned", return_value=False),
            patch.object(login.signal, "signal", side_effect=register),
            patch.object(login.subprocess, "Popen", side_effect=start),
        ):
            self.assertEqual(login.launch(self.root), 128 + signal.SIGTERM)
        self.assertFalse(self.dropin.exists())
        self.assertTrue(all(value == signal.SIG_DFL for value in handlers.values()))

    def test_verified_receipt_is_bound_to_lease_and_compositor_record(self):
        lease = self.write_lease()
        self.record_acceptance(lease)
        self.assertTrue(login._verified_login(self.directory, lease))
        self.assertFalse(login._verified_login(self.directory, lease | {"bundle_id": OTHER_BUNDLE}))
        login._receipt_path(self.directory, TOKEN).unlink()
        self.assertFalse(login._verified_login(self.directory, lease))

    def test_missing_tools_are_actionable_and_read_only(self):
        with patch.object(login, "STOCK", self.root / "missing"):
            with self.assertRaisesRegex(RuntimeError, "Required session executable"):
                login._require_tools()
        self.assertFalse(self.directory.exists())


if __name__ == "__main__":
    unittest.main()
