"""Freeze a conservative Niri include graph without flattening its merge order.

Only include path tokens change. Keeping nodes in their original files preserves
Niri's per-file duplicate checks, positional merges and repeated includes. This
scanner establishes file ownership; the selected Niri still validates KDL.
"""

import json
import os
import posixpath
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from .native_build import _regular_file
from .setup import _kdl_string
from .storage import digest

MAX_FILES = 128
MAX_FILE_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024
MAX_INCLUDE_NODES = 512
MAX_NODE_DEPTH = 64
# The pinned Niri rejects the tenth nested include.
MAX_DEPTH = 9
_NEWLINES = "\r\n\f\v\x85\u2028\u2029"
_OWNED_NAME = re.compile(r"(?:config\.kdl|config/[0-9]{4}\.kdl)")
_BLOCK_MARKER = re.compile(r"/\*|\*/")
_RAW_START = re.compile(r'r(\#*)"')


@dataclass(frozen=True)
class _Token:
    text: str
    start: int
    end: int
    kind: str


@dataclass(frozen=True)
class _Include:
    path: str
    start: int
    end: int
    optional: bool


def _tokens(source):
    """Retain character spans while comments, strings and continuations stay opaque."""
    result, offset = [], 1 if source.startswith("\ufeff") else 0
    while offset < len(source):
        start = offset
        char = source[offset]
        if char in _NEWLINES:
            offset += 2 if source[offset : offset + 2] == "\r\n" else 1
            result.append(_Token("\n", start, offset, "punct"))
        elif char.isspace() or char == "\ufeff":
            offset += 1
        elif source.startswith("//", offset):
            offset += 2
            while offset < len(source) and source[offset] not in _NEWLINES:
                offset += 1
        elif source.startswith("/*", offset):
            offset += 2
            depth = 1
            while depth:
                match = _BLOCK_MARKER.search(source, offset)
                if match is None:
                    raise ValueError("Unterminated config block comment")
                depth += 1 if match.group() == "/*" else -1
                offset = match.end()
        elif char == "\\":
            # An explicit continuation may contain horizontal whitespace and a
            # line comment. Other forms are refused rather than guessed.
            offset += 1
            while (
                offset < len(source)
                and (source[offset].isspace() or source[offset] == "\ufeff")
                and source[offset] not in _NEWLINES
            ):
                offset += 1
            if source.startswith("//", offset):
                offset += 2
                while offset < len(source) and source[offset] not in _NEWLINES:
                    offset += 1
            if offset == len(source) or source[offset] not in _NEWLINES:
                raise ValueError("Unsupported config line continuation")
            offset += 2 if source[offset : offset + 2] == "\r\n" else 1
        elif match := _RAW_START.match(source, offset):
            ending = '"' + match[1]
            content = match.end()
            end = source.find(ending, content)
            if end == -1:
                raise ValueError("Unterminated raw config string")
            offset = end + len(ending)
            result.append(_Token(source[start:offset], start, offset, "string"))
        elif char == '"':
            offset += 1
            while offset < len(source):
                if source[offset] == "\\":
                    offset += 2
                elif source[offset] == '"':
                    offset += 1
                    break
                else:
                    offset += 1
            else:
                raise ValueError("Unterminated config string")
            result.append(_Token(source[start:offset], start, offset, "string"))
        elif source.startswith("/-", offset):
            offset += 2
            result.append(_Token("/-", start, offset, "punct"))
        elif char in "{};=()":
            offset += 1
            result.append(_Token(char, start, offset, "punct"))
        else:
            while (
                offset < len(source)
                and not source[offset].isspace()
                and source[offset] not in '{};=()"/\\\ufeff'
            ):
                offset += 1
            if offset == start:
                raise ValueError("Unsupported config token")
            result.append(_Token(source[start:offset], start, offset, "bare"))
    return result


def _name(token):
    return _kdl_string(token.text) if token.kind == "string" else token.text


def _include(header):
    arguments, properties, index = [], {}, 0
    while index < len(header):
        ignored = header[index].text == "/-"
        index += int(ignored)
        if index >= len(header) or header[index].kind not in ("string", "bare"):
            raise ValueError("Unsupported include argument or annotation")
        value = header[index]
        index += 1
        if index < len(header) and header[index].text == "=":
            index += 1
            if index >= len(header) or header[index].kind not in ("string", "bare"):
                raise ValueError("Unsupported include property")
            assigned = header[index]
            index += 1
            if not ignored:
                key = _name(value)
                if key in properties:
                    raise ValueError("Repeated include property")
                properties[key] = assigned
        elif not ignored:
            arguments.append(value)
    if len(arguments) != 1 or arguments[0].kind != "string":
        raise ValueError("Includes require exactly one quoted or raw string path")
    if set(properties) - {"optional"}:
        raise ValueError("Unsupported include property")
    optional = properties.get("optional")
    if optional and (optional.kind != "bare" or optional.text not in ("true", "false")):
        raise ValueError("Include optional must be true or false")
    path = _name(arguments[0])
    if not path or any(char in path for char in "\x00*?[]"):
        raise ValueError("Include paths must be nonempty literal filenames without glob characters")
    if path.endswith("/") or path.rsplit("/", 1)[-1] in (".", ".."):
        raise ValueError("Include paths must end in a filename, not a directory component")
    return _Include(
        path, arguments[0].start, arguments[0].end, bool(optional and optional.text == "true")
    )


