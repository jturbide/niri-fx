"""Bounded, read-only accounting of regular files inside one native bundle.

Logical sizes and allocated blocks cover regular files only, deduplicated by
(device, inode). Directory blocks, symlink blocks and every symlink target are
excluded. Allocated bytes sum st_blocks and may share extents with other files.
This is metadata sampled during a walk, not a filesystem snapshot, reclaimable-
space estimate or proof that any file is safe to delete.
"""

import errno
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

MAX_ENTRIES = 20000
MAX_DEPTH = 64
MAX_ANCESTORS = 256
MAX_DETAILS = 64
_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK


def _identity(info):
    # Access time changes when inspecting directories; it is not a mutation of
    # the measured data. ctime also catches restored mtime and permission edits.
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        getattr(info, "st_blocks", None),
    )


def _stat_at(parent, name):
    return os.stat(name, dir_fd=parent, follow_symlinks=False)


@dataclass
class _Node:
    name: str
    info: os.stat_result
    children: list = field(default_factory=list)


class _Inspection:
    def __init__(self, path):
        self.path = path
        self.errors = []
        self.excluded = []
        self.omitted_errors = 0
        self.omitted_exclusions = 0
        self.inodes = {}
        self.observed = {
            "logical_bytes": 0,
            "allocated_bytes": 0,
            "regular_files": 0,
            "unique_regular_files": 0,
            "hardlink_aliases": 0,
            "directories": 0,
            "symlinks": 0,
            "special_files": 0,
            "entries": 0,
        }

    def error(self, path, code, error=None):
        item = {"path": str(path), "code": code}
        if error is not None and error.errno is not None:
            item["errno"] = error.errno
        if len(self.errors) < MAX_DETAILS:
            self.errors.append(item)
        else:
            self.omitted_errors += 1

    def io_error(self, path, error):
        self.error(
            path,
            "permission-denied" if error.errno in (errno.EACCES, errno.EPERM) else "io-error",
            error,
        )

    def exclude(self, path, kind):
        if len(self.excluded) < MAX_DETAILS:
            self.excluded.append({"path": str(path), "kind": kind})
        else:
            self.omitted_exclusions += 1

    def regular_file(self, path, info):
        self.observed["regular_files"] += 1
        inode = info.st_dev, info.st_ino
        if inode in self.inodes:
            self.observed["hardlink_aliases"] += 1
            if self.inodes[inode] != _identity(info):
                self.error(path, "entry-changed")
            return
        self.inodes[inode] = _identity(info)
        self.observed["unique_regular_files"] += 1
        self.observed["logical_bytes"] += info.st_size
        blocks = getattr(info, "st_blocks", None)
        if blocks is None or blocks < 0:
            self.observed["allocated_bytes"] = None
            self.error(path, "allocation-unavailable")
        elif self.observed["allocated_bytes"] is not None:
            self.observed["allocated_bytes"] += blocks * 512

    def walk(self, descriptor, node, relative, depth):
        names = []
        try:
            # Do not materialize an unbounded scandir iterator before applying
            # the limit. Entry names are then sorted for reproducible reporting.
            with os.scandir(descriptor) as entries:
                for entry in entries:
                    if self.observed["entries"] >= MAX_ENTRIES:
                        self.error(relative, "entry-limit")
                        break
                    self.observed["entries"] += 1
                    names.append(entry.name)
        except OSError as error:
            self.io_error(relative, error)
        for name in sorted(names):
            path = f"{relative}/{name}" if relative != "." else name
            try:
                info = _stat_at(descriptor, name)
            except OSError as error:
                self.io_error(path, error)
                continue
            child = _Node(name, info)
            node.children.append(child)
            if stat.S_ISREG(info.st_mode):
                self.regular_file(path, info)
            elif stat.S_ISLNK(info.st_mode):
                self.observed["symlinks"] += 1
                self.exclude(path, "symlink-target-not-inspected")
            elif stat.S_ISDIR(info.st_mode):
                self.observed["directories"] += 1
                if depth >= MAX_DEPTH:
                    self.error(path, "depth-limit")
                    continue
                child_fd = None
                try:
                    child_fd = os.open(name, _DIRECTORY_FLAGS, dir_fd=descriptor)
                    if _identity(os.fstat(child_fd)) != _identity(info):
                        self.error(path, "entry-changed")
                    else:
                        self.walk(child_fd, child, path, depth + 1)
                except OSError as error:
                    self.io_error(path, error)
                finally:
                    if child_fd is not None:
                        os.close(child_fd)
            else:
                self.observed["special_files"] += 1
                self.exclude(path, "special-file")
        if _identity(os.fstat(descriptor)) != _identity(node.info):
            self.error(relative, "entry-changed")

    def verify(self, descriptor, node, relative):
        """Recheck metadata after the walk so later siblings cannot hide edits."""
        if _identity(os.fstat(descriptor)) != _identity(node.info):
            self.error(relative, "entry-changed")
            return
        for child in node.children:
            path = f"{relative}/{child.name}" if relative != "." else child.name
            try:
                info = _stat_at(descriptor, child.name)
                if _identity(info) != _identity(child.info):
                    self.error(path, "entry-changed")
                    continue
                if stat.S_ISDIR(info.st_mode):
                    child_fd = os.open(child.name, _DIRECTORY_FLAGS, dir_fd=descriptor)
                    try:
                        self.verify(child_fd, child, path)
                    finally:
                        os.close(child_fd)
            except OSError as error:
                self.io_error(path, error)
        if _identity(os.fstat(descriptor)) != _identity(node.info):
            self.error(relative, "entry-changed")

    def report(self, available):
        complete = available and not self.errors and not self.omitted_errors
        return {
            "path": str(self.path),
            "status": "complete" if complete else "incomplete" if available else "unavailable",
            "scope": "regular-files-only; hardlinks-deduplicated; symlink-targets-excluded",
            "logical_bytes": self.observed["logical_bytes"] if complete else None,
            "allocated_bytes": self.observed["allocated_bytes"] if complete else None,
            "observed": self.observed,
            "excluded": sorted(self.excluded, key=lambda item: (item["path"], item["kind"])),
            "errors": sorted(self.errors, key=lambda item: (item["path"], item["code"])),
            "omitted_errors": self.omitted_errors,
            "omitted_exclusions": self.omitted_exclusions,
            "limits": {"entries": MAX_ENTRIES, "depth": MAX_DEPTH},
        }


