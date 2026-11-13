"""Bounded process-local observation permission and atomic replay refusal.

Private policy loading is a current-authority port, not a wire-record decoder.
A permit still requires separately reopened live action/process/reservation
owners before any observation. Nothing here can dispatch, signal or mutate jobs.
"""

from __future__ import annotations

import secrets
import threading
from dataclasses import dataclass

from literate_ai.application.worker_telemetry_authentication import (
    require_telemetry_authentication,
)
from literate_ai.contracts._validation import int_value
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.contracts.worker_telemetry import MAX_TELEMETRY_ACTIONS, TelemetryScope


class TelemetryAuthorizationError(ValueError):
    pass


def _fail(reason):
    raise TelemetryAuthorizationError("worker.telemetry_authorization_" + reason)


@dataclass(frozen=True, slots=True)
class TelemetryObservationPolicy:
    controller_identity: ContentIdentity
    catalog_identity: ContentIdentity
    registration_identity: ContentIdentity
    worker_identity: ContentIdentity
    request_key_identity: ContentIdentity
    valid_from_ms: int
    valid_until_ms: int
    action_identities: tuple[ContentIdentity, ...]
    allow_worker_aggregate: bool = False

    def __post_init__(self):
        for value in (
            self.controller_identity,
            self.catalog_identity,
            self.registration_identity,
            self.worker_identity,
            self.request_key_identity,
        ):
            if not isinstance(value, ContentIdentity):
                _fail("policy_invalid")
        int_value(self.valid_from_ms, "telemetry.policy_from")
        int_value(self.valid_until_ms, "telemetry.policy_until")
        if (
            self.valid_until_ms <= self.valid_from_ms
            or type(self.allow_worker_aggregate) is not bool
        ):
            _fail("policy_invalid")
        actions = self.action_identities
        if (
            not isinstance(actions, tuple)
            or len(actions) > MAX_TELEMETRY_ACTIONS
            or any(not isinstance(a, ContentIdentity) for a in actions)
        ):
            _fail("policy_actions_invalid")
        if tuple(a.uri for a in actions) != tuple(sorted({a.uri for a in actions})):
            _fail("policy_actions_invalid")

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/private-observation-policy@1",
                "controller": self.controller_identity.uri,
                "catalog": self.catalog_identity.uri,
                "registration": self.registration_identity.uri,
                "worker": self.worker_identity.uri,
                "request_key": self.request_key_identity.uri,
                "from_ms": self.valid_from_ms,
                "until_ms": self.valid_until_ms,
                "actions": [a.uri for a in self.action_identities],
                "allow_worker_aggregate": self.allow_worker_aggregate,
            }
        )


class TelemetryReplayWindow:
    """Finite nonce ownership. Full windows refuse rather than evict live claims."""

    def __init__(self, *, maximum_entries=256):
        int_value(maximum_entries, "telemetry.replay_entries", minimum=1, maximum=4096)
        self._maximum = maximum_entries
        self._entries = {}
        self._lock = threading.Lock()
        self._last_now = 0

    def claim(self, request, now_ms):
        int_value(now_ms, "telemetry.replay_now")
        if not request.issued_at_ms <= now_ms < request.expires_at_ms:
            _fail("expired")
        if not self._lock.acquire(blocking=False):
            _fail("busy")
        try:
            if now_ms < self._last_now:
                _fail("clock_regressed")
            self._last_now = now_ms
            self._entries = {k: v for k, v in self._entries.items() if v > now_ms}
            key = (request.controller_identity, request.worker_identity, request.nonce)
            if key in self._entries:
                _fail("replayed")
            if len(self._entries) >= self._maximum:
                _fail("replay_capacity")
            self._entries[key] = request.expires_at_ms
        finally:
            self._lock.release()


_PERMIT_ISSUER = object()


class TelemetryObservationPermit:
    __slots__ = ("_authority", "_proof", "_issuer")

    def __init__(self, authority, proof, *, _issuer):
        if _issuer is not _PERMIT_ISSUER:
            _fail("permit_invalid")
        object.__setattr__(self, "_authority", authority)
        object.__setattr__(self, "_proof", proof)
        object.__setattr__(self, "_issuer", _issuer)

    def __setattr__(self, name, value):
        raise AttributeError("worker.telemetry_permit_immutable")

    def __reduce_ex__(self, protocol):
        raise TypeError("worker.telemetry_permit_not_serializable")

    @property
    def request(self):
        return self._proof.request

    def require_current(self):
        return self._authority._validate(self._proof)


