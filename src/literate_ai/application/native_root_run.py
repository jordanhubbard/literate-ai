"""One explicitly bounded local run lifetime, never restored from evidence.

This constraint grants no host-execution permission. The admitting CLI must keep
it around all authorized stages and propagate its remaining time to blocking
operations. Boundary checks alone do not preempt a blocked operation.
"""

from __future__ import annotations

import math
import os
import secrets
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Lock

from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.native_root_continuation import (
    NativeRootRunDeadline,
    NativeRootRunPolicy,
)


class NativeRootRunError(RuntimeError):
    def __init__(self, code: str):
        self.code = "native_root_run." + code
        super().__init__(self.code)


def _nanoseconds(clock: Callable[[], int]) -> int:
    value = clock()
    if type(value) is not int or value < 0:
        raise NativeRootRunError("clock_invalid")
    return value


def _seconds(value: object) -> float:
    if type(value) not in (int, float):
        raise NativeRootRunError("timeout_invalid")
    try:
        seconds = float(value)
    except OverflowError:
        raise NativeRootRunError("timeout_invalid") from None
    if not math.isfinite(seconds) or seconds <= 0:
        raise NativeRootRunError("timeout_invalid")
    return seconds


def _binding_uris(values: tuple[ContentIdentity, ...]) -> tuple[str, ...]:
    if any(type(identity) is not ContentIdentity for identity in values):
        raise NativeRootRunError("binding_invalid")
    for identity in values:
        identity.__post_init__()
    return tuple(identity.uri for identity in values)


