"""Preallocated monotonic announcements before an owner becomes publishable.

These are observation claims, never execution reservations. The actual issuer
attempts each of 64 independent row locks once, without waiting. Failed
allocation poisons the selector independently of those locks. Queries compare
records with an original issued owner; they never create claims, repair old state
or grant execution from the table.
"""

from __future__ import annotations

import hashlib
import os
import threading
import weakref
from contextlib import ExitStack
from dataclasses import dataclass, field

from literate_ai.contracts.identity import ContentIdentity, canonical_identity

from .worker_telemetry_issuance import ObservationIssuance
from .worker_telemetry_namespace import (
    CLAIM_RECORD_BYTES,
    CLAIMS_HEADER_BYTES,
    MAX_OWNER_CLAIMS,
    locked_claim_row,
    open_worker_telemetry_namespace,
    refuse,
    write_at,
)
from .worker_telemetry_wire import WorkerTelemetryWireError

_ISSUER = object()


def selector_digest(configuration, operation):
    return canonical_identity(
        {
            "schema": "literate-ai/private-worker-telemetry-owner-slot-name@1",
            "registration_identity": configuration.registration_identity.to_dict(),
            "operation_identity": operation.to_dict(),
        }
    ).digest


def require_unpoisoned(poison, selector):
    if os.pread(poison, 1, int(selector[:4], 16)) != b"\0":
        refuse("owner_ambiguous")


def _decode_record(raw):
    if len(raw) != CLAIM_RECORD_BYTES:
        refuse("announcement_unavailable")
    if raw == bytes(CLAIM_RECORD_BYTES):
        return None
    if raw[:1] not in {b"P", b"R", b"C"} or any(raw[257:]):
        refuse("announcement_unavailable")
    payload = raw[1:193]
    if any(c not in b"0123456789abcdef" for c in payload) or raw[
        193:257
    ] != hashlib.sha256(payload).hexdigest().encode("ascii"):
        refuse("announcement_unavailable")
    return (
        raw[:1],
        payload[:64].decode("ascii"),
        payload[64:128].decode("ascii"),
        payload[128:192].decode("ascii"),
    )


def _observed_duplicate(claims, selector, own_index, own_record):
    """Denial-only closing probe; raw records can NEVER make a sample healthy."""
    for index in range(MAX_OWNER_CLAIMS):
        try:
            record = _decode_record(
                os.pread(
                    claims,
                    CLAIM_RECORD_BYTES,
                    CLAIMS_HEADER_BYTES + index * CLAIM_RECORD_BYTES,
                )
            )
        except WorkerTelemetryWireError:
            continue
        if index == own_index and record == own_record:
            continue
        if record is not None and record[1] == selector:
            return True
    return False


def _complete_frontier(claim_locks, claims, current):
    """Compare the COMPLETE finite table twice; contention is only unavailable.

    No lock spans rows or signing. This is a closing comparison, not an atomic
    batch promise. A pending/changed/locked row can conceal a same-selector peer,
    so no healthy sample may be published from such a frontier.
    """

    def read():
        result = []
        for index in range(MAX_OWNER_CLAIMS):
            with locked_claim_row(claim_locks, index):
                raw = os.pread(
                    claims,
                    CLAIM_RECORD_BYTES,
                    CLAIMS_HEADER_BYTES + index * CLAIM_RECORD_BYTES,
                )
                record = _decode_record(raw)
                if record is not None and record[0] != b"R":
                    refuse("observation_overloaded")
                result.append(record)
        return tuple(result)

    current()
    before = read()
    after = read()
    if before != after:
        refuse("observation_overloaded")
    current()
    return after


