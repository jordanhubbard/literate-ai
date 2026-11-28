"""Injected state/storage controls, not original runtime or grant qualification."""

import copy
import dataclasses
import gc
import inspect
import os
import shutil
import threading
import types
import unittest
import weakref
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import node_library_verifier_inspection as captures
from literate_ai.adapters import node_sdk_verifier_runtime as owner
from literate_ai.adapters.node_sdk_verifier_closing_payload import _new_closing_payload
from literate_ai.adapters.node_sdk_verifier_resources import _VerifierResourcePool
from literate_ai.contracts import canonical_identity
from tests.smoke import test_node_provider_lifecycle as provider_fixture


def controller(*, ports=None, compiler=None):
    """Deliberately bypass assembly to isolate private retirement mechanics."""
    bound = SimpleNamespace(
        configuration=SimpleNamespace(),
        ports=SimpleNamespace() if ports is None else ports,
        closure=object(),
        consumer=object(),
        target=object()
        if compiler is None
        else SimpleNamespace(typescript=SimpleNamespace(compiler=compiler)),
    )
    binding_handle = object.__new__(owner._RuntimeInspectionBinding)
    binding = owner._BindingState(binding_handle, bound)
    bound._inspection_binding = binding_handle
    bound._inspection_registration = binding
    bound.configuration._binding = bound.configuration._original_binding = bound
    bound.ports._node_sdk_host_binding = bound
    operation = object.__new__(owner._RuntimeInspectionOperation)
    state = owner._OperationState(binding, operation)
    binding.active = state
    owner._OPERATIONS[operation] = weakref.ref(state)
    model = canonical_identity("controlled metadata")
    state._witness = state._invocation_witness = owner._finite_metadata(model)
    state._state, state._sealed = "LIVE", True
    return bound, binding, state, operation, model


