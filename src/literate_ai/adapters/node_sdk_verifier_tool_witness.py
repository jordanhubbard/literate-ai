"""Detached direct-Node file observation, never provenance or execution authority."""

import hashlib
import os
import stat
import types
from pathlib import PosixPath

from literate_ai._filesystem import capture_directory_ancestries
from literate_ai.adapters.builders.javascript import (
    NodeToolchain,
    _node_toolchain_identity,
)
from literate_ai.projects import PinnedInputClosure, _PinnedInput

_NODE_NAMES = (
    "command",
    "launcher_executable",
    "launcher_digest",
    "runtime_executable",
    "runtime_digest",
    "version",
    "identity",
)
_ENTRY_NAMES = ("path", "boundary", "content", "labels")
_NODE_SLOTS = tuple(vars(NodeToolchain)[name] for name in _NODE_NAMES)
_ENTRY_SLOTS = tuple(vars(_PinnedInput)[name] for name in _ENTRY_NAMES)
_PIN_DICT = vars(PinnedInputClosure)["__dict__"]
_PIN_REQUIRE = PinnedInputClosure.require_unchanged
_PIN_KEYS = frozenset(
    {
        "maximum_files",
        "maximum_file_bytes",
        "maximum_total_bytes",
        "_entries",
        "_total_bytes",
        "_labels",
    }
)
_LABELS = ("node-verifier-launcher", "node-verifier-runtime")
MAXIMUM_NODE_OBSERVATION_BYTES = 1024 * 1024
_NATIVE_LSTAT = os.lstat
_ABSENT = object()
_NAMESPACES = {
    cls: (
        type.__getattribute__(cls, "__mro__"),
        tuple(
            (base, tuple(type.__getattribute__(base, "__dict__").items()))
            for base in type.__getattribute__(cls, "__mro__")
        ),
    )
    for cls in (NodeToolchain, PinnedInputClosure, _PinnedInput, PosixPath)
}


def _require_namespace(cls):
    mro, namespaces = _NAMESPACES[cls]
    if type.__getattribute__(cls, "__mro__") is not mro:
        raise ValueError("original Node observation storage changed")
    for base, original in namespaces:
        current = type.__getattribute__(base, "__dict__")
        if len(current) != len(original) or any(
            current.get(name, _ABSENT) is not value for name, value in original
        ):
            raise ValueError("original Node observation storage changed")


def _node_values(node):
    if type(node) is not NodeToolchain:
        raise TypeError("Node observation requires original typed tool metadata")
    _require_namespace(NodeToolchain)
    return tuple(
        types.MemberDescriptorType.__get__(slot, node, NodeToolchain)
        for slot in _NODE_SLOTS
    )


