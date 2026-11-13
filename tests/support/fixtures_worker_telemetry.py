"""Pure telemetry data fixtures; no permission, process owner or authentication."""

from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.worker_telemetry import (
    TelemetryMeasurementScope,
    TelemetryMetricName,
    TelemetryMetricStatus,
    TelemetryScope,
    WorkerTelemetryMetric,
    WorkerTelemetryProgress,
    WorkerTelemetryRequest,
)
from literate_ai.contracts.worker_telemetry_observations import (
    TelemetryActionState,
    TelemetryResponseStatus,
    TelemetryStage,
    WorkerTelemetryObservation,
    WorkerTelemetryResponse,
)


def telemetry_request(count=1, *, aggregate=False):
    return WorkerTelemetryRequest(
        *(
            canonical_identity(n)
            for n in ("controller", "catalog", "registration", "worker", "permission")
        ),
        "a" * 64,
        1000,
        31000,
        TelemetryScope.WORKER_AGGREGATE if aggregate else TelemetryScope.ACTIONS,
        ()
        if aggregate
        else tuple(
            sorted((canonical_identity(n) for n in range(count)), key=lambda i: i.uri)
        ),
    )


def telemetry_observation(action):
    return WorkerTelemetryObservation(
        action,
        None if action is None else canonical_identity("reservation"),
        None if action is None else canonical_identity("process-start"),
        canonical_identity("owner-epoch"),
        canonical_identity("counter-epoch"),
        2000,
        TelemetryStage.UNKNOWN if action is None else TelemetryStage.BUILD,
        TelemetryActionState.UNKNOWN
        if action is None
        else TelemetryActionState.RUNNING,
        WorkerTelemetryProgress(),
        tuple(
            WorkerTelemetryMetric(
                n,
                TelemetryMeasurementScope.WORKER_HOST
                if action is None
                else TelemetryMeasurementScope.PROCESS_SUBTREE,
                TelemetryMetricStatus.UNSUPPORTED,
                None,
            )
            for n in sorted(TelemetryMetricName, key=lambda n: n.value)
        ),
    )


def telemetry_response(request):
    return WorkerTelemetryResponse(
        request.identity,
        request.worker_identity,
        request.observation_scope_identity,
        canonical_identity("observer-epoch"),
        0,
        2000,
        request.expires_at_ms,
        TelemetryResponseStatus.OBSERVED,
        tuple(telemetry_observation(a) for a in request.action_identities)
        if request.action_identities
        else (telemetry_observation(None),),
    )
