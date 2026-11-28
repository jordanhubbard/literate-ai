"""Finite durable replay/rate admission, never a live execution owner.

Queries reopen an explicitly initialized namespace. Allocations are committed
before consumption, and bind the exact ledger inode and random allocation token.
Missing, replaced or torn state refuses instead of recreating empty history.
"""

from __future__ import annotations

import hashlib
import os
import secrets
import time
from contextlib import ExitStack, contextmanager
from datetime import UTC, datetime

from literate_ai.contracts.identity import canonical_json_bytes

from .action_dispatch_wire import ActionDispatchDeadline
from .worker_telemetry_authentication_v2 import verify_telemetry_request
from .worker_telemetry_configuration import CurrentWorkerTelemetryConfiguration
from .worker_telemetry_namespace import (
    ALLOCATION_HEADER_BYTES,
    ALLOCATION_RECORD_BYTES,
    MAX_SCOPE_LEDGERS,
    node_wire,
    open_file,
    open_worker_telemetry_namespace,
    refuse,
    require_file,
    write_at,
)
from .worker_telemetry_wire_v2 import WorkerTelemetryWireError, _decode

_HEADER_BYTES = 1024
_BITMAP_BYTES = 512 * 1024
_FILE_BYTES = _HEADER_BYTES + _BITMAP_BYTES
_LEDGER_SCHEMA = "literate-ai/private-worker-telemetry-replay@1"
_ALLOCATION_SCHEMA = "literate-ai/private-worker-telemetry-allocation@1"


def _digest(value):
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


@contextmanager
def _locked(descriptor):
    import fcntl

    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        refuse("observation_overloaded")
    try:
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)


def _header(raw):
    if len(raw) != _HEADER_BYTES or raw[:1] != b"0":
        refuse("bookkeeping_incomplete")
    value = _decode(raw[1:].rstrip(b"\0"), _HEADER_BYTES)
    if (
        not isinstance(value, dict)
        or set(value)
        != {
            "schema",
            "scope",
            "allocation_nonce",
            "expires_at_ms",
            "last_query_ms",
            "last_monotonic_ns",
        }
        or value["schema"] != _LEDGER_SCHEMA
        or not _digest(value["scope"])
        or not _digest(value["allocation_nonce"])
        or type(value["expires_at_ms"]) is not int
        or not 0 <= value["expires_at_ms"] <= 2**63 - 1
        or type(value["last_query_ms"]) is not int
        or not -1 <= value["last_query_ms"] < value["expires_at_ms"]
        or type(value["last_monotonic_ns"]) is not int
        or not -1 <= value["last_monotonic_ns"] <= 2**63 - 1
    ):
        refuse("bookkeeping_invalid")
    return value


def _encoded_header(value):
    raw = b"0" + canonical_json_bytes(value)
    if len(raw) > _HEADER_BYTES:
        refuse("bookkeeping_limit")
    return raw.ljust(_HEADER_BYTES, b"\0")


def _allocation(raw):
    if len(raw) != ALLOCATION_RECORD_BYTES:
        refuse("bookkeeping_invalid")
    if raw == bytes(ALLOCATION_RECORD_BYTES):
        return None
    if raw[:1] != b"2":
        refuse("bookkeeping_incomplete")
    value = _decode(raw[1:].rstrip(b"\0"), ALLOCATION_RECORD_BYTES)
    if (
        not isinstance(value, dict)
        or set(value)
        != {"schema", "scope", "allocation_nonce", "expires_at_ms", "node"}
        or value["schema"] != _ALLOCATION_SCHEMA
        or not _digest(value["scope"])
        or not _digest(value["allocation_nonce"])
        or type(value["expires_at_ms"]) is not int
        or not 0 <= value["expires_at_ms"] <= 2**63 - 1
        or type(value["node"]) is not list
        or len(value["node"]) != 5
    ):
        refuse("bookkeeping_invalid")
    return value


