"""Typed closing cleanup against real quota leases; no runtime/phase authority."""

import gc
import threading
import unittest
import weakref
from unittest import mock

from literate_ai.adapters import node_sdk_verifier_closing_payload as payload_owner
from literate_ai.adapters import node_sdk_verifier_resources as resources
from literate_ai.adapters.node_sdk_verifier_closing_payload import (
    _VerifierClosingPayload,
)
from literate_ai.adapters.node_sdk_verifier_resources import _VerifierResourcePool


class Source:
    pass


class ClosingPayloadReleaseTests(unittest.TestCase):
    def test_fixed_factory_refuses_constructor_substitution_before_callbacks(self):
        called = []

        def substituted(*args, **kwargs):
            called.append(True)
            raise AssertionError("substituted constructor called")

        for name in ("__init__",):
            with self.subTest(name=name):
                with mock.patch.object(_VerifierClosingPayload, name, substituted):
                    with self.assertRaisesRegex(ValueError, "namespace changed"):
                        payload_owner._new_closing_payload(
                            (lambda: None,) * 4, (lambda: None,) * 3
                        )
        self.assertEqual(called, [])

    def test_payload_requires_all_three_fixed_cleanup_owners(self):
        with self.assertRaises(TypeError):
            _VerifierClosingPayload((lambda: None,) * 4, (lambda: None,) * 2)

    def unlocked_observation(self, pool):
        result = []

        def observe():
            acquired = pool._lock.acquire(timeout=1)
            try:
                result.append((acquired, pool.statistics()["bytes"]))
            finally:
                if acquired:
                    pool._lock.release()

        thread = threading.Thread(target=observe)
        thread.start()
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(result), 1)
        return result[0]

    def fixture(self, *, failed_component=None):
        pool = _VerifierResourcePool(maximum_bytes=20)
        owner = pool.create_owner()
        lease = pool.reserve_capture(4)
        boxes = ([Source()], [Source()], [Source()])
        references = tuple(weakref.ref(box[0]) for box in boxes)
        events = []
        attempts = [0, 0, 0]
        failure = MemoryError("original component cleanup interruption")

        def compiler_guard():
            if not boxes[0]:
                raise ValueError("compiler source retired")

        def oracle_guard():
            if not boxes[1]:
                raise ValueError("oracle source retired")

        def file_guard():
            if not boxes[2]:
                raise ValueError("file metadata retired")

        def release(index):
            attempts[index] += 1
            events.append((index, *self.unlocked_observation(pool)))
            if failed_component == index and attempts[index] == 1:
                raise failure
            boxes[index].clear()

        payload = _VerifierClosingPayload(
            (file_guard, lambda: None, compiler_guard, oracle_guard),
            (lambda: release(0), lambda: release(1), lambda: release(2)),
        )
        pool.prepare_handoff(
            lease,
            owner,
            closing_bytes=2,
            compiler=object(),
            compiler_facts=(object(),),
            compiler_bytes=3,
        )
        pool.attach_payload(lease, payload)
        pool.commit_handoff(lease)
        pool.capture_closed(lease, successful=True)
        return pool, owner, lease, payload, references, events, attempts, failure

    def test_components_release_outside_lock_while_original_charge_remains(self):
        pool, owner, _lease, payload, references, events, attempts, _failure = (
            self.fixture()
        )
        payload.require_current()
        pool.retire(owner)
        self.assertEqual(attempts, [1, 1, 1])
        self.assertEqual(events, [(0, True, 5), (1, True, 5), (2, True, 5)])
        self.assertTrue(all(reference() is None for reference in references))
        self.assertEqual(pool.statistics()["bytes"], 0)
        payload.release()
        payload.release()
        self.assertEqual(attempts, [1, 1, 1])
        with self.assertRaises(ValueError):
            payload.require_current()

    def test_partial_component_cleanup_is_durable_and_resumes_without_repeating_done(
        self,
    ):
        for index in (0, 1, 2):
            with self.subTest(component=index):
                pool, owner, lease, _payload, references, events, attempts, failure = (
                    self.fixture(failed_component=index)
                )
                with self.assertRaises(MemoryError) as raised:
                    pool.retire(owner)
                self.assertIs(raised.exception, failure)
                self.assertEqual(attempts, [1, 1, 1])
                self.assertIsNotNone(references[index]())
                for other in range(3):
                    if other != index:
                        self.assertIsNone(references[other]())
                self.assertIsNotNone(pool._captures[lease].payload)
                self.assertEqual(pool.statistics()["bytes"], 5)
                pool.drain_pending()
                self.assertEqual(attempts[index], 2)
                for other in range(3):
                    if other != index:
                        self.assertEqual(attempts[other], 1)
                self.assertTrue(
                    all(
                        unlocked and charged == 5
                        for _component, unlocked, charged in events
                    )
                )
                self.assertTrue(all(reference() is None for reference in references))
                self.assertEqual(pool.statistics()["bytes"], 0)

    def test_releases_wait_for_original_closing_reader_to_settle(self):
        pool, owner, _lease, _payload, references, events, _attempts, _failure = (
            self.fixture()
        )
        view = pool.prepare_closing(owner)
        pool.retire(owner)
        self.assertFalse(events)
        self.assertEqual(pool.statistics()["bytes"], 5)
        self.assertTrue(all(reference() is not None for reference in references))
        del view
        pool.closing_complete(owner)
        self.assertEqual(len(events), 3)
        self.assertTrue(all(reference() is None for reference in references))
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_detachment_allocation_failure_does_not_replay_completed_components(self):
        pool, owner, lease, _payload, references, events, attempts, _failure = (
            self.fixture()
        )

        class RefuseAllocation(list):
            def __new__(cls):
                raise MemoryError("after original component cleanup")

        with mock.patch.object(resources, "list", RefuseAllocation, create=True):
            with self.assertRaises(MemoryError):
                pool.retire(owner)
        self.assertEqual(attempts, [1, 1, 1])
        self.assertTrue(all(reference() is None for reference in references))
        self.assertIsNotNone(pool._captures[lease].payload)
        self.assertEqual(pool.statistics()["bytes"], 5)
        pool.drain_pending()
        self.assertEqual(attempts, [1, 1, 1])
        self.assertEqual(len(events), 3)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_final_payload_reference_drops_outside_lock_before_uncharging(self):
        pool, owner, _lease, payload, _references, _events, _attempts, _failure = (
            self.fixture()
        )
        observations = []
        reference = weakref.ref(
            payload, lambda _ref: observations.append(self.unlocked_observation(pool))
        )
        del payload
        pool.retire(owner)
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(observations, [(True, 5)])
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_replaced_release_helper_is_refused_without_getter_calls(self):
        pool, owner, lease, payload, _references, _events, attempts, _failure = (
            self.fixture()
        )
        called = []

        def trap(_value):
            called.append(True)
            raise AssertionError("substituted release helper invoked")

        with mock.patch.object(_VerifierClosingPayload, "_release_one", property(trap)):
            with self.assertRaisesRegex(ValueError, "namespace changed"):
                pool.retire(owner)
            self.assertIs(pool._captures[lease].payload, payload)
            self.assertEqual(pool.statistics()["bytes"], 5)
        self.assertFalse(called)
        self.assertEqual(attempts, [0, 0, 0])
        pool.drain_pending()
        self.assertEqual(attempts, [1, 1, 1])
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_class_substitution_between_components_stops_before_replacement_runs(self):
        pool = _VerifierResourcePool(maximum_bytes=20)
        owner, lease = pool.create_owner(), pool.reserve_capture(4)
        calls, replacements, patches = [], [], []

        def compiler_release():
            calls.append("compiler")
            if not patches:
                patch = mock.patch.object(
                    _VerifierClosingPayload,
                    "_release_one",
                    property(lambda _value: replacements.append(True)),
                )
                patch.start()
                patches.append(patch)

        payload = _VerifierClosingPayload(
            (lambda: None,) * 4,
            (
                compiler_release,
                lambda: calls.append("oracle"),
                lambda: calls.append("files"),
            ),
        )
        pool.prepare_handoff(
            lease,
            owner,
            closing_bytes=2,
            compiler=object(),
            compiler_facts=(object(),),
            compiler_bytes=3,
        )
        pool.attach_payload(lease, payload)
        pool.commit_handoff(lease)
        pool.capture_closed(lease, successful=True)
        try:
            with self.assertRaisesRegex(ValueError, "namespace changed"):
                pool.retire(owner)
            self.assertEqual(pool.statistics()["bytes"], 5)
            self.assertEqual(calls, ["compiler"])
            self.assertFalse(replacements)
        finally:
            for patch in patches:
                patch.stop()
        pool.drain_pending()
        self.assertEqual(calls, ["compiler", "compiler", "oracle", "files"])
        self.assertFalse(replacements)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_untyped_payload_release_property_is_never_accessed(self):
        called = []

        class OtherPayload:
            @property
            def release(self):
                called.append(True)
                raise AssertionError("arbitrary release hook accessed")

        pool = _VerifierResourcePool(maximum_bytes=20)
        owner = pool.create_owner()
        lease = pool.reserve_capture(4)
        pool.prepare_handoff(
            lease,
            owner,
            closing_bytes=2,
            compiler=object(),
            compiler_facts=(object(),),
            compiler_bytes=3,
        )
        pool.attach_payload(lease, OtherPayload())
        pool.commit_handoff(lease)
        pool.capture_closed(lease, successful=True)
        pool.retire(owner)
        self.assertFalse(called)
        self.assertEqual(pool.statistics()["bytes"], 0)
