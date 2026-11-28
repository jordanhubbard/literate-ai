"""Actual operation-local observation owners; historical records cannot reopen them.

The separate authenticated relay exposes only actual operation observations.
Generic processing is queued/unprotected; original protected parent provenance
is explicit and still does not prove native launch or completion. Native metrics
remain unsupported until exact containment attribution is supplied.
"""

from __future__ import annotations

import os
import secrets
import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.worker_telemetry_v2 import (
    MAX_OPERATIONS,
    METRIC_NAMES,
    TelemetryMetric,
    TelemetryMetricScope,
    TelemetryMetricStatus,
    TelemetryReason,
    TelemetrySampleSource,
    TelemetryStage,
    TelemetryState,
    WorkerTelemetrySample,
)

from .action_dispatch_wire import ActionDispatchDeadline
from .worker_telemetry_configuration import (
    CurrentWorkerTelemetryConfiguration,
    load_worker_telemetry_configuration,
)
from .worker_telemetry_context import ActualOperationObservation
from .worker_telemetry_process import SpawnedProcessObservation
from .worker_telemetry_reservation import ActualProtectedReservationObservation
from .worker_telemetry_wire_v2 import WorkerTelemetryWireError

_OWNER_SEAL = object()
_PUBLISHER_SEAL = object()


def _refuse(code):
    raise WorkerTelemetryWireError("worker_telemetry." + code)


