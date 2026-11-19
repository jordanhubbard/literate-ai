"""Injected state/storage controls, not original runtime or grant qualification."""

import copy
import dataclasses
import gc
import inspect
import os
import shutil
import types
import unittest
import weakref
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import node_library_verifier_inspection as captures
from literate_ai.adapters import node_sdk_verifier_runtime as owner
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
