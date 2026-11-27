"""Original provider issuance with injected runtime joins; no host/native acceptance."""

import copy
import os
import shutil
import sys
import threading
import time
import unittest
import weakref
from datetime import UTC, datetime, timedelta
from unittest import mock

from literate_ai.adapters import node_sdk_verifier_authority as membership
from literate_ai.adapters import node_sdk_verifier_authorization as owner
from literate_ai.adapters import node_sdk_verifier_runtime as runtime
from literate_ai.contracts import canonical_identity
from literate_ai.security.policy import AuthorizationError, SecurityProfile
from tests.smoke import test_node_sdk_verifier_authorization as fixture
from tests.smoke import test_node_sdk_verifier_runtime as state_fixture


class GrantJournalMetadataTests(unittest.TestCase):
    """Metadata capacity/weak cleanup only; no issued authority or native inputs."""

    def test_operation_journal_capacity_is_bounded_and_retirement_recovers_it(self):
        states = []
        acknowledgement = fixture.WeakNamespace()
        try:
            for _ in range(owner._MAX_GRANT_OPERATIONS):
                _bound, _binding, state, _operation, identity = (
                    state_fixture.controller(ports=fixture.WeakNamespace())
                )
                states.append(state)
                owner._grant_registration(
                    state, acknowledgement, identity.uri, create=True
                )
            _bound, _binding, extra, _operation, identity = state_fixture.controller(
                ports=fixture.WeakNamespace()
            )
            states.append(extra)
            with self.assertRaisesRegex(ValueError, "capacity exhausted"):
                owner._grant_registration(
                    extra, acknowledgement, identity.uri, create=True
                )
            self.assertNotIn(extra.handle, runtime._GRANT_OPERATIONS)
            self.assertEqual(len(owner._OPERATION_GRANTS), owner._MAX_GRANT_OPERATIONS)
        finally:
            for state in states:
                state.retire()
        self.assertFalse(owner._OPERATION_GRANTS)

    def test_collected_original_operation_releases_journal_outside_its_mutex(self):
        import gc

        bound, binding, state, operation, identity = state_fixture.controller(
            ports=fixture.WeakNamespace()
        )
        acknowledgement = fixture.WeakNamespace()
        registration = owner._grant_registration(
            state, acknowledgement, identity.uri, create=True
        )
        availability = []

        def release():
            def probe():
                acquired = owner._GRANT_LOCK.acquire(timeout=1)
                availability.append(acquired)
                if acquired:
                    owner._GRANT_LOCK.release()

            thread = threading.Thread(target=probe)
            thread.start()
            thread.join(timeout=2)

        registration[3]["metadata cleanup fixture"] = (
            "PREPARED",
            (None, None, None, release),
            identity.uri,
            identity.uri,
        )
        reference, key = weakref.ref(operation), id(operation)
        del bound, binding, state, operation
        gc.collect()
        self.assertIsNone(reference())
        self.assertNotIn(key, owner._OPERATION_GRANTS)
        self.assertEqual(availability, [True])