def _includes(data):
    tokens = _tokens(data.decode("utf-8"))
    index, found = 0, []

    def nodes(depth, inactive=False):
        nonlocal index
        if depth > MAX_NODE_DEPTH:
            raise ValueError("Config node nesting exceeds its limit")
        active_count = 0
        while index < len(tokens):
            if tokens[index].text in ("\n", ";"):
                index += 1
                continue
            if tokens[index].text == "}":
                if depth == 0:
                    raise ValueError("Unexpected closing config brace")
                index += 1
                return active_count
            ignored = inactive or tokens[index].text == "/-"
            if tokens[index].text == "/-":
                index += 1
            if index == len(tokens):
                raise ValueError("Incomplete slash-dash config node")
            if tokens[index].text == "(":
                if not ignored:
                    raise ValueError(
                        "Config node type annotations are unsupported for include snapshots"
                    )
                while index < len(tokens) and tokens[index].text != ")":
                    index += 1
                index += 1
            if index >= len(tokens) or tokens[index].kind not in ("bare", "string"):
                raise ValueError("Unsupported config node syntax")
            name = _name(tokens[index])
            index += 1
            header = []
            while index < len(tokens) and tokens[index].text not in ("\n", ";", "{", "}"):
                header.append(tokens[index])
                index += 1
            child_count = 0
            if index < len(tokens) and tokens[index].text == "{":
                index += 1
                ignored_children = bool(header and header[-1].text == "/-")
                if ignored_children:
                    header.pop()
                child_count = nodes(depth + 1, ignored or ignored_children)
                if index < len(tokens) and tokens[index].text not in ("\n", ";", "}"):
                    raise ValueError("Unsupported config content after child nodes")
            if not ignored:
                active_count += 1
                if name == "include":
                    if depth or child_count:
                        raise ValueError("Includes must be top-level nodes without active children")
                    found.append(_include(header))
            if index < len(tokens) and tokens[index].text in ("\n", ";"):
                index += 1
        if depth:
            raise ValueError("Unclosed config child block")
        return active_count

    nodes(0)
    return found


def require_self_contained(data):
    """Use the same lexer for legacy single-file bundles and include snapshots."""
    if _includes(data):
        raise ValueError(
            "Native session bundles require a self-contained config with no active include nodes"
        )


def _safe_path(path):
    path = Path(path).absolute()
    # Check before normalizing '..': traversing a symlink and then its parent
    # has different filesystem semantics from a lexical path simplification.
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f"Config snapshot paths must not be symlinks: {part}")
    if ".." in path.parts:
        # Resolving lexically would turn "missing/../existing" into an existing
        # file even though the original OS lookup fails. Inspect every original
        # prefix: older pathlib.resolve() also collapses regular-file/.. .
        try:
            for parent in path.parents:
                if not stat.S_ISDIR(parent.stat().st_mode):
                    raise ValueError("Config parent traversal requires existing directories")
        except (FileNotFoundError, NotADirectoryError) as error:
            raise ValueError("Config parent traversal requires existing directories") from error
    return Path(os.path.abspath(path))


def _read(path):
    with _regular_file(path) as stream:
        before = os.fstat(stream.fileno())
        data = stream.read(MAX_FILE_BYTES + 1)
        after = os.fstat(stream.fileno())
    current = path.stat()

    def identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

    if identity(before) != identity(after) or identity(after) != identity(current):
        raise ValueError(f"Config changed while reading: {path}")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Config snapshot file exceeds its size limit")
    return data, stat.S_IMODE(current.st_mode)


def _source_include(parent, value):
    path = Path(value)
    if path.parts and path.parts[0] == "~":
        path = Path.home().joinpath(*path.parts[1:])
    elif not path.is_absolute():
        path = parent / path
    return _safe_path(path)