def _file_stamp(value):
    if not stat.S_ISREG(value.st_mode):
        raise ValueError("original Node observation requires a regular file")
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def capture_detached_node_tool_witness(tools, node):
    """Observe one original direct tool across full entry/exit byte checks.

    The returned sticky guard retains metadata, paths and original POSIX stamps
    only. It never reopens a closure, reads content, calls owner code, grants
    execution, or establishes runtime-phase membership. The original enrolled
    capture/operation must separately own that membership and its final clocks.
    """
    succeeded = False
    try:
        if os.name != "posix" or type(tools) is not PinnedInputClosure:
            raise TypeError("detached Node observation requires original POSIX inputs")
        _require_namespace(PinnedInputClosure)
        _require_namespace(_PinnedInput)
        _require_namespace(PosixPath)
        values = _node_values(node)
        (
            command,
            launcher,
            launcher_digest,
            runtime,
            runtime_digest,
            version,
            identity,
        ) = values
        if (
            type(command) is not tuple
            or len(command) != 1
            or any(
                type(value) is not str or not 1 <= len(value) <= 4096
                for value in (*command, *values[1:])
            )
            or sum(len(value.encode("utf-8")) for value in (*command, *values[1:]))
            > 16384
            or len(version) > 256
            or command[0] != launcher
            or runtime != launcher
            or runtime_digest != launcher_digest
            or len(launcher_digest) != 71
            or len(identity) != 71
            or _node_toolchain_identity(
                command=command,
                launcher_executable=launcher,
                launcher_digest=launcher_digest,
                runtime_executable=runtime,
                runtime_digest=runtime_digest,
                version=version,
            )
            != identity
        ):
            raise ValueError(
                "detached Node observation requires its exact direct preimage"
            )
        data = types.GetSetDescriptorType.__get__(_PIN_DICT, tools, PinnedInputClosure)
        if (
            type(data) is not dict
            or len(data) != len(_PIN_KEYS)
            or any(type(name) is not str for name in data)
            or frozenset(data) != _PIN_KEYS
        ):
            raise ValueError("Node input storage has substituted members")
        for name, maximum in (
            ("maximum_files", 2),
            ("maximum_file_bytes", 512 * 1024**2),
            ("maximum_total_bytes", 512 * 1024**2),
        ):
            value = dict.__getitem__(data, name)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError("Node input bounds differ from its capture profile")
        entries, labels = data["_entries"], data["_labels"]
        if (
            type(entries) is not dict
            or len(entries) != 1
            or type(labels) is not dict
            or len(labels) != 2
            or any(type(name) is not str for name in labels)
        ):
            raise ValueError("Node observation requires one original tool entry")
        key, entry = next(iter(dict.items(entries)))
        if type(entry) is not _PinnedInput:
            raise TypeError("Node observation requires original pinned entry storage")
        path, boundary, content, names = (
            types.MemberDescriptorType.__get__(slot, entry, _PinnedInput)
            for slot in _ENTRY_SLOTS
        )
        if (
            type(path) is not PosixPath
            or type(boundary) is not PosixPath
            or str(path) != launcher
            or boundary != path.parent
            or type(key) is not tuple
            or len(key) != 2
            or any(type(value) is not PosixPath for value in key)
            or key != (path, boundary)
            or type(content) is not bytes
            or not 1 <= len(content) <= 512 * 1024**2
            or type(names) is not tuple
            or len(names) != 2
            or any(type(name) is not str for name in names)
            or names != _LABELS
            or set(labels) != set(_LABELS)
            or type(data["_total_bytes"]) is not int
            or data["_total_bytes"] != len(content)
            or len(content) > data["maximum_file_bytes"]
            or len(content) > data["maximum_total_bytes"]
            or "sha256:" + hashlib.sha256(content).hexdigest() != launcher_digest
        ):
            raise ValueError(
                "Node observation differs from original tool bytes or roles"
            )
        for label in _LABELS:
            row = labels[label]
            if (
                type(row) is not tuple
                or len(row) != 3
                or any(type(value) is not PosixPath for value in row[:2])
                or row[:2] != (path, boundary)
                or row[2] is not content
            ):
                raise ValueError("Node tool role differs from original pinned storage")
        _PIN_REQUIRE(tools)
        # Reuse the original ancestry owner for capture bracketing. Continuation
        # retains only detached strings/numbers and the original native syscall.
        if len(path.parts) > 65:
            raise ValueError("Node observation ancestry exceeds its metadata bound")
        directories_current = capture_directory_ancestries((path.parent,))
        reader, stamp_values, node_values = _NATIVE_LSTAT, _file_stamp, _node_values
        parents = (*reversed(path.parent.parents), path.parent)
        if len(parents) > 64:
            raise ValueError("Node observation ancestry exceeds its metadata bound")
        ancestry = []
        metadata_bytes = sum(
            len(value.encode("utf-8")) for value in (*command, *values[1:])
        )
        for parent in parents:
            name = str(parent)
            metadata_bytes += len(name.encode("utf-8"))
            if metadata_bytes > 65536:
                raise ValueError("Node observation exceeds its metadata bound")
            observed = reader(name)
            if not stat.S_ISDIR(observed.st_mode) or observed.st_ino == 0:
                raise ValueError(
                    "Node observation ancestry is not original regular storage"
                )
            ancestry.append(
                (name, (observed.st_dev, observed.st_ino, observed.st_mode))
            )
        ancestry = tuple(ancestry)
        filename = str(path)
        original_stamp = stamp_values(reader(filename))
        failed = False

        def require_original():
            nonlocal failed
            if failed:
                raise ValueError("detached Node observation already failed")
            try:
                current = node_values(node)
                if any(a is not b for a, b in zip(current, values, strict=True)):
                    raise ValueError("original Node invocation metadata changed")
                for name, expected in ancestry:
                    observed = reader(name)
                    if (observed.st_dev, observed.st_ino, observed.st_mode) != expected:
                        raise ValueError("original Node ancestry changed")
                if stamp_values(reader(filename)) != original_stamp:
                    raise ValueError("original Node file changed")
                for name, expected in ancestry:
                    observed = reader(name)
                    if (observed.st_dev, observed.st_ino, observed.st_mode) != expected:
                        raise ValueError("original Node ancestry changed")
            except BaseException:
                failed = True
                raise

        _PIN_REQUIRE(tools)
        directories_current()
        require_original()
        succeeded = True
        return require_original
    finally:
        tools = data = entries = labels = key = entry = content = row = None
        path = boundary = names = directories_current = parents = None
        if not succeeded:
            node = values = ancestry = filename = original_stamp = None
