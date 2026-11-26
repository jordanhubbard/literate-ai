"""Bounded numeric transport, NOT owner/admission issuance.

The canonical original-runner integration must independently prove actual Job
assignment and current operation authority before attaching this feed. These
objects alone carry no authorization and are not accepted by any current owner.
"""

from __future__ import annotations

import os
import threading
import weakref
from dataclasses import dataclass, field

from literate_ai.adapters.worker_telemetry_issuance import ObservationIssuance

_WRITER = object()
_FEED = object()
_MAX_CPU_NS = 2**63 - 1


class NumericFeedUnavailable(ValueError):
    def __init__(self) -> None:
        super().__init__("worker_telemetry.windows_job_observation_unavailable")


@dataclass(frozen=True, slots=True)
class NumericJobSample:
    epoch: str
    monotonic_started_ns: int
    monotonic_ended_ns: int
    observed_at_ms: int
    cpu_time_ns: int
    job_reported_total_processes: int
    job_reported_active_processes: int


@dataclass(frozen=True, slots=True, weakref_slot=True, repr=False)
class OriginalNumericWriter:
    _feed: object = field(repr=False)
    _pid: int
    _thread: int
    _active: threading.Event = field(repr=False)
    _issuance: ObservationIssuance = field(repr=False)

    def __post_init__(self):
        if type(self._issuance) is not ObservationIssuance:
            raise NumericFeedUnavailable()
        self._issuance.require_constructor(self, _WRITER)

    def require_original(self):
        self._issuance.require_original(self, _WRITER)
        if (
            os.getpid() != self._pid
            or threading.get_ident() != self._thread
            or not self._active.is_set()
        ):
            raise NumericFeedUnavailable()

    def close(self):
        # Invalidation is independent of feed-lock health and occurs before the
        # runner's actual Job termination/release. The observer holds no handles.
        self._issuance.require_original(self, _WRITER)
        if os.getpid() != self._pid or threading.get_ident() != self._thread:
            raise NumericFeedUnavailable()
        self._active.clear()

    def __copy__(self):
        raise NumericFeedUnavailable()

    def __deepcopy__(self, memo):
        raise NumericFeedUnavailable()

    def __reduce__(self):
        raise NumericFeedUnavailable()


class NumericJobFeed:
    """One latest sample; no process/kernel reference or arbitrary callback."""

    __slots__ = ("_values", "_issuance", "__weakref__")

    def __init__(self, *, epoch: str):
        if (
            type(epoch) is not str
            or len(epoch) != 64
            or any(character not in "0123456789abcdef" for character in epoch)
        ):
            raise NumericFeedUnavailable()
        # The future actual runner prepares the opaque epoch before spawning.
        # It binds that value to its original operation and Job witness outside
        # this fact-only feed; a caller-supplied epoch is never live authority.
        object.__setattr__(
            self,
            "_values",
            (epoch, os.getpid(), threading.get_ident(), threading.Lock(), [None, None]),
        )
        object.__setattr__(self, "_issuance", ObservationIssuance(_FEED))
        self._issuance.bind(self, _FEED)

    def __setattr__(self, name, value):
        raise NumericFeedUnavailable()

    def _original(self):
        self._issuance.require_original(self, _FEED)
        if self._values[1] != os.getpid():
            raise NumericFeedUnavailable()

    @property
    def epoch(self):
        self._original()
        return self._values[0]

    def begin_original_writer(self):
        self._original()
        if self._values[2] != threading.get_ident():
            raise NumericFeedUnavailable()
        lock, state = self._values[3:]
        if not lock.acquire(blocking=False):
            raise NumericFeedUnavailable()
        try:
            if state[0] is not None:
                raise NumericFeedUnavailable()
            active = threading.Event()
            active.set()
            issuance = ObservationIssuance(_WRITER)
            writer = OriginalNumericWriter(
                self, os.getpid(), threading.get_ident(), active, issuance
            )
            issuance.bind(writer, _WRITER)
            state[0] = weakref.ref(writer)
            return writer
        finally:
            lock.release()

    def push(self, writer, sample):
        self._original()
        if type(writer) is not OriginalNumericWriter:
            raise NumericFeedUnavailable()
        writer.require_original()
        if writer._feed is not self or type(sample) is not NumericJobSample:
            raise NumericFeedUnavailable()
        if (
            sample.epoch != self._values[0]
            or type(sample.monotonic_started_ns) is not int
            or type(sample.monotonic_ended_ns) is not int
            or type(sample.observed_at_ms) is not int
            or not 0 <= sample.observed_at_ms <= _MAX_CPU_NS
            or type(sample.cpu_time_ns) is not int
            or type(sample.job_reported_total_processes) is not int
            or type(sample.job_reported_active_processes) is not int
            or not 0
            <= sample.monotonic_started_ns
            <= sample.monotonic_ended_ns
            <= _MAX_CPU_NS
            or not 0 <= sample.cpu_time_ns <= _MAX_CPU_NS
            or not 0
            <= sample.job_reported_active_processes
            <= sample.job_reported_total_processes
            <= 2**32 - 1
        ):
            raise NumericFeedUnavailable()
        lock, state = self._values[3:]
        if not lock.acquire(blocking=False):
            return False
        try:
            if state[0] is None or state[0]() is not writer:
                raise NumericFeedUnavailable()
            previous = state[1]
            if previous is not None and (
                sample.monotonic_started_ns < previous.monotonic_ended_ns
                or sample.cpu_time_ns < previous.cpu_time_ns
                or sample.job_reported_total_processes
                < previous.job_reported_total_processes
            ):
                # Never silently establish another counter epoch on regression.
                writer._active.clear()
                raise NumericFeedUnavailable()
            state[1] = sample
            return True
        finally:
            lock.release()

    def snapshot(self):
        self._original()
        lock, state = self._values[3:]
        if not lock.acquire(blocking=False):
            raise NumericFeedUnavailable()
        try:
            if state[0] is None:
                return None  # Precisely never begun, not an ended writer.
            writer = state[0]()
            if writer is None or not writer._active.is_set() or state[1] is None:
                raise NumericFeedUnavailable()
            writer._issuance.require_original(writer, _WRITER)
            return state[1]
        finally:
            lock.release()

    def __copy__(self):
        raise NumericFeedUnavailable()

    def __deepcopy__(self, memo):
        raise NumericFeedUnavailable()

    def __reduce__(self):
        raise NumericFeedUnavailable()
