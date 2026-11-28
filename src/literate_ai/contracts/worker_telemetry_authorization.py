"""Observation-scope declarations; decoding never issues a live permission."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, ClassVar

from ._validation import bool_value, contract_fields, fail, int_value, list_value
from .identity import ContentIdentity, canonical_identity
from .worker_capacity import capacity_alias
from .worker_telemetry_v2 import (
    MAX_DURATION_MS,
    MAX_OPERATIONS,
    MIN_POLL_INTERVAL_MS,
    TelemetryScope,
    WorkerTelemetryRequest,
)

MAX_SCOPE_LIFETIME_MS = 24 * 60 * 60 * 1000
MAX_CONCURRENT_QUERIES = 4
_PUBLIC_KEY = re.compile(r"[0-9a-f]{64}\Z")


def telemetry_key_identity(public_key: str) -> ContentIdentity:
    if not isinstance(public_key, str) or not _PUBLIC_KEY.fullmatch(public_key):
        fail("WorkerTelemetryScope.public_key", "must encode one public Ed25519 key")
    return ContentIdentity.parse_uri(
        "sha256:" + hashlib.sha256(bytes.fromhex(public_key)).hexdigest()
    )


@dataclass(frozen=True, slots=True)
class WorkerTelemetryScope:
    """A value to be reopened from current private operator configuration.

    The transport and live receiver must independently establish that this exact
    declaration is configured. A client-supplied or historical document does not
    grant observation, execution, cancellation, renewal, or process selection.
    Authorized operation identities bind exact dispatch requests; node action
    identities remain metadata and may repeat across concurrent operations.
    """

    worker_id: str
    worker_identity: ContentIdentity
    registration_identity: ContentIdentity
    catalog_identity: ContentIdentity
    controller_public_key: str
    worker_public_key: str
    operation_identities: tuple[ContentIdentity, ...]
    allow_host_aggregate: bool
    not_before_ms: int
    expires_at_ms: int
    maximum_duration_ms: int
    maximum_sample_age_ms: int
    allow_cached_observations: bool
    minimum_poll_interval_ms: int
    maximum_concurrent_queries: int

    SCHEMA: ClassVar[str] = "literate-ai/worker-telemetry-scope@1"

    def __post_init__(self) -> None:
        capacity_alias(self.worker_id, "WorkerTelemetryScope.worker_id")
        for name in (
            "worker_identity",
            "registration_identity",
            "catalog_identity",
        ):
            if type(getattr(self, name)) is not ContentIdentity:
                fail(
                    "WorkerTelemetryScope." + name, "must be an exact content identity"
                )
        telemetry_key_identity(self.controller_public_key)
        telemetry_key_identity(self.worker_public_key)
        if self.controller_public_key == self.worker_public_key:
            fail("WorkerTelemetryScope", "controller and worker keys must be distinct")
        if (
            not isinstance(self.operation_identities, tuple)
            or len(self.operation_identities) > MAX_OPERATIONS
        ):
            fail("WorkerTelemetryScope.operation_identities", "must be a bounded tuple")
        if any(
            type(action) is not ContentIdentity for action in self.operation_identities
        ):
            fail(
                "WorkerTelemetryScope.operation_identities",
                "must contain exact identities",
            )
        names = tuple(action.uri for action in self.operation_identities)
        if names != tuple(sorted(set(names))):
            fail("WorkerTelemetryScope.operation_identities", "must be uniquely sorted")
        bool_value(
            self.allow_host_aggregate, "WorkerTelemetryScope.allow_host_aggregate"
        )
        if not names and not self.allow_host_aggregate:
            fail("WorkerTelemetryScope", "must declare at least one observation scope")
        int_value(self.not_before_ms, "WorkerTelemetryScope.not_before_ms")
        int_value(
            self.expires_at_ms,
            "WorkerTelemetryScope.expires_at_ms",
            minimum=self.not_before_ms + 1,
        )
        if self.expires_at_ms - self.not_before_ms > MAX_SCOPE_LIFETIME_MS:
            fail("WorkerTelemetryScope", "observation scope lifetime exceeds 24 hours")
        int_value(
            self.maximum_duration_ms,
            "WorkerTelemetryScope.maximum_duration_ms",
            minimum=1,
            maximum=MAX_DURATION_MS,
        )
        int_value(
            self.maximum_sample_age_ms,
            "WorkerTelemetryScope.maximum_sample_age_ms",
            minimum=1,
            maximum=MAX_DURATION_MS,
        )
        bool_value(
            self.allow_cached_observations,
            "WorkerTelemetryScope.allow_cached_observations",
        )
        int_value(
            self.minimum_poll_interval_ms,
            "WorkerTelemetryScope.minimum_poll_interval_ms",
            minimum=MIN_POLL_INTERVAL_MS,
            maximum=MAX_DURATION_MS,
        )
        int_value(
            self.maximum_concurrent_queries,
            "WorkerTelemetryScope.maximum_concurrent_queries",
            minimum=1,
            maximum=MAX_CONCURRENT_QUERIES,
        )

    @property
    def controller_identity(self) -> ContentIdentity:
        return telemetry_key_identity(self.controller_public_key)

    @property
    def worker_signer_identity(self) -> ContentIdentity:
        return telemetry_key_identity(self.worker_public_key)

    @property
    def identity(self) -> ContentIdentity:
        return canonical_identity(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "worker_id": self.worker_id,
            "worker_identity": self.worker_identity.to_dict(),
            "registration_identity": self.registration_identity.to_dict(),
            "catalog_identity": self.catalog_identity.to_dict(),
            "controller_public_key": self.controller_public_key,
            "worker_public_key": self.worker_public_key,
            "operation_identities": [
                action.to_dict() for action in self.operation_identities
            ],
            "allow_host_aggregate": self.allow_host_aggregate,
            "not_before_ms": self.not_before_ms,
            "expires_at_ms": self.expires_at_ms,
            "maximum_duration_ms": self.maximum_duration_ms,
            "maximum_sample_age_ms": self.maximum_sample_age_ms,
            "allow_cached_observations": self.allow_cached_observations,
            "minimum_poll_interval_ms": self.minimum_poll_interval_ms,
            "maximum_concurrent_queries": self.maximum_concurrent_queries,
        }

    @classmethod
    def from_dict(cls, value: Any) -> WorkerTelemetryScope:
        data = contract_fields(
            value,
            path="WorkerTelemetryScope",
            schema_uri=cls.SCHEMA,
            required=frozenset(
                {
                    "worker_id",
                    "worker_identity",
                    "registration_identity",
                    "catalog_identity",
                    "controller_public_key",
                    "worker_public_key",
                    "operation_identities",
                    "allow_host_aggregate",
                    "not_before_ms",
                    "expires_at_ms",
                    "maximum_duration_ms",
                    "maximum_sample_age_ms",
                    "allow_cached_observations",
                    "minimum_poll_interval_ms",
                    "maximum_concurrent_queries",
                }
            ),
        )
        rows = list_value(
            data["operation_identities"], "WorkerTelemetryScope.operation_identities"
        )
        if len(rows) > MAX_OPERATIONS:
            fail(
                "WorkerTelemetryScope.operation_identities",
                "must contain at most 64 entries",
            )
        return cls(
            data["worker_id"],
            ContentIdentity.from_dict(data["worker_identity"]),
            ContentIdentity.from_dict(data["registration_identity"]),
            ContentIdentity.from_dict(data["catalog_identity"]),
            data["controller_public_key"],
            data["worker_public_key"],
            tuple(ContentIdentity.from_dict(row) for row in rows),
            data["allow_host_aggregate"],
            data["not_before_ms"],
            data["expires_at_ms"],
            data["maximum_duration_ms"],
            data["maximum_sample_age_ms"],
            data["allow_cached_observations"],
            data["minimum_poll_interval_ms"],
            data["maximum_concurrent_queries"],
        )

    def require_request(self, request: WorkerTelemetryRequest, *, now_ms: int) -> None:
        """Validate configured-scope projection/time, not signatures or live owners."""
        int_value(now_ms, "WorkerTelemetryScope.now_ms")
        if type(request) is not WorkerTelemetryRequest:
            fail("WorkerTelemetryScope", "must receive a typed observation request")
        if (
            request.observation_scope_identity != self.identity
            or request.worker_id != self.worker_id
            or request.worker_identity != self.worker_identity
            or request.registration_identity != self.registration_identity
            or request.catalog_identity != self.catalog_identity
            or request.controller_identity != self.controller_identity
        ):
            fail("WorkerTelemetryScope", "exact configured observation binding differs")
        if (
            not self.not_before_ms
            <= request.issued_at_ms
            <= now_ms
            < request.expires_at_ms
            <= self.expires_at_ms
        ):
            fail(
                "WorkerTelemetryScope",
                "observation request is outside current scope time",
            )
        if (
            request.expires_at_ms - request.issued_at_ms > self.maximum_duration_ms
            or request.maximum_sample_age_ms > self.maximum_sample_age_ms
        ):
            fail(
                "WorkerTelemetryScope", "observation request exceeds configured budgets"
            )
        if request.allow_cached_observations and not self.allow_cached_observations:
            fail(
                "WorkerTelemetryScope",
                "configured scope does not permit cached observations",
            )
        if request.scope is TelemetryScope.WORKER_HOST:
            if not self.allow_host_aggregate:
                fail("WorkerTelemetryScope", "aggregate observation is not permitted")
        elif not set(request.operation_identities).issubset(self.operation_identities):
            fail(
                "WorkerTelemetryScope",
                "observation selection is outside configured actions",
            )
