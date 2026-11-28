"""Opt-in readonly observation handoff; the execution runner retains control."""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from typing import TYPE_CHECKING

from literate_ai.application.action_dag_scheduler import LifecycleActionDispatchRequest
from literate_ai.contracts.identity import ContentIdentity

from .action_dispatch_wire import ActionDispatchDeadline
from .worker_telemetry_issuance import ObservationIssuance
from .worker_telemetry_process import capture_spawned_process

if TYPE_CHECKING:
    from .worker_telemetry_owner import LiveWorkerTelemetryOwner

_OWNER: ContextVar[LiveWorkerTelemetryOwner | None] = ContextVar(
    "literate_ai_worker_telemetry_owner", default=None
)


@contextmanager
def activate_owner_observation(owner: LiveWorkerTelemetryOwner):
    # Runtime type admission is intentionally separate from every decoded wire DTO.
    from .worker_telemetry_owner import LiveWorkerTelemetryOwner

    if type(owner) is not LiveWorkerTelemetryOwner:
        raise TypeError("telemetry requires an actual live operation observation owner")
    owner.require_open()
    token = _OWNER.set(owner)
    try:
        yield
    finally:
        _OWNER.reset(token)


def observe_actual_spawn(pid: int) -> None:
    """Only called after a successful canonical spawn/bind, never from wire data.

    No argv, environment, paths, Popen, or mutable process owner crosses this seam.
    Missing native observation support never changes the child's execution result.
    """
    owner = _OWNER.get()
    if owner is None:
        return
    try:
        process = capture_spawned_process(pid)
        if process is not None:
            owner.record_process_observation(process)
    except Exception:
        # Observation is optional. User interrupts retain their normal semantics.
        return


_ADMISSION_SEAL = object()


@dataclass(frozen=True, slots=True, weakref_slot=True, repr=False)
class ActualOperationObservation:
    """Receiver-issued readonly provenance, never decoded or restored."""

    request: object
    deadline: object
    measured_capability: object
    _receiver_pid: int
    _active: threading.Event = field(repr=False)
    _seal: object = field(repr=False)

    def __post_init__(self):
        if (
            type(self._seal) is not ObservationIssuance
            or type(self.request) is not LifecycleActionDispatchRequest
            or type(self.deadline) is not ActionDispatchDeadline
            or type(self.measured_capability) is not ContentIdentity
            or self.request.deadline_identity != self.deadline.identity
        ):
            raise TypeError("an actual receiver admission boundary is required")
        self._seal.require_constructor(self, _ADMISSION_SEAL)

    def require_current(self):
        if (
            type(self._seal) is not ObservationIssuance
            or self._receiver_pid != os.getpid()
            or not self._active.is_set()
        ):
            raise ValueError("worker_telemetry.operation_ended")
        self._seal.require_original(self, _ADMISSION_SEAL)
        self.deadline.remaining()

    @property
    def reservation_identity(self):
        # The generic measured-request hook precedes protected worker admission.
        return None

    def __copy__(self):
        raise TypeError("actual observation admissions cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("actual observation admissions cannot be copied")

    def __reduce__(self):
        raise TypeError("actual observation admissions cannot be restored")


_LIFETIME: ContextVar[list | None] = ContextVar(
    "literate_ai_worker_telemetry_lifetime", default=None
)


def observation_lifetime(function):
    """Reset only observation state on every action return or exception."""

    @wraps(function)
    def scoped(*args, **kwargs):
        owners = []
        lifetime = _LIFETIME.set(owners)
        try:
            return function(*args, **kwargs)
        finally:
            for owner, token, admission in reversed(owners):
                try:
                    admission._active.clear()
                    owner.close()
                except Exception:
                    pass
                finally:
                    _OWNER.reset(token)
            _LIFETIME.reset(lifetime)

    return scoped


def begin_actual_operation_observation(publisher, request, deadline, capability):
    """An optional hook after actual measured admission, not a wire constructor."""
    owners = _LIFETIME.get()
    if publisher is None or capability is None or owners is None or len(owners) >= 64:
        return
    admission = None
    owner = None
    try:
        from .worker_telemetry_owner import ConfiguredWorkerTelemetryPublisher

        if type(publisher) is not ConfiguredWorkerTelemetryPublisher:
            return
        active = threading.Event()
        active.set()
        issuance = ObservationIssuance(_ADMISSION_SEAL)
        admission = ActualOperationObservation(
            request, deadline, capability, os.getpid(), active, issuance
        )
        issuance.bind(admission, _ADMISSION_SEAL)
        admission.require_current()
        owner = publisher.start_actual_operation(admission)
        owner.require_open()
        token = _OWNER.set(owner)
        owners.append((owner, token, admission))
    except Exception:
        if admission is not None:
            admission._active.clear()
        if owner is not None:
            try:
                owner.close()
            except Exception:
                pass
        # No observer/configuration failure changes action execution authority.
        return
