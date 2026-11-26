"""Finalizer composition stays strict without claiming native-controller proof.

These source controls use modeled lifecycle stages and real local owner custody.
They execute no generated/native code or configured worker action.
"""

import os
import unittest
from contextlib import contextmanager
from dataclasses import replace
from unittest import mock

from literate_ai.adapters import native_root_continuation as backend
from literate_ai.application.native_root_run import (
    NativeRootRunError,
    current_native_root_run,
    open_native_root_run,
)
from literate_ai.application.standard_project_lifecycle import (
    StandardProjectLifecycleError,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from tests.critical import test_native_root_binding as binding
from tests.critical import test_standard_project_finalizer as finalizer
from tests.support import fixtures_test_standard_project_lifecycle as fixture


class NativeRootFinalizerEligibilityTests(unittest.TestCase):
    setUp = finalizer.StandardProjectFinalizerTests.setUp
    evidence = finalizer.StandardProjectFinalizerTests.evidence
    legacy_execute = finalizer.StandardProjectFinalizerTests.execute

    def owner(self):
        return open_native_root_run(
            NativeRootRunPolicy(120, 3),
            project_identity=canonical_identity("finalizer-project"),
            framework_distribution_identity=canonical_identity("framework"),
            lifecycle_policy_identity=canonical_identity("policy"),
            require_current=lambda: None,
        )

    def selected_execute(self, owner):
        f = self.fixture

        @contextmanager
        def factory(**arguments):
            self.assertIs(arguments["original_run"], owner)
            self.assertIs(current_native_root_run(), owner)
            if self.service.project_finalizer is None:
                self.assertNotIn("project_finalizer", arguments)
            else:
                self.assertIs(
                    arguments["project_finalizer"], self.service.project_finalizer
                )
            yield None

        self.service.native_root_continuation_factory = factory
        return self.service.execute(
            f.execution,
            component_lock=f.lock,
            invalidation=fixture._decision(
                f.execution, f.names, "money", tuple(f.names.values())
            ),
            prepared_nodes=f.nodes,
            max_parallelism=2,
            live_run=owner,
            project_authority_identity=canonical_identity("approved-authority"),
        )

    @unittest.skipUnless(os.name == "posix", "owned POSIX binding fixture")
    def test_backend_excludes_finalizer_before_native_scope_capture(self):
        f = binding.NativeRootBindingTests()
        f.setUp()
        self.addCleanup(f.doCleanups)
        with (
            mock.patch.object(
                backend, "capture_loaded_rust_library_verifier_inputs"
            ) as capture,
            f.opened(project_finalizer=object()) as (scope, owner),
        ):
            self.assertIsNone(scope)
            owner.require_current()
            capture.assert_not_called()

    def test_default_finalizer_preserves_factory_kwargs_and_original_lifetime(self):
        self.service.project_finalizer = None
        expected = object()
        with self.owner() as owner:

            def pipeline(*args, **kwargs):
                self.assertIs(current_native_root_run(), owner)
                return expected

            with mock.patch.object(
                type(self.service), "_execute", side_effect=pipeline
            ):
                self.assertIs(self.selected_execute(owner), expected)
            owner.require_current()

    def test_selected_finalizer_keeps_exact_legacy_evidence_without_controller(self):
        with (
            self.owner() as owner,
            mock.patch(
                "literate_ai.application.native_root_continuation."
                "execute_native_root_continuation"
            ) as controller,
        ):
            result = self.selected_execute(owner)
            owner.require_current()
        self.assertTrue(result.successful)
        self.finalize.assert_called_once()
        self.assertEqual(
            result.root_integration, self.evidence(*self.finalize.call_args.args)
        )
        self.assertIsNone(result.native_root_execution)
        controller.assert_not_called()

    def test_selected_finalizer_retains_untyped_evidence_refusal(self):
        self.finalize.side_effect = None
        self.finalize.return_value = object()
        with self.owner() as owner:
            with self.assertRaises(StandardProjectLifecycleError) as caught:
                self.selected_execute(owner)
        self.assertEqual(
            caught.exception.code, "standard_lifecycle.finalization_invalid"
        )
        self.assertNotIn(("admit", "project"), self.ports.events)

    def test_selected_finalizer_retains_foreign_evidence_refusal(self):
        self.finalize.side_effect = lambda *args: replace(
            self.evidence(*args), execution_plan_identity=canonical_identity("foreign")
        )
        with self.owner() as owner:
            with self.assertRaises(StandardProjectLifecycleError) as caught:
                self.selected_execute(owner)
        self.assertEqual(
            caught.exception.code, "standard_lifecycle.finalization_mismatch"
        )
        self.assertNotIn(("admit", "project"), self.ports.events)

    def test_selected_finalizer_original_error_propagates_without_fallback(self):
        original = RuntimeError("original finalizer failure")
        self.finalize.side_effect = original
        with self.owner() as owner:
            with self.assertRaises(RuntimeError) as caught:
                self.selected_execute(owner)
        self.assertIs(caught.exception, original)
        self.assertNotIn(("admit", "project"), self.ports.events)

    def test_finalizer_cannot_close_original_lifetime_then_admit(self):
        with self.owner() as owner:

            def finalize(*args):
                evidence = self.evidence(*args)
                owner.close()
                return evidence

            self.finalize.side_effect = finalize
            with self.assertRaises(NativeRootRunError) as caught:
                self.selected_execute(owner)
        self.assertEqual(caught.exception.code, "native_root_run.closed")
        self.assertNotIn(("admit", "project"), self.ports.events)

    def test_active_controller_refuses_finalizer_before_delegation(self):
        baseline = self.legacy_execute()
        integration = baseline.root_integration
        self.finalize.reset_mock()
        controller = mock.Mock()
        with (
            mock.patch.object(
                self.service.artifact_assembler,
                "assemble_project_artifacts",
                return_value=(integration.artifact_graph, integration.link_plan),
            ),
            mock.patch.object(
                self.service.package_creator,
                "create_project_package",
                return_value=(integration.package_plan, integration.package_result),
            ),
            mock.patch(
                "literate_ai.application.native_root_continuation."
                "current_native_root_controller",
                return_value=controller,
            ),
        ):
            with self.assertRaises(StandardProjectLifecycleError) as caught:
                self.service._integrate_project_root(
                    self.fixture.lock,
                    self.fixture.execution,
                    baseline.project_build_plan,
                    baseline.node_results,
                )
        self.assertEqual(
            caught.exception.code,
            "standard_lifecycle.native_root_finalizer_unsupported",
        )
        self.finalize.assert_not_called()
        controller.close_accepted_root.assert_not_called()
