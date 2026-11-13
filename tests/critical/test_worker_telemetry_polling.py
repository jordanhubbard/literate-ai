"""Actual MAC/scope proofs and bounded polling bookkeeping; no native receiver."""

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
from literate_ai.application.worker_telemetry_authorization import (
    TelemetryAuthorizationError,
    TelemetryObservationPolicy,
    TelemetryScopeAuthority,
)
from literate_ai.application.worker_telemetry_polling import (
    TelemetryPollingError,
    TelemetryPollTicket,
    TelemetryPollWindow,
)
from tests.support.fixtures_worker_telemetry import telemetry_request


class WorkerTelemetryPollingTests(unittest.TestCase):
    def setUp(self):
        self.wall = [2000]
        self.monotonic = [10_000_000_000]
        self.base = telemetry_request(2)
        self.credential = TelemetryObservationCredential(
            self.base.controller_identity, b"test-only-observation-polling-key-material"
        )
        policy = TelemetryObservationPolicy(
            self.base.controller_identity,
            self.base.catalog_identity,
            self.base.registration_identity,
            self.base.worker_identity,
            self.credential.key_identity,
            0,
            2_000_000,
            self.base.action_identities,
        )
        self.current = [policy]
        self.authority = TelemetryScopeAuthority(
            lambda: self.current[0], lambda: self.wall[0]
        )
        self.window = TelemetryPollWindow(
            self.authority, monotonic_ns=lambda: self.monotonic[0]
        )
        self.nonce = 0

    def reset_window(self, **options):
        # New original authority; prior wire proofs cannot transfer to this scope.
        self.authority = TelemetryScopeAuthority(
            lambda: self.current[0], lambda: self.wall[0]
        )
        self.window = TelemetryPollWindow(
            self.authority, monotonic_ns=lambda: self.monotonic[0], **options
        )
        return self.window

    def proof(self, **changes):
        self.nonce += 1
        request = replace(
            self.base,
            observation_scope_identity=self.authority.identity,
            nonce=f"{self.nonce:064x}",
            **(
                {
                    "issued_at_ms": self.wall[0] - 1000,
                    "expires_at_ms": self.wall[0] + 29000,
                }
                | changes
            ),
        )
        return authenticate_telemetry_request(
            sign_telemetry_request(request, self.credential),
            self.credential,
            now_ms=self.wall[0],
        )

    def advance(self, milliseconds):
        self.wall[0] += milliseconds
        self.monotonic[0] += milliseconds * 1_000_000

    def test_authenticated_queries_coalesce_without_another_collection_or_deadline(
        self,
    ):
        first = self.window.begin(self.proof())
        self.advance(10)
        second = self.window.begin(self.proof())
        self.assertTrue(first.is_leader)
        self.assertFalse(second.is_leader)
        self.assertEqual(first.deadline_ns, second.deadline_ns)
        self.assertEqual(self.window.retained_counts, (1, 2))
        first.require_current()
        second.require_current()
        with self.assertRaisesRegex(TelemetryPollingError, "collector_owner_required"):
            second.finish()
        first.finish()
        self.assertEqual(self.window.retained_counts, (0, 0))
        self.assertTrue(second.cancellation_requested)

    def test_begin_requires_authentication_and_consumes_every_nonce_even_on_refusal(
        self,
    ):
        with self.assertRaises(ValueError):
            self.window.begin(self.base)
        proof = self.proof()
        ticket = self.window.begin(proof)
        with self.assertRaisesRegex(ValueError, "replayed"):
            self.window.begin(proof)
        ticket.finish()
        refused = self.proof()
        with self.assertRaisesRegex(TelemetryPollingError, "rate_excess"):
            self.window.begin(refused)
        with self.assertRaisesRegex(ValueError, "replayed"):
            self.window.begin(refused)
        self.assertEqual(self.window.retained_counts, (0, 0))

    def test_one_second_minimum_survives_finish_and_has_an_exact_boundary(self):
        self.window.begin(self.proof()).finish()
        self.advance(999)
        with self.assertRaisesRegex(TelemetryPollingError, "rate_excess"):
            self.window.begin(self.proof())
        self.advance(1)
        self.window.begin(self.proof()).finish()

    def test_waiters_are_bounded_and_detaching_one_does_not_cancel_the_others(self):
        tickets = [self.window.begin(self.proof()) for _ in range(64)]
        with self.assertRaisesRegex(TelemetryPollingError, "waiter_capacity"):
            self.window.begin(self.proof())
        self.assertEqual(self.window.retained_counts, (1, 64))
        tickets[-1].release()
        tickets[-1].release()
        self.assertTrue(tickets[-1].cancellation_requested)
        self.assertFalse(tickets[0].cancellation_requested)
        self.assertFalse(self.window.begin(self.proof()).is_leader)
        self.assertEqual(self.window.retained_counts, (1, 64))
        tickets[0].finish()

    def test_cancelled_collectors_hold_capacity_until_their_original_finally_hook(self):
        window = self.reset_window(maximum_collectors=2)
        first = window.begin(
            self.proof(action_identities=self.base.action_identities[:1])
        )
        self.advance(1000)
        second = window.begin(
            self.proof(action_identities=self.base.action_identities[1:])
        )
        first.release()
        self.assertTrue(first.cancellation_requested)
        self.advance(1000)
        with self.assertRaisesRegex(TelemetryPollingError, "collector_capacity"):
            window.begin(self.proof())
        self.assertEqual(window.retained_counts, (2, 1))
        first.finish()
        third = window.begin(self.proof())
        first.finish()  # Retired tickets cannot release a successor's slot.
        self.assertEqual(window.retained_counts, (2, 2))
        second.finish()
        third.finish()

    def test_request_expiry_and_monotonic_deadline_do_not_evict_running_collectors(
        self,
    ):
        ticket = self.window.begin(self.proof())
        self.assertLessEqual(ticket.deadline_ns - self.monotonic[0], 30_000_000_000)
        self.advance(29000)
        self.assertTrue(ticket.cancellation_requested)
        with self.assertRaisesRegex(TelemetryPollingError, "collector_retiring"):
            self.window.begin(self.proof())
        self.assertEqual(self.window.retained_counts, (1, 1))
        ticket.finish()
        self.window.begin(self.proof()).finish()

    def test_shorter_coalesced_request_keeps_its_own_expiry_without_stopping_leader(
        self,
    ):
        first = self.window.begin(self.proof())
        second = self.window.begin(self.proof(expires_at_ms=self.wall[0] + 100))
        self.assertLess(second.deadline_ns, first.deadline_ns)
        self.advance(100)
        self.assertTrue(second.cancellation_requested)
        self.assertFalse(first.cancellation_requested)
        second.release()
        first.finish()

    def test_policy_loss_revokes_polling_and_cleanup_remains_available(self):
        ticket = self.window.begin(self.proof())
        self.current[0] = None
        self.assertTrue(ticket.cancellation_requested)
        with self.assertRaises(ValueError):
            self.window.begin(self.proof())
        ticket.release()
        ticket.finish()
        self.assertEqual(self.window.retained_counts, (0, 0))

    def test_scope_owner_close_cancels_observation_tickets_without_releasing_live_slots(
        self,
    ):
        first = self.window.begin(self.proof())
        second = self.window.begin(self.proof())
        self.window.close()
        self.assertTrue(first.cancellation_requested)
        self.assertTrue(second.cancellation_requested)
        with self.assertRaisesRegex(TelemetryPollingError, "closed"):
            self.window.begin(self.proof())
        self.assertEqual(self.window.retained_counts, (1, 2))
        first.finish()

    def test_monotonic_regression_permanently_closes_this_polling_owner(self):
        ticket = self.window.begin(self.proof())
        self.monotonic[0] -= 1
        with self.assertRaisesRegex(TelemetryPollingError, "clock_regressed"):
            ticket.require_current()
        self.monotonic[0] += 2
        with self.assertRaisesRegex(TelemetryPollingError, "closed"):
            self.window.begin(self.proof())
        self.assertTrue(ticket.cancellation_requested)
        ticket.finish()

    def test_busy_and_private_clock_errors_are_safe_bounded_refusals(self):
        self.window._lock.acquire()
        try:
            with self.assertRaisesRegex(TelemetryPollingError, "busy"):
                self.window.begin(self.proof())
        finally:
            self.window._lock.release()

        def unavailable():
            raise RuntimeError("secret-shaped-private-clock-detail")

        authority = TelemetryScopeAuthority(
            lambda: self.current[0], lambda: self.wall[0]
        )
        window = TelemetryPollWindow(authority, monotonic_ns=unavailable)
        request = replace(self.base, observation_scope_identity=authority.identity)
        proof = authenticate_telemetry_request(
            sign_telemetry_request(request, self.credential),
            self.credential,
            now_ms=self.wall[0],
        )
        with self.assertRaisesRegex(
            TelemetryPollingError, "clock_unavailable"
        ) as error:
            window.begin(proof)
        self.assertNotIn("secret-shaped", str(error.exception))
        self.assertEqual(window.retained_counts, (0, 0))

    def test_tickets_cannot_be_fabricated_pickled_mutated_or_used_by_a_foreign_window(
        self,
    ):
        ticket = self.window.begin(self.proof())
        other = TelemetryPollWindow(
            TelemetryScopeAuthority(lambda: self.current[0], lambda: self.wall[0])
        )
        for value in (ticket, object.__new__(TelemetryPollTicket), self.base):
            with self.assertRaisesRegex(TelemetryPollingError, "foreign_ticket"):
                other.finish(value)
        with self.assertRaises(TypeError):
            pickle.dumps(ticket)
        with self.assertRaises(AttributeError):
            ticket._window = other
        ticket.finish()

    def test_simultaneous_valid_queries_create_only_one_collector(self):
        proofs = [self.proof() for _ in range(8)]
        barrier = threading.Barrier(8)

        def begin(proof):
            barrier.wait(timeout=10)
            try:
                return self.window.begin(proof)
            except (TelemetryPollingError, TelemetryAuthorizationError) as error:
                self.assertRegex(
                    str(error), r"worker\.telemetry_(polling|authorization)_busy$"
                )
                return None  # Only atomic nonblocking busy refusals are allowed.

        with ThreadPoolExecutor(max_workers=8) as pool:
            tickets = [t for t in pool.map(begin, proofs) if t is not None]
        self.assertTrue(tickets)
        self.assertEqual(sum(t.is_leader for t in tickets), 1)
        self.assertEqual(self.window.retained_counts, (1, len(tickets)))
        next(t for t in tickets if t.is_leader).finish()

    def test_completed_queries_leave_no_sample_history_or_growing_slot_inventory(self):
        for _ in range(100):
            self.window.begin(self.proof()).finish()
            self.assertEqual(self.window.retained_counts, (0, 0))
            self.advance(1000)

    def test_configuration_cannot_remove_the_finite_collector_or_waiter_ceiling(self):
        for config in (
            {"maximum_collectors": 0},
            {"maximum_collectors": 17},
            {"maximum_waiters": 0},
            {"maximum_waiters": 65},
            {"maximum_collectors": True},
            {"maximum_waiters": True},
        ):
            with self.subTest(config=config), self.assertRaises(ValueError):
                TelemetryPollWindow(self.authority, **config)

    def test_reconstructing_a_window_cannot_reset_this_scope_rate_or_capacity(self):
        ticket = self.window.begin(self.proof())
        for retire in (False, True):
            if retire:
                self.window.close()
                ticket.finish()
            with self.assertRaisesRegex(ValueError, "poll_owner_claimed"):
                TelemetryPollWindow(self.authority)

    def test_slow_authority_checks_cannot_backdate_the_collection_rate_boundary(self):
        calls = 0

        def current():
            nonlocal calls
            calls += 1
            if calls == 4:
                self.advance(2000)
            return self.current[0]

        self.authority._loader = current
        ticket = self.window.begin(self.proof())
        ticket.finish()
        with self.assertRaisesRegex(TelemetryPollingError, "rate_excess"):
            self.window.begin(self.proof())

    def test_slow_admission_cannot_publish_an_already_expired_monotonic_ticket(self):
        calls = 0

        def current():
            nonlocal calls
            calls += 1
            if calls == 4:
                # Independent monotonic expiry even if wall time has not advanced.
                self.monotonic[0] += 30_000_000_000
            return self.current[0]

        self.authority._loader = current
        with self.assertRaisesRegex(TelemetryPollingError, "expired"):
            self.window.begin(self.proof())
        self.assertEqual(self.window.retained_counts, (0, 0))

    def _install_slow_policy_port(self):
        def current():
            self.advance(10)
            return self.current[0]

        self.authority = TelemetryScopeAuthority(current, lambda: self.wall[0])
        self.window = TelemetryPollWindow(
            self.authority, monotonic_ns=lambda: self.monotonic[0]
        )

    def test_currentness_refuses_a_deadline_crossed_during_policy_validation(self):
        self._install_slow_policy_port()
        proof = self.proof()
        ticket = self.window.begin(proof)
        self.advance((ticket.deadline_ns - self.monotonic[0]) // 1_000_000 - 5)
        self.assertLess(self.monotonic[0], ticket.deadline_ns)
        try:
            with self.assertRaisesRegex(TelemetryPollingError, "inactive"):
                ticket.require_current()
            self.assertGreaterEqual(self.monotonic[0], ticket.deadline_ns)
            self.assertLess(self.wall[0], proof.request.expires_at_ms)
            self.assertTrue(ticket.cancellation_requested)
            self.assertEqual(self.window.retained_counts, (1, 1))
        finally:
            ticket.finish()
        self.assertEqual(self.window.retained_counts, (0, 0))

    def test_slow_currentness_preserves_a_fresh_ticket(self):
        self._install_slow_policy_port()
        ticket = self.window.begin(self.proof())
        try:
            ticket.require_current()
            self.assertFalse(ticket.cancellation_requested)
            self.assertEqual(self.window.retained_counts, (1, 1))
        finally:
            ticket.finish()

    def test_slow_coalesced_validation_cannot_extend_its_participant_deadline(self):
        self._install_slow_policy_port()
        first = self.window.begin(self.proof())
        proof = self.proof(expires_at_ms=self.wall[0] + 100)
        second = self.window.begin(proof)
        self.assertLess(second.deadline_ns, first.deadline_ns)
        self.advance((second.deadline_ns - self.monotonic[0]) // 1_000_000 - 5)
        try:
            with self.assertRaisesRegex(TelemetryPollingError, "inactive"):
                second.require_current()
            self.assertLess(self.wall[0], proof.request.expires_at_ms)
            first.require_current()
            self.assertFalse(first.cancellation_requested)
            self.assertEqual(self.window.retained_counts, (1, 2))
            second.release()
            self.assertEqual(self.window.retained_counts, (1, 1))
        finally:
            first.finish()
        self.assertEqual(self.window.retained_counts, (0, 0))

    def test_clock_regression_during_currentness_closes_the_polling_owner(self):
        regress = False

        def current():
            if regress:
                self.monotonic[0] -= 1
            return self.current[0]

        self.authority = TelemetryScopeAuthority(current, lambda: self.wall[0])
        self.window = TelemetryPollWindow(
            self.authority, monotonic_ns=lambda: self.monotonic[0]
        )
        ticket = self.window.begin(self.proof())
        regress = True
        try:
            with self.assertRaisesRegex(TelemetryPollingError, "clock_regressed"):
                ticket.require_current()
            regress = False
            self.monotonic[0] += 2
            with self.assertRaisesRegex(TelemetryPollingError, "closed"):
                self.window.begin(self.proof())
            self.assertTrue(ticket.cancellation_requested)
            self.assertEqual(self.window.retained_counts, (1, 1))
        finally:
            ticket.finish()
        self.assertEqual(self.window.retained_counts, (0, 0))