class LiveWorkerTelemetryOwner:
    """Readonly access to one actual active receiver operation, never a decoder."""

    def __init__(self, admission, registration_identity, *, _seal):
        if _seal is not _OWNER_SEAL or type(admission) not in {
            ActualOperationObservation,
            ActualProtectedReservationObservation,
        }:
            _refuse("live_owner_required")
        admission.require_current()
        self._admission = admission
        self._pid = os.getpid()
        self._closed = threading.Event()
        self._ambiguous = threading.Event()
        self._lock = threading.Lock()  # Observation data only; never an action lock.
        self._observations = {}
        self._sequence = 0
        self._announcement = None
        self._publishable = False
        self._native_feed = None
        if type(admission) is ActualProtectedReservationObservation:
            from .worker_telemetry_native_feed import new_actual_native_feed

            self._native_feed = new_actual_native_feed(admission)
        provenance = (
            {"measured_capability_identity": admission.measured_capability.to_dict()}
            if type(admission) is ActualOperationObservation
            else {"reservation_identity": admission.reservation_identity.to_dict()}
        )
        self._identity = canonical_identity(
            {
                "schema": "literate-ai/actual-worker-observation-owner-epoch@1",
                "registration_identity": registration_identity.to_dict(),
                "actual_request_identity": admission.request.identity.to_dict(),
                **provenance,
                "receiver_pid": self._pid,
                "nonce": secrets.token_hex(32),
                "started_monotonic_ns": time.monotonic_ns(),
            }
        )
        self._counter_epoch = canonical_identity(
            {
                "schema": "literate-ai/unavailable-worker-counter-epoch@1",
                "owner_epoch": self._identity.to_dict(),
            }
        )
        self._seal = _seal

    @property
    def action_identity(self):
        return self._admission.request.action.identity

    @property
    def operation_identity(self):
        return self._admission.request.identity

    def require_open(self):
        if (
            self._seal is not _OWNER_SEAL
            or self._pid != os.getpid()
            or self._closed.is_set()
            or not self._publishable
        ):
            _refuse("owner_unavailable")
        if self._ambiguous.is_set():
            _refuse("owner_ambiguous")
        self._admission.require_current()

    def record_process_observation(self, process):
        """Receive only readonly tokens from actual spawn, without waiting."""
        self.require_open()
        if type(process) is not SpawnedProcessObservation:
            _refuse("actual_process_observation_required")
        if not self._lock.acquire(blocking=False):
            return
        try:
            if len(self._observations) < 64:
                self._observations.setdefault(process.epoch, process)
        finally:
            self._lock.release()
        # No process-only CPU/RSS is advertised as a complete action subtree.

    def sample(self, *, request=None):
        self.require_open()
        if not self._lock.acquire(blocking=False):
            _refuse("observation_overloaded")
        try:
            self._sequence += 1
            sequence = self._sequence
        finally:
            self._lock.release()
        kind = self._admission.request.action.kind.value
        stage = (
            TelemetryStage(kind)
            if kind in {item.value for item in TelemetryStage}
            else TelemetryStage.UNKNOWN
        )
        observed_at_ms = int(datetime.now(UTC).timestamp() * 1000)
        monotonic_ns = time.monotonic_ns()
        state = TelemetryState.QUEUED
        source = TelemetrySampleSource.FRESH
        counter_epoch = self._counter_epoch
        interval_started_monotonic_ns = None
        if self._native_feed is not None:
            # Reading/waiting occurs only in the separate observation service.
            # The actual execution runner only pushes into a nonblocking slot.
            until = time.monotonic() + 2
            while True:
                self.require_open()
                try:
                    native = self._native_feed.snapshot()
                except WorkerTelemetryWireError:
                    state = TelemetryState.UNKNOWN
                    break
                if native is None:
                    break
                binding, (_native_sequence, wall, monotonic) = native
                if request is not None and wall < request.issued_at_ms:
                    if request.allow_cached_observations:
                        source = TelemetrySampleSource.CACHED
                    else:
                        if (
                            time.monotonic() >= until
                            or int(datetime.now(UTC).timestamp() * 1000)
                            >= request.expires_at_ms
                        ):
                            _refuse("native_observation_unavailable")
                        self._closed.wait(0.05)
                        continue
                observed_at_ms, monotonic_ns = wall, monotonic
                state = TelemetryState.RUNNING
                counter_epoch = canonical_identity(
                    {
                        "schema": "literate-ai/native-worker-counter-epoch@1",
                        "binding": binding,
                    }
                )
                break
        metrics = self._resource_metrics(None)
        provider = (
            self._admission._configuration.native_resources
            if type(self._admission) is ActualProtectedReservationObservation
            else None
        )
        if provider is not None and state is TelemetryState.RUNNING:
            while True:
                self.require_open()
                try:
                    measurement = self._native_feed.resource_snapshot()
                except WorkerTelemetryWireError:
                    state = TelemetryState.UNKNOWN
                    break
                now = int(datetime.now(UTC).timestamp() * 1000)
                if (
                    measurement is not None
                    and 0 <= now - measurement.observed_at_ms <= 30000
                    and (
                        request is None
                        or measurement.observed_at_ms >= request.issued_at_ms
                        or (
                            request.allow_cached_observations
                            and measurement.observed_at_ms
                            >= request.issued_at_ms - request.maximum_sample_age_ms
                        )
                    )
                ):
                    observed_at_ms = measurement.observed_at_ms
                    monotonic_ns = measurement.monotonic_ns
                    counter_epoch = measurement.counter_epoch
                    interval_started_monotonic_ns = (
                        measurement.interval_started_monotonic_ns
                    )
                    source = (
                        TelemetrySampleSource.CACHED
                        if request is not None and observed_at_ms < request.issued_at_ms
                        else TelemetrySampleSource.COALESCED
                    )
                    metrics = self._resource_metrics(measurement)
                    break
                if time.monotonic() >= until or (
                    request is not None and now >= request.expires_at_ms
                ):
                    break
                self._closed.wait(0.05)
            # A sample read before native completion must not retain a RUNNING
            # label/counters if the original runner ended during observation.
            if state is TelemetryState.RUNNING:
                try:
                    self._native_feed.snapshot()
                except WorkerTelemetryWireError:
                    state = TelemetryState.UNKNOWN
                    metrics = self._resource_metrics(None)
                    interval_started_monotonic_ns = None
        sample = WorkerTelemetrySample(
            self.operation_identity,
            self.action_identity,
            self._identity,
            counter_epoch,
            source,
            interval_started_monotonic_ns,
            sequence,
            observed_at_ms,
            monotonic_ns,
            stage,
            # The generic hook proves an actual processing request, not its
            # later worker-specific execution/reservation admission.
            state,
            None,
            metrics,
            self._admission.reservation_identity,
        )
        self.require_open()
        return sample

    def _resource_metrics(self, measurement):
        provider = (
            self._admission._configuration.native_resources
            if type(self._admission) is ActualProtectedReservationObservation
            else None
        )
        measured = (
            {
                "cpu_time_ns": measurement.cpu_time_ns,
                "cpu_utilization_basis_points": (
                    measurement.cpu_utilization_basis_points
                ),
                "memory_resident_bytes": measurement.memory_resident_bytes,
            }
            if measurement is not None
            else {}
        )
        result = []
        for name in METRIC_NAMES:
            if provider is not None and name in {
                "cpu_time_ns",
                "cpu_utilization_basis_points",
                "memory_resident_bytes",
            }:
                value = measured.get(name)
                result.append(
                    TelemetryMetric(
                        name,
                        TelemetryMetricScope.ACTION_SUBTREE,
                        TelemetryMetricStatus.MEASURED
                        if value is not None
                        else TelemetryMetricStatus.UNAVAILABLE,
                        value,
                        None
                        if value is not None
                        else TelemetryReason.NATIVE_COUNTER_UNAVAILABLE,
                    )
                )
            else:
                result.append(
                    TelemetryMetric(
                        name,
                        TelemetryMetricScope.UNAVAILABLE,
                        TelemetryMetricStatus.UNSUPPORTED
                        if provider is None
                        else TelemetryMetricStatus.UNAVAILABLE,
                        None,
                        TelemetryReason.ATTRIBUTION_UNSUPPORTED
                        if provider is None
                        else TelemetryReason.NATIVE_COUNTER_UNAVAILABLE,
                    )
                )
        return tuple(result)

    def close(self):
        # Execution/result publication never joins collectors or takes their lock.
        self._closed.set()
        if self._native_feed is not None:
            self._native_feed.close()

    def __copy__(self):
        _refuse("live_owner_not_copyable")

    def __deepcopy__(self, memo):
        _refuse("live_owner_not_copyable")

    def __reduce__(self):
        _refuse("live_owner_not_restorable")


