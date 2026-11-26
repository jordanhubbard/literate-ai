"""Operator-provisioning probe observations, never a lifecycle admission.

SOURCE WIP. Only an original explicitly acknowledged native build can
issue this context. A numeric push after canonical guardian allocation selects a
probe target; neither a receipt nor caller-selected PID can issue one. The probe
runs fixed framework code and has no Component/SDK/package authority.
"""

from __future__ import annotations

import json
import os
import threading
import time
import weakref
from dataclasses import dataclass, field
from datetime import datetime

from literate_ai.contracts.identity import canonical_identity

from .worker_telemetry_issuance import ObservationIssuance
from .worker_telemetry_native_build import CurrentNativeProviderBuild
from .worker_telemetry_wire import WorkerTelemetryWireError

_CONTEXT = object()
_RUNNER = object()
_TARGET = object()


def _refuse():
    raise WorkerTelemetryWireError("worker_telemetry.native_probe_unavailable")


@dataclass(frozen=True, slots=True, weakref_slot=True, repr=False)
class OriginalNativeProviderProbeTarget:
    _runner: object = field(repr=False)
    _build: object = field(repr=False)
    _guardian_pid: int = field(repr=False)
    _parent_pid: int = field(repr=False)
    _issuance: ObservationIssuance = field(repr=False)

    def __post_init__(self):
        if type(self._issuance) is not ObservationIssuance:
            _refuse()
        self._issuance.require_constructor(self, _TARGET)

    def require_current(self, *, rehash=True):
        self._issuance.require_original(self, _TARGET)
        runner = self._runner()
        build = self._build()
        if runner is None or build is None or os.getpid() != self._parent_pid:
            _refuse()
        runner.require_current()
        if rehash:
            build.require_artifact_current()
        else:
            build.require_current(rehash=False)
        runner.require_current()

    def __copy__(self):
        _refuse()

    def __deepcopy__(self, memo):
        _refuse()

    def __reduce__(self):
        _refuse()


@dataclass(frozen=True, slots=True, weakref_slot=True, repr=False)
class OriginalNativeProviderProbeRunner:
    _context: object = field(repr=False)
    _nonce: str = field(repr=False)
    _binding: str = field(repr=False)
    _thread: int = field(repr=False)
    _active: threading.Event = field(repr=False)
    _issuance: ObservationIssuance = field(repr=False)

    def __post_init__(self):
        if type(self._issuance) is not ObservationIssuance:
            _refuse()
        self._issuance.require_constructor(self, _RUNNER)

    def require_current(self):
        self._issuance.require_original(self, _RUNNER)
        if not self._active.is_set():
            _refuse()
        self._context.require_live()

    @property
    def binding(self):
        self.require_current()
        return self._binding

    def close(self):
        # Original executor invalidates the witness BEFORE native cleanup.
        self._active.clear()
        self._context._runner_ended(self)

    def __copy__(self):
        _refuse()

    def __deepcopy__(self, memo):
        _refuse()

    def __reduce__(self):
        _refuse()


