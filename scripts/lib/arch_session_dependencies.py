"""Withhold and restore dependencies only inside disposable Arch acceptance.

The native fault uses the actual retained compositor and its actual dependency.
The login probe substitutes only the inactive-service check and makes every
later lifecycle boundary a tripwire. No compositor session is started.
"""

import argparse
import hashlib
import json
import os
import pwd
import re
import shutil
import stat
import subprocess
import sys
import sysconfig
import tempfile
from contextlib import contextmanager
from pathlib import Path

LOGIN_PROBE = """import json
from pathlib import Path
import sys
from unittest.mock import patch

root = Path.home() / '.local/share/niri-fx/native'
tools = json.loads((root / 'tools/selection.json').read_text())
record = json.loads((root / 'tools/runtimes' / (tools['current'] + '.json')).read_text())
sys.path.insert(0, str(Path(record['package']).parent))
from niri_fx import native_login

def forbidden(*args, **kwargs):
    raise AssertionError('Unexpected session lifecycle boundary')

if sys.argv[1] == 'validate':
    selection = native_login.load_selection(root)
    native_login._bundle(root, selection['selected'])
    print('Actual retained bundle preflight passed')
else:
    with (patch.object(native_login, 'require_stopped', return_value=None),
          patch.object(native_login, 'systemctl', side_effect=forbidden),
          patch.object(native_login, 'runtime_paths', side_effect=forbidden),
          patch.object(native_login, 'write_new', side_effect=forbidden),
          patch.object(native_login.os, 'execv', side_effect=forbidden)):
        # _bundle must be allowed to run its short validation subprocesses.
        # Reaching runtime_paths already fails before any session Popen call.
        try:
            native_login.launch(root)
        except (RuntimeError, OSError) as error:
            print(str(error), file=sys.stderr)
            raise SystemExit(1)
        raise AssertionError('Missing dependency unexpectedly permitted login')
"""


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def inventory(paths, relative=None):
    records = []
    for path in sorted(paths):
        item = {"path": str(path.relative_to(relative) if relative else path)}
        try:
            info = path.lstat()
        except FileNotFoundError:
            item["missing"] = True
        else:
            item.update(mode=info.st_mode, uid=info.st_uid, gid=info.st_gid)
            if stat.S_ISLNK(info.st_mode):
                item["target"] = str(path.readlink())
            elif stat.S_ISREG(info.st_mode):
                item["sha256"] = sha(path)
        records.append(item)
    return records


