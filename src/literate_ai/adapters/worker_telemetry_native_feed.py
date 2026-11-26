"""Bounded push-only observations from an original protected native runner.

This feed owns no execution descriptor, PID, cancellation operation or cleanup
proof. Decoded guardian frames never construct a live owner. Only the original
runner's active context can update its one coalesced numeric snapshot.
"""

from __future__ import annotations

import os
import threading
import time
import weakref
from dataclasses import dataclass, field
from datetime import UTC, datetime

from literate_ai.contracts.identity import canonical_identity

from .worker_telemetry_issuance import ObservationIssuance
from .worker_telemetry_native_binding import CurrentNativeResourceProvider
from .worker_telemetry_wire import WorkerTelemetryWireError

_FEED_ISSUER = object()
_RUNNER_ISSUER = object()


def _refuse():
    raise WorkerTelemetryWireError("worker_telemetry.native_observation_unavailable")


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ActualNativeRunnerObservation:
    """Original-instance, context-local witness; never restored from a frame."""

    _feed: object = field(repr=False)
    _nonce: str = field(repr=False)
    _binding: str = field(repr=False)
    _pid: int = field(repr=False)
    _thread: int = field(repr=False)
    _active: threading.Event = field(repr=False)
    _issuance: ObservationIssuance = field(repr=False)

    def require_current(self):
        self._issuance.require_original(self, _RUNNER_ISSUER)
        if self._pid != os.getpid() or not self._active.is_set():
            _refuse()
        self._feed.require_current()

    @property
    def binding(self):
        self.require_current()
        return self._binding

    def close(self):
        # Invalidation precedes native cleanup. There is no execution operation.
        self._active.clear()

    def __copy__(self):
        _refuse()

    def __deepcopy__(self, memo):
        _refuse()

    def __reduce__(self):
        _refuse()


_TARGET_ISSUER = object()


@dataclass(frozen=True, slots=True, weakref_slot=True, repr=False)
class OriginalNativeResourceTarget:
    _runner: object = field(repr=False)
    _provider: object = field(repr=False)
    _guardian_pid: int = field(repr=False)
    _parent_pid: int = field(repr=False)
    _issuance: ObservationIssuance = field(repr=False)

    def __post_init__(self):
        if type(self._issuance) is not ObservationIssuance:
            _refuse()
        self._issuance.require_constructor(self, _TARGET_ISSUER)

    def require_current(self):
        self._issuance.require_original(self, _TARGET_ISSUER)
        runner = self._runner()
        if runner is None or self._parent_pid != os.getpid():
            _refuse()
        runner.require_current()
        if (
            runner._feed._admission._configuration.native_resources
            is not self._provider
        ):
            _refuse()
        scope = runner._feed._admission._configuration.scope
        now = time.time_ns() // 1_000_000
        if not scope.not_before_ms <= now < scope.expires_at_ms:
            _refuse()
        self._provider.require_current(rehash=False)

    def __copy__(self):
        _refuse()

    def __deepcopy__(self, memo):
        _refuse()

    def __reduce__(self):
        _refuse()


def _issue_original_native_target(runner, guardian_pid):
    """ONLY called from actual runner's validated private heartbeat path."""
    if (
        type(runner) is not ActualNativeRunnerObservation
        or type(runner._issuance) is not ObservationIssuance
    ):
        _refuse()
    runner._issuance.require_original(runner, _RUNNER_ISSUER)
    # push() already checked the actual parent fence BEFORE taking its tiny
    # nonblocking data lock. Do not repeat filesystem work under that lock.
    # This metadata-only issue grants no measurements; observer require_current
    # still proves the complete original lifetime before/after helper use.
    if (
        runner._pid != os.getpid()
        or not runner._active.is_set()
        or runner._feed._state[0] is None
        or runner._feed._state[0]() is not runner
        or runner._thread != threading.get_ident()
        or type(guardian_pid) is not int
        or not 2 <= guardian_pid < 2**31
        or guardian_pid == os.getpid()
    ):
        _refuse()
    provider = runner._feed._admission._configuration.native_resources
    if provider is None:
        return None
    if type(provider) is not CurrentNativeResourceProvider:
        _refuse()
    # No filesystem/hash work, helper launch, observer thread start or user callback
    # on the execution path. Full provider checks occur in the observer only.
    issuance = ObservationIssuance(_TARGET_ISSUER)
    target = OriginalNativeResourceTarget(
        weakref.ref(runner), provider, guardian_pid, os.getpid(), issuance
    )
    issuance.bind(target, _TARGET_ISSUER)
    return target


