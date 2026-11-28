"""Fresh signed samples from actual local owners for a cross-process batch.

The relay may assemble a64-action request only from nonce-bound contributions
serviced by those live owners. Directory records merely locate finite slots;
decoding them cannot construct owners or answer a new challenge. This internal
telemetry family changes no legacy action/descriptor protocol.
"""

from __future__ import annotations

from datetime import UTC, datetime

from literate_ai.contracts._validation import fields
from literate_ai.contracts.identity import ContentIdentity, canonical_json_bytes
from literate_ai.contracts.worker_telemetry_authorization import WorkerTelemetryScope
from literate_ai.contracts.worker_telemetry_v2 import (
    MAX_SAMPLE_BYTES,
    TelemetrySampleSource,
    TelemetryScope,
    WorkerTelemetryRequest,
    WorkerTelemetrySample,
)

from .action_dispatch_wire import ActionDispatchDeadline
from .worker_telemetry_authentication_v2 import (
    _frame,
    _verified_payload,
    verify_telemetry_request,
)
from .worker_telemetry_owner import ConfiguredWorkerTelemetryPublisher
from .worker_telemetry_wire_v2 import WorkerTelemetryWireError

_SCHEMA = "literate-ai/private-worker-telemetry-contribution@1"
MAX_CONTRIBUTION_BYTES = MAX_SAMPLE_BYTES + 4096


def _refuse(code):
    raise WorkerTelemetryWireError("worker_telemetry." + code)


def _require_sample(sample, request, scope, operation_identity, now_ms):
    scope.require_request(request, now_ms=now_ms)
    if (
        request.scope is not TelemetryScope.OPERATIONS
        or type(operation_identity) is not ContentIdentity
        or operation_identity not in request.operation_identities
        or sample.operation_identity != operation_identity
        or not 0 <= now_ms - sample.observed_at_ms <= request.maximum_sample_age_ms
        or sample.observed_at_ms > request.expires_at_ms
        or sample.observed_at_ms
        < request.issued_at_ms
        - (request.maximum_sample_age_ms if request.allow_cached_observations else 0)
        or (
            sample.source is TelemetrySampleSource.FRESH
            and sample.observed_at_ms < request.issued_at_ms
        )
        or (
            sample.source is TelemetrySampleSource.CACHED
            and not request.allow_cached_observations
        )
    ):
        _refuse("contribution_mismatch")


def contribute_actual_worker_sample(
    publisher: ConfiguredWorkerTelemetryPublisher,
    raw_request: bytes,
    operation_identity: ContentIdentity,
) -> bytes:
    """Called only by the existing actual publisher's bounded background relay.

    Global replay/rate admission belongs to the query relay, once per complete
    batch. A contribution cannot itself become a complete trusted batch response.
    No path, PID, command, environment or historical-owner factory is accepted.
    """
    if type(publisher) is not ConfiguredWorkerTelemetryPublisher:
        _refuse("actual_receiver_required")
    publisher._require_local()
    configuration = publisher._configuration
    request = verify_telemetry_request(
        raw_request,
        configuration.scope,
        now_ms=int(datetime.now(UTC).timestamp() * 1000),
    )
    if (
        request.scope is not TelemetryScope.OPERATIONS
        or type(operation_identity) is not ContentIdentity
        or operation_identity not in request.operation_identities
    ):
        _refuse("contribution_mismatch")
    if not publisher._lock.acquire(blocking=False):
        _refuse("observation_overloaded")
    try:
        owner = publisher._owners.get(operation_identity)
        if owner is None:
            _refuse("owner_unavailable")
    finally:
        publisher._lock.release()
    sample = owner.sample(request=request)
    _require_sample(
        sample,
        request,
        configuration.scope,
        operation_identity,
        int(datetime.now(UTC).timestamp() * 1000),
    )
    payload = {
        "schema": _SCHEMA,
        "request_identity": request.identity.to_dict(),
        "publisher_epoch": publisher._epoch.to_dict(),
        "sample": sample.to_dict(),
    }
    frame = _frame(
        payload,
        schema=_SCHEMA,
        scope=configuration.scope,
        signer=configuration.signer,
        public_key=configuration.scope.worker_public_key,
        signer_identity=configuration.scope.worker_signer_identity,
        maximum=MAX_CONTRIBUTION_BYTES,
    )
    configuration.require_current(
        deadline=ActionDispatchDeadline(
            datetime.fromtimestamp(request.expires_at_ms / 1000, UTC)
        )
    )
    owner.require_open()
    _require_sample(
        sample,
        request,
        configuration.scope,
        operation_identity,
        int(datetime.now(UTC).timestamp() * 1000),
    )
    return frame


def verify_worker_telemetry_contribution(
    raw,
    *,
    request,
    scope,
    expected_operation_identity,
    expected_publisher_epoch,
    now_ms,
) -> WorkerTelemetrySample:
    """Verify one exact fresh challenge response; returns a sample, never an owner."""
    if (
        type(request) is not WorkerTelemetryRequest
        or type(scope) is not WorkerTelemetryScope
    ):
        _refuse("contribution_mismatch")
    payload = _verified_payload(
        raw,
        schema=_SCHEMA,
        scope=scope,
        public_key=scope.worker_public_key,
        signer_identity=scope.worker_signer_identity,
        maximum=MAX_CONTRIBUTION_BYTES,
    )
    try:
        value = fields(
            payload,
            path="WorkerTelemetryContribution",
            required=frozenset(
                {"schema", "request_identity", "publisher_epoch", "sample"}
            ),
        )
        if (
            value["schema"] != _SCHEMA
            or ContentIdentity.from_dict(value["request_identity"]) != request.identity
            or type(expected_publisher_epoch) is not ContentIdentity
            or ContentIdentity.from_dict(value["publisher_epoch"])
            != expected_publisher_epoch
            or len(canonical_json_bytes(value["sample"])) > MAX_SAMPLE_BYTES
        ):
            _refuse("contribution_mismatch")
        sample = WorkerTelemetrySample.from_dict(value["sample"])
        _require_sample(sample, request, scope, expected_operation_identity, now_ms)
        return sample
    except WorkerTelemetryWireError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise WorkerTelemetryWireError("worker_telemetry.contribution_invalid") from exc
