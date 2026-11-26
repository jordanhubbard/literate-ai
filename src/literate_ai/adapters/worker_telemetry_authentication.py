"""Authenticated observation frames, never execution or live-owner grants.

The actual receiver must reopen the configured scope and establish current
registration, replay/rate limits and live action ownership independently. This
module reuses the existing Ed25519 evidence signer and length-framed DSSE PAE;
its closed telemetry frame is not the external DSSE JSON envelope format.
"""

from __future__ import annotations

import re
from typing import Any

from literate_ai.contracts._validation import fields, int_value
from literate_ai.contracts.identity import ContentIdentity, canonical_json_bytes
from literate_ai.contracts.worker_telemetry import (
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    WorkerTelemetryRequest,
    WorkerTelemetryResponse,
)
from literate_ai.contracts.worker_telemetry_authorization import WorkerTelemetryScope
from literate_ai.security.evidence.dsse import DsseEnvelope, DsseError, DsseSignature
from literate_ai.security.evidence.ed25519 import (
    Ed25519EvidenceSigner,
    verify_ed25519_envelope,
)

from .worker_telemetry_wire import WorkerTelemetryWireError, _decode

_REQUEST = "literate-ai/authenticated-worker-telemetry-request@1"
_RESPONSE = "literate-ai/authenticated-worker-telemetry-response@1"
_SIGNATURE = re.compile(r"[0-9a-f]{128}\Z")


def _scope(value: Any) -> WorkerTelemetryScope:
    if type(value) is not WorkerTelemetryScope:
        raise WorkerTelemetryWireError("worker_telemetry.scope_required")
    return value


def _frame(
    payload: dict[str, object],
    *,
    schema: str,
    scope: WorkerTelemetryScope,
    signer: Ed25519EvidenceSigner,
    public_key: str,
    signer_identity: ContentIdentity,
    maximum: int,
) -> bytes:
    if (
        type(signer) is not Ed25519EvidenceSigner
        or signer.public_key.hex() != public_key
    ):
        raise WorkerTelemetryWireError("worker_telemetry.signer_mismatch")
    body = canonical_json_bytes(payload)
    envelope = signer.sign(schema, body)
    frame = canonical_json_bytes(
        {
            "schema": schema,
            "observation_scope_identity": scope.identity.to_dict(),
            "signer_identity": signer_identity.to_dict(),
            "payload": payload,
            "signature": envelope.signatures[0].signature.hex(),
        }
    )
    # Measure the complete actual signed representation, not an estimated header.
    if len(frame) > maximum:
        raise WorkerTelemetryWireError("worker_telemetry.frame_limit")
    return frame


def _verified_payload(
    raw: bytes,
    *,
    schema: str,
    scope: WorkerTelemetryScope,
    public_key: str,
    signer_identity: ContentIdentity,
    maximum: int,
) -> Any:
    value = _decode(raw, maximum)
    try:
        data = fields(
            value,
            path="WorkerTelemetryAuthenticatedFrame",
            required=frozenset(
                {
                    "schema",
                    "observation_scope_identity",
                    "signer_identity",
                    "payload",
                    "signature",
                }
            ),
        )
        if (
            data["schema"] != schema
            or ContentIdentity.from_dict(data["observation_scope_identity"])
            != scope.identity
            or ContentIdentity.from_dict(data["signer_identity"]) != signer_identity
            or not isinstance(data["signature"], str)
            or not _SIGNATURE.fullmatch(data["signature"])
        ):
            raise WorkerTelemetryWireError("worker_telemetry.frame_mismatch")
        payload = canonical_json_bytes(data["payload"])
        envelope = DsseEnvelope(
            schema,
            payload,
            (DsseSignature(bytes.fromhex(data["signature"]), signer_identity.uri),),
        )
        verified = verify_ed25519_envelope(
            envelope,
            trusted_public_keys=(bytes.fromhex(public_key),),
            expected_payload_type=schema,
        )
        if verified.payload != payload:
            raise WorkerTelemetryWireError("worker_telemetry.invalid_signature")
        return data["payload"]
    except WorkerTelemetryWireError:
        raise
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise WorkerTelemetryWireError("worker_telemetry.invalid_signature") from exc


def encode_telemetry_request(
    request: WorkerTelemetryRequest,
    scope: WorkerTelemetryScope,
    signer: Ed25519EvidenceSigner,
    *,
    now_ms: int,
) -> bytes:
    scope = _scope(scope)
    scope.require_request(request, now_ms=now_ms)
    return _frame(
        request.to_dict(),
        schema=_REQUEST,
        scope=scope,
        signer=signer,
        public_key=scope.controller_public_key,
        signer_identity=scope.controller_identity,
        maximum=MAX_REQUEST_BYTES,
    )


def verify_telemetry_request(
    raw: bytes, scope: WorkerTelemetryScope, *, now_ms: int
) -> WorkerTelemetryRequest:
    scope = _scope(scope)
    value = _verified_payload(
        raw,
        schema=_REQUEST,
        scope=scope,
        public_key=scope.controller_public_key,
        signer_identity=scope.controller_identity,
        maximum=MAX_REQUEST_BYTES,
    )
    try:
        request = WorkerTelemetryRequest.from_dict(value)
        scope.require_request(request, now_ms=now_ms)
        return request
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise WorkerTelemetryWireError("worker_telemetry.request_denied") from exc


def _current_response(
    response: WorkerTelemetryResponse,
    request: WorkerTelemetryRequest,
    scope: WorkerTelemetryScope,
    now_ms: int,
) -> None:
    int_value(now_ms, "WorkerTelemetryResponse.now_ms")
    scope.require_request(request, now_ms=now_ms)
    if type(response) is not WorkerTelemetryResponse:
        raise WorkerTelemetryWireError("worker_telemetry.response_required")
    response.require_request(request)
    if any(
        not 0 <= now_ms - sample.observed_at_ms <= request.maximum_sample_age_ms
        for sample in response.samples
    ):
        raise WorkerTelemetryWireError("worker_telemetry.sample_stale")


def encode_telemetry_response(
    response: WorkerTelemetryResponse,
    request: WorkerTelemetryRequest,
    scope: WorkerTelemetryScope,
    signer: Ed25519EvidenceSigner,
    *,
    now_ms: int,
) -> bytes:
    scope = _scope(scope)
    _current_response(response, request, scope, now_ms)
    return _frame(
        response.to_dict(),
        schema=_RESPONSE,
        scope=scope,
        signer=signer,
        public_key=scope.worker_public_key,
        signer_identity=scope.worker_signer_identity,
        maximum=MAX_RESPONSE_BYTES,
    )


def verify_telemetry_response(
    raw: bytes,
    request: WorkerTelemetryRequest,
    scope: WorkerTelemetryScope,
    *,
    now_ms: int,
) -> WorkerTelemetryResponse:
    scope = _scope(scope)
    value = _verified_payload(
        raw,
        schema=_RESPONSE,
        scope=scope,
        public_key=scope.worker_public_key,
        signer_identity=scope.worker_signer_identity,
        maximum=MAX_RESPONSE_BYTES,
    )
    try:
        response = WorkerTelemetryResponse.from_dict(value)
        _current_response(response, request, scope, now_ms)
        return response
    except (DsseError, ValueError, TypeError, KeyError, RecursionError) as exc:
        raise WorkerTelemetryWireError("worker_telemetry.response_denied") from exc