def inspect_storage(path):
    """Return bounded metadata accounting without reading or following file data.

    Incomplete/unavailable totals are null; ``observed`` reports only the partial
    sample. Symlinks and special files are counted and excluded, never opened.
    Ancestor directories are opened one component at a time with O_NOFOLLOW and
    remain pinned while walking. A second metadata pass detects observed races;
    it cannot guarantee an atomic view of a concurrently changing filesystem.
    """
    path = Path(path).expanduser()
    if not path.is_absolute():
        # Preserve traversal components until O_NOFOLLOW has checked each one.
        # Path.absolute() normalized them on some supported Python versions.
        path = Path.cwd() / path
    inspection = _Inspection(path)
    descriptors, ancestors = [], []
    available = False
    try:
        parts = path.parts[1:]
        if len(parts) > MAX_ANCESTORS:
            inspection.error(".", "ancestor-limit")
            return inspection.report(False)
        descriptor = os.open(path.anchor, _DIRECTORY_FLAGS)
        descriptors.append(descriptor)
        for part in parts:
            info = _stat_at(descriptor, part)
            if not stat.S_ISDIR(info.st_mode):
                inspection.error(
                    ".",
                    "symlink-root-or-ancestor" if stat.S_ISLNK(info.st_mode) else "not-directory",
                )
                return inspection.report(False)
            next_fd = os.open(part, _DIRECTORY_FLAGS, dir_fd=descriptor)
            descriptors.append(next_fd)
            opened = os.fstat(next_fd)
            if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                inspection.error(".", "ancestor-changed")
                return inspection.report(False)
            ancestors.append((descriptor, part, opened.st_dev, opened.st_ino))
            descriptor = next_fd
        available = True
        inspection.observed["directories"] = 1
        node = _Node(".", os.fstat(descriptor))
        inspection.walk(descriptor, node, ".", 0)
        if not inspection.errors and not inspection.omitted_errors:
            inspection.verify(descriptor, node, ".")
        for parent_fd, name, device, inode in ancestors:
            current = _stat_at(parent_fd, name)
            if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != (
                device,
                inode,
            ):
                inspection.error(".", "ancestor-changed")
    except OSError as error:
        inspection.io_error(".", error)
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)
    return inspection.report(available)
