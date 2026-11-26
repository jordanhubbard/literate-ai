"""Adapter custody checks with modeled stage registration and real local pins.

The independent observer is controlled here. These tests establish neither
native execution nor packaged acceptance or release qualification.
"""

import os
import unittest
from contextlib import ExitStack, contextmanager
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters.lifecycle.standard_local import LocalStandardLifecycleError
from literate_ai.application import native_root_continuation as application
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_root_continuation import NativeRootPackageBinding
from tests.critical import test_native_root_binding as binding_fixture


@unittest.skipUnless(os.name == "posix", "uses the owned POSIX protocol fixture")
class NativeRootAdapterCustodyTests(unittest.TestCase):
    setUp = binding_fixture.NativeRootBindingTests.setUp
    observe = binding_fixture.NativeRootBindingTests.observe
    metadata = binding_fixture.NativeRootBindingTests.metadata
    library_current = binding_fixture.NativeRootBindingTests.library_current
    native_protocol = binding_fixture.NativeRootBindingTests.native_protocol
    opened = binding_fixture.NativeRootBindingTests.opened
    modeled_registered_candidate = (
        binding_fixture.NativeRootBindingTests.modeled_registered_candidate
    )

    @contextmanager
    def late_controller(self):
        with self.modeled_registered_candidate() as (_output, plan, stage, _tree):
            with self.opened() as (scope, _run), ExitStack() as contexts:
                package = NativeRootPackageBinding(
                    *(canonical_identity({"actual-model-package": i}) for i in range(6))
                )
                controller = SimpleNamespace(
                    scope=scope,
                    contexts=contexts,
                    prepared_candidate=self.node,
                    node_observation=(
                        stage.source_generation,
                        plan,
                        self.modeled_node,
                    ),
                    package_binding=package,
                    require_current=scope.require_current,
                )
                package_plan = SimpleNamespace(
                    artifact_graph_identity=package.artifact_graph_identity,
                    link_plan_identity=package.link_plan_identity,
                    identity=package.package_plan_identity,
                )
                arguments = (
                    self.lock,
                    SimpleNamespace(root_plan=plan),
                    package_plan,
                    SimpleNamespace(identity=package.package_result_identity),
                    self.fixture.oracle,
                    package.root_generated_test_identity,
                    package.packaged_execution_identity,
                )
                token = application._ACTIVE.set(controller)
                try:
                    yield controller, arguments
                finally:
                    application._ACTIVE.reset(token)

    def replace_package_result(self, controller):
        object.__setattr__(
            controller.package_binding,
            "package_result_identity",
            canonical_identity({"foreign": "same-object-package-result"}),
        )

    def test_active_owner_mismatch_refuses_before_legacy_acceptance(self):
        with self.late_controller() as (controller, arguments):
            controller.scope = SimpleNamespace(
                ports=object(), run_binding=controller.scope.run_binding
            )
            with (
                mock.patch.object(self.ports, "_accept_library_observed") as observed,
                self.assertRaises(LocalStandardLifecycleError),
            ):
                self.ports._accept_library(*arguments)
            observed.assert_not_called()

    def test_admission_callback_cannot_reseal_changed_package_before_observation(self):
        with self.late_controller() as (controller, arguments):
            current = controller.require_current

            def changed():
                current()
                self.replace_package_result(controller)

            controller.require_current = changed
            with (
                mock.patch.object(self.ports, "_accept_library_observed") as observed,
                self.assertRaises(LocalStandardLifecycleError),
            ):
                self.ports._accept_library(*arguments)
            observed.assert_not_called()

    def test_same_object_package_change_after_observation_prevents_return(self):
        with self.late_controller() as (controller, arguments):

            def observed(*_args, **_kwargs):
                self.replace_package_result(controller)
                return canonical_identity({"controlled": "observed"})

            with (
                mock.patch.object(
                    self.ports, "_accept_library_observed", side_effect=observed
                ),
                self.assertRaises(LocalStandardLifecycleError),
            ):
                self.ports._accept_library(*arguments)

    def test_final_currentness_callback_cannot_change_package_before_return(self):
        with self.late_controller() as (controller, arguments):
            current = controller.require_current
            calls = []

            def changed():
                current()
                calls.append(True)
                if len(calls) == 2:
                    self.replace_package_result(controller)

            controller.require_current = changed
            with (
                mock.patch.object(
                    self.ports,
                    "_accept_library_observed",
                    return_value=canonical_identity({"controlled": "observed"}),
                ) as observed,
                self.assertRaises(LocalStandardLifecycleError),
            ):
                self.ports._accept_library(*arguments)
            observed.assert_called_once()
            self.assertEqual(len(calls), 2)

    def test_matching_return_retains_context_until_original_owner_closes(
        self,
    ):
        with self.late_controller() as (controller, arguments):
            closed = []
            identity = canonical_identity({"controlled": "matching-observation"})

            def observed(*args, **kwargs):
                self.assertIs(args[7], controller.contexts)
                self.assertIs(kwargs["_native_root_controller"], controller)
                controller.contexts.callback(closed.append, True)
                return identity

            with mock.patch.object(
                self.ports, "_accept_library_observed", side_effect=observed
            ):
                self.assertEqual(self.ports._accept_library(*arguments), identity)
            self.assertEqual(closed, [])
            controller.contexts.close()
            self.assertEqual(closed, [True])

    def test_rejection_signal_retains_context_until_original_owner_closes(
        self,
    ):
        with self.late_controller() as (controller, arguments):
            closed = []
            identity = canonical_identity({"controlled": "wrong-value-observation"})
            rejection = application.NativeRootPackageRejected(controller, identity)

            def observed(*_args, **_kwargs):
                controller.contexts.callback(closed.append, True)
                raise rejection

            with mock.patch.object(
                self.ports, "_accept_library_observed", side_effect=observed
            ):
                with self.assertRaises(application.NativeRootPackageRejected) as caught:
                    self.ports._accept_library(*arguments)
            self.assertIs(caught.exception, rejection)
            self.assertEqual(closed, [])
            controller.contexts.close()
            self.assertEqual(closed, [True])
