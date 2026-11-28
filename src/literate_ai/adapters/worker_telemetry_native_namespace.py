"""Explicit absent-only private native-provider bookkeeping preparation.

This creates no provider, samples, tool install or execution authority. Historical
markers are comparison inputs only; original build/probe witnesses are separate.
"""

from __future__ import annotations

import os
import secrets
import stat
import sys
from contextlib import ExitStack, contextmanager
from pathlib import Path

from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes

from .user_paths import resolve_user_paths
from .worker_telemetry_namespace import (
    _parent,
    node_identity,
    node_wire,
    open_file,
    private,
    write_at,
)
from .worker_telemetry_wire_v2 import WorkerTelemetryWireError, _decode

_NAMES = {
    "build": "worker-telemetry-native-builds",
    "provider": "worker-telemetry-native-providers",
}
_SCHEMA = "literate-ai/private-worker-telemetry-native-namespace@1"


def _refuse():
    raise WorkerTelemetryWireError("worker_telemetry.native_namespace_unavailable")


def _root(role):
    if (
        os.name != "posix"
        or not sys.platform.startswith("freebsd")
        or role not in _NAMES
    ):
        _refuse()
    return Path(resolve_user_paths().state_root) / _NAMES[role]


def initialize_native_provider_namespaces():
    """Explicit operator command; neither existing root is adopted or edited.

    Both absences are checked before creation. A subsequent failure preserves
    the partial owned namespace as evidence; it is never silently resumed.
    """
    with ExitStack() as stack:
        roots = tuple((role, _root(role)) for role in _NAMES)
        parent, parent_node = _parent(roots[0][1], stack)
        for _, root in roots:
            try:
                os.stat(root.name, dir_fd=parent, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError("native provider namespace exists")
        result = {}
        records = []
        for role, root in roots:
            if node_identity(os.fstat(parent)) != node_identity(
                parent_node
            ) or node_identity(root.parent.lstat()) != node_identity(parent_node):
                _refuse()
            os.mkdir(root.name, 0o700, dir_fd=parent)
            descriptor = os.open(
                root.name,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=parent,
            )
            stack.callback(os.close, descriptor)
            private(os.fstat(descriptor), directory=True)
            node = os.fstat(descriptor)
            lock_fd = open_file(descriptor, ".lock", create=True)
            stack.callback(os.close, lock_fd)
            marker = canonical_json_bytes(
                {
                    "schema": _SCHEMA,
                    "role": role,
                    "root": node_wire(node),
                    "parent": node_wire(parent_node),
                    "lock": node_wire(os.fstat(lock_fd)),
                    "nonce": secrets.token_hex(32),
                    "maximum_directories": 32 if role == "build" else 64,
                    "directory_metadata_charge_bytes": 16 * 1024,
                }
            )
            fd = open_file(descriptor, ".owner", create=True)
            stack.callback(os.close, fd)
            write_at(fd, marker, 0)
            os.fsync(fd)
            os.fsync(lock_fd)
            os.fsync(descriptor)
            if (
                node_wire(root.lstat()) != node_wire(node)
                or os.pread(fd, 16385, 0) != marker
            ):
                _refuse()
            records.append((root, descriptor, node, fd, os.fstat(fd), marker, lock_fd))
            result[role] = canonical_identity(_decode(marker, 16384)).to_dict()
        os.fsync(parent)
        if node_identity(os.fstat(parent)) != node_identity(parent_node):
            _refuse()
        for root, descriptor, node, fd, marker_node, marker, lock_fd in records:
            if (
                node_wire(root.parent.lstat()) != node_wire(parent_node)
                or node_wire(root.lstat()) != node_wire(node)
                or node_wire(os.fstat(descriptor)) != node_wire(node)
            ):
                _refuse()
            for name, held, expected, size in (
                (".owner", fd, marker_node, len(marker)),
                (".lock", lock_fd, os.fstat(lock_fd), 0),
            ):
                named = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
                current = os.fstat(held)
                private(current)
                private(named)
                if (
                    node_wire(current) != node_wire(expected)
                    or node_wire(named) != node_wire(expected)
                    or current.st_size != size
                    or named.st_size != size
                ):
                    _refuse()
            if os.pread(fd, 16385, 0) != marker:
                _refuse()
            names = set()
            with os.scandir(descriptor) as entries:
                for entry in entries:
                    if len(names) >= 2:
                        _refuse()
                    names.add(entry.name)
            if names != {".owner", ".lock"}:
                _refuse()
        return result


@contextmanager
def native_provider_namespace(role, *, writing=False):
    """Attest a preexisting explicitly prepared root; creates nothing."""
    root = _root(role)
    creator = os.getpid()
    with ExitStack() as stack:
        parent, parent_node = _parent(root, stack)
        descriptor = os.open(
            root.name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent,
        )
        stack.callback(os.close, descriptor)
        node = os.fstat(descriptor)
        private(node, directory=True)
        marker_fd = os.open(
            ".owner",
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
            dir_fd=descriptor,
        )
        stack.callback(os.close, marker_fd)
        marker_node = os.fstat(marker_fd)
        private(marker_node)
        if not 0 < marker_node.st_size <= 16384:
            _refuse()
        raw = os.pread(marker_fd, 16385, 0)
        value = _decode(raw, 16384)
        if (
            type(value) is not dict
            or set(value)
            != {
                "schema",
                "role",
                "root",
                "parent",
                "lock",
                "nonce",
                "maximum_directories",
                "directory_metadata_charge_bytes",
            }
            or value["schema"] != _SCHEMA
            or value["role"] != role
            or value["root"] != node_wire(node)
            or value["parent"] != node_wire(parent_node)
            or type(value["nonce"]) is not str
            or len(value["nonce"]) != 64
            or any(c not in "0123456789abcdef" for c in value["nonce"])
            or type(value["maximum_directories"]) is not int
            or value["maximum_directories"] != (32 if role == "build" else 64)
            or type(value["directory_metadata_charge_bytes"]) is not int
            or value["directory_metadata_charge_bytes"] != 16 * 1024
            or canonical_json_bytes(value) != raw
        ):
            _refuse()

        lock_fd = open_file(descriptor, ".lock")
        stack.callback(os.close, lock_fd)
        if writing:
            import fcntl

            try:
                fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                _refuse()
            stack.callback(fcntl.flock, lock_fd, fcntl.LOCK_UN)

        def current():
            if (
                creator != os.getpid()
                or node_wire(os.fstat(parent)) != value["parent"]
                or node_wire(root.parent.lstat()) != value["parent"]
                or node_wire(os.fstat(descriptor)) != value["root"]
                or node_wire(root.lstat()) != value["root"]
            ):
                _refuse()
            held = os.fstat(marker_fd)
            named = os.stat(".owner", dir_fd=descriptor, follow_symlinks=False)
            private(held)
            private(named)
            if (
                node_wire(held) != node_wire(marker_node)
                or node_wire(named) != node_wire(marker_node)
                or held.st_size != len(raw)
                or named.st_size != len(raw)
                or os.pread(marker_fd, 16385, 0) != raw
            ):
                _refuse()
            held_lock = os.fstat(lock_fd)
            named_lock = os.stat(".lock", dir_fd=descriptor, follow_symlinks=False)
            private(held_lock)
            private(named_lock)
            if (
                node_wire(held_lock) != value["lock"]
                or node_wire(named_lock) != value["lock"]
                or held_lock.st_size != 0
                or named_lock.st_size != 0
            ):
                _refuse()
            # Every child, including retained failed stages, consumes a bounded
            # metadata slot. No age-based deletion, auto adoption or cleanup.
            count = 0
            with os.scandir(descriptor) as entries:
                for entry in entries:
                    if entry.name in {".owner", ".lock"}:
                        continue
                    if count >= value["maximum_directories"]:
                        _refuse()
                    child = entry.stat(follow_symlinks=False)
                    if (
                        not stat.S_ISDIR(child.st_mode)
                        or child.st_uid != os.geteuid()
                        or stat.S_IMODE(child.st_mode) != 0o700
                    ):
                        _refuse()
                    count += 1
            return count

        current()
        yield (
            root,
            descriptor,
            canonical_identity(value),
            current,
            value["maximum_directories"],
        )
        current()
