"""Original-runner observation targets and an independent bounded sampler.

No query chooses a PID or starts a sampler. The actual native runner supplies
one target after its private kernel heartbeat. A separate observation service
starts sampling without execution/result locks, control handles, or joins.
"""

from __future__ import annotations

import os
import threading
import time
from contextvars import Context
from dataclasses import dataclass

from literate_ai.contracts.identity import ContentIdentity, canonical_identity

from .builders._process import run_bounded_process
from .freebsd_telemetry_resources import (
    MAX_NATIVE_RESOURCE_BYTES,
    MAX_NATIVE_RESOURCE_MEMBERS,
    compare_native_resource_snapshot,
)
from .worker_telemetry_native_feed import OriginalNativeResourceTarget
from .worker_telemetry_wire_v2 import WorkerTelemetryWireError, _decode


def _refuse():
    raise WorkerTelemetryWireError("worker_telemetry.native_observation_unavailable")


@dataclass(frozen=True, slots=True)
class NativeResourceMeasurement:
    """Numeric facts; constructing these does not create a live owner."""

    provider_identity: ContentIdentity
    counter_epoch: ContentIdentity
    observed_at_ms: int
    monotonic_ns: int
    cpu_time_ns: int
    memory_resident_bytes: int
    cpu_utilization_basis_points: int | None
    interval_started_monotonic_ns: int | None

    def __post_init__(self):
        if (
            type(self.provider_identity) is not ContentIdentity
            or type(self.counter_epoch) is not ContentIdentity
            or any(
                type(value) is not int or not 0 <= value < 2**63
                for value in (
                    self.observed_at_ms,
                    self.monotonic_ns,
                    self.cpu_time_ns,
                    self.memory_resident_bytes,
                )
            )
            or min(self.observed_at_ms, self.monotonic_ns) <= 0
            or (
                self.cpu_utilization_basis_points is not None
                and (
                    type(self.cpu_utilization_basis_points) is not int
                    or not 0 <= self.cpu_utilization_basis_points < 2**63
                )
            )
        ):
            _refuse()
        if self.cpu_utilization_basis_points is None:
            if self.interval_started_monotonic_ns is not None:
                _refuse()
        elif (
            type(self.interval_started_monotonic_ns) is not int
            or not 0 < self.interval_started_monotonic_ns < self.monotonic_ns
            or self.monotonic_ns - self.interval_started_monotonic_ns > 30_000_000_000
        ):
            _refuse()


def _measure(target, generation, previous):
    if type(target) is not OriginalNativeResourceTarget:
        _refuse()
    target.require_current()
    provider = target._provider
    provider.require_current()
    runner = target._runner()
    if runner is None:
        _refuse()
    configuration = runner._feed._admission._configuration
    configuration.require_observation_inputs_current(
        deadline=runner._feed._admission.deadline
    )
    timeout = min(
        provider.process_timeout_ms / 1000,
        runner._feed._admission.deadline.remaining(),
    )
    result = run_bounded_process(
        (str(provider.executable), str(target._guardian_pid)),
        cwd=provider.executable.parent,
        environment={"PATH": os.defpath, "LC_ALL": "C", "LANG": "C"},
        timeout_seconds=timeout,
        stdout_limit_bytes=provider.output_limit_bytes,
        stderr_limit_bytes=4096,
        error_prefix="worker_telemetry.native_resource",
        interrupt_guard=target.require_current,
        terminate_descendants=True,
        trace=False,
    )
    target.require_current()
    provider.require_current()
    configuration.require_observation_inputs_current(
        deadline=runner._feed._admission.deadline
    )
    if result.returncode != 0:
        _refuse()
    raw = result.stdout
    # Establish initial numeric birth facts ONLY under the original live runner
    # and nonce-bound target. Decoder values never construct that authority.
    if generation is None:
        value = _decode(raw, MAX_NATIVE_RESOURCE_BYTES)
        rows = value.get("members") if type(value) is dict else None
        if (
            type(rows) is not list
            or not 1 <= len(rows) <= MAX_NATIVE_RESOURCE_MEMBERS
            or type(rows[0]) is not dict
        ):
            _refuse()
        generation = (
            target._guardian_pid,
            rows[0].get("start_seconds"),
            rows[0].get("start_microseconds"),
        )
    snapshot = compare_native_resource_snapshot(
        raw, root_generation=generation, original_parent_pid=target._parent_pid
    )
    now_ms = time.time_ns() // 1_000_000
    now_ns = time.monotonic_ns()
    if (
        not 0 <= now_ms - snapshot.observed_at_ms <= 30000
        or not 0 <= now_ns - snapshot.monotonic_ns <= 30_000_000_000
    ):
        _refuse()
    counter_epoch = canonical_identity(
        {
            "schema": "literate-ai/native-worker-resource-counter-epoch@1",
            "native_binding": runner.binding,
            "provider_identity": provider.identity.to_dict(),
            "generation": list(generation),
        }
    )
    utilization = None
    if previous is not None:
        elapsed = snapshot.monotonic_ns - previous.monotonic_ns
        consumed = snapshot.cpu_time_ns - previous.cpu_time_ns
        if consumed < 0 or previous.counter_epoch != counter_epoch:
            _refuse()
        if 0 < elapsed <= 30_000_000_000:
            utilization = consumed * 10000 // elapsed
            if utilization >= 2**63:
                _refuse()
    measurement = NativeResourceMeasurement(
        provider.identity,
        counter_epoch,
        snapshot.observed_at_ms,
        snapshot.monotonic_ns,
        snapshot.cpu_time_ns,
        snapshot.memory_resident_bytes,
        utilization,
        previous.monotonic_ns if utilization is not None else None,
    )
    target.require_current()
    return generation, measurement


def start_native_resource_sampling(owner):
    """Separate actual-owner service only, never called by a query handler.

    Thread startup and all blocking native/file IO occur off the execution path.
    At most one helper per owner is in flight; no samples/history are appended.
    This service holds no Popen, signal, JobObject or reaper control descriptor.
    """
    from .worker_telemetry_owner import LiveWorkerTelemetryOwner

    if type(owner) is not LiveWorkerTelemetryOwner:
        _refuse()
    owner.require_open()
    feed = owner._native_feed
    if feed is None or feed._admission._configuration.native_resources is None:
        return
    provider = feed._admission._configuration.native_resources

    def sample():
        # One monotonic actual-feed claim prevents duplicate helper streams,
        # even if a private caller accidentally starts this service twice.
        while not owner._closed.is_set():
            try:
                owner.require_open()
                if not feed.claim_resource_sampler():
                    return
                break
            except WorkerTelemetryWireError as exc:
                if exc.code != "worker_telemetry.observation_overloaded":
                    return
                owner._closed.wait(0.05)
            except Exception:
                return
        generation = previous = None
        while not owner._closed.is_set():
            try:
                owner.require_open()
                feed._admission._configuration.require_observation_inputs_current(
                    deadline=feed._admission.deadline
                )
            except Exception:
                return  # Admission/deadline/operator revocation ends this service.
            try:
                target = feed.resource_target()
                if target is not None:
                    generation, measurement = _measure(target, generation, previous)
                    feed.push_resources(target, measurement)
                    previous = measurement
            except Exception:
                # No paths, diagnostics, command bytes or fabricated zeros.
                # Preserve the actual old timestamp; freshness expires it.
                pass
            owner._closed.wait(provider.interval_ms / 1000)

    threading.Thread(
        target=lambda: Context().run(sample),
        daemon=True,
        name="litai-native-resource-observer",
    ).start()
