"""Process-local proof issued by a trusted message-authentication adapter.

This proves message origin only. It grants no observation scope, action ownership
or execution capability and has no serialized reconstruction path.
"""

from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.worker_telemetry import WorkerTelemetryRequest

_ISSUER = object()


class AuthenticatedTelemetryRequest:
    __slots__ = ("_request", "_key_identity", "_issuer")

    def __init__(self, request, key_identity, *, _issuer):
        if (
            _issuer is not _ISSUER
            or not isinstance(request, WorkerTelemetryRequest)
            or not isinstance(key_identity, ContentIdentity)
        ):
            raise ValueError("worker.telemetry_authentication_proof_invalid")
        object.__setattr__(self, "_request", request)
        object.__setattr__(self, "_key_identity", key_identity)
        object.__setattr__(self, "_issuer", _issuer)

    def __setattr__(self, name, value):
        raise AttributeError("worker.telemetry_authentication_proof_immutable")

    def __reduce_ex__(self, protocol):
        raise TypeError("worker.telemetry_authentication_proof_not_serializable")

    @property
    def request(self):
        return self._request

    @property
    def key_identity(self):
        return self._key_identity


def _authenticated_telemetry_request(request, key_identity):
    """Adapter port: invoke only after verifying the configured private credential."""
    return AuthenticatedTelemetryRequest(request, key_identity, _issuer=_ISSUER)


def require_telemetry_authentication(proof):
    if (
        type(proof) is not AuthenticatedTelemetryRequest
        or getattr(proof, "_issuer", None) is not _ISSUER
    ):
        raise ValueError("worker.telemetry_authentication_proof_required")
    return proof.request, proof.key_identity