def _fingerprint(root_file, files):
    value = {"root": root_file, "files": {name: digest(data) for name, data in files.items()}}
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def inspect_snapshot(root_file, files):
    """Prove every active include belongs to the exact, reachable owned graph."""
    if (
        root_file != "config.kdl"
        or not isinstance(files, dict)
        or not files
        or len(files) > MAX_FILES
    ):
        raise ValueError("Invalid config snapshot root or file count")
    if any(
        not isinstance(name, str)
        or not _OWNED_NAME.fullmatch(name)
        or not isinstance(data, bytes)
        or len(data) > MAX_FILE_BYTES
        for name, data in files.items()
    ):
        raise ValueError("Invalid config snapshot file name, bytes or size")
    if root_file not in files or sum(map(len, files.values())) > MAX_TOTAL_BYTES:
        raise ValueError("Config snapshot root is missing or total size exceeds its limit")
    graph, edges = {}, 0
    for name, data in files.items():
        children = []
        for include in _includes(data):
            if include.path.startswith(("/", "~")) or ".." in include.path.split("/"):
                raise ValueError("Config snapshot include escapes its owned files")
            child = posixpath.normpath(posixpath.join(posixpath.dirname(name), include.path))
            if child not in files:
                raise ValueError("Config snapshot include is not an owned file")
            children.append(child)
        edges += len(children)
        if edges > MAX_INCLUDE_NODES:
            raise ValueError("Too many config include nodes")
        graph[name] = children
    reached, heights = set(), {}

    def visit(name, active):
        if name in active:
            raise ValueError("Config include cycle")
        reached.add(name)
        if name not in heights:
            heights[name] = max(
                (1 + visit(child, active | {name}) for child in graph[name]), default=0
            )
        return heights[name]

    if visit(root_file, set()) > MAX_DEPTH:
        raise ValueError("Config snapshot exceeds Niri's include depth limit")
    if reached != files.keys():
        raise ValueError("Config snapshot contains unreachable files")
    return _fingerprint(root_file, files)


def snapshot(path, *, overrides=None):
    """Read an include graph and rewrite paths into an immutable owned snapshot."""
    root = _safe_path(Path(path).expanduser())
    overrides = (
        {}
        if overrides is None
        else {_safe_path(Path(name).expanduser()): data for name, data in overrides.items()}
    )
    if any(
        not isinstance(data, bytes) or len(data) > MAX_FILE_BYTES for data in overrides.values()
    ):
        raise ValueError("Config snapshot overrides require bounded file bytes")
    names, files, records, observed = {root: "config.kdl"}, {}, {}, []
    total, edge_count = 0, 0

    def visit(path, active, optional=False):
        nonlocal total, edge_count
        if path in active:
            raise ValueError("Config include cycle")
        if path in records:
            if records[path] is None and not optional:
                raise ValueError(f"Required config include is missing: {path}")
            return names[path]
        if len(names) > MAX_FILES:
            raise ValueError("Too many files in config snapshot")
        try:
            original, mode = _read(path)
        except FileNotFoundError:
            if not optional and path not in overrides:
                raise ValueError(f"Required config include is missing: {path}") from None
            original, mode = None, None
        data = overrides.get(path, original)
        records[path] = data
        observed.append(
            {
                "logical": str(path),
                "target": str(path),
                "before": original,
                "after": original,
                "mode": mode if mode is not None else 0o600,
                "regular_only": True,
                **({"expected_mode": mode} if mode is not None else {}),
            }
        )
        if data is None:
            files[names[path]] = (
                b"// Optional include was absent when this snapshot was prepared.\n"
            )
            return names[path]
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ValueError("Config snapshot total size exceeds its limit")
        includes = _includes(data)
        edge_count += len(includes)
        if edge_count > MAX_INCLUDE_NODES:
            raise ValueError("Too many config include nodes")
        if len(active) > MAX_DEPTH:
            raise ValueError("Config snapshot exceeds Niri's include depth limit")
        replacements = []
        for include in includes:
            child = _source_include(path.parent, include.path)
            if child not in names:
                names[child] = f"config/{len(names):04d}.kdl"
            destination = visit(child, active | {path}, include.optional)
            relative = posixpath.relpath(destination, posixpath.dirname(names[path]) or ".")
            replacements.append((include.start, include.end, json.dumps(relative)))
        text = data.decode("utf-8")
        for start, end, replacement in reversed(replacements):
            text = text[:start] + replacement + text[end:]
        files[names[path]] = text.encode("utf-8")
        return names[path]

    visit(root, set())
    files = dict(sorted(files.items()))
    fingerprint = inspect_snapshot("config.kdl", files)
    return {
        "root": "config.kdl",
        "files": files,
        "observed": observed,
        "fingerprint": fingerprint,
        "missing_optional": [str(path) for path, data in records.items() if data is None],
    }