class NativeProviderProbeFeed:
    """One actual operator probe, with no execution FD or control callback."""

    __slots__ = ("_values", "_issuance", "__weakref__")

    def __init__(self, build, expires_at, *, _issuer):
        if _issuer is not _CONTEXT or type(build) is not CurrentNativeProviderBuild:
            _refuse()
        build.require_current()
        if type(expires_at) is not datetime or expires_at.tzinfo is None:
            _refuse()
        receipt_identity = canonical_identity(json.loads(build.receipt)).to_dict()
        remaining = expires_at.timestamp() - time.time()
        if not 0 < remaining <= 30:
            _refuse()
        object.__setattr__(
            self,
            "_values",
            (
                weakref.ref(build),
                os.getpid(),
                threading.get_ident(),
                expires_at,
                time.monotonic() + remaining,
                threading.Event(),
                threading.Lock(),
                [None, None, False, None, False],
                receipt_identity,
            ),
        )
        object.__setattr__(self, "_issuance", ObservationIssuance(_CONTEXT))
        self._issuance.bind(self, _CONTEXT)

    def __setattr__(self, name, value):
        _refuse()

    def require_live(self):
        # Used by the original runner push: metadata only, no FS/import/thread
        # startup, source walk, sampling, or arbitrary callback under its lock.
        self._issuance.require_original(self, _CONTEXT)
        if (
            os.getpid() != self._values[1]
            or self._values[5].is_set()
            or time.monotonic() >= self._values[4]
        ):
            _refuse()
        build = self._values[0]()
        if build is None:
            _refuse()
        build.require_live()

    def require_current(self):
        self.require_live()
        self._values[0]().require_current(rehash=False)
        self.require_live()

    def begin_original_runner(self, nonce, expires_at):
        self.require_live()
        if (
            type(nonce) is not str
            or len(nonce) != 32
            or any(c not in "0123456789abcdef" for c in nonce)
            or threading.get_ident() != self._values[2]
            or expires_at != self._values[3]
            or not self._values[6].acquire(blocking=False)
        ):
            _refuse()
        try:
            state = self._values[7]
            if state[2]:
                _refuse()
            state[2] = True
            issuance = ObservationIssuance(_RUNNER)
            runner = OriginalNativeProviderProbeRunner(
                self,
                nonce,
                canonical_identity(
                    {
                        "schema": (
                            "literate-ai/original-native-provider-probe-binding@1"
                        ),
                        "nonce": nonce,
                        "build_receipt": self._values[8],
                        "parent_pid": self._values[1],
                        "started_monotonic_ns": time.monotonic_ns(),
                    }
                ).digest,
                threading.get_ident(),
                threading.Event(),
                issuance,
            )
            issuance.bind(runner, _RUNNER)
            runner._active.set()
            state[0] = weakref.ref(runner)
            return runner
        finally:
            self._values[6].release()

    def push(self, runner, observation, *, guardian_pid):
        self.require_live()
        if (
            type(runner) is not OriginalNativeProviderProbeRunner
            or runner._context is not self
            or threading.get_ident() != runner._thread
        ):
            _refuse()
        runner.require_current()
        if (
            type(guardian_pid) is not int
            or not 2 <= guardian_pid < 2**31
            or guardian_pid == os.getpid()
        ):
            _refuse()
        if (
            type(observation) is not dict
            or set(observation)
            != {"binding", "nonce", "sequence", "observed_at_ms", "monotonic_ns"}
            or observation["binding"] != runner._binding
            or observation["nonce"] != runner._nonce
            or any(
                type(observation[key]) is not int or not 0 < observation[key] < 2**63
                for key in ("sequence", "observed_at_ms", "monotonic_ns")
            )
            or not 0
            <= time.time_ns() // 1_000_000 - observation["observed_at_ms"]
            <= 30000
            or not 0
            <= time.monotonic_ns() - observation["monotonic_ns"]
            <= 30_000_000_000
        ):
            _refuse()
        if not self._values[6].acquire(blocking=False):
            return
        try:
            state = self._values[7]
            if state[0] is None or state[0]() is not runner:
                _refuse()
            # Canonical runner already verified private nonce/binding/frame and
            # actual kernel/reaper+child allocation before invoking this push.
            if state[3] is not None and observation["sequence"] <= state[3]:
                _refuse()
            state[3] = observation["sequence"]
            if state[1] is None:
                issuance = ObservationIssuance(_TARGET)
                target = OriginalNativeProviderProbeTarget(
                    weakref.ref(runner),
                    self._values[0],
                    guardian_pid,
                    self._values[1],
                    issuance,
                )
                issuance.bind(target, _TARGET)
                state[1] = target
        finally:
            self._values[6].release()

    def target(self):
        self.require_current()
        if not self._values[6].acquire(blocking=False):
            _refuse()
        try:
            target = self._values[7][1]
        finally:
            self._values[6].release()
        if target is None:
            return None
        target.require_current(rehash=False)
        return target

    def _runner_ended(self, runner):
        # Original executor invalidates before native cleanup. An ended channel
        # never becomes "not started" or issues another probe target.
        self._issuance.require_original(self, _CONTEXT)
        runner._issuance.require_original(runner, _RUNNER)
        if (
            runner._context is not self
            or runner._thread != threading.get_ident()
            or self._values[7][0] is None
            or self._values[7][0]() is not runner
        ):
            _refuse()
        self._values[7][4] = True

    def runner_ended(self):
        self.require_live()
        return self._values[7][4]

    def close(self):
        self._values[5].set()

    def __copy__(self):
        _refuse()

    def __deepcopy__(self, memo):
        _refuse()

    def __reduce__(self):
        _refuse()


def original_native_provider_probe(build, *, expires_at):
    """Production provisioner only; not called from any query/decoded receipt."""
    return NativeProviderProbeFeed(build, expires_at, _issuer=_CONTEXT)
