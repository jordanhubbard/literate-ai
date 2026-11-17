"""Real MAC proofs plus injected private policy/clock ports; no native owner claim."""

import pickle
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

from literate_ai.adapters.worker_telemetry_authentication import (
    TelemetryObservationCredential,
    authenticate_telemetry_request,
    sign_telemetry_request,
)
from literate_ai.application.worker_telemetry_authentication import (
    AuthenticatedTelemetryRequest,
)
from literate_ai.application.worker_telemetry_authorization import (
    TelemetryAuthorizationError,
    TelemetryObservationPolicy,
    TelemetryReplayWindow,
    TelemetryScopeAuthority,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.worker_telemetry import TelemetryScope
from tests.support.fixtures_worker_telemetry import telemetry_request


class WorkerTelemetryAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.now = [2000]
        self.base = telemetry_request()
        self.key = TelemetryObservationCredential(
            self.base.controller_identity, b"private-test-only-observation-key-material"
        )
        self.policy = TelemetryObservationPolicy(
            self.base.controller_identity,
            self.base.catalog_identity,
            self.base.registration_identity,
            self.base.worker_identity,
            self.key.key_identity,
            0,
            40000,
            self.base.action_identities,
        )
        self.current = [self.policy]
        self.authority = TelemetryScopeAuthority(
            lambda: self.current[0], lambda: self.now[0]
        )
        self.request = replace(
            self.base, observation_scope_identity=self.authority.identity
        )

    def proof(self, request=None, *, key=None):
        request = self.request if request is None else request
        key = self.key if key is None else key
        return authenticate_telemetry_request(
            sign_telemetry_request(request, key), key, now_ms=self.now[0]
        )

    def test_current_permission_and_nonce_produce_only_a_revalidated_scope_permit(self):
        permit = self.authority.authorize(self.proof())
        self.assertEqual(permit.request, self.request)
        self.authority.require_permit(permit)
        with self.assertRaisesRegex(TelemetryAuthorizationError, "replayed"):
            self.authority.authorize(self.proof())
        self.authority.close()
        with self.assertRaisesRegex(TelemetryAuthorizationError, "owner_closed"):
            permit.require_current()

    def test_decoded_records_and_fabricated_or_pickled_proofs_cannot_authorize(self):
        for value in (
            self.request,
            self.request.to_dict(),
            object.__new__(AuthenticatedTelemetryRequest),
        ):
            with self.subTest(type=type(value).__name__), self.assertRaises(ValueError):
                self.authority.authorize(value)
        with self.assertRaises(ValueError):
            AuthenticatedTelemetryRequest(
                self.request, self.key.key_identity, _issuer=object()
            )
        proof = self.proof()
        with self.assertRaises(TypeError):
            pickle.dumps(proof)
        with self.assertRaises(AttributeError):
            proof._request = self.base
        permit = self.authority.authorize(proof)
        with self.assertRaises(TypeError):
            pickle.dumps(permit)
        with self.assertRaises(AttributeError):
            permit._authority = self.authority

    def test_new_authority_cannot_restore_old_permissions_from_identical_policy_data(
        self,
    ):
        new = TelemetryScopeAuthority(lambda: self.policy, lambda: self.now[0])
        self.assertNotEqual(new.identity, self.authority.identity)
        self.assertNotEqual(new.epoch, self.authority.epoch)
        with self.assertRaisesRegex(TelemetryAuthorizationError, "scope_mismatch"):
            new.authorize(self.proof())
        permit = self.authority.authorize(self.proof())
        with self.assertRaisesRegex(TelemetryAuthorizationError, "foreign_permit"):
            new.require_permit(permit)

    def test_all_registration_catalog_worker_controller_and_scope_substitutions_refuse(
        self,
    ):
        for field in (
            "catalog_identity",
            "registration_identity",
            "worker_identity",
            "observation_scope_identity",
        ):
            request = replace(self.request, **{field: canonical_identity("foreign")})
            with (
                self.subTest(field=field),
                self.assertRaisesRegex(TelemetryAuthorizationError, "scope_mismatch"),
            ):
                self.authority.authorize(self.proof(request))
        foreign = TelemetryObservationCredential(
            canonical_identity("foreign-controller"), b"x" * 32
        )
        request = replace(self.request, controller_identity=foreign.principal_identity)
        with self.assertRaises(TelemetryAuthorizationError):
            self.authority.authorize(self.proof(request, key=foreign))
        # Refused metadata must not consume the legitimate scope's challenge.
        self.authority.authorize(self.proof())

    def test_unconfigured_signing_key_and_foreign_action_refuse_even_with_valid_macs(
        self,
    ):
        other = TelemetryObservationCredential(self.base.controller_identity, b"y" * 32)
        with self.assertRaisesRegex(TelemetryAuthorizationError, "scope_mismatch"):
            self.authority.authorize(self.proof(key=other))
        request = replace(
            self.request, action_identities=(canonical_identity("foreign-action"),)
        )
        with self.assertRaisesRegex(TelemetryAuthorizationError, "action_denied"):
            self.authority.authorize(self.proof(request))
        self.authority.authorize(self.proof())

    def test_aggregate_requires_separate_explicit_permission(self):
        request = replace(
            self.request, scope=TelemetryScope.WORKER_AGGREGATE, action_identities=()
        )
        with self.assertRaisesRegex(TelemetryAuthorizationError, "aggregate_denied"):
            self.authority.authorize(self.proof(request))
        policy = replace(self.policy, allow_worker_aggregate=True)
        authority = TelemetryScopeAuthority(lambda: policy, lambda: self.now[0])
        request = replace(request, observation_scope_identity=authority.identity)
        permit = authority.authorize(self.proof(request))
        authority.require_permit(permit)
        self.assertIs(permit.request.scope, TelemetryScope.WORKER_AGGREGATE)

    def test_current_policy_change_revokes_permits_and_cannot_silently_restore_them(
        self,
    ):
        permit = self.authority.authorize(self.proof())
        self.current[0] = replace(
            self.policy, registration_identity=canonical_identity("changed")
        )
        with self.assertRaisesRegex(TelemetryAuthorizationError, "policy_changed"):
            permit.require_current()
        self.current[0] = self.policy
        with self.assertRaisesRegex(TelemetryAuthorizationError, "owner_closed"):
            permit.require_current()
        with self.assertRaises(TelemetryAuthorizationError):
            self.authority.authorize(self.proof(replace(self.request, nonce="b" * 64)))

    def test_policy_change_during_authorization_cannot_publish_a_permit(self):
        calls = []

        def load():
            calls.append(1)
            return (
                self.policy
                if len(calls) < 3
                else replace(self.policy, action_identities=())
            )

        authority = TelemetryScopeAuthority(load, lambda: self.now[0])
        request = replace(self.request, observation_scope_identity=authority.identity)
        with self.assertRaisesRegex(TelemetryAuthorizationError, "policy_changed"):
            authority.authorize(self.proof(request))
        self.assertEqual(len(calls), 3)

    def test_expired_or_regressed_clock_cannot_revive_a_prior_permit(self):
        permit = self.authority.authorize(self.proof())
        self.now[0] = 31000
        with self.assertRaisesRegex(TelemetryAuthorizationError, "expired"):
            permit.require_current()
        self.now[0] = 2000
        with self.assertRaisesRegex(TelemetryAuthorizationError, "clock_regressed"):
            permit.require_current()

    def test_nonce_capacity_refuses_without_evicting_live_claims_and_reaps_expired_only(
        self,
    ):
        authority = TelemetryScopeAuthority(
            lambda: self.policy,
            lambda: self.now[0],
            replay_window=TelemetryReplayWindow(maximum_entries=1),
        )
        request = replace(self.request, observation_scope_identity=authority.identity)
        authority.authorize(self.proof(request))
        with self.assertRaisesRegex(TelemetryAuthorizationError, "replay_capacity"):
            authority.authorize(self.proof(replace(request, nonce="b" * 64)))
        with self.assertRaisesRegex(TelemetryAuthorizationError, "replayed"):
            authority.authorize(self.proof(request))
        self.now[0] = 31000
        fresh = replace(
            request, issued_at_ms=31000, expires_at_ms=40000, nonce="b" * 64
        )
        authority.authorize(self.proof(fresh))

    def test_concurrent_duplicate_challenges_never_publish_multiple_permits(self):
        barrier = threading.Barrier(8)

        def attempt(_):
            proof = self.proof()
            barrier.wait(timeout=3)
            try:
                self.authority.authorize(proof)
            except TelemetryAuthorizationError:
                return False
            return True

        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(attempt, range(8)))
        self.assertLessEqual(sum(outcomes), 1)
        with self.assertRaisesRegex(TelemetryAuthorizationError, "replayed"):
            self.authority.authorize(self.proof())

    def test_policy_port_failure_is_safe_and_never_converts_into_authorization(self):
        def load():
            raise RuntimeError("private-path-and-credential-marker")

        with self.assertRaises(TelemetryAuthorizationError) as caught:
            TelemetryScopeAuthority(load, lambda: self.now[0])
        self.assertNotIn("private-path", str(caught.exception))
        with self.assertRaises(ValueError):
            TelemetryReplayWindow(maximum_entries=True)
        with self.assertRaises(ValueError):
            TelemetryReplayWindow(maximum_entries=4097)
        with self.assertRaises(ValueError):
            replace(self.policy, allow_worker_aggregate=1)

    def test_clock_port_failure_never_exposes_private_exception_text(self):
        def clock():
            raise RuntimeError("private-clock-credential-marker")

        authority = TelemetryScopeAuthority(lambda: self.policy, clock)
        request = replace(self.request, observation_scope_identity=authority.identity)
        with self.assertRaises(TelemetryAuthorizationError) as caught:
            authority.authorize(self.proof(request))
        self.assertNotIn("private-clock", str(caught.exception))

    def test_missing_policy_closes_owner_even_if_identical_policy_is_restored(self):
        permit = self.authority.authorize(self.proof())
        self.current[0] = None
        with self.assertRaises(TelemetryAuthorizationError):
            permit.require_current()
        self.current[0] = self.policy
        with self.assertRaisesRegex(TelemetryAuthorizationError, "owner_closed"):
            permit.require_current()
