"""One finite authenticated observation through the selected worker's own route."""

from __future__ import annotations

import secrets
import time
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

from literate_ai.contracts._validation import bool_value, int_value
from literate_ai.contracts.execution_dispatch import ExecutionWorkerKind
from literate_ai.contracts.identity import ContentIdentity, canonical_json_bytes
from literate_ai.contracts.worker_telemetry import (
    MAX_OPERATIONS,
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    TelemetryScope,
    WorkerTelemetryRequest,
)

from .action_command_dispatch import command_worker_environment
from .action_dispatch_wire import ActionDispatchDeadline
from .action_transport import action_receiver_command, supports_action_transport
from .builders._process import run_bounded_process
from .builders.python import BuildError
from .worker_telemetry_authentication import (
    encode_telemetry_request,
    verify_telemetry_response,
)
from .worker_telemetry_configuration import load_worker_telemetry_configuration
from .worker_telemetry_wire import WorkerTelemetryWireError, _decode


def query_worker_telemetry(
    configuration_path: Path,
    *,
    worker_id: str,
    operations: tuple[ContentIdentity, ...],
    worker_host: bool = False,
    timeout_ms: int = 10000,
    maximum_sample_age_ms: int = 5000,
    allow_cached_observations: bool = False,
    environment: Mapping[str, str],
) -> dict[str, object]:
    """No retries, job dispatch, historical owners or alternative transport argv.

    The private controller command must equal the selected catalog receiver.
    Only a fixed observation mode is appended; the receiver's private wrapper
    owns its local configuration path. No wire field can select that path.
    """
    int_value(timeout_ms, "WorkerTelemetry.timeout_ms", minimum=1, maximum=30000)
    int_value(
        maximum_sample_age_ms,
        "WorkerTelemetry.maximum_sample_age_ms",
        minimum=1,
        maximum=30000,
    )
    bool_value(worker_host, "WorkerTelemetry.worker_host")
    bool_value(allow_cached_observations, "WorkerTelemetry.allow_cached_observations")
    if (
        type(operations) is not tuple
        or len(operations) > MAX_OPERATIONS
        or any(type(item) is not ContentIdentity for item in operations)
        or len(set(operations)) != len(operations)
        or bool(operations) == worker_host
    ):
        raise WorkerTelemetryWireError("worker_telemetry.operation_selection_invalid")
    ends = time.monotonic() + timeout_ms / 1000
    deadline = ActionDispatchDeadline(
        datetime.now(UTC) + timedelta(milliseconds=timeout_ms)
    )
    configuration = load_worker_telemetry_configuration(
        configuration_path, role="controller", deadline=deadline
    )
    selected = configuration.worker
    if selected.worker_id != worker_id or not supports_action_transport(selected):
        raise WorkerTelemetryWireError("worker_telemetry.configured_worker_mismatch")
    receiver = (
        selected.command
        if selected.kind is ExecutionWorkerKind.COMMAND
        else selected.action_command
    )
    if configuration.receiver_command != receiver:
        raise WorkerTelemetryWireError("worker_telemetry.receiver_route_mismatch")

    def current():
        if time.monotonic() >= ends:
            raise WorkerTelemetryWireError("worker_telemetry.query_expired")
        configuration.require_current(deadline=deadline)
        if time.monotonic() >= ends:
            raise WorkerTelemetryWireError("worker_telemetry.query_expired")

    current()
    scope = configuration.scope
    request = WorkerTelemetryRequest(
        selected.worker_id,
        selected.identity,
        configuration.registration_identity,
        configuration.catalog.identity,
        scope.controller_identity,
        scope.identity,
        TelemetryScope.WORKER_HOST if worker_host else TelemetryScope.OPERATIONS,
        tuple(sorted(operations, key=lambda item: item.uri)),
        secrets.token_hex(16),
        int(datetime.now(UTC).timestamp() * 1000),
        int(deadline.expires_at.timestamp() * 1000),
        maximum_sample_age_ms,
        allow_cached_observations,
    )
    raw = encode_telemetry_request(
        request, scope, configuration.signer, now_ms=int(time.time() * 1000)
    )
    command = action_receiver_command(selected, deadline, mode="--observe-telemetry")
    current()
    try:
        result = run_bounded_process(
            command,
            cwd=None,
            environment=command_worker_environment(
                selected, environment, protocol="literate-ai/worker-telemetry@1"
            ),
            timeout_seconds=min(deadline.remaining(), ends - time.monotonic()),
            stdout_limit_bytes=MAX_RESPONSE_BYTES,
            stderr_limit_bytes=4096,
            input_bytes=raw,
            input_limit_bytes=MAX_REQUEST_BYTES,
            interrupt_guard=current,
            terminate_descendants=True,
            error_prefix="worker_telemetry.transport",
            trace=False,
        )
    except BuildError as exc:
        raise WorkerTelemetryWireError(
            "worker_telemetry.transport_unavailable"
        ) from exc
    current()
    if result.returncode != 0:
        # Refusals and old unsupported receivers are not authenticated samples.
        # Never expose their arbitrary stdout/stderr as trusted observations.
        raise WorkerTelemetryWireError("worker_telemetry.receiver_refused")
    verify_telemetry_response(
        result.stdout, request, scope, now_ms=int(time.time() * 1000)
    )
    current()
    observation = {
        "schema": "literate-ai/worker-telemetry-query-result@1",
        "request": request.to_dict(),
        "authenticated_response": _decode(result.stdout, MAX_RESPONSE_BYTES),
    }
    # Reserve space for the ordinary CLI envelope. This is an output bound,
    # additional to the independently measured authenticated response frame.
    if len(canonical_json_bytes(observation)) > MAX_RESPONSE_BYTES - 4096:
        raise WorkerTelemetryWireError("worker_telemetry.frame_limit")
    return observation