class Probe:
    def __init__(self, output, homes):
        self.output, self.homes = output, homes
        self.users = []
        for suffix, home in zip(("a", "b"), homes, strict=True):
            user = pwd.getpwnam("nirifx-session-" + suffix)
            assert user.pw_uid != 0 and Path(user.pw_dir) == home
            assert home.parent.parent == Path("/tmp")
            assert home.parent.name.startswith("nirifx-arch-session.")
            assert not any(path.is_symlink() for path in (home, *home.parents))
            self.users.append(user.pw_name)
        output.mkdir(mode=0o755)
        # Evidence may be a bind mount. Keep renamed dependencies on the
        # container filesystem so restoration preserves their original inode.
        self.quarantine = Path(tempfile.mkdtemp(prefix="nirifx-dependencies-", dir="/var/tmp"))
        owned = subprocess.check_output(["pacman", "-Qql", "niri"], text=True).splitlines()
        self.stock_files = [Path(path) for path in owned if not path.endswith("/")]
        self.baseline = self.snapshot("baseline")
        self.probe = output / "login-preflight.py"
        self.probe.write_text(LOGIN_PROBE)

    def save(self, name, value):
        (self.output / (name + ".json")).write_text(json.dumps(value, indent=2) + "\n")

    def snapshot(self, name):
        state = {
            "homes": [inventory(home.rglob("*"), home) for home in self.homes],
            "stock_niri": inventory(self.stock_files),
        }
        self.save(name + "-state", state)
        return state

    def unchanged(self, name):
        assert self.snapshot(name) == self.baseline, "Retained or stock files changed: " + name

    def run(self, label, command, *, account=0):
        prefix = []
        if account is not None:
            prefix = [
                "runuser",
                "-u",
                self.users[account],
                "--",
                "env",
                "-i",
                "HOME=" + str(self.homes[account]),
                "PATH=/usr/bin",
                "LANG=C.UTF-8",
                "PYTHONDONTWRITEBYTECODE=1",
            ]
        result = subprocess.run(
            prefix + list(map(str, command)), capture_output=True, text=True, timeout=30, cwd="/"
        )
        self.save(
            label,
            {
                "command": list(map(str, command)),
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
        )
        return result

    def retained(self, label):
        for index, home in enumerate(self.homes):
            cli = home / ".local/bin/niri-fx"
            result = self.run(
                label + f"-user-{index}", [cli, "native", "status", "--offline"], account=index
            )
            assert result.returncode == 0, result.stderr

    def validate(self, label, *, native_ok=True, stock_ok=True):
        for index, home in enumerate(self.homes):
            root = home / ".local/share/niri-fx/native"
            bundle = root / "bundles" / read(root / "selection.json")["selected"]
            for kind, binary, config, expected in (
                ("native", bundle / "bin/niri", bundle / "config.kdl", native_ok),
                ("stock", Path("/usr/bin/niri"), home / ".config/niri/config.kdl", stock_ok),
            ):
                result = self.run(
                    label + f"-{kind}-{index}", [binary, "validate", "-c", config], account=index
                )
                assert (result.returncode == 0) == expected, result.stderr

    @contextmanager
    def withheld(self, path, name):
        saved = self.quarantine / name
        assert not saved.exists() and not saved.is_symlink()
        path.rename(saved)
        try:
            yield
        finally:
            if path.exists() or path.is_symlink():
                raise RuntimeError("Unexpected replacement prevents restoring " + str(path))
            saved.rename(path)

    def dependencies(self, binary, label):
        result = self.run(label, ["/usr/bin/ldd", binary], account=None)
        assert result.returncode == 0, result.stderr
        return {
            name: Path(path).resolve()
            for name, path in re.findall(r"^\s*(\S+) => (/\S+) \(", result.stdout, re.MULTILINE)
        }

    def execute(self):
        report = {
            "status": "running",
            "scope": "disposable container dependency faults",
            "python_minor_upgrade": "not_assessed_same_interpreter_version",
            "physical_session_acceptance": "not_assessed",
        }
        try:
            self.retained("baseline")
            self.validate("baseline")
            site = Path(sysconfig.get_path("purelib")) / "niri_fx"
            assert site.is_relative_to("/usr/lib") and site.is_dir() and not site.is_symlink()
            with self.withheld(site, "system-niri_fx"):
                result = self.run("missing-site-system-cli", ["/usr/bin/niri-fx", "--version"])
                assert result.returncode != 0 and "niri_fx" in result.stderr
                self.retained("missing-site-retained")
                self.validate("missing-site")
                self.unchanged("missing-site")
            assert (
                self.run("restored-site-system-cli", ["/usr/bin/niri-fx", "--version"]).returncode
                == 0
            )
            self.unchanged("restored-site")
            report["system_package_relocation"] = "retained_tools_and_native_validation_passed"

            python = Path("/usr/bin/python3")
            copied = self.output / "relocated-python3"
            shutil.copy2(python.resolve(), copied)
            report["python_binary_sha256"] = sha(copied)
            report["python_version"] = list(sys.version_info[:3])
            with self.withheld(python, "python3-entry"):
                for index, home in enumerate(self.homes):
                    for kind, command in (
                        ("cli", [home / ".local/bin/niri-fx", "--version"]),
                        ("session", ["/usr/bin/niri-fx-session"]),
                    ):
                        result = self.run(f"missing-python-{kind}-{index}", command, account=index)
                        assert result.returncode != 0
                        if kind == "cli":
                            assert "python3" in result.stderr
                self.unchanged("missing-python")
                # Redirect only the stable entry to the same executable bytes.
                # This tests path relocation, never another Python minor release.
                python.symlink_to(copied)
                try:
                    self.retained("relocated-python")
                    self.unchanged("relocated-python")
                finally:
                    assert python.is_symlink() and python.readlink() == copied
                    python.unlink()
            self.retained("restored-python")
            self.unchanged("restored-python")
            report["python_entry_unavailable"] = "both_users_refused_without_fallback"
            report["same_python_binary_relocation"] = "passed"

            root = self.homes[0] / ".local/share/niri-fx/native"
            selected = root / "bundles" / read(root / "selection.json")["selected"]
            needed = self.dependencies(selected / "bin/niri", "native-ldd")
            chosen = next(
                (
                    path
                    for name, path in needed.items()
                    if name.startswith(("libdisplay-info.so.", "libinput.so."))
                ),
                None,
            )
            assert chosen is not None and chosen.is_relative_to("/usr/lib") and chosen.is_file()
            for program in ("python3", "bash", "runuser", "env", "timeout", "systemctl", "pacman"):
                closure = self.dependencies(
                    Path("/usr/bin") / program, "orchestration-ldd-" + program
                )
                assert chosen not in closure.values(), "Fault would break test orchestration"
            stock_needs = chosen in self.dependencies(Path("/usr/bin/niri"), "stock-ldd").values()
            report["library"] = {
                "path": str(chosen),
                "sha256": sha(chosen),
                "stock_niri_also_depends": stock_needs,
            }
            with self.withheld(chosen, chosen.name):
                self.retained("missing-library-tools")
                self.validate("missing-library", native_ok=False, stock_ok=not stock_needs)
                failure = self.run(
                    "missing-library-login-preflight", [python, "-I", "-B", self.probe, "launch"]
                )
                assert failure.returncode == 1 and chosen.name.split(".so")[0] in failure.stderr
                assert "Unexpected session lifecycle boundary" not in failure.stderr
                self.unchanged("missing-library")
            self.validate("restored-library")
            for index in range(2):
                result = self.run(
                    f"restored-login-preflight-{index}",
                    [python, "-I", "-B", self.probe, "validate"],
                    account=index,
                )
                assert result.returncode == 0, result.stderr
            self.unchanged("restored-library")
            report["native_dependency_failure"] = "real_loader_refusal_before_session_dispatch"
            report["native_dependency_recovery"] = "original_library_restored_both_niris_validated"
            report["native_diagnostic"] = (
                "passed"
                if "Niri executable cannot run:" in failure.stderr
                else "legacy_config_error"
            )
            assert report["native_diagnostic"] == "passed", (
                "Native loader failure needs a dependency diagnostic"
            )
            report["status"] = "passed"
        except BaseException as error:
            report.update(status="failed", error=str(error))
            raise
        finally:
            final_error = None
            try:
                self.unchanged("final")
                report["state_preservation"] = "passed"
            except BaseException as error:
                final_error = error
                report.update(status="failed", state_preservation="failed", final_error=str(error))
            restored = not any(self.quarantine.iterdir())
            report["dependency_restoration"] = "passed" if restored else "incomplete"
            if not restored:
                report["status"] = "failed"
            self.save("summary", report)
            # Never discard a dependency left behind by a failed restoration.
            if restored:
                self.quarantine.rmdir()
            if final_error is not None:
                raise final_error
            if not restored:
                raise RuntimeError("Preserved dependencies need recovery: " + str(self.quarantine))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("homes", type=Path, nargs=2)
    args = parser.parse_args()
    if (
        os.environ.get("NIRIFX_ARCH_PACKAGE_CONTAINER") != "1"
        or os.geteuid() != 0
        or not any(path.exists() for path in (Path("/.dockerenv"), Path("/run/.containerenv")))
        or "ID=arch\n" not in Path("/etc/os-release").read_text()
    ):
        parser.error("Refusing execution outside the disposable Arch package container")
    Probe(args.output, args.homes).execute()


if __name__ == "__main__":
    main()
