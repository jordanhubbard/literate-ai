"""Original issuer and provider runner; injected operation joins, no host acceptance."""

import copy
import os
import shutil
import threading
import unittest
import weakref
from contextlib import contextmanager
from dataclasses import replace
from unittest import mock

from literate_ai.adapters import node_library_verifier_inspection as captures
from literate_ai.adapters import node_sdk_verifier_authorization as owner
from literate_ai.adapters import node_sdk_verifier_runtime as runtime
from tests.smoke import test_node_sdk_verifier_issuance as issuance
from tests.smoke import test_node_sdk_verifier_runtime as state_fixture


@unittest.skipUnless(
    os.name == "posix"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "requires actual selected provider capture fixture",
)
class OriginalVerifierGrantUseTests(unittest.TestCase):
    bind = issuance.EnrolledVerifierIssuanceTests.bind
    issue = issuance.EnrolledVerifierIssuanceTests.issue

    @classmethod
    def setUpClass(cls):
        issuance.EnrolledVerifierIssuanceTests.setUpClass()

    @contextmanager
    def ready(self):
        c = self.bind()
        f = c.fixture
        # Deliberately register the injected original binding for mode-selection
        # controls. This is not qualification of the actual host constructor.
        runtime._BINDINGS[c.bound._inspection_binding] = weakref.ref(c.binding)
        self.addCleanup(runtime._BINDINGS.pop, c.bound._inspection_binding, None)
        with f.ports.accepted_library_provider(
            f.accepted, require_current=f.owner
        ) as scope:
            runtime.register_node_verifier_provider(
                c.operation, f.ports, scope, f.revision, f.oracle, f.compiler
            )
            with captures.capture_node_provider_verifier_inspection(
                f.ports,
                scope,
                revision=f.revision,
                oracle=f.oracle,
                compiler=f.compiler,
            ) as handle:
                ticket = captures.enroll_runtime_verifier_inspection(
                    c.operation, handle
                )
                grant = self.issue(handle, ticket)
                self.original_request = owner._grant_registration(c.state)[3][ticket][
                    1
                ][0]
            yield f, scope, grant

    def use(self, grant, request=None, *, ports=None, operation=None):
        return owner.require_node_verifier_authorization(
            self.c.fixture.ports if ports is None else ports,
            self.c.operation if operation is None else operation,
            grant,
            self.original_request if request is None else request,
        )

    def test_original_closed_capture_grant_and_fresh_equal_request_succeed(self):
        with self.ready() as (_f, _scope, grant):
            self.assertIsNone(self.use(grant, copy.deepcopy(self.original_request)))
            self.assertFalse(self.c.state._poisoned)

    def test_equal_copied_grant_refuses_and_poison_is_sticky(self):
        with self.ready() as (_f, _scope, grant):
            with self.assertRaisesRegex(ValueError, "exact original"):
                self.use(copy.deepcopy(grant))
            with self.assertRaises(ValueError):
                self.use(grant)
            self.assertTrue(self.c.state._poisoned)

    def test_changed_request_refuses(self):
        with self.ready() as (_f, _scope, grant):
            changed = replace(self.original_request, requested_privileges=())
            with self.assertRaisesRegex(ValueError, "closed capture"):
                self.use(grant, changed)
            self.assertTrue(self.c.state._poisoned)

    def test_callback_bearing_request_refuses_before_serialization(self):
        calls = []

        class Text(str):
            def __str__(self):
                calls.append(True)
                raise AssertionError("foreign request field invoked")

        with self.ready() as (_f, _scope, grant):
            changed = copy.deepcopy(self.original_request)
            object.__setattr__(
                changed,
                "source_bundle_digest",
                Text(self.original_request.source_bundle_digest),
            )
            with self.assertRaisesRegex(TypeError, "unsupported finite"):
                self.use(grant, changed)
            self.assertFalse(calls)
            self.assertTrue(self.c.state._poisoned)

    def test_foreign_ports_refuse(self):
        with self.ready() as (_f, _scope, grant):
            with self.assertRaisesRegex(ValueError, "another runtime"):
                self.use(grant, ports=object())
            self.assertTrue(self.c.state._poisoned)

    def test_foreign_operation_refuses_without_poisoning_original(self):
        with self.ready() as (_f, _scope, grant):
            with self.assertRaises(TypeError):
                self.use(grant, operation=object())
            self.assertFalse(self.c.state._poisoned)

    def test_issuing_capture_cannot_execute_before_successful_settlement(self):
        c = self.bind()
        with self.assertRaisesRegex(ValueError, "closed capture"):
            with c.capture() as (handle, ticket):
                grant = self.issue(handle, ticket)
                request = owner._grant_registration(c.state)[3][ticket][1][0]
                self.use(grant, request)
        self.assertTrue(c.state._poisoned)

    def test_missing_explicit_operation_cannot_select_manual_execution(self):
        with self.ready() as (f, _scope, grant):
            with self.assertRaisesRegex(ValueError, "explicitly threaded"):
                runtime.require_node_verifier_grant_use(
                    f.ports, None, grant, self.original_request
                )
            self.assertTrue(self.c.state._poisoned)

    def test_cleared_intent_cannot_select_manual_execution(self):
        with self.ready() as (f, _scope, grant):
            self.c.state._grant_intent = None
            with self.assertRaisesRegex(ValueError, "explicitly threaded"):
                runtime.require_node_verifier_grant_use(
                    f.ports, None, grant, self.original_request
                )
            self.assertTrue(self.c.state._poisoned)

    def _missing_operation_with_changed_host_pointer(self, replacement):
        with self.ready() as (f, scope, grant):
            f.processes.clear()
            f.ports._node_sdk_host_binding = replacement
            with self.assertRaisesRegex(ValueError, "explicitly threaded"):
                f.run_join(
                    scope,
                    lambda *_: self.fail("missing operation reached consumer"),
                    authorization=grant,
                )
            self.assertTrue(self.c.state._poisoned)
            self.assertFalse(f.processes)

    def test_cleared_host_pointer_cannot_select_manual_execution(self):
        self._missing_operation_with_changed_host_pointer(None)

    def test_replaced_host_pointer_cannot_select_manual_execution(self):
        self._missing_operation_with_changed_host_pointer(object())

    def test_retiring_marker_preserves_unrelated_manual_execution(self):
        with self.ready() as (f, _scope, grant):
            # Reproduce retirement's interval after live lookup is removed but
            # before original grant membership and DTO witnesses are drained.
            reference = runtime._OPERATIONS.pop(self.c.operation)
            try:
                unrelated = issuance.fixture.WeakNamespace(_node_sdk_host_binding=None)
                self.assertIsNone(
                    runtime.require_node_verifier_grant_use(
                        unrelated, None, grant, self.original_request
                    )
                )
                with self.assertRaisesRegex(ValueError, "explicitly threaded"):
                    runtime.require_node_verifier_grant_use(
                        f.ports, None, grant, self.original_request
                    )
                self.assertTrue(self.c.state._poisoned)
            finally:
                runtime._OPERATIONS[self.c.operation] = reference

    def test_untyped_operation_refuses_before_substituted_authorization_lookup(self):
        _bound, _binding, state, operation, _ = state_fixture.controller()
        self.addCleanup(state.retire)
        with mock.patch.object(
            owner, "require_node_verifier_authorization"
        ) as substitute:
            with self.assertRaisesRegex(ValueError, "typed grant membership"):
                runtime.require_node_verifier_grant_use(
                    _binding.originals[2], operation, object(), object()
                )
            substitute.assert_not_called()
        self.assertTrue(state._poisoned)

    def test_concurrent_marker_publication_and_retirement_preserve_manual_ports(self):
        with self.ready() as (f, _scope, grant):
            unrelated = issuance.fixture.WeakNamespace(_node_sdk_host_binding=None)
            started, finish, failures, published = (
                threading.Event(),
                threading.Event(),
                [],
                [],
            )

            def mutate():
                started.set()
                try:
                    for _ in range(100):
                        _bound, _binding, state, _operation, identity = (
                            state_fixture.controller(
                                ports=issuance.fixture.WeakNamespace()
                            )
                        )
                        try:
                            owner._grant_registration(
                                state, self.ack, identity.uri, create=True
                            )
                            published.append(True)
                        finally:
                            state.retire()
                except BaseException as error:
                    failures.append(error)
                finally:
                    finish.set()

            writer = threading.Thread(target=mutate)
            writer.start()
            self.assertTrue(started.wait(timeout=5))
            try:
                for _ in range(1000):
                    self.assertIsNone(
                        runtime.require_node_verifier_grant_use(
                            unrelated, None, grant, self.original_request
                        )
                    )
                with self.assertRaisesRegex(ValueError, "explicitly threaded"):
                    runtime.require_node_verifier_grant_use(
                        f.ports, None, grant, self.original_request
                    )
            finally:
                writer.join(timeout=10)
            self.assertFalse(writer.is_alive())
            self.assertTrue(finish.is_set())
            self.assertFalse(failures, failures)
            self.assertEqual(len(published), 100)

    def _substituted_guard_cannot_start_tools(
        self, *, authorization_guard, during_owner
    ):
        with self.ready() as (f, scope, grant):
            module, name = (
                (owner, "require_node_verifier_authorization")
                if authorization_guard
                else (runtime, "require_node_verifier_grant_use")
            )
            calls, changes = [], []
            f.processes.clear()

            def replacement(*_args):
                calls.append(True)

            patcher = mock.patch.object(module, name, replacement)

            def changed_owner():
                if not changes:
                    changes.append(True)
                    patcher.start()

            try:
                if not during_owner:
                    patcher.start()
                with self.assertRaisesRegex(ValueError, "fixed SDK verifier"):
                    f.run_join(
                        scope,
                        lambda *_: self.fail("substituted guard reached consumer"),
                        authorization=grant,
                        verifier_operation=self.c.operation,
                        **({"require_current": changed_owner} if during_owner else {}),
                    )
            finally:
                patcher.stop()
            self.assertFalse(calls)
            self.assertFalse(f.processes)
            if during_owner:
                self.assertTrue(self.c.state._poisoned)
                self.assertEqual(changes, [True])

    def test_substituted_selector_before_runner_entry_is_not_invoked(self):
        self._substituted_guard_cannot_start_tools(
            authorization_guard=False, during_owner=False
        )

    def test_substituted_authorization_before_runner_entry_is_not_invoked(self):
        self._substituted_guard_cannot_start_tools(
            authorization_guard=True, during_owner=False
        )

    def test_substituted_selector_during_custody_is_not_invoked(self):
        self._substituted_guard_cannot_start_tools(
            authorization_guard=False, during_owner=True
        )

    def test_substituted_authorization_during_custody_is_not_invoked(self):
        self._substituted_guard_cannot_start_tools(
            authorization_guard=True, during_owner=True
        )

    def test_retired_operation_refuses_original_grant(self):
        with self.ready() as (_f, _scope, grant):
            self.c.state._sealed = True
            self.c.state.close()
            self.c.state.retire()
            with self.assertRaisesRegex(ValueError, "ended"):
                self.use(grant)

    def test_actual_provider_tools_require_exact_grant_and_explicit_operation(self):
        with self.ready() as (f, scope, grant):
            calls = []

            def consume(checks, require_live):
                require_live()
                calls.append(checks.identity)
                return "original grant runner completed"

            self.assertEqual(
                f.run_join(
                    scope,
                    consume,
                    authorization=grant,
                    verifier_operation=self.c.operation,
                ),
                "original grant runner completed",
            )
            self.assertEqual(len(calls), 1)
            self.assertTrue(f.processes)

    def test_copied_grant_cannot_start_actual_provider_tools(self):
        with self.ready() as (f, scope, grant):
            f.processes.clear()
            with self.assertRaisesRegex(ValueError, "exact original"):
                f.run_join(
                    scope,
                    lambda *_: self.fail("copied grant reached consumer"),
                    authorization=copy.deepcopy(grant),
                    verifier_operation=self.c.operation,
                )
            self.assertFalse(f.processes)

    def test_final_clock_poison_withholds_actual_provider_result(self):
        with self.ready() as (f, scope, grant):
            original_clock = f.ports.clock
            completed = []

            def clock():
                if completed:
                    self.c.state._poisoned = True
                return original_clock()

            def consume(_checks, _live):
                completed.append(True)
                return "must not escape"

            with mock.patch.object(f.ports, "clock", clock):
                with self.assertRaisesRegex(ValueError, "poisoned"):
                    f.run_join(
                        scope,
                        consume,
                        authorization=grant,
                        verifier_operation=self.c.operation,
                    )
            self.assertTrue(completed)
