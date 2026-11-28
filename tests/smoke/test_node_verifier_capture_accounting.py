"""Actual shared capture accounting; no runtime-origin or native qualification."""

import threading
import unittest
import weakref
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import node_library_verifier_inspection as captures
from literate_ai.adapters.node_sdk_verifier_resources import _VerifierResourcePool
from tests.smoke import test_node_sdk_verifier_runtime as runtime_fixture


class CaptureAccountingTests(unittest.TestCase):
    def setUp(self):
        self.journal = {}
        self.enterContext(mock.patch.object(captures, "_PENDING_CLEANUP", self.journal))

    def tearDown(self):
        self.assertFalse(self.journal)

    def runtime_membership(self):
        control = runtime_fixture.RuntimeInspectionStateTests()
        control.setUp()
        self.addCleanup(control.doCleanups)
        ticket = control.ticket()
        return control, ticket, (weakref.ref(control.operation), weakref.ref(ticket))

    def test_enrollment_publication_interruptions_poison_original_ticket(self):
        for boundary in ("weakref", "second-write", "lock-exit"):
            with self.subTest(boundary=boundary):
                self.exercise_enrollment_interruption(boundary)

    def exercise_enrollment_interruption(self, boundary):
        control, ticket, _membership = self.runtime_membership()
        failure = KeyboardInterrupt("enrollment " + boundary)
        reservation = [None] * 10

        class Entry(list):
            def __setitem__(self, key, value):
                if key == 5 and boundary == "second-write":
                    raise failure
                return super().__setitem__(key, value)

        entry = Entry(
            [
                None,
                0,
                False,
                False,
                SimpleNamespace(description=None),
                None,
                reservation,
            ]
        )
        lock = captures._LOCK

        class ExitFailure:
            def __enter__(self):
                lock.acquire()

            def __exit__(self, *_args):
                lock.release()
                if boundary == "lock-exit":
                    raise failure

        def reference(value):
            if boundary == "weakref":
                raise failure
            return weakref.ref(value)

        handle = object()
        with (
            mock.patch.object(captures, "_current"),
            mock.patch.object(captures, "_LIVE", {handle: entry}),
            mock.patch.object(captures, "_LOCK", ExitFailure()),
            mock.patch.object(captures, "weakref", SimpleNamespace(ref=reference)),
            mock.patch.object(
                runtime_fixture.owner,
                "enroll_node_verifier_capture",
                return_value=ticket,
            ) as enroll,
        ):
            with self.assertRaises(KeyboardInterrupt) as raised:
                captures.enroll_runtime_verifier_inspection(control.operation, handle)
            self.assertIs(raised.exception, failure)
            enroll.assert_called_once()
        with self.assertRaisesRegex(ValueError, "poisoned"):
            ticket.require_current()
        failure.__traceback__ = None

    def test_closed_report_observes_completed_cleanup(self):
        control, ticket, membership = self.runtime_membership()
        pool = _VerifierResourcePool()
        original_report = captures._report_capture_membership
        observed = []

        def report(refs, *, failed):
            observed.append((failed, pool.statistics(), bool(self.journal)))
            self.assertNotIn("terminal", captures._RESERVED)
            original_report(refs, failed=failed)

        with (
            mock.patch.object(captures, "_RESOURCE_POOL", pool),
            mock.patch.object(
                captures, "_report_capture_membership", side_effect=report
            ),
        ):
            with captures._reserve_inspection("terminal", object(), object()) as row:
                row[9] = membership
                self.assertEqual(
                    control.state._tickets[next(iter(control.state._tickets))][2],
                    "CAPTURING",
                )
        self.assertEqual(len(observed), 1)
        self.assertFalse(observed[0][0])
        self.assertEqual(observed[0][1]["bytes"], 0)
        self.assertFalse(observed[0][2])
        ticket.require_current()
        self.assertEqual(
            control.state._tickets[next(iter(control.state._tickets))][2], "CLOSED"
        )

    def test_cleanup_failure_poison_survives_journal_recovery(self):
        control, ticket, membership = self.runtime_membership()
        pool = _VerifierResourcePool()
        failure = KeyboardInterrupt("exact settlement cancellation")
        with mock.patch.object(captures, "_RESOURCE_POOL", pool):
            with mock.patch.object(pool, "settle_capture_cleanup", side_effect=failure):
                with self.assertRaises(KeyboardInterrupt) as raised:
                    with captures._reserve_inspection(
                        "terminal", object(), object()
                    ) as row:
                        row[9] = membership
                self.assertIs(raised.exception, failure)
            with self.assertRaisesRegex(ValueError, "poisoned"):
                ticket.require_current()
            captures._resume_ending_reservations()
        self.assertFalse(self.journal)
        self.assertEqual(pool.statistics()["bytes"], 0)
        with self.assertRaisesRegex(ValueError, "poisoned"):
            ticket.require_current()
        failure.__traceback__ = None

    def test_uncertain_closed_publication_is_downgraded_without_replay(self):
        control, ticket, membership = self.runtime_membership()
        pool = _VerifierResourcePool()
        original_report = captures._report_capture_membership
        failure = KeyboardInterrupt("exact terminal publication cancellation")
        attempts = []

        def report(refs, *, failed):
            attempts.append(failed)
            original_report(refs, failed=failed)
            if not failed:
                raise failure

        with (
            mock.patch.object(captures, "_RESOURCE_POOL", pool),
            mock.patch.object(
                captures, "_report_capture_membership", side_effect=report
            ),
        ):
            with self.assertRaises(KeyboardInterrupt) as raised:
                with captures._reserve_inspection(
                    "terminal", object(), object()
                ) as row:
                    row[9] = membership
            self.assertIs(raised.exception, failure)
        self.assertEqual(attempts, [False, True])
        with self.assertRaisesRegex(ValueError, "poisoned"):
            ticket.require_current()
        failure.__traceback__ = None

    def test_last_subject_references_drop_unlocked_while_charged(self):
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled):
                self.exercise_last_subject_release(cancelled)

    def exercise_last_subject_release(self, cancelled):
        class Subject:
            pass

        pool = _VerifierResourcePool()
        original_lock = captures._LOCK
        entry_box, references, observations, threads = [], [], [], []
        failure = KeyboardInterrupt("original detachment cancellation")

        class InterruptingLock:
            fired = False

            def __enter__(self):
                original_lock.acquire()
                return self

            def __exit__(self, *_error):
                interrupt = (
                    cancelled
                    and not self.fired
                    and entry_box
                    and entry_box[0][0] is None
                )
                if interrupt:
                    self.fired = True
                original_lock.release()
                if interrupt:
                    raise failure
                return False

        def released(_reference):
            result = []

            def probe():
                acquired = original_lock.acquire(timeout=1)
                try:
                    result.append((acquired, pool.statistics()["bytes"]))
                finally:
                    if acquired:
                        original_lock.release()

            thread = threading.Thread(target=probe)
            threads.append(thread)
            thread.start()
            thread.join(timeout=2)
            observations.extend(result)

        def exercise():
            with captures._reserve_inspection(
                "final-refs", Subject(), Subject()
            ) as entry:
                entry_box.append(entry)
                references.extend(weakref.ref(value, released) for value in entry[:2])

        with (
            mock.patch.object(captures, "_RESOURCE_POOL", pool),
            mock.patch.object(captures, "_LOCK", InterruptingLock()),
        ):
            if cancelled:
                with self.assertRaises(KeyboardInterrupt) as raised:
                    exercise()
                self.assertIs(raised.exception, failure)
            else:
                exercise()
        for thread in threads:
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
        self.assertTrue(all(reference() is None for reference in references))
        self.assertEqual(len(observations), 2)
        self.assertTrue(
            all(
                acquired and charged == captures._MAX_BYTES
                for acquired, charged in observations
            )
        )
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_same_lease_retains_closing_charge_after_capture_registry_removal(self):
        pool = _VerifierResourcePool(maximum_bytes=captures._MAX_BYTES)
        owner = pool.create_owner()
        with mock.patch.object(captures, "_RESOURCE_POOL", pool):
            with captures._reserve_inspection("first", object(), object()) as entry:
                captures._reserve_bytes(entry, 2)
                pool.prepare_handoff(
                    entry[4],
                    owner,
                    closing_bytes=2,
                    compiler=object(),
                    compiler_facts=(object(),),
                    compiler_bytes=3,
                )
                pool.attach_payload(entry[4], object())
                pool.commit_handoff(entry[4])
            self.assertNotIn("first", captures._RESERVED)
            self.assertEqual(pool.statistics()["bytes"], 5)
            self.assertEqual(pool.statistics()["slots"], 1)
            with self.assertRaisesRegex(ValueError, "capacity exhausted"):
                with captures._reserve_inspection("second", object(), object()):
                    self.fail("closing bytes must remain in the shared quota")
            pool.retire(owner)
            with captures._reserve_inspection("second", object(), object()):
                self.assertEqual(pool.statistics()["slots"], 1)
        self.assertEqual(pool.statistics()["bytes"], 0)
        self.assertEqual(pool.statistics()["slots"], 0)

    def test_duplicate_admission_releases_only_the_new_lease(self):
        pool = _VerifierResourcePool(maximum_bytes=2 * captures._MAX_BYTES)
        with mock.patch.object(captures, "_RESOURCE_POOL", pool):
            with captures._reserve_inspection("duplicate", object(), object()) as entry:
                with self.assertRaisesRegex(ValueError, "already active"):
                    with captures._reserve_inspection("duplicate", object(), object()):
                        self.fail("duplicate capture admitted")
                self.assertIs(captures._RESERVED["duplicate"], entry)
                self.assertEqual(pool.statistics()["bytes"], captures._MAX_BYTES)
                self.assertEqual(pool.statistics()["slots"], 1)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_registration_allocation_failure_preserves_primary_and_releases(self):
        failure = MemoryError("original registration insertion failure")

        class FailAfterInsert(dict):
            def __setitem__(self, key, value):
                super().__setitem__(key, value)
                raise failure

        pool = _VerifierResourcePool()
        registry = FailAfterInsert()
        with (
            mock.patch.object(captures, "_RESOURCE_POOL", pool),
            mock.patch.object(captures, "_RESERVED", registry),
        ):
            with self.assertRaises(MemoryError) as raised:
                with captures._reserve_inspection("allocation", object(), object()):
                    self.fail("failed registration admitted")
        self.assertIs(raised.exception, failure)
        self.assertFalse(registry)
        self.assertEqual(pool.statistics()["bytes"], 0)
        self.assertEqual(pool.statistics()["slots"], 0)

    def test_registry_cleanup_cancellation_preserves_body_failure_and_retries(self):
        primary = ValueError("original capture body failure")
        observations = []

        class InterruptPop(dict):
            fired = False

            def pop(self, key, default=None):
                observations.append(pool.statistics()["bytes"])
                if not self.fired:
                    self.fired = True
                    raise KeyboardInterrupt("secondary registry cleanup cancellation")
                return super().pop(key, default)

        pool, registry = _VerifierResourcePool(), InterruptPop()
        with (
            mock.patch.object(captures, "_RESOURCE_POOL", pool),
            mock.patch.object(captures, "_RESERVED", registry),
        ):
            with self.assertRaises(ValueError) as raised:
                with captures._reserve_inspection("cancel", object(), object()):
                    raise primary
        self.assertIs(raised.exception, primary)
        self.assertFalse(registry)
        self.assertEqual(pool.statistics()["bytes"], 0)
        self.assertGreaterEqual(len(observations), 2)
        self.assertTrue(all(amount == captures._MAX_BYTES for amount in observations))

    def test_unremoved_identity_retains_charge_and_resumes_after_error(self):
        failure = KeyboardInterrupt("original identity cleanup cancellation")

        class BlockPop(dict):
            blocked = True

            def pop(self, key, default=None):
                if self.blocked:
                    raise failure
                return super().pop(key, default)

        pool, registry = _VerifierResourcePool(), BlockPop()
        with (
            mock.patch.object(captures, "_RESOURCE_POOL", pool),
            mock.patch.object(captures, "_RESERVED", registry),
        ):
            with self.assertRaises(KeyboardInterrupt) as raised:
                with captures._reserve_inspection(
                    "retained", object(), object()
                ) as entry:
                    pass
            self.assertIs(raised.exception, failure)
            self.assertIs(registry["retained"], entry)
            self.assertIsNotNone(entry[1])
            self.assertEqual(pool.statistics()["bytes"], captures._MAX_BYTES)
            self.assertTrue(self.journal)
            registry.blocked = False
            captures._resume_ending_reservations()
            self.assertFalse(registry)
            self.assertIsNone(entry[1])
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_interrupted_before_settlement_retains_a_resumable_exact_lease(self):
        failure = KeyboardInterrupt("original cancellation before settlement")
        pool = _VerifierResourcePool()
        with mock.patch.object(captures, "_RESOURCE_POOL", pool):
            with mock.patch.object(pool, "settle_capture_cleanup", side_effect=failure):
                with self.assertRaises(KeyboardInterrupt) as raised:
                    with captures._reserve_inspection(
                        "unsettled", object(), object()
                    ) as entry:
                        pass
                self.assertIs(raised.exception, failure)
                self.assertNotIn("unsettled", captures._RESERVED)
                self.assertTrue(pool._captures[entry[4]].active)
                self.assertEqual(pool.statistics()["bytes"], captures._MAX_BYTES)
                self.assertIs(self.journal[entry[4]], entry)
            captures._resume_ending_reservations()
        self.assertEqual(pool.statistics()["bytes"], 0)
        self.assertEqual(pool.statistics()["slots"], 0)

    def test_release_failure_preserves_primary_and_drains_original_lease(self):
        primary = ValueError("original capture body failure")
        pool = _VerifierResourcePool()
        original = pool._next_release
        calls = []
        armed = False

        def fail_once():
            if armed:
                calls.append(True)
                if len(calls) == 1:
                    raise MemoryError("secondary release allocation failure")
            return original()

        with (
            mock.patch.object(captures, "_RESOURCE_POOL", pool),
            mock.patch.object(pool, "_next_release", side_effect=fail_once),
        ):
            with self.assertRaises(ValueError) as raised:
                with captures._reserve_inspection("release", object(), object()):
                    armed = True
                    raise primary
        self.assertIs(raised.exception, primary)
        self.assertGreaterEqual(len(calls), 2)
        self.assertNotIn("release", captures._RESERVED)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_cleanup_cancellation_after_success_withholds_acknowledgment(self):
        pool = _VerifierResourcePool()
        original = pool.settle_capture_cleanup
        failure = KeyboardInterrupt("original capture cleanup cancellation")
        calls = []

        def interrupt(*args, **kwargs):
            calls.append(True)
            original(*args, **kwargs)
            if len(calls) == 1:
                raise failure

        with (
            mock.patch.object(captures, "_RESOURCE_POOL", pool),
            mock.patch.object(pool, "settle_capture_cleanup", side_effect=interrupt),
        ):
            with self.assertRaises(KeyboardInterrupt) as raised:
                with captures._reserve_inspection("closed", object(), object()):
                    pass
        self.assertIs(raised.exception, failure)
        self.assertEqual(len(calls), 2)
        self.assertNotIn("closed", captures._RESERVED)
        self.assertEqual(pool.statistics()["bytes"], 0)
