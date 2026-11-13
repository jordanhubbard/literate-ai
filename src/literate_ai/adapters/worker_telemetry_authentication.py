"""Telemetry-only message authentication using explicitly supplied private keys.

Authenticating a principal does not grant observation scope or reopen an action
owner. A receiver must separately authorize current registration/action scope,
atomically refuse replay, and verify live owners before collecting anything.
No credential discovery, transport, listener or execution capability lives here.
"""

from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass, field
from typing import BinaryIO

from literate_ai.adapters.worker_telemetry_wire import (
    _load,
    decode_telemetry_request,
    decode_telemetry_response,
    encode_telemetry_request,
    encode_telemetry_response,
)
from literate_ai.application.worker_telemetry_authentication import (
    AuthenticatedTelemetryRequest,
    _authenticated_telemetry_request,
)
from literate_ai.contracts._validation import contract_fields, int_value
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.worker_telemetry import (
    MAX_TELEMETRY_RESPONSE_BYTES,
    MAX_TELEMETRY_SAMPLE_BYTES,
    WorkerTelemetryRequest,
)
from literate_ai.contracts.worker_telemetry_observations import WorkerTelemetryResponse

AUTHENTICATED_TELEMETRY_REQUEST = "literate-ai/authenticated-worker-telemetry-request@1"
AUTHENTICATED_TELEMETRY_RESPONSE = (
    "literate-ai/authenticated-worker-telemetry-response@1"
)
MAX_TELEMETRY_AUTH_HEADER_BYTES = 1024
_SIGNATURE = re.compile(r"[0-9a-f]{64}\Z")
_DOMAIN = b"literate-ai:observation-only-telemetry:v1\0"


class TelemetryAuthenticationError(ValueError):
    """Fixed safe failure category, without credentials or untrusted metadata."""


def _fail(reason):
    raise TelemetryAuthenticationError("worker.telemetry_auth_" + reason)


@dataclass(frozen=True, slots=True)
class TelemetryObservationCredential:
    principal_identity: ContentIdentity
    _secret: bytes = field(repr=False)
    key_identity: ContentIdentity = field(init=False)

    def __post_init__(self):
        if (
            not isinstance(self.principal_identity, ContentIdentity)
            or type(self._secret) is not bytes
            or not 32 <= len(self._secret) <= 4096
        ):
            _fail("credential_invalid")
        object.__setattr__(
            self,
            "key_identity",
            canonical_identity(
                {
                    "schema": "literate-ai/observation-only-key-identity@1",
                    "principal_identity": self.principal_identity.uri,
                    "key_sha256": hashlib.sha256(self._secret).hexdigest(),
                }
            ),
        )


def _credential(credential):
    if type(credential) is not TelemetryObservationCredential:
        _fail("credential_required")


def _signature(credential, schema, header, body):
    # The schema domain and length-bound canonical header prevent request/response
    # reflection and ambiguity between header bytes and the complete framed body.
    return hmac.new(
        credential._secret,
        _DOMAIN
        + schema.encode("ascii")
        + b"\0"
        + canonical_json_bytes(header)
        + b"\0"
        + body,
        hashlib.sha256,
    ).hexdigest()


def _seal(body, credential, schema, maximum):
    _credential(credential)
    header = {
        "schema": schema,
        "principal_identity": credential.principal_identity.uri,
        "key_identity": credential.key_identity.uri,
        "body_bytes": len(body),
    }
    header["signature"] = _signature(credential, schema, header, body)
    raw_header = canonical_json_bytes(header) + b"\n"
    if (
        len(raw_header) > MAX_TELEMETRY_AUTH_HEADER_BYTES
        or len(raw_header) + len(body) > maximum
    ):
        _fail("size_limit")
    return raw_header + body


def _open(raw, credential, schema, maximum):
    _credential(credential)
    if type(raw) is not bytes or len(raw) > maximum:
        _fail("size_limit")
    end = raw.find(b"\n", 0, MAX_TELEMETRY_AUTH_HEADER_BYTES)
    if end < 0:
        _fail("header_limit")
    try:
        header = dict(
            contract_fields(
                _load(raw[:end]),
                path="TelemetryAuthentication",
                schema_uri=schema,
                required=frozenset(
                    {"principal_identity", "key_identity", "body_bytes", "signature"}
                ),
            )
        )
        size = int_value(
            header["body_bytes"], "telemetry.auth_body", minimum=1, maximum=maximum
        )
        if (
            size != len(raw) - end - 1
            or header["principal_identity"] != credential.principal_identity.uri
            or header["key_identity"] != credential.key_identity.uri
        ):
            _fail("binding_invalid")
        signature = header.pop("signature")
        if not isinstance(signature, str) or not _SIGNATURE.fullmatch(signature):
            _fail("signature_invalid")
        body = raw[end + 1 :]
        if not hmac.compare_digest(
            signature, _signature(credential, schema, header, body)
        ):
            _fail("signature_invalid")
        return body
    except (ValueError, TypeError, AttributeError, UnicodeError):
        raise TelemetryAuthenticationError("worker.telemetry_auth_invalid") from None


