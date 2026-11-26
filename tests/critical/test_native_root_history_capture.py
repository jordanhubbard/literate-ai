"""Real local source-CAS traversal through explicitly modeled closed history.

Generation uses the deterministic source-provider fixture. Lifecycle/audit/node
history is modeled data, not native observation, policy admission or replay proof.
"""

import hashlib
import unittest
from dataclasses import replace
from unittest import mock

from literate_ai.adapters.generation_preparation import (
    FilesystemComponentWorkspaceAllocator,
    LockedComponentNodePreparationAdapter,
)
from literate_ai.adapters.native_root_capture import capture_native_root_source_history
from literate_ai.adapters.qualification_capture import (
    QualificationCaptureError,
    QualificationEvidenceRecorder,
)
from literate_ai.adapters.source_generation import CodingCliSourceGenerationInvocation
from literate_ai.application import (
    GenerationExecutionPlan,
    prepare_component_generation_nodes,
)
from literate_ai.contracts import ContentIdentity, SourceGenerationDisposition
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.executable_components import SourceGenerationNodeResult
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_root_continuation import (
    NativeRootAcceptanceClosure,
    NativeRootCandidateAttempt,
    NativeRootContinuationLedger,
    NativeRootExecutionResult,
    NativeRootPackageBinding,
    NativeRootRepairRequest,
)
from tests.critical import test_native_root_continuation_contracts as closed_fixture
from tests.support import fixtures_test_application_generation as execution_fixture
from tests.support import (
    fixtures_test_cached_coding_cli_source_generation_runner as source_fixture,
)
from tests.support import (
    fixtures_test_component_node_generation_preparation as preparation_fixture,
)
from tests.support import (
    fixtures_test_qualification_lifecycle_runner as lifecycle_fixture,
)