class LiveNativeRootRun:
    """Opaque process-local lifetime. Closed projections remain ordinary data."""

    __slots__ = (
        "_seal",
        "_pid",
        "_lock",
        "_active",
        "_policy",
        "_policy_identity",
        "_deadline",
        "_deadline_identity",
        "_expires_monotonic_ns",
        "_last_monotonic_ns",
        "_utc_clock",
        "_monotonic_clock",
        "_check_current",
        "_upstream",
        "_bindings",
        "_original_binding_uris",
    )

    def __init__(self):
        raise TypeError("use open_native_root_run with an explicit reviewed policy")

    def __copy__(self):
        raise TypeError("a live native root run cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("a live native root run cannot be copied")

    def __reduce_ex__(self, protocol):
        raise TypeError("a live native root run cannot be serialized")

    def _require_owner(self):
        # Do not touch a lock inherited from another process or a copied holder.
        if self._seal is not self or self._pid != os.getpid():
            raise NativeRootRunError("owner_invalid")

    @property
    def deadline(self) -> NativeRootRunDeadline:
        return self._deadline

    @property
    def policy(self) -> NativeRootRunPolicy:
        return self._policy

    @property
    def bindings(self) -> tuple[ContentIdentity, ...]:
        """Original project-definition, framework and lifecycle-policy IDs."""
        return self._bindings

    def _local_remaining(self) -> float:
        self._require_owner()
        with self._lock:
            if not self._active:
                raise NativeRootRunError("closed")
            try:
                if self._policy.identity != self._policy_identity:
                    raise NativeRootRunError("policy_changed")
                if self._deadline.identity != self._deadline_identity:
                    raise NativeRootRunError("deadline_changed")
                if _binding_uris(self._bindings) != self._original_binding_uris:
                    raise NativeRootRunError("binding_changed")
                now = _nanoseconds(self._monotonic_clock)
                utc_now = _nanoseconds(self._utc_clock)
                if now < self._last_monotonic_ns:
                    raise NativeRootRunError("clock_regressed")
                self._last_monotonic_ns = now
                left = min(
                    self._expires_monotonic_ns - now,
                    self._deadline.expires_utc_ns - utc_now,
                )
                if left <= 0:
                    raise NativeRootRunError("expired")
                return left / 1_000_000_000
            except BaseException:
                self._active = False
                self._check_current = None
                self._upstream = None
                raise

    def remaining(self) -> float:
        local = self._local_remaining()
        upstream = self._upstream
        if upstream is None:
            return local
        try:
            # No external callback runs under the private lock. In particular an
            # upstream owner may itself check another admitted action lifetime.
            upstream_left = _seconds(upstream())
            return min(upstream_left, self._local_remaining())
        except BaseException:
            self.close()
            raise

    def require_current(self) -> None:
        self.remaining()
        check = self._check_current
        try:
            if check is None:
                raise NativeRootRunError("closed")
            check()
            self.remaining()
        except BaseException:
            self.close()
            raise

    def clamp_timeout(self, operation_limit: float) -> float:
        self._require_owner()
        try:
            return min(_seconds(operation_limit), self.remaining())
        except BaseException:
            self.close()
            raise

    def close(self) -> None:
        if self._seal is not self or self._pid != os.getpid():
            return
        with self._lock:
            self._active = False
            self._check_current = None
            self._upstream = None


_ACTIVE_NATIVE_ROOT_RUN: ContextVar[LiveNativeRootRun | None] = ContextVar(
    "literate_ai_native_root_run", default=None
)


def current_native_root_run() -> LiveNativeRootRun | None:
    """Return the active original constraint, never restore one from evidence."""
    owner = _ACTIVE_NATIVE_ROOT_RUN.get()
    if owner is not None:
        owner.require_current()
    return owner


def native_root_timeout(operation_limit: float) -> float:
    """Intersect an existing operation cap; no selection preserves its behavior."""
    owner = current_native_root_run()
    return operation_limit if owner is None else owner.clamp_timeout(operation_limit)


@contextmanager
def activate_native_root_run(owner: LiveNativeRootRun) -> Iterator[LiveNativeRootRun]:
    """Propagate the same live owner within this context; grant no host authority."""
    if type(owner) is not LiveNativeRootRun:
        raise NativeRootRunError("owner_invalid")
    previous = _ACTIVE_NATIVE_ROOT_RUN.get()
    if previous is not None and previous is not owner:
        raise NativeRootRunError("owner_mismatch")
    owner.require_current()
    token = _ACTIVE_NATIVE_ROOT_RUN.set(owner)
    try:
        yield owner
    finally:
        _ACTIVE_NATIVE_ROOT_RUN.reset(token)


@contextmanager
def open_native_root_run(
    policy: NativeRootRunPolicy,
    *,
    project_identity: ContentIdentity,
    framework_distribution_identity: ContentIdentity,
    lifecycle_policy_identity: ContentIdentity,
    require_current: Callable[[], None],
    original_remaining: Callable[[], float] | None = None,
    utc_clock: Callable[[], int] = time.time_ns,
    monotonic_clock: Callable[[], int] = time.monotonic_ns,
) -> Iterator[LiveNativeRootRun]:
    """Admit one explicit time constraint at the original command boundary.

    The original command's ordinary execution authorization remains mandatory.
    ``project_identity`` is its original ProjectDefinition identity; root
    preparation separately seals the approved project authority revision.
    ``original_remaining`` may tighten an already admitted action deadline;
    neither replacements nor decoded evidence may create a new run here.
    """
    if type(policy) is not NativeRootRunPolicy:
        raise NativeRootRunError("policy_invalid")
    # Revalidate the selected closed data; frozen instances must not allow a
    # caller's bypass of their original constructor checks to select a budget.
    NativeRootRunPolicy.from_dict(policy.to_dict())
    bindings = (
        project_identity,
        framework_distribution_identity,
        lifecycle_policy_identity,
    )
    original_binding_uris = _binding_uris(bindings)
    if not callable(require_current) or (
        original_remaining is not None and not callable(original_remaining)
    ):
        raise NativeRootRunError("callback_invalid")
    started = _nanoseconds(utc_clock)
    monotonic_started = _nanoseconds(monotonic_clock)
    duration_ns = policy.max_duration_seconds * 1_000_000_000
    if original_remaining is not None:
        numerator, denominator = _seconds(original_remaining()).as_integer_ratio()
        duration_ns = min(duration_ns, numerator * 1_000_000_000 // denominator)
    if duration_ns <= 0:
        raise NativeRootRunError("expired")
    owner = object.__new__(LiveNativeRootRun)
    owner._seal = owner
    owner._pid = os.getpid()
    owner._lock = Lock()
    owner._active = True
    owner._policy = policy
    owner._policy_identity = policy.identity
    owner._deadline = NativeRootRunDeadline(
        run_nonce=secrets.token_hex(16),
        policy_identity=policy.identity,
        started_utc_ns=started,
        expires_utc_ns=started + duration_ns,
    )
    owner._deadline_identity = owner._deadline.identity
    owner._expires_monotonic_ns = monotonic_started + duration_ns
    owner._last_monotonic_ns = monotonic_started
    owner._utc_clock = utc_clock
    owner._monotonic_clock = monotonic_clock
    owner._check_current = require_current
    owner._upstream = original_remaining
    owner._bindings = bindings
    owner._original_binding_uris = original_binding_uris
    try:
        owner.require_current()
        yield owner
    finally:
        owner.close()
