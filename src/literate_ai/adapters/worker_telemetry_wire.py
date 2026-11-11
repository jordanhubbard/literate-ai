"""Finite newline-framed telemetry codec, with no transport or authority grants.

The caller must cap transport reads before accumulating these bytes. Successful
parsing establishes only correspondence to an untrusted request, not current
permission, freshness, authentication, replay acceptance or a live action owner.
"""

from __future__ import annotations

import json

from literate_ai.contracts._validation import contract_fields, enum_value, int_value
from literate_ai.contracts.identity import ContentIdentity, canonical_json_bytes
from literate_ai.contracts.worker_telemetry import (
    MAX_TELEMETRY_ACTIONS,
    MAX_TELEMETRY_RESPONSE_BYTES,
    MAX_TELEMETRY_SAMPLE_BYTES,
    WorkerTelemetryRequest,
)
from literate_ai.contracts.worker_telemetry_observations import (
    TelemetryResponseStatus,
    WorkerTelemetryObservation,
    WorkerTelemetryResponse,
)


class TelemetryWireError(ValueError):
    """Fixed public category; never include attacker-controlled field text."""


def _fail(code):
    raise TelemetryWireError("worker.telemetry_wire_" + code)


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            _fail("duplicate_field")
        result[key] = value
    return result


def _nonfinite(_value):
    _fail("nonfinite")


def _load(record):
    try:
        return json.loads(
            record.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_nonfinite
        )
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise TelemetryWireError("worker.telemetry_wire_invalid") from exc


def _record(value):
    raw = canonical_json_bytes(value) + b"\n"
    if len(raw) > MAX_TELEMETRY_SAMPLE_BYTES:
        _fail("record_limit")
    return raw


def encode_telemetry_request(request: WorkerTelemetryRequest) -> bytes:
    if not isinstance(request, WorkerTelemetryRequest):
        _fail("request_type")
    return _record(request.to_dict())


def decode_telemetry_request(raw: bytes) -> WorkerTelemetryRequest:
    if type(raw) is not bytes:
        _fail("bytes_required")
    if len(raw) > MAX_TELEMETRY_SAMPLE_BYTES:
        _fail("record_limit")
    if not raw.endswith(b"\n") or raw.count(b"\n") != 1:
        _fail("framing")
    try:
        return WorkerTelemetryRequest.from_dict(_load(raw[:-1]))
    except (ValueError, TypeError, AttributeError) as exc:
        raise TelemetryWireError("worker.telemetry_wire_invalid_request") from exc


def encode_telemetry_response(
    response: WorkerTelemetryResponse, request: WorkerTelemetryRequest
) -> bytes:
    if not isinstance(response, WorkerTelemetryResponse):
        _fail("response_type")
    response.require_request_binding(request)
    parts = [_record(response.header())]
    size = len(parts[0])
    for sample in response.samples:
        record = _record(sample.to_dict())
        size += len(record)
        if size > MAX_TELEMETRY_RESPONSE_BYTES:
            _fail("response_limit")
        parts.append(record)
    return b"".join(parts)


def decode_telemetry_response(
    raw: bytes, request: WorkerTelemetryRequest
) -> WorkerTelemetryResponse:
    if type(raw) is not bytes:
        _fail("bytes_required")
    # Bound complete framing before allocating a line list or decoding JSON.
    if len(raw) > MAX_TELEMETRY_RESPONSE_BYTES:
        _fail("response_limit")
    count = raw.count(b"\n")
    if not raw.endswith(b"\n") or not 1 <= count <= MAX_TELEMETRY_ACTIONS + 1:
        _fail("framing")
    records = raw[:-1].split(b"\n")
    if any(len(record) + 1 > MAX_TELEMETRY_SAMPLE_BYTES for record in records):
        _fail("record_limit")
    try:
        d = contract_fields(
            _load(records[0]),
            path="WorkerTelemetryResponse",
            schema_uri=WorkerTelemetryResponse.SCHEMA,
            required=frozenset(
                {
                    "request_identity",
                    "worker_identity",
                    "observation_scope_identity",
                    "observer_epoch",
                    "sequence",
                    "observed_at_ms",
                    "expires_at_ms",
                    "status",
                    "sample_count",
                }
            ),
        )
        size = int_value(
            d["sample_count"], "telemetry.sample_count", maximum=MAX_TELEMETRY_ACTIONS
        )
        if size != len(records) - 1:
            _fail("sample_count")
        # Reject mismatched headers before decoding or retaining any sample.
        if (
            d["request_identity"] != request.identity.uri
            or d["worker_identity"] != request.worker_identity.uri
            or d["observation_scope_identity"] != request.observation_scope_identity.uri
            or d["expires_at_ms"] != request.expires_at_ms
        ):
            _fail("request_binding")
        response = WorkerTelemetryResponse(
            ContentIdentity.parse_uri(d["request_identity"]),
            ContentIdentity.parse_uri(d["worker_identity"]),
            ContentIdentity.parse_uri(d["observation_scope_identity"]),
            ContentIdentity.parse_uri(d["observer_epoch"]),
            d["sequence"],
            d["observed_at_ms"],
            d["expires_at_ms"],
            enum_value(TelemetryResponseStatus, d["status"], "response.status"),
            tuple(
                WorkerTelemetryObservation.from_dict(_load(record))
                for record in records[1:]
            ),
        )
        response.require_request_binding(request)
        return response
    except (ValueError, TypeError, AttributeError, RecursionError) as exc:
        raise TelemetryWireError("worker.telemetry_wire_invalid_response") from exc
