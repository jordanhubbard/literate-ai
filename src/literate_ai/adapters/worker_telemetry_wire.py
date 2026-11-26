"""Finite telemetry JSON decoding; this module grants no observation permission."""

from __future__ import annotations

import json
from typing import Any

from literate_ai.contracts.worker_telemetry import (
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    WorkerTelemetryRequest,
    WorkerTelemetryResponse,
)


class WorkerTelemetryWireError(ValueError):
    """Safe protocol error with no echoed input, paths or exception messages."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise WorkerTelemetryWireError("worker_telemetry.duplicate_field")
        result[name] = value
    return result


def _integer(value: str) -> int:
    if len(value.lstrip("-")) > 19:
        raise WorkerTelemetryWireError("worker_telemetry.invalid_integer")
    number = int(value)
    if not -(2**63) <= number <= 2**63 - 1:
        raise WorkerTelemetryWireError("worker_telemetry.invalid_integer")
    return number


def _noninteger(value: str) -> Any:
    raise WorkerTelemetryWireError("worker_telemetry.invalid_number")


def _decode(raw: bytes, maximum: int) -> Any:
    if type(raw) is not bytes or not raw or len(raw) > maximum:
        raise WorkerTelemetryWireError("worker_telemetry.frame_limit")
    try:
        return json.loads(
            raw,
            object_pairs_hook=_pairs,
            parse_int=_integer,
            parse_float=_noninteger,
            parse_constant=_noninteger,
        )
    except WorkerTelemetryWireError:
        raise
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise WorkerTelemetryWireError("worker_telemetry.invalid_json") from exc


def decode_worker_telemetry_request(raw: bytes) -> WorkerTelemetryRequest:
    value = _decode(raw, MAX_REQUEST_BYTES)
    try:
        return WorkerTelemetryRequest.from_dict(value)
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise WorkerTelemetryWireError("worker_telemetry.invalid_request") from exc


def decode_worker_telemetry_response(raw: bytes) -> WorkerTelemetryResponse:
    # The enclosing authenticated frame owns the remaining 4096 bytes. Merely
    # parsing this body cannot turn an unattested sample into trusted telemetry.
    value = _decode(raw, MAX_RESPONSE_BYTES - 4096)
    try:
        return WorkerTelemetryResponse.from_dict(value)
    except (ValueError, TypeError, KeyError, RecursionError) as exc:
        raise WorkerTelemetryWireError("worker_telemetry.invalid_response") from exc
