"""Explicitly initialized observation custody; queries never recreate lost state."""

from __future__ import annotations

import os
import secrets
import stat
from contextlib import ExitStack, contextmanager
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.contracts.identity import canonical_json_bytes

from .action_dispatch_wire import record_identity
from .repository_refresh import _local_identity_wire
from .user_paths import resolve_user_paths
from .worker_telemetry_wire_v2 import WorkerTelemetryWireError, _decode

MAX_SCOPE_LEDGERS = 64
ALLOCATION_RECORD_BYTES = 1024
ALLOCATION_HEADER_BYTES = 32
ALLOCATION_BYTES = ALLOCATION_HEADER_BYTES + MAX_SCOPE_LEDGERS * ALLOCATION_RECORD_BYTES
MAX_NAMESPACE_MARKER_BYTES = 16 * 1024
MAX_OWNER_CLAIMS = 64
CLAIM_RECORD_BYTES = 512
CLAIMS_HEADER_BYTES = 32
CLAIMS_BYTES = CLAIMS_HEADER_BYTES + MAX_OWNER_CLAIMS * CLAIM_RECORD_BYTES
POISON_BYTES = 65536
# Zero-byte locks still consume filesystem metadata. Reserve a conservative
# 16KiB bookkeeping charge per inode in addition to their explicit finite count;
# this is accounting, not a promise to sandbox arbitrary filesystem allocation.
CLAIM_LOCK_METADATA_CHARGE_BYTES = MAX_OWNER_CLAIMS * 16 * 1024
_SCHEMA = "literate-ai/private-worker-telemetry-namespace@3"


def claim_lock_name(index):
    if type(index) is not int or not 0 <= index < MAX_OWNER_CLAIMS:
        refuse("announcement_unavailable")
    return f".claim-lock-{index:02d}"


def refuse(code):
    raise WorkerTelemetryWireError("worker_telemetry." + code)


def private(metadata, *, directory=False):
    if (
        (
            not stat.S_ISDIR(metadata.st_mode)
            if directory
            else not stat.S_ISREG(metadata.st_mode)
        )
        or metadata.st_uid != os.geteuid()
        or stat.S_IMODE(metadata.st_mode) & 0o077
        or (not directory and metadata.st_nlink != 1)
    ):
        refuse("bookkeeping_unsafe")


def node_identity(node):
    return node.st_dev, node.st_ino, node.st_mode, node.st_uid, node.st_gid


def node_wire(node):
    return _local_identity_wire(node_identity(node))


def write_at(descriptor, raw, offset):
    while raw:
        count = os.pwrite(descriptor, raw, offset)
        if count <= 0:
            refuse("bookkeeping_unavailable")
        raw = raw[count:]
        offset += count


def open_file(directory, name, *, create=False):
    flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
    if create:
        flags |= os.O_CREAT | os.O_EXCL
    descriptor = os.open(name, flags, 0o600, dir_fd=directory)
    try:
        private(os.fstat(descriptor))
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def require_file(directory, name, descriptor, *, expected, size):
    held = os.fstat(descriptor)
    named = os.stat(name, dir_fd=directory, follow_symlinks=False)
    private(held)
    private(named)
    if (
        node_wire(held) != expected
        or node_wire(named) != expected
        or held.st_size != size
        or named.st_size != size
    ):
        refuse("bookkeeping_changed")


def _root():
    if os.name != "posix":
        refuse("native_key_custody_unsupported")
    return Path(resolve_user_paths().state_root) / "worker-telemetry"


def _parent(root, stack):
    require_safe_directory(root.parent)
    node = root.parent.lstat()
    if node.st_uid != os.geteuid() or stat.S_IMODE(node.st_mode) & 0o022:
        refuse("bookkeeping_unsafe")
    descriptor = os.open(
        root.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    )
    stack.callback(os.close, descriptor)
    if node_identity(os.fstat(descriptor)) != node_identity(node):
        refuse("bookkeeping_changed")
    return descriptor, node