def require_announced(
    claim_lock,
    claims,
    poison,
    current,
    configuration,
    operation,
    index,
    publisher,
    owner,
):
    """Read-only full-frontier comparison, never an owner decoder/allocator."""
    if type(index) is not int or not 0 <= index < MAX_OWNER_CLAIMS:
        refuse("announcement_unavailable")
    selector = selector_digest(configuration, operation)
    current()
    require_unpoisoned(poison, selector)
    records = _complete_frontier(claim_lock, claims, current)
    if records[index] != (b"R", selector, publisher.digest, owner.digest):
        refuse("owner_ambiguous")
    if sum(record is not None and record[1] == selector for record in records) != 1:
        refuse("owner_ambiguous")
    require_unpoisoned(poison, selector)
    current()
    if _observed_duplicate(
        claims, selector, index, (b"R", selector, publisher.digest, owner.digest)
    ):
        refuse("owner_ambiguous")
    current()
    require_unpoisoned(poison, selector)


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ActualOwnerAnnouncement:
    index: int
    _publisher: object = field(repr=False)
    _owner: object = field(repr=False)
    _pid: int = field(repr=False)
    _issuance: ObservationIssuance = field(repr=False)

    def require_original(self, publisher, owner):
        self._issuance.require_original(self, _ISSUER)
        if (
            self._pid != os.getpid()
            or self._publisher() is not publisher
            or self._owner() is not owner
        ):
            refuse("actual_owner_announcement_required")

    def __copy__(self):
        refuse("announcement_not_copyable")

    def __deepcopy__(self, memo):
        refuse("announcement_not_copyable")

    def __reduce__(self):
        refuse("announcement_not_restorable")


def _quiet_close(stack):
    try:
        stack.close()
    except Exception:
        pass