class TelemetryScopeAuthority:
    """Original current policy owner; reconstructing policy data creates a new scope.

    The configured loader must reopen actual current private policy/registration
    custody on every call. Tests may inject it, but that is not native admission.
    The authority owns observation bookkeeping only, never a job mutation lock.
    """

    def __init__(self, load_current_policy, clock_ms, *, replay_window=None):
        if not callable(load_current_policy) or not callable(clock_ms):
            _fail("ports_required")
        self._loader = load_current_policy
        self._clock = clock_ms
        self._closed = False
        self._clock_lock = threading.Lock()
        self._last_now = 0
        self._poll_owner_claimed = False
        self._policy = self._load()
        self._replay = (
            TelemetryReplayWindow() if replay_window is None else replay_window
        )
        if type(self._replay) is not TelemetryReplayWindow:
            _fail("replay_owner_required")
        self._epoch = canonical_identity(
            {"original_observation_owner": secrets.token_hex(32)}
        )
        self._identity = canonical_identity(
            {"policy": self._policy.identity.uri, "owner_epoch": self._epoch.uri}
        )

    def _load(self):
        try:
            policy = self._loader()
        except Exception:
            raise TelemetryAuthorizationError(
                "worker.telemetry_authorization_policy_unavailable"
            ) from None
        if type(policy) is not TelemetryObservationPolicy:
            _fail("policy_required")
        return policy

    @property
    def identity(self):
        return self._identity

    @property
    def epoch(self):
        return self._epoch

    def close(self):
        # Revokes only this observation namespace; it has no selected-job handle.
        self._closed = True

    def claim_polling_owner(self):
        """One process-local polling owner for this scope's entire lifetime."""
        if not self._clock_lock.acquire(blocking=False):
            _fail("busy")
        try:
            if self._closed:
                _fail("owner_closed")
            if self._poll_owner_claimed:
                _fail("poll_owner_claimed")
            self._poll_owner_claimed = True
        finally:
            self._clock_lock.release()

    def _validate(self, proof):
        request, key = require_telemetry_authentication(proof)
        if self._closed:
            _fail("owner_closed")
        try:
            policy = self._load()
        except TelemetryAuthorizationError:
            self._closed = True
            raise
        if policy != self._policy:
            self._closed = True
            _fail("policy_changed")
        try:
            now = self._clock()
            int_value(now, "telemetry.authorization_now")
        except Exception:
            raise TelemetryAuthorizationError(
                "worker.telemetry_authorization_clock_unavailable"
            ) from None
        if not self._clock_lock.acquire(blocking=False):
            _fail("busy")
        try:
            if now < self._last_now:
                _fail("clock_regressed")
            self._last_now = now
        finally:
            self._clock_lock.release()
        if (
            not policy.valid_from_ms
            <= request.issued_at_ms
            <= now
            < request.expires_at_ms
            <= policy.valid_until_ms
        ):
            _fail("expired")
        if (
            request.controller_identity != policy.controller_identity
            or request.catalog_identity != policy.catalog_identity
            or request.registration_identity != policy.registration_identity
            or request.worker_identity != policy.worker_identity
            or request.observation_scope_identity != self._identity
            or key != policy.request_key_identity
        ):
            _fail("scope_mismatch")
        if request.scope is TelemetryScope.WORKER_AGGREGATE:
            if not policy.allow_worker_aggregate:
                _fail("aggregate_denied")
        elif not set(request.action_identities) <= set(policy.action_identities):
            _fail("action_denied")
        if self._closed:
            _fail("owner_closed")
        return request, now

    def authorize(self, proof):
        request, now = self._validate(proof)
        self._replay.claim(request, now)
        # Reopen custody after claiming. Failure consumes the challenge but can
        # never return a permit under changed authority; use a fresh request.
        self._validate(proof)
        return TelemetryObservationPermit(self, proof, _issuer=_PERMIT_ISSUER)

    def require_permit(self, permit):
        if (
            type(permit) is not TelemetryObservationPermit
            or getattr(permit, "_issuer", None) is not _PERMIT_ISSUER
            or getattr(permit, "_authority", None) is not self
        ):
            _fail("foreign_permit")
        return permit.require_current()