class RuntimeResourceOwnerTests(unittest.TestCase):
    def setUp(self):
        self.bound, self.binding, self.state, self.operation, _model = controller()
        self.addCleanup(self.state.retire)

    def lock_available_to_other_thread(self):
        results = []

        def probe():
            acquired = self.binding.lock.acquire(timeout=1)
            results.append(acquired)
            if acquired:
                self.binding.lock.release()

        thread = threading.Thread(target=probe)
        thread.start()
        thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        return results == [True]

    def test_lazy_owner_is_reused_and_allocated_retired_outside_binding_lock(self):
        pool = _VerifierResourcePool()
        create, retire = pool.create_owner, pool.retire
        observations = []

        def allocate(**kwargs):
            observations.append(("allocate", self.lock_available_to_other_thread()))
            return create(**kwargs)

        def release(*args, **kwargs):
            observations.append(("retire", self.lock_available_to_other_thread()))
            return retire(*args, **kwargs)

        with (
            mock.patch.object(pool, "create_owner", side_effect=allocate),
            mock.patch.object(pool, "retire", side_effect=release),
        ):
            first = self.state.resource_owner_for(pool)
            self.assertIs(self.state.resource_owner_for(pool), first)
            self.assertEqual(pool.statistics()["owners"], 1)
            self.state.retire()
        self.assertEqual(observations, [("allocate", True), ("retire", True)])
        self.assertEqual(pool.statistics()["owners"], 0)

    def test_concurrent_first_allocations_publish_one_owner_and_retire_loser(self):
        pool = _VerifierResourcePool()
        create = pool.create_owner
        barrier = threading.Barrier(2)
        results, errors = [], []

        def allocate(**kwargs):
            result = create(**kwargs)
            barrier.wait(timeout=3)
            return result

        def acquire():
            try:
                results.append(self.state.resource_owner_for(pool))
            except BaseException as error:
                errors.append(error)

        with mock.patch.object(pool, "create_owner", side_effect=allocate):
            threads = [threading.Thread(target=acquire) for _ in range(2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=4)
                self.assertFalse(thread.is_alive())
        self.assertFalse(errors)
        self.assertEqual(len(results), 2)
        self.assertIs(results[0], results[1])
        self.assertEqual(pool.statistics()["owners"], 1)
        self.state.retire()
        self.assertEqual(pool.statistics()["owners"], 0)

    def test_foreign_pool_refuses_without_replacing_original_owner(self):
        pool, foreign = _VerifierResourcePool(), _VerifierResourcePool()
        first = self.state.resource_owner_for(pool)
        with self.assertRaisesRegex(ValueError, "identity changed"):
            self.state.resource_owner_for(foreign)
        self.assertIs(self.state._resource_owner_handle, first)
        self.assertEqual(foreign.statistics()["owners"], 0)
        with self.assertRaisesRegex(ValueError, "poisoned"):
            self.operation.require_current()
        self.state.retire()
        self.assertEqual(pool.statistics()["owners"], 0)

    def test_retirement_during_allocation_refuses_and_retires_candidate(self):
        pool = _VerifierResourcePool()
        create = pool.create_owner

        def allocate(**kwargs):
            candidate = create(**kwargs)
            with self.assertRaisesRegex(ValueError, "pending"):
                self.state.retire()
            return candidate

        with mock.patch.object(pool, "create_owner", side_effect=allocate):
            with self.assertRaisesRegex(ValueError, "ended or poisoned"):
                self.state.resource_owner_for(pool)
        self.assertEqual(pool.statistics()["owners"], 0)

    def test_operation_context_retires_resource_owner_outside_binding_lock(self):
        pool = _VerifierResourcePool()
        self.binding.active = None
        observed = []
        retire = pool.retire

        def start(state, *_args):
            state._state, state._sealed = "LIVE", True
            state._witness = state._invocation_witness = lambda: None

        def release(*args, **kwargs):
            observed.append(self.lock_available_to_other_thread())
            return retire(*args, **kwargs)

        with (
            mock.patch.object(owner._OperationState, "start", start),
            mock.patch.object(pool, "retire", side_effect=release),
        ):
            with self.binding.operation(None, None, ()) as operation:
                owner._operation_state(operation).resource_owner_for(pool)
        self.assertEqual(observed, [True])
        self.assertIsNone(self.binding.active)
        self.assertEqual(pool.statistics()["owners"], 0)

    def test_operation_publication_lock_exit_cancellation_cleans_original_state(self):
        self.binding.active = None
        lock = self.binding.lock
        failure = KeyboardInterrupt("exact initial operation publication cancellation")
        seen = []
        binding = self.binding

        class InterruptPublication:
            fired = False

            def __enter__(self):
                lock.acquire()

            def __exit__(self, *_args):
                state = binding.active
                lock.release()
                if not self.fired and state is not None and state._state == "OPENING":
                    self.fired = True
                    seen.append(state.handle)
                    raise failure

        with mock.patch.object(self.binding, "lock", InterruptPublication()):
            with self.assertRaises(KeyboardInterrupt) as raised:
                with self.binding.operation(None, None, ()):
                    self.fail("cancelled opening cannot enter the operation")
            self.assertIs(raised.exception, failure)
        self.assertEqual(len(seen), 1)
        self.assertNotIn(seen[0], owner._OPERATIONS)
        self.assertIsNone(self.binding.active)

    def test_allocation_reservation_lock_exit_cancellation_cleans_unused_journal(self):
        pool = _VerifierResourcePool()
        lock = self.binding.lock
        state = self.state
        failure = KeyboardInterrupt("exact resource journal publication cancellation")

        class InterruptPublication:
            fired = False

            def __enter__(self):
                lock.acquire()

            def __exit__(self, *_args):
                lock.release()
                if not self.fired and state._pending_resource_owners:
                    self.fired = True
                    raise failure

        with (
            mock.patch.object(self.binding, "lock", InterruptPublication()),
            mock.patch.object(pool, "create_owner") as create,
        ):
            with self.assertRaises(KeyboardInterrupt) as raised:
                self.state.resource_owner_for(pool)
            self.assertIs(raised.exception, failure)
            create.assert_not_called()
        self.assertFalse(self.state._pending_resource_owners)
        self.assertEqual(pool.statistics()["owners"], 0)

    def test_cancellation_after_pool_allocation_return_keeps_owner_recoverable(self):
        pool = _VerifierResourcePool()
        create = pool.create_owner
        failure = KeyboardInterrupt("exact cancellation before caller receives owner")

        def allocate(**kwargs):
            create(**kwargs)
            raise failure

        with mock.patch.object(pool, "create_owner", side_effect=allocate):
            with self.assertRaises(KeyboardInterrupt) as raised:
                self.state.resource_owner_for(pool)
            self.assertIs(raised.exception, failure)
        self.assertFalse(self.state._pending_resource_owners)
        self.assertEqual(pool.statistics()["owners"], 0)

    def test_pretransition_retirement_failure_keeps_binding_journal_until_recovery(
        self,
    ):
        pool = _VerifierResourcePool()
        self.binding.active = None
        failure = MemoryError("original pool retirement failed before transition")

        def start(state, *_args):
            state._state, state._sealed = "LIVE", True
            state._witness = state._invocation_witness = lambda: None

        with (
            mock.patch.object(owner._OperationState, "start", start),
            mock.patch.object(pool, "retire", side_effect=failure),
        ):
            with self.assertRaises(MemoryError) as raised:
                with self.binding.operation(None, None, ()) as operation:
                    owner._operation_state(operation).resource_owner_for(pool)
            self.assertIs(raised.exception, failure)
        self.assertIsNotNone(self.binding.active)
        self.assertFalse(self.binding.active._retirement_complete)
        self.assertEqual(pool.statistics()["owners"], 1)
        self.binding._resume_retiring()
        self.assertIsNone(self.binding.active)
        self.assertEqual(pool.statistics()["owners"], 0)

    def test_original_body_cancellation_survives_resource_retirement_error(self):
        pool = _VerifierResourcePool()
        self.binding.active = None
        failure = KeyboardInterrupt("exact original operation cancellation")
        retire = pool.retire

        def start(state, *_args):
            state._state, state._sealed = "LIVE", True
            state._witness = state._invocation_witness = lambda: None

        def release(*args, **kwargs):
            retire(*args, **kwargs)
            raise MemoryError("secondary resource retirement failure")

        with (
            mock.patch.object(owner._OperationState, "start", start),
            mock.patch.object(pool, "retire", side_effect=release),
        ):
            with self.assertRaises(KeyboardInterrupt) as raised:
                with self.binding.operation(None, None, ()) as operation:
                    owner._operation_state(operation).resource_owner_for(pool)
                    raise failure
            self.assertIs(raised.exception, failure)
        self.assertIsNotNone(self.binding.active)
        self.binding._resume_retiring()
        self.assertIsNone(self.binding.active)
        self.assertEqual(pool.statistics()["owners"], 0)


class RuntimeInspectionStateTests(unittest.TestCase):
    def setUp(self):
        self.bound, self.binding, self.state, self.operation, self.model = controller()
        self.addCleanup(self.state.retire)

    def ticket(self):
        ticket = object.__new__(owner._InspectionTicket)
        facts = ("provider", self.model.uri, self.model.uri)
        self.state._tickets[facts[:2]] = [ticket, facts, "CAPTURING"]
        owner._TICKETS[ticket] = weakref.ref(self.state), facts
        return ticket

    def test_handles_cannot_replace_coordinated_baselines(self):
        ticket = self.ticket()
        for handle in (self.operation, ticket, self.binding.handle):
            for field in ("_state", "_receipt_values", "_prepared_identity"):
                with self.subTest(field=field), self.assertRaises(AttributeError):
                    object.__setattr__(handle, field, "forged")
        ticket.require_current()
        with self.assertRaises(ValueError):
            copy.copy(ticket).require_current()
        with self.assertRaises(ValueError):
            copy.copy(self.operation).require_current()
        self.operation.require_current()

    def test_capture_failure_is_sticky_after_caller_catches_it(self):
        ticket = self.ticket()
        self.state.report_capture(ticket, failed=True)
        for action in (
            ticket.require_current,
            self.operation.require_current,
            self.state.close,
        ):
            with self.assertRaises(ValueError):
                action()
        with self.assertRaises(ValueError):
            self.state.report_capture(ticket, failed=False)

    def test_capture_close_and_terminal_retirement(self):
        ticket = self.ticket()
        self.state.report_capture(ticket, failed=False)
        ticket.require_current()
        self.state.close()
        self.state.retire()
        with self.assertRaises(ValueError):
            ticket.require_current()
        with self.assertRaises(ValueError):
            self.operation.require_current()
        with self.assertRaises(AttributeError):
            object.__setattr__(self.operation, "_state", "LIVE")

    def test_classification_reserves_before_scan_and_retains_only_bounded_witnesses(
        self,
    ):
        ticket = self.ticket()
        acknowledgement, observation, classification = (
            canonical_identity(value).uri
            for value in ("intent", "observation", "classification")
        )
        self.state.begin_classification(ticket, acknowledgement)
        self.state.begin_scan(ticket)
        self.state.finish_scan(ticket, self.model.uri)
        self.state.finish_classification(
            ticket, acknowledgement, observation, classification
        )
        self.assertEqual(
            self.state._classifications[ticket],
            ("CLASSIFIED", acknowledgement, observation, classification),
        )
        self.state.report_capture(ticket, failed=False)
        self.state.close()
        self.state.retire()
        self.assertEqual(self.state._classifications, {})

    def test_classification_cannot_adopt_previously_scanned_capture(self):
        ticket = self.ticket()
        self.state.begin_scan(ticket)
        self.state.finish_scan(ticket, self.model.uri)
        with self.assertRaisesRegex(ValueError, "unscanned capture"):
            self.state.begin_classification(ticket, self.model.uri)
        with self.assertRaises(ValueError):
            self.operation.require_current()

    def test_unfinished_classification_withholds_successful_close(self):
        ticket = self.ticket()
        self.state.begin_classification(ticket, self.model.uri)
        self.state.begin_scan(ticket)
        self.state.finish_scan(ticket, self.model.uri)
        self.state.report_capture(ticket, failed=False)
        with self.assertRaisesRegex(ValueError, "unfinished classifications"):
            self.state.close()

    def test_repeated_classification_poison_is_sticky(self):
        ticket = self.ticket()
        self.state.begin_classification(ticket, self.model.uri)
        with self.assertRaisesRegex(ValueError, "unscanned capture"):
            self.state.begin_classification(ticket, self.model.uri)
        with self.assertRaises(ValueError):
            self.state.begin_scan(ticket)

    def test_missing_scan_refuses_classification(self):
        ticket = self.ticket()
        self.state.begin_classification(ticket, self.model.uri)
        with self.assertRaisesRegex(ValueError, "capture reservation"):
            self.state.finish_classification(
                ticket, self.model.uri, self.model.uri, self.model.uri
            )
        self.assertTrue(self.state._poisoned)

    def test_changed_acknowledgement_cannot_finish_original_reservation(self):
        ticket = self.ticket()
        self.state.begin_classification(ticket, self.model.uri)
        self.state.begin_scan(ticket)
        self.state.finish_scan(ticket, self.model.uri)
        changed = canonical_identity("different intent").uri
        with self.assertRaisesRegex(ValueError, "capture reservation"):
            self.state.finish_classification(
                ticket, changed, self.model.uri, self.model.uri
            )
        self.assertTrue(self.state._poisoned)

    def test_classification_failure_cannot_revive_after_a_completed_scan(self):
        ticket = self.ticket()
        self.state.begin_classification(ticket, self.model.uri)
        self.state.begin_scan(ticket)
        self.state.finish_scan(ticket, self.model.uri)
        self.state.fail_classification(ticket)
        self.assertEqual(
            self.state._classifications[ticket], ("FAILED", self.model.uri, None, None)
        )
        with self.assertRaises(ValueError):
            self.state.finish_classification(
                ticket, self.model.uri, self.model.uri, self.model.uri
            )

    def test_classification_refuses_nonprimitive_or_malformed_identities(self):
        ticket = self.ticket()
        with self.assertRaisesRegex(ValueError, "unscanned capture"):
            self.state.begin_classification(ticket, object())
        self.assertEqual(self.state._classifications, {})

    def test_classification_lock_exit_cancellation_withholds_close(self):
        for phase in ("begin", "finish"):
            with self.subTest(phase=phase):
                _, binding, state, operation, model = controller()
                self.addCleanup(state.retire)
                ticket = object.__new__(owner._InspectionTicket)
                facts = ("provider", model.uri, model.uri)
                state._tickets[facts[:2]] = [ticket, facts, "CAPTURING"]
                owner._TICKETS[ticket] = weakref.ref(state), facts
                if phase == "finish":
                    state.begin_classification(ticket, model.uri)
                    state.begin_scan(ticket)
                    state.finish_scan(ticket, model.uri)
                original_lock = binding.lock
                primary = KeyboardInterrupt("original classification cancellation")

                class InterruptedLock:
                    depth = 0
                    failed = False

                    def __enter__(self, mutex=original_lock):
                        mutex.acquire()
                        self.depth += 1

                    def __exit__(self, *_args, mutex=original_lock, failure=primary):
                        self.depth -= 1
                        mutex.release()
                        if not self.depth and not self.failed:
                            self.failed = True
                            raise failure

                with mock.patch.object(binding, "lock", InterruptedLock()):
                    with self.assertRaises(KeyboardInterrupt) as failure:
                        if phase == "begin":
                            state.begin_classification(ticket, model.uri)
                        else:
                            state.finish_classification(
                                ticket, model.uri, model.uri, model.uri
                            )
                self.assertIs(failure.exception, primary)
                self.assertTrue(state._poisoned)
                # Even after capture settlement, no swallowed cancellation may
                # promote an already-written CLASSIFIED record into success.
                state._tickets[facts[:2]][2] = "CLOSED"
                with self.assertRaises(ValueError):
                    operation.require_current()
                with self.assertRaises(ValueError):
                    state.close()

    def test_success_cannot_close_without_actual_invocation_or_open_capture(self):
        self.state._sealed = False
        with self.assertRaisesRegex(ValueError, "actual invocation"):
            self.state.close()
        _, _, another, _, _ = controller()
        self.addCleanup(another.retire)
        ticket = object.__new__(owner._InspectionTicket)
        another._tickets[("root", "fixture")] = [ticket, (), "CAPTURING"]
        with self.assertRaisesRegex(ValueError, "unclosed"):
            another.close()

    def test_final_witness_swallowed_reentry_withholds_success(self):
        attempted = []

        def witness():
            try:
                with self.binding.operation(None, None, ()):
                    self.fail("nested operation cannot enter")
            except ValueError:
                attempted.append(True)

        self.state._witness = witness
        with self.assertRaisesRegex(ValueError, "during final witnesses"):
            self.state.close()
        self.assertEqual(attempted, [True])

    def test_context_reserves_before_opening_callback_and_retires(self):
        self.binding.active = None
        entered = []

        def start(state, *_args):
            try:
                with self.binding.operation(None, None, ()):
                    self.fail("opening reentry cannot enter")
            except ValueError:
                entered.append(True)
            state._state, state._sealed = "LIVE", True
            state._witness = state._invocation_witness = lambda: None

        with mock.patch.object(owner._OperationState, "start", start):
            with self.assertRaisesRegex(ValueError, "poisoned"):
                with self.binding.operation(None, None, ()):
                    self.fail("swallowed opening refusal cannot recover")
        self.assertEqual(entered, [True])
        self.assertIsNone(self.binding.active)


class FiniteInspectionMetadataTests(unittest.TestCase):
    def test_original_grant_metadata_has_storage_only_checks(self):
        from datetime import UTC, datetime, timedelta, tzinfo

        from literate_ai.security.policy import BuildAuthorization, SecurityProfile

        calls = []

        class TrapZone(tzinfo):
            def utcoffset(self, _value):
                calls.append(True)
                raise AssertionError("finite witness called timezone")

        now = datetime.now(UTC)
        grant = BuildAuthorization(
            "fixture-grant",
            *("sha256:" + "a" * 64 for _ in range(3)),
            "fixture",
            "metadata observation",
            SecurityProfile.CONSTRAINED,
            ("execute-component",),
            now,
            now + timedelta(minutes=1),
        )
        # Exact datetime is opaque. Lifecycle grant owners still check time;
        # this membership witness never invokes user-supplied timezone hooks.
        stamp = now.replace(tzinfo=TrapZone())
        object.__setattr__(grant, "expires_at", stamp)
        guard = owner._finite_metadata(grant)
        with mock.patch.object(
            type(grant), "to_dict", side_effect=AssertionError("serializer called")
        ):
            guard()
            object.__setattr__(grant, "expires_at", now)
            with self.assertRaisesRegex(ValueError, "finite metadata changed"):
                guard()
        self.assertEqual(calls, [])

    def test_exact_commonjs_record_has_closed_storage_support(self):
        from literate_ai.contracts.node_sdk import CommonJSModuleDeclaration

        record = CommonJSModuleDeclaration("counter/index", "add.cjs", "index.d.ts")
        guard = owner._finite_metadata(record)
        called = []
        with mock.patch.object(
            type(record), "identity", property(lambda _: called.append(True))
        ):
            guard()
            object.__setattr__(record, "runtime", "other.cjs")
            with self.assertRaisesRegex(ValueError, "finite metadata changed"):
                guard()
        self.assertEqual(called, [])

    def test_exact_sdk_export_record_has_closed_storage_support(self):
        from literate_ai.contracts.node_sdk import NodeSDKExportDeclaration

        record = NodeSDKExportDeclaration("counter/index", "index")
        guard = owner._finite_metadata(record)
        called = []
        with mock.patch.object(
            type(record), "paths", property(lambda _: called.append(True))
        ):
            guard()
            object.__setattr__(record, "stem", "other")
            with self.assertRaisesRegex(ValueError, "finite metadata changed"):
                guard()
        self.assertEqual(called, [])

    def test_serializer_is_not_called_and_field_drift_still_refuses(self):
        value = canonical_identity("metadata")
        guard = owner._finite_metadata(value)
        called = []

        def trap(_value):
            called.append(True)
            raise AssertionError("finite guard called serializer")

        with mock.patch.object(type(value), "uri", property(trap)):
            guard()
            object.__setattr__(value, "digest", "0" * 64)
            with self.assertRaisesRegex(ValueError, "finite metadata changed"):
                guard()
        self.assertEqual(called, [])

    def test_replaced_field_descriptor_refuses_without_running_it(self):
        value = canonical_identity("metadata")
        guard = owner._finite_metadata(value)
        called = []
        with mock.patch.object(
            type(value), "digest", property(lambda _: called.append(True)), create=True
        ):
            with self.assertRaisesRegex(ValueError, "descriptor changed"):
                guard()
        self.assertEqual(called, [])

    def test_substituted_mapping_key_never_invokes_equality(self):
        called = []

        class Key(str):
            __hash__ = str.__hash__

            def __eq__(self, other):
                called.append(True)
                return str.__eq__(self, other)

        value = {"key": "original"}
        guard = owner._finite_metadata(value)
        value.clear()
        value[Key("key")] = "original"
        called.clear()
        with self.assertRaisesRegex(ValueError, "key type changed"):
            guard()
        self.assertEqual(called, [])

    def test_arbitrary_record_and_metaclass_cannot_run_field_or_key_code(self):
        @dataclasses.dataclass
        class Foreign:
            value: int

        value = Foreign(1)
        called = []
        Foreign.value = property(lambda _: called.append(True))
        with self.assertRaises(TypeError):
            owner._finite_metadata(value)

        class Meta(type):
            def __hash__(cls):
                called.append(True)
                return 1

        class ForeignMeta(metaclass=Meta):
            pass

        with self.assertRaisesRegex(TypeError, "metaclass"):
            owner._finite_metadata(ForeignMeta())
        self.assertEqual(called, [])

    def test_inherited_field_shadowing_refuses_without_property_access(self):
        # Storage-only fixture: initialization bypasses domain validation. The
        # actual runtime test separately establishes valid model ownership.
        selected = None
        for cls, spec in owner._SUPPORTED_RECORDS.items():
            inherited = next(
                (
                    (name, descriptor)
                    for name, lookup, descriptor, storage in spec[2]
                    if storage == "slot" and lookup[0][1] is owner._MISSING
                ),
                None,
            )
            if inherited is not None:
                try:
                    value = object.__new__(cls)
                except TypeError:
                    continue
                for name, _lookup, descriptor, storage in spec[2]:
                    if storage == "slot":
                        types.MemberDescriptorType.__set__(descriptor, value, None)
                    else:
                        data = types.GetSetDescriptorType.__get__(
                            spec[1][1], value, cls
                        )
                        dict.__setitem__(data, name, None)
                selected = cls, value, inherited[0]
                break
        self.assertIsNotNone(selected, "supported inherited-field control required")
        cls, value, name = selected
        guard = owner._finite_metadata(value)
        called = []
        with mock.patch.object(
            cls, name, property(lambda _: called.append(True)), create=True
        ):
            with self.assertRaisesRegex(ValueError, "descriptor changed"):
                guard()
        self.assertEqual(called, [])


@unittest.skipUnless(
    os.name == "posix"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "requires actual selected provider capture fixture",
)
class EnrolledCaptureFailureTests(unittest.TestCase):
    """Real captures with injected operation state, not original runtime binding."""

    @classmethod
    def setUpClass(cls):
        provider_fixture.NodeProviderLifecycleTests.setUpClass()

    def setUp(self):
        self.fixture = provider_fixture.NodeProviderLifecycleTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.bound, self.binding, self.state, self.operation, _ = controller(
            ports=f.ports, compiler=f.compiler
        )
        self.addCleanup(self.state.retire)
        key = f.revision.identity.uri
        self.bound.revisions = {key: f.revision}
        self.bound.configuration.provider_oracles = {key: f.oracle}
        self.state._receipts = {key: f.accepted}
        self.state._sealed = False
        self.addCleanup(self._release_state)

    def _release_state(self):
        self.bound = self.binding = self.state = self.operation = None
        gc.collect()

    @contextmanager
    def capture(self):
        f = self.fixture
        with f.ports.accepted_library_provider(
            f.accepted, require_current=f.owner
        ) as scope:
            owner.register_node_verifier_provider(
                self.operation, f.ports, scope, f.revision, f.oracle, f.compiler
            )
            with captures.capture_node_provider_verifier_inspection(
                f.ports,
                scope,
                revision=f.revision,
                oracle=f.oracle,
                compiler=f.compiler,
            ) as handle:
                ticket = captures.enroll_runtime_verifier_inspection(
                    self.operation, handle
                )
                yield handle, ticket

    def test_actual_capture_stays_capturing_through_resource_settlement(self):
        pool = captures._RESOURCE_POOL
        original = pool.settle_capture_cleanup
        observations = []

        def settle(*args, **kwargs):
            observations.append(tuple(row[2] for row in self.state._tickets.values()))
            return original(*args, **kwargs)

        with mock.patch.object(pool, "settle_capture_cleanup", side_effect=settle):
            with self.capture() as (_handle, ticket):
                ticket.require_current()
                pool_identity, lease_identity = self.state._capture_leases[ticket]
                self.assertIs(pool_identity, captures._LIVE[_handle][6][3])
                self.assertIs(lease_identity, captures._LIVE[_handle][6][4])
        self.assertEqual(observations, [("CAPTURING",)])
        self.assertEqual(
            tuple(row[2] for row in self.state._tickets.values()), ("CLOSED",)
        )
        self.assertFalse(captures._RESERVED)
        self.assertFalse(captures._PENDING_CLEANUP)

    def test_actual_detached_capture_closes_after_original_scopes_exit(self):
        pool = captures._RESOURCE_POOL
        baseline = pool.statistics()
        with self.capture() as (handle, ticket):
            ticket.require_current()
        self.assertEqual(self.state._handoffs[ticket][3], "COMMITTED")
        self.assertGreater(pool.statistics()["bytes"], baseline["bytes"])
        self.assertEqual(
            pool.statistics()["compiler_snapshots"],
            baseline["compiler_snapshots"] + 1,
        )
        # Only operation binding is injected: this is original provider capture
        # and detached observation coverage, not native invocation provenance.
        self.state._sealed = True
        with mock.patch.object(
            captures.NodeLibraryVerifierInspection,
            "require_current",
            side_effect=AssertionError("closing revived the live capture"),
        ):
            self.state.close()
        self.assertIsNone(self.state._closing_publication)
        self.state.retire()
        self.assertEqual(pool.statistics(), baseline)

    def test_three_capture_quota_model_uses_actual_sizes_and_one_original_compiler(
        self,
    ):
        # One actual provider establishes original compiler custody and measured
        # reservations. The following two leases are quota controls, not root or
        # provider enrollment/provenance: full native qualification is separate.
        pool = captures._RESOURCE_POOL
        baseline = pool.statistics()
        resize, prepare = pool.resize_capture, pool.prepare_handoff
        amounts, sizes = [], {}

        def measured_resize(lease, amount):
            amounts.append(amount)
            return resize(lease, amount)

        def measured_prepare(*args, **kwargs):
            sizes.update(kwargs)
            return prepare(*args, **kwargs)

        with (
            mock.patch.object(pool, "resize_capture", side_effect=measured_resize),
            mock.patch.object(pool, "prepare_handoff", side_effect=measured_prepare),
        ):
            with self.capture() as (_handle, ticket):
                ticket.require_current()
        self.assertTrue(amounts)
        owner_handle = self.state._resource_owner_handle
        peak = pool.statistics()["bytes"]
        try:
            for _index in range(2):
                lease = pool.reserve_capture(captures._MAX_BYTES)
                for amount in amounts:
                    try:
                        resize(lease, amount)
                    except ValueError as error:
                        raise AssertionError(
                            f"modeled capture {_index + 2}, requested {amount}, "
                            f"current {pool.statistics()['bytes']}, stages {amounts}"
                        ) from error
                    peak = max(peak, pool.statistics()["bytes"])
                prepare(lease, owner_handle, **sizes)
                peak = max(peak, pool.statistics()["bytes"])
                payload = _new_closing_payload((lambda: None,) * 4, (lambda: None,) * 3)
                pool.attach_payload(lease, payload)
                pool.commit_handoff(lease)
                pool.settle_capture_cleanup(lease, successful=True)
            self.assertEqual(
                pool.statistics()["compiler_snapshots"],
                baseline["compiler_snapshots"] + 1,
            )
            self.assertLessEqual(peak, 512 * 1024 * 1024)
        finally:
            sizes.clear()
            payload = None
            self.state.retire()
        self.assertEqual(pool.statistics(), baseline)

    def test_two_actual_operations_fit_without_cross_operation_compiler_dedup(self):
        pool = captures._RESOURCE_POOL
        baseline = pool.statistics()
        with self.capture() as (_handle, ticket):
            ticket.require_current()
        retained = pool.statistics()["bytes"]
        other = EnrolledCaptureFailureTests()
        try:
            other.setUp()
            with other.capture() as (_other_handle, other_ticket):
                other_ticket.require_current()
            self.assertEqual(
                pool.statistics()["compiler_snapshots"],
                baseline["compiler_snapshots"] + 2,
            )
            self.assertGreater(pool.statistics()["bytes"], retained)
            other.state._sealed = True
            other.state.close()
        finally:
            other.doCleanups()
        self.assertEqual(pool.statistics()["bytes"], retained)
        self.state._sealed = True
        self.state.close()
        self.state.retire()
        self.assertEqual(pool.statistics(), baseline)

    def test_prepare_cancellation_releases_journal_before_settling_charge(self):
        pool = captures._RESOURCE_POOL
        baseline = pool.statistics()
        failure = KeyboardInterrupt("original handoff preparation cancelled")
        release = captures._RELEASE_CLOSING_PAYLOAD
        observations = []

        def release_while_charged(payload):
            observations.append(pool.statistics()["bytes"] > baseline["bytes"])
            release(payload)

        with (
            mock.patch.object(
                self.state, "prepare_capture_handoff", side_effect=failure
            ),
            mock.patch.object(
                captures, "_RELEASE_CLOSING_PAYLOAD", side_effect=release_while_charged
            ),
        ):
            with self.assertRaises(KeyboardInterrupt) as caught:
                with self.capture() as (_handle, ticket):
                    ticket.require_current()
            self.assertIs(caught.exception, failure)
        self.assertEqual(observations, [True])
        self.assertFalse(captures._PENDING_CLEANUP)
        self.assertEqual(pool.statistics(), baseline)
        with self.assertRaises(ValueError):
            ticket.require_current()
        failure.__traceback__ = None

    def test_unacknowledged_commit_is_not_replayed_or_reported_closed(self):
        pool = captures._RESOURCE_POOL
        baseline = pool.statistics()
        commit = self.state.commit_capture_handoff
        failure = KeyboardInterrupt("original handoff commit acknowledgment lost")
        committed = []

        def commit_then_cancel(ticket):
            commit(ticket)
            committed.append(ticket)
            raise failure

        with mock.patch.object(
            self.state, "commit_capture_handoff", side_effect=commit_then_cancel
        ):
            with self.assertRaises(KeyboardInterrupt) as caught:
                with self.capture() as (_handle, ticket):
                    ticket.require_current()
            self.assertIs(caught.exception, failure)
        self.assertEqual(committed, [ticket])
        self.assertEqual(
            tuple(row[2] for row in self.state._tickets.values()), ("FAILED",)
        )
        self.assertFalse(captures._PENDING_CLEANUP)
        self.state.retire()
        self.assertEqual(pool.statistics(), baseline)
        failure.__traceback__ = None

    def test_failed_payload_release_keeps_charge_until_metadata_recovery(self):
        pool = captures._RESOURCE_POOL
        baseline = pool.statistics()
        failure = KeyboardInterrupt("original handoff preparation cancelled")
        release = captures._RELEASE_CLOSING_PAYLOAD
        attempts = []

        def interrupted_release(payload):
            attempts.append(pool.statistics()["bytes"])
            raise RuntimeError("observation release acknowledgment unavailable")

        with (
            mock.patch.object(
                self.state, "prepare_capture_handoff", side_effect=failure
            ),
            mock.patch.object(
                captures, "_RELEASE_CLOSING_PAYLOAD", side_effect=interrupted_release
            ),
        ):
            with self.assertRaises(KeyboardInterrupt) as caught:
                with self.capture():
                    pass
            self.assertIs(caught.exception, failure)
        self.assertEqual(len(attempts), 2)
        self.assertTrue(all(amount > baseline["bytes"] for amount in attempts))
        self.assertTrue(captures._PENDING_CLEANUP)
        self.assertGreater(pool.statistics()["bytes"], baseline["bytes"])
        with mock.patch.object(captures, "_RELEASE_CLOSING_PAYLOAD", wraps=release):
            captures._resume_ending_reservations()
        self.assertFalse(captures._PENDING_CLEANUP)
        self.assertEqual(pool.statistics(), baseline)
        failure.__traceback__ = None

    def test_actual_capture_cleanup_cancellation_poison_survives_settlement(self):
        pool = captures._RESOURCE_POOL
        original = pool.settle_capture_cleanup
        failure = KeyboardInterrupt("actual cleanup cancellation after settlement")
        calls = []

        def settle(*args, **kwargs):
            original(*args, **kwargs)
            calls.append(True)
            if len(calls) == 1:
                raise failure

        with mock.patch.object(pool, "settle_capture_cleanup", side_effect=settle):
            with self.assertRaises(KeyboardInterrupt) as raised:
                with self.capture() as (_handle, ticket):
                    ticket.require_current()
            self.assertIs(raised.exception, failure)
        self.assertEqual(len(calls), 2)
        self.assertFalse(captures._RESERVED)
        self.assertFalse(captures._PENDING_CLEANUP)
        with self.assertRaisesRegex(ValueError, "poisoned"):
            ticket.require_current()
        failure.__traceback__ = None

    def test_original_execution_and_accepted_build_metadata_preflight(self):
        # Actual provider BUILD/TEST/EXEC receipt, including its original grant.
        # No metadata substitution and no new verifier execution is performed.
        f = self.fixture
        require_original = owner._finite_metadata(f.execution, f.revision, f.accepted)
        require_original()

    def test_closed_membership_retains_no_released_tool_readset(self):
        with self.capture() as (handle, ticket):
            tools = weakref.ref(
                inspect.getclosurevars(captures._LIVE[handle][0]).nonlocals["tools"]
            )
            ticket.require_current()
        gc.collect()
        self.assertIsNone(tools())
        self.assertFalse(captures._RESERVED)
        ticket.require_current()
        with self.assertRaises(ValueError):
            handle.require_current()

    def test_swallowed_validation_failure_poison_survives_restoration(self):
        f = self.fixture
        original = f.compiler._bootstrap
        try:
            with self.assertRaises(ValueError):
                with self.capture() as (handle, ticket):
                    object.__setattr__(
                        f.compiler, "_bootstrap", original + "// changed"
                    )
                    try:
                        handle.require_current()
                    except ValueError:
                        pass
                    object.__setattr__(f.compiler, "_bootstrap", original)
                    with self.assertRaisesRegex(ValueError, "poisoned"):
                        ticket.require_current()
            with self.assertRaisesRegex(ValueError, "poisoned"):
                self.operation.require_current()
        finally:
            object.__setattr__(f.compiler, "_bootstrap", original)

    def test_body_cancellation_fails_enrollment_without_masking_error(self):
        cancelled = KeyboardInterrupt("original enrolled cancellation")
        with self.assertRaises(KeyboardInterrupt) as caught:
            with self.capture() as (_handle, ticket):
                raise cancelled
        self.assertIs(caught.exception, cancelled)
        with self.assertRaisesRegex(ValueError, "poisoned"):
            ticket.require_current()
        cancelled.__traceback__ = None

    def test_final_closing_failure_poison_is_reported(self):
        f = self.fixture
        original = f.compiler._bootstrap
        original_capture = captures.capture_loaded_node_library_verifier_inputs

        @contextmanager
        def closing_mutation(oracle):
            with original_capture(oracle) as scope:
                yield scope
            object.__setattr__(f.compiler, "_bootstrap", original + "// late change")

        try:
            with mock.patch.object(
                captures,
                "capture_loaded_node_library_verifier_inputs",
                closing_mutation,
            ):
                with self.assertRaises(ValueError):
                    with self.capture() as (_handle, ticket):
                        ticket.require_current()
            with self.assertRaisesRegex(ValueError, "poisoned"):
                ticket.require_current()
        finally:
            object.__setattr__(f.compiler, "_bootstrap", original)
