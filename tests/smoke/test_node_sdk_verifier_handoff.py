"""Private transaction controls; no capture provenance or native qualification."""

import copy
import gc
import inspect
import types
import unittest
import weakref
from unittest import mock

from literate_ai.adapters import node_sdk_verifier_resources as resources
from literate_ai.adapters import node_sdk_verifier_runtime as runtime
from literate_ai.adapters.node_sdk_verifier_closing_payload import (
    _VerifierClosingPayload,
)
from literate_ai.adapters.node_sdk_verifier_resources import _VerifierResourcePool
from tests.smoke import test_node_sdk_verifier_runtime as fixtures


class CaptureHandoffTests(unittest.TestCase):
    def setUp(self):
        self.bound, self.binding, self.state, self.operation, self.model = (
            fixtures.controller()
        )
        self.addCleanup(self.state.retire)
        self.pool = _VerifierResourcePool()
        self.ticket, self.lease = self.enroll("first")
        self.compiler, self.leaf = object(), object()
        self.released = []

    def enroll(self, name):
        # Explicit fixture-only enrollment: real resource-owner validation belongs
        # to the original capture engine and is deliberately not claimed here.
        ticket = object.__new__(runtime._InspectionTicket)
        facts = ("provider", self.model.uri + name, self.model.uri)
        self.state._tickets[facts[:2]] = [ticket, facts, "CAPTURING"]
        runtime._TICKETS[ticket] = weakref.ref(self.state), facts
        lease = self.pool.reserve_capture(4)
        self.state._capture_leases[ticket] = self.pool, lease
        self.addCleanup(self.pool.settle_capture_cleanup, lease, successful=False)
        return ticket, lease

    def payload(self):
        return _VerifierClosingPayload(
            (lambda: None,) * 4,
            tuple(lambda i=i: self.released.append(i) for i in range(3)),
        )

    def prepare(self, *, ticket=None, lease=None, pool=None):
        payload = self.payload()
        self.state.prepare_capture_handoff(
            self.ticket if ticket is None else ticket,
            self.pool if pool is None else pool,
            self.lease if lease is None else lease,
            payload,
            closing_bytes=2,
            compiler=self.compiler,
            compiler_facts=(self.leaf,),
            compiler_bytes=3,
        )
        return payload

    def test_prepare_commit_and_exact_set_borrow_preserve_original_membership(self):
        payload = self.prepare()
        self.assertEqual(self.state._handoffs[self.ticket][3], "PREPARED")
        self.state.commit_capture_handoff(self.ticket)
        self.assertEqual(self.state._handoffs[self.ticket][3], "COMMITTED")
        self.pool.settle_capture_cleanup(self.lease, successful=True)
        self.state.report_capture(self.ticket, failed=False)
        self.state.close()
        self.assertIsNone(self.state._closing_publication)
        self.assertFalse(payload._retired)
        self.state.retire()
        self.assertEqual(self.released, [0, 1, 2])
        self.assertEqual(self.pool.statistics()["bytes"], 0)

    def ready(self, guard=None):
        if guard is None:
            payload = self.prepare()
        else:

            def make_payload():
                return _VerifierClosingPayload(
                    (guard,) * 4,
                    tuple(lambda i=i: self.released.append(i) for i in range(3)),
                )

            with mock.patch.object(self, "payload", new=make_payload):
                payload = self.prepare()
        self.state.commit_capture_handoff(self.ticket)
        self.pool.settle_capture_cleanup(self.lease, successful=True)
        self.state.report_capture(self.ticket, failed=False)
        return payload

    def assert_close_views_cleared(self, traceback):
        found = False
        while traceback is not None:
            if traceback.tb_frame.f_code is runtime._OperationState.close.__code__:
                found = True
                for name in ("view", "payload", "compiler", "facts"):
                    self.assertIsNone(traceback.tb_frame.f_locals[name])
            traceback = traceback.tb_next
        self.assertTrue(found)

    def test_closing_borrow_guards_and_completion_are_outside_binding(self):
        observed = []

        def probe():
            return fixtures.RuntimeResourceOwnerTests.lock_available_to_other_thread(
                self
            )

        def guard():
            observed.append(("guard", probe()))

        self.ready(guard)
        borrow, settle = self.pool.prepare_closing, self.pool.settle_closing_cleanup

        def borrowing(*args, **kwargs):
            observed.append(("borrow", probe()))
            return borrow(*args, **kwargs)

        def completing(*args):
            observed.append(("complete", probe()))
            frame = inspect.currentframe()
            try:
                while frame is not None:
                    if frame.f_code is runtime._OperationState.close.__code__:
                        for name in ("view", "payload", "compiler", "facts"):
                            self.assertIsNone(frame.f_locals[name])
                        break
                    frame = frame.f_back
                self.assertIsNotNone(frame)
            finally:
                frame = None
            return settle(*args)

        with (
            mock.patch.object(self.pool, "prepare_closing", new=borrowing),
            mock.patch.object(self.pool, "settle_closing_cleanup", new=completing),
        ):
            self.state.close()
        self.assertEqual(
            observed, [("borrow", True)] + [("guard", True)] * 4 + [("complete", True)]
        )

    def test_retained_closing_guard_failure_releases_compiler_after_retirement(self):
        class Source:
            pass

        source = Source()
        reference = weakref.ref(source)
        self.compiler = self.leaf = source
        failure = KeyboardInterrupt("original closing guard failure")

        def guard():
            raise failure

        self.ready(guard)
        retained = None
        try:
            self.state.close()
        except KeyboardInterrupt as error:
            retained = error
        self.assertIs(retained, failure)
        self.assert_close_views_cleared(retained.__traceback__)
        self.state.retire()
        self.compiler = self.leaf = source = None
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(self.pool.statistics()["bytes"], 0)

    def test_closing_completion_failure_keeps_publication_until_metadata_recovery(self):
        calls = []
        self.ready(lambda: calls.append(True))
        failure = MemoryError("before original borrow completion")

        def incomplete(*_args):
            raise failure

        with mock.patch.object(self.pool, "settle_closing_cleanup", new=incomplete):
            with self.assertRaises(MemoryError) as raised:
                self.state.close()
        self.assertIs(raised.exception, failure)
        self.assertIsNotNone(self.state._closing_publication)
        self.assertGreater(self.pool.statistics()["bytes"], 0)
        self.state.retire()
        self.assertEqual(calls, [True] * 4)
        self.assertIsNone(self.state._closing_publication)
        self.assertEqual(self.pool.statistics()["bytes"], 0)

    def test_original_guard_failure_survives_failed_completion_and_recovery(self):
        failure = ValueError("original closing error")

        def guard():
            raise failure

        def incomplete(*_args):
            raise MemoryError("secondary completion failure")

        self.ready(guard)
        with mock.patch.object(self.pool, "settle_closing_cleanup", new=incomplete):
            with self.assertRaises(ValueError) as raised:
                self.state.close()
        self.assertIs(raised.exception, failure)
        self.assertIsNotNone(self.state._closing_publication)
        self.state.retire()
        self.assertEqual(self.pool.statistics()["bytes"], 0)

    def test_interrupted_unreturned_view_settles_original_token_without_guard_replay(
        self,
    ):
        calls = []
        self.ready(lambda: calls.append(True))
        borrow = self.pool.prepare_closing
        failure = KeyboardInterrupt("after borrow before caller received view")

        def interrupted(*args, **kwargs):
            borrow(*args, **kwargs)
            raise failure

        with mock.patch.object(self.pool, "prepare_closing", new=interrupted):
            with self.assertRaises(KeyboardInterrupt) as raised:
                self.state.close()
        self.assertIs(raised.exception, failure)
        self.assertFalse(calls)
        self.assertIsNone(self.state._closing_publication)
        self.state.retire()
        self.assertEqual(self.pool.statistics()["bytes"], 0)

    def test_retirement_cannot_complete_a_reader_still_executing_guards(self):
        observed = []

        def guard():
            if not observed:
                with self.assertRaisesRegex(
                    ValueError, "reader settlement remains pending"
                ):
                    self.state.retire()
                observed.append(self.pool.statistics()["bytes"])

        self.ready(guard)
        with self.assertRaisesRegex(ValueError, "during final witnesses"):
            self.state.close()
        self.assertGreater(observed[0], 0)
        self.state.retire()
        self.assertEqual(self.pool.statistics()["bytes"], 0)

    def test_wrong_publication_cannot_complete_another_original_reader(self):
        self.ready()
        owner = self.state._resource_owner_handle
        publication = resources._new_closing_publication(self.pool, owner)
        view = self.pool.prepare_closing(owner, _publication=publication)
        foreign = resources._new_closing_publication(self.pool, owner)
        resources._mark_closing_views_dropped(foreign)
        with self.assertRaisesRegex(ValueError, "another reader"):
            self.pool.settle_closing_cleanup(owner, foreign)
        self.assertIsNotNone(self.pool._owners[owner].closing_borrowed)
        del view
        resources._mark_closing_views_dropped(publication)
        self.pool.settle_closing_cleanup(owner, publication)
        self.pool.settle_closing_cleanup(owner, publication)

    def test_malformed_publication_owner_never_runs_foreign_hash_or_equality(self):
        self.ready()
        owner = self.state._resource_owner_handle
        publication = resources._new_closing_publication(self.pool, owner)
        resources._mark_closing_views_dropped(publication)
        calls = []

        class Foreign:
            def __hash__(self):
                calls.append("hash")
                raise AssertionError("foreign hash")

            def __eq__(self, _other):
                calls.append("equality")
                raise AssertionError("foreign equality")

        foreign = Foreign()
        types.MemberDescriptorType.__set__(
            resources._CLOSING_SLOTS["owner"], publication, foreign
        )
        for candidate in (owner, foreign):
            with self.assertRaises(TypeError):
                self.pool.settle_closing_cleanup(candidate, publication)
        self.assertFalse(calls)

    def test_publication_token_and_flags_refuse_foreign_boolean_code(self):
        self.ready()
        owner = self.state._resource_owner_handle
        calls = []

        class Foreign:
            def __bool__(self):
                calls.append(True)
                raise AssertionError("foreign boolean conversion")

        for name in ("token", "claimed", "dropped"):
            with self.subTest(field=name):
                publication = resources._new_closing_publication(self.pool, owner)
                resources._mark_closing_views_dropped(publication)
                types.MemberDescriptorType.__set__(
                    resources._CLOSING_SLOTS[name], publication, Foreign()
                )
                with self.assertRaises(TypeError):
                    self.pool.settle_closing_cleanup(owner, publication)
        self.assertFalse(calls)

    def test_reused_publication_cannot_drop_existing_borrow_when_claim_flag_is_false(
        self,
    ):
        self.ready()
        owner = self.state._resource_owner_handle
        publication = resources._new_closing_publication(self.pool, owner)
        view = self.pool.prepare_closing(owner, _publication=publication)
        token = self.pool._owners[owner].closing_borrowed
        # A mutable metadata flag is not evidence that an existing borrow ended.
        types.MemberDescriptorType.__set__(
            resources._CLOSING_SLOTS["claimed"], publication, False
        )
        with self.assertRaises(ValueError):
            self.pool.prepare_closing(owner, _publication=publication)
        self.assertIs(self.pool._owners[owner].closing_borrowed, token)
        self.assertFalse(self.released)
        self.assertGreater(self.pool.statistics()["bytes"], 0)
        del view
        resources._mark_closing_views_dropped(publication)
        self.pool.settle_closing_cleanup(owner, publication)
        self.assertEqual(self.released, [0, 1, 2])
        self.assertEqual(self.pool.statistics()["bytes"], 0)

    def test_settlement_reentry_cannot_publish_success_after_last_guard(self):
        self.ready()
        settle = self.pool.settle_closing_cleanup
        attempts = []

        def reentered(*args):
            settle(*args)
            try:
                self.state.close()
            except ValueError:
                attempts.append(True)

        with mock.patch.object(self.pool, "settle_closing_cleanup", new=reentered):
            with self.assertRaisesRegex(ValueError, "during final witnesses"):
                self.state.close()
        self.assertEqual(attempts, [True])
        self.assertIsNone(self.state._closing_publication)
        self.assertIsNone(
            self.pool._owners[self.state._resource_owner_handle].closing_borrowed
        )
        self.state.retire()
        self.assertEqual(self.pool.statistics()["bytes"], 0)

    def test_failure_after_completion_transition_resumes_without_guard_replay(self):
        calls = []
        self.ready(lambda: calls.append(True))
        settle = self.pool.settle_closing_cleanup
        failure = MemoryError("after original completion")

        def interrupted(*args):
            settle(*args)
            raise failure

        with mock.patch.object(self.pool, "settle_closing_cleanup", new=interrupted):
            with self.assertRaises(MemoryError) as raised:
                self.state.close()
        self.assertIs(raised.exception, failure)
        self.assertIsNotNone(self.state._closing_publication)
        self.state.retire()
        self.assertEqual(calls, [True] * 4)
        self.assertEqual(self.pool.statistics()["bytes"], 0)

    def test_publication_lock_exit_cancellation_never_borrows_or_runs_guards(self):
        calls = []
        self.ready(lambda: calls.append(True))
        lock = self.binding.lock
        failure = KeyboardInterrupt("after original publication")
        observed = []

        class InterruptedLock:
            def __enter__(_self):
                lock.acquire()

            def __exit__(_self, *_args):
                lock.release()
                if self.state._closing_publication is not None and not observed:
                    observed.append(True)
                    raise failure

        with (
            mock.patch.object(self.binding, "lock", InterruptedLock()),
            mock.patch.object(self.pool, "prepare_closing") as borrow,
        ):
            with self.assertRaises(KeyboardInterrupt) as raised:
                self.state.close()
            borrow.assert_not_called()
        self.assertIs(raised.exception, failure)
        self.assertFalse(calls)
        self.assertIsNone(self.state._closing_publication)
        self.state.retire()
        self.assertEqual(self.pool.statistics()["bytes"], 0)

    def test_interrupted_drop_proof_keeps_borrow_charged_and_retirement_pending(self):
        self.ready()
        mark = resources._mark_closing_views_dropped
        failure = MemoryError("before original dropped-view proof")

        def interrupted(_publication):
            raise failure

        retained = None
        with mock.patch.object(
            resources, "_mark_closing_views_dropped", new=interrupted
        ):
            try:
                self.state.close()
            except MemoryError as error:
                retained = error
        self.assertIs(retained, failure)
        self.assert_close_views_cleared(retained.__traceback__)
        publication = self.state._closing_publication
        self.assertIs(resources._closing_publication_values(publication)[4], False)
        with self.assertRaisesRegex(ValueError, "reader settlement remains pending"):
            self.state.retire()
        self.assertGreater(self.pool.statistics()["bytes"], 0)
        # Fixture-only teardown after directly proving that this controlled
        # frame dropped its references; production retirement never guesses.
        mark(publication)
        self.state.retire()
        self.assertEqual(self.pool.statistics()["bytes"], 0)

    def test_registered_closed_capture_requires_committed_handoff(self):
        self.pool.settle_capture_cleanup(self.lease, successful=True)
        self.state.report_capture(self.ticket, failed=False)
        with self.assertRaisesRegex(ValueError, "committed handoffs"):
            self.state.close()

    def test_final_metadata_drift_during_guards_withholds_success(self):
        original = self.model.digest

        def guard():
            object.__setattr__(self.model, "digest", "0" * 64)

        self.ready(guard)
        try:
            with self.assertRaisesRegex(ValueError, "finite metadata changed"):
                self.state.close()
        finally:
            object.__setattr__(self.model, "digest", original)
        self.state.retire()
        self.assertEqual(self.pool.statistics()["bytes"], 0)

    def test_pool_side_effects_run_outside_binding_lock(self):
        observed = []
        patches = []
        for name in ("prepare_handoff", "attach_payload", "commit_handoff"):
            original = getattr(self.pool, name)

            def call(*args, _original=original, _name=name, **kwargs):
                observed.append(
                    (
                        _name,
                        fixtures.RuntimeResourceOwnerTests.lock_available_to_other_thread(
                            self
                        ),
                    )
                )
                return _original(*args, **kwargs)

            patch = mock.patch.object(self.pool, name, side_effect=call)
            patch.start()
            patches.append(patch)
        try:
            self.prepare()
            self.state.commit_capture_handoff(self.ticket)
        finally:
            for patch in reversed(patches):
                patch.stop()
        self.assertEqual(
            observed,
            [
                ("prepare_handoff", True),
                ("attach_payload", True),
                ("commit_handoff", True),
            ],
        )

    def test_uncommitted_capture_cannot_report_closed(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError, "lifecycle changed"):
            self.state.report_capture(self.ticket, failed=False)
        self.assertTrue(self.state._poisoned)

    def test_foreign_pool_refuses_before_pool_allocation(self):
        foreign = _VerifierResourcePool()
        with self.assertRaisesRegex(ValueError, "original capturing lease"):
            self.prepare(pool=foreign)
        self.assertEqual(foreign.statistics()["owners"], 0)
        self.assertEqual(self.pool.statistics()["owners"], 0)

    def test_foreign_lease_refuses_before_pool_allocation(self):
        _ticket, lease = self.enroll("second")
        with self.assertRaisesRegex(ValueError, "original capturing lease"):
            self.prepare(lease=lease)
        self.assertEqual(self.pool.statistics()["owners"], 0)

    def test_copied_ticket_refuses_before_pool_allocation(self):
        with self.assertRaises(ValueError):
            self.prepare(ticket=copy.copy(self.ticket))
        self.assertEqual(self.pool.statistics()["owners"], 0)

    def test_foreign_ticket_never_runs_hash_or_equality(self):
        calls = []

        class Foreign:
            def __hash__(self):
                calls.append("hash")
                raise AssertionError("foreign hash")

            def __eq__(self, _other):
                calls.append("equality")
                raise AssertionError("foreign equality")

        ticket = Foreign()
        for action in (
            lambda: self.prepare(ticket=ticket),
            lambda: self.state.commit_capture_handoff(ticket),
            lambda: self.state.require_ticket(ticket),
            lambda: self.state.report_capture(ticket, failed=False),
        ):
            with self.assertRaises(TypeError):
                action()
        self.assertFalse(calls)

    def test_retained_capacity_failure_releases_pool_factory_compiler_references(self):
        class Source:
            pass

        compiler = Source()
        reference = weakref.ref(compiler)
        self.compiler = self.leaf = compiler
        self.pool._maximum_bytes = 2 * 1024 * 1024 + 8
        retained = None
        try:
            self.prepare()
        except ValueError as error:
            retained = error
        self.assertIsNotNone(retained)
        self.assertIsNotNone(retained.__traceback__)
        self.pool.settle_capture_cleanup(self.lease, successful=False)
        self.compiler = self.leaf = compiler = None
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(self.pool.statistics()["bytes"], 0)

    def test_enrollment_only_pool_final_reference_drops_outside_binding(self):
        pool = _VerifierResourcePool()
        observed = []
        reference = weakref.ref(
            pool,
            lambda _ref: observed.append(
                fixtures.RuntimeResourceOwnerTests.lock_available_to_other_thread(self)
            ),
        )
        # Controlled direct metadata injection to exercise final-reference order;
        # fixed production enrollment uses the long-lived shared capture pool.
        self.state._capture_leases[object()] = (pool, None)
        del pool
        self.state.retire()
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(observed, [True])

    def test_attach_interruption_keeps_preparing_failed_and_charge_until_settlement(
        self,
    ):
        attach = self.pool.attach_payload
        failure = MemoryError("after original attachment")

        def interrupted(*args):
            attach(*args)
            raise failure

        with mock.patch.object(self.pool, "attach_payload", side_effect=interrupted):
            with self.assertRaises(MemoryError) as raised:
                self.prepare()
        self.assertIs(raised.exception, failure)
        self.assertEqual(self.state._handoffs[self.ticket][3], "PREPARING")
        self.assertGreater(self.pool.statistics()["bytes"], 0)
        self.assertFalse(self.released)
        self.pool.settle_capture_cleanup(self.lease, successful=False)
        self.assertEqual(self.released, [0, 1, 2])
        self.assertEqual(self.pool.statistics()["bytes"], 0)

    def test_rejected_attachment_does_not_retain_unattached_payload_in_traceback(self):
        attach = self.pool.attach_payload

        def refuse(handle, payload):
            try:
                # A controlled already-attached flag forces the original method's
                # refusal before it retains this payload, without user callbacks.
                self.pool._captures[handle].attached = True
                attach(handle, payload)
            finally:
                payload = None

        payload = self.payload()
        reference = weakref.ref(payload)
        retained = None
        # A direct function replacement avoids Mock's own retained argument frames.
        with mock.patch.object(self.pool, "attach_payload", new=refuse):
            try:
                self.state.prepare_capture_handoff(
                    self.ticket,
                    self.pool,
                    self.lease,
                    payload,
                    closing_bytes=2,
                    compiler=self.compiler,
                    compiler_facts=(self.leaf,),
                    compiler_bytes=3,
                )
            except ValueError as error:
                retained = error
        payload = None
        gc.collect()
        self.assertIsNotNone(retained)
        self.assertIsNotNone(retained.__traceback__)
        self.assertIsNone(reference())

    def test_uncertain_commit_never_replays_or_reports_closed(self):
        self.prepare()
        commit = self.pool.commit_handoff
        failure = KeyboardInterrupt("after original commit")
        calls = []

        def interrupted(*args):
            calls.append(True)
            commit(*args)
            raise failure

        with mock.patch.object(self.pool, "commit_handoff", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt) as raised:
                self.state.commit_capture_handoff(self.ticket)
            self.assertIs(raised.exception, failure)
            with self.assertRaises(ValueError):
                self.state.commit_capture_handoff(self.ticket)
        self.assertEqual(calls, [True])
        self.assertEqual(self.state._handoffs[self.ticket][3], "COMMITTING")
        with self.assertRaises(ValueError):
            self.state.report_capture(self.ticket, failed=False)

    def test_each_observation_keeps_metadata_charge_while_compiler_source_deduplicates(
        self,
    ):
        self.prepare()
        self.state.commit_capture_handoff(self.ticket)
        self.pool.settle_capture_cleanup(self.lease, successful=True)
        first = self.pool.statistics()["bytes"]
        ticket, lease = self.enroll("second")
        self.prepare(ticket=ticket, lease=lease)
        self.state.commit_capture_handoff(ticket)
        self.pool.settle_capture_cleanup(lease, successful=True)
        self.assertEqual(self.pool.statistics()["compiler_snapshots"], 1)
        self.assertEqual(self.pool.statistics()["bytes"] - first, 2 * 1024 * 1024 + 2)

    def test_closing_rejects_duplicate_lease_set_even_when_count_matches(self):
        self.prepare()
        self.state.commit_capture_handoff(self.ticket)
        self.pool.settle_capture_cleanup(self.lease, successful=True)
        ticket, lease = self.enroll("second")
        self.prepare(ticket=ticket, lease=lease)
        self.state.commit_capture_handoff(ticket)
        self.pool.settle_capture_cleanup(lease, successful=True)
        with self.assertRaisesRegex(ValueError, "membership differs"):
            self.pool.prepare_closing(
                self.state._resource_owner_handle,
                expected_captures=(self.lease, self.lease),
            )
        self.assertEqual(self.pool.statistics()["bytes"], 0)

    def test_closing_rejects_foreign_original_handle_from_another_pool(self):
        self.prepare()
        self.state.commit_capture_handoff(self.ticket)
        self.pool.settle_capture_cleanup(self.lease, successful=True)
        foreign = _VerifierResourcePool()
        lease = foreign.reserve_capture(4)
        self.addCleanup(foreign.settle_capture_cleanup, lease, successful=False)
        with self.assertRaisesRegex(ValueError, "membership differs"):
            self.pool.prepare_closing(
                self.state._resource_owner_handle, expected_captures=(lease,)
            )
        self.assertEqual(self.pool.statistics()["bytes"], 0)

    def test_closing_rejects_tuple_subclass_without_iteration(self):
        self.prepare()
        self.state.commit_capture_handoff(self.ticket)
        self.pool.settle_capture_cleanup(self.lease, successful=True)
        calls = []

        class Handles(tuple):
            def __iter__(self):
                calls.append(True)
                raise AssertionError("foreign iterator")

        with self.assertRaises(TypeError):
            self.pool.prepare_closing(
                self.state._resource_owner_handle,
                expected_captures=Handles((self.lease,)),
            )
        self.assertFalse(calls)
