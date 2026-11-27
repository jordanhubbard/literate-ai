"""Pure resource-owner controls, not inspection or grant qualification."""

import gc
import threading
import unittest
import weakref
from unittest import mock

from literate_ai.adapters import node_sdk_verifier_resources as resources
from literate_ai.adapters.node_sdk_verifier_resources import _VerifierResourcePool


class Payload:
    def __init__(self, content):
        self.content = content


class VerifierResourceTests(unittest.TestCase):
    def test_owner_publication_records_original_handle_before_return(self):
        pool = _VerifierResourcePool()
        publication = resources._new_owner_publication(pool)
        self.assertIsNone(resources._published_owner(publication))
        handle = pool.create_owner(_publication=publication)
        self.assertIs(resources._published_owner(publication), handle)
        with self.assertRaisesRegex(ValueError, "already used"):
            pool.create_owner(_publication=publication)
        pool.retire(handle)
        self.assertEqual(pool.statistics()["owners"], 0)

    def test_owner_publication_cannot_be_used_with_a_different_pool(self):
        pool, foreign = _VerifierResourcePool(), _VerifierResourcePool()
        publication = resources._new_owner_publication(pool)
        with self.assertRaises(TypeError):
            foreign.create_owner(_publication=publication)
        self.assertEqual(foreign.statistics()["owners"], 0)
        handle = pool.create_owner(_publication=publication)
        pool.retire(handle)
        self.assertEqual(pool.statistics()["owners"], 0)

    def test_fresh_nested_snapshot_containers_share_original_leaf_charge(self):
        pool = _VerifierResourcePool(maximum_bytes=20)
        owner = pool.create_owner()
        compiler, source = object(), Payload(b"abc")
        facts = ((compiler, (source,)),)
        first, *_ = self.handoff(pool, owner, compiler=compiler, facts=facts)
        pool.capture_closed(first, successful=True)
        fresh_facts = tuple([(compiler, tuple([source]))])
        self.assertIsNot(fresh_facts, facts)
        second, _, _, _, fresh = self.handoff(
            pool, owner, compiler=compiler, facts=fresh_facts
        )
        self.assertFalse(fresh)
        self.assertEqual(pool.statistics()["compiler_snapshots"], 1)
        self.assertEqual(pool.statistics()["bytes"], 11)
        pool.capture_closed(second, successful=True)
        pool.retire(owner)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_original_tuple_fields_share_only_the_same_original_container(self):
        pool = _VerifierResourcePool(maximum_bytes=20)
        owner, compiler = pool.create_owner(), object()
        original = (object(),)
        first, *_ = self.handoff(
            pool,
            owner,
            compiler=compiler,
            facts=(resources._tuple_field_reference(original),),
        )
        pool.capture_closed(first, successful=True)
        second, _, _, _, fresh = self.handoff(
            pool,
            owner,
            compiler=compiler,
            facts=(resources._tuple_field_reference(original),),
        )
        self.assertFalse(fresh)
        self.assertEqual(pool.statistics()["compiler_snapshots"], 1)
        pool.capture_closed(second, successful=True)
        pool.retire(owner)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_equal_replacement_of_original_tuple_field_refuses_before_handoff(self):
        pool = _VerifierResourcePool(maximum_bytes=20)
        owner, compiler = pool.create_owner(), object()
        original = (object(),)
        replacement = tuple(list(original))
        self.assertEqual(original, replacement)
        self.assertIsNot(original, replacement)
        first, *_ = self.handoff(
            pool,
            owner,
            compiler=compiler,
            facts=(resources._tuple_field_reference(original),),
        )
        pool.capture_closed(first, successful=True)
        second = pool.reserve_capture(4)
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            pool.prepare_handoff(
                second,
                owner,
                closing_bytes=2,
                compiler=compiler,
                compiler_facts=(resources._tuple_field_reference(replacement),),
                compiler_bytes=3,
            )
        pool.settle_capture_cleanup(second, successful=False)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_original_tuple_reference_refuses_substitution_without_getter_calls(self):
        original = (object(),)
        reference = resources._tuple_field_reference(original)
        called = []
        with mock.patch.object(
            resources._OriginalTupleReference,
            "__getitem__",
            property(lambda _value: called.append(True)),
        ):
            with self.assertRaisesRegex(ValueError, "namespace changed"):
                resources._validate_compiler_facts((reference,))
            with self.assertRaisesRegex(ValueError, "namespace changed"):
                resources._same_compiler_facts((reference,), (reference,))
        self.assertFalse(called)
        resources._validate_compiler_facts((reference,))

    def test_original_tuple_reference_rejects_subclasses_without_iteration(self):
        called = []

        class Substitute(tuple):
            def __iter__(self):
                called.append(True)
                raise AssertionError("substituted tuple iterator invoked")

        with self.assertRaises(TypeError):
            resources._tuple_field_reference(Substitute((object(),)))
        self.assertFalse(called)

    def test_admitted_original_tuple_anchor_cannot_be_rebased(self):
        pool = _VerifierResourcePool(maximum_bytes=20)
        owner, compiler = pool.create_owner(), object()
        original = (object(),)
        replacement = tuple(list(original))
        first, *_ = self.handoff(
            pool,
            owner,
            compiler=compiler,
            facts=(resources._tuple_field_reference(original),),
        )
        pool.capture_closed(first, successful=True)
        anchor = pool._owners[owner].compilers[id(compiler)].facts[0]
        with self.assertRaises(AttributeError):
            object.__setattr__(anchor, "_original", replacement)
        with self.assertRaises(TypeError):
            anchor[0] = replacement
        second = pool.reserve_capture(4)
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            pool.prepare_handoff(
                second,
                owner,
                closing_bytes=2,
                compiler=compiler,
                compiler_facts=(resources._tuple_field_reference(replacement),),
                compiler_bytes=3,
            )
        pool.settle_capture_cleanup(second, successful=False)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_original_tuple_reference_storage_must_remain_an_exact_tuple(self):
        reference = tuple.__new__(resources._OriginalTupleReference, ([object()],))
        with self.assertRaisesRegex(ValueError, "reference changed"):
            resources._validate_compiler_facts((reference,))

    def test_nested_changed_leaf_refuses_without_equality_or_rebaseline(self):
        calls = []

        class Trap:
            def __eq__(self, other):
                calls.append("equality")
                raise AssertionError("leaf equality called")

        pool = _VerifierResourcePool(maximum_bytes=20)
        owner, compiler, original = pool.create_owner(), object(), Trap()
        first, *_ = self.handoff(pool, owner, compiler=compiler, facts=((original,),))
        pool.capture_closed(first, successful=True)
        second = pool.reserve_capture(4)
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            pool.prepare_handoff(
                second,
                owner,
                closing_bytes=2,
                compiler=compiler,
                compiler_facts=((Trap(),),),
                compiler_bytes=3,
            )
        self.assertFalse(calls)
        pool.settle_capture_cleanup(second, successful=False)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_tuple_subclass_is_refused_before_iteration(self):
        calls = []

        class Container(tuple):
            def __iter__(self):
                calls.append(True)
                raise AssertionError("substitute iterator called")

        with self.assertRaises(TypeError):
            resources._validate_compiler_facts((Container((object(),)),))
        self.assertFalse(calls)

    def test_nested_snapshot_depth_width_and_total_node_bounds(self):
        nested = (object(),)
        for _ in range(9):
            nested = (nested,)
        for facts in (nested, ((object(),) * 4097,), ((object(),) * 4096,) * 4):
            with self.subTest(shape=len(facts)), self.assertRaises(ValueError):
                resources._validate_compiler_facts(facts)

    def test_shared_tuple_containers_are_not_cycles(self):
        shared = (object(), object())
        facts = (shared, shared)
        resources._validate_compiler_facts(facts)
        self.assertTrue(resources._same_compiler_facts(facts, (shared, shared)))
        self.assertFalse(resources._same_compiler_facts(facts, (shared,)))

    def pending_release_fixture(self, *, retired=True):
        pool = _VerifierResourcePool(maximum_slots=4, maximum_bytes=40)
        owners = (pool.create_owner(), pool.create_owner())
        references, observations, threads = [], [], []

        def observe_release(_reference):
            result = []
            thread = threading.Thread(
                target=lambda: result.append(pool.statistics()["bytes"])
            )
            threads.append(thread)
            thread.start()
            thread.join(timeout=1)
            observations.append((not thread.is_alive(), result[0] if result else 0))

        for owner in owners:
            compiler, facts = object(), (Payload(b"abc"),)
            references.append(weakref.ref(facts[0], observe_release))
            for _index in range(2):
                capture, _, _, payload, _ = self.handoff(
                    pool, owner, compiler=compiler, facts=facts
                )
                references.append(weakref.ref(payload, observe_release))
                pool.capture_closed(capture, successful=True)
        # Queue both owners before the actual drain, as another current drainer
        # could. Only fixture setup suppresses draining; all fault/recovery calls
        # below execute the original production drain implementation.
        if retired:
            with mock.patch.object(pool, "drain_pending", return_value=None):
                for owner in owners:
                    pool.retire(owner)
        return pool, owners, references, observations, threads

    def interrupt_lock_exit(self, pool, predicate, failure):
        original = pool._lock

        class InterruptingLock:
            fired = False

            def __enter__(self):
                original.acquire()
                return self

            def __exit__(self, *_error):
                interrupt = not self.fired and predicate()
                if interrupt:
                    self.fired = True
                original.release()
                if interrupt:
                    raise failure
                return False

        pool._lock = InterruptingLock()

    def test_cancelled_drainer_publication_cannot_strand_its_token(self):
        pool, owners, references, observations, threads = self.pending_release_fixture()
        failure = KeyboardInterrupt("original drainer publication cancellation")
        self.interrupt_lock_exit(pool, lambda: pool._drainer is not None, failure)
        with self.assertRaises(KeyboardInterrupt) as raised:
            pool.drain_pending()
        self.assertIs(raised.exception, failure)
        self.assertIsNone(pool._drainer)
        self.assertEqual(pool.statistics()["bytes"], 14)
        self.assert_release_finished(pool, references, observations, threads)

    def test_cancelled_owner_factory_does_not_leave_an_unreturned_owner(self):
        pool = _VerifierResourcePool()
        failure = KeyboardInterrupt("original owner factory publication cancellation")
        self.interrupt_lock_exit(pool, lambda: bool(pool._owners), failure)
        with self.assertRaises(KeyboardInterrupt) as raised:
            pool.create_owner()
        self.assertIs(raised.exception, failure)
        pool.drain_pending()
        self.assertEqual(pool.statistics()["owners"], 0)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_cancelled_capture_factory_releases_its_unreturned_lease(self):
        pool = _VerifierResourcePool()
        failure = KeyboardInterrupt("original capture factory publication cancellation")
        self.interrupt_lock_exit(pool, lambda: bool(pool._captures), failure)
        with self.assertRaises(KeyboardInterrupt) as raised:
            pool.reserve_capture(4)
        self.assertIs(raised.exception, failure)
        pool.drain_pending()
        self.assertEqual(pool.statistics()["bytes"], 0)
        self.assertEqual(pool.statistics()["slots"], 0)

    def test_unallocated_closing_view_does_not_leave_a_reader(self):
        pool, owners, references, observations, threads = self.pending_release_fixture(
            retired=False
        )
        failure = MemoryError("original closing view allocation failure")

        class RefuseTuple(tuple):
            def __new__(cls, _values):
                raise failure

        with mock.patch.object(resources, "tuple", RefuseTuple, create=True):
            with self.assertRaises(MemoryError) as raised:
                pool.prepare_closing(owners[0])
        self.assertIs(raised.exception, failure)
        state = pool._owners.get(owners[0])
        self.assertTrue(state is None or state.closing_borrowed is None)
        for owner in owners:
            pool.retire(owner)
        self.assert_release_finished(pool, references, observations, threads)

    def test_cancelled_closing_publication_drops_its_unreturned_view(self):
        pool, owners, references, observations, threads = self.pending_release_fixture(
            retired=False
        )
        failure = KeyboardInterrupt("original closing publication cancellation")
        self.interrupt_lock_exit(
            pool,
            lambda: any(o.closing_borrowed for o in pool._owners.values()),
            failure,
        )
        with self.assertRaises(KeyboardInterrupt) as raised:
            pool.prepare_closing(owners[0])
        self.assertIs(raised.exception, failure)
        state = pool._owners.get(owners[0])
        self.assertTrue(state is None or state.closing_borrowed is None)
        for owner in owners:
            pool.retire(owner)
        self.assert_release_finished(pool, references, observations, threads)

    def test_failed_second_closing_cannot_clear_the_first_reader(self):
        pool, owners, references, observations, threads = self.pending_release_fixture(
            retired=False
        )
        view = pool.prepare_closing(owners[0])
        with self.assertRaises(ValueError):
            pool.prepare_closing(owners[0])
        self.assertEqual(pool.statistics()["bytes"], 14)
        self.assertTrue(pool._owners[owners[0]].closing_borrowed)
        del view
        pool.closing_complete(owners[0])
        pool.retire(owners[1])
        self.assert_release_finished(pool, references, observations, threads)

    def assert_release_finished(self, pool, references, observations, threads):
        pool.drain_pending()
        pool.drain_pending()  # Idempotent cleanup never releases twice.
        gc.collect()
        for thread in threads:
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())
        self.assertTrue(all(reference() is None for reference in references))
        self.assertEqual(
            pool.statistics(),
            {
                "bytes": 0,
                "slots": 0,
                "owners": 0,
                "compiler_snapshots": 0,
            },
        )
        self.assertEqual(len(observations), len(references))
        self.assertTrue(
            all(unlocked and charged > 0 for unlocked, charged in observations)
        )

    def test_release_allocation_failure_keeps_durable_work_for_resume(self):
        pool, owners, references, observations, threads = self.pending_release_fixture()
        failure = MemoryError("original release-list allocation failure")

        class RefuseAllocation(list):
            def __new__(cls):
                raise failure

        with mock.patch.object(resources, "list", RefuseAllocation, create=True):
            with self.assertRaises(MemoryError) as raised:
                pool.drain_pending()
        self.assertIs(raised.exception, failure)
        self.assertEqual(pool.statistics()["bytes"], 14)
        self.assertTrue(all(reference() is not None for reference in references))
        self.assert_release_finished(pool, references, observations, threads)
        self.assertFalse(pool.retire(owners[0]))

    def test_release_cancellation_after_partial_detachment_remains_resumable(self):
        cuts = (
            (resources._Capture, "payload"),
            (resources._Compiler, "original"),
            (resources._Compiler, "facts"),
        )
        for cls, field in cuts:
            with self.subTest(field=field):
                pool, owners, references, observations, threads = (
                    self.pending_release_fixture()
                )
                failure = KeyboardInterrupt("original detachment cancellation")
                fired = []

                def interrupt(
                    record, name, value, *, field=field, failure=failure, fired=fired
                ):
                    object.__setattr__(record, name, value)
                    if name == field and record.releasing and not fired:
                        fired.append(True)
                        raise failure

                with mock.patch.object(cls, "__setattr__", interrupt):
                    with self.assertRaises(KeyboardInterrupt) as raised:
                        pool.drain_pending()
                self.assertIs(raised.exception, failure)
                self.assertTrue(fired)
                self.assertGreater(pool.statistics()["bytes"], 0)
                self.assert_release_finished(pool, references, observations, threads)

    def test_release_accounting_cancellation_before_or_after_pop_is_resumable(self):
        for field in ("captures", "compilers"):
            for after in (False, True):
                with self.subTest(field=field, after=after):
                    pool, owners, references, observations, threads = (
                        self.pending_release_fixture()
                    )
                    failure = KeyboardInterrupt("original accounting cancellation")

                    class InterruptPop(dict):
                        fired = False

                        def pop(
                            self, key, default=None, *, after=after, failure=failure
                        ):
                            if self.fired:
                                return super().pop(key, default)
                            self.fired = True
                            if after:
                                super().pop(key, default)
                            raise failure

                    if field == "captures":
                        pool._captures = InterruptPop(pool._captures)
                    else:
                        state = pool._owners[owners[0]]
                        state.compilers = InterruptPop(state.compilers)
                    with self.assertRaises(KeyboardInterrupt) as raised:
                        pool.drain_pending()
                    self.assertIs(raised.exception, failure)
                    self.assert_release_finished(
                        pool, references, observations, threads
                    )

    def test_handoff_allocation_failure_rolls_back_before_owner_retirement(self):
        for field in ("captures", "compilers"):
            with self.subTest(field=field):
                failure = MemoryError("original handoff insertion failure")

                class FailAfterInsert(dict):
                    def __setitem__(self, key, value, *, error=failure):
                        super().__setitem__(key, value)
                        raise error

                pool = _VerifierResourcePool(maximum_slots=1, maximum_bytes=20)
                owner, capture = pool.create_owner(), pool.reserve_capture(4)
                setattr(pool._owners[owner], field, FailAfterInsert())
                source = Payload(b"abc")
                reference = weakref.ref(source)
                with self.assertRaises(MemoryError) as raised:
                    pool.prepare_handoff(
                        capture,
                        owner,
                        closing_bytes=2,
                        compiler=object(),
                        compiler_facts=(source,),
                        compiler_bytes=3,
                    )
                self.assertIs(raised.exception, failure)
                del source
                gc.collect()
                self.assertIsNone(reference())
                self.assertEqual(pool.statistics()["bytes"], 4)
                self.assertEqual(pool.statistics()["owners"], 0)
                with self.assertRaises(ValueError):
                    pool.prepare_closing(owner)
                pool.capture_closed(capture, successful=False)
                self.assertEqual(pool.statistics()["bytes"], 0)
                self.assertEqual(pool.statistics()["slots"], 0)

    def test_snapshot_allocation_failure_preserves_primary_and_capture_charge(self):
        pool = _VerifierResourcePool(maximum_slots=1, maximum_bytes=20)
        owner, capture = pool.create_owner(), pool.reserve_capture(4)
        failure = MemoryError("original snapshot allocation failure")
        with mock.patch.object(resources, "_Compiler", side_effect=failure):
            with self.assertRaises(MemoryError) as raised:
                pool.prepare_handoff(
                    capture,
                    owner,
                    closing_bytes=2,
                    compiler=object(),
                    compiler_facts=(object(),),
                    compiler_bytes=3,
                )
        self.assertIs(raised.exception, failure)
        self.assertEqual(pool.statistics()["bytes"], 4)
        self.assertEqual(pool.statistics()["owners"], 0)
        pool.capture_closed(capture, successful=False)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_failed_unowned_capture_cannot_later_handoff(self):
        pool = _VerifierResourcePool(maximum_slots=1, maximum_bytes=20)
        owner, capture = pool.create_owner(), pool.reserve_capture(4)
        with self.assertRaises(ValueError):
            pool.resize_capture(capture, -1)
        with self.assertRaises(ValueError):
            pool.prepare_handoff(
                capture,
                owner,
                closing_bytes=2,
                compiler=object(),
                compiler_facts=(object(),),
                compiler_bytes=3,
            )
        self.assertEqual(pool.statistics()["bytes"], 4)
        pool.capture_closed(capture, successful=False)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_handoff_charge_cannot_be_resized_away(self):
        pool = _VerifierResourcePool(maximum_slots=1, maximum_bytes=20)
        owner = pool.create_owner()
        capture, compiler, facts, payload, _ = self.handoff(pool, owner)
        with self.assertRaises(ValueError):
            pool.resize_capture(capture, 0)
        self.assertEqual(pool.statistics()["bytes"], 9)
        with self.assertRaises(ValueError):
            pool.prepare_closing(owner)
        pool.capture_closed(capture, successful=True)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_limits_cannot_exceed_the_shared_ceiling(self):
        for options in (
            {"maximum_slots": 34},
            {"maximum_bytes": 512 * 1024 * 1024 + 1},
            {"maximum_slots": True},
            {"maximum_bytes": 2.5},
        ):
            with self.subTest(options=options), self.assertRaises(ValueError):
                _VerifierResourcePool(**options)

    def handoff(self, pool, owner, *, compiler=None, facts=None):
        compiler = object() if compiler is None else compiler
        facts = (Payload(b"abc"),) if facts is None else facts
        capture = pool.reserve_capture(4)
        fresh = pool.prepare_handoff(
            capture,
            owner,
            closing_bytes=2,
            compiler=compiler,
            compiler_facts=facts,
            compiler_bytes=3,
        )
        payload = Payload(b"xy")
        pool.attach_payload(capture, payload)
        pool.commit_handoff(capture)
        return capture, compiler, facts, payload, fresh

    def test_one_slot_transfers_and_payloads_collect_after_retirement(self):
        pool = _VerifierResourcePool(maximum_slots=2, maximum_bytes=20)
        owner = pool.create_owner()
        capture, compiler, facts, payload, fresh = self.handoff(pool, owner)
        weak_source, weak_payload = weakref.ref(facts[0]), weakref.ref(payload)
        self.assertTrue(fresh)
        self.assertEqual(pool.statistics()["bytes"], 9)
        pool.capture_closed(capture, successful=True)
        self.assertEqual(pool.statistics()["slots"], 1)
        self.assertEqual(pool.statistics()["bytes"], 5)
        view = pool.prepare_closing(owner)
        self.assertIs(view[0][0], payload)
        del view, compiler, facts, payload
        pool.closing_complete(owner)
        pool.retire(owner)
        gc.collect()
        self.assertIsNone(weak_source())
        self.assertIsNone(weak_payload())
        self.assertEqual(pool.statistics()["bytes"], 0)
        self.assertEqual(pool.statistics()["slots"], 0)

    def test_capacity_refuses_before_retaining_snapshot(self):
        pool = _VerifierResourcePool(maximum_slots=1, maximum_bytes=8)
        owner, capture = pool.create_owner(), pool.reserve_capture(4)
        compiler, source = object(), Payload(b"abc")
        reference = weakref.ref(source)
        with self.assertRaisesRegex(ValueError, "capacity"):
            pool.prepare_handoff(
                capture,
                owner,
                closing_bytes=2,
                compiler=compiler,
                compiler_facts=(source,),
                compiler_bytes=3,
            )
        del source
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(pool.statistics()["bytes"], 4)
        pool.capture_closed(capture, successful=False)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_compiler_dedup_is_exact_and_operation_local(self):
        pool = _VerifierResourcePool(maximum_slots=3, maximum_bytes=30)
        first, second = pool.create_owner(), pool.create_owner()
        compiler, facts = object(), (Payload(b"abc"),)
        a, _, _, pa, fresh_a = self.handoff(pool, first, compiler=compiler, facts=facts)
        b, _, _, pb, fresh_b = self.handoff(
            pool, first, compiler=compiler, facts=tuple(list(facts))
        )
        c, _, _, pc, fresh_c = self.handoff(
            pool, second, compiler=compiler, facts=facts
        )
        self.assertEqual((fresh_a, fresh_b, fresh_c), (True, False, True))
        self.assertEqual(pool.statistics()["compiler_snapshots"], 2)
        for handle in (a, b, c):
            pool.capture_closed(handle, successful=True)
        pool.retire(first)
        pool.retire(second)
        self.assertEqual(pool.statistics()["bytes"], 0)
        self.assertEqual(pool.statistics()["owners"], 0)

    def test_changed_snapshot_is_sticky_and_does_not_call_equality(self):
        class Trap:
            def __eq__(self, other):
                raise AssertionError("snapshot equality called")

        pool = _VerifierResourcePool(maximum_slots=2, maximum_bytes=20)
        owner = pool.create_owner()
        compiler, original = object(), Trap()
        a, _, _, payload, _ = self.handoff(
            pool, owner, compiler=compiler, facts=(original,)
        )
        pool.capture_closed(a, successful=True)
        b = pool.reserve_capture(1)
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            pool.prepare_handoff(
                b,
                owner,
                closing_bytes=1,
                compiler=compiler,
                compiler_facts=(Trap(),),
                compiler_bytes=3,
            )
        with self.assertRaises(ValueError):
            pool.prepare_closing(owner)
        pool.capture_closed(b, successful=False)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_retirement_waits_for_active_capture(self):
        pool = _VerifierResourcePool(maximum_slots=1, maximum_bytes=20)
        owner = pool.create_owner()
        capture, compiler, facts, payload, _ = self.handoff(pool, owner)
        source_ref, payload_ref = weakref.ref(facts[0]), weakref.ref(payload)
        del compiler, facts, payload
        pool.retire(owner)
        gc.collect()
        self.assertEqual(pool.statistics()["bytes"], 9)
        self.assertIsNotNone(source_ref())
        self.assertIsNotNone(payload_ref())
        pool.capture_closed(capture, successful=False)
        gc.collect()
        self.assertIsNone(source_ref())
        self.assertIsNone(payload_ref())
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_retirement_waits_for_closing_reader(self):
        pool = _VerifierResourcePool(maximum_slots=1, maximum_bytes=20)
        owner = pool.create_owner()
        capture, compiler, facts, payload, _ = self.handoff(pool, owner)
        source_ref = weakref.ref(facts[0])
        pool.capture_closed(capture, successful=True)
        view = pool.prepare_closing(owner)
        pool.retire(owner)
        self.assertEqual(pool.statistics()["bytes"], 5)
        del view, compiler, facts, payload
        pool.closing_complete(owner)
        gc.collect()
        self.assertIsNone(source_ref())
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_concurrent_retire_and_capture_settlement(self):
        for _ in range(10):
            pool = _VerifierResourcePool(maximum_slots=1, maximum_bytes=20)
            owner = pool.create_owner()
            capture, compiler, facts, payload, _ = self.handoff(pool, owner)
            barrier = threading.Barrier(2)
            errors = []

            def run(action, barrier=barrier, errors=errors):
                try:
                    barrier.wait(timeout=2)
                    action()
                except BaseException as error:
                    errors.append(error)

            threads = [
                threading.Thread(target=run, args=(action,))
                for action in (
                    lambda pool=pool, owner=owner: pool.retire(owner),
                    lambda pool=pool, capture=capture: pool.capture_closed(
                        capture, successful=True
                    ),
                )
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=3)
                self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(pool.statistics()["bytes"], 0)

    def test_payload_release_is_unlocked_and_still_charged(self):
        pool = _VerifierResourcePool(maximum_slots=1, maximum_bytes=20)
        owner = pool.create_owner()
        capture, compiler, facts, payload, _ = self.handoff(pool, owner)
        observations, threads = [], []

        def on_release(_reference):
            result = []
            thread = threading.Thread(
                target=lambda: result.append(pool.statistics()["bytes"])
            )
            threads.append(thread)
            thread.start()
            thread.join(timeout=1)
            observations.append((not thread.is_alive(), result[0] if result else None))

        reference = weakref.ref(payload, on_release)
        pool.capture_closed(capture, successful=True)
        del payload
        pool.retire(owner)
        for thread in threads:
            thread.join(timeout=2)
        self.assertIsNone(reference())
        self.assertTrue(observations)
        self.assertTrue(
            all(unlocked and charged >= 2 for unlocked, charged in observations)
        )

    def test_failed_commit_cannot_recover_into_a_closing_witness(self):
        pool = _VerifierResourcePool(maximum_slots=1, maximum_bytes=20)
        owner, capture = pool.create_owner(), pool.reserve_capture(4)
        pool.prepare_handoff(
            capture,
            owner,
            closing_bytes=2,
            compiler=object(),
            compiler_facts=(object(),),
            compiler_bytes=3,
        )
        with self.assertRaises(ValueError):
            pool.commit_handoff(capture)
        with self.assertRaises(ValueError):
            pool.attach_payload(capture, Payload(b"xy"))
        with self.assertRaises(ValueError):
            pool.prepare_closing(owner)
        pool.capture_closed(capture, successful=False)
        self.assertEqual(pool.statistics()["bytes"], 0)

    def test_duplicate_settlement_never_double_releases(self):
        pool = _VerifierResourcePool(maximum_slots=1, maximum_bytes=4)
        capture = pool.reserve_capture(4)
        pool.capture_closed(capture, successful=True)
        with self.assertRaises(ValueError):
            pool.capture_closed(capture, successful=True)
        self.assertEqual(pool.statistics()["bytes"], 0)
        with self.assertRaises(ValueError):
            pool.reserve_capture(True)
