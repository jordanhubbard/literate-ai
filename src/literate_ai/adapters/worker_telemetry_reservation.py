"""Original protected-parent observations; marker bytes cannot issue this view.

Only the canonical reservation context calls the optional issuer after exclusive
creation. The view holds a weak reference, never an execution descriptor/lease.
It observes reservation provenance, not native launch, admission or completion.
"""

from __future__ import annotations

import os
import threading
import weakref
from contextlib import contextmanager
from dataclasses import dataclass, field

from literate_ai.application.action_dag_scheduler import LifecycleActionDispatchRequest
from literate_ai.contracts.identity import ContentIdentity, canonical_identity

from .action_dispatch_wire import ActionDispatchDeadline, record_identity
from .worker_telemetry_configuration import CurrentWorkerTelemetryConfiguration
from .worker_telemetry_issuance import ObservationIssuance
from .worker_telemetry_wire import WorkerTelemetryWireError

_PARENT_ISSUER = object()


def _refuse():
    raise WorkerTelemetryWireError("worker_telemetry.protected_parent_unavailable")


def _signature(node):
    return (
        node.st_dev,
        node.st_ino,
        node.st_mode,
        node.st_uid,
        node.st_gid,
        node.st_nlink,
        node.st_size,
        node.st_mtime_ns,
        node.st_ctime_ns,
    )


@dataclass(frozen=True, slots=True, weakref_slot=True, repr=False)
class ActualProtectedReservationObservation:
    """Original actual parent view, never a restored reservation or grant."""

    request: object
    deadline: ActionDispatchDeadline
    reservation_identity: ContentIdentity
    _configuration: CurrentWorkerTelemetryConfiguration = field(repr=False)
    _parent: object = field(repr=False)
    _values: tuple = field(repr=False)
    _descriptor_signature: tuple = field(repr=False)
    _pid: int
    _active: threading.Event = field(repr=False)
    _issuance: ObservationIssuance = field(repr=False)

    def __post_init__(self):
        if (
            type(self._issuance) is not ObservationIssuance
            or type(self.request) is not LifecycleActionDispatchRequest
            or type(self.deadline) is not ActionDispatchDeadline
            or type(self.reservation_identity) is not ContentIdentity
        ):
            _refuse()
        self._issuance.require_constructor(self, _PARENT_ISSUER)

    def require_current(self):
        if not self._active.is_set() or os.getpid() != self._pid:
            _refuse()
        self._issuance.require_original(self, _PARENT_ISSUER)
        self.deadline.remaining()
        parent = self._parent()
        if parent is None:
            _refuse()
        expected_path, registration, nonce, content, descriptor, context = self._values

        def require_parent():
            if (
                parent.request is not self.request
                or parent.path != expected_path
                or parent.registration != registration
                or parent.pid != self._pid
                or parent.nonce != nonce
                or parent.content != content
                or parent.descriptor != descriptor
                or parent.released
                or parent._observation_context is not context
                or _signature(os.fstat(descriptor)) != self._descriptor_signature
            ):
                _refuse()
            parent.require_actual_observation_context()

        require_parent()
        parent.require_current()
        # Full configured inputs/code bracket authenticated contributions and
        # final collector output. Idle polling checks only this actual original
        # parent fence; it must not rehash whole source/config every50ms.
        require_parent()
        if (
            not self._active.is_set()
            or os.getpid() != self._pid
            or _signature(os.fstat(descriptor)) != self._descriptor_signature
        ):
            _refuse()
        self.deadline.remaining()

    def __copy__(self):
        raise TypeError("protected parent observations cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("protected parent observations cannot be copied")

    def __reduce__(self):
        raise TypeError("protected parent observations cannot be restored")


def _issue(publisher, parent, deadline, active):
    from .retained_receiver_attempt import _OwnedReceiverAttempt
    from .worker_telemetry_owner import ConfiguredWorkerTelemetryPublisher

    if (
        type(publisher) is not ConfiguredWorkerTelemetryPublisher
        or type(parent) is not _OwnedReceiverAttempt
        or type(deadline) is not ActionDispatchDeadline
    ):
        _refuse()
    publisher._require_local()
    configuration = publisher._configuration
    configured = configuration.protected_parent_configuration
    if (
        configured is None
        or configuration.protected_parent_identity != parent.registration
        or parent.path != configured.with_name(configured.name + ".attempt")
        or parent.pid != os.getpid()
        or parent.request.deadline_identity != deadline.identity
    ):
        _refuse()
    parent.require_actual_observation_context()
    parent.require_current()
    configuration.require_current(deadline=deadline)
    values = (
        parent.path,
        parent.registration,
        parent.nonce,
        parent.content,
        parent.descriptor,
        parent._observation_context,
    )
    identity = canonical_identity(
        {
            "schema": "literate-ai/actual-protected-parent-observation@1",
            "request_identity": parent.request.identity.to_dict(),
            "registration_identity": parent.registration.to_dict(),
            "marker_identity": record_identity(parent.content).to_dict(),
        }
    )
    issuance = ObservationIssuance(_PARENT_ISSUER)
    observed = ActualProtectedReservationObservation(
        parent.request,
        deadline,
        identity,
        configuration,
        weakref.ref(parent),
        values,
        _signature(os.fstat(parent.descriptor)),
        os.getpid(),
        active,
        issuance,
    )
    issuance.bind(observed, _PARENT_ISSUER)
    observed.require_current()
    return observed


@contextmanager
def observe_protected_receiver_attempt(publisher, parent, deadline):
    """Optional observer registration cannot change actual attempt execution.

    Active provenance ends before the canonical context closes its descriptor.
    Nothing here releases, renews, cancels or interprets native cleanup evidence.
    """
    if publisher is None:
        yield
        return
    active = None
    owner = None
    try:
        active = threading.Event()
        active.set()
        observed = _issue(publisher, parent, deadline, active)
        owner = publisher.start_actual_protected_operation(observed)
    except Exception:
        if active is not None:
            try:
                active.clear()
            except Exception:
                pass
        active = None
    try:
        yield
    finally:
        if active is not None:
            try:
                active.clear()
            except Exception:
                pass
        if owner is not None:
            try:
                owner.close()
            except Exception:
                pass


@contextmanager
def optional_protected_telemetry_publisher(configuration_path):
    """Optional observer startup never acts on execution ownership or outcome."""
    publisher = relay = None
    if configuration_path is not None:
        try:
            from .worker_telemetry_owner import open_worker_telemetry_publisher
            from .worker_telemetry_relay import start_worker_telemetry_relay

            publisher = open_worker_telemetry_publisher(configuration_path)
            if publisher._configuration.protected_parent_configuration is None:
                _refuse()
            relay = start_worker_telemetry_relay(publisher)
        except Exception:
            publisher = None
    try:
        yield publisher
    finally:
        if relay is not None:
            try:
                relay.close()
            except Exception:
                pass
        if publisher is not None:
            try:
                publisher.close()
            except Exception:
                pass