class ActualNativeObservationFeed:
    """One fixed-size latest observation, with no callback into user code."""

    __slots__ = ("_values", "_issuance", "__weakref__")

    def __init__(self, admission, *, _issuer):
        from .worker_telemetry_reservation import ActualProtectedReservationObservation

        if (
            _issuer is not _FEED_ISSUER
            or type(admission) is not ActualProtectedReservationObservation
        ):
            _refuse()
        admission.require_current()
        object.__setattr__(
            self,
            "_values",
            (
                admission,
                os.getpid(),
                threading.Lock(),
                threading.Event(),
                [None, None, None, None, False],
            ),
        )
        object.__setattr__(self, "_issuance", ObservationIssuance(_FEED_ISSUER))
        self._issuance.bind(self, _FEED_ISSUER)

    def __setattr__(self, name, value):
        _refuse()

    @property
    def _admission(self):
        return self._values[0]

    @property
    def _pid(self):
        return self._values[1]

    @property
    def _lock(self):
        return self._values[2]

    @property
    def _closed(self):
        return self._values[3]

    @property
    def _state(self):
        return self._values[4]

    def require_current(self):
        self._issuance.require_original(self, _FEED_ISSUER)
        if self._pid != os.getpid() or self._closed.is_set():
            _refuse()
        self._admission.require_current()

    def begin_original_runner(self, nonce, expires_at):
        self.require_current()
        if (
            type(nonce) is not str
            or len(nonce) != 32
            or any(c not in "0123456789abcdef" for c in nonce)
            or expires_at != self._admission.deadline.expires_at
        ):
            _refuse()
        if not self._lock.acquire(blocking=False):
            _refuse()
        try:
            # One actual runner per original reservation. An ended runner is not
            # reusable for another execution under the same observation owner.
            if self._state[0] is not None:
                _refuse()
            active = threading.Event()
            active.set()
            binding = canonical_identity(
                {
                    "schema": "literate-ai/actual-native-observation-binding@1",
                    "reservation_identity": (
                        self._admission.reservation_identity.to_dict()
                    ),
                    "operation_identity": self._admission.request.identity.to_dict(),
                    "native_nonce": nonce,
                }
            ).digest
            issuance = ObservationIssuance(_RUNNER_ISSUER)
            runner = ActualNativeRunnerObservation(
                self,
                nonce,
                binding,
                os.getpid(),
                threading.get_ident(),
                active,
                issuance,
            )
            issuance.bind(runner, _RUNNER_ISSUER)
            self._state[0] = weakref.ref(runner)
            return runner
        finally:
            self._lock.release()

    def push(self, runner, frame, *, guardian_pid=None):
        """Called only by the original reader of its private guardian pipe.

        No arbitrary callable runs here, and contention discards an observation
        rather than waiting on execution, result, or cleanup locks. The caller
        has already bounded/validated the frame against its actual guardian.
        """
        if type(runner) is not ActualNativeRunnerObservation:
            _refuse()
        runner.require_current()
        if (
            runner._feed is not self
            or self._state[0]() is not runner
            or runner._thread != threading.get_ident()
        ):
            _refuse()
        if (
            type(frame) is not dict
            or set(frame)
            != {"binding", "nonce", "sequence", "observed_at_ms", "monotonic_ns"}
            or frame["binding"] != runner._binding
            or frame["nonce"] != runner._nonce
            or any(
                type(frame[name]) is not int or not 0 < frame[name] <= 2**63 - 1
                for name in ("sequence", "observed_at_ms", "monotonic_ns")
            )
        ):
            _refuse()
        now = int(datetime.now(UTC).timestamp() * 1000)
        if not 0 <= now - frame["observed_at_ms"] <= 30000:
            _refuse()
        if not 0 <= time.monotonic_ns() - frame["monotonic_ns"] <= 30_000_000_000:
            _refuse()
        if not self._lock.acquire(blocking=False):
            return
        try:
            if self._state[1] is not None and frame["sequence"] <= self._state[1][0]:
                _refuse()
            self._state[1] = (
                frame["sequence"],
                frame["observed_at_ms"],
                frame["monotonic_ns"],
            )
            if (
                self._state[2] is None
                and self._admission._configuration.native_resources is not None
            ):
                self._state[2] = _issue_original_native_target(runner, guardian_pid)
        finally:
            self._lock.release()

    def snapshot(self):
        self.require_current()
        if self._state[0] is None:
            return None
        runner = self._state[0]()
        if runner is None:
            _refuse()
        runner.require_current()
        if not self._lock.acquire(blocking=False):
            _refuse()
        try:
            value = self._state[1]
        finally:
            self._lock.release()
        runner.require_current()
        if value is None:
            _refuse()
        return runner._binding, value

    def claim_resource_sampler(self):
        # Called only in the separate observer thread, never execution/query.
        self.require_current()
        if not self._lock.acquire(blocking=False):
            raise WorkerTelemetryWireError("worker_telemetry.observation_overloaded")
        try:
            if self._state[4]:
                return False
            self._state[4] = True
            return True
        finally:
            self._lock.release()

    def resource_target(self):
        self.require_current()
        if not self._lock.acquire(blocking=False):
            _refuse()
        try:
            target = self._state[2]
        finally:
            self._lock.release()
        if target is not None:
            target.require_current()
        return target

    def push_resources(self, target, measurement):
        from .worker_telemetry_native_measurement import NativeResourceMeasurement

        self.require_current()
        if (
            type(target) is not OriginalNativeResourceTarget
            or type(measurement) is not NativeResourceMeasurement
            or self._admission._configuration.native_resources is not target._provider
            or measurement.provider_identity != target._provider.identity
        ):
            _refuse()
        target.require_current()
        if not self._lock.acquire(blocking=False):
            return
        try:
            if self._state[2] is not target:
                _refuse()
            self._state[3] = measurement
        finally:
            self._lock.release()
        target.require_current()

    def resource_snapshot(self):
        target = self.resource_target()
        if target is None:
            return None
        if not self._lock.acquire(blocking=False):
            _refuse()
        try:
            measurement = self._state[3]
        finally:
            self._lock.release()
        target.require_current()
        return measurement

    def close(self):
        self._closed.set()

    def __copy__(self):
        _refuse()

    def __deepcopy__(self, memo):
        _refuse()

    def __reduce__(self):
        _refuse()


def new_actual_native_feed(admission):
    return ActualNativeObservationFeed(admission, _issuer=_FEED_ISSUER)
