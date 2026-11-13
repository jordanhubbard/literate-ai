"""Read-only original controller reservation views, not worker execution authority.

The actual capacity owner publishes immutable observation state. Consumers never
take its mutation Condition or receive an operation/cancel/release capability.
This controller provenance still needs the receiver's actual live action/process
owner before any process counter can become a trusted worker action observation.
"""

from __future__ import annotations

import secrets
import threading
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace

from literate_ai.application.action_dag_scheduler import (
    LifecycleActionDispatchRequest,
    LifecycleActionWorker,
)
from literate_ai.contracts.identity import ContentIdentity, canonical_identity

_CURRENT = ContextVar("literate_ai_original_reservation_observation", default=None)
_ISSUER = object()
_CAPACITY_ISSUER = object()


class ReservationObservationError(ValueError):
    pass


def _fail(reason):
    raise ReservationObservationError("worker.telemetry_reservation_" + reason)


@dataclass(frozen=True, slots=True)
class ActionReservationSnapshot:
    reservation_identity: ContentIdentity
    binding_identity: ContentIdentity
    request_identity: ContentIdentity
    action_identity: ContentIdentity
    worker_identity: ContentIdentity
    catalog_identity: ContentIdentity
    deadline_identity: ContentIdentity
    slot: int
    expires_at_ms: int


@dataclass(frozen=True, slots=True)
class _Published:
    active: bool = False
    retired: bool = False
    unknown: bool = False
    binding: ActionReservationSnapshot | None = None


class ActionReservationObservation:
    __slots__ = ("_holder", "_binding", "_issuer")

    def __init__(self, holder, binding, *, _issuer):
        if _issuer is not _ISSUER:
            _fail("original_owner_required")
        object.__setattr__(self, "_holder", holder)
        object.__setattr__(self, "_binding", binding)
        object.__setattr__(self, "_issuer", _issuer)

    def __setattr__(self, name, value):
        raise AttributeError("worker.telemetry_reservation_view_immutable")

    def __reduce_ex__(self, protocol):
        raise TypeError("worker.telemetry_reservation_view_not_serializable")

    def require_current(self, request=None):
        if getattr(self, "_issuer", None) is not _ISSUER:
            _fail("original_owner_required")
        current = self._holder.published
        if (
            not current.active
            or current.retired
            or current.unknown
            or current.binding is not self._binding
        ):
            _fail("inactive")
        if request is not None and (
            not isinstance(request, LifecycleActionDispatchRequest)
            or request.identity != self._binding.request_identity
        ):
            _fail("request_mismatch")
        # This is a separate observation clock lock; never the slot Condition.
        self._holder.require_observation_time()
        if self._holder.published is not current:
            _fail("changed")
        return self._binding


class _ReservationObserver:
    def __init__(self, worker, slot, deadline, *, _issuer):
        if (
            _issuer is not _CAPACITY_ISSUER
            or not isinstance(worker, LifecycleActionWorker)
            or not 0 <= slot < worker.slots
        ):
            _fail("unavailable")
        self.worker, self.slot = worker, slot
        self.deadline_identity = deadline.identity
        self.expires_at_ms = int(deadline.expires_at.timestamp() * 1000)
        self.identity = canonical_identity(
            {"original_capacity_reservation": secrets.token_hex(32)}
        )
        self.published = _Published()
        self._publication_lock = threading.Lock()
        self._clock_lock = threading.Lock()
        self._last_now = 0
        self._clock_closed = False

    def enter(self):
        with self._publication_lock:
            if not self.published.retired and not self.published.unknown:
                self.published = replace(self.published, active=True)

    def leave(self):
        with self._publication_lock:
            self.published = replace(self.published, active=False)

    def retire(self):
        with self._publication_lock:
            self.published = replace(self.published, active=False, retired=True)

    def quarantine(self):
        with self._publication_lock:
            self.published = replace(self.published, unknown=True)

    def bind(self, request):
        if (
            not isinstance(request, LifecycleActionDispatchRequest)
            or request.worker != self.worker
            or request.slot != self.slot
            or request.deadline_identity != self.deadline_identity
        ):
            _fail("binding_mismatch")
        # Request identities may do external work. Prepare them without holding
        # publication ownership, then revalidate the actual live state below.
        request_identity = request.identity
        candidate = ActionReservationSnapshot(
            self.identity,
            canonical_identity({"original_dispatch_binding": secrets.token_hex(32)}),
            request_identity,
            request.action.identity,
            self.worker.worker_identity,
            self.worker.catalog_identity,
            self.deadline_identity,
            self.slot,
            self.expires_at_ms,
        )
        with self._publication_lock:
            current = self.published
            if not current.active or current.retired or current.unknown:
                _fail("binding_mismatch")
            binding = current.binding
            if binding is None or binding.request_identity != request_identity:
                binding = candidate
                self.published = replace(current, binding=binding)
        return ActionReservationObservation(self, binding, _issuer=_ISSUER)

    def view(self):
        binding = self.published.binding
        if binding is None:
            return None
        return ActionReservationObservation(self, binding, _issuer=_ISSUER)

    def finish_binding(self, binding):
        with self._publication_lock:
            if self.published.binding is binding:
                self.published = replace(self.published, binding=None)

    def require_observation_time(self):
        if not self._clock_lock.acquire(blocking=False):
            _fail("busy")
        try:
            now = time.time_ns() // 1_000_000
            if self._clock_closed or now < self._last_now or now >= self.expires_at_ms:
                self._clock_closed = True
                _fail("expired_or_regressed")
            self._last_now = now
        finally:
            self._clock_lock.release()


def create_original_reservation_observer(worker, slot, deadline, *, _issuer=None):
    """Capacity adapter hook, called only after its actual slot claim succeeds."""
    try:
        return _ReservationObserver(worker, slot, deadline, _issuer=_issuer)
    except Exception:
        return None  # Observation setup cannot fail capacity reservation/execution.


@contextmanager
def original_reservation_scope(observer):
    token = _CURRENT.set(observer)
    try:
        if observer is not None:
            observer.enter()
        yield
    finally:
        _CURRENT.reset(token)
        if observer is not None:
            observer.leave()


def bind_current_action_reservation(request):
    """Dispatch hook: bind the real current request, without granting execution."""
    observer = _CURRENT.get()
    if observer is None:
        return None
    try:
        return observer.bind(request)
    except Exception:
        observer.quarantine()
        return None  # Refuse observation, preserving the original dispatch path.


def current_action_reservation_observation():
    observer = _CURRENT.get()
    return None if observer is None else observer.view()


def finish_action_reservation_observation(view):
    """Original exchange finally hook; retires observation, never capacity."""
    if type(view) is not ActionReservationObservation:
        return
    try:
        if view._issuer is _ISSUER:
            view._holder.finish_binding(view._binding)
    except Exception:
        # The enclosing original reservation scope also closes its view. This
        # hook cannot replace the original dispatch result/cleanup exception.
        return