def initialize_worker_telemetry_namespace():
    """Explicit operator setup only; always mint a new namespace identity.

    Existing or partially initialized roots refuse without edits or cleanup. Lost
    state requires a fresh identity in private configuration/registration/scope;
    old requests can never authorize a newly initialized empty namespace.
    """
    root = _root()
    with ExitStack() as stack:
        parent, parent_node = _parent(root, stack)
        os.mkdir(root.name, 0o700, dir_fd=parent)  # Exclusive; never adopt an old root.
        directory = os.open(
            root.name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent,
        )
        stack.callback(os.close, directory)
        private(os.fstat(directory), directory=True)
        lock = open_file(directory, ".lock", create=True)
        stack.callback(os.close, lock)
        allocation = open_file(directory, ".allocated", create=True)
        stack.callback(os.close, allocation)
        nonce = secrets.token_bytes(ALLOCATION_HEADER_BYTES)
        write_at(
            allocation, nonce + bytes(ALLOCATION_BYTES - ALLOCATION_HEADER_BYTES), 0
        )
        os.fsync(allocation)
        os.fsync(lock)
        claim_lock_nodes = []
        for index in range(MAX_OWNER_CLAIMS):
            # Initialization creates the COMPLETE fixed frontier before use.
            # Close each FD here; keeping 64 per nested namespace context can
            # exhaust otherwise valid host descriptor limits.
            descriptor = open_file(directory, claim_lock_name(index), create=True)
            try:
                claim_lock_nodes.append(node_wire(os.fstat(descriptor)))
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        claims = open_file(directory, ".claims", create=True)
        stack.callback(os.close, claims)
        poison = open_file(directory, ".poison", create=True)
        stack.callback(os.close, poison)
        # Explicit initialization reserves all later announcement storage. No
        # action or query creates/grows these files or evicts historical claims.
        write_at(claims, nonce + bytes(CLAIMS_BYTES - CLAIMS_HEADER_BYTES), 0)
        write_at(poison, bytes(POISON_BYTES), 0)
        for descriptor in (claims, poison):
            os.fsync(descriptor)
        os.mkdir("live", 0o700, dir_fd=directory)
        live = os.open(
            "live",
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=directory,
        )
        stack.callback(os.close, live)
        marker = canonical_json_bytes(
            {
                "schema": _SCHEMA,
                "allocation_nonce": nonce.hex(),
                "root": node_wire(os.fstat(directory)),
                "parent": node_wire(parent_node),
                "lock": node_wire(os.fstat(lock)),
                "allocation": node_wire(os.fstat(allocation)),
                "live": node_wire(os.fstat(live)),
                "claim_locks": claim_lock_nodes,
                "claim_lock_metadata_charge_bytes": CLAIM_LOCK_METADATA_CHARGE_BYTES,
                "claims": node_wire(os.fstat(claims)),
                "poison": node_wire(os.fstat(poison)),
            }
        )
        if len(marker) > MAX_NAMESPACE_MARKER_BYTES:
            refuse("bookkeeping_limit")
        marker_fd = open_file(directory, ".owner", create=True)
        stack.callback(os.close, marker_fd)
        write_at(marker_fd, marker, 0)
        os.fsync(marker_fd)
        os.fsync(live)
        os.fsync(directory)
        os.fsync(parent)
        if node_identity(root.lstat()) != node_identity(
            os.fstat(directory)
        ) or node_identity(root.parent.lstat()) != node_identity(parent_node):
            refuse("bookkeeping_changed")
        return record_identity(marker)