def _current(request, now_ms):
    int_value(now_ms, "telemetry.auth_now_ms")
    if not request.issued_at_ms <= now_ms < request.expires_at_ms:
        _fail("expired_or_future")


def sign_telemetry_request(
    request: WorkerTelemetryRequest, credential: TelemetryObservationCredential
) -> bytes:
    _credential(credential)
    if (
        not isinstance(request, WorkerTelemetryRequest)
        or request.controller_identity != credential.principal_identity
    ):
        _fail("principal_mismatch")
    return _seal(
        encode_telemetry_request(request),
        credential,
        AUTHENTICATED_TELEMETRY_REQUEST,
        MAX_TELEMETRY_SAMPLE_BYTES,
    )


def authenticate_telemetry_request(
    raw: bytes, credential: TelemetryObservationCredential, *, now_ms: int
) -> AuthenticatedTelemetryRequest:
    body = _open(
        raw, credential, AUTHENTICATED_TELEMETRY_REQUEST, MAX_TELEMETRY_SAMPLE_BYTES
    )
    request = decode_telemetry_request(body)
    if request.controller_identity != credential.principal_identity:
        _fail("principal_mismatch")
    _current(request, now_ms)
    return _authenticated_telemetry_request(request, credential.key_identity)


def sign_telemetry_response(
    response: WorkerTelemetryResponse,
    request: WorkerTelemetryRequest,
    credential: TelemetryObservationCredential,
) -> bytes:
    _credential(credential)
    if request.worker_identity != credential.principal_identity:
        _fail("principal_mismatch")
    return _seal(
        encode_telemetry_response(response, request),
        credential,
        AUTHENTICATED_TELEMETRY_RESPONSE,
        MAX_TELEMETRY_RESPONSE_BYTES,
    )


def authenticate_telemetry_response(
    raw: bytes,
    request: WorkerTelemetryRequest,
    credential: TelemetryObservationCredential,
    *,
    now_ms: int,
) -> WorkerTelemetryResponse:
    _credential(credential)
    if request.worker_identity != credential.principal_identity:
        _fail("principal_mismatch")
    _current(request, now_ms)
    body = _open(
        raw, credential, AUTHENTICATED_TELEMETRY_RESPONSE, MAX_TELEMETRY_RESPONSE_BYTES
    )
    response = decode_telemetry_response(body, request)
    if response.observed_at_ms > now_ms:
        _fail("observation_from_future")
    return response


def read_telemetry_envelope(stream: BinaryIO, *, response: bool) -> bytes:
    """Read finite frames only. The transport must separately enforce a deadline.

    No cancellation, deadline or signal is ever passed to a selected job. A
    stalled reader must be bounded by its separate observation transport owner.
    """
    if type(response) is not bool:
        _fail("operation_invalid")
    maximum = MAX_TELEMETRY_RESPONSE_BYTES if response else MAX_TELEMETRY_SAMPLE_BYTES
    parts = []
    size = 0
    records = 0
    # One auth header, one response header and up to 64 samples (request: 2).
    record_limit = 66 if response else 2
    while True:
        record_budget = (
            MAX_TELEMETRY_AUTH_HEADER_BYTES
            if records == 0
            else MAX_TELEMETRY_SAMPLE_BYTES
        )
        allowance = 0 if records == record_limit else min(record_budget, maximum - size)
        raw = stream.readline(allowance + 1)
        if type(raw) is not bytes:
            _fail("stream_invalid")
        if not raw:
            break
        if records == record_limit:
            _fail("framing_limit")
        if len(raw) > allowance:
            _fail("size_limit")
        if not raw.endswith(b"\n"):
            _fail("framing_invalid")
        records += 1
        if records > record_limit or (
            records == 1 and len(raw) > MAX_TELEMETRY_AUTH_HEADER_BYTES
        ):
            _fail("framing_limit")
        size += len(raw)
        parts.append(raw)
    if records < 2:
        _fail("framing_invalid")
    return b"".join(parts)
