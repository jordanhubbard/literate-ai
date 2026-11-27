"""Bounded observation declarations; decoding never creates a live action owner."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any, ClassVar

from ._validation import (
    bool_value,
    contract_fields,
    enum_value,
    fail,
    fields,
    int_value,
    list_value,
)
from .identity import ContentIdentity, canonical_identity, canonical_json_bytes
from .worker_capacity import capacity_alias

MAX_OPERATIONS = 64
MAX_SAMPLE_BYTES = 16 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_REQUEST_BYTES = 32 * 1024
MAX_DURATION_MS = 30_000
MIN_POLL_INTERVAL_MS = 1000
_NONCE = re.compile(r"[0-9a-f]{32}\Z")


class TelemetryScope(StrEnum):
    OPERATIONS = "operations"
    WORKER_HOST = "worker-host"


class TelemetrySampleSource(StrEnum):
    FRESH = "fresh"
    COALESCED = "coalesced"
    CACHED = "cached"


class TelemetryMetricScope(StrEnum):
    ACTION_SUBTREE = "action-subtree"
    CONTAINER = "container"
    WORKER_HOST = "worker-host"
    UNAVAILABLE = "unavailable"


class TelemetryMetricStatus(StrEnum):
    MEASURED = "measured"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    DENIED = "denied"


class TelemetryReason(StrEnum):
    NATIVE_COUNTER_UNAVAILABLE = "native-counter-unavailable"
    ATTRIBUTION_UNSUPPORTED = "attribution-unsupported"
    PERMISSION_DENIED = "permission-denied"
    OWNER_UNAVAILABLE = "owner-unavailable"
    COUNTER_RESET = "counter-reset"


class TelemetryStage(StrEnum):
    UNKNOWN = "unknown"
    QUEUED = "queued"
    MATERIALIZE = "materialize"
    INDEX = "index"
    VALIDATE = "validate"
    BUILD = "build"
    TEST = "test"
    EXECUTE = "execute"
    ACCEPT = "accept"
    PACKAGE = "package"
    LINK = "link"
    VERIFY = "verify"
    COMPLETE = "complete"


class TelemetryState(StrEnum):
    UNKNOWN = "unknown"
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    FAILED = "failed"
    COMPLETED = "completed"


# Native cumulative counters use the separate counter epoch. Host counters cannot
# be reported as action counters merely because an action was selected.
# CPU utilization is delta(cpu_time_ns) / delta(monotonic_time_ns) * 10000:
# 10000 means one fully occupied CPU core, so parallel work may exceed 10000.
# The sample carries the actual interval; missing interval means unavailable.
# A native counter reset changes counter_epoch, never the real owner_epoch.
METRIC_DEFINITIONS = MappingProxyType(
    {
        "cpu_time_ns": ("nanoseconds", "counter"),
        "cpu_utilization_basis_points": ("basis-points-of-one-core", "gauge"),
        "memory_resident_bytes": ("bytes", "gauge"),
        "network_in_bytes": ("bytes", "counter"),
        "network_out_bytes": ("bytes", "counter"),
        "disk_read_bytes": ("bytes", "counter"),
        "disk_write_bytes": ("bytes", "counter"),
    }
)
METRIC_NAMES = tuple(sorted(METRIC_DEFINITIONS))


def _identity(value: Any, path: str) -> None:
    if type(value) is not ContentIdentity:
        fail(path, "must be an exact content identity")


def _bounded_rows(value: Any, path: str, maximum: int) -> Any:
    rows = list_value(value, path)
    if len(rows) > maximum:
        fail(path, f"must contain at most {maximum} entries")
    return rows


@dataclass(frozen=True, slots=True)
class TelemetryMetric:
    name: str
    scope: TelemetryMetricScope
    status: TelemetryMetricStatus
    value: int | None
    reason: TelemetryReason | None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or self.name not in METRIC_DEFINITIONS:
            fail("TelemetryMetric.name", "must name a defined safe metric")
        if (
            type(self.scope) is not TelemetryMetricScope
            or type(self.status) is not TelemetryMetricStatus
        ):
            fail("TelemetryMetric", "scope and status must be typed")
        if self.status is TelemetryMetricStatus.MEASURED:
            int_value(self.value, "TelemetryMetric.value")
            if (
                self.reason is not None
                or self.scope is TelemetryMetricScope.UNAVAILABLE
            ):
                fail(
                    "TelemetryMetric",
                    "measured values require actual scope and no refusal reason",
                )
        elif self.value is not None or type(self.reason) is not TelemetryReason:
            fail("TelemetryMetric", "unmeasured values require null and a typed reason")

    def to_dict(self) -> dict[str, object]:
        unit, kind = METRIC_DEFINITIONS[self.name]
        return {
            "name": self.name,
            "unit": unit,
            "kind": kind,
            "scope": self.scope.value,
            "status": self.status.value,
            "value": self.value,
            "reason": None if self.reason is None else self.reason.value,
        }

    @classmethod
    def from_dict(cls, value: Any) -> TelemetryMetric:
        data = fields(
            value,
            path="TelemetryMetric",
            required=frozenset(
                {"name", "unit", "kind", "scope", "status", "value", "reason"}
            ),
        )
        name = data["name"]
        if not isinstance(name, str) or METRIC_DEFINITIONS.get(name) != (
            data["unit"],
            data["kind"],
        ):
            fail("TelemetryMetric", "metric unit/kind must match its defined name")
        return cls(
            name,
            enum_value(TelemetryMetricScope, data["scope"], "TelemetryMetric.scope"),
            enum_value(TelemetryMetricStatus, data["status"], "TelemetryMetric.status"),
            data["value"],
            None
            if data["reason"] is None
            else enum_value(TelemetryReason, data["reason"], "TelemetryMetric.reason"),
        )


@dataclass(frozen=True, slots=True)
class TelemetryProgress:
    completed: int
    total: int
    unit: str

    def __post_init__(self) -> None:
        int_value(self.total, "TelemetryProgress.total", minimum=1)
        int_value(self.completed, "TelemetryProgress.completed", maximum=self.total)
        if not isinstance(self.unit, str) or self.unit not in {
            "files",
            "bytes",
            "units",
            "steps",
        }:
            fail("TelemetryProgress.unit", "must be a defined work unit")

    def to_dict(self) -> dict[str, object]:
        return {"completed": self.completed, "total": self.total, "unit": self.unit}

    @classmethod
    def from_dict(cls, value: Any) -> TelemetryProgress:
        return cls(
            **fields(
                value,
                path="TelemetryProgress",
                required=frozenset({"completed", "total", "unit"}),
            )
        )


@dataclass(frozen=True, slots=True)
class WorkerTelemetryRequest:
    """Select exact dispatch operations, not repeatable action-node identities.

    Each operation identity is the canonical LifecycleActionDispatchRequest
    identity, binding its schedule, worker, slot and original deadline. Samples
    separately report the node's action identity as explicit metadata.
    """

    worker_id: str
    worker_identity: ContentIdentity
    registration_identity: ContentIdentity
    catalog_identity: ContentIdentity
    controller_identity: ContentIdentity
    observation_scope_identity: ContentIdentity
    scope: TelemetryScope
    operation_identities: tuple[ContentIdentity, ...]
    nonce: str
    issued_at_ms: int
    expires_at_ms: int
    maximum_sample_age_ms: int
    allow_cached_observations: bool

    SCHEMA: ClassVar[str] = "literate-ai/worker-telemetry-request@2"

    def __post_init__(self) -> None:
        capacity_alias(self.worker_id, "WorkerTelemetryRequest.worker_id")
        for name in (
            "worker_identity",
            "registration_identity",
            "catalog_identity",
            "controller_identity",
            "observation_scope_identity",
        ):
            _identity(getattr(self, name), "WorkerTelemetryRequest." + name)
        if type(self.scope) is not TelemetryScope:
            fail("WorkerTelemetryRequest.scope", "must be typed")
        if (
            not isinstance(self.operation_identities, tuple)
            or len(self.operation_identities) > MAX_OPERATIONS
        ):
            fail(
                "WorkerTelemetryRequest.operation_identities", "must be a bounded tuple"
            )
        for operation in self.operation_identities:
            _identity(operation, "WorkerTelemetryRequest.operation_identities")
        names = tuple(operation.uri for operation in self.operation_identities)
        if names != tuple(sorted(set(names))):
            fail(
                "WorkerTelemetryRequest.operation_identities", "must be uniquely sorted"
            )
        if bool(names) != (self.scope is TelemetryScope.OPERATIONS):
            fail(
                "WorkerTelemetryRequest",
                "operation scope requires a nonempty selection; "
                "host scope has no operation selection",
            )
        if not isinstance(self.nonce, str) or not _NONCE.fullmatch(self.nonce):
            fail(
                "WorkerTelemetryRequest.nonce", "must be 128-bit lower-case hexadecimal"
            )
        int_value(self.issued_at_ms, "WorkerTelemetryRequest.issued_at_ms")
        int_value(
            self.expires_at_ms,
            "WorkerTelemetryRequest.expires_at_ms",
            minimum=self.issued_at_ms + 1,
        )
        int_value(
            self.maximum_sample_age_ms,
            "WorkerTelemetryRequest.maximum_sample_age_ms",
            minimum=1,
            maximum=MAX_DURATION_MS,
        )
        bool_value(
            self.allow_cached_observations,
            "WorkerTelemetryRequest.allow_cached_observations",
        )
        if self.expires_at_ms - self.issued_at_ms > MAX_DURATION_MS:
            fail("WorkerTelemetryRequest", "observation duration exceeds 30 seconds")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "worker_id": self.worker_id,
            **{
                name: getattr(self, name).to_dict()
                for name in (
                    "worker_identity",
                    "registration_identity",
                    "catalog_identity",
                    "controller_identity",
                    "observation_scope_identity",
                )
            },
            "scope": self.scope.value,
            "operation_identities": [
                action.to_dict() for action in self.operation_identities
            ],
            "nonce": self.nonce,
            "issued_at_ms": self.issued_at_ms,
            "expires_at_ms": self.expires_at_ms,
            "maximum_sample_age_ms": self.maximum_sample_age_ms,
            "allow_cached_observations": self.allow_cached_observations,
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
                    "worker_id",
                    "worker_identity",
                    "registration_identity",
                    "catalog_identity",
                    "controller_identity",
                    "observation_scope_identity",
                    "scope",
                    "operation_identities",
                    "nonce",
                    "issued_at_ms",
                    "expires_at_ms",
                    "maximum_sample_age_ms",
                    "allow_cached_observations",
                }
            ),
        )
        rows = _bounded_rows(
            data["operation_identities"],
            "WorkerTelemetryRequest.operation_identities",
            MAX_OPERATIONS,
        )
        return cls(
            data["worker_id"],
            *(
                ContentIdentity.from_dict(data[name])
                for name in (
                    "worker_identity",
                    "registration_identity",
                    "catalog_identity",
                    "controller_identity",
                    "observation_scope_identity",
                )
            ),
            enum_value(TelemetryScope, data["scope"], "WorkerTelemetryRequest.scope"),
            tuple(ContentIdentity.from_dict(row) for row in rows),
            data["nonce"],
            data["issued_at_ms"],
            data["expires_at_ms"],
            data["maximum_sample_age_ms"],
            data["allow_cached_observations"],
        )


@dataclass(frozen=True, slots=True)
class WorkerTelemetrySample:
    # Exact dispatch request identity selects schedule/worker/slot/deadline.
    # Node action identity is explicit metadata and may repeat across operations.
    operation_identity: ContentIdentity | None
    action_identity: ContentIdentity | None
    owner_epoch: ContentIdentity
    counter_epoch: ContentIdentity
    source: TelemetrySampleSource
    interval_started_monotonic_ns: int | None
    sequence: int
    observed_at_ms: int
    monotonic_time_ns: int
    stage: TelemetryStage
    state: TelemetryState
    progress: TelemetryProgress | None
    metrics: tuple[TelemetryMetric, ...]
    reservation_identity: ContentIdentity | None

    SCHEMA: ClassVar[str] = "literate-ai/worker-telemetry-sample@1"

    def __post_init__(self) -> None:
        if self.reservation_identity is not None:
            _identity(
                self.reservation_identity, "WorkerTelemetrySample.reservation_identity"
            )
        if (self.operation_identity is None) != (self.action_identity is None):
            fail(
                "WorkerTelemetrySample",
                "operation and action must both be null or typed",
            )
        if self.operation_identity is not None:
            _identity(
                self.operation_identity, "WorkerTelemetrySample.operation_identity"
            )
        if self.action_identity is not None:
            _identity(self.action_identity, "WorkerTelemetrySample.action_identity")
        _identity(self.owner_epoch, "WorkerTelemetrySample.owner_epoch")
        _identity(self.counter_epoch, "WorkerTelemetrySample.counter_epoch")
        if type(self.source) is not TelemetrySampleSource:
            fail("WorkerTelemetrySample.source", "must be a typed sample origin")
        if self.interval_started_monotonic_ns is not None:
            int_value(
                self.interval_started_monotonic_ns,
                "WorkerTelemetrySample.interval_started_monotonic_ns",
            )
            int_value(
                self.monotonic_time_ns,
                "WorkerTelemetrySample.monotonic_time_ns",
                minimum=self.interval_started_monotonic_ns + 1,
                maximum=self.interval_started_monotonic_ns
                + MAX_DURATION_MS * 1_000_000,
            )
        for name in ("sequence", "observed_at_ms", "monotonic_time_ns"):
            int_value(getattr(self, name), "WorkerTelemetrySample." + name)
        if (
            type(self.stage) is not TelemetryStage
            or type(self.state) is not TelemetryState
        ):
            fail(
                "WorkerTelemetrySample", "stage and state must be typed safe vocabulary"
            )
        if self.progress is not None and type(self.progress) is not TelemetryProgress:
            fail("WorkerTelemetrySample.progress", "must be typed or null")
        if (
            not isinstance(self.metrics, tuple)
            or len(self.metrics) != len(METRIC_NAMES)
            or any(type(metric) is not TelemetryMetric for metric in self.metrics)
        ):
            fail(
                "WorkerTelemetrySample.metrics",
                "must contain all defined typed metrics",
            )
        if tuple(metric.name for metric in self.metrics) != METRIC_NAMES:
            fail(
                "WorkerTelemetrySample.metrics",
                "must contain the uniquely sorted complete metric set",
            )
        if self.action_identity is None and (
            self.stage is not TelemetryStage.UNKNOWN
            or self.state is not TelemetryState.UNKNOWN
            or self.progress is not None
            or self.reservation_identity is not None
        ):
            fail(
                "WorkerTelemetrySample",
                "host samples cannot assert an action lifecycle",
            )
        if self.action_identity is not None and self.reservation_identity is None:
            if (
                self.state not in {TelemetryState.UNKNOWN, TelemetryState.QUEUED}
                or self.progress is not None
                or any(
                    metric.scope is not TelemetryMetricScope.UNAVAILABLE
                    for metric in self.metrics
                )
            ):
                fail(
                    "WorkerTelemetrySample",
                    "unprotected processing cannot claim execution or metrics",
                )
        if self.interval_started_monotonic_ns is None and any(
            metric.name == "cpu_utilization_basis_points"
            and metric.status is TelemetryMetricStatus.MEASURED
            for metric in self.metrics
        ):
            fail(
                "WorkerTelemetrySample",
                "measured CPU gauge requires an actual monotonic interval",
            )
        allowed_scopes = (
            {TelemetryMetricScope.WORKER_HOST, TelemetryMetricScope.UNAVAILABLE}
            if self.action_identity is None
            else {
                TelemetryMetricScope.ACTION_SUBTREE,
                TelemetryMetricScope.CONTAINER,
                TelemetryMetricScope.UNAVAILABLE,
            }
        )
        if any(metric.scope not in allowed_scopes for metric in self.metrics):
            fail(
                "WorkerTelemetrySample",
                "metric scope does not match authorized sample scope",
            )
        if len(canonical_json_bytes(self.to_dict())) > MAX_SAMPLE_BYTES:
            fail("WorkerTelemetrySample", "sample exceeds 16 KiB")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "operation_identity": None
            if self.operation_identity is None
            else self.operation_identity.to_dict(),
            "action_identity": None
            if self.action_identity is None
            else self.action_identity.to_dict(),
            "reservation_identity": None
            if self.reservation_identity is None
            else self.reservation_identity.to_dict(),
            "owner_epoch": self.owner_epoch.to_dict(),
            "counter_epoch": self.counter_epoch.to_dict(),
            "source": self.source.value,
            "interval_started_monotonic_ns": self.interval_started_monotonic_ns,
            "sequence": self.sequence,
            "observed_at_ms": self.observed_at_ms,
            "monotonic_time_ns": self.monotonic_time_ns,
            "stage": self.stage.value,
            "state": self.state.value,
            "progress": None if self.progress is None else self.progress.to_dict(),
            "metrics": [metric.to_dict() for metric in self.metrics],
        }

    @classmethod
    def from_dict(cls, value: Any) -> WorkerTelemetrySample:
        data = contract_fields(
            value,
            path="WorkerTelemetrySample",
            schema_uri=cls.SCHEMA,
            required=frozenset(
                {
                    "operation_identity",
                    "action_identity",
                    "reservation_identity",
                    "owner_epoch",
                    "counter_epoch",
                    "source",
                    "interval_started_monotonic_ns",
                    "sequence",
                    "observed_at_ms",
                    "monotonic_time_ns",
                    "stage",
                    "state",
                    "progress",
                    "metrics",
                }
            ),
        )
        rows = _bounded_rows(
            data["metrics"], "WorkerTelemetrySample.metrics", len(METRIC_NAMES)
        )
        return cls(
            None
            if data["operation_identity"] is None
            else ContentIdentity.from_dict(data["operation_identity"]),
            None
            if data["action_identity"] is None
            else ContentIdentity.from_dict(data["action_identity"]),
            ContentIdentity.from_dict(data["owner_epoch"]),
            ContentIdentity.from_dict(data["counter_epoch"]),
            enum_value(
                TelemetrySampleSource, data["source"], "WorkerTelemetrySample.source"
            ),
            data["interval_started_monotonic_ns"],
            data["sequence"],
            data["observed_at_ms"],
            data["monotonic_time_ns"],
            enum_value(TelemetryStage, data["stage"], "WorkerTelemetrySample.stage"),
            enum_value(TelemetryState, data["state"], "WorkerTelemetrySample.state"),
            None
            if data["progress"] is None
            else TelemetryProgress.from_dict(data["progress"]),
            tuple(TelemetryMetric.from_dict(row) for row in rows),
            None
            if data["reservation_identity"] is None
            else ContentIdentity.from_dict(data["reservation_identity"]),
        )


@dataclass(frozen=True, slots=True)
class WorkerTelemetryResponse:
    """Observation bytes awaiting actual authenticated receiver verification."""

    request_identity: ContentIdentity
    receiver_epoch: ContentIdentity
    sequence: int
    samples: tuple[WorkerTelemetrySample, ...]

    SCHEMA: ClassVar[str] = "literate-ai/worker-telemetry-response@2"

    def __post_init__(self) -> None:
        _identity(self.request_identity, "WorkerTelemetryResponse.request_identity")
        _identity(self.receiver_epoch, "WorkerTelemetryResponse.receiver_epoch")
        int_value(self.sequence, "WorkerTelemetryResponse.sequence")
        if (
            not isinstance(self.samples, tuple)
            or not 1 <= len(self.samples) <= MAX_OPERATIONS
        ):
            fail(
                "WorkerTelemetryResponse.samples", "must contain 1 to 64 typed samples"
            )
        if any(type(sample) is not WorkerTelemetrySample for sample in self.samples):
            fail("WorkerTelemetryResponse.samples", "must contain exact typed samples")
        operations = tuple(sample.operation_identity for sample in self.samples)
        if None in operations:
            if operations != (None,):
                fail(
                    "WorkerTelemetryResponse",
                    "host observation must be one separate sample",
                )
        elif tuple(operation.uri for operation in operations) != tuple(
            sorted({operation.uri for operation in operations})
        ):
            fail("WorkerTelemetryResponse", "operation samples must be uniquely sorted")
        # Reserve framing overhead for an enclosing authentication envelope.
        if len(canonical_json_bytes(self.to_dict())) > MAX_RESPONSE_BYTES - 4096:
            fail(
                "WorkerTelemetryResponse", "observation batch exceeds its framed budget"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "request_identity": self.request_identity.to_dict(),
            "receiver_epoch": self.receiver_epoch.to_dict(),
            "sequence": self.sequence,
            "samples": [sample.to_dict() for sample in self.samples],
        }

    @classmethod
    def from_dict(cls, value: Any) -> WorkerTelemetryResponse:
        data = contract_fields(
            value,
            path="WorkerTelemetryResponse",
            schema_uri=cls.SCHEMA,
            required=frozenset(
                {"request_identity", "receiver_epoch", "sequence", "samples"}
            ),
        )
        rows = _bounded_rows(
            data["samples"], "WorkerTelemetryResponse.samples", MAX_OPERATIONS
        )
        # Incremental raw accounting precedes construction of another sample DTO.
        used = 0
        for row in rows:
            size = len(canonical_json_bytes(row))
            if size > MAX_SAMPLE_BYTES:
                fail(
                    "WorkerTelemetryResponse.samples",
                    "individual sample exceeds 16 KiB",
                )
            used += size
            if used > MAX_RESPONSE_BYTES - 4096:
                fail(
                    "WorkerTelemetryResponse.samples",
                    "aggregate sample budget exhausted",
                )
        return cls(
            ContentIdentity.from_dict(data["request_identity"]),
            ContentIdentity.from_dict(data["receiver_epoch"]),
            data["sequence"],
            tuple(WorkerTelemetrySample.from_dict(row) for row in rows),
        )

    def require_request(self, request: WorkerTelemetryRequest) -> None:
        """Check selection and declared window; grant no currentness or trust."""
        if (
            type(request) is not WorkerTelemetryRequest
            or self.request_identity != request.identity
        ):
            fail(
                "WorkerTelemetryResponse", "exact observation request identity differs"
            )
        expected = (
            request.operation_identities
            if request.scope is TelemetryScope.OPERATIONS
            else (None,)
        )
        if tuple(sample.operation_identity for sample in self.samples) != expected:
            fail(
                "WorkerTelemetryResponse",
                "exact requested operation membership differs",
            )
        for sample in self.samples:
            if (
                sample.source is TelemetrySampleSource.CACHED
                and not request.allow_cached_observations
            ):
                fail(
                    "WorkerTelemetryResponse", "cached observations were not requested"
                )
            earliest = (
                request.issued_at_ms
                if sample.source is TelemetrySampleSource.FRESH
                or not request.allow_cached_observations
                else request.issued_at_ms - request.maximum_sample_age_ms
            )
            if not earliest <= sample.observed_at_ms <= request.expires_at_ms:
                fail(
                    "WorkerTelemetryResponse",
                    "sample lies outside the declared request/sample-age window",
                )
