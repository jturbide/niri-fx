"""Read-only installation notices for a running local Studio process."""

import re
import sys
from dataclasses import dataclass
from itertools import islice
from pathlib import Path

from . import __version__, native_tools, native_tools_launcher

_READ_ERRORS = (OSError, ValueError, KeyError, TypeError, RecursionError, StopIteration)
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+_-]{0,63}")
_MAX_ARCHIVED_RECEIPTS = 128


@dataclass(frozen=True)
class RuntimeIdentity:
    python: Path
    package: Path
    version: str

    @classmethod
    def capture(cls):
        # Resolve the package, but retain the venv's interpreter spelling. Two
        # environments can both symlink bin/python to the same system binary.
        return cls(Path(sys.executable).absolute(), Path(__file__).resolve().parent, __version__)

    def matches(self, record):
        return (
            self.python == Path(record["python"]).absolute()
            and self.package == Path(record["package"]).resolve()
            and self.version == record["version"]
        )


class StudioInstallation:
    def __init__(self, root):
        self.root = Path(root).expanduser().absolute()
        self.running = RuntimeIdentity.capture()
        self.runtime_id = None
        # A checkout beside a system interpreter cannot be a retained venv.
        # Avoid reading an unrelated desktop installation for source previews.
        self.source = not self.running.package.is_relative_to(self.running.python.parent.parent)
        if not self.source:
            try:
                report, _ = self._selection()
                if report is not None:
                    self.runtime_id = self._identify(report)
            except _READ_ERRORS:
                pass  # A later check can verify repaired metadata against this startup identity.

    def _selection(self):
        report = native_tools.status(self.root)
        if not report["installed"]:
            tools = self.root / "tools"
            if tools.exists() or tools.is_symlink():
                raise ValueError("Shared tools metadata is incomplete")
            return None, None
        selected = next(
            runtime for runtime in report["runtimes"] if runtime["id"] == report["current"]
        )
        if selected["status"] != "intact":
            raise ValueError("Selected tools runtime is unavailable")
        record = native_tools_launcher.runtime_record(self.root / "tools", report["current"])
        version = record["version"]
        if not isinstance(version, str) or not _VERSION.fullmatch(version):
            raise ValueError("Selected tools version is invalid")
        return report, version

    def _identify(self, report):
        identifiers = [entry["id"] for entry in report["runtimes"]]
        for identifier in identifiers:
            if self._matches_receipt(identifier):
                return identifier
        # The running receipt may have left current/previous after several
        # upgrades. Inspect a bounded archive once, without executing runtimes.
        directory = self.root / "tools/runtimes"
        if directory.is_symlink():
            raise ValueError("Tools receipt directory is unavailable")
        archived = list(islice(directory.glob("*.json"), _MAX_ARCHIVED_RECEIPTS + 1))
        if len(archived) > _MAX_ARCHIVED_RECEIPTS:
            raise ValueError("Tools receipt archive exceeds the inspection limit")
        for path in archived:
            if path.stem not in identifiers and self._matches_receipt(path.stem):
                return path.stem
        return None

    def _matches_receipt(self, identifier):
        try:
            record = native_tools_launcher.runtime_record(self.root / "tools", identifier)
            matches = self.running.matches(record)
        except _READ_ERRORS:
            return False
        if matches:
            # A recognized but damaged running installation is unavailable,
            # rather than an unrelated source checkout.
            native_tools_launcher.verify_runtime(record)
        return matches

    def snapshot(self):
        if self.source:
            return {"state": "unmanaged", "selected_version": None}
        try:
            report, version = self._selection()
            if report is None:
                if self.runtime_id is not None:
                    raise ValueError("Shared tools selection is unavailable")
                return {"state": "unmanaged", "selected_version": None}
            if self.runtime_id is None:
                self.runtime_id = self._identify(report)
                if self.runtime_id is None:
                    return {"state": "unmanaged", "selected_version": None}
            if report["phase"] == "prepared":
                state = "prepared"
            else:
                state = "current" if report["current"] == self.runtime_id else "changed"
            return {"state": state, "selected_version": version}
        except _READ_ERRORS:
            return {"state": "unavailable", "selected_version": None}