class NativeRootHistoryCaptureTests(unittest.TestCase):
    def setUp(self):
        self.source = f = source_fixture.CachedCodingCliSourceGenerationRunnerTests()
        f.setUp()
        self.addCleanup(f.tearDown)
        _, execution = preparation_fixture._fixture()
        adapter = LockedComponentNodePreparationAdapter()
        parent = f.root / "history-workspaces"
        parent.mkdir()
        prepared = prepare_component_generation_nodes(
            execution,
            authority=f.snapshot,
            authority_lock_identity=adapter.authority_lock_identity,
            authority_guard=adapter.guard,
            node_projector=adapter.project,
            workspace_allocator=FilesystemComponentWorkspaceAllocator(parent).allocate,
            framework_envelope=lambda projection: projection.recipe.prompt().encode(),
            budget=preparation_fixture._budget(),
        )
        f.node = next(
            node
            for node in prepared
            if node.plan.component_revision == execution.root_revision
        )
        routes = execution_fixture.router()
        stages = execution_fixture.stages()
        f.execution_plan = GenerationExecutionPlan(
            f.node.definition.workflow_definition,
            f.node.definition.routing_policy,
            stages,
            tuple(routes.select(stage.policy) for stage in stages),
        )
        f.invocation = CodingCliSourceGenerationInvocation.create(
            f.execution_plan,
            f.stage_request,
            application_root_revision_identity=execution.root_revision,
            readiness_identity=f.readiness,
        )
        self.original = f.node
        first = f.runner(f.node)
        fresh = f._fresh_node()
        prompt = fresh.request.prompt + b"\ncomplete fresh modeled replacement\n"
        request = replace(
            fresh.request.request,
            prompt_identity=ContentIdentity.parse_uri(
                "sha256:" + hashlib.sha256(prompt).hexdigest()
            ),
        )
        self.replacement = replace(
            fresh, request=replace(fresh.request, request=request, prompt=prompt)
        )
        # This deterministic delegate has one cached slot for its cache tests.
        # A changed bounded request here needs its own actual delegate result.
        f.generator._cached = None
        second = f.runner(self.replacement)
        self.assertEqual(f.generator.delegate_calls, 2)
        self.outputs = (first, second)
        self.lifecycle = lifecycle_fixture._lifecycle("capture-history")
        records = closed_fixture.NativeRootContinuationContractTests()
        records.setUp()
        self.run = replace(
            records.run,
            root_revision=first.candidate.component_revision,
            component_lock_identity=first.provenance.component_lock_identity,
            execution_plan_identity=self.lifecycle.execution_plan_identity,
            original_recipe_identity=first.candidate.recipe_identity,
            original_generation_plan_identity=first.candidate.component_generation_plan_identity,
            original_bounded_request_identity=first.candidate.source_generation_request_identity,
        )
        self.recorder = QualificationEvidenceRecorder(
            max_bytes=32 * 1024**2, max_records=2000
        )
        self.documents = tuple(
            self.node_document(node, output)
            for node, output in zip(
                (self.original, self.replacement), self.outputs, strict=True
            )
        )
        self.seal_history()

    def node_document(self, prepared, output):
        request, candidate = prepared.request.request, output.candidate
        generation = SourceGenerationNodeResult(
            candidate.component_revision,
            candidate.component_generation_plan_identity,
            candidate.generation_key_identity,
            candidate.context_manifest_identity,
            request.budget.identity,
            request.complexity_decision_identity,
            candidate.prompt_identity,
            candidate.recipe_identity,
            candidate.workspace_allocation_identity,
            SourceGenerationDisposition.GENERATED,
            output.candidate_identity,
            output.provenance_identity,
            output.runtime_observation,
            None,
        )
        return {
            "schema": "literate-ai/standard-node-lifecycle-result@4",
            "component_revision": self.run.root_revision.uri,
            "source_output": output.to_dict(),
            "source_generation": generation.to_dict(),
            "modeled_label": "original node record remains unchanged",
        }

    def seal_history(self):
        run = self.run
        nodes = tuple(
            self.recorder.remember_json(document) for document in self.documents
        )
        first, second = self.outputs
        failure, diagnostic = (
            canonical_identity("modeled failure"),
            canonical_identity("modeled diagnostic"),
        )
        original = NativeRootCandidateAttempt(
            run.identity,
            0,
            (),
            "initial",
            None,
            first.candidate.source_generation_request_identity,
            first.candidate.workspace_allocation_identity,
            first.identity,
            nodes[0],
            None,
            None,
            "node-rejected",
            failure,
            diagnostic,
            "retryable",
            None,
            None,
        )
        repair = NativeRootRepairRequest(
            run.identity,
            1,
            run.original_recipe_identity,
            (original.identity,),
            diagnostic,
            None,
            second.candidate.source_generation_request_identity,
            second.candidate.workspace_allocation_identity,
            "node-build-test",
            failure,
        )
        package = NativeRootPackageBinding(
            *(canonical_identity({"modeled package": i}) for i in range(6))
        )
        acceptance = canonical_identity("modeled actual acceptance pointer")
        accepted = NativeRootCandidateAttempt(
            run.identity,
            1,
            (original.identity,),
            "native-root-repair",
            repair.identity,
            second.candidate.source_generation_request_identity,
            second.candidate.workspace_allocation_identity,
            second.identity,
            nodes[1],
            None,
            None,
            "root-accepted",
            None,
            None,
            "none",
            acceptance,
            package,
        )
        ledger = NativeRootContinuationLedger(
            run.identity, (original, accepted), (), "accepted", None
        )
        closure = NativeRootAcceptanceClosure(
            run.identity,
            ledger.identity,
            acceptance,
            second.identity,
            package.package_plan_identity,
            package.package_result_identity,
        )
        audit = NativeRootExecutionResult(
            run.identity,
            ledger.identity,
            self.lifecycle.identity,
            closure.identity,
            "accepted",
        )
        for record in (
            run,
            original,
            accepted,
            repair,
            ledger,
            closure,
            audit,
            *self.outputs,
        ):
            self.recorder.remember_json(record.to_dict())
        object.__setattr__(self.lifecycle, "native_root_execution", audit)
        self.ledger, self.audit = ledger, audit

    def capture(self):
        return capture_native_root_source_history(
            self.lifecycle, self.recorder, cas=self.source.cas
        )

    def test_both_rejected_and_accepted_sources_traverse_original_cas_without_relabel(
        self,
    ):
        before = dict(self.recorder.entries)
        labels = tuple(document.copy() for document in self.documents)
        self.assertNotIn(self.outputs[0].candidate.source_manifest_identity, before)
        self.assertEqual(
            self.capture(), tuple(output.identity for output in self.outputs)
        )
        after = dict(self.recorder.entries)
        for output in self.outputs:
            self.assertIn(output.candidate.source_manifest_identity, after)
            self.assertIn(output.candidate.source_bundle_identity, after)
        for identity, content in before.items():
            self.assertEqual(after[identity], content)
        self.assertEqual(self.documents, labels)
        self.assertIs(self.lifecycle.native_root_execution, self.audit)
        self.assertEqual(
            [attempt.outcome for attempt in self.ledger.attempts],
            ["node-rejected", "root-accepted"],
        )

    def test_missing_historical_node_refuses_before_any_cas_traversal(self):
        missing = self.ledger.attempts[0].node_lifecycle_result_identity
        self.recorder._records.pop(missing)
        with mock.patch.object(self.source.cas, "path_for") as read:
            with self.assertRaises(QualificationCaptureError):
                self.capture()
            read.assert_not_called()

    def test_missing_historical_source_output_refuses(self):
        self.recorder._records.pop(self.outputs[0].identity)
        with self.assertRaises(QualificationCaptureError):
            self.capture()

    def test_hash_valid_node_with_wrong_source_output_refuses(self):
        self.documents = (
            {**self.documents[0], "source_output": self.outputs[1].to_dict()},
            self.documents[1],
        )
        self.seal_history()
        with self.assertRaises(QualificationCaptureError):
            self.capture()

    def test_missing_first_source_manifest_in_actual_cas_refuses(self):
        reference = self.outputs[0].candidate.source_manifest_identity
        self.source.cas.path_for(BlobRef(reference.digest, 0)).unlink()
        with self.assertRaises(QualificationCaptureError):
            self.capture()

    def test_nonserialized_audit_must_match_exact_retained_lifecycle_identity(self):
        wrong = replace(
            self.audit,
            final_lifecycle_result_identity=canonical_identity("foreign lifecycle"),
        )
        self.recorder.remember_json(wrong.to_dict())
        object.__setattr__(self.lifecycle, "native_root_execution", wrong)
        with self.assertRaises(QualificationCaptureError):
            self.capture()

    def test_retained_source_cannot_be_relabelled_as_generated_history(self):
        first = self.outputs[0]
        provenance = replace(
            first.provenance,
            retained_source_identity=canonical_identity("original retained source"),
            route_decision_identities=(),
            model_stage_output_identities=(),
            provider_evidence_identities=(),
        )
        retained = replace(
            first, provenance=provenance, provenance_identity=provenance.identity
        )
        self.outputs = (retained, self.outputs[1])
        self.documents = (
            self.node_document(self.original, retained),
            self.documents[1],
        )
        self.seal_history()
        with mock.patch.object(self.source.cas, "path_for") as read:
            with self.assertRaises(QualificationCaptureError):
                self.capture()
            read.assert_not_called()

    def test_no_metadata_path_does_not_touch_original_cas(self):
        object.__setattr__(self.lifecycle, "native_root_execution", None)
        with mock.patch.object(
            self.source.cas, "path_for", side_effect=AssertionError("CAS touched")
        ):
            self.assertEqual(self.capture(), ())

    def test_existing_recorder_record_limit_is_enforced_during_bundle_capture(self):
        self.recorder.max_records = len(self.recorder.entries)
        with self.assertRaisesRegex(QualificationCaptureError, "record-limit"):
            self.capture()
