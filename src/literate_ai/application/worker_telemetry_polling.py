"""Finite process-local polling admission; no collector or job-control capability.

An admitted leader still needs the original live action owner, a bounded native
collector and the negotiated transport. This owner retains no samples or history.
Collector slots remain occupied until their original leader finishes, including
after cancellation/expiry: an uncooperative collector cannot create capacity.
"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from literate_ai.application.worker_telemetry_authorization import (
    TelemetryAuthorizationError,
    TelemetryScopeAuthority,
)
from literate_ai.contracts._validation import int_value

_SECOND_NS = 1_000_000_000
_TICKET_ISSUER = object()


class TelemetryPollingError(ValueError):
    pass


def _fail(reason):
    raise TelemetryPollingError("worker.telemetry_polling_" + reason)


@dataclass(slots=True)
class _Collection:
    key: tuple
    permit: object
    deadline_ns: int
    leader: object = field(default_factory=object)
    participants: set = field(default_factory=set)
    cancelled: bool = False
    finished: bool = False


class TelemetryPollTicket:
    """Opaque local bookkeeping, never a serialized or execution grant."""

    __slots__ = (
        "_window",
        "_collection",
        "_participant",
        "_permit",
        "_deadline_ns",
        "_issuer",
    )

    def __init__(
        self, window, collection, participant, permit, deadline_ns, *, _issuer
    ):
        if _issuer is not _TICKET_ISSUER:
            _fail("ticket_invalid")
        for name, value in (
            ("_window", window),
            ("_collection", collection),
            ("_participant", participant),
            ("_permit", permit),
            ("_deadline_ns", deadline_ns),
            ("_issuer", _issuer),
        ):
            object.__setattr__(self, name, value)

    def __setattr__(self, name, value):
        raise AttributeError("worker.telemetry_poll_ticket_immutable")

    def __reduce_ex__(self, protocol):
        raise TypeError("worker.telemetry_poll_ticket_not_serializable")

    @property
    def is_leader(self):
        return self._participant is self._collection.leader

    @property
    def deadline_ns(self):
        return min(self._collection.deadline_ns, self._deadline_ns)

    @property
    def cancellation_requested(self):
        try:
            self.require_current()
        except (TelemetryPollingError, TelemetryAuthorizationError):
            return True
        return False

    def require_current(self):
        self._window.require_current(self)

    def release(self):
        """Detach this observer; the collector's slot is not released here."""
        self._window.release(self)

    def finish(self):
        """Original collector's finally hook, including failed/expired collection."""
        self._window.finish(self)


class TelemetryPollWindow:
    """One current authority's one-second rate and bounded coalescing window.

    Each begin consumes a genuinely authenticated nonce through the original
    authority. Equivalent simultaneous selectors share one collection, while each
    participant retains its own current permission. A join never extends the first
    deadline. No response data is produced here; codecs must still bind every
    response and sample to its participant's exact request and freshness window.
    """

    def __init__(
        self,
        authority,
        *,
        monotonic_ns=time.monotonic_ns,
        maximum_collectors=4,
        maximum_waiters=64,
    ):
        if type(authority) is not TelemetryScopeAuthority or not callable(monotonic_ns):
            _fail("original_authority_required")
        int_value(maximum_collectors, "telemetry.collectors", minimum=1, maximum=16)
        int_value(maximum_waiters, "telemetry.waiters", minimum=1, maximum=64)
        self._authority = authority
        self._clock = monotonic_ns
        self._maximum_collectors = maximum_collectors
        self._maximum_waiters = maximum_waiters
        self._lock = threading.Lock()
        self._collections = {}
        self._last_now = 0
        self._last_started = None
        self._closed = False
        authority.claim_polling_owner()

    @contextmanager
    def _guard(self):
        if not self._lock.acquire(blocking=False):
            _fail("busy")
        try:
            yield
        finally:
            self._lock.release()

    def _now(self):
        try:
            now = self._clock()
            int_value(now, "telemetry.poll_now", maximum=(1 << 63) - 30 * _SECOND_NS)
        except Exception:
            raise TelemetryPollingError(
                "worker.telemetry_polling_clock_unavailable"
            ) from None
        if now < self._last_now:
            self._close()
            _fail("clock_regressed")
        self._last_now = now
        return now

    def _close(self):
        self._closed = True
        for collection in self._collections.values():
            collection.cancelled = True

    def close(self):
        # Observation bookkeeping only; there are no job/process handles here.
        with self._guard():
            self._close()

    def begin(self, proof):
        permit = self._authority.authorize(proof)
        request = permit.request
        key = (request.scope, request.action_identities)
        with self._guard():
            now = self._now()
            if self._closed:
                _fail("closed")
            request, wall_now = self._authority.require_permit(permit)
            duration_ns = min(30_000, request.expires_at_ms - wall_now) * 1_000_000
            deadline_ns = now + duration_ns
            collection = self._collections.get(key)
            if collection is not None:
                if collection.cancelled or now >= collection.deadline_ns:
                    collection.cancelled = True
                    _fail("collector_retiring")
                self._authority.require_permit(collection.permit)
                if len(collection.participants) >= self._maximum_waiters:
                    _fail("waiter_capacity")
                participant = object()
            else:
                if len(self._collections) >= self._maximum_collectors:
                    _fail("collector_capacity")
                if (
                    self._last_started is not None
                    and now - self._last_started < _SECOND_NS
                ):
                    _fail("rate_excess")
                collection = _Collection(key, permit, deadline_ns)
                participant = collection.leader
            # Slow authority ports cannot extend the first deadline or backdate
            # the actual collection start behind the recorded rate bound.
            self._authority.require_permit(permit)
            accepted_ns = self._now()
            if accepted_ns >= min(deadline_ns, collection.deadline_ns):
                _fail("expired")
            if participant is collection.leader:
                self._collections[key] = collection
                self._last_started = accepted_ns
            collection.participants.add(participant)
            return TelemetryPollTicket(
                self,
                collection,
                participant,
                permit,
                deadline_ns,
                _issuer=_TICKET_ISSUER,
            )

    def _require_ticket(self, ticket):
        if (
            type(ticket) is not TelemetryPollTicket
            or getattr(ticket, "_issuer", None) is not _TICKET_ISSUER
            or getattr(ticket, "_window", None) is not self
        ):
            _fail("foreign_ticket")
        return ticket._collection

    def require_current(self, ticket):
        with self._guard():
            collection = self._require_ticket(ticket)
            now = self._now()
            if (
                self._closed
                or collection.finished
                or collection.cancelled
                or now >= ticket.deadline_ns
                or ticket._participant not in collection.participants
            ):
                _fail("inactive")
            self._authority.require_permit(ticket._permit)
            if self._now() >= ticket.deadline_ns:
                _fail("inactive")

    def release(self, ticket):
        with self._guard():
            collection = self._require_ticket(ticket)
            collection.participants.discard(ticket._participant)
            if ticket.is_leader or not collection.participants:
                collection.cancelled = True

    def finish(self, ticket):
        with self._guard():
            collection = self._require_ticket(ticket)
            if not ticket.is_leader:
                _fail("collector_owner_required")
            if not collection.finished:
                assert self._collections.get(collection.key) is collection
                del self._collections[collection.key]
                collection.participants.clear()
                collection.finished = True
                collection.cancelled = True

    @property
    def retained_counts(self):
        with self._guard():
            return len(self._collections), sum(
                len(c.participants) for c in self._collections.values()
            )