@unittest.skipUnless(
    os.name == "posix"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "requires actual selected provider capture fixture",
)
class EnrolledVerifierIssuanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.EnrolledVerifierClassificationTests.setUpClass()

    def bind(self, *, lifetime=None):
        control = fixture.EnrolledVerifierClassificationTests()
        control.setUp()
        self.addCleanup(control.doCleanups)
        self.c, self.ack = control.c, control.ack
        if lifetime is not None:
            membership._retire_acknowledgement(self.ack)
            f = self.c.fixture
            self.ack = owner.acknowledge_node_sdk_verifier_execution(
                snapshot=f.snapshot,
                execution=f.execution,
                actor="isolated issuance fixture",
                reason="original provider grant qualification",
                authorization_lifetime=lifetime,
                authorization_deadline=datetime.now(UTC) + timedelta(minutes=10),
                acknowledge_identity_only_inputs=True,
            )
            self.addCleanup(membership._retire_acknowledgement, self.ack)
            facts = owner._original_owner(self.ack)[4]
            membership._bind_acknowledgement(
                self.ack,
                self.c.bound.configuration,
                self.c.bound,
                facts=facts,
                originals=(f.snapshot, f.execution),
            )
        # The operation and these exact metadata functions remain deliberately
        # injected. Source/capture and the fixed issuer itself are original.
        self.c.state._original_witness = self.c.state._witness
        self.c.state._original_invocation_witness = self.c.state._invocation_witness
        return self.c

    def issue(self, handle, ticket):
        return owner._issue_enrolled_node_verifier_authorization(
            self.ack, self.c.operation, handle, ticket
        )

    def assert_retired(self):
        self.c.state.retire()
        self.assertIsNone(self.c.state._grant_intent)
        self.assertEqual(self.c.state._grant_payloads, {})
        self.assertNotIn(id(self.c.operation), owner._OPERATION_GRANTS)
        self.assertNotIn(self.c.operation, runtime._GRANT_OPERATIONS)
        self.assertIsNone(self.c.state._retirement_attempt)

    def test_original_grant_registers_before_return_and_closes_with_capture(self):
        c = self.bind()
        with c.capture() as (handle, ticket):
            grant = self.issue(handle, ticket)
            record = c.state._grants[ticket]
            original = owner._grant_registration(c.state)[3][ticket]
            self.assertEqual(record[0], "ISSUED")
            self.assertIs(original[1], c.state._grant_payloads[ticket])
            self.assertIs(original[1][1], grant)
            self.assertIs(grant.profile, SecurityProfile.CONSTRAINED)
            self.assertEqual(grant.privileges, ("execute-library-verifier",))
            self.assertEqual(grant.request_digest, record[2])
            self.assertEqual(canonical_identity(grant.to_dict()).uri, record[3])
            c.operation.require_current()
        c.state._sealed = True
        c.state.close()
        self.assert_retired()

    def test_changed_live_revocation_provider_refuses_without_invocation(self):
        c = self.bind()
        verifier = owner._original_owner(self.ack)[11]
        original = verifier.provider
        trap = mock.Mock(
            side_effect=AssertionError("unsupported revocation provider ran")
        )
        with self.assertRaises(ValueError), c.capture() as (handle, ticket):
            self.issue(handle, ticket)
            object.__setattr__(verifier, "provider", trap)
            try:
                with self.assertRaisesRegex(ValueError, "owner changed"):
                    c.operation.require_current()
            finally:
                object.__setattr__(verifier, "provider", original)
            self.assertEqual(trap.mock_calls, [])
        self.assert_retired()

    def test_nonempty_revocation_state_refuses_without_reading_foreign_entries(self):
        c = self.bind()
        revocations = owner._original_owner(self.ack)[9]

        class Trap:
            def __eq__(self, _other):
                raise AssertionError("foreign revocation DATA ran")

        with self.assertRaises(ValueError), c.capture() as (handle, ticket):
            self.issue(handle, ticket)
            object.__setattr__(revocations, "entries", Trap())
            try:
                with self.assertRaisesRegex(ValueError, "owner changed"):
                    c.operation.require_current()
            finally:
                object.__setattr__(revocations, "entries", ())
        self.assert_retired()

    def test_replaced_payload_and_witness_cannot_rebase_original_grant(self):
        c = self.bind()
        with self.assertRaises(ValueError), c.capture() as (handle, ticket):
            grant = self.issue(handle, ticket)
            payload = c.state._grant_payloads[ticket]
            copied = copy.copy(grant)
            c.state._grant_payloads[ticket] = (
                payload[0],
                copied,
                lambda: None,
                lambda: None,
            )
            with self.assertRaisesRegex(ValueError, "publication is incomplete"):
                c.operation.require_current()
        self.assert_retired()

    def test_coordinated_runtime_map_replacement_cannot_rebase_fixed_issuer(self):
        c = self.bind()
        with self.assertRaises(ValueError), c.capture() as (handle, ticket):
            grant = self.issue(handle, ticket)
            payload = c.state._grant_payloads[ticket]
            copied = copy.copy(grant)
            object.__setattr__(copied, "reason", "substituted grant")
            c.state._grant_payloads[ticket] = (
                payload[0],
                copied,
                lambda: None,
                lambda: None,
            )
            before = c.state._grants[ticket]
            c.state._grants[ticket] = (
                *before[:3],
                canonical_identity(copied.to_dict()).uri,
            )
            with self.assertRaisesRegex(ValueError, "publication is incomplete"):
                c.operation.require_current()
        self.assert_retired()

    def test_runtime_witness_fields_cannot_replace_fixed_original_metadata(self):
        c = self.bind()
        trap = mock.Mock(side_effect=AssertionError("substituted finite witness ran"))
        with self.assertRaises(ValueError), c.capture() as (handle, ticket):
            self.issue(handle, ticket)
            c.state._witness = c.state._original_witness = trap
            with self.assertRaisesRegex(
                ValueError, "original operation metadata changed"
            ):
                c.operation.require_current()
            self.assertEqual(trap.mock_calls, [])
        self.assert_retired()

    def test_cleared_runtime_intent_cannot_disable_original_grant_checks(self):
        c = self.bind()
        with self.assertRaises(ValueError), c.capture() as (handle, ticket):
            self.issue(handle, ticket)
            c.state._grant_intent = None
            with self.assertRaisesRegex(ValueError, "lost its intent"):
                c.operation.require_current()
        self.assert_retired()

    def test_journal_before_intent_publication_is_drained_by_runtime_retirement(self):
        c = self.bind()
        primary = KeyboardInterrupt("cancelled before intent publication")
        with self.assertRaises(ValueError), c.capture() as (handle, ticket):
            with mock.patch.object(c.state, "begin_issuance", side_effect=primary):
                with self.assertRaises(KeyboardInterrupt) as failure:
                    self.issue(handle, ticket)
            self.assertIs(failure.exception, primary)
            self.assertIsNone(c.state._grant_intent)
            self.assertIn(id(c.operation), owner._OPERATION_GRANTS)
            self.assertIn(c.operation, runtime._GRANT_OPERATIONS)
        self.assert_retired()

    def _foreign_metadata(self, *, closing, intent):
        c = self.bind()
        calls = []

        class Trap:
            def __hash__(self):
                calls.append("hash")
                return 129

            def __eq__(self, _other):
                calls.append("equal")
                return False

            def __ne__(self, _other):
                calls.append("unequal")
                return True

        value = Trap()

        def mutate(ticket):
            if intent:
                c.state._grant_intent = (self.ack, value)
            else:
                c.state._grants[value] = c.state._grants[ticket]
            calls.clear()  # The fixture insertion may hash; framework checks must not.

        if closing:
            with c.capture() as (handle, ticket):
                self.issue(handle, ticket)
            c.state._sealed = True
            pool = c.state._resource_pool
            original = pool.settle_closing_cleanup

            def settled(*args, **kwargs):
                result = original(*args, **kwargs)
                mutate(ticket)
                return result

            with mock.patch.object(pool, "settle_closing_cleanup", side_effect=settled):
                with self.assertRaises(ValueError):
                    c.state.close()
        else:
            with self.assertRaises(ValueError), c.capture() as (handle, ticket):
                self.issue(handle, ticket)
                mutate(ticket)
                with self.assertRaises(ValueError):
                    c.operation.require_current()
        self.assertEqual(calls, [])
        self.assert_retired()
        self.assertEqual(calls, [])

    def test_foreign_key_is_rejected_before_live_hashing(self):
        self._foreign_metadata(closing=False, intent=False)

    def test_foreign_key_is_rejected_at_final_settlement_before_hashing(self):
        self._foreign_metadata(closing=True, intent=False)

    def test_foreign_intent_is_rejected_before_live_equality(self):
        self._foreign_metadata(closing=False, intent=True)

    def test_foreign_intent_is_rejected_at_final_settlement_before_equality(self):
        self._foreign_metadata(closing=True, intent=True)

    def test_original_grant_retirement_releases_outside_operation_mutex(self):
        c = self.bind()
        with c.capture() as (handle, ticket):
            self.issue(handle, ticket)
        c.state._sealed = True
        c.state.close()
        journal = owner._grant_registration(c.state)[3]
        record = journal[ticket]
        original_release = record[1][3]
        available = []

        expected_records = dict(
            zip(
                original_release.__code__.co_freevars,
                (cell.cell_contents for cell in original_release.__closure__),
                strict=True,
            )
        )["records"]

        def profile(frame, event, _arg):
            if (
                event == "call"
                and frame.f_code is original_release.__code__
                and frame.f_locals.get("records") is expected_records
            ):

                def probe():
                    acquired = c.binding.lock.acquire(timeout=1)
                    available.append(acquired)
                    if acquired:
                        c.binding.lock.release()

                thread = threading.Thread(target=probe)
                thread.start()
                thread.join(timeout=2)
                self.assertFalse(thread.is_alive())

        previous = sys.getprofile()
        try:
            sys.setprofile(profile)
            self.assert_retired()
        finally:
            sys.setprofile(previous)
        self.assertEqual(available, [True])

    def _cleanup_failure(self, exception_class):
        c = self.bind()
        original = c.fixture.ports.require_library_provider_custody
        installed = []

        def injected_code():
            first, second = [], False
            if exception_class is KeyboardInterrupt:

                def fail():
                    nonlocal first, second
                    first.clear()
                    second = True
                    raise KeyboardInterrupt(
                        "injected classification cleanup cancellation"
                    )
            else:

                def fail():
                    nonlocal first, second
                    first.clear()
                    second = True
                    raise RuntimeError("injected classification cleanup failure")

            return fail.__code__

        code = injected_code()

        def custody(*args, **kwargs):
            result = original(*args, **kwargs)
            frame = sys._getframe(1)
            try:
                while frame is not None:
                    if (
                        frame.f_code.co_name
                        == "_issue_enrolled_node_verifier_authorization"
                    ):
                        release = frame.f_locals.get("release_classification")
                        if release is not None and not installed:
                            self.assertEqual(
                                len(release.__code__.co_freevars), len(code.co_freevars)
                            )
                            release.__code__ = code
                            installed.append(True)
                        break
                    frame = frame.f_back
            finally:
                frame = None
            return result

        with self.assertRaises(ValueError), c.capture() as (handle, ticket):
            with mock.patch.object(
                c.fixture.ports, "require_library_provider_custody", side_effect=custody
            ):
                with self.assertRaises(exception_class):
                    self.issue(handle, ticket)
            self.assertEqual(installed, [True])
            self.assertIn(ticket, c.state._grant_payloads)
            self.assertTrue(c.state._poisoned)
            self.assertEqual(c.state._grants[ticket][0], "FAILED")
            with self.assertRaises(ValueError):
                c.operation.require_current()
        c.state._sealed = True
        with self.assertRaises(ValueError):
            c.state.close()
        self.assert_retired()

    def test_cleanup_failure_after_registration_withholds_success_and_close(self):
        self._cleanup_failure(RuntimeError)

    def test_cleanup_cancellation_after_registration_withholds_success_and_close(self):
        self._cleanup_failure(KeyboardInterrupt)

    def test_expiry_before_return_withholds_original_grant(self):
        c = self.bind(lifetime=timedelta(microseconds=1))
        with self.assertRaises(ValueError), c.capture() as (handle, ticket):
            with self.assertRaisesRegex(AuthorizationError, "authorization_expired"):
                self.issue(handle, ticket)
            self.assertEqual(c.state._grants[ticket][0], "FAILED")
        self.assert_retired()

    def test_earlier_grant_expiry_blocks_later_reservation_without_renewal(self):
        c = self.bind(lifetime=timedelta(seconds=2))
        with c.capture() as (handle, ticket):
            grant = self.issue(handle, ticket)
        times = grant.issued_at, grant.expires_at
        while datetime.now(UTC) < grant.expires_at:
            time.sleep(0.01)
        # Only this second ticket is injected metadata; no second provider
        # capture or native invocation qualification is inferred.
        later = object.__new__(runtime._InspectionTicket)
        facts = (
            "provider",
            canonical_identity("later provider").uri,
            canonical_identity("later request").uri,
        )
        c.state._tickets[facts[:2]] = [later, facts, "CAPTURING"]
        runtime._TICKETS[later] = weakref.ref(c.state), facts
        with self.assertRaisesRegex(AuthorizationError, "authorization_expired"):
            c.state.begin_issuance(later, self.ack, c.state._grant_intent[1])
        self.assertNotIn(later, c.state._grants)
        self.assertEqual((grant.issued_at, grant.expires_at), times)
        c.state._sealed = True
        with self.assertRaises(ValueError):
            c.state.close()
        self.assert_retired()

    def test_expiry_during_closing_settlement_withholds_aggregate_success(self):
        c = self.bind(lifetime=timedelta(seconds=2))
        with c.capture() as (handle, ticket):
            grant = self.issue(handle, ticket)
        c.state._sealed = True
        pool = c.state._resource_pool
        settle = pool.settle_closing_cleanup
        seen = []

        def settled(*args, **kwargs):
            result = settle(*args, **kwargs)
            seen.append(True)
            while datetime.now(UTC) < grant.expires_at:
                time.sleep(0.01)
            return result

        with mock.patch.object(pool, "settle_closing_cleanup", side_effect=settled):
            with self.assertRaisesRegex(AuthorizationError, "authorization_expired"):
                c.state.close()
        self.assertEqual(seen, [True])
        self.assertTrue(c.state._poisoned)
        self.assert_retired()

    def _foreign_flags_after_settlement(self, field):
        c = self.bind()
        with c.capture() as (handle, ticket):
            self.issue(handle, ticket)
        c.state._sealed = True
        pool = c.state._resource_pool
        original = pool.settle_closing_cleanup
        calls = []

        class Trap:
            def __bool__(self):
                calls.append("bool")
                return False

            def __eq__(self, _other):
                calls.append("equal")
                return False

            def __ne__(self, _other):
                calls.append("unequal")
                return True

        def settled(*args, **kwargs):
            result = original(*args, **kwargs)
            setattr(c.state, field, Trap())
            return result

        with mock.patch.object(pool, "settle_closing_cleanup", side_effect=settled):
            with self.assertRaisesRegex(ValueError, "closed primitive metadata"):
                c.state.close()
        self.assertEqual(calls, [])
        self.assert_retired()
        self.assertEqual(calls, [])

    def test_foreign_poison_flag_refuses_after_settlement_without_truthiness(self):
        self._foreign_flags_after_settlement("_poisoned")

    def test_foreign_sealed_flag_refuses_after_settlement_without_truthiness(self):
        self._foreign_flags_after_settlement("_sealed")

    def test_foreign_phase_refuses_after_settlement_without_equality(self):
        self._foreign_flags_after_settlement("_state")

    def test_expiry_during_resource_retirement_withholds_terminal_success(self):
        c = self.bind(lifetime=timedelta(seconds=2))
        with c.capture() as (handle, ticket):
            grant = self.issue(handle, ticket)
        c.state._sealed = True
        c.state.close()
        pool = c.state._resource_pool
        retire = pool.retire
        seen = []

        def retired(*args, **kwargs):
            result = retire(*args, **kwargs)
            seen.append(True)
            while datetime.now(UTC) < grant.expires_at:
                time.sleep(0.01)
            return result

        with mock.patch.object(pool, "retire", side_effect=retired):
            with self.assertRaisesRegex(AuthorizationError, "authorization_expired"):
                c.state.retire()
        self.assertEqual(seen, [True])
        self.assertTrue(c.state._retirement_complete)
        self.assertTrue(c.state._poisoned)
        self.assert_retired()

    def _resource_retirement_mutation(self, field):
        c = self.bind()
        with c.capture() as (handle, ticket):
            self.issue(handle, ticket)
        c.state._sealed = True
        c.state.close()
        pool, configuration = c.state._resource_pool, c.bound.configuration
        retire = pool.retire
        original = None if field is None else getattr(configuration, field)
        seen = []

        def retired(*args, **kwargs):
            result = retire(*args, **kwargs)
            if field is None:
                with self.assertRaisesRegex(ValueError, "retirement reentered"):
                    c.state.retire()
            else:
                setattr(configuration, field, object())
            seen.append(True)
            return result

        try:
            with mock.patch.object(pool, "retire", side_effect=retired):
                with self.assertRaisesRegex(
                    ValueError, "poisoned during retirement|configuration changed"
                ):
                    c.state.retire()
        finally:
            if field is not None:
                setattr(configuration, field, original)
        self.assertEqual(seen, [True])
        self.assertTrue(c.state._poisoned)
        self.assertTrue(c.state._retirement_complete)
        self.assert_retired()
        c.binding._resume_retiring()
        self.assertIsNone(c.binding.active)

    def test_swallowed_retirement_reentry_withholds_success_after_original_close(self):
        self._resource_retirement_mutation(None)

    def test_snapshot_replacement_during_retirement_withholds_success(self):
        self._resource_retirement_mutation("snapshot")

    def test_execution_replacement_during_retirement_withholds_success(self):
        self._resource_retirement_mutation("expected_execution")
