"""Root exceptions retain truthful terminal history, without native claims.

These use the modeled lifecycle/registered-source fixture and original local
binding. No compiler or independent native observer is executed by this module.
"""

import os
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters.candidate_repair import (
    FilesystemStandardCandidateRepairAdapter,
)
from literate_ai.adapters.native_root_continuation import NativeRootContinuationError
from literate_ai.application.native_root_candidate_sequence import (
    open_native_root_candidate_sequence,
)
from literate_ai.application.native_root_continuation import (
    NativeRootController,
    current_native_root_controller,
    execute_native_root_continuation,
)
from literate_ai.application.native_root_run import (
    NativeRootRunError,
    activate_native_root_run,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_root_continuation import (
    NativeRootContinuationLedger,
    NativeRootPackageBinding,
)
from literate_ai.contracts.standard_lifecycle_membership import (
    StandardNodeFailureEvidence,
    StandardNodeFailurePhase,
)
from tests.critical import test_native_root_binding as fixture


@unittest.skipUnless(os.name == "posix", "owned POSIX protocol fixture setup")
class NativeRootControllerTerminalTests(unittest.TestCase):
    setUp = fixture.NativeRootBindingTests.setUp
    observe = fixture.NativeRootBindingTests.observe
    metadata = fixture.NativeRootBindingTests.metadata
    library_current = fixture.NativeRootBindingTests.library_current
    native_protocol = fixture.NativeRootBindingTests.native_protocol
    opened = fixture.NativeRootBindingTests.opened
    modeled_registered_candidate = (
        fixture.NativeRootBindingTests.modeled_registered_candidate
    )

    def test_post_node_storage_failure_retains_node_and_one_terminal_attempt(self):
        with self.modeled_registered_candidate() as (_output, plan, stage, _tree):
            original_node = self.modeled_node.identity_document()
            with self.opened() as (scope, owner):
                with open_native_root_candidate_sequence(
                    owner,
                    scope.run_binding,
                    project_authority_identity=(
                        scope.run_binding.project_authority_identity
                    ),
                    require_current=scope.require_current,
                ) as sequence:
                    repair = mock.Mock()
                    controller = NativeRootController(scope, repair, sequence)
                    failure = OSError("controlled package storage failure")
                    package = NativeRootPackageBinding(
                        *(canonical_identity({"modeled-package": i}) for i in range(6))
                    )

                    def pipeline(prepared):
                        controller.observe_node(
                            prepared, stage.source_generation, plan, self.modeled_node
                        )
                        controller.package_binding = package
                        raise failure

                    with self.assertRaises(OSError) as caught:
                        controller.execute(pipeline)
                    self.assertIs(caught.exception, failure)
                    ledger = sequence.ledger()
                    self.assertEqual(ledger.disposition, "terminal")
                    self.assertEqual(sequence.consumed_candidates, 1)
                    self.assertEqual(len(ledger.attempts), 1)
                    attempt = ledger.attempts[0]
                    self.assertEqual(attempt.outcome, "root-terminal")
                    self.assertEqual(attempt.retryability, "terminal")
                    self.assertEqual(attempt.final_packaged_binding, package)
                    self.assertIsNone(attempt.actual_packaged_acceptance_identity)
                    self.assertEqual(
                        attempt.node_lifecycle_result_identity,
                        self.modeled_node.identity,
                    )
                    self.assertIsNone(attempt.diagnostic_identity)
                    self.assertEqual(
                        self.modeled_node.identity_document(), original_node
                    )
                    repair.prepare_root_repair.assert_not_called()

    def test_pre_node_failure_records_no_manufactured_node_or_repair(self):
        with self.opened() as (scope, owner):
            with open_native_root_candidate_sequence(
                owner,
                scope.run_binding,
                project_authority_identity=(
                    scope.run_binding.project_authority_identity
                ),
                require_current=scope.require_current,
            ) as sequence:
                repair = mock.Mock()
                controller = NativeRootController(scope, repair, sequence)
                failure = ValueError("controlled preparation validation failure")
                with self.assertRaises(ValueError) as caught:
                    controller.execute(mock.Mock(side_effect=failure))
                self.assertIs(caught.exception, failure)
                ledger = sequence.ledger()
                self.assertIsInstance(ledger, NativeRootContinuationLedger)
                self.assertEqual(ledger.disposition, "terminal")
                self.assertEqual(sequence.consumed_candidates, 1)
                attempt = ledger.attempts[0]
                self.assertEqual(attempt.outcome, "terminal-before-node")
                self.assertIsNone(attempt.source_output_identity)
                self.assertIsNone(attempt.node_lifecycle_result_identity)
                repair.prepare_root_repair.assert_not_called()

    def test_failed_evidence_storage_preserves_original_error_and_pending_count(self):
        with self.opened() as (scope, owner):
            with open_native_root_candidate_sequence(
                owner,
                scope.run_binding,
                project_authority_identity=(
                    scope.run_binding.project_authority_identity
                ),
                require_current=scope.require_current,
            ) as sequence:
                repair = mock.Mock()
                controller = NativeRootController(scope, repair, sequence)
                failure = ValueError("controlled original failure")
                with (
                    mock.patch.object(
                        scope,
                        "retain_record",
                        side_effect=OSError("controlled evidence storage failure"),
                    ),
                    self.assertRaises(ValueError) as caught,
                ):
                    controller.execute(mock.Mock(side_effect=failure))
                self.assertIs(caught.exception, failure)
                self.assertIn(
                    "native root terminal evidence could not close",
                    failure.__notes__,
                )
                self.assertEqual(sequence.consumed_candidates, 1)
                with self.assertRaises(NativeRootRunError):
                    sequence.ledger()
                repair.prepare_root_repair.assert_not_called()

    def test_wrapper_cleanup_failure_preserves_original_terminal_error(self):
        with self.opened() as (scope, _owner):
            failure = OSError("controlled original pipeline failure")
            cleanup_failure = ValueError("controlled ordinary cleanup failure")
            repair = mock.Mock()

            def cleanup():
                raise cleanup_failure

            def pipeline(_prepared):
                controller = current_native_root_controller()
                self.assertIsNotNone(controller)
                controller.contexts.callback(cleanup)
                raise failure

            with self.assertRaises(OSError) as caught:
                execute_native_root_continuation(scope, repair, pipeline)
            self.assertIs(caught.exception, failure)
            self.assertIn(
                "native root cleanup failed after terminal refusal", failure.__notes__
            )
            self.assertIsNone(current_native_root_controller())
            repair.prepare_root_repair.assert_not_called()

    def test_wrapper_cleanup_refuses_a_controlled_body_return(self):
        # Model only a normally returning body to exercise the outer cleanup
        # boundary. The sentinel is not accepted lifecycle or native evidence.
        with self.opened() as (scope, _owner):
            cleanup_failure = OSError("controlled final cleanup failure")
            returned = object()

            def cleanup():
                raise cleanup_failure

            def body(controller, _pipeline):
                controller.contexts.callback(cleanup)
                return returned

            with (
                mock.patch.object(
                    NativeRootController, "execute", autospec=True, side_effect=body
                ),
                self.assertRaises(OSError) as caught,
            ):
                execute_native_root_continuation(scope, mock.Mock(), mock.Mock())
            self.assertIs(caught.exception, cleanup_failure)
            self.assertIsNone(current_native_root_controller())

    def test_checkpoint_failure_closes_actual_new_allocation_without_old_node(self):
        with self.modeled_registered_candidate() as (_output, plan, stage, _tree):
            failure = StandardNodeFailureEvidence(
                self.lock.root_revision,
                StandardNodeFailurePhase.TEST,
                "generated-test.failed",
                canonical_identity({"modeled-generated-test": "failed"}),
                "the generated public test failed",
            )
            failed_node = replace(
                self.modeled_node,
                failure_code=failure.code,
                failure_evidence=failure,
                test_identity=None,
                execution_identity=None,
                acceptance_identity=None,
                generated_test_evidence=None,
                execution_evidence=None,
                acceptance_evidence=None,
                source_cache_membership=None,
                source_cache_publication_identity=None,
            )
            original_node = failed_node.identity_document()
            with self.opened() as (scope, owner), activate_native_root_run(owner):
                with open_native_root_candidate_sequence(
                    owner,
                    scope.run_binding,
                    project_authority_identity=(
                        scope.run_binding.project_authority_identity
                    ),
                    require_current=scope.require_current,
                ) as sequence:
                    repair = FilesystemStandardCandidateRepairAdapter({})
                    checkpoint_failure = OSError(
                        "controlled checkpoint storage failure"
                    )
                    observations = []

                    def checkpoint():
                        observations.append(
                            (
                                controller.prepared_candidate,
                                controller.node_observation,
                                controller.package_binding,
                                controller._native,
                            )
                        )
                        raise checkpoint_failure

                    controller = NativeRootController(
                        scope, repair, sequence, start_replacement=checkpoint
                    )

                    def pipeline(prepared):
                        controller.observe_node(
                            prepared, stage.source_generation, plan, failed_node
                        )
                        return SimpleNamespace(node_results=(failed_node,))

                    with (
                        mock.patch.object(
                            repair,
                            "prepare_root_repair",
                            wraps=repair.prepare_root_repair,
                        ) as prepare,
                        self.assertRaises(OSError) as caught,
                    ):
                        controller.execute(pipeline)
                    self.assertIs(caught.exception, checkpoint_failure)
                    self.assertEqual(prepare.call_count, 1)
                    self.assertEqual(len(observations), 1)
                    replacement, node, package, native = observations[0]
                    self.assertIsNone(node)
                    self.assertIsNone(package)
                    self.assertIsNone(native)
                    self.assertNotEqual(
                        replacement.request.request.identity,
                        self.node.request.request.identity,
                    )
                    self.assertNotEqual(
                        replacement.workspace.allocation_identity,
                        self.node.workspace.allocation_identity,
                    )
                    ledger = sequence.ledger()
                    self.assertEqual(ledger.disposition, "terminal")
                    self.assertEqual(sequence.consumed_candidates, 2)
                    self.assertEqual(len(ledger.attempts), 2)
                    first, second = ledger.attempts
                    self.assertEqual(
                        first.node_lifecycle_result_identity, failed_node.identity
                    )
                    self.assertEqual(second.outcome, "terminal-before-node")
                    self.assertEqual(second.ordinal, 1)
                    self.assertEqual(
                        second.predecessor_root_attempt_identities, (first.identity,)
                    )
                    self.assertEqual(
                        second.bounded_generation_request_identity,
                        replacement.request.request.identity,
                    )
                    self.assertEqual(
                        second.workspace_allocation_identity,
                        replacement.workspace.allocation_identity,
                    )
                    self.assertIsNone(second.source_output_identity)
                    self.assertIsNone(second.node_lifecycle_result_identity)
                    self.assertIsNone(second.final_packaged_binding)
                    self.assertIsNone(second.diagnostic_identity)
                    self.assertEqual(second.retryability, "terminal")
                    self.assertEqual(failed_node.identity_document(), original_node)

    def test_currentness_failure_preserves_original_without_a_closed_ledger(self):
        with self.opened() as (scope, owner):
            with open_native_root_candidate_sequence(
                owner,
                scope.run_binding,
                project_authority_identity=scope.run_binding.project_authority_identity,
                require_current=scope.require_current,
            ) as sequence:
                repair = mock.Mock()
                controller = NativeRootController(scope, repair, sequence)
                failure = OSError("controlled original pipeline failure")
                allocated = []

                def pipeline(_prepared):
                    allocated.append(sequence.consumed_candidates)
                    owner.close()
                    raise failure

                with (
                    mock.patch.object(
                        scope, "retain_record", wraps=scope.retain_record
                    ) as retain,
                    self.assertRaises(OSError) as caught,
                ):
                    controller.execute(pipeline)
                self.assertIs(caught.exception, failure)
                self.assertEqual(allocated, [1])
                self.assertIn(
                    "native root terminal evidence could not close", failure.__notes__
                )
                retain.assert_not_called()
                with self.assertRaises(
                    (NativeRootRunError, NativeRootContinuationError)
                ):
                    sequence.ledger()
                repair.prepare_root_repair.assert_not_called()
