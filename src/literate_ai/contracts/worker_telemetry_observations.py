"""Untrusted observation values; current authentication and live owners are separate."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar

from ._validation import contract_fields, enum_value
from .identity import ContentIdentity
from .worker_telemetry import (
    MAX_TELEMETRY_ACTIONS,
    TelemetryMeasurementScope,
    TelemetryMetricName,
    TelemetryScope,
    WorkerTelemetryMetric,
    WorkerTelemetryProgress,
    WorkerTelemetryRequest,
    _identity,
    _integer,
)


class TelemetryStage(StrEnum):
    UNKNOWN = "unknown"
    QUEUED = "queued"
    GENERATE = "generate"
    VALIDATE = "validate"
    BUILD = "build"
    TEST = "test"
    EXECUTE = "execute"
    ACCEPT = "accept"
    PUBLISH = "publish"


class TelemetryActionState(StrEnum):
    UNKNOWN = "unknown"
    QUEUED = "queued"
    RUNNING = "running"
    BLOCKED = "blocked"
    FINISHED = "finished"


class TelemetryResponseStatus(StrEnum):
    OBSERVED = "observed"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
    DENIED = "denied"


def _optional_identity(value):
    if value is not None:
        _identity(value)


def _read_optional_identity(value):
    return None if value is None else ContentIdentity.parse_uri(value)


def _write_optional_identity(value):
    return None if value is None else value.uri


@dataclass(frozen=True, slots=True)
class WorkerTelemetryObservation:
    action_identity: ContentIdentity | None
    reservation_identity: ContentIdentity | None
    process_start_identity: ContentIdentity | None
    owner_epoch: ContentIdentity
    counter_epoch: ContentIdentity
    observed_at_ms: int
    stage: TelemetryStage
    state: TelemetryActionState
    progress: WorkerTelemetryProgress
    metrics: tuple[WorkerTelemetryMetric, ...]
    terminal_result_identity: ContentIdentity | None = None

    SCHEMA: ClassVar[str] = "literate-ai/worker-telemetry-observation@1"

    def __post_init__(self):
        for value in (self.owner_epoch, self.counter_epoch):
            _identity(value)
        for value in (
            self.action_identity,
            self.reservation_identity,
            self.process_start_identity,
            self.terminal_result_identity,
        ):
            _optional_identity(value)
        _integer(self.observed_at_ms)
        if not isinstance(self.stage, TelemetryStage) or not isinstance(
            self.state, TelemetryActionState
        ):
            raise ValueError("worker.telemetry_state_invalid")
        if not isinstance(self.progress, WorkerTelemetryProgress):
            raise ValueError("worker.telemetry_progress_invalid")
        metrics = self.metrics
        if (
            not isinstance(metrics, tuple)
            or len(metrics) != len(TelemetryMetricName)
            or any(not isinstance(m, WorkerTelemetryMetric) for m in metrics)
        ):
            raise ValueError("worker.telemetry_metrics_invalid")
        if tuple(m.name.value for m in metrics) != tuple(
            sorted(n.value for n in TelemetryMetricName)
        ):
            raise ValueError("worker.telemetry_metric_inventory_invalid")
        if self.action_identity is None:
            if (
                self.reservation_identity is not None
                or self.process_start_identity is not None
                or self.terminal_result_identity is not None
                or self.stage is not TelemetryStage.UNKNOWN
                or self.state is not TelemetryActionState.UNKNOWN
                or any(
                    m.scope is not TelemetryMeasurementScope.WORKER_HOST
                    for m in metrics
                )
            ):
                raise ValueError("worker.telemetry_aggregate_attribution_invalid")
        elif self.reservation_identity is None or self.process_start_identity is None:
            raise ValueError("worker.telemetry_action_owner_missing")
        # A reference does not authenticate terminal success. The eventual receiver
        # must reopen the genuine final-result owner; absence remains unknown.
        if (self.state is TelemetryActionState.FINISHED) != (
            self.terminal_result_identity is not None
        ):
            raise ValueError("worker.telemetry_terminal_evidence_invalid")

    def to_dict(self):
        return {
            "schema": self.SCHEMA,
            "action_identity": _write_optional_identity(self.action_identity),
            "reservation_identity": _write_optional_identity(self.reservation_identity),
            "process_start_identity": _write_optional_identity(
                self.process_start_identity
            ),
            "owner_epoch": self.owner_epoch.uri,
            "counter_epoch": self.counter_epoch.uri,
            "observed_at_ms": self.observed_at_ms,
            "stage": self.stage.value,
            "state": self.state.value,
            "progress": self.progress.to_dict(),
            "metrics": [m.to_dict() for m in self.metrics],
            "terminal_result_identity": _write_optional_identity(
                self.terminal_result_identity
            ),
        }

    @classmethod
    def from_dict(cls, value: Any):
        d = contract_fields(
            value,
            path="WorkerTelemetryObservation",
            schema_uri=cls.SCHEMA,
            required=frozenset(
                {
                    "action_identity",
                    "reservation_identity",
                    "process_start_identity",
                    "owner_epoch",
                    "counter_epoch",
                    "observed_at_ms",
                    "stage",
                    "state",
                    "progress",
                    "metrics",
                    "terminal_result_identity",
                }
            ),
        )
        metrics = d["metrics"]
        if type(metrics) is not list or len(metrics) != len(TelemetryMetricName):
            raise ValueError("worker.telemetry_metrics_invalid")
        return cls(
            _read_optional_identity(d["action_identity"]),
            _read_optional_identity(d["reservation_identity"]),
            _read_optional_identity(d["process_start_identity"]),
            ContentIdentity.parse_uri(d["owner_epoch"]),
            ContentIdentity.parse_uri(d["counter_epoch"]),
            d["observed_at_ms"],
            enum_value(TelemetryStage, d["stage"], "observation.stage"),
            enum_value(TelemetryActionState, d["state"], "observation.state"),
            WorkerTelemetryProgress.from_dict(d["progress"]),
            tuple(WorkerTelemetryMetric.from_dict(m) for m in metrics),
            _read_optional_identity(d["terminal_result_identity"]),
        )


@dataclass(frozen=True, slots=True)
class WorkerTelemetryResponse:
    request_identity: ContentIdentity
    worker_identity: ContentIdentity
    observation_scope_identity: ContentIdentity
    observer_epoch: ContentIdentity
    sequence: int
    observed_at_ms: int
    expires_at_ms: int
    status: TelemetryResponseStatus
    samples: tuple[WorkerTelemetryObservation, ...]

    SCHEMA: ClassVar[str] = "literate-ai/worker-telemetry-response@1"

    def __post_init__(self):
        for value in (
            self.request_identity,
            self.worker_identity,
            self.observation_scope_identity,
            self.observer_epoch,
        ):
            _identity(value)
        for value in (self.sequence, self.observed_at_ms, self.expires_at_ms):
            _integer(value)
        if self.observed_at_ms >= self.expires_at_ms:
            raise ValueError("worker.telemetry_response_expiry_invalid")
        if not isinstance(self.status, TelemetryResponseStatus):
            raise ValueError("worker.telemetry_response_status_invalid")
        if (
            not isinstance(self.samples, tuple)
            or len(self.samples) > MAX_TELEMETRY_ACTIONS
            or any(not isinstance(s, WorkerTelemetryObservation) for s in self.samples)
        ):
            raise ValueError("worker.telemetry_samples_invalid")
        if bool(self.samples) != (self.status is TelemetryResponseStatus.OBSERVED):
            raise ValueError("worker.telemetry_response_samples_invalid")
        if any(s.observed_at_ms > self.observed_at_ms for s in self.samples):
            raise ValueError("worker.telemetry_sample_time_invalid")

    def header(self):
        return {
            "schema": self.SCHEMA,
            "request_identity": self.request_identity.uri,
            "worker_identity": self.worker_identity.uri,
            "observation_scope_identity": self.observation_scope_identity.uri,
            "observer_epoch": self.observer_epoch.uri,
            "sequence": self.sequence,
            "observed_at_ms": self.observed_at_ms,
            "expires_at_ms": self.expires_at_ms,
            "status": self.status.value,
            "sample_count": len(self.samples),
        }

    def require_request_binding(self, request: WorkerTelemetryRequest):
        """Check data correspondence only; this does not authenticate a response."""
        if not isinstance(request, WorkerTelemetryRequest) or (
            self.request_identity != request.identity
            or self.worker_identity != request.worker_identity
            or self.observation_scope_identity != request.observation_scope_identity
            or self.expires_at_ms != request.expires_at_ms
            or self.observed_at_ms < request.issued_at_ms
            or any(s.observed_at_ms < request.issued_at_ms for s in self.samples)
        ):
            raise ValueError("worker.telemetry_response_binding_invalid")
        if self.status is not TelemetryResponseStatus.OBSERVED:
            return
        if request.scope is TelemetryScope.ACTIONS:
            if (
                tuple(s.action_identity for s in self.samples)
                != request.action_identities
            ):
                raise ValueError("worker.telemetry_action_inventory_invalid")
        elif len(self.samples) != 1 or self.samples[0].action_identity is not None:
            raise ValueError("worker.telemetry_aggregate_inventory_invalid")