class ConfiguredOwnerAnnouncements:
    """Original issuer's held observation descriptors, never execution handles."""

    __slots__ = ("_values", "__weakref__")

    def __init__(self, configuration):
        stack = ExitStack()
        try:
            namespace = stack.enter_context(
                open_worker_telemetry_namespace(configuration)
            )
            finalizer = weakref.finalize(self, _quiet_close, stack)
            object.__setattr__(
                self,
                "_values",
                (
                    configuration,
                    namespace,
                    os.getpid(),
                    threading.get_ident(),
                    [False],
                    finalizer,
                ),
            )
        except BaseException:
            _quiet_close(stack)
            raise

    def __setattr__(self, name, value):
        refuse("announcement_not_copyable")

    @property
    def _configuration(self):
        return self._values[0]

    @property
    def _namespace(self):
        return self._values[1]

    @property
    def _pid(self):
        return self._values[2]

    @property
    def _thread(self):
        return self._values[3]

    @property
    def _state(self):
        return self._values[4]

    @property
    def _finalizer(self):
        return self._values[5]

    def require_healthy(self):
        if self._state[0] or self._pid != os.getpid() or not self._finalizer.alive:
            refuse("announcement_unavailable")

    def require_issuer(self):
        self.require_healthy()
        if self._thread != threading.get_ident():
            refuse("announcement_unavailable")

    def close(self):
        if self._pid != os.getpid() or self._thread != threading.get_ident():
            refuse("announcement_unavailable")
        self._state[0] = True
        self._finalizer()

    def announce(self, publisher, owner):
        self.require_issuer()
        if publisher._configuration is not self._configuration:
            refuse("actual_owner_announcement_required")
        owner._admission.require_current()
        (_directory, _lock, _allocation, _live, claim_lock, claims, poison, current) = (
            self._namespace
        )
        selector = selector_digest(self._configuration, owner.operation_identity)

        def poison_selector():
            self.poison_operation(owner.operation_identity)

        committed = False
        try:
            current()
            require_unpoisoned(poison, selector)
            selected = None
            # Finite scan, one nonblocking attempt per independent row. Busy
            # OTHER rows never permanently poison a successfully announced job.
            for index in range(MAX_OWNER_CLAIMS):
                offset = CLAIMS_HEADER_BYTES + index * CLAIM_RECORD_BYTES
                # A checksummed SAME-selector claim is monotonic evidence for
                # refusal, never permission. Observe it even while a reader
                # holds that row's flock. Torn/foreign/empty probes grant
                # nothing and cannot poison an unrelated operation.
                try:
                    observed = _decode_record(
                        os.pread(claims, CLAIM_RECORD_BYTES, offset)
                    )
                except WorkerTelemetryWireError:
                    observed = None
                if observed is not None and observed[1] == selector:
                    refuse("owner_ambiguous")
                try:
                    with locked_claim_row(claim_lock, index):
                        record = _decode_record(
                            os.pread(claims, CLAIM_RECORD_BYTES, offset)
                        )
                        if record is not None:
                            if record[1] == selector:
                                refuse("owner_ambiguous")
                            continue
                        payload = (
                            selector + publisher._epoch.digest + owner._identity.digest
                        ).encode("ascii")
                        pending = (
                            b"P"
                            + payload
                            + hashlib.sha256(payload).hexdigest().encode("ascii")
                        ).ljust(CLAIM_RECORD_BYTES, b"\0")
                        write_at(claims, pending, offset)
                        if os.pread(claims, CLAIM_RECORD_BYTES, offset) != pending:
                            refuse("announcement_unavailable")
                        write_at(claims, b"R", offset)
                        if _decode_record(
                            os.pread(claims, CLAIM_RECORD_BYTES, offset)
                        ) != (
                            b"R",
                            selector,
                            publisher._epoch.digest,
                            owner._identity.digest,
                        ):
                            refuse("announcement_unavailable")
                        selected = index
                        committed = True
                        break
                except WorkerTelemetryWireError as exc:
                    if exc.code != "worker_telemetry.observation_overloaded":
                        raise
            if selected is None:
                refuse("owner_limit")
            # An unknown frontier temporarily disables publication, not actual
            # execution. The durable own row still announces this real owner;
            # every subsequent query reopens the WHOLE frontier before signing.
            try:
                records = _complete_frontier(claim_lock, claims, current)
            except WorkerTelemetryWireError as exc:
                if exc.code != "worker_telemetry.observation_overloaded":
                    raise
            else:
                if (
                    sum(
                        record is not None and record[1] == selector
                        for record in records
                    )
                    != 1
                ):
                    poison_selector()
                    refuse("owner_ambiguous")
            owner._admission.require_current()
            issuance = ObservationIssuance(_ISSUER)
            announcement = ActualOwnerAnnouncement(
                selected,
                weakref.ref(publisher),
                weakref.ref(owner),
                os.getpid(),
                issuance,
            )
            issuance.bind(announcement, _ISSUER)
            current()
            # Two original issuers can commit DIFFERENT rows after observing
            # all-empty predecessors. Once either reaches its execution body,
            # its R claim persists. This closing denial-only scan makes the
            # chronological second body poison the exact selector even while
            # another observer holds the earlier row's flock.
            if _observed_duplicate(
                claims,
                selector,
                selected,
                (b"R", selector, publisher._epoch.digest, owner._identity.digest),
            ):
                poison_selector()
                refuse("owner_ambiguous")
            current()
            require_unpoisoned(poison, selector)
            return announcement
        except BaseException:
            if not committed:
                # No execution body may begin with an unannounced owner while a
                # previous same-selector publisher could still look healthy.
                poison_selector()
            raise

    def poison_operation(self, operation):
        self.require_issuer()
        if (
            type(operation) is not ContentIdentity
            or operation not in self._configuration.scope.operation_identities
        ):
            refuse("actual_owner_announcement_required")
        (
            _directory,
            _lock,
            _allocation,
            _live,
            _claim_lock,
            _claims,
            poison,
            current,
        ) = self._namespace
        try:
            current()
            selector = selector_digest(self._configuration, operation)
            # One byte is a monotonic cell, not a packed RMW bitmap. Hash
            # collisions only refuse extra observations; no writer clears it.
            offset = int(selector[:4], 16)
            if os.pwrite(poison, b"1", offset) != 1:
                refuse("announcement_unavailable")
            if os.pread(poison, 1, offset) != b"1":
                refuse("announcement_unavailable")
            current()
        except BaseException:
            self._state[0] = True
            raise

    def __copy__(self):
        refuse("announcement_not_copyable")

    def __deepcopy__(self, memo):
        refuse("announcement_not_copyable")

    def __reduce__(self):
        refuse("announcement_not_restorable")
