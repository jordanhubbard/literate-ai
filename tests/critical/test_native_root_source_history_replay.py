"""Real captured source bytes with modeled source production/transport authority.

No model or generated native command executes. Transport anchoring, ledger and
preparation eligibility are explicit test inputs; full history is not attested.
"""

import tempfile
import unittest
from contextlib import chdir
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import generation_preparation as planning
from literate_ai.adapters.generation_preparation import (
    FilesystemComponentWorkspaceAllocator,
    LockedComponentModelSelectionAdapter,
    LockedComponentNodePreparationAdapter,
)
from literate_ai.adapters.models.coding_cli import (
    CodingCliSelection,
    _planned_generation_prompt,
)
from literate_ai.adapters.native_root_preparation_replay import (
    ReopenedNativeRootPreparation,
    project_current_native_root_preparation,
)
from literate_ai.adapters.native_root_source_history_replay import (
    NativeRootSourceHistoryReplayError,
    NativeRootSourceReplayTransport,
    verify_closed_native_root_source_attempt,
)
from literate_ai.adapters.qualification_capture import (
    QualificationCaptureError,
    QualificationEvidenceReader,
    QualificationEvidenceRecorder,
    capture_qualification_source_records,
)
from literate_ai.adapters.source_generation import (
    CachedCodingCliSourceGenerationRunner,
    CodingCliSourceGenerationInvocation,
)
from literate_ai.adapters.standard_project import (
    FilesystemStandardProjectPlanningAdapter,
    FilesystemStandardSourceGenerationAdapter,
    _default_generation_budget,
    project_standard_source_invocation,
)
from literate_ai.application.component_generation_preparation import (
    ComponentGenerationWorkspaceDescriptor,
    PreparedComponentGenerationNode,
)
from literate_ai.application.standard_project_lifecycle import (
    StandardNodeLifecycleResult,
)
from literate_ai.contracts.executable_components import (
    SourceGenerationDisposition,
    SourceGenerationNodeResult,
)
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.storage import FileSystemCAS
from tests.critical import test_native_root_continuation_contracts as contracts
from tests.support import (
    fixtures_test_cached_coding_cli_source_generation_runner as source,
)
from tests.support.fixtures_test_standard_command_projection import _locked_snapshot


def _original_invocation_provider(adapter, snapshot, execution_plan):
    """Frozen pre-extraction producer block; compare actual original output bytes."""
    planner = planning.GenerationExecutionPlanningAdapter()

    def provide(node):
        recipe = node.recipe
        execution = planner.plan_node(
            snapshot,
            node,
            selection=adapter.generator.selection,
            model=recipe.model_for(adapter.generator.selection.name),
        )
        prior = {
            "component_revision": node.plan.component_revision.uri,
            "source_generation_request_identity": node.request.request.identity.uri,
            "component_generation_plan_identity": node.plan.identity.uri,
            "context_manifest_identity": (
                node.request.request.context_manifest_identity.uri
            ),
            "workspace_allocation_identity": node.workspace.allocation_identity.uri,
            "recipe_identity": recipe.identity,
            "generation_key_identity": node.plan.generation_key.identity.uri,
            "required_entrypoints": list(recipe.all_required_entrypoints),
            "direct_public_interface_identities": [
                item.uri
                for item in node.plan.generation_key.direct_public_interface_identities
            ],
        }
        if getattr(adapter, "project_authority_identity", None) is not None:
            prior["project_authority_identity"] = adapter.project_authority_identity.uri
        request = {
            "stage_id": execution.model_stages[-1].stage_id,
            "prior_stage_outputs": {"plan": prior},
            "input_identity": canonical_identity(prior).to_dict(),
        }
        return CodingCliSourceGenerationInvocation.create(
            execution,
            request,
            application_root_revision_identity=execution_plan.root_revision,
            readiness_identity=canonical_identity(
                {
                    "standard-source-readiness": node.plan.component_revision.uri,
                    "execution_plan": execution_plan.identity.uri,
                }
            ),
        )

    return provide


class _ModeledGenerator(source._FakeCachedGenerator):
    def __init__(self, selection):
        super().__init__()
        self.selection = selection

    def planned_request_identity(
        self, recipe, *, execution_plan, stage_request, bounded_prompt=None
    ):
        return canonical_identity(
            _planned_generation_prompt(
                recipe,
                execution_plan,
                stage_request,
                self.selection,
                bounded_prompt=bounded_prompt,
            )
        )


class NativeRootSourceHistoryReplayTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        _component, snapshot, _ = _locked_snapshot(self.root, generation_ready=True)
        self.provider = "codex"
        execution = FilesystemStandardProjectPlanningAdapter().plan_for_coding_cli(
            snapshot, coding_cli=self.provider
        )
        self.current = project_current_native_root_preparation(
            snapshot=snapshot,
            execution_plan=execution,
            provider_id=self.provider,
            pipeline_model=None,
            budget_selector=_default_generation_budget,
        )
        plan = self.current.generation_plan
        projection = LockedComponentNodePreparationAdapter(
            model_selector=LockedComponentModelSelectionAdapter(),
            coding_cli=self.provider,
        ).project(snapshot, plan)
        locator = self.root / "never-opened-historical-workspace"
        allocation = canonical_identity(
            {
                "schema": "literate-ai/component-workspace-allocation@1",
                "component_revision": plan.component_revision.uri,
                "generation_plan_identity": plan.identity.uri,
                "locator": str(locator),
            }
        )
        self.workspace = ComponentGenerationWorkspaceDescriptor(
            plan.component_revision,
            plan.identity,
            plan.generation_key.identity,
            allocation,
            str(locator),
        )
        self.prepared = PreparedComponentGenerationNode(
            plan,
            projection.definition,
            projection.recipe,
            self.current.original,
            self.workspace,
        )
        self.selection = CodingCliSelection(
            self.provider, "/nonexistent/modeled-codex", "sha256:" + "e" * 64
        )
        self.transport = NativeRootSourceReplayTransport(
            self.provider,
            ContentIdentity.parse_uri(self.selection.executable_identity),
            self.selection.isolation,
        )
        self.authority = canonical_identity("independently-modeled-current-approval")
        fixture = contracts.NativeRootContinuationContractTests()
        fixture.setUp()
        self.run = replace(
            fixture.run,
            project_authority_identity=self.authority,
            component_lock_identity=execution.component_lock_identity,
            execution_plan_identity=execution.identity,
            root_revision=execution.root_revision,
            original_generation_plan_identity=plan.identity,
            original_recipe_identity=self.current.recipe_identity,
            original_bounded_request_identity=self.current.original.request.identity,
            qualified_dependency_binding_identities=(),
        )
        self.attempt_template = fixture.root0
        self.cas = FileSystemCAS(self.root / "captured-cas")
        self.invocation = self.project()
        self.output = self.capture(self.invocation)
        self.node = self.node_for(self.output)
        self.attempt = replace(
            fixture.root0,
            run_binding_identity=self.run.identity,
            bounded_generation_request_identity=self.current.original.request.identity,
            workspace_allocation_identity=allocation,
            source_output_identity=self.output.identity,
            node_lifecycle_result_identity=self.node.identity,
        )
        self.preparation = ReopenedNativeRootPreparation(
            self.current.original.request, self.current.original.prompt, self.workspace
        )

    def project(self, **changes):
        kwargs = dict(
            selection=self.transport,
            project_authority_identity=self.authority,
            approved_project_root=self.root,
        )
        kwargs.update(changes)
        return project_standard_source_invocation(
            self.current.snapshot, self.current.execution_plan, self.prepared, **kwargs
        )

    def capture(self, invocation, *, planned_override=None):
        generator = _ModeledGenerator(self.selection)
        with tempfile.TemporaryDirectory(dir=self.root) as generated_root:
            generated = generator.generate(
                self.prepared.recipe,
                output_root=Path(generated_root),
                execution_plan=invocation.execution_plan,
                stage_request=invocation.stage_request,
                bounded_prompt=self.prepared.request.prompt,
            )
        generated = replace(
            generated,
            model=self.prepared.recipe.model_for(self.provider),
            coding_cli_tool_binding_identity=self.transport.tool_binding_identity,
        )
        planned = generator.planned_request_identity(
            self.prepared.recipe,
            execution_plan=invocation.execution_plan,
            stage_request=invocation.stage_request,
            bounded_prompt=self.prepared.request.prompt,
        )
        if planned_override is not None:
            planned = planned_override
            generated = replace(generated, request_identity=planned.uri)
        runner = CachedCodingCliSourceGenerationRunner(
            generator, cas=self.cas, invocation_provider=lambda _node: invocation
        )
        return runner._record(
            self.prepared, invocation, generated, planned_request_identity=planned
        )

    def node_for(self, output):
        request = self.current.original.request
        source_result = SourceGenerationNodeResult(
            self.current.generation_plan.component_revision,
            self.current.generation_plan.identity,
            self.current.generation_plan.generation_key.identity,
            request.context_manifest_identity,
            request.budget.identity,
            request.budget_decision.identity,
            request.prompt_identity,
            self.current.recipe_identity,
            self.workspace.allocation_identity,
            SourceGenerationDisposition.GENERATED,
            output.candidate_identity,
            output.provenance_identity,
            output.runtime_observation,
            None,
        )
        return StandardNodeLifecycleResult(
            source_result.component_revision,
            source_result,
            output,
            None,
            (),
            None,
            None,
            None,
            None,
            None,
            None,
        )

    def reader(self, *, node=None, omit=()):
        node = self.node if node is None else node
        recorder = QualificationEvidenceRecorder(max_bytes=10_000_000, max_records=1000)
        capture_qualification_source_records(
            recorder, candidate=node.source_output.candidate, cas=self.cas
        )
        recorder.remember_json(
            {
                "schema": "literate-ai/coding-cli-tool-binding@1",
                "coding_cli": self.selection.name,
                "executable_identity": self.selection.executable_identity,
                "isolation": self.selection.isolation.to_dict(),
            }
        )
        recorder.remember_json(node.identity_document())
        recorder.remember_json(self.preparation.request.to_dict())
        recorder.remember_bytes(self.preparation.prompt)
        return QualificationEvidenceReader(
            tuple(entry for entry in recorder.entries if entry[0] not in omit),
            max_bytes=10_000_000,
            max_records=1000,
        )

    def verify(self, **changes):
        kwargs = dict(
            current=self.current,
            run=self.run,
            attempt=self.attempt,
            preparation=self.preparation,
            expected_tool_binding_identity=ContentIdentity.parse_uri(
                self.transport.tool_binding_identity
            ),
            provider_id=self.provider,
            pipeline_model=None,
            approved_project_root=self.root,
            approved_project_authority_identity=self.authority,
        )
        reader = changes.pop("reader", None)
        kwargs.update(changes)
        return verify_closed_native_root_source_attempt(
            self.reader() if reader is None else reader, **kwargs
        )

    def test_real_captured_source_reopens_without_provider_or_workspace_access(self):
        with (
            mock.patch.object(
                FilesystemComponentWorkspaceAllocator,
                "allocate",
                side_effect=AssertionError("replay allocation"),
            ),
            mock.patch.object(
                CodingCliSelection,
                "require_unchanged",
                side_effect=AssertionError("replay live executable guard"),
            ),
        ):
            self.assertEqual(self.verify(), self.node)
        self.assertFalse(Path(self.workspace.locator).exists())
        self.assertEqual(
            self.transport.provenance_status, "independent-transport-anchor-required"
        )

    def test_original_producer_invocation_and_planned_prompt_bytes_are_unchanged(self):
        adapter = FilesystemStandardSourceGenerationAdapter.__new__(
            FilesystemStandardSourceGenerationAdapter
        )
        adapter.generator = SimpleNamespace(selection=self.selection)
        for authority in (None, self.authority):
            adapter.project_authority_identity = authority
            original = _original_invocation_provider(
                adapter, self.current.snapshot, self.current.execution_plan
            )(self.prepared)
            extracted = adapter._invocation_provider(
                self.current.snapshot, self.current.execution_plan
            )(self.prepared)
            self.assertEqual(
                original.identity_document(), extracted.identity_document()
            )
            self.assertEqual(
                original.execution_plan.to_dict(), extracted.execution_plan.to_dict()
            )
            self.assertEqual(
                _planned_generation_prompt(
                    self.prepared.recipe,
                    original.execution_plan,
                    original.stage_request,
                    self.selection,
                    bounded_prompt=self.prepared.request.prompt,
                ),
                _planned_generation_prompt(
                    self.prepared.recipe,
                    extracted.execution_plan,
                    extracted.stage_request,
                    self.transport,
                    bounded_prompt=self.prepared.request.prompt,
                ),
            )

    def test_explicit_workflow_root_is_cwd_independent(self):
        other = self.root / "unrelated-cwd"
        other.mkdir()
        with (
            mock.patch.object(
                planning,
                "_nearest_project_root",
                side_effect=AssertionError("ambient project root used"),
            ),
            mock.patch.object(
                planning,
                "compile_generation_execution_plan",
                wraps=planning.compile_generation_execution_plan,
            ) as compile_plan,
        ):
            with chdir(self.root):
                first = self.project()
            with chdir(other):
                second = self.project()
            self.assertEqual(first.identity_document(), second.identity_document())
            self.assertEqual(
                first.execution_plan.to_dict(), second.execution_plan.to_dict()
            )
            self.assertTrue(compile_plan.call_args_list)
            self.assertTrue(
                all(
                    call.kwargs["project_root"] == self.root
                    for call in compile_plan.call_args_list
                )
            )

    def test_raw_executable_and_approved_authority_substitution_refuse(self):
        with self.assertRaises(
            (NativeRootSourceHistoryReplayError, QualificationCaptureError)
        ):
            self.verify(
                expected_tool_binding_identity=canonical_identity("other-binding")
            )
        with self.assertRaisesRegex(
            NativeRootSourceHistoryReplayError, "context_changed"
        ):
            self.verify(
                approved_project_authority_identity=canonical_identity("foreign")
            )

    def test_exact_public_prompt_bytes_and_source_blobs_are_required(self):
        binding = ContentIdentity.parse_uri(self.transport.tool_binding_identity)
        with self.assertRaisesRegex(QualificationCaptureError, "record-missing"):
            self.verify(reader=self.reader(omit=(binding,)))
        reader = self.reader()
        reader._records[self.preparation.request.prompt_identity] = (
            b"changed public prompt"
        )
        with self.assertRaisesRegex(
            NativeRootSourceHistoryReplayError, "public_request_changed"
        ):
            self.verify(reader=reader)
        reader = self.reader(omit=(self.output.candidate.source_bom_identity,))
        with self.assertRaisesRegex(QualificationCaptureError, "record-missing"):
            self.verify(reader=reader)

    def test_reused_or_retained_source_disposition_cannot_select_generated_route(self):
        for disposition in (
            SourceGenerationDisposition.REUSED,
            SourceGenerationDisposition.RETAINED,
        ):
            node = replace(
                self.node,
                source_generation=replace(
                    self.node.source_generation,
                    disposition=disposition,
                    runtime_observation=None,
                ),
            )
            attempt = replace(
                self.attempt, node_lifecycle_result_identity=node.identity
            )
            with (
                self.subTest(disposition=disposition),
                self.assertRaisesRegex(
                    NativeRootSourceHistoryReplayError, "generated_origin_required"
                ),
            ):
                self.verify(reader=self.reader(node=node), attempt=attempt)

    def test_typed_node_context_and_recorded_attempt_identity_must_match(self):
        node = replace(
            self.node,
            source_generation=replace(
                self.node.source_generation,
                complexity_budget_identity=canonical_identity("foreign-budget"),
            ),
        )
        with self.assertRaisesRegex(
            NativeRootSourceHistoryReplayError, "source_context_changed"
        ):
            self.verify(
                reader=self.reader(node=node),
                attempt=replace(
                    self.attempt, node_lifecycle_result_identity=node.identity
                ),
            )
        with self.assertRaisesRegex(
            NativeRootSourceHistoryReplayError, "generated_origin_required"
        ):
            self.verify(
                attempt=replace(
                    self.attempt,
                    source_output_identity=canonical_identity("foreign-output"),
                )
            )

    def test_coherently_captured_foreign_stage_input_refuses_current_invocation(self):
        request = self.invocation.stage_request
        prior = dict(request["prior_stage_outputs"]["plan"])
        prior["required_entrypoints"] = ["source/unapproved.py"]
        request["prior_stage_outputs"] = {"plan": prior}
        request["input_identity"] = canonical_identity(prior).to_dict()
        invocation = CodingCliSourceGenerationInvocation.create(
            self.invocation.execution_plan,
            request,
            application_root_revision_identity=(
                self.invocation.application_root_revision_identity
            ),
            readiness_identity=self.invocation.readiness_identity,
        )
        output = self.capture(invocation)
        node = self.node_for(output)
        attempt = replace(
            self.attempt,
            source_output_identity=output.identity,
            node_lifecycle_result_identity=node.identity,
        )
        with self.assertRaisesRegex(
            NativeRootSourceHistoryReplayError, "invocation_changed"
        ):
            self.verify(reader=self.reader(node=node), attempt=attempt)

    def test_retained_provenance_and_missing_transport_do_not_gain_generated_authority(
        self,
    ):
        provenance = replace(
            self.output.provenance,
            retained_source_identity=canonical_identity("operator-retained-source"),
            route_decision_identities=(),
            model_stage_output_identities=(),
            provider_evidence_identities=(),
        )
        output = replace(
            self.output,
            provenance=provenance,
            provenance_identity=provenance.identity,
        )
        node = self.node_for(output)
        with self.assertRaisesRegex(
            NativeRootSourceHistoryReplayError, "generated_origin_required"
        ):
            self.verify(
                reader=self.reader(node=node),
                attempt=replace(
                    self.attempt,
                    source_output_identity=output.identity,
                    node_lifecycle_result_identity=node.identity,
                ),
            )
        with self.assertRaises(TypeError):
            self.verify(expected_tool_binding_identity=None)

    def test_coherent_foreign_planned_prompt_commitment_refuses_exact_public_prompt(
        self,
    ):
        output = self.capture(
            self.invocation,
            planned_override=canonical_identity("foreign-planned-prompt"),
        )
        node = self.node_for(output)
        with self.assertRaisesRegex(
            NativeRootSourceHistoryReplayError, "planned_transport_changed"
        ):
            self.verify(
                reader=self.reader(node=node),
                attempt=replace(
                    self.attempt,
                    source_output_identity=output.identity,
                    node_lifecycle_result_identity=node.identity,
                ),
            )