def _require_ledger(directory, name, descriptor, allocation):
    require_file(
        directory, name, descriptor, expected=allocation["node"], size=_FILE_BYTES
    )
    header = _header(os.pread(descriptor, _HEADER_BYTES, 0))
    if any(
        header[field] != allocation[field]
        for field in ("scope", "allocation_nonce", "expires_at_ms")
    ):
        refuse("bookkeeping_changed")
    return header


def _select_ledger(configuration, directory, allocation_fd, current, stack, deadline):
    selected = None
    first_unused = None
    seen_scopes = set()
    for index in range(MAX_SCOPE_LEDGERS):
        deadline.remaining()
        offset = ALLOCATION_HEADER_BYTES + index * ALLOCATION_RECORD_BYTES
        allocation = _allocation(
            os.pread(allocation_fd, ALLOCATION_RECORD_BYTES, offset)
        )
        name = f"scope-{index:02d}"
        if allocation is None:
            try:
                os.stat(name, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                if first_unused is None:
                    first_unused = index
            else:
                refuse("bookkeeping_foreign")
            continue
        # An allocated file may never disappear or be replaced, even between
        # receiver restarts. Do not close/reopen the selected descriptor.
        descriptor = open_file(directory, name)
        retained = False
        try:
            _require_ledger(directory, name, descriptor, allocation)
            if allocation["scope"] in seen_scopes:
                refuse("bookkeeping_invalid")
            seen_scopes.add(allocation["scope"])
            if allocation["scope"] == configuration.scope.identity.digest:
                if selected is not None:
                    refuse("bookkeeping_invalid")
                stack.callback(os.close, descriptor)
                retained = True
                selected = name, descriptor, allocation
        finally:
            if not retained:
                os.close(descriptor)
    if selected is not None:
        return selected
    if first_unused is None:
        refuse("bookkeeping_limit")
    index = first_unused
    offset = ALLOCATION_HEADER_BYTES + index * ALLOCATION_RECORD_BYTES
    name = f"scope-{index:02d}"
    current()
    # Commit a pending allocation BEFORE creating any ledger. A crash leaves a
    # typed incomplete state; no later query can initialize that slot again.
    write_at(allocation_fd, b"1" + bytes(ALLOCATION_RECORD_BYTES - 1), offset)
    os.fsync(allocation_fd)
    current()
    descriptor = open_file(directory, name, create=True)
    stack.callback(os.close, descriptor)
    header = {
        "schema": _LEDGER_SCHEMA,
        "scope": configuration.scope.identity.digest,
        "allocation_nonce": secrets.token_hex(32),
        "expires_at_ms": configuration.scope.expires_at_ms,
        "last_query_ms": -1,
        "last_monotonic_ns": -1,
    }
    write_at(descriptor, _encoded_header(header) + bytes(_BITMAP_BYTES), 0)
    os.fsync(descriptor)
    os.fsync(directory)
    allocation = {
        field: header[field] for field in ("scope", "allocation_nonce", "expires_at_ms")
    }
    allocation.update(schema=_ALLOCATION_SCHEMA, node=node_wire(os.fstat(descriptor)))
    raw = b"2" + canonical_json_bytes(allocation)
    if len(raw) > ALLOCATION_RECORD_BYTES:
        refuse("bookkeeping_limit")
    _require_ledger(directory, name, descriptor, allocation)
    current()
    # Publish the allocation's ready flag last; then and only then may a nonce
    # be consumed or a successful observation returned.
    write_at(
        allocation_fd, raw[1:].ljust(ALLOCATION_RECORD_BYTES - 1, b"\0"), offset + 1
    )
    os.fsync(allocation_fd)
    write_at(allocation_fd, b"2", offset)
    os.fsync(allocation_fd)
    current()
    return name, descriptor, allocation


def consume_worker_telemetry_request(
    raw: bytes, configuration: CurrentWorkerTelemetryConfiguration
):
    """Authenticate and durably consume once, before collecting or answering.

    At most64 fixed512KiB scope bitmaps are retained, with a fixed64KiB
    allocation table. A Bloom false positive safely refuses. Ledgers are never
    evicted automatically. Concurrency slots and actual live membership remain
    separate receiver responsibilities; this function grants neither.
    """
    if (
        type(configuration) is not CurrentWorkerTelemetryConfiguration
        or configuration.role != "receiver"
        or os.name != "posix"
    ):
        refuse("receiver_configuration_required")
    now = int(datetime.now(UTC).timestamp() * 1000)
    request = verify_telemetry_request(raw, configuration.scope, now_ms=now)
    deadline = ActionDispatchDeadline(
        datetime.fromtimestamp(request.expires_at_ms / 1000, UTC)
    )
    configuration.require_current(deadline=deadline)
    try:
        with open_worker_telemetry_namespace(configuration) as (
            directory,
            lock,
            allocation_fd,
            _live,
            _claim_lock,
            _claims,
            _poison,
            current,
        ):
            with _locked(lock), ExitStack() as stack:
                current()
                name, descriptor, allocation = _select_ledger(
                    configuration, directory, allocation_fd, current, stack, deadline
                )
                header = _require_ledger(directory, name, descriptor, allocation)
                if (
                    header["scope"] != configuration.scope.identity.digest
                    or header["expires_at_ms"] != configuration.scope.expires_at_ms
                ):
                    refuse("bookkeeping_changed")
                now = int(datetime.now(UTC).timestamp() * 1000)
                monotonic = time.monotonic_ns()
                configuration.scope.require_request(request, now_ms=now)
                if (
                    header["last_query_ms"] >= 0
                    and now - header["last_query_ms"]
                    < configuration.scope.minimum_poll_interval_ms
                    or header["last_monotonic_ns"] >= 0
                    and monotonic - header["last_monotonic_ns"]
                    < configuration.scope.minimum_poll_interval_ms * 1_000_000
                ):
                    refuse("poll_rate_exceeded")
                digest = hashlib.sha256(
                    bytes.fromhex(configuration.scope.identity.digest)
                    + bytes.fromhex(request.nonce)
                ).digest()
                changes = {}
                for offset in range(0, 28, 4):
                    bit = int.from_bytes(digest[offset : offset + 4], "big") % (
                        _BITMAP_BYTES * 8
                    )
                    position = _HEADER_BYTES + bit // 8
                    original = changes.get(position)
                    if original is None:
                        chunk = os.pread(descriptor, 1, position)
                        if len(chunk) != 1:
                            refuse("bookkeeping_invalid")
                        original = chunk[0]
                    changes[position] = original | 1 << (bit % 8)
                if all(
                    os.pread(descriptor, 1, position) == bytes((changed,))
                    for position, changed in changes.items()
                ):
                    refuse("request_replayed")
                current()
                _require_ledger(directory, name, descriptor, allocation)
                # Poison first, consume all bits durably, then publish validity
                # last. Every write still targets the held exact allocated file.
                write_at(descriptor, b"1", 0)
                os.fsync(descriptor)
                require_file(
                    directory,
                    name,
                    descriptor,
                    expected=allocation["node"],
                    size=_FILE_BYTES,
                )
                current()
                for position, changed in changes.items():
                    write_at(descriptor, bytes((changed,)), position)
                os.fsync(descriptor)
                header.update(last_query_ms=now, last_monotonic_ns=monotonic)
                write_at(descriptor, _encoded_header(header)[1:], 1)
                os.fsync(descriptor)
                require_file(
                    directory,
                    name,
                    descriptor,
                    expected=allocation["node"],
                    size=_FILE_BYTES,
                )
                current()
                write_at(descriptor, b"0", 0)
                os.fsync(descriptor)
                if _require_ledger(
                    directory, name, descriptor, allocation
                ) != header or any(
                    os.pread(descriptor, 1, position) != bytes((changed,))
                    for position, changed in changes.items()
                ):
                    refuse("bookkeeping_changed")
                current()
        configuration.require_current(deadline=deadline)
        configuration.scope.require_request(
            request, now_ms=int(datetime.now(UTC).timestamp() * 1000)
        )
        return request
    except WorkerTelemetryWireError:
        raise
    except (OSError, ValueError, RuntimeError, TypeError) as exc:
        raise WorkerTelemetryWireError(
            "worker_telemetry.bookkeeping_unavailable"
        ) from exc