@contextmanager
def open_worker_telemetry_namespace(configuration):
    root = configuration.observation_root
    if root != _root() or configuration.observation_namespace_identity is None:
        refuse("observation_namespace_mismatch")
    with ExitStack() as stack:
        parent, parent_node = _parent(root, stack)
        directory = os.open(
            root.name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=parent,
        )
        stack.callback(os.close, directory)
        root_node = os.fstat(directory)
        private(root_node, directory=True)
        marker_fd = open_file(directory, ".owner")
        stack.callback(os.close, marker_fd)
        marker_node = os.fstat(marker_fd)
        if not 1 <= marker_node.st_size <= MAX_NAMESPACE_MARKER_BYTES:
            refuse("bookkeeping_foreign")
        marker = os.pread(marker_fd, MAX_NAMESPACE_MARKER_BYTES + 1, 0)
        if record_identity(marker) != configuration.observation_namespace_identity:
            refuse("bookkeeping_foreign")
        value = _decode(marker, MAX_NAMESPACE_MARKER_BYTES)
        if (
            not isinstance(value, dict)
            or set(value)
            != {
                "schema",
                "allocation_nonce",
                "root",
                "parent",
                "lock",
                "allocation",
                "live",
                "claim_locks",
                "claim_lock_metadata_charge_bytes",
                "claims",
                "poison",
            }
            or value["schema"] != _SCHEMA
            or type(value["claim_locks"]) is not list
            or len(value["claim_locks"]) != MAX_OWNER_CLAIMS
            or type(value["claim_lock_metadata_charge_bytes"]) is not int
            or value["claim_lock_metadata_charge_bytes"]
            != CLAIM_LOCK_METADATA_CHARGE_BYTES
        ):
            refuse("bookkeeping_foreign")
        nonce = value["allocation_nonce"]
        if (
            not isinstance(nonce, str)
            or len(nonce) != 64
            or any(c not in "0123456789abcdef" for c in nonce)
        ):
            refuse("bookkeeping_foreign")
        lock = open_file(directory, ".lock")
        stack.callback(os.close, lock)
        allocation = open_file(directory, ".allocated")
        stack.callback(os.close, allocation)
        claims = open_file(directory, ".claims")
        stack.callback(os.close, claims)
        poison = open_file(directory, ".poison")
        stack.callback(os.close, poison)
        live = os.open(
            "live",
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
            dir_fd=directory,
        )
        stack.callback(os.close, live)
        with os.scandir(directory) as entries:
            for count, entry in enumerate(entries):
                if (
                    count >= MAX_SCOPE_LEDGERS + MAX_OWNER_CLAIMS + 6
                    or entry.name
                    not in {
                        ".owner",
                        ".lock",
                        ".allocated",
                        "live",
                        *(claim_lock_name(i) for i in range(MAX_OWNER_CLAIMS)),
                        ".claims",
                        ".poison",
                        *(f"scope-{i:02d}" for i in range(MAX_SCOPE_LEDGERS)),
                    }
                ):
                    refuse("bookkeeping_foreign")

        def current(*, check_claim_locks=True):
            private(os.fstat(directory), directory=True)
            private(os.fstat(live), directory=True)
            if (
                node_wire(os.fstat(directory)) != value["root"]
                or node_wire(root.lstat()) != value["root"]
                or node_wire(root.parent.lstat()) != value["parent"]
                or node_wire(parent_node) != value["parent"]
                or node_wire(os.fstat(live)) != value["live"]
                or node_wire(os.stat("live", dir_fd=directory, follow_symlinks=False))
                != value["live"]
            ):
                refuse("bookkeeping_changed")
            require_file(
                directory,
                ".owner",
                marker_fd,
                expected=node_wire(marker_node),
                size=len(marker),
            )
            if os.pread(marker_fd, MAX_NAMESPACE_MARKER_BYTES + 1, 0) != marker:
                refuse("bookkeeping_changed")
            require_file(directory, ".lock", lock, expected=value["lock"], size=0)
            require_file(
                directory,
                ".allocated",
                allocation,
                expected=value["allocation"],
                size=ALLOCATION_BYTES,
            )
            if os.pread(allocation, ALLOCATION_HEADER_BYTES, 0) != bytes.fromhex(nonce):
                refuse("bookkeeping_changed")
            for name, descriptor, expected, size in (
                (".claims", claims, value["claims"], CLAIMS_BYTES),
                (".poison", poison, value["poison"], POISON_BYTES),
            ):
                require_file(directory, name, descriptor, expected=expected, size=size)
            if os.pread(claims, CLAIMS_HEADER_BYTES, 0) != bytes.fromhex(nonce):
                refuse("bookkeeping_changed")
            if check_claim_locks:
                for index in range(MAX_OWNER_CLAIMS):
                    node = os.stat(
                        claim_lock_name(index), dir_fd=directory, follow_symlinks=False
                    )
                    private(node)
                    if (
                        node_wire(node) != value["claim_locks"][index]
                        or node.st_size != 0
                    ):
                        refuse("bookkeeping_changed")

        current()
        claim_locks = (directory, tuple(value["claim_locks"]), current)
        yield directory, lock, allocation, live, claim_locks, claims, poison, current
        current()


@contextmanager
def locked_claim_row(claim_locks, index):
    """One lazy held flock FD, joined to the fully attested fixed namespace.

    Separate inodes avoid cross-operation contention and POSIX record-lock
    close semantics. Readers never create locks. This holds no execution lock.
    """
    from .worker_telemetry_replay import _locked

    directory, nodes, current = claim_locks
    name = claim_lock_name(index)
    current(check_claim_locks=False)
    descriptor = open_file(directory, name)
    try:
        require_file(directory, name, descriptor, expected=nodes[index], size=0)
        with _locked(descriptor):
            require_file(directory, name, descriptor, expected=nodes[index], size=0)
            yield
            require_file(directory, name, descriptor, expected=nodes[index], size=0)
        current(check_claim_locks=False)
    finally:
        os.close(descriptor)