class ConfiguredWorkerTelemetryPublisher:
    """Configured receiver-only registry; its query methods have no job controls."""

    def __init__(self, configuration, *, _seal):
        if (
            _seal is not _PUBLISHER_SEAL
            or type(configuration) is not CurrentWorkerTelemetryConfiguration
            or configuration.role != "receiver"
        ):
            _refuse("current_receiver_configuration_required")
        self._configuration = configuration
        self._pid = os.getpid()
        self._seal = _seal
        self._owners = {}
        self._lock = threading.Lock()
        self._closed = False
        self._epoch = canonical_identity(
            {
                "schema": "literate-ai/actual-worker-observation-receiver-epoch@1",
                "registration_identity": configuration.registration_identity.to_dict(),
                "nonce": secrets.token_hex(32),
            }
        )
        from .worker_telemetry_claims import ConfiguredOwnerAnnouncements

        # Pre-open only observation descriptors before any actual owner can be
        # issued. Foreground failures can poison without allocating descriptors.
        self._announcements = ConfiguredOwnerAnnouncements(configuration)

    def _require_local(self):
        if (
            self._seal is not _PUBLISHER_SEAL
            or self._pid != os.getpid()
            or self._closed
        ):
            _refuse("actual_receiver_required")
        self._announcements.require_healthy()

    def start_actual_operation(self, admission):
        if self._configuration.protected_parent_configuration is not None:
            _refuse("protected_parent_required")
        if type(admission) is not ActualOperationObservation:
            _refuse("actual_operation_required")
        return self._start(admission)

    def start_actual_protected_operation(self, admission):
        if (
            type(admission) is not ActualProtectedReservationObservation
            or admission._configuration is not self._configuration
        ):
            _refuse("protected_parent_required")
        return self._start(admission)

    def _start(self, admission):
        self._require_local()
        admission.require_current()
        scope = self._configuration.scope
        worker = admission.request.worker
        if (
            worker.worker_id != scope.worker_id
            or worker.worker_identity != scope.worker_identity
            or worker.catalog_identity != scope.catalog_identity
            or admission.request.identity not in scope.operation_identities
            or not scope.not_before_ms
            <= int(datetime.now(UTC).timestamp() * 1000)
            < scope.expires_at_ms
        ):
            _refuse("actual_operation_scope_mismatch")
        announcement_failed = False
        try:
            if not self._lock.acquire(blocking=False):
                _refuse("observation_overloaded")
            try:
                identity = admission.request.identity
                previous = self._owners.get(identity)
                if previous is not None:
                    previous._ambiguous.set()
                    _refuse("owner_ambiguous")
                if len(self._owners) >= MAX_OPERATIONS:
                    _refuse("owner_limit")
                owner = LiveWorkerTelemetryOwner(
                    admission,
                    self._configuration.registration_identity,
                    _seal=_OWNER_SEAL,
                )
                try:
                    owner._announcement = self._announcements.announce(self, owner)
                except BaseException:
                    # announce already attempted its one independent poison
                    # write, including an explicit failure to publish that fact.
                    announcement_failed = True
                    raise
                owner._publishable = True
                self._owners[identity] = owner
                return owner
            finally:
                self._lock.release()
        except BaseException:
            # Never silently discard a genuine but unannounced duplicate. This
            # monotonic byte write is independent of every contended claim lock.
            # An I/O failure remains explicit observation unavailability; it is
            # not represented as successful cross-process conflict publication.
            if not announcement_failed:
                self._announcements.poison_operation(admission.request.identity)
            raise

    def close(self):
        if self._seal is not _PUBLISHER_SEAL or self._pid != os.getpid():
            _refuse("actual_receiver_required")
        self._closed = True
        try:
            for owner in self._owners.values():
                try:
                    owner.close()
                except Exception:
                    pass
        finally:
            try:
                self._announcements.close()
            except Exception:
                pass  # Observation-only cleanup cannot replace a job outcome.

    def respond(self, raw: bytes) -> bytes:
        """Use the same global custody/ambiguity checks as the private receiver.

        An in-memory registry is not a separate route around duplicate publisher
        refusal. Only actual background services can answer fresh challenges.
        """
        self._require_local()
        from .worker_telemetry_relay import collect_worker_telemetry

        with collect_worker_telemetry(raw, self._configuration) as (frame, _deadline):
            return frame

    def native_feed_for_actual_parent(self, parent):
        """Hand the original parent only its already-issued observation feed."""
        self._require_local()
        if not self._lock.acquire(blocking=False):
            _refuse("observation_overloaded")
        try:
            owner = self._owners.get(parent.request.identity)
            if (
                owner is None
                or type(owner._admission) is not ActualProtectedReservationObservation
                or owner._admission._parent() is not parent
            ):
                _refuse("protected_parent_required")
            owner.require_open()
            return owner._native_feed
        finally:
            self._lock.release()

    def __copy__(self):
        _refuse("actual_receiver_not_copyable")

    def __deepcopy__(self, memo):
        _refuse("actual_receiver_not_copyable")

    def __reduce__(self):
        _refuse("actual_receiver_not_restorable")


def open_worker_telemetry_publisher(configuration_path: Path):
    """Explicit private operator startup, separate from action capability checks."""
    configuration = load_worker_telemetry_configuration(
        configuration_path,
        role="receiver",
        deadline=ActionDispatchDeadline(datetime.now(UTC) + timedelta(seconds=30)),
    )
    return ConfiguredWorkerTelemetryPublisher(configuration, _seal=_PUBLISHER_SEAL)
