"""Actual preparation retention with modeled lifecycle observations only.

Local CAS/recorder writes and fresh repair allocation are real. No generated
process, compiler, installed framework or independent native acceptance runs.
"""

import os
import unittest
from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters.candidate_repair import (
    FilesystemStandardCandidateRepairAdapter,
)
from literate_ai.adapters.native_root_continuation import NativeRootContinuationError
from literate_ai.adapters.qualification_capture import QualificationEvidenceRecorder
from literate_ai.application.native_root_candidate_sequence import (
    open_native_root_candidate_sequence,
)
from literate_ai.application.native_root_continuation import NativeRootController
from literate_ai.application.native_root_run import (
    NativeRootRunError,
    activate_native_root_run,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.executable_components.context import (
    BoundedComponentGenerationRequest,
)
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.standard_lifecycle_membership import (
    StandardNodeFailureEvidence,
    StandardNodeFailurePhase,
)
from tests.critical import test_native_root_binding as fixture


@unittest.skipUnless(os.name == "posix", "owned POSIX protocol fixture setup")
class NativeRootPreparationRetentionTests(unittest.TestCase):
    setUp = fixture.NativeRootBindingTests.setUp
    observe = fixture.NativeRootBindingTests.observe
    metadata = fixture.NativeRootBindingTests.metadata
    library_current = fixture.NativeRootBindingTests.library_current
    native_protocol = fixture.NativeRootBindingTests.native_protocol
    opened = fixture.NativeRootBindingTests.opened
    modeled_registered_candidate = (
        fixture.NativeRootBindingTests.modeled_registered_candidate
    )

    @contextmanager
    def controller(self, *, repair=None, checkpoint=None):
        self.recorder = QualificationEvidenceRecorder(
            max_bytes=16 * 1024**2, max_records=2000
        )
        self.ports._evidence_recorder = self.recorder
        with self.opened() as (scope, owner), activate_native_root_run(owner):
            with open_native_root_candidate_sequence(
                owner,
                scope.run_binding,
                project_authority_identity=scope.run_binding.project_authority_identity,
                require_current=scope.require_current,
            ) as sequence:
                yield (
                    scope,
                    sequence,
                    NativeRootController(
                        scope,
                        repair if repair is not None else mock.Mock(),
                        sequence,
                        start_replacement=checkpoint,
                    ),
                )

    def preparation_records(self, prepared):
        workspace = prepared.workspace
        allocation = {
            "schema": "literate-ai/component-workspace-allocation@1",
            "component_revision": prepared.plan.component_revision.uri,
            "generation_plan_identity": prepared.plan.identity.uri,
            "locator": workspace.locator,
        }
        descriptor = {
            "schema": "literate-ai/component-generation-workspace@1",
            "component_revision": workspace.component_revision.uri,
            "generation_plan_identity": workspace.generation_plan_identity.uri,
            "generation_key_identity": workspace.generation_key_identity.uri,
            "allocation_identity": workspace.allocation_identity.uri,
            "locator": workspace.locator,
            "workspace": workspace.workspace.value,
        }
        return (
            (prepared.request.request.identity, prepared.request.request.to_dict()),
            (workspace.allocation_identity, allocation),
            (workspace.identity, descriptor),
        )

    def assert_preparation_retained(self, scope, prepared):
        retained = dict(self.recorder.entries)
        for identity, document in self.preparation_records(prepared):
            payload = canonical_json_bytes(document)
            self.assertEqual(canonical_identity(document), identity)
            self.assertEqual(retained[identity], payload)
            self.assertEqual(
                scope._evidence.get_bytes(BlobRef(identity.digest, len(payload))),
                payload,
            )
        request = prepared.request.request
        self.assertEqual(
            BoundedComponentGenerationRequest.from_dict(request.to_dict()),
            request,
        )
        # The records contain public context identities/bounds, never prompt bytes.
        self.assertNotIn("prompt", request.to_dict())
        payloads = b"".join(
            retained[identity] for identity, _ in self.preparation_records(prepared)
        )
        self.assertNotIn(prepared.request.prompt, payloads)

    def test_original_records_are_retained_before_pipeline_with_exact_ids(self):
        with self.controller() as (scope, sequence, controller):
            failure = OSError("controlled original pipeline stop")

            def pipeline(prepared):
                self.assert_preparation_retained(scope, prepared)
                self.assertEqual(sequence.consumed_candidates, 1)
                raise failure

            with self.assertRaises(OSError) as raised:
                controller.execute(pipeline)
            self.assertIs(raised.exception, failure)
            ledger = sequence.ledger()
            self.assertEqual(ledger.disposition, "terminal")
            self.assertEqual(len(ledger.attempts), 1)
            self.assertEqual(ledger.attempts[0].outcome, "terminal-before-node")
            self.assertEqual(
                ledger.attempts[0].workspace_allocation_identity,
                self.node.workspace.allocation_identity,
            )

    def test_replacement_records_and_root_request_exist_before_checkpoint(self):
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
            checkpoint_failure = OSError("controlled post-retention checkpoint stop")
            observed = []

            def checkpoint():
                replacement = controller.prepared_candidate
                self.assert_preparation_retained(scope, self.node)
                self.assert_preparation_retained(scope, replacement)
                self.assertIn(
                    controller._incoming.identity, dict(self.recorder.entries)
                )
                observed.append(replacement)
                raise checkpoint_failure

            repair = FilesystemStandardCandidateRepairAdapter({})
            with self.controller(repair=repair, checkpoint=checkpoint) as (
                scope,
                sequence,
                controller,
            ):

                def pipeline(prepared):
                    controller.observe_node(
                        prepared, stage.source_generation, plan, failed_node
                    )
                    return SimpleNamespace(node_results=(failed_node,))

                with self.assertRaises(OSError) as raised:
                    controller.execute(pipeline)
                self.assertIs(raised.exception, checkpoint_failure)
                self.assertEqual(len(observed), 1)
                replacement = observed[0]
                self.assertNotEqual(
                    replacement.request.request.identity,
                    self.node.request.request.identity,
                )
                self.assertNotEqual(
                    replacement.workspace.allocation_identity,
                    self.node.workspace.allocation_identity,
                )
                ledger = sequence.ledger()
                self.assertEqual(sequence.consumed_candidates, 2)
                self.assertEqual(len(ledger.attempts), 2)
                self.assertEqual(ledger.attempts[1].outcome, "terminal-before-node")
                self.assertIsNone(ledger.attempts[1].node_lifecycle_result_identity)
                self.assertEqual(failed_node.identity_document(), original_node)

    def test_tampered_allocation_preimage_refuses_without_inventing_record(self):
        self.node = replace(
            self.node,
            workspace=replace(
                self.node.workspace,
                allocation_identity=canonical_identity({"tampered-allocation": True}),
            ),
        )
        with self.controller() as (_scope, sequence, controller):
            pipeline = mock.Mock()
            with self.assertRaisesRegex(ValueError, "allocation preimage differs"):
                controller.execute(pipeline)
            pipeline.assert_not_called()
            ledger = sequence.ledger()
            self.assertEqual(sequence.consumed_candidates, 1)
            self.assertEqual(ledger.disposition, "terminal")
            self.assertEqual(ledger.attempts[0].outcome, "terminal-before-node")
            self.assertNotIn(
                self.node.workspace.allocation_identity, dict(self.recorder.entries)
            )

    def test_retention_error_preserves_original_error_and_allocated_terminal_count(
        self,
    ):
        for failed_record in range(3):
            with (
                self.subTest(failed_record=failed_record),
                self.controller() as (
                    scope,
                    sequence,
                    controller,
                ),
            ):
                target, _ = self.preparation_records(self.node)[failed_record]
                original = scope.retain_record
                failure = OSError("controlled preparation record write failure")

                def retain(record, target=target, failure=failure, original=original):
                    document = (
                        record.to_dict() if hasattr(record, "to_dict") else record
                    )
                    if canonical_identity(document) == target:
                        raise failure
                    return original(record)

                pipeline = mock.Mock()
                with (
                    mock.patch.object(scope, "retain_record", side_effect=retain),
                    self.assertRaises(OSError) as raised,
                ):
                    controller.execute(pipeline)
                self.assertIs(raised.exception, failure)
                pipeline.assert_not_called()
                self.assertEqual(sequence.consumed_candidates, 1)
                ledger = sequence.ledger()
                self.assertEqual(ledger.disposition, "terminal")
                self.assertEqual(len(ledger.attempts), 1)
                self.assertIsNone(ledger.attempts[0].node_lifecycle_result_identity)

    def test_closed_owner_during_retention_preserves_error_and_pending_allocation(self):
        with self.controller() as (scope, sequence, controller):
            failure = OSError("controlled retention custody loss")

            def retain(_record):
                scope.close()
                raise failure

            pipeline = mock.Mock()
            with (
                mock.patch.object(scope, "retain_record", side_effect=retain),
                self.assertRaises(OSError) as raised,
            ):
                controller.execute(pipeline)
            self.assertIs(raised.exception, failure)
            pipeline.assert_not_called()
            self.assertIsNotNone(sequence._pending)
            self.assertEqual(sequence._attempts, ())
            self.assertIn(
                "native root terminal evidence could not close", failure.__notes__
            )
            with self.assertRaises((NativeRootRunError, NativeRootContinuationError)):
                sequence.ledger()
