"""Closed observational data for ADR 0059; decoded values grant no live authority.

This is the contract foundation, not an authenticated telemetry implementation.
The receiver still needs current transport authentication, observation permission,
registration and operation-local action owners. No PID/path/command selector is
representable, and these values cannot dispatch, signal or renew a job.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, ClassVar

from ._validation import contract_fields, enum_value, fields, int_value
from .identity import ContentIdentity, canonical_identity

MAX_TELEMETRY_ACTIONS = 64
MAX_TELEMETRY_SAMPLE_BYTES = 16 * 1024
MAX_TELEMETRY_RESPONSE_BYTES = 1024 * 1024
MAX_TELEMETRY_REQUEST_MS = 30_000
MIN_TELEMETRY_POLL_INTERVAL_MS = 1_000
_MAX_COUNTER = 2**63 - 1
_NONCE = re.compile(r"[0-9a-f]{64}\Z")


def _identity(value: Any) -> None:
    if not isinstance(value, ContentIdentity):
        raise ValueError("worker.telemetry_identity_invalid")


def _integer(value: Any, maximum: int = _MAX_COUNTER) -> None:
    int_value(value, "worker.telemetry_integer", minimum=0, maximum=maximum)


class TelemetryScope(StrEnum):
    ACTIONS = "actions"
    WORKER_AGGREGATE = "worker-aggregate"


@dataclass(frozen=True, slots=True)
class WorkerTelemetryRequest:
    controller_identity: ContentIdentity
    catalog_identity: ContentIdentity
    registration_identity: ContentIdentity
    worker_identity: ContentIdentity
    observation_scope_identity: ContentIdentity
    nonce: str
    issued_at_ms: int
    expires_at_ms: int
    scope: TelemetryScope
    action_identities: tuple[ContentIdentity, ...]

    SCHEMA: ClassVar[str] = "literate-ai/worker-telemetry-request@1"

    def __post_init__(self) -> None:
        for item in (
            self.controller_identity,
            self.catalog_identity,
            self.registration_identity,
            self.worker_identity,
            self.observation_scope_identity,
        ):
            _identity(item)
        if not isinstance(self.nonce, str) or not _NONCE.fullmatch(self.nonce):
            raise ValueError("worker.telemetry_nonce_invalid")
        _integer(self.issued_at_ms)
        _integer(self.expires_at_ms)
        if not 0 < self.expires_at_ms - self.issued_at_ms <= MAX_TELEMETRY_REQUEST_MS:
            raise ValueError("worker.telemetry_deadline_invalid")
        if not isinstance(self.scope, TelemetryScope):
            raise ValueError("worker.telemetry_scope_invalid")
        actions = self.action_identities
        if not isinstance(actions, tuple) or len(actions) > MAX_TELEMETRY_ACTIONS:
            raise ValueError("worker.telemetry_actions_invalid")
        for item in actions:
            _identity(item)
        if tuple(item.uri for item in actions) != tuple(
            sorted({item.uri for item in actions})
        ):
            raise ValueError("worker.telemetry_actions_invalid")
        if bool(actions) != (self.scope is TelemetryScope.ACTIONS):
            raise ValueError("worker.telemetry_selection_invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "controller_identity": self.controller_identity.uri,
            "catalog_identity": self.catalog_identity.uri,
            "registration_identity": self.registration_identity.uri,
            "worker_identity": self.worker_identity.uri,
            "observation_scope_identity": self.observation_scope_identity.uri,
            "nonce": self.nonce,
            "issued_at_ms": self.issued_at_ms,
            "expires_at_ms": self.expires_at_ms,
            "scope": self.scope.value,
            "action_identities": [item.uri for item in self.action_identities],
        }

    @property
    def identity(self) -> ContentIdentity:
        return canonical_identity(self.to_dict())

    @classmethod
    def from_dict(cls, value: Any) -> WorkerTelemetryRequest:
        data = contract_fields(
            value,
            path="WorkerTelemetryRequest",
            schema_uri=cls.SCHEMA,
            required=frozenset(
                {
                    "controller_identity",
                    "catalog_identity",
                    "registration_identity",
                    "worker_identity",
                    "observation_scope_identity",
                    "nonce",
                    "issued_at_ms",
                    "expires_at_ms",
                    "scope",
                    "action_identities",
                }
            ),
        )
        actions = data["action_identities"]
        if type(actions) is not list or len(actions) > MAX_TELEMETRY_ACTIONS:
            raise ValueError("worker.telemetry_actions_invalid")
        return cls(
            *(
                ContentIdentity.parse_uri(data[name])
                for name in (
                    "controller_identity",
                    "catalog_identity",
                    "registration_identity",
                    "worker_identity",
                    "observation_scope_identity",
                )
            ),
            data["nonce"],
            data["issued_at_ms"],
            data["expires_at_ms"],
            enum_value(TelemetryScope, data["scope"], "WorkerTelemetryRequest.scope"),
            tuple(ContentIdentity.parse_uri(item) for item in actions),
        )


class TelemetryMetricStatus(StrEnum):
    MEASURED = "measured"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    DENIED = "denied"


class TelemetryMeasurementScope(StrEnum):
    PROCESS_SUBTREE = "process-subtree"
    CONTAINER = "container"
    WORKER_HOST = "worker-host"


class TelemetryMetricName(StrEnum):
    NETWORK_IN_BYTES = "network-in-bytes"
    NETWORK_OUT_BYTES = "network-out-bytes"
    DISK_READ_BYTES = "disk-read-bytes"
    DISK_WRITTEN_BYTES = "disk-written-bytes"
    CPU_TIME_NS = "cpu-time-ns"
    CPU_UTILIZATION_BASIS_POINTS = "cpu-utilization-basis-points"
    MEMORY_BYTES = "memory-bytes"


@dataclass(frozen=True, slots=True)
class WorkerTelemetryMetric:
    name: TelemetryMetricName
    scope: TelemetryMeasurementScope
    status: TelemetryMetricStatus
    value: int | None

    def __post_init__(self) -> None:
        if not (
            isinstance(self.name, TelemetryMetricName)
            and isinstance(self.scope, TelemetryMeasurementScope)
            and isinstance(self.status, TelemetryMetricStatus)
        ):
            raise ValueError("worker.telemetry_metric_invalid")
        if self.status is TelemetryMetricStatus.MEASURED:
            _integer(
                self.value,
                10_000
                if self.name is TelemetryMetricName.CPU_UTILIZATION_BASIS_POINTS
                else _MAX_COUNTER,
            )
        elif self.value is not None:
            raise ValueError("worker.telemetry_unmeasured_value")

    @property
    def unit(self) -> str:
        if self.name is TelemetryMetricName.CPU_TIME_NS:
            return "nanoseconds"
        if self.name is TelemetryMetricName.CPU_UTILIZATION_BASIS_POINTS:
            return "basis-points"
        return "bytes"

    @property
    def cumulative(self) -> bool:
        return self.name not in {
            TelemetryMetricName.CPU_UTILIZATION_BASIS_POINTS,
            TelemetryMetricName.MEMORY_BYTES,
        }

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name.value,
            "scope": self.scope.value,
            "status": self.status.value,
            "value": self.value,
            "unit": self.unit,
            "cumulative": self.cumulative,
        }

    @classmethod
    def from_dict(cls, value: Any) -> WorkerTelemetryMetric:
        data = fields(
            value,
            path="WorkerTelemetryMetric",
            required=frozenset(
                {"name", "scope", "status", "value", "unit", "cumulative"}
            ),
        )
        result = cls(
            enum_value(TelemetryMetricName, data["name"], "metric.name"),
            enum_value(TelemetryMeasurementScope, data["scope"], "metric.scope"),
            enum_value(TelemetryMetricStatus, data["status"], "metric.status"),
            data["value"],
        )
        if (
            data["unit"] != result.unit
            or type(data["cumulative"]) is not bool
            or data["cumulative"] != result.cumulative
        ):
            raise ValueError("worker.telemetry_metric_semantics_invalid")
        return result


class TelemetryProgressReason(StrEnum):
    UNKNOWN = "unknown"
    OPAQUE_WORK = "opaque-work"
    NOT_STARTED = "not-started"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class WorkerTelemetryProgress:
    """Defined completed/total work only; null pairs mean indeterminate progress."""

    completed: int | None = None
    total: int | None = None
    reason: TelemetryProgressReason | None = TelemetryProgressReason.OPAQUE_WORK

    def __post_init__(self) -> None:
        if self.completed is None and self.total is None:
            if not isinstance(self.reason, TelemetryProgressReason):
                raise ValueError("worker.telemetry_progress_reason_missing")
            return
        if self.reason is not None:
            raise ValueError("worker.telemetry_measured_progress_reason")
        _integer(self.completed)
        _integer(self.total)
        if not self.total or self.completed > self.total:
            raise ValueError("worker.telemetry_progress_invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "completed": self.completed,
            "total": self.total,
            "reason": self.reason.value if self.reason is not None else None,
        }

    @classmethod
    def from_dict(cls, value: Any) -> WorkerTelemetryProgress:
        data = fields(
            value,
            path="WorkerTelemetryProgress",
            required=frozenset({"completed", "total", "reason"}),
        )
        return cls(
            data["completed"],
            data["total"],
            None
            if data["reason"] is None
            else enum_value(TelemetryProgressReason, data["reason"], "progress.reason"),
        )
